"""
Auth Service — Microservice d'authentification
PFA 2025-2026 : Centralisation des Logs pour la Détection d'Incidents de Sécurité
"""

import os
import re
import json
import time
import random
import threading
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from flask import Flask, request, jsonify
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter
import jwt

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

# Brute-force counters (keyed on real IP)
failed_attempts = defaultdict(int)
lock = threading.Lock()

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


@app.route('/login', methods=['POST'])
def login():
    """Authenticate user and return a signed JWT on success."""
    data = request.get_json(silent=True) or {}
    username = sanitize_input(data.get('username', 'unknown'))
    password = data.get('password', '')
    client_ip = get_client_ip()

    time.sleep(random.uniform(0.05, 0.2))

    if VALID_USERS.get(username) == password:
        with lock:
            failed_attempts[client_ip] = 0

        payload = {
            'sub': username,
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
    with lock:
        failed_attempts[client_ip] += 1
        count = failed_attempts[client_ip]

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

    if brute_force:
        brute_force_total.labels(ip=client_ip).inc()
        log_event('CRITICAL', f'BRUTE FORCE ATTACK detected from IP {client_ip}', {
            'ip': client_ip, 'failed_attempts': count,
            'event_type': 'brute_force'
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


if __name__ == '__main__':
    log_event('INFO', f'{SERVICE_NAME} starting on port 5001', {
        'event_type': 'service_start', 'port': 5001
    })
    app.run(host='0.0.0.0', port=5001, debug=False)
