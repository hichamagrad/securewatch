"""
Setup Kibana — index pattern + dashboards
PFA 2025-2026 : SecureWatch
Creates:
  - Data view  : security-logs-*
  - Viz 1      : Total security events (metric)
  - Viz 2      : Events by alert type (bar chart)
  - Viz 3      : Security events timeline (area)
  - Dashboard  : SecureWatch Security Dashboard
"""

import sys
import json
import time
import warnings

try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    warnings.filterwarnings('ignore', category=InsecureRequestWarning)
except ImportError:
    print("pip install requests"); sys.exit(1)

KIBANA  = "http://localhost:5601"
HEADERS = {"kbn-xsrf": "true", "Content-Type": "application/json"}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get(path):
    return requests.get(KIBANA + path, headers=HEADERS, timeout=10)

def _post(path, payload):
    return requests.post(KIBANA + path, headers=HEADERS,
                         data=json.dumps(payload), timeout=10)


def wait_for_kibana(retries=40, interval=5):
    print("[*] Attente de Kibana...")
    for i in range(retries):
        try:
            r = _get("/api/status")
            if r.status_code == 200:
                level = r.json().get("status", {}).get("overall", {}).get("level", "")
                if level in ("available", "degraded"):
                    print(f"    Kibana OK ({level})")
                    return True
        except Exception:
            pass
        print(f"    Tentative {i+1}/{retries}…")
        time.sleep(interval)
    return False


# ── Index pattern (data view) ─────────────────────────────────────────────────

def create_index_pattern():
    print("[1] Création de l'index pattern security-logs-*")

    # Kibana 8.x data views API
    r = _post("/api/data_views/data_view", {
        "data_view": {
            "title": "security-logs-*",
            "timeFieldName": "@timestamp",
            "name": "SecureWatch Security Logs",
        }
    })

    if r.status_code in (200, 201):
        dv_id = r.json()["data_view"]["id"]
        print(f"    OK — id: {dv_id}")
        _set_default_data_view(dv_id)
        return dv_id

    if r.status_code == 400 and "Duplicate" in r.text:
        # Already exists — fetch it
        r2 = _get("/api/data_views")
        if r2.status_code == 200:
            for dv in r2.json().get("data_view", []):
                if "security-logs" in dv.get("title", ""):
                    print(f"    Déjà existant — id: {dv['id']}")
                    return dv["id"]

    print(f"    ERREUR: {r.status_code} — {r.text[:300]}")
    return None


def _set_default_data_view(dv_id):
    r = _post("/api/data_views/default", {"data_view_id": dv_id, "force": True})
    if r.status_code in (200, 201):
        print("    Index pattern défini comme défaut")


# ── Visualizations ────────────────────────────────────────────────────────────

def _search_source(index_id):
    return json.dumps({
        "query": {"query": "", "language": "kuery"},
        "filter": [],
        "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",
    })


def _index_ref(index_id):
    return [{
        "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
        "type": "index-pattern",
        "id": index_id,
    }]


def create_visualization(obj_id, title, vis_state, index_id):
    payload = {
        "attributes": {
            "title": title,
            "visState": json.dumps(vis_state),
            "uiStateJSON": "{}",
            "description": f"SecureWatch PFA — {title}",
            "kibanaSavedObjectMeta": {"searchSourceJSON": _search_source(index_id)},
        },
        "references": _index_ref(index_id),
    }
    r = _post(f"/api/saved_objects/visualization/{obj_id}?overwrite=true", payload)
    if r.status_code in (200, 201):
        print(f"    OK — {title}")
        return obj_id
    print(f"    ERREUR ({title}): {r.status_code} — {r.text[:300]}")
    return None


