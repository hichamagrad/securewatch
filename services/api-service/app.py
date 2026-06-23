"""
API Service — Microservice API principale
PFA 2025-2026 : Centralisation des Logs pour la Détection d'Incidents de Sécurité
"""

import os
import re
import json
import random
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter
import jwt
import redis as redis_lib

app = Flask(__name__)

# ── Prometheus metrics ────────────────────────────────────
metrics = PrometheusMetrics(app, default_labels={'service': 'api-service'})
metrics.info('api_service_info', 'API Service metadata', version='1.0')

forbidden_access_total = Counter(
    'forbidden_access_total', 'Total forbidden access attempts', ['endpoint']
)
server_errors_total = Counter(
    'server_errors_total', 'Total 500 Internal Server Errors', ['endpoint']
)
scanner_ua_total = Counter(
    'scanner_ua_total', 'Total scanner/offensive tool detections'
)
geo_anomaly_total = Counter(
    'geo_anomaly_total', 'Total geographic anomaly detections'
)

SERVICE_NAME = os.environ.get('SERVICE_NAME', 'api-service')
LOG_FILE = '/app/logs/api-service.log'

# ── Security detection patterns ───────────────────────────────
SCANNER_UAS = re.compile(
    r"(sqlmap|nikto|nessus|masscan|nmap\s|zgrab|openvas|dirbuster|"
    r"nuclei|gobuster|ffuf|wfuzz|burpsuite|acunetix|w3af|arachni)",
    re.IGNORECASE,
)

# IP prefixes mapped to (country_code, country_name)
_GEO_SUSPICIOUS = {
    "195.154.": ("RU", "Russia"),
    "91.121.":  ("RU", "Russia"),
    "103.235.": ("CN", "China"),
    "175.45.176.": ("KP", "North Korea"),
    "5.61.":    ("IR", "Iran"),
    "185.220.": ("TOR", "Tor Exit Node"),
    "162.247.": ("TOR", "Tor Exit Node"),
    "41.223.":  ("NG", "Nigeria"),
}


def _geo_lookup(ip: str):
    for prefix, info in _GEO_SUSPICIOUS.items():
        if ip.startswith(prefix):
            return info
    return None, None

# JWT — must match the secret used by auth-service
JWT_SECRET = os.environ.get('JWT_SECRET', 'change-me-in-production-minimum-32chars!')
JWT_ALGORITHM = 'HS256'

# ── Redis (persistent webhook alert store) ───────────────────
_redis = None
_redis_lock = threading.Lock()
WEBHOOK_KEY = 'webhook_alerts'
WEBHOOK_MAX = 100

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

USERS_DATA = [
    {'id': 1, 'name': 'Alice Martin',  'role': 'admin',    'email': 'alice@pfa.local'},
    {'id': 2, 'name': 'Bob Dupont',    'role': 'user',     'email': 'bob@pfa.local'},
    {'id': 3, 'name': 'Carol Simon',   'role': 'operator', 'email': 'carol@pfa.local'},
    {'id': 4, 'name': 'David Leroy',   'role': 'user',     'email': 'david@pfa.local'},
]

SAFE_CONTENT_TYPES = [
    'application/json',
    'multipart/form-data',
    'text/plain',
    'application/pdf',
]


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


