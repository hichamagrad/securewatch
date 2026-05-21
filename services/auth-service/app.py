"""
Auth Service — Microservice d'authentification
PFA 2025-2026 : Centralisation des Logs pour la Détection d'Incidents de Sécurité

Ce service gère les authentifications et génère des logs structurés en JSON.
Les événements de sécurité (échecs, brute force) sont tracés et envoyés via Filebeat → ELK.
"""

import os
import json
import time
import random
import threading
from datetime import datetime
from collections import defaultdict
from flask import Flask, request, jsonify
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter

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

# Compteur d'échecs par IP (détection brute force)
failed_attempts = defaultdict(int)
lock = threading.Lock()

# Utilisateurs valides (simulation)
VALID_USERS = {
    'admin': 'password123',
    'user1': 'secret456',
    'operator': 'ops789',
    'hicham': 'pfa2026'
}


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
    print(log_line, flush=True)  # stdout Docker

    # Écriture dans le volume partagé (collecté par Filebeat)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_line + '\n')


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    """Vérification de l'état du service."""
    log_event('INFO', 'Health check OK', {
        'endpoint': '/health', 'status': 200, 'event_type': 'health_check'
    })
    return jsonify({'status': 'healthy', 'service': SERVICE_NAME}), 200


@app.route('/login', methods=['POST'])
def login():
    """Authentification utilisateur. Logue chaque tentative (succès ou échec)."""
    data = request.get_json(silent=True) or {}
    username = data.get('username', 'unknown')
    password = data.get('password', '')
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    # Délai de traitement simulé
    time.sleep(random.uniform(0.05, 0.2))

    if VALID_USERS.get(username) == password:
        # ── Succès ──────────────────────────────
        with lock:
            failed_attempts[client_ip] = 0
        log_event('INFO', f'Authentication successful for user {username}', {
            'user': username, 'ip': client_ip,
            'endpoint': '/login', 'status': 200,
            'event_type': 'auth_success'
        })
        return jsonify({
            'token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock',
            'user': username
        }), 200

    else:
        # ── Échec ────────────────────────────────
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
    """Déconnexion utilisateur."""
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    username = request.headers.get('X-User', 'unknown')
    log_event('INFO', f'User {username} logged out', {
        'user': username, 'ip': client_ip,
        'endpoint': '/logout', 'status': 200,
        'event_type': 'logout'
    })
    return jsonify({'message': 'Logged out successfully'}), 200


@app.route('/register', methods=['POST'])
def register():
    """Enregistrement d'un nouvel utilisateur."""
    data = request.get_json(silent=True) or {}
    username = data.get('username', 'unknown')
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
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