def create_visualizations(index_id):
    print("[2] Création des visualisations")

    # ── Viz 1 : Total security events (metric) ────────────────
    metric_state = {
        "type": "metric",
        "aggs": [{"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}],
        "params": {
            "addTooltip": True,
            "addLegend": False,
            "type": "metric",
            "metric": {
                "percentageMode": False,
                "useRanges": False,
                "colorSchema": "Green to Red",
                "metricColorMode": "None",
                "colorsRange": [{"from": 0, "to": 100000}],
                "labels": {"show": True},
                "invertColors": False,
                "style": {
                    "bgFill": "#000", "bgColor": False,
                    "labelColor": False,
                    "subText": "Security Events",
                    "fontSize": 60,
                },
            },
        },
    }
    v1 = create_visualization("sw-total-events", "SecureWatch — Total Security Events",
                              metric_state, index_id)

    # ── Viz 2 : Events by alert_type (vertical bar) ───────────
    bar_state = {
        "type": "histogram",
        "aggs": [
            {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"},
            {
                "id": "2", "enabled": True, "type": "terms",
                "params": {
                    "field": "alert_type.keyword", "orderBy": "1",
                    "order": "desc", "size": 12,
                    "otherBucket": False, "missingBucket": False,
                },
                "schema": "segment",
            },
        ],
        "params": {
            "type": "histogram",
            "grid": {"categoryLines": False},
            "categoryAxes": [{
                "id": "CategoryAxis-1", "type": "category", "position": "bottom",
                "show": True, "style": {}, "scale": {"type": "linear"},
                "labels": {"show": True, "filter": True, "truncate": 120},
                "title": {},
            }],
            "valueAxes": [{
                "id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value",
                "position": "left", "show": True, "style": {},
                "scale": {"type": "linear", "mode": "normal"},
                "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                "title": {"text": "Count"},
            }],
            "seriesParams": [{
                "show": True, "type": "histogram", "mode": "stacked",
                "data": {"label": "Count", "id": "1"},
                "valueAxis": "ValueAxis-1",
                "drawLinesBetweenPoints": True, "lineWidth": 2, "showCircles": True,
            }],
            "addTooltip": True, "addLegend": True, "legendPosition": "right",
            "times": [], "addTimeMarker": False,
            "labels": {"show": True},
            "thresholdLine": {"show": False, "value": 10, "width": 1,
                              "style": "full", "color": "#E7664C"},
        },
    }
    v2 = create_visualization("sw-events-by-type", "SecureWatch — Events by Alert Type",
                              bar_state, index_id)

    # ── Viz 3 : Security events timeline (area) ───────────────
    area_state = {
        "type": "area",
        "aggs": [
            {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"},
            {
                "id": "2", "enabled": True, "type": "date_histogram",
                "params": {
                    "field": "@timestamp",
                    "useNormalizedEsInterval": True,
                    "scaleMetricValues": False,
                    "interval": "auto",
                    "drop_partials": False,
                    "min_doc_count": 1,
                    "extended_bounds": {},
                },
                "schema": "segment",
            },
            {
                "id": "3", "enabled": True, "type": "terms",
                "params": {
                    "field": "alert_type.keyword", "orderBy": "1",
                    "order": "desc", "size": 6,
                    "otherBucket": False, "missingBucket": False,
                },
                "schema": "group",
            },
        ],
        "params": {
            "type": "area",
            "grid": {"categoryLines": False},
            "categoryAxes": [{
                "id": "CategoryAxis-1", "type": "category", "position": "bottom",
                "show": True, "style": {}, "scale": {"type": "linear"},
                "labels": {"show": True, "filter": True, "truncate": 100},
                "title": {},
            }],
            "valueAxes": [{
                "id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value",
                "position": "left", "show": True, "style": {},
                "scale": {"type": "linear", "mode": "normal"},
                "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                "title": {"text": "Count"},
            }],
            "seriesParams": [{
                "show": True, "type": "area", "mode": "stacked",
                "data": {"label": "Count", "id": "1"},
                "drawLinesBetweenPoints": False, "lineWidth": 2,
                "showCircles": False, "interpolate": "linear",
                "valueAxis": "ValueAxis-1",
            }],
            "addTooltip": True, "addLegend": True, "legendPosition": "right",
            "times": [], "addTimeMarker": True,
            "thresholdLine": {"show": False, "value": 10, "width": 1,
                              "style": "full", "color": "#E7664C"},
            "labels": {},
        },
    }
    v3 = create_visualization("sw-events-timeline", "SecureWatch — Security Events Timeline",
                              area_state, index_id)

    return [v for v in (v1, v2, v3) if v]


# ── Dashboard ─────────────────────────────────────────────────────────────────

def create_dashboard(viz_ids):
    print("[3] Création du dashboard")
    if not viz_ids:
        print("    Aucune visualisation disponible, abandon.")
        return

    panels = []
    refs   = []
    layout = [
        # (x, y, w, h) on a 48-column grid
        (0,  0, 12, 10),   # metric — top-left
        (12, 0, 36, 18),   # bar chart — top-right (wider)
        (0,  18, 48, 16),  # timeline — full width
    ]

    for i, (vid, (x, y, w, h)) in enumerate(zip(viz_ids, layout)):
        ref_name = f"panel_{i}"
        panels.append({
            "version": "8.12.0",
            "type": "visualization",
            "gridData": {"x": x, "y": y, "w": w, "h": h, "i": str(i)},
            "panelIndex": str(i),
            "embeddableConfig": {"enhancements": {}},
            "panelRefName": ref_name,
        })
        refs.append({"name": ref_name, "type": "visualization", "id": vid})

    payload = {
        "attributes": {
            "title": "SecureWatch — Security Dashboard",
            "panelsJSON": json.dumps(panels),
            "optionsJSON": json.dumps({"hidePanelTitles": False, "useMargins": True}),
            "timeRestore": True,
            "timeTo": "now",
            "timeFrom": "now-24h",
            "refreshInterval": {"pause": False, "value": 30000},
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"language": "kuery", "query": ""},
                    "filter": [],
                })
            },
        },
        "references": refs,
    }

    r = _post("/api/saved_objects/dashboard/sw-security-dashboard?overwrite=true", payload)
    if r.status_code in (200, 201):
        dash_id = r.json().get("id", "sw-security-dashboard")
        print(f"    OK — id: {dash_id}")
        print(f"    URL : {KIBANA}/app/dashboards#/view/{dash_id}")
    else:
        print(f"    ERREUR: {r.status_code} — {r.text[:300]}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  SecureWatch — Setup Kibana PFA 2025-2026")
    print("=" * 55)

    if not wait_for_kibana():
        print("[!] Kibana inaccessible après 40 tentatives.")
        print("    Vérifier : docker-compose ps kibana")
        sys.exit(1)

    index_id = create_index_pattern()
    if not index_id:
        print("[!] Échec création index pattern — abandon.")
        sys.exit(1)

    viz_ids = create_visualizations(index_id)

    create_dashboard(viz_ids)

    print("\n[OK] Setup Kibana terminé.")
    print(f"     Discover  : {KIBANA}/app/discover")
    print(f"     Dashboard : {KIBANA}/app/dashboards")
    print(f"     Index     : security-logs-*")


if __name__ == "__main__":
    main()
