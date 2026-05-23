# SecureWatch
### Centralisation des Logs & Détection d'Incidents de Sécurité — PFA 2025-2026

> Architecture microservices locale avec ELK Stack, API Gateway HTTPS, monitoring Prometheus/Grafana/Alertmanager et détection d'incidents en temps réel.

---

## Table des matières

1. [Architecture](#architecture)
2. [Services & Ports](#services--ports)
3. [Démarrage](#démarrage)
4. [Interfaces web](#interfaces-web)
5. [API Gateway HTTPS](#api-gateway-https)
6. [Sécurité & Vulnérabilités corrigées](#sécurité--vulnérabilités-corrigées)
7. [Alertes Prometheus](#alertes-prometheus)
8. [Comptes de test](#comptes-de-test)
9. [Scénarios d'attaque](#scénarios-dattaque)
10. [Analyse des logs](#analyse-des-logs)
11. [Guide de simulation complète](#guide-de-simulation-complète)
12. [Structure du projet](#structure-du-projet)
13. [Dépannage](#dépannage)

---

## Architecture

```
  Client
    │
    ├── HTTP  :8080  ──► 301 redirect
    └── HTTPS :8443  ──► API GATEWAY (Nginx)
                              │  Rate Limit · TLS · Logs JSON
                              ├── /auth/*  ──► auth-service:5001 (interne)
                              └── /api/*   ──► api-service:5002  (interne)
                                    │                │
                              logs JSON         logs JSON + métriques /metrics
                                    └─────┬──────────┘
                           ┌──────────────┴─────────────────────────┐
                           ▼                                         ▼
                      ELK Stack                             Monitoring Stack
                   Filebeat → /logs/                     Prometheus :9090
                   Logstash :5044                         ├── auth-service
                   Elasticsearch :9200                    ├── api-service
                   Kibana :5601                           ├── nginx-exporter
                   SecureWatch UI :3000                   ├── node-exporter
                                                          ├── alertmanager
                                                          ├── Grafana :3001
                                                          └── Alertmanager :9093
```

**Réseaux Docker (isolation) :**

| Réseau | Services |
|---|---|
| `gateway-net` | gateway, auth-service, api-service, nginx-exporter, frontend |
| `monitoring-net` | prometheus, alertmanager, grafana, node-exporter, nginx-exporter, auth-service, api-service, gateway |
| `elk` | elasticsearch, logstash, kibana, filebeat, auth-service, api-service, gateway, frontend |

> Les ports 5001 et 5002 ne sont **jamais exposés** sur l'hôte — les microservices ne sont accessibles que via la gateway.

---

## Services & Ports

| Service | Port hôte | Rôle |
|---|---|---|
| **SecureWatch Dashboard** | 3000 | Interface principale du projet |
| **API Gateway HTTP** | 8080 | Redirige vers HTTPS (301) |
| **API Gateway HTTPS** | 8443 | Point d'entrée TLS — toutes les requêtes API |
| **Kibana** | 5601 | Exploration et visualisation des logs ELK |
| **Elasticsearch** | 9200 | Stockage et indexation des logs |
| **Logstash** | 5044 | Pipeline de traitement des logs |
| **Prometheus** | 9090 | Métriques temps réel + règles d'alertes |
| **Alertmanager** | 9093 | Routage et affichage des alertes |
| **Grafana** | 3001 | Dashboards infrastructure & sécurité |
| auth-service | — | Interne uniquement (via gateway) |
| api-service | — | Interne uniquement (via gateway) |
| node-exporter | — | Interne uniquement |
| nginx-exporter | — | Interne uniquement |
| filebeat | — | Interne uniquement |

---

## Démarrage

### Prérequis
- Docker Desktop — **minimum 6 Go RAM alloués** (recommandé : 8 Go)
- Python 3.8+ avec `pip install requests`

### Premier lancement

```powershell
cd "C:\Users\<nom>\Desktop\pfa 20252026"

# Créer le dossier de logs partagé (une seule fois)
mkdir logs

# Démarrer tous les services
docker-compose up -d

# Attendre ~120 secondes puis vérifier
docker-compose ps
```

Tous les services doivent afficher `Up` ou `Up (healthy)` :

```
alertmanager     Up
api-service      Up (healthy)
auth-service     Up (healthy)
elasticsearch    Up (healthy)
filebeat         Up
frontend         Up
gateway          Up
grafana          Up
kibana           Up
logstash         Up (healthy)
nginx-exporter   Up
node-exporter    Up
prometheus       Up
```

### Relancer après modification du code

```powershell
docker-compose up -d --build
# ou cibler un service spécifique
docker-compose up -d --build auth-service api-service frontend
```

### Arrêter

```powershell
# Arrêter (données conservées)
docker-compose down

# Arrêter + supprimer toutes les données
docker-compose down -v
```

---

## Interfaces web

| Interface | URL | Identifiants |
|---|---|---|
| SecureWatch Dashboard | http://localhost:3000 | — |
| Alertmanager | http://localhost:9093 | — |
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3001 | `admin` / `pfa2026` |
| Kibana | http://localhost:5601 | — |
| Elasticsearch | http://localhost:9200 | — |

> **HTTPS gateway** — le certificat est auto-signé : accepter l'exception dans le navigateur ou ajouter `-k` avec curl.

---

## API Gateway HTTPS

La gateway Nginx expose deux ports :

| Port | Protocole | Comportement |
|---|---|---|
| 8080 | HTTP | Retourne 301 → `https://<host>:8443` |
| 8443 | HTTPS/TLS | Toutes les routes API |

**Certificat** : RSA 2048, auto-signé, valide 365 jours (`gateway/certs/`).

**En-têtes de sécurité appliqués sur toutes les réponses HTTPS :**
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
```

### Routes exposées

| Route | Service cible | Rate limit |
|---|---|---|
| `POST /auth/login` | auth-service:5001 | 5 req/min par IP, burst 10 |
| `POST /auth/logout` | auth-service:5001 | 5 req/min par IP |
| `POST /auth/register` | auth-service:5001 | 5 req/min par IP |
| `GET  /auth/health` | auth-service:5001 | 5 req/min par IP |
| `GET  /api/health` | api-service:5002 | 30 req/min par IP |
| `GET  /api/users` | api-service:5002 | 30 req/min par IP |
| `GET  /api/data` | api-service:5002 | 30 req/min par IP |
| `GET  /api/admin` | api-service:5002 | 30 req/min par IP |
| `GET  /api/config` | api-service:5002 | 30 req/min par IP |
| `GET  /api/reports` | api-service:5002 | 30 req/min par IP |
| `POST /api/upload` | api-service:5002 | 30 req/min par IP |
| Toute autre route | — | → 404 JSON |

Dépassement → **HTTP 429** avec corps JSON + log dans ELK tagué `rate_limited`.

### Tester la gateway

```powershell
# Health checks via HTTPS
curl -k https://localhost:8443/auth/health
curl -k https://localhost:8443/api/health

# Vérifier la redirection HTTP → HTTPS
curl -v http://localhost:8080/auth/health
# Réponse attendue : 301 Location: https://...:8443/auth/health

# Login valide
curl -k -X POST https://localhost:8443/auth/login `
  -H "Content-Type: application/json" `
  -d '{"username":"admin","password":"Admin@SecureWatch2026!"}'

# Login invalide → 401
curl -k -X POST https://localhost:8443/auth/login `
  -H "Content-Type: application/json" `
  -d '{"username":"hacker","password":"wrong"}'
```

---

## Sécurité & Vulnérabilités corrigées

Un audit de sécurité complet a été réalisé sur le projet. Les 10 vulnérabilités identifiées ont été corrigées avant la livraison finale.

### Tableau des vulnérabilités

| # | Vulnérabilité | Sévérité | Fichier(s) concerné(s) | Correction appliquée |
|---|---|:---:|---|---|
| 1 | **Authentification JWT factice** — n'importe quelle valeur `Bearer xxx` donnait accès aux endpoints protégés | Critique | `api-service/app.py` | Validation réelle via `PyJWT.decode()` : signature HS256 + expiration vérifiées à chaque requête |
| 2 | **Identifiants par défaut faibles** — mots de passe triviaux (`admin:admin`, `user1:user1`) codés en dur | Critique | `auth-service/app.py` | Mots de passe par défaut renforcés ; surchargeables via variables d'environnement `DEMO_*_PASSWORD` dans `.env` |
| 3 | **Stored XSS via `innerHTML`** — données de logs insérées brutes dans le DOM ; un attaquant pouvant injecter un log avec `<script>` dans Elasticsearch déclenchait l'exécution dans tous les navigateurs connectés | Critique | `frontend/app.js` | Fonction `escapeHtml()` appliquée sur tous les champs issus des logs (`message`, `service`, `ip`, `event_type`) avant toute insertion `innerHTML` |
| 4 | **Elasticsearch exposé sans authentification** — le proxy `/es/` redirigeait toutes les méthodes HTTP (DELETE, PUT…) vers Elasticsearch, permettant suppression d'index ou exfiltration complète | Élevée | `frontend/nginx.conf` | Liste blanche stricte : seuls `GET /_cluster/health` et `POST /security-logs*/_search` sont autorisés ; tout le reste retourne 403 |
| 5 | **Usurpation d'IP contournant la détection brute force** — les services lisaient `X-Forwarded-For` fourni par le client, permettant de changer d'IP fictive à chaque tentative | Élevée | `auth-service/app.py`, `api-service/app.py` | Passage à `X-Real-IP`, positionné par nginx depuis `$remote_addr` (IP réelle de connexion, non modifiable par le client) |
| 6 | **Prometheus exposé sans authentification** — l'API `/prometheus/` complète était accessible : énumération des cibles, de la configuration interne, des labels | Élevée | `frontend/nginx.conf` | Liste blanche stricte : seuls `/api/v1/query`, `/api/v1/query_range` et `/-/healthy` sont autorisés |
| 7 | **Injection dans les logs** — le nom d'utilisateur était intégré brut dans les messages de log ; l'injection de `\n{"level":"CRITICAL",...}` créait de faux événements critiques | Moyenne | `auth-service/app.py` | Fonction `sanitize_input()` : suppression des caractères de contrôle ASCII (0x00–0x1F) et limitation à 64 caractères |
| 8 | **Clé privée TLS dans le dépôt git** — `gateway/certs/selfsigned.key` était commité et donc accessible à quiconque ayant accès au repo | Moyenne | `.gitignore` | Vérifié que `gateway/certs/` est correctement ignoré par git dès l'origine ; les fichiers n'ont jamais été trackés |
| 9 | **Upload non authentifié acceptant tout** — `/api/upload` répondait 200 OK sans token, quel que soit le contenu | Moyenne | `api-service/app.py` | Ajout d'une vérification JWT obligatoire ; les types MIME suspects retournent désormais **HTTP 415** au lieu de 200 |
| 10 | **En-têtes de sécurité absents sur le frontend** — le serveur nginx du dashboard ne transmettait aucun en-tête de protection ; les handlers `onclick`/`onchange` inline dans le HTML empêchaient toute CSP stricte | Moyenne | `frontend/nginx.conf`, `frontend/index.html`, `frontend/app.js` | Ajout de `X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`, `Referrer-Policy` et `Content-Security-Policy` (sans `unsafe-inline` pour les scripts — les handlers inline ont été déplacés vers `addEventListener` dans `app.js`) |

### Architecture de sécurité après correction

```
Client
  │
  ├── JWT signé (HS256, 1h) ──► auth-service /login
  │                                    │
  │        ┌───────────────────────────┘
  │        ▼
  └── Bearer <token> ──► api-service (validation signature + expiration)
                                │
                         accès refusé si token invalide/expiré → 401

Frontend (port 3000)
  ├── CSP sans unsafe-inline (scripts)
  ├── X-Frame-Options: DENY
  ├── Proxy /es/  ──── ALLOWLIST ───► GET /_cluster/health
  │                                   POST /security-logs*/_search seulement
  └── Proxy /prom/ ── ALLOWLIST ───► GET /api/v1/query[_range] seulement

auth-service / api-service
  ├── IP réelle via X-Real-IP (non spoofable)
  ├── Logs sanitisés (pas d'injection de contrôle)
  └── JWT_SECRET via variable d'environnement (.env)
```

### Configurer le secret JWT (production)

Le secret par défaut est un placeholder. Pour une mise en production :

```powershell
# Générer un secret fort
python -c "import secrets; print(secrets.token_hex(32))"

# Ajouter dans .env (déjà dans .gitignore)
# JWT_SECRET=<valeur générée>

# Relancer
docker compose up --build -d
```

---

## Alertes Prometheus

### Règles configurées (`monitoring/alert_rules.yml`)

**Groupe Sécurité** — évalué toutes les 30 s :

| Alerte | Condition | Sévérité | Délai |
|---|---|---|---|
| `BruteForceDetected` | `increase(brute_force_total[5m]) > 0` | critical | immédiat |
| `HighAuthFailureRate` | > 3 échecs auth/min pendant 2 min | warning | 2 min |
| `RateLimitViolations` | > 5 requêtes 429 en 5 min | warning | immédiat |
| `ForbiddenAccessSpike` | > 5 accès 403/min pendant 2 min | warning | 2 min |

**Groupe Infrastructure** — évalué toutes les 30 s :

| Alerte | Condition | Sévérité | Délai |
|---|---|---|---|
| `ServiceDown` | `up == 0` pendant 1 min | critical | 1 min |
| `HighCPUUsage` | CPU > 80% pendant 2 min | warning | 2 min |
| `HighMemoryUsage` | RAM > 85% pendant 2 min | warning | 2 min |
| `HighErrorRate` | > 0.1 erreur 5xx/s pendant 2 min | warning | 2 min |

### Consulter les alertes

```
http://localhost:9090/alerts    → état de chaque règle (inactive / pending / firing)
http://localhost:9093           → alertes actives dans Alertmanager
```

---

## Comptes de test

| Utilisateur | Mot de passe par défaut | Variable d'environnement | Rôle |
|---|---|---|---|
| `admin` | `Admin@SecureWatch2026!` | `DEMO_ADMIN_PASSWORD` | Administrateur |
| `user1` | `User1@PFA2026!` | `DEMO_USER1_PASSWORD` | Utilisateur |
| `operator` | `Operator@PFA2026!` | `DEMO_OPERATOR_PASSWORD` | Opérateur |

Les mots de passe peuvent être surchargés sans rebuild via le fichier `.env` (voir section [Sécurité & Vulnérabilités corrigées](#sécurité--vulnérabilités-corrigées)).

Tout autre couple → **HTTP 401** et log `auth_failure` dans ELK.

---

## Scénarios d'attaque

### Installer les dépendances

```powershell
pip install requests
```

### Lancer un scénario

```powershell
python scripts/generate_attacks.py --scenario <nom>
```

### Scénarios disponibles

```powershell
# Scénario 1 — Brute force
# 8 à 12 tentatives de connexion avec credentials invalides depuis une IP attaquante
# Déclenche : logs auth_failure + brute_force, alerte BruteForceDetected dans Prometheus
python scripts/generate_attacks.py --scenario brute-force

# Scénario 2 — Scan de routes interdites
# 9 routes protégées scannées (admin, config, secrets…) → HTTP 403/404
# Déclenche : logs forbidden_access, alerte ForbiddenAccessSpike si répété
python scripts/generate_attacks.py --scenario forbidden-scan

# Scénario 3 — Trafic normal
# 15 requêtes légitimes avec token valide → HTTP 200
# Alimente les métriques de base sans déclencher d'alerte
python scripts/generate_attacks.py --scenario normal

# Scénario 4 — Erreurs serveur
# 20 appels à /api/data → ~10% de réponses 500 aléatoires
# Déclenche : logs server_error, potentiellement alerte HighErrorRate
python scripts/generate_attacks.py --scenario server-errors

# Scénario 5 — Uploads suspects
# 5 fichiers avec types MIME dangereux (exe, php, sh, js, octet-stream)
# Déclenche : logs suspicious_upload niveau WARNING
python scripts/generate_attacks.py --scenario suspicious-upload

# Scénario 6 — Test rate limiting
# Phase 1 : 60 requêtes /api/data en rafale → 429 à partir de la ~38e (burst 50)
# Phase 2 : 10 tentatives /auth/login invalides → 429 à partir de la 2e (burst 10)
# Déclenche : logs rate_limited dans ELK, alerte RateLimitViolations dans Prometheus
python scripts/generate_attacks.py --scenario rate-limit

# Tous les scénarios enchaînés
python scripts/generate_attacks.py --scenario all
```

### Analyse des logs après simulation

```powershell
# Rapport complet (24 dernières heures)
python scripts/analyse_logs.py

# Rapport étendu avec seuil brute force abaissé
python scripts/analyse_logs.py --since 48 --threshold-bf 3
```

---

## Guide de simulation complète

Séquence recommandée pour une démonstration du projet de A à Z.

### Étape 0 — Vérification avant la présentation

```powershell
cd "C:\Users\<nom>\Desktop\pfa 20252026"
docker-compose ps
```
Tous les 13 services doivent être `Up`. Si un service est arrêté :
```powershell
docker-compose up -d
```

Générer du trafic de base pour avoir des données dans le dashboard :
```powershell
python scripts/generate_attacks.py --scenario normal
```

---

### Étape 1 — Dashboard principal (http://localhost:3000)

**Onglet "Tableau de bord"**
- Montrer les compteurs en haut : Total événements, Échecs auth, Accès interdits, Erreurs système, Brute Force
- Expliquer que les données viennent d'**Elasticsearch** via le pipeline Filebeat → Logstash → ES
- Le dashboard se rafraîchit automatiquement toutes les **8 secondes**

**Onglet "Flux de Logs"**
- Montrer les logs en temps réel avec les champs : timestamp, niveau, service, message
- Utiliser les filtres (niveau WARNING, service auth-service) pour isoler des événements
- Expliquer le format JSON structuré et pourquoi c'est important pour la corrélation

**Onglet "État des Services"**
- Montrer la grille de statut des 11 services
- Expliquer que chaque service est sondé via un proxy nginx (pas d'accès CORS direct)

---

### Étape 2 — Démontrer l'isolation réseau (gateway)

Dans un terminal, montrer que les microservices ne sont PAS accessibles directement :
```powershell
# Accès direct refusé (port non exposé)
curl http://localhost:5001/health   # Connection refused
curl http://localhost:5002/health   # Connection refused

# Accès via gateway HTTPS : fonctionne
curl -k https://localhost:8443/auth/health
curl -k https://localhost:8443/api/health
```

Montrer la redirection HTTP → HTTPS :
```powershell
curl -v http://localhost:8080/auth/health
# → 301 Moved Permanently → https://...:8443/auth/health
```

---

### Étape 3 — Simuler un brute force

```powershell
python scripts/generate_attacks.py --scenario brute-force
```

Ce qui se passe dans le terminal :
- 8 à 12 tentatives avec credentials invalides depuis une IP attaquante (ex: 185.220.101.5)
- Réponses HTTP 401 jusqu'à ce que auth-service détecte l'attaque
- Log `brute_force` généré avec `failed_attempts` et l'IP source

Pendant ou juste après, aller dans le dashboard :
- **Tableau de bord** → compteur "Brute Force" incrémenté
- **Flux de Logs** → filtre niveau CRITICAL → logs `brute_force` visibles
- **Onglet Alertes** → carte rouge **BRUTE FORCE** avec l'IP attaquante et le nombre de tentatives

Après ~30 secondes, vérifier Prometheus :
```
http://localhost:9090/alerts → BruteForceDetected : firing
http://localhost:9093        → alerte active dans Alertmanager
```

---

### Étape 4 — Simuler un scan de routes interdites

```powershell
# Lancer deux fois pour dépasser le seuil de détection (5 tentatives par IP)
python scripts/generate_attacks.py --scenario forbidden-scan
python scripts/generate_attacks.py --scenario forbidden-scan
```

Ce qui se passe :
- 9 routes scannées → `/api/admin`, `/api/config`, `/api/secrets`… → HTTP 403/404
- Logs `forbidden_access` générés avec l'IP et l'endpoint ciblé

Dans le dashboard :
- **Onglet Alertes** → carte orange **ACCÈS INTERDIT** apparaît (seuil : 5 tentatives par IP)
- **Flux de Logs** → filtre `forbidden` → voir le pattern de scan

---

### Étape 5 — Démontrer le rate limiting

```powershell
python scripts/generate_attacks.py --scenario rate-limit
```

Ce que montre le terminal :
- Phase 1 : 60 requêtes `/api/data` — les 429 apparaissent à partir de la ~38e (burst de 50 absorbé)
- Phase 2 : 10 tentatives `/auth/login` invalides — 429 dès la 2e (burst de 10, limite 5/min)

Points à expliquer :
- Le **rate limiting est dans la gateway Nginx** — aucun code applicatif impliqué
- Les 429 ne passent jamais jusqu'aux microservices Flask
- Les 429 sont loggés dans ELK via les logs d'accès JSON de la gateway

---

### Étape 6 — Monitoring Prometheus (http://localhost:3000 → Monitoring)

**Onglet Infrastructure :**
- Stat cards : CPU hôte, RAM, total requêtes auth-service, total requêtes api-service
- Graphique CPU 30 min — données venant de **node-exporter** → Prometheus
- Graphique RAM 30 min
- Graphique requêtes HTTP/s par service

**Onglet Sécurité :**
- Stat cards : brute force total, 403 total, **429 total** (source: Elasticsearch), 500 total
- Graphique auth failures/min — source Prometheus (`auth_failures_total`)
- Graphique 429/min — source **Elasticsearch** (gateway logs, Flask ne voit jamais les 429)
- Graphique combiné sécurité : 403 + auth failures sur 30 min

Expliquer l'architecture hybride : la plupart des métriques viennent de Prometheus, mais les 429 viennent d'Elasticsearch car nginx bloque les requêtes avant qu'elles atteignent Flask.

---

### Étape 7 — Grafana (http://localhost:3001)

Identifiants : `admin` / `pfa2026`

**Dashboard "Infrastructure — SecureWatch" :**
- CPU Usage % — `(1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))) * 100`
- RAM utilisée en Go
- HTTP Requests/s par service (auth + api)
- Temps de réponse p95
- Taux d'erreurs 5xx/s

**Dashboard "Sécurité — SecureWatch" :**
- Compteur brute force
- Courbes 403, 429, auth failures
- Distribution par endpoint
- Répartition par code HTTP

Expliquer : les dashboards sont **auto-provisionnés** au démarrage — aucune configuration manuelle.

---

### Étape 8 — Alertes Prometheus & Alertmanager

**Prometheus — état des règles :**
```
http://localhost:9090/alerts
```
Montrer les règles avec leurs états : `inactive`, `pending`, `firing`.

**Alertmanager — alertes actives :**
```
http://localhost:9093
```
Si le brute force a été lancé : `BruteForceDetected` apparaît en rouge avec la durée, les labels (severity=critical, category=security) et le résumé.

Expliquer le pipeline d'alertes :
```
Prometheus évalue les règles toutes les 30s
  → règle FIRING si condition vraie
    → envoi à Alertmanager
      → groupement par alertname + category + severity
        → routage selon la sévérité
          → affiché dans l'UI (+ email/Slack si configuré)
```

---

### Étape 9 — Kibana (http://localhost:5601)

Analytics → Discover → index `security-logs-*`

Requêtes utiles à montrer :
```
event_type: brute_force          → toutes les attaques brute force
event_type: forbidden_access     → tous les accès interdits
status: 429                      → toutes les requêtes rate limitées
level: CRITICAL                  → événements critiques
service: api-gateway             → logs de la gateway uniquement
tags: security_event             → tous les événements de sécurité
```

Ajouter des colonnes : `ip`, `service`, `level`, `event_type`, `alert_type`.

Montrer un document complet et expliquer les champs ajoutés par Logstash : `alert_type`, `tags`, `source`.

---

### Étape 10 — Rapport final en ligne de commande

```powershell
python scripts/analyse_logs.py
```

Affiche un résumé complet dans le terminal :
- Total d'événements par niveau (INFO / WARNING / ERROR / CRITICAL)
- Répartition par service
- Répartition par type d'événement
- Liste des alertes détectées triées par sévérité (CRITIQUE → ÉLEVÉ → MOYEN)
- Statut global de sécurité du système

---

### Scénarios supplémentaires (optionnel)

```powershell
# Erreurs serveur (500)
python scripts/generate_attacks.py --scenario server-errors

# Uploads de fichiers suspects
python scripts/generate_attacks.py --scenario suspicious-upload

# Tout enchaîné (brute force + forbidden + normal + server-errors + uploads + rate-limit)
python scripts/generate_attacks.py --scenario all
```

---

## Structure du projet

```
pfa 20252026/
├── docker-compose.yml              # 13 conteneurs, 3 réseaux isolés
│
├── gateway/
│   ├── nginx.conf                  # HTTP→HTTPS redirect, rate limiting, logs JSON, proxy
│   └── certs/
│       ├── selfsigned.crt          # Certificat TLS (RSA 2048, 365 jours)
│       └── selfsigned.key          # Clé privée
│
├── monitoring/
│   ├── prometheus.yml              # Scrape configs (5 targets) + rule_files + alerting
│   ├── alert_rules.yml             # 8 règles d'alertes (4 sécurité + 4 infrastructure)
│   ├── alertmanager.yml            # Routage des alertes, inhibitions, receivers
│   └── grafana/
│       ├── provisioning/
│       │   ├── datasources/prometheus.yml
│       │   └── dashboards/dashboards.yml
│       └── dashboards/
│           ├── infrastructure.json
│           └── security.json
│
├── services/
│   ├── auth-service/
│   │   ├── app.py                  # Flask : /login /logout /register /health /metrics
│   │   │                           # Counters Prometheus : auth_failures_total, brute_force_total
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── api-service/
│   │   ├── app.py                  # Flask : /api/* /health /metrics
│   │   │                           # Counters : forbidden_access_total, server_errors_total
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── frontend/
│       ├── index.html
│       ├── style.css
│       ├── app.js                  # Dashboard : ES queries, Prometheus panels, alertes, services
│       ├── nginx.conf              # Proxies : /es/, /prometheus/, /grafana/, health checks
│       └── Dockerfile
│
├── elasticsearch/elasticsearch.yml
├── kibana/kibana.yml
├── logstash/
│   ├── logstash.yml
│   └── pipeline/logstash.conf     # Parsing JSON, tagging sécurité, indexation ES
├── filebeat/filebeat.yml          # Collecte /logs/*.log → Logstash
│
├── scripts/
│   ├── generate_attacks.py        # 6 scénarios (brute force, 403, rate-limit…)
│   └── analyse_logs.py            # Rapport CLI depuis Elasticsearch
│
└── logs/                          # Volume partagé : gateway + microservices → Filebeat
```

---

## Dépannage

### Un service n'est pas `Up`

```powershell
docker-compose logs -f <service>
# ex:
docker-compose logs -f elasticsearch
docker-compose logs -f gateway
docker-compose logs -f prometheus
docker-compose logs -f alertmanager
```

### Elasticsearch ne démarre pas

```powershell
# En PowerShell administrateur
wsl -d docker-desktop sysctl -w vm.max_map_count=262144
```

### Le dashboard affiche des données de démo

Elasticsearch n'est pas encore prêt. Attendre 60–90 s après `docker-compose up -d`.

### La section Monitoring affiche `—` partout

Le dashboard Monitoring initialise les graphiques uniquement quand la section est visible (lazy init). Cliquer sur "Monitoring" dans la barre latérale, puis attendre ~15 secondes le premier chargement.

Si le problème persiste, vérifier que Prometheus est accessible :
```powershell
Invoke-WebRequest http://localhost:9090/api/v1/query?query=up -UseBasicParsing
```

### Les scénarios échouent avec une erreur SSL

```powershell
pip install requests
# Les scripts utilisent verify=False — aucune configuration supplémentaire nécessaire
python scripts/generate_attacks.py --scenario normal
```

### Alertmanager ne reçoit pas les alertes

```powershell
# Vérifier que Prometheus a chargé les règles
Invoke-WebRequest http://localhost:9090/api/v1/rules -UseBasicParsing
# Vérifier les alertes actives
Invoke-WebRequest http://localhost:9093/api/v2/alerts -UseBasicParsing
```

### Recharger la config Prometheus à chaud (sans redémarrer)

```powershell
Invoke-WebRequest -Method POST http://localhost:9090/-/reload -UseBasicParsing
```

### Logs dans Elasticsearch

```powershell
# Compter tous les documents
Invoke-WebRequest "http://localhost:9200/security-logs-*/_count" -UseBasicParsing

# 5 derniers événements de sécurité
Invoke-WebRequest "http://localhost:9200/security-logs-*/_search?size=5&sort=@timestamp:desc&q=tags:security_event" -UseBasicParsing
```

---

## Technologies

| Technologie | Version | Rôle |
|---|---|---|
| **Nginx** | Alpine | API Gateway HTTPS — TLS, rate limiting, logs JSON, proxy |
| **OpenSSL** | 3.x | Certificat TLS auto-signé (RSA 2048) |
| **Prometheus** | Latest | Métriques temps réel — scrape 15 s, 8 règles d'alertes |
| **Alertmanager** | Latest | Routage, groupement et affichage des alertes |
| **Grafana** | Latest | 2 dashboards auto-provisionnés (infrastructure + sécurité) |
| **Node Exporter** | Latest | Métriques CPU/RAM/disque de l'hôte |
| **Nginx Exporter** | Latest | Métriques de la gateway Nginx |
| **Elasticsearch** | 8.12.0 | Stockage et indexation des logs |
| **Logstash** | 8.12.0 | Pipeline — parsing JSON, tagging sécurité, indexation |
| **Filebeat** | 8.12.0 | Collecte des fichiers de logs → Logstash |
| **Kibana** | 8.12.0 | Exploration et visualisation ELK |
| **Python / Flask** | 3.11 / 3.0 | Microservices + métriques Prometheus |
| **Chart.js** | 4.4.0 | Graphiques temps réel dans SecureWatch |
| Docker Compose | Latest | Orchestration — 13 conteneurs, 3 réseaux |

---

*PFA 2025-2026 — Modernisation des SI par l'Architecture Microservices et le Cloud Local*