def _decode_jwt(req):
    """Return decoded JWT payload or None."""
    auth = req.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    try:
        return jwt.decode(auth[7:], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def is_authorized(req) -> bool:
    """Validate a signed JWT Bearer token (signature + expiry)."""
    return _decode_jwt(req) is not None


def get_role(req) -> str:
    """Return the role claim from the JWT, or empty string if unauthenticated."""
    payload = _decode_jwt(req)
    return payload.get('role', 'user') if payload else ''


def require_roles(req, allowed: list):
    """Check JWT validity then role membership.

    Returns (ok: bool, http_status: int).
    Callers should return 401 if not is_authorized, 403 if wrong role.
    """
    payload = _decode_jwt(req)
    if payload is None:
        return False, 401
    if payload.get('role', 'user') not in allowed:
        return False, 403
    return True, 200


def get_client_ip() -> str:
    """Return the real client IP.

    X-Real-IP is set by nginx to $remote_addr and cannot be spoofed
    through the gateway, unlike X-Forwarded-For.
    """
    return request.headers.get('X-Real-IP', request.remote_addr)


# ─── Security middleware ────────────────────────────────────────────────────────

@app.before_request
def detect_threats():
    ip = get_client_ip()
    ua = request.headers.get('User-Agent', '')

    # Scanner / offensive tool detection
    if ua and SCANNER_UAS.search(ua):
        safe_ua = re.sub(r'[\x00-\x1f\x7f]', '', ua)[:200]
        log_event('WARNING', f'Scanner/offensive tool detected from {ip}: {safe_ua[:80]}', {
            'ip': ip, 'endpoint': request.path, 'method': request.method,
            'event_type': 'suspicious_ua', 'user_agent': safe_ua,
        })
        scanner_ua_total.inc()

    # Geographic anomaly — check first hop of X-Forwarded-For
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        first_ip = xff.split(',')[0].strip()
        country_code, country_name = _geo_lookup(first_ip)
        if country_code:
            log_event('WARNING',
                      f'Geographic anomaly: request from {country_name} ({country_code}) via {first_ip}', {
                          'ip': ip, 'claimed_ip': first_ip,
                          'country_code': country_code, 'country_name': country_name,
                          'endpoint': request.path, 'method': request.method,
                          'event_type': 'geo_anomaly',
                      })
            geo_anomaly_total.inc()


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': SERVICE_NAME}), 200


@app.route('/api/users', methods=['GET'])
def get_users():
    """Admin + Operator only."""
    ip = get_client_ip()
    ok, code = require_roles(request, ['admin', 'operator'])
    if not ok:
        event = 'unauthorized_access' if code == 401 else 'forbidden_access'
        log_event('WARNING', f'{code} — /api/users denied (role: {get_role(request)})', {
            'ip': ip, 'endpoint': '/api/users', 'method': 'GET',
            'status': code, 'event_type': event, 'role': get_role(request)
        })
        msg = 'Unauthorized — Bearer token required' if code == 401 else 'Forbidden — Operator or Admin role required'
        return jsonify({'error': msg}), code

    log_event('INFO', 'GET /api/users — 200 OK', {
        'ip': ip, 'endpoint': '/api/users', 'method': 'GET',
        'status': 200, 'event_type': 'api_access',
        'records': len(USERS_DATA), 'role': get_role(request)
    })
    return jsonify({'users': USERS_DATA, 'total': len(USERS_DATA)}), 200


@app.route('/api/admin', methods=['GET'])
def get_admin():
    ip = get_client_ip()
    forbidden_access_total.labels(endpoint='/api/admin').inc()
    log_event('WARNING', '403 Forbidden — Unauthorized access to admin panel', {
        'ip': ip, 'endpoint': '/api/admin',
        'method': 'GET', 'status': 403,
        'event_type': 'forbidden_access'
    })
    return jsonify({'error': 'Forbidden — Admin access required'}), 403


@app.route('/api/config', methods=['GET'])
def get_config():
    ip = get_client_ip()
    forbidden_access_total.labels(endpoint='/api/config').inc()
    log_event('WARNING', '403 Forbidden — Access to /api/config denied', {
        'ip': ip, 'endpoint': '/api/config',
        'method': 'GET', 'status': 403,
        'event_type': 'forbidden_access'
    })
    return jsonify({'error': 'Forbidden'}), 403


@app.route('/api/data', methods=['GET'])
def get_data():
    """All authenticated roles (admin, operator, user)."""
    ip = get_client_ip()

    if not is_authorized(request):
        log_event('WARNING', '401 Unauthorized — /api/data', {
            'ip': ip, 'endpoint': '/api/data',
            'method': 'GET', 'status': 401,
            'event_type': 'unauthorized_access'
        })
        return jsonify({'error': 'Unauthorized'}), 401

    if random.random() < 0.10:
        server_errors_total.labels(endpoint='/api/data').inc()
        log_event('ERROR', '500 Internal Server Error on /api/data', {
            'ip': ip, 'endpoint': '/api/data',
            'method': 'GET', 'status': 500,
            'event_type': 'server_error',
            'error_detail': 'Database connection timeout'
        })
        return jsonify({'error': 'Internal Server Error'}), 500

    records = random.randint(10, 500)
    log_event('INFO', f'GET /api/data — 200 OK ({records} records)', {
        'ip': ip, 'endpoint': '/api/data',
        'method': 'GET', 'status': 200,
        'event_type': 'api_access', 'records': records
    })
    return jsonify({'data': 'Business data payload', 'records': records}), 200


@app.route('/api/upload', methods=['POST'])
def upload():
    """Admin + Operator only — rejects suspicious content types."""
    ip = get_client_ip()

    ok, code = require_roles(request, ['admin', 'operator'])
    if not ok:
        event = 'unauthorized_access' if code == 401 else 'forbidden_access'
        log_event('WARNING', f'{code} — /api/upload denied (role: {get_role(request)})', {
            'ip': ip, 'endpoint': '/api/upload', 'method': 'POST',
            'status': code, 'event_type': event, 'role': get_role(request)
        })
        msg = 'Unauthorized — Bearer token required' if code == 401 else 'Forbidden — Operator or Admin role required'
        return jsonify({'error': msg}), code

    content_type = request.content_type or 'unknown'
    content_length = request.content_length or 0
    suspicious = not any(ct in content_type for ct in SAFE_CONTENT_TYPES)

    if suspicious:
        log_event('WARNING', f'POST /api/upload — suspicious content_type rejected: {content_type}', {
            'ip': ip, 'endpoint': '/api/upload',
            'method': 'POST', 'status': 415,
            'content_type': content_type, 'content_length': content_length,
            'event_type': 'suspicious_upload', 'suspicious': True
        })
        return jsonify({'error': 'Unsupported Media Type', 'suspicious': True}), 415

    log_event('INFO', f'POST /api/upload — content_type={content_type}', {
        'ip': ip, 'endpoint': '/api/upload',
        'method': 'POST', 'status': 200,
        'content_type': content_type, 'content_length': content_length,
        'event_type': 'file_upload', 'suspicious': False
    })
    return jsonify({'message': 'Upload received', 'suspicious': False}), 200


@app.route('/api/reports', methods=['GET'])
def get_reports():
    """Admin + Operator only."""
    ip = get_client_ip()
    ok, code = require_roles(request, ['admin', 'operator'])
    if not ok:
        event = 'unauthorized_access' if code == 401 else 'forbidden_access'
        log_event('WARNING', f'{code} — /api/reports denied (role: {get_role(request)})', {
            'ip': ip, 'endpoint': '/api/reports', 'method': 'GET',
            'status': code, 'event_type': event, 'role': get_role(request)
        })
        msg = 'Unauthorized' if code == 401 else 'Forbidden — Operator or Admin role required'
        return jsonify({'error': msg}), code

    log_event('INFO', 'GET /api/reports — 200 OK', {
        'ip': ip, 'endpoint': '/api/reports',
        'method': 'GET', 'status': 200,
        'event_type': 'api_access'
    })
    return jsonify({'reports': ['report_2026_05.pdf', 'report_2026_04.pdf']}), 200


@app.route('/api/alerts/webhook', methods=['POST'])
def alerts_webhook():
    """Receives Alertmanager webhook POSTs — no auth required (internal network only)."""
    data = request.get_json(silent=True) or {}
    ip = get_client_ip()
    incoming = data.get('alerts', [])

    r = get_redis()
    for alert in incoming:
        entry = json.dumps({
            'status':   alert.get('status', 'unknown'),
            'name':     alert.get('labels', {}).get('alertname', ''),
            'severity': alert.get('labels', {}).get('severity', 'info'),
            'category': alert.get('labels', {}).get('category', ''),
            'summary':  alert.get('annotations', {}).get('summary', ''),
            'starts_at': alert.get('startsAt', ''),
        })
        if r:
            try:
                r.lpush(WEBHOOK_KEY, entry)
                r.ltrim(WEBHOOK_KEY, 0, WEBHOOK_MAX - 1)
            except Exception:
                pass

    log_event('INFO', f'Alertmanager webhook: {len(incoming)} alert(s) received', {
        'ip': ip, 'endpoint': '/api/alerts/webhook',
        'event_type': 'alertmanager_webhook', 'count': len(incoming)
    })
    return jsonify({'received': len(incoming)}), 200


@app.route('/api/alerts/pushed', methods=['GET'])
def get_pushed_alerts():
    """Admin + Operator only — returns Alertmanager webhook alerts (Redis-backed)."""
    ip = get_client_ip()
    ok, code = require_roles(request, ['admin', 'operator'])
    if not ok:
        event = 'unauthorized_access' if code == 401 else 'forbidden_access'
        log_event('WARNING', f'{code} — /api/alerts/pushed denied (role: {get_role(request)})', {
            'ip': ip, 'endpoint': '/api/alerts/pushed', 'method': 'GET',
            'status': code, 'event_type': event, 'role': get_role(request)
        })
        msg = 'Unauthorized' if code == 401 else 'Forbidden — Operator or Admin role required'
        return jsonify({'error': msg}), code

    r = get_redis()
    alerts = []
    if r:
        try:
            alerts = [json.loads(s) for s in r.lrange(WEBHOOK_KEY, 0, WEBHOOK_MAX - 1)]
        except Exception:
            pass
    return jsonify({'alerts': alerts}), 200


@app.errorhandler(404)
def not_found(e):
    ip = get_client_ip()
    log_event('WARNING', f'404 Not Found — {request.path}', {
        'ip': ip, 'endpoint': request.path,
        'method': request.method, 'status': 404,
        'event_type': 'not_found'
    })
    return jsonify({'error': 'Not found'}), 404


if __name__ == '__main__':
    log_event('INFO', f'{SERVICE_NAME} starting on port 5002', {
        'event_type': 'service_start', 'port': 5002
    })
    app.run(host='0.0.0.0', port=5002, debug=False)
