"""
Auth Service — Microservice d'authentification
PFA 2025-2026 : Centralisation des Logs pour la Détection d'Incidents de Sécurité
"""

import os
import re
import json
import time
import queue
import random
import threading
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from flask import Flask, request, jsonify, Response, stream_with_context
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter
import jwt
import redis as redis_lib

app = Flask(__name__)

# ── Prometheus metrics ────────────────────────────────────
metrics = PrometheusMetrics(app, default_labels={'service': 'auth-service'})
metrics.info('auth_service_info', 'Auth Service metadata', version='1.0')

auth_failures_total = Counter(
    'auth_failures_total', 'Total authentication failures', ['ip']
)
brute_force_total = Counter(
    'brute_force_total', 'Brute force attacks detected', ['ip']
)

SERVICE_NAME = os.environ.get('SERVICE_NAME', 'auth-service')
LOG_FILE = '/app/logs/auth-service.log'

# JWT — secret must be set via environment variable in production
JWT_SECRET = os.environ.get('JWT_SECRET', 'change-me-in-production-minimum-32chars!')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRY_HOURS = 1

# ── Redis (persistent brute-force counters) ──────────────────
_redis = None
_redis_lock = threading.Lock()

def get_redis():
    global _redis
    if _redis is not None:
        return _redis
    with _redis_lock:
        if _redis is None:
            try:
                r = redis_lib.Redis(
                    host=os.environ.get('REDIS_HOST', 'redis'),
                    port=int(os.environ.get('REDIS_PORT', 6379)),
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                )
                r.ping()
                _redis = r
            except Exception:
                pass
    return _redis

BF_PREFIX = 'bf:'
BF_WINDOW  = 3600  # 1 h sliding window

def incr_failure(ip: str) -> int:
    r = get_redis()
    if r:
        try:
            key = BF_PREFIX + ip
            count = r.incr(key)
            if count == 1:
                r.expire(key, BF_WINDOW)
            return count
        except Exception:
            pass
    # fallback: in-memory
    with lock:
        failed_attempts[ip] += 1
        return failed_attempts[ip]

def reset_failure(ip: str):
    r = get_redis()
    if r:
        try:
            r.delete(BF_PREFIX + ip)
            return
        except Exception:
            pass
    with lock:
        failed_attempts[ip] = 0

# In-memory fallback (used when Redis is unreachable)
failed_attempts = defaultdict(int)
lock = threading.Lock()

# ── SSE client registry ───────────────────────────────────────
_sse_clients: list = []
_sse_lock = threading.Lock()

def push_sse(data: dict):
    """Push a JSON event to all active SSE clients; prune disconnected ones."""
    msg = 'data: ' + json.dumps(data) + '\n\n'
    with _sse_lock:
        alive = []
        for q in _sse_clients:
            try:
                q.put_nowait(msg)
                alive.append(q)
            except queue.Full:
                pass  # slow client — drop silently, it will reconnect
        _sse_clients[:] = alive

VALID_USERS = {
    'admin':    os.environ.get('DEMO_ADMIN_PASSWORD',    'Admin@SecureWatch2026!'),
    'user1':    os.environ.get('DEMO_USER1_PASSWORD',    'User1@PFA2026!'),
    'operator': os.environ.get('DEMO_OPERATOR_PASSWORD', 'Operator@PFA2026!'),
}


def sanitize_input(value: str, max_length: int = 64) -> str:
    """Strip ASCII control characters and limit length to prevent log injection."""
    return re.sub(r'[\x00-\x1f\x7f]', '', str(value))[:max_length]


def get_client_ip() -> str:
    """Return the real client IP.

    X-Real-IP is set by nginx to $remote_addr (the connecting client) and
    cannot be spoofed through the gateway, unlike X-Forwarded-For.
    """
    return request.headers.get('X-Real-IP', request.remote_addr)


def log_event(level: str, message: str, extra: dict = None):
    """Write a structured JSON log entry."""
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "service": SERVICE_NAME,
        "message": message,
    }
    if extra:
        entry.update(extra)

    log_line = json.dumps(entry)
    print(log_line, flush=True)

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_line + '\n')


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    log_event('INFO', 'Health check OK', {
        'endpoint': '/health', 'status': 200, 'event_type': 'health_check'
    })
    return jsonify({'status': 'healthy', 'service': SERVICE_NAME}), 200


