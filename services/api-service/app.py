"""
API Service — Microservice API principale
PFA 2025-2026 : Centralisation des Logs pour la Détection d'Incidents de Sécurité

Ce service expose des endpoints API et génère des logs de sécurité variés :
accès autorisés, accès interdits (403), erreurs système (500), uploads suspects.
"""

import os
import json
import random
from datetime import datetime
from flask import Flask, request, jsonify
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter

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

SERVICE_NAME = os.environ.get('SERVICE_NAME', 'api-service')
LOG_FILE = '/app/logs/api-service.log'

# Données simulées
USERS_DATA = [
    {'id': 1, 'name': 'Alice Martin', 'role': 'admin', 'email': 'alice@pfa.local'},
    {'id': 2, 'name': 'Bob Dupont', 'role': 'user', 'email': 'bob@pfa.local'},
    {'id': 3, 'name': 'Carol Simon', 'role': 'operator', 'email': 'carol@pfa.local'},
    {'id': 4, 'name': 'David Leroy', 'role': 'user', 'email': 'david@pfa.local'},
]


def log_event(level: str, message: str, extra: dict = None):
    """Écrit une entrée de log structurée en JSON."""
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


def is_authorized(req) -> bool:
    """Vérifie la présence d'un token Bearer dans l'en-tête Authorization."""
    auth = req.headers.get('Authorization', '')
    return auth.startswith('Bearer ')


def get_client_ip() -> str:
    return request.headers.get('X-Forwarded-For', request.remote_addr)


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': SERVICE_NAME}), 200


@app.route('/api/users', methods=['GET'])
def get_users():
    """Liste des utilisateurs — nécessite Authorization."""
    ip = get_client_ip()
    if not is_authorized(request):
        log_event('WARNING', '401 Unauthorized access to /api/users', {
            'ip': ip, 'endpoint': '/api/users',
            'method': 'GET', 'status': 401,
            'event_type': 'unauthorized_access'
        })
        return jsonify({'error': 'Unauthorized — Bearer token required'}), 401

    log_event('INFO', 'GET /api/users — 200 OK', {
        'ip': ip, 'endpoint': '/api/users',
        'method': 'GET', 'status': 200,
        'event_type': 'api_access', 'records': len(USERS_DATA)
    })
    return jsonify({'users': USERS_DATA, 'total': len(USERS_DATA)}), 200


@app.route('/api/admin', methods=['GET'])
def get_admin():
    """Panel d'administration — toujours refusé (403) pour démonstration."""
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
    """Configuration système — toujours refusé (403)."""
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
    """Données métier — génère aléatoirement différentes réponses pour la démo."""
    ip = get_client_ip()

    if not is_authorized(request):
        log_event('WARNING', '403 Forbidden — Access to /api/data denied', {
            'ip': ip, 'endpoint': '/api/data',
            'method': 'GET', 'status': 403,
            'event_type': 'forbidden_access'
        })
        return jsonify({'error': 'Forbidden'}), 403

    # 10 % de chance d'erreur serveur (simulation)
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
    """Upload de fichier — flagge les types suspects."""
    ip = get_client_ip()
    content_type = request.content_type or 'unknown'
    content_length = request.content_length or 0

    SAFE_TYPES = ['application/json', 'multipart/form-data',
                  'text/plain', 'application/pdf']
    suspicious = not any(ct in content_type for ct in SAFE_TYPES)

    level = 'WARNING' if suspicious else 'INFO'
    event_type = 'suspicious_upload' if suspicious else 'file_upload'

    log_event(level, f'POST /api/upload — content_type={content_type}', {
        'ip': ip, 'endpoint': '/api/upload',
        'method': 'POST', 'status': 200,
        'content_type': content_type,
        'content_length': content_length,
        'event_type': event_type, 'suspicious': suspicious
    })
    return jsonify({'message': 'Upload received', 'suspicious': suspicious}), 200


@app.route('/api/reports', methods=['GET'])
def get_reports():
    """Rapports — accessible avec token."""
    ip = get_client_ip()
    if not is_authorized(request):
        log_event('WARNING', '401 Unauthorized — /api/reports', {
            'ip': ip, 'endpoint': '/api/reports',
            'method': 'GET', 'status': 401,
            'event_type': 'unauthorized_access'
        })
        return jsonify({'error': 'Unauthorized'}), 401

    log_event('INFO', 'GET /api/reports — 200 OK', {
        'ip': ip, 'endpoint': '/api/reports',
        'method': 'GET', 'status': 200,
        'event_type': 'api_access'
    })
    return jsonify({'reports': ['report_2026_05.pdf', 'report_2026_04.pdf']}), 200


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
