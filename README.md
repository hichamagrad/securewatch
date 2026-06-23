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
7. [Alertes Prometheus & Webhook Alertmanager](#alertes-prometheus--webhook-alertmanager)
8. [Contrôle d'accès RBAC](#contrôle-daccès-rbac)
9. [Fonctionnalités interactives](#fonctionnalités-interactives)
10. [Carte des Attaques Géographiques](#carte-des-attaques-géographiques)
11. [Temps réel — Server-Sent Events](#temps-réel--server-sent-events)
12. [Comptes de test](#comptes-de-test)
13. [Scénarios d'attaque](#scénarios-dattaque)
14. [Analyse des logs](#analyse-des-logs)
15. [Guide de simulation complète](#guide-de-simulation-complète)
16. [Rapport & Screenshots](#rapport--screenshots)
17. [Structure du projet](#structure-du-projet)
18. [Dépannage](#dépannage)

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
| **Redis** | — | Interne uniquement — compteurs brute force persistants |
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
| Grafana | http://localhost:3001 | `admin` / `changeme` |
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

## Alertes Prometheus & Webhook Alertmanager

### Webhook Alertmanager → api-service (actif)

Toutes les alertes Prometheus sont désormais transmises à l'api-service via un webhook interne, sans configuration externe (email/Slack) requise.

**Pipeline complet :**
```
Prometheus (règle FIRING)
  → Alertmanager
    → POST http://api-service:5002/api/alerts/webhook
      → stockage Redis (max 100 alertes, persistant entre redémarrages)
        → GET /api/alerts/pushed (admin + operator uniquement)
```

**Endpoints ajoutés à l'api-service :**

| Endpoint | Méthode | Auth | Description |
|---|---|---|---|
| `/api/alerts/webhook` | POST | Aucune (réseau interne) | Reçoit les notifications Alertmanager |
| `/api/alerts/pushed` | GET | JWT (admin ou operator) | Retourne les alertes reçues (max 100) |

Le receiver Alertmanager actif :
```yaml
receivers:
  - name: 'securewatch-webhook'
    webhook_configs:
      - url: 'http://api-service:5002/api/alerts/webhook'
        send_resolved: true
```

### Règles configurées (`monitoring/alert_rules.yml`)

**Groupe Sécurité** — évalué toutes les 30 s :

| Alerte | Condition | Sévérité | Délai |
|---|---|---|---|
| `BruteForceDetected` | `increase(brute_force_total[5m]) > 0` | critical | immédiat |
| `HighAuthFailureRate` | > 3 échecs auth/min pendant 2 min | warning | 2 min |
| `RateLimitViolations` | > 5 requêtes 429 en 5 min | warning | immédiat |
| `ForbiddenAccessSpike` | > 5 accès 403/min pendant 2 min | warning | 2 min |
| `SQLiDetected` | `increase(sqli_attempts_total[5m]) > 0` | critical | immédiat |
| `ScannerDetected` | `increase(scanner_ua_total[5m]) > 0` | warning | immédiat |
| `GeoAnomalyDetected` | `increase(geo_anomaly_total[5m]) > 0` | warning | immédiat |

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

## Fonctionnalités interactives

### Sélecteur de fenêtre temporelle

Un menu déroulant dans la barre supérieure (toujours visible) contrôle la plage de données chargée depuis Elasticsearch et l'échelle des graphiques.

| Option | Granularité du graphique | Taille de lot ES |
|---|---|---|
| 1 heure | 12 × 5 min | 1 000 entrées |
| 6 heures | 12 × 30 min | 1 000 entrées |
| **24 heures** (défaut) | 12 × 2 h | 1 000 entrées |
| 7 jours | 14 × 12 h | 1 000 entrées |

Changer la plage déclenche un rechargement immédiat des logs, des compteurs et du graphique "Événements par Heure". Le sous-titre du graphique se met à jour dynamiquement.

### Export CSV des logs

Un bouton **⬇ CSV** dans la section "Flux de Logs" exporte les logs actuellement filtrés (niveau, service, recherche texte) au format RFC-4180. Le fichier est nommé `securewatch-logs-YYYY-MM-DD.csv` et contient jusqu'à 200 entrées.

Champs exportés : `timestamp`, `level`, `service`, `message`, `ip`, `event_type`.

### Acquittement des alertes

Chaque carte d'alerte dans la section "Alertes de Sécurité" dispose d'un bouton **Ignorer** :

- La décision est persistée dans `localStorage` sous la clé `sw-dismissed-alerts`
- L'empreinte de l'alerte est `type|IP` — stable entre les rechargements
- Le compteur de la barre latérale et le badge de section excluent les alertes ignorées
- Un bouton **Réinitialiser** apparaît dans l'en-tête de la section dès qu'au moins une alerte est ignorée
- Les alertes ignorées réapparaissent si la même IP lance une nouvelle attaque avec un fingerprint différent

### Carte des Attaques Géographiques

Voir la section [Carte des Attaques Géographiques](#carte-des-attaques-géographiques) ci-dessous.

### Rétention automatique des logs (ILM Elasticsearch)

Un conteneur init `es-setup` (`curlimages/curl`) s'exécute une fois au démarrage, après qu'Elasticsearch est `healthy`, et applique :

1. **Politique ILM** `securewatch-14d` — phase `delete` à 14 jours
2. **Index template** `securewatch-logs-template` — attaché à `security-logs-*`, 1 shard, 0 réplicas

Après ce bootstrap, chaque nouvel index quotidien hérite automatiquement de la politique. Les indices de plus de 14 jours sont supprimés sans intervention manuelle.

```powershell
# Vérifier la politique appliquée
Invoke-WebRequest "http://localhost:9200/_ilm/policy/securewatch-14d" -UseBasicParsing
# Voir les indices et leur état ILM
Invoke-WebRequest "http://localhost:9200/security-logs-*/_ilm/explain" -UseBasicParsing
```

---

## Carte des Attaques Géographiques

L'onglet **Carte des Attaques Géographiques** (accessible aux rôles `admin` et `operator`) affiche une carte du monde interactive projetant les origines géographiques des connexions suspectes détectées dans les logs.

### Rendu

- **Projection Natural Earth** (D3.js v7) avec graticule et fond de sphère
- Les pays identifiés comme sources d'anomalies géographiques sont mis en évidence selon leur niveau de risque :
  - `critical` — Corée du Nord, nœuds Tor
  - `high` — Russie, Chine, Iran
  - `medium` — Nigeria
- Des **points d'attaque pulsants** sont placés aux coordonnées de chaque IP suspecte avec une infobulle affichant le pays, le code de risque et le nombre d'événements.

### Pays surveillés

| Code | Pays | Niveau |
|---|---|:---:|
| KP | Corée du Nord | critical |
| TOR | Nœud Tor Exit | critical |
| RU | Russie | high |
| CN | Chine | high |
| IR | Iran | high |
| NG | Nigeria | medium |

### Données

La carte se base sur les logs `event_type: geo_anomaly` présents dans Elasticsearch pour la plage temporelle sélectionnée. Elle se met à jour à chaque rafraîchissement global (8 s) si la section est active.

Le fichier de topologie `world-110m.json` (Natural Earth 110 m, TopoJSON v3) est servi par le conteneur `frontend`.

### Bibliothèques utilisées (chargées via CDN dans `index.html`)

| Bibliothèque | Version | Rôle |
|---|---|---|
| D3.js | v7 | Projection géographique, SVG, graticule |
| TopoJSON | v3 | Décodage du fichier `world-110m.json` |

---

## Temps réel — Server-Sent Events

Le dashboard bascule de la scrutation toutes les 8 secondes à un flux SSE pour les événements de sécurité critiques.

### Architecture

```
auth-service (Flask)
  │  push_sse({'type': 'brute_force',   'ip': ..., 'count': ...})
  │  push_sse({'type': 'auth_failure',  ...})
  │  push_sse({'type': 'sqli_attempt',  'ip': ..., 'payload': ...})
  │  push_sse({'type': 'suspicious_ua', 'ip': ..., 'user_agent': ...})
  ▼
/events/stream  (text/event-stream, X-Accel-Buffering: no)
  │
  ▼ proxy (frontend nginx — buffering off, timeout 3600s)
  │
  ▼
EventSource('/auth/stream?token=<jwt>')  ← navigateur
  │
  ├─ auth_failure   → refresh() immédiat (mise à jour compteurs + logs)
  ├─ brute_force    → refresh() + toast "Brute force — IP x.x.x.x (N tentatives)"
  ├─ sqli_attempt   → refresh() + toast "Injection SQL — IP x.x.x.x : <payload>"
  └─ suspicious_ua  → refresh() + toast "Scanner détecté — IP x.x.x.x : <ua>"
```

### Comportement

- **Connexion** : à la connexion (`startApp()`), le frontend ouvre une `EventSource` avec le JWT en paramètre (les en-têtes HTTP ne sont pas disponibles pour `EventSource`).
- **Keepalive** : le serveur envoie un commentaire `: keepalive` toutes les 20 s pour maintenir la connexion à travers les proxies.
- **Reconnexion** : si la connexion se coupe, le frontend tente de se reconnecter après 10 s si le token est encore valide.
- **Déconnexion** : la fermeture de session (`logout`) ferme proprement l'`EventSource`.
- **File de messages** : chaque client SSE a une file de 50 messages max. Les messages en excès pour un client lent sont abandonnés sans bloquer les autres.
- **Polling conservé** : le polling toutes les 8 s reste actif pour les mises à jour générales (métriques Prometheus, état des services). SSE couvre uniquement les événements de sécurité urgents.

### Redis — compteurs brute force persistants

Avant Redis, `failed_attempts = defaultdict(int)` était en mémoire : un redémarrage du conteneur remettait tous les compteurs à zéro, permettant à un attaquant de contourner la détection.

**Avec Redis (`redis:7-alpine`) :**

| Opération | Commande Redis | Détail |
|---|---|---|
| Échec auth | `INCR bf:<ip>` + `EXPIRE bf:<ip> 3600` | Fenêtre glissante de 1 h |
| Succès auth | `DEL bf:<ip>` | Réinitialise le compteur |
| Redémarrage | — | Compteurs conservés dans Redis |

```powershell
# Inspecter les compteurs en direct
docker exec redis redis-cli KEYS "bf:*"
docker exec redis redis-cli GET "bf:10.0.0.5"
```

**Fallback** : si Redis est inaccessible au démarrage ou tombe en cours de route, `incr_failure()` et `reset_failure()` basculent silencieusement sur le `defaultdict` en mémoire. Le service ne s'arrête jamais à cause de Redis.

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

## Contrôle d'accès RBAC

SecureWatch implémente un contrôle d'accès basé sur les rôles (RBAC) à deux niveaux : côté client (UI) et côté serveur (api-service).

### Rôles et permissions

| Section | admin | operator | user |
|---|:---:|:---:|:---:|
| Tableau de bord | ✓ | ✓ | ✓ |
| Flux de Logs | ✓ | ✓ | ✓ |
| Alertes de Sécurité | ✓ | ✓ | ✗ |
| Carte des Attaques Géographiques | ✓ | ✓ | ✗ |
| État des Services | ✓ | ✓ | ✗ |
| Monitoring Prometheus | ✓ | ✗ | ✗ |
| `/api/alerts/pushed` | ✓ | ✓ | ✗ |

### Fonctionnement

**1. Émission du rôle (auth-service)**

À la connexion, `auth-service` intègre le rôle dans le JWT :
```json
{ "sub": "operator", "role": "operator", "iat": ..., "exp": ... }
```
Le frontend lit le claim `role` depuis le payload Base64 et le stocke dans `localStorage`.

**2. Application côté frontend (app.js)**

- `applyRoleRestrictions()` — appelée au démarrage, ajoute la classe `nav-restricted` sur les items de navigation inaccessibles et positionne `aria-disabled="true"`.
- `showSection(name)` — bloque la navigation et affiche un toast `Accès refusé — Rôle <requis> requis` si le rôle courant n'est pas autorisé.
- `canAccess(section)` — vérifie le rôle en mémoire avant toute navigation.

**3. Application côté serveur (api-service)**

L'endpoint `/api/alerts/pushed` valide le JWT **et** vérifie que le rôle est `admin` ou `operator` avant de retourner les données — les simples utilisateurs reçoivent HTTP 403.

### Tester le RBAC

```powershell
# Générer les screenshots de chaque rôle (nécessite Playwright)
pip install playwright
playwright install chromium
python scripts/screenshot_rbac.py
# → rapport/screenshots/ui_review/rbac_admin_dashboard.png
# → rapport/screenshots/ui_review/rbac_operator_dashboard.png
# → rapport/screenshots/ui_review/rbac_user1_dashboard.png
```

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

# Scénario 7 — Injection SQL
# 6 payloads SQLi envoyés comme username à /auth/login (OR bypass, UNION, SLEEP, DROP…)
# auth-service détecte les patterns via regex et retourne HTTP 400
# Déclenche : logs sqli_attempt niveau WARNING, SSE push, Logstash tag SQL_INJECTION
python scripts/generate_attacks.py --scenario sql-injection

# Scénario 8 — User-agents scanners
# 8 requêtes avec UA connus (sqlmap, Nikto, Nessus, masscan, Nuclei, gobuster…)
# Les services détectent l'UA avant traitement (before_request) et logguent l'incident
# Déclenche : logs suspicious_ua niveau WARNING, Logstash tag SCANNER_DETECTED
python scripts/generate_attacks.py --scenario scanner-ua

# Scénario 9 — Anomalie géographique
# 7 requêtes avec X-Forwarded-For simulant des IPs suspectes (RU, CN, KP, IR, TOR, NG)
# api-service détecte les préfixes IP géographiques et logge l'anomalie
# Déclenche : logs geo_anomaly niveau WARNING, Logstash tag GEO_ANOMALY
python scripts/generate_attacks.py --scenario geo-anomaly

# Tous les scénarios enchaînés (9 au total)
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

Rangée 1 — Compteurs de détection d'attaques (source Prometheus) :
- **Brute Force Détecté** (`brute_force_total`)
- **Injections SQL** (`sqli_attempts_total`)
- **Scanners Offensifs** (`scanner_ua_total`, agrégé auth-service + api-service)
- **Anomalies Géo** (`geo_anomaly_total`)

Rangée 2 — Métriques HTTP (sources mixtes) :
- **Accès Interdits 403** — source Prometheus (`flask_http_request_total{status="403"}`)
- **Rate Limit 429** — source **Elasticsearch** (gateway logs, Flask ne voit jamais les 429)
- **Erreurs Système 500** — source Prometheus

Graphiques :
- **Échecs Auth / min** — courbe des tentatives échouées sur 30 min (`auth_failures_total`)
- **Rate Limit (429) / min** — courbe des requêtes bloquées depuis Elasticsearch
- **Menaces Avancées — Tendances** — 3 courbes simultanées : SQLi (rouge), Scanner UA (violet), Anomalie Géo (cyan) sur 30 min
- **Incidents de Sécurité — Tendances** — 403 Forbidden + Auth Failures sur 30 min

Expliquer l'architecture hybride : la plupart des métriques viennent de Prometheus, mais les 429 viennent d'Elasticsearch car nginx bloque les requêtes avant qu'elles atteignent Flask.

---

### Étape 7 — Grafana (http://localhost:3001)

Identifiants : `admin` / `changeme`

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

**Première utilisation — configurer le dashboard automatiquement :**

```powershell
python scripts/setup_kibana.py
# Crée : index pattern security-logs-*, 3 visualisations, 1 dashboard
# URL dashboard : http://localhost:5601/app/dashboards
```

Analytics → Discover → index `security-logs-*` est maintenant configuré par défaut.

Requêtes utiles à montrer :
```
event_type: brute_force          → toutes les attaques brute force
event_type: forbidden_access     → tous les accès interdits
event_type: sqli_attempt         → tentatives d'injection SQL détectées
event_type: suspicious_ua        → scanners et outils offensifs détectés
event_type: geo_anomaly          → connexions depuis pays suspects
status: 429                      → toutes les requêtes rate limitées
level: CRITICAL                  → événements critiques
service: api-gateway             → logs de la gateway uniquement
tags: security_event             → tous les événements de sécurité
```

Ajouter des colonnes : `ip`, `service`, `level`, `event_type`, `alert_type`.

Montrer un document complet et expliquer les champs ajoutés par Logstash : `alert_type`, `tags`, `source`.

Le dashboard pré-configuré regroupe : compteur total d'événements, répartition par `alert_type` (barres), timeline des événements par type (aires empilées, dernières 24 h).

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

# Injection SQL (payloads dans /auth/login)
python scripts/generate_attacks.py --scenario sql-injection

# Scanners offensifs (sqlmap, Nikto, masscan…)
python scripts/generate_attacks.py --scenario scanner-ua

# Anomalies géographiques (RU, CN, KP, IR, TOR…)
python scripts/generate_attacks.py --scenario geo-anomaly

# Tout enchaîné (9 scénarios)
python scripts/generate_attacks.py --scenario all
```

---

## Rapport & Screenshots

Le rapport académique LaTeX et les captures d'écran pour la soutenance sont dans le dossier `rapport/`.

### Contenu

```
rapport/
├── rapport_securewatch.tex         # Source LaTeX du rapport (PFA 2025-2026)
├── SCREENSHOTS_A_PRENDRE.md        # Guide de compilation et liste des figures
└── screenshots/
    ├── architecture_diagram.png
    ├── dashboard_overview.png
    ├── dashboard_logs.png
    ├── dashboard_alertes.png
    ├── dashboard_services.png
    ├── dashboard_monitoring_infra.png
    ├── dashboard_monitoring_security.png
    ├── grafana_infra.png
    ├── grafana_security.png
    ├── kibana_discover.png
    ├── prometheus_alerts.png
    ├── prometheus_targets.png
    ├── alertmanager_ui.png
    ├── gateway_rate_limit.png
    ├── rate_limit_terminal.png
    ├── flux_donnees.png
    └── ui_review/                  # Screenshots RBAC, thèmes, responsive
        ├── rbac_admin_dashboard.png
        ├── rbac_operator_dashboard.png
        ├── rbac_user1_dashboard.png
        └── ...
```

### Scripts de capture (Playwright)

Tous les scripts nécessitent `pip install playwright && playwright install chromium` et que la stack soit démarrée (`docker-compose up -d`).

| Script | Rôle |
|---|---|
| `scripts/take_screenshots.py` | Capture principale — toutes les sections du dashboard |
| `scripts/take_screenshots_remaining.py` | Complète les captures manquantes |
| `scripts/generate_missing_screenshots.py` | Détecte et génère les screenshots absents |
| `scripts/screenshot_rbac.py` | Screenshots par rôle (admin / operator / user) |
| `scripts/screenshot_auth.py` | Flux d'authentification (login, erreur, logout) |
| `scripts/screenshot_ui.py` | Vues générales de l'interface |
| `scripts/screenshot_themes.py` | Comparaison thème clair / sombre |
| `scripts/screenshot_responsive.py` | Rendu mobile, tablette, desktop |
| `scripts/take_alerts_screenshots.py` | États des alertes Prometheus / Alertmanager |
| `scripts/setup_kibana.py` | Provisionne Kibana : index pattern, 3 visualisations, dashboard |
| `scripts/take_kibana_screenshot.py` | Vue Kibana Discover avec index `security-logs-*` |
| `scripts/functional_audit.py` | Audit fonctionnel automatisé — rapport PASS/FAIL |

```powershell
# Lancer l'audit fonctionnel complet
python scripts/functional_audit.py

# Capturer toutes les screenshots du rapport
python scripts/take_screenshots.py
python scripts/screenshot_rbac.py
python scripts/screenshot_themes.py
python scripts/screenshot_responsive.py
```

---

## Structure du projet

```
pfa 2025-2026/
├── docker-compose.yml              # 16 conteneurs, 3 réseaux isolés
│                                   # Inclut : Redis, es-setup (ILM), Logstash -Xms128m/-Xmx256m
├── .env.example                    # Template des variables d'environnement
│
├── gateway/
│   ├── nginx.conf                  # HTTP→HTTPS redirect, rate limiting, logs JSON, proxy
│   └── certs/
│       ├── selfsigned.crt          # Certificat TLS (RSA 2048, 365 jours)
│       └── selfsigned.key          # Clé privée (non commité)
│
├── monitoring/
│   ├── prometheus.yml              # Scrape configs (5 targets) + rule_files + alerting
│   ├── alert_rules.yml             # 11 règles d'alertes (7 sécurité + 4 infrastructure)
│   ├── alertmanager.yml            # Webhook actif → api-service:5002/api/alerts/webhook
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
│   │   ├── app.py                  # Flask : /login /logout /register /validate /health /metrics
│   │   │                           # JWT HS256, brute force detection, sanitize_input()
│   │   │                           # Détection SQLi (SQLI_PATTERNS regex) + scanner UA (before_request)
│   │   │                           # Redis : incr_failure / reset_failure (fallback mémoire)
│   │   │                           # SSE  : /events/stream — push push_sse() sur auth_failure/brute_force/sqli_attempt/suspicious_ua
│   │   │                           # Counters Prometheus : auth_failures_total, brute_force_total, sqli_attempts_total, scanner_ua_total
│   │   ├── Dockerfile
│   │   └── requirements.txt        # + redis>=5.0.0
│   ├── api-service/
│   │   ├── app.py                  # Flask : /api/* /health /metrics
│   │   │                           # Validation JWT réelle (PyJWT), RBAC server-side
│   │   │                           # Détection scanner UA + anomalie géo X-Forwarded-For (before_request)
│   │   │                           # /api/alerts/webhook (Alertmanager, stockage Redis) + /api/alerts/pushed
│   │   │                           # Counters : forbidden_access_total, server_errors_total, scanner_ua_total, geo_anomaly_total
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── frontend/
│       ├── index.html              # SPA : login, nav RBAC, time-range select, btn-export-csv, section geomap
│       ├── style.css               # Thème dark/light, nav-restricted, access-toast, dismiss btn, geo-map styles
│       ├── app.js                  # RBAC (SECTION_ROLES, applyRoleRestrictions)
│       │                           # SSE  : initSSE / closeSSE / showSecurityToast (brute_force, sqli_attempt, suspicious_ua)
│       │                           # UX   : sélecteur plage, exportCSV, acquittement alertes
│       │                           # ES queries, Prometheus panels, alertes, services status
│       │                           # Geo Map : initGeoMap / refreshGeoMap (D3.js + TopoJSON)
│       │                           # Monitoring Sécurité : 7 stat cards + 4 graphiques
│       │                           #   refreshSecurity() — sqli_attempts_total, scanner_ua_total, geo_anomaly_total
│       │                           #   chart-threats : Menaces Avancées (SQLi + Scanner + Geo, 30 min)
│       ├── world-110m.json         # Topologie mondiale Natural Earth 110m (TopoJSON v3)
│       ├── nginx.conf              # Proxies allowlist : /es/, /prometheus/, health checks
│       │                           # SSE  : /auth/stream (buffering off, timeout 3600s)
│       │                           # En-têtes CSP, X-Frame-Options, X-Content-Type-Options
│       └── Dockerfile
│
├── elasticsearch/
│   ├── elasticsearch.yml
│   └── ilm_setup.sh               # Bootstrap ILM policy securewatch-14d (14 jours)
├── kibana/kibana.yml
├── logstash/
│   ├── logstash.yml
│   └── pipeline/logstash.conf     # Parsing JSON, tagging sécurité, indexation ES
│                                   # event_types : brute_force, auth_failure, forbidden_access,
│                                   #   unauthorized_access, suspicious_upload, rate_limited,
│                                   #   sqli_attempt, suspicious_ua, geo_anomaly, server_error
├── filebeat/filebeat.yml          # Collecte /logs/*.log → Logstash
│
├── scripts/
│   ├── generate_attacks.py        # 9 scénarios d'attaque (brute force, 403, rate-limit,
│   │                              #   sql-injection, scanner-ua, geo-anomaly…)
│   ├── setup_kibana.py            # Provisionne Kibana : index pattern + 3 visualisations + dashboard
│   ├── analyse_logs.py            # Rapport CLI depuis Elasticsearch
│   ├── functional_audit.py        # Audit fonctionnel automatisé Playwright (PASS/FAIL)
│   ├── take_screenshots.py        # Captures principales du dashboard
│   ├── take_screenshots_remaining.py
│   ├── generate_missing_screenshots.py
│   ├── screenshot_rbac.py         # Captures par rôle (admin / operator / user)
│   ├── screenshot_auth.py         # Flux d'authentification
│   ├── screenshot_ui.py           # Vues générales de l'interface
│   ├── screenshot_themes.py       # Thème clair vs sombre
│   ├── screenshot_responsive.py   # Mobile / tablette / desktop
│   ├── take_alerts_screenshots.py # États des alertes Prometheus
│   ├── take_kibana_screenshot.py  # Vue Kibana Discover
│   └── requirements.txt           # playwright, requests
│
├── rapport/
│   ├── rapport_securewatch.tex    # Source LaTeX du rapport académique
│   ├── SCREENSHOTS_A_PRENDRE.md  # Guide de compilation LaTeX + liste des figures
│   └── screenshots/               # 16 captures pour le rapport + dossier ui_review/
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

### La section Monitoring affiche `—` pour les graphiques

Le dashboard Monitoring initialise les graphiques uniquement quand la section est visible (lazy init). Cliquer sur "Monitoring" dans la barre latérale, puis attendre ~15 secondes le premier chargement.

> Les compteurs affichent `0` (et non `—`) lorsqu'aucun événement n'a encore été détecté — c'est le comportement attendu.

Si les graphiques restent vides, vérifier que Prometheus est accessible :
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
| **Prometheus** | Latest | Métriques temps réel — scrape 15 s, 11 règles d'alertes |
| **Alertmanager** | Latest | Routage, groupement et affichage des alertes |
| **Grafana** | Latest | 2 dashboards auto-provisionnés (infrastructure + sécurité) |
| **Node Exporter** | Latest | Métriques CPU/RAM/disque de l'hôte |
| **Nginx Exporter** | Latest | Métriques de la gateway Nginx |
| **Elasticsearch** | 8.12.0 | Stockage et indexation des logs |
| **Logstash** | 8.12.0 | Pipeline — parsing JSON, tagging sécurité, indexation |
| **Filebeat** | 8.12.0 | Collecte des fichiers de logs → Logstash |
| **Kibana** | 8.12.0 | Exploration et visualisation ELK |
| **Python / Flask** | 3.11 / 3.0 | Microservices + métriques Prometheus + SSE stream |
| **Redis** | 7 Alpine | Compteurs brute force persistants — INCR/EXPIRE/DEL |
| **Chart.js** | 4.4.0 | Graphiques temps réel dans SecureWatch |
| **D3.js** | v7 | Carte des attaques géographiques — projection Natural Earth |
| **TopoJSON** | v3 | Décodage de la topologie mondiale `world-110m.json` |
| Docker Compose | Latest | Orchestration — 16 conteneurs, 3 réseaux |

---

*PFA 2025-2026 — Modernisation des SI par l'Architecture Microservices et le Cloud Local*