@app.route('/events/stream')
def event_stream():
    """Server-Sent Events — real-time security alerts for authorised clients.

    EventSource cannot send custom headers, so the JWT is passed as ?token=
    (acceptable for a dev/demo environment).
    """
    token = request.args.get('token', '')
    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return jsonify({'error': 'Invalid or expired token'}), 401

    q: queue.Queue = queue.Queue(maxsize=50)
    with _sse_lock:
        _sse_clients.append(q)

    def generate():
        try:
            yield ': connected\n\n'       # opens the HTTP stream immediately
            while True:
                try:
                    yield q.get(timeout=20)
                except queue.Empty:
                    yield ': keepalive\n\n'  # prevent proxy/browser timeout
        finally:
            with _sse_lock:
                try:
                    _sse_clients.remove(q)
                except ValueError:
                    pass

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',   # disable nginx proxy buffering
        }
    )


@app.route('/login', methods=['POST'])
def login():
    """Authenticate user and return a signed JWT on success."""
    data = request.get_json(silent=True) or {}
    username = sanitize_input(data.get('username', 'unknown'))
    password = data.get('password', '')
    client_ip = get_client_ip()

    time.sleep(random.uniform(0.05, 0.2))

    if VALID_USERS.get(username) == password:
        reset_failure(client_ip)

        role_map = {'admin': 'admin', 'operator': 'operator'}
        payload = {
            'sub': username,
            'role': role_map.get(username, 'user'),
            'iat': datetime.now(timezone.utc),
            'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        log_event('INFO', f'Authentication successful for user {username}', {
            'user': username, 'ip': client_ip,
            'endpoint': '/login', 'status': 200,
            'event_type': 'auth_success'
        })
        return jsonify({'token': token, 'user': username}), 200

    # ── Failed attempt ──────────────────────────────────────
    count = incr_failure(client_ip)

    level = 'CRITICAL' if count >= 5 else 'WARNING'
    brute_force = count >= 5

    auth_failures_total.labels(ip=client_ip).inc()
    log_event(level, f'Authentication failed for user {username}', {
        'user': username, 'ip': client_ip,
        'endpoint': '/login', 'status': 401,
        'event_type': 'auth_failure',
        'failed_attempts': count,
        'brute_force_suspected': brute_force
    })

    # Push auth_failure to SSE subscribers for real-time dashboard update
    push_sse({
        'type': 'auth_failure',
        'ip': client_ip,
        'count': count,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
    })

    if brute_force:
        brute_force_total.labels(ip=client_ip).inc()
        log_event('CRITICAL', f'BRUTE FORCE ATTACK detected from IP {client_ip}', {
            'ip': client_ip, 'failed_attempts': count,
            'event_type': 'brute_force'
        })
        push_sse({
            'type': 'brute_force',
            'ip': client_ip,
            'count': count,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        })

    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/logout', methods=['POST'])
def logout():
    client_ip = get_client_ip()
    username = sanitize_input(request.headers.get('X-User', 'unknown'))
    log_event('INFO', f'User {username} logged out', {
        'user': username, 'ip': client_ip,
        'endpoint': '/logout', 'status': 200,
        'event_type': 'logout'
    })
    return jsonify({'message': 'Logged out successfully'}), 200


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username = sanitize_input(data.get('username', 'unknown'))
    client_ip = get_client_ip()
    log_event('INFO', f'User registration for {username}', {
        'user': username, 'ip': client_ip,
        'endpoint': '/register', 'status': 201,
        'event_type': 'registration'
    })
    return jsonify({'message': 'User registered successfully'}), 201


@app.route('/validate', methods=['GET', 'POST'])
def validate_token():
    """Used by nginx auth_request to validate JWT — returns 200 or 401."""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'error': 'No token'}), 401
    try:
        jwt.decode(auth[7:], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return jsonify({'status': 'valid'}), 200
    except jwt.PyJWTError:
        return jsonify({'error': 'Invalid or expired token'}), 401


if __name__ == '__main__':
    log_event('INFO', f'{SERVICE_NAME} starting on port 5001', {
        'event_type': 'service_start', 'port': 5001
    })
    app.run(host='0.0.0.0', port=5001, debug=False)
