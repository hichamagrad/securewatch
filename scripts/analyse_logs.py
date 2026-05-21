#!/usr/bin/env python3
"""
analyse_logs.py — Script d'analyse des logs de sécurité
PFA 2025-2026 : Centralisation des Logs pour la Détection d'Incidents de Sécurité

Usage :
    python analyse_logs.py
    python analyse_logs.py --since 48 --threshold-bf 3
    python analyse_logs.py --es-host http://localhost:9200

Détecte :
    - Attaques brute force (> N échecs d'auth par IP)
    - Tentatives d'accès interdits répétées (403)
    - Erreurs système répétées (500)
    - Uploads suspects
"""

import sys
import json
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

try:
    import requests
except ImportError:
    print("[!] Module 'requests' manquant. Installez-le : pip install requests")
    sys.exit(1)

# ── Configuration par défaut ──────────────────────────────
ES_HOST      = "http://localhost:9200"
INDEX_PATTERN = "security-logs-*"


# ─────────────────────────────────────────────────────────
# Connexion & Requêtes Elasticsearch
# ─────────────────────────────────────────────────────────

def fetch_logs(es_host: str, since_hours: int = 24, size: int = 10000) -> list:
    """Interroge Elasticsearch pour récupérer les logs des N dernières heures."""
    since = (datetime.utcnow() - timedelta(hours=since_hours)).isoformat() + "Z"

    body = {
        "query": {
            "bool": {
                "must": [
                    {"range": {"@timestamp": {"gte": since}}}
                ]
            }
        },
        "sort": [{"@timestamp": {"order": "desc"}}],
        "size": size
    }

    url = f"{es_host}/{INDEX_PATTERN}/_search"
    try:
        r = requests.post(
            url, json=body,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        r.raise_for_status()
        hits = r.json().get("hits", {}).get("hits", [])
        logs = [h["_source"] for h in hits]
        print(f"[✓] {len(logs)} événements récupérés depuis Elasticsearch")
        return logs

    except requests.exceptions.ConnectionError:
        print(f"[✗] Impossible de se connecter à {es_host}")
        print("     Vérifiez que les services Docker sont actifs : docker-compose ps")
        return []
    except requests.exceptions.HTTPError as e:
        print(f"[✗] Erreur HTTP : {e}")
        print("     Vérifiez que l'index security-logs-* existe dans Elasticsearch")
        return []
    except Exception as e:
        print(f"[✗] Erreur inattendue : {e}")
        return []


# ─────────────────────────────────────────────────────────
# Détections de Sécurité
# ─────────────────────────────────────────────────────────

def detect_brute_force(logs: list, threshold: int = 5) -> list:
    """
    Détecte les attaques brute force.
    Critère : >= threshold échecs d'authentification depuis la même IP en 24h.
    """
    ip_failures = defaultdict(list)
    for log in logs:
        if log.get("event_type") == "auth_failure":
            ip = log.get("ip", "unknown")
            ip_failures[ip].append(log.get("timestamp", ""))

    alerts = []
    for ip, times in ip_failures.items():
        if len(times) >= threshold:
            alerts.append({
                "type":      "BRUTE_FORCE",
                "severity":  "CRITIQUE",
                "ip":        ip,
                "count":     len(times),
                "first_seen": min(times) if times else "—",
                "last_seen":  max(times) if times else "—",
                "description": (
                    f"IP {ip} a effectué {len(times)} tentatives "
                    f"d'authentification échouées (seuil: {threshold})"
                )
            })
    return sorted(alerts, key=lambda x: x["count"], reverse=True)


def detect_forbidden_access(logs: list, threshold: int = 10) -> list:
    """
    Détecte les tentatives d'accès interdits répétées.
    Critère : >= threshold réponses 403 depuis la même IP.
    """
    ip_forbidden = defaultdict(list)
    for log in logs:
        if log.get("event_type") == "forbidden_access" or log.get("status") == 403:
            ip = log.get("ip", "unknown")
            endpoint = log.get("endpoint", "—")
            ip_forbidden[ip].append(endpoint)

    alerts = []
    for ip, endpoints in ip_forbidden.items():
        if len(endpoints) >= threshold:
            unique_ep = list(set(endpoints))
            alerts.append({
                "type":        "ACCES_INTERDIT",
                "severity":    "ELEVE",
                "ip":          ip,
                "count":       len(endpoints),
                "endpoints":   unique_ep[:5],
                "description": (
                    f"IP {ip} a reçu {len(endpoints)} refus d'accès (403) "
                    f"sur {len(unique_ep)} endpoint(s) distinct(s)"
                )
            })
    return sorted(alerts, key=lambda x: x["count"], reverse=True)


def detect_server_errors(logs: list, threshold: int = 5) -> list:
    """
    Détecte les erreurs système répétées.
    Critère : >= threshold erreurs 500/ERROR par service.
    """
    svc_errors = defaultdict(list)
    for log in logs:
        if log.get("level") in ("ERROR", "CRITICAL") or log.get("status") == 500:
            service = log.get("service", "unknown")
            svc_errors[service].append(log.get("message", ""))

    alerts = []
    for service, msgs in svc_errors.items():
        if len(msgs) >= threshold:
            alerts.append({
                "type":        "ERREURS_SYSTEME",
                "severity":    "MOYEN",
                "service":     service,
                "count":       len(msgs),
                "description": (
                    f"Le service '{service}' a généré {len(msgs)} erreurs "
                    f"système en 24h — instabilité possible"
                )
            })
    return sorted(alerts, key=lambda x: x["count"], reverse=True)


def detect_suspicious_uploads(logs: list) -> list:
    """Détecte les uploads suspects (type MIME inhabituel)."""
    suspicious = [
        l for l in logs
        if l.get("event_type") == "suspicious_upload" or l.get("suspicious") is True
    ]
    if not suspicious:
        return []
    return [{
        "type":        "UPLOAD_SUSPECT",
        "severity":    "ELEVE",
        "count":       len(suspicious),
        "description": f"{len(suspicious)} upload(s) avec type MIME suspect détecté(s)"
    }]


# ─────────────────────────────────────────────────────────
# Rapport
# ─────────────────────────────────────────────────────────

def print_stats(logs: list):
    """Affiche les statistiques générales des logs."""
    if not logs:
        return

    by_level   = defaultdict(int)
    by_service = defaultdict(int)
    by_type    = defaultdict(int)

    for log in logs:
        by_level[log.get("level", "UNKNOWN")] += 1
        by_service[log.get("service", "unknown")] += 1
        if log.get("event_type"):
            by_type[log["event_type"]] += 1

    print("\n📊 STATISTIQUES GÉNÉRALES")
    print(f"   Total événements  : {len(logs)}")
    print("\n   Par niveau :")
    for lv, cnt in sorted(by_level.items()):
        icon = {"INFO": "ℹ", "WARNING": "⚠", "ERROR": "✗", "CRITICAL": "🚨"}.get(lv, "·")
        bar = "█" * min(cnt // 2, 40)
        print(f"     {icon} {lv:<12} {cnt:>5}  {bar}")

    print("\n   Par service :")
    for svc, cnt in sorted(by_service.items(), key=lambda x: -x[1]):
        print(f"     · {svc:<20} {cnt:>5} événements")

    print("\n   Par type d'événement :")
    for et, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"     · {et:<28} {cnt:>5}")


def print_alerts(all_alerts: list):
    """Affiche les alertes de sécurité détectées."""
    severity_icon = {
        "CRITIQUE": "🔴",
        "ELEVE":    "🟠",
        "MOYEN":    "🟡",
    }

    print(f"\n🚨 INCIDENTS DE SÉCURITÉ DÉTECTÉS : {len(all_alerts)}")
    print("─" * 60)

    if not all_alerts:
        print("   ✅ Aucun incident détecté pour la période analysée.")
        return

    for alert in all_alerts:
        icon = severity_icon.get(alert.get("severity", ""), "⚪")
        sev  = alert.get("severity", "INCONNU")
        atype = alert.get("type", "INCONNU")
        print(f"\n   {icon} [{sev}] {atype}")
        print(f"      {alert['description']}")

        if "ip" in alert:
            print(f"      IP : {alert['ip']}")
        if "service" in alert:
            print(f"      Service : {alert['service']}")
        if "count" in alert:
            print(f"      Occurrences : {alert['count']}")
        if "endpoints" in alert:
            print(f"      Endpoints ciblés : {', '.join(alert['endpoints'])}")


def generate_report(logs: list, all_alerts: list, since_hours: int):
    """Génère le rapport complet dans le terminal."""
    width = 62
    print("\n" + "═" * width)
    print(f"  {'RAPPORT D\'ANALYSE DE SÉCURITÉ':^{width-4}}")
    print(f"  {'PFA 2025-2026 — Centralisation des Logs':^{width-4}}")
    print("═" * width)
    print(f"  Généré le : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Période   : {since_hours} dernières heures")
    print(f"  Source    : Elasticsearch → {INDEX_PATTERN}")

    print_stats(logs)
    print_alerts(all_alerts)

    print("\n" + "═" * width)
    if any(a.get("severity") == "CRITIQUE" for a in all_alerts):
        print("  ⛔ STATUT : ALERTE CRITIQUE — Intervention immédiate requise")
    elif any(a.get("severity") == "ELEVE" for a in all_alerts):
        print("  ⚠  STATUT : ALERTE ÉLEVÉE — Vérification recommandée")
    elif all_alerts:
        print("  ℹ  STATUT : AVERTISSEMENTS — Surveillance renforcée conseillée")
    else:
        print("  ✅ STATUT : NORMAL — Aucun incident détecté")
    print("═" * width + "\n")


# ─────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Analyse des logs de sécurité — PFA 2025-2026",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exemples :\n"
               "  python analyse_logs.py\n"
               "  python analyse_logs.py --since 48 --threshold-bf 3\n"
               "  python analyse_logs.py --es-host http://localhost:9200"
    )
    parser.add_argument("--since",        type=int,   default=24,
                        help="Analyser les N dernières heures (défaut: 24)")
    parser.add_argument("--threshold-bf", type=int,   default=5,
                        help="Seuil brute force — nb échecs par IP (défaut: 5)")
    parser.add_argument("--threshold-403",type=int,   default=10,
                        help="Seuil accès interdits — nb 403 par IP (défaut: 10)")
    parser.add_argument("--threshold-500",type=int,   default=5,
                        help="Seuil erreurs système — nb 500 par service (défaut: 5)")
    parser.add_argument("--es-host",      type=str,   default=ES_HOST,
                        help=f"URL Elasticsearch (défaut: {ES_HOST})")
    args = parser.parse_args()

    print(f"\n[*] SecureWatch — Analyse des Logs de Sécurité")
    print(f"[*] Connexion : {args.es_host}")
    print(f"[*] Période   : {args.since} dernières heures")
    print(f"[*] Seuils    : brute_force={args.threshold_bf}, 403={args.threshold_403}, 500={args.threshold_500}")

    # Récupération des logs
    logs = fetch_logs(args.es_host, since_hours=args.since)
    if not logs:
        print("\n[!] Aucun log trouvé. Vérifiez que :")
        print("    1. Les conteneurs Docker sont démarrés (docker-compose up -d)")
        print("    2. Les microservices ont généré des logs")
        print("    3. Filebeat → Logstash → Elasticsearch sont opérationnels")
        sys.exit(0)

    # Détections
    all_alerts = (
        detect_brute_force(logs, args.threshold_bf) +
        detect_forbidden_access(logs, args.threshold_403) +
        detect_server_errors(logs, args.threshold_500) +
        detect_suspicious_uploads(logs)
    )

    # Rapport
    generate_report(logs, all_alerts, args.since)


if __name__ == "__main__":
    main()
