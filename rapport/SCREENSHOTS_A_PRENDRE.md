# Screenshots à prendre pour le rapport LaTeX

Placer tous les fichiers dans : `rapport/screenshots/`
Format recommandé : PNG, largeur minimale 1200px

---

## Logos (page de garde)

| Fichier attendu | Ce que c'est |
|---|---|
| `logo_universite.png` | Logo de votre université (fond transparent si possible) |
| `logo_ecole.png` | Logo de votre école / filière / département |

---

## Captures à prendre (dans l'ordre du rapport)

### 1. `architecture_diagram.png`
Faire un schéma de l'architecture (à la main ou avec draw.io/Excalidraw).
Sinon : capture de la page README ouverte dans VS Code avec le diagramme ASCII.

### 2. `flux_donnees.png`
Schéma du flux de données (logs + métriques).
Sinon : même chose, section "Flux de Données" du README.

---

### 3. `kibana_discover.png`
- Ouvrir http://localhost:5601
- Analytics → Discover → index `security-logs-*`
- Filtre : `event_type: brute_force`
- Ajouter colonnes : ip, level, event_type, alert_type
- Prendre la capture avec au moins 5 résultats visibles

---

### 4. `gateway_rate_limit.png`
- Ouvrir un terminal PowerShell
- Lancer : `python scripts/generate_attacks.py --scenario rate-limit`
- Capturer le terminal quand les 429 apparaissent (phase 1 ET phase 2)

---

### 5. `prometheus_targets.png`
- Ouvrir http://localhost:9090/targets
- Tous les targets doivent être UP (points verts)
- Capturer la page entière

---

### 6. `prometheus_alerts.png`
- Lancer d'abord : `python scripts/generate_attacks.py --scenario brute-force`
- Attendre 30 secondes
- Ouvrir http://localhost:9090/alerts
- Capturer avec `BruteForceDetected` en rouge (FIRING)

---

### 7. `alertmanager_ui.png`
- Après le brute force, ouvrir http://localhost:9093
- Capturer la carte d'alerte BruteForceDetected avec ses labels

---

### 8. `grafana_infra.png`
- Ouvrir http://localhost:3001 (admin / pfa2026)
- Ouvrir le dashboard "Infrastructure — SecureWatch"
- Capturer avec les graphiques affichant des données

---

### 9. `grafana_security.png`
- Même Grafana, dashboard "Sécurité — SecureWatch"
- Capturer avec les courbes auth failures + 403 visibles

---

### 10. `dashboard_overview.png`
- Ouvrir http://localhost:3000
- Onglet "Tableau de bord"
- Capturer avec les compteurs remplis (lancer des scénarios avant)

---

### 11. `dashboard_logs.png`
- Onglet "Flux de Logs"
- Filtre : niveau WARNING ou CRITICAL
- Capturer avec des événements de sécurité visibles

---

### 12. `dashboard_alertes.png`
- Onglet "Alertes de Sécurité"
- Après brute force + forbidden scan : capturer avec les cartes d'alerte
- Doit montrer au moins une alerte BRUTE FORCE (rouge) et une ACCÈS INTERDIT (orange)

---

### 13. `dashboard_monitoring_infra.png`
- Onglet "Monitoring" → onglet "Infrastructure"
- Attendre que les graphiques se chargent (~15 secondes)
- Capturer avec les graphiques CPU et RAM affichant des courbes

---

### 14. `dashboard_monitoring_security.png`
- Onglet "Monitoring" → onglet "Sécurité"
- Capturer avec les stat cards remplies et les graphiques visibles

---

### 15. `dashboard_services.png`
- Onglet "État des Services"
- Capturer avec la grille des 11 services (points verts = online)

---

### 16. `rate_limit_terminal.png`
- Même capture que #4 ou recapturer en zoomant sur la phase 2
- Doit montrer clairement les `<<< RATE LIMITED` en rouge/gras

---

## Ordre recommandé de prise de captures

```
1. Lancer tous les scénarios :
   python scripts/generate_attacks.py --scenario all

2. Attendre 30 secondes pour que Prometheus évalue les alertes

3. Prendre dans cet ordre :
   - prometheus_targets.png   (http://localhost:9090/targets)
   - prometheus_alerts.png    (http://localhost:9090/alerts)
   - alertmanager_ui.png      (http://localhost:9093)
   - grafana_infra.png        (http://localhost:3001)
   - grafana_security.png     (http://localhost:3001)
   - kibana_discover.png      (http://localhost:5601)
   - dashboard_overview.png   (http://localhost:3000)
   - dashboard_logs.png       (http://localhost:3000 → Flux de Logs)
   - dashboard_alertes.png    (http://localhost:3000 → Alertes)
   - dashboard_monitoring_infra.png
   - dashboard_monitoring_security.png
   - dashboard_services.png

4. Relancer rate-limit séparément pour le terminal :
   python scripts/generate_attacks.py --scenario rate-limit
   → capturer gateway_rate_limit.png et rate_limit_terminal.png
```

---

## Compilation LaTeX

```powershell
cd "C:\Users\<nom>\Desktop\pfa 20252026\rapport"

# Premier passage (génère les références)
pdflatex rapport_securewatch.tex

# Second passage (résout les références croisées)
pdflatex rapport_securewatch.tex
```

Nécessite une distribution LaTeX installée (MiKTeX ou TeX Live).
Si MiKTeX n'est pas installé : https://miktex.org/download

### Packages requis (installés automatiquement par MiKTeX au premier passage)
- babel (french), inputenc, fontenc
- geometry, setspace, parskip
- graphicx, xcolor, float, caption, subcaption
- fancyhdr, hyperref
- listings, lstautogobble
- booktabs, tabularx, longtable, multirow, array
- tcolorbox (avec skins, breakable)
- enumitem, titlesec, amsmath, pifont
- lmodern, microtype
