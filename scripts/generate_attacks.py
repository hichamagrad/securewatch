import time, argparse, random, sys, warnings
try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    warnings.filterwarnings('ignore', category=InsecureRequestWarning)
except ImportError:
    print("pip install requests"); sys.exit(1)

# Tout passe par l'API Gateway HTTPS sur le port 8443
AUTH_URL = "https://localhost:8443/auth"
API_URL  = "https://localhost:8443/api"

ATTACKER = ["10.0.0.5", "192.168.1.42", "185.220.101.5"]
NORMAL   = ["172.18.0.1", "172.18.0.3"]
USERS    = ["admin","root","user","test","guest"]
PWDS     = ["password","123456","admin","letmein","qwerty"]

def req(m, url, **kw):
    try: return getattr(requests,m)(url,timeout=5,verify=False,**kw).status_code
    except: return None

def check():
    print("[*] Verification services via gateway (port 8080)...")
    ok = True
    for n,u in [("Auth", AUTH_URL+"/health"), ("API", API_URL+"/health")]:
        s = req("get",u)
        print("    " + ("OK" if s==200 else "ERREUR") + "  " + n + " -> " + str(s))
        if s != 200: ok = False
    return ok

def brute_force(delay=0.2, **kw):
    ip = random.choice(ATTACKER)
    n  = random.randint(8, 12)
    print("[SCENARIO 1] Brute Force depuis " + ip + " - " + str(n) + " tentatives")
    for i in range(n):
        u = random.choice(USERS)
        p = random.choice(PWDS)
        s = req("post",AUTH_URL+"/login",json={"username":u,"password":p},headers={"X-Forwarded-For":ip})
        print("  [" + str(i+1) + "] " + u + ":" + p + " -> HTTP " + str(s))
        time.sleep(delay)
    print("  -> " + str(n) + " tentatives envoyees")

def forbidden_scan(delay=0.15, **kw):
    ip = random.choice(ATTACKER)
    print("[SCENARIO 2] Scan routes interdites depuis " + ip)
    routes = ["/admin","/config","/secrets","/users",
              "/debug","/env","/backup","/keys","/tokens"]
    for r in routes:
        s = req("get",API_URL+r,headers={"X-Forwarded-For":ip})
        print("  [" + str(s) + "] GET /api" + r)
        time.sleep(delay)
    print("  -> " + str(len(routes)) + " routes sondees")

def normal_traffic(delay=0.1, **kw):
    print("[SCENARIO 3] Trafic normal - 15 requetes")
    token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock"
    for i in range(15):
        ip = random.choice(NORMAL)
        c  = i % 4
        if c==0:
            s=req("post",AUTH_URL+"/login",json={"username":"admin","password":"password123"},headers={"X-Forwarded-For":ip}); e="POST /auth/login"
        elif c==1:
            s=req("get",API_URL+"/users",headers={"Authorization":token,"X-Forwarded-For":ip}); e="GET /api/users"
        elif c==2:
            s=req("get",API_URL+"/data",headers={"Authorization":token,"X-Forwarded-For":ip}); e="GET /api/data"
        else:
            s=req("get",AUTH_URL+"/health",headers={"X-Forwarded-For":ip}); e="GET /auth/health"
        print("  [" + str(i+1) + "] " + e + " -> " + str(s))
        time.sleep(delay)
    print("  -> 15 requetes normales")

def server_errors(delay=0.1, **kw):
    print("[SCENARIO 4] Generation erreurs 500 - 20 appels")
    token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock"
    errors = 0
    for i in range(20):
        ip = random.choice(NORMAL + ATTACKER)
        s  = req("get",API_URL+"/data",headers={"Authorization":token,"X-Forwarded-For":ip})
        if s == 500: errors += 1
        print("  [" + str(i+1) + "] " + ("ERREUR 500" if s==500 else "OK "+str(s)))
        time.sleep(delay)
    print("  -> " + str(errors) + "/20 erreurs 500")

def suspicious_uploads(delay=0.2, **kw):
    print("[SCENARIO 5] Uploads suspects")
    ip = random.choice(ATTACKER)
    types = ["application/x-php","application/x-shellscript",
             "application/octet-stream","text/javascript","application/x-executable"]
    for i,ct in enumerate(types):
        s = req("post",API_URL+"/upload",data=b"payload",headers={"Content-Type":ct,"X-Forwarded-For":ip})
        print("  [" + str(i+1) + "] " + ct + " -> HTTP " + str(s))
        time.sleep(delay)
    print("  -> " + str(len(types)) + " uploads envoyes")

def rate_limit_test(delay=0.05, **kw):
    """Envoie une rafale de requêtes pour déclencher le rate limiting (429) de la gateway."""
    print("[SCENARIO 6] Test rate limiting — rafale vers /api/data et /auth/login")
    token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock"
    hits_429 = 0

    print("  Phase 1 : 60 requetes /api/data en rafale (limite: 30/min, burst=50)")
    for i in range(60):
        s = req("get", API_URL+"/data", headers={"Authorization":token})
        if s == 429: hits_429 += 1
        marker = " <<< RATE LIMITED" if s == 429 else ""
        print("  [" + str(i+1) + "] HTTP " + str(s) + marker)
        time.sleep(delay)

    print("  Phase 2 : 10 tentatives /auth/login en rafale avec credentials invalides (limite: 5/min)")
    for i in range(10):
        u = random.choice(USERS)
        p = random.choice(PWDS)
        s = req("post", AUTH_URL+"/login", json={"username":u,"password":p})
        if s == 429: hits_429 += 1
        marker = " <<< RATE LIMITED" if s == 429 else ""
        print("  [" + str(i+1) + "] " + u + ":" + p + " -> HTTP " + str(s) + marker)
        time.sleep(delay)

    print("  -> " + str(hits_429) + " requetes bloquees (429) sur 70 envoyees")

SQL_PAYLOADS = [
    ("' OR '1'='1",           "classic_or"),
    ("admin'--",              "comment_bypass"),
    ("1; DROP TABLE users--", "drop_table"),
    ("' UNION SELECT 1,2,3--","union_select"),
    ("' OR SLEEP(5)--",       "time_based"),
    ("1' AND '1'='1",         "blind_injection"),
]

def sql_injection(delay=0.2, **kw):
    ip = random.choice(ATTACKER)
    print("[SCENARIO 7] SQL Injection depuis " + ip + " - " + str(len(SQL_PAYLOADS)) + " payloads")
    for i, (payload, label) in enumerate(SQL_PAYLOADS):
        s = req("post", AUTH_URL + "/login",
                json={"username": payload, "password": "x"},
                headers={"X-Forwarded-For": ip})
        print("  [" + str(i+1) + "] " + label + ": '" + payload[:35] + "' -> HTTP " + str(s))
        time.sleep(delay)
    print("  -> " + str(len(SQL_PAYLOADS)) + " tentatives SQLi envoyees")


SCANNER_AGENTS = [
    "sqlmap/1.7.8#stable (https://sqlmap.org)",
    "Nikto/2.1.6",
    "Mozilla/5.0 (compatible; Nessus; http://www.nessus.org/)",
    "masscan/1.3 (https://github.com/robertdavidgraham/masscan)",
    "Mozilla/5.0 zgrab/0.x",
    "Nuclei - Open-source project (github.com/projectdiscovery/nuclei)",
    "DirBuster-1.0-RC1",
    "gobuster/3.6",
]

def suspicious_user_agent(delay=0.2, **kw):
    ip = random.choice(ATTACKER)
    print("[SCENARIO 8] Scanners suspects depuis " + ip)
    scan_routes = [
        API_URL + "/users", API_URL + "/admin", API_URL + "/data",
        AUTH_URL + "/health", API_URL + "/config", API_URL + "/reports",
        API_URL + "/users", API_URL + "/admin",
    ]
    for i, ua in enumerate(SCANNER_AGENTS):
        endpoint = scan_routes[i % len(scan_routes)]
        s = req("get", endpoint, headers={"X-Forwarded-For": ip, "User-Agent": ua})
        print("  [" + str(i+1) + "] " + ua[:50] + " -> HTTP " + str(s))
        time.sleep(delay)
    print("  -> " + str(len(SCANNER_AGENTS)) + " requetes avec UA suspects")


GEO_ANOMALY_IPS = [
    ("195.154.167.211", "RU",  "Russia"),
    ("103.235.46.116",  "CN",  "China"),
    ("175.45.176.3",    "KP",  "North Korea"),
    ("5.61.27.157",     "IR",  "Iran"),
    ("185.220.101.5",   "TOR", "Tor Exit Node"),
    ("41.223.27.133",   "NG",  "Nigeria"),
    ("91.121.45.22",    "RU",  "Russia"),
]

def geo_anomaly(delay=0.3, **kw):
    print("[SCENARIO 9] Anomalies geographiques - " + str(len(GEO_ANOMALY_IPS)) + " IPs")
    geo_routes = [API_URL + "/users", API_URL + "/admin", API_URL + "/data",
                  AUTH_URL + "/health", API_URL + "/reports"]
    for i, (ip, code, country) in enumerate(GEO_ANOMALY_IPS):
        endpoint = geo_routes[i % len(geo_routes)]
        s = req("get", endpoint, headers={"X-Forwarded-For": ip})
        print("  [" + code + "] " + ip + " (" + country + ") -> HTTP " + str(s))
        time.sleep(delay)
    print("  -> " + str(len(GEO_ANOMALY_IPS)) + " IPs suspectes testees")


SCENARIOS = {
    "brute-force":       brute_force,
    "forbidden-scan":    forbidden_scan,
    "normal":            normal_traffic,
    "server-errors":     server_errors,
    "suspicious-upload": suspicious_uploads,
    "rate-limit":        rate_limit_test,
    "sql-injection":     sql_injection,
    "scanner-ua":        suspicious_user_agent,
    "geo-anomaly":       geo_anomaly,
}

def main():
    p = argparse.ArgumentParser(description="Simulateur attaques PFA 2025-2026")
    p.add_argument("--scenario", choices=list(SCENARIOS.keys())+["all"], default="all")
    p.add_argument("--delay", type=float, default=0.2)
    a = p.parse_args()
    print("="*50); print("  SecureWatch - Simulateur Attaques PFA"); print("="*50)
    if not check():
        print("[!] Gateway inaccessible. Verifier : docker-compose ps"); sys.exit(1)
    if a.scenario == "all":
        for fn in SCENARIOS.values():
            fn(delay=a.delay); time.sleep(1)
    else:
        SCENARIOS[a.scenario](delay=a.delay)
    print("[OK] Simulation terminee.")
    print("     Gateway    : https://localhost:8443  (HTTP :8080 redirige)")
    print("     Dashboard  : http://localhost:3000")
    print("     Kibana     : http://localhost:5601")
    print("     Grafana    : http://localhost:3001  (admin / changeme)")
    print("     Prometheus : http://localhost:9090")
    print("     Analyse    : python scripts/analyse_logs.py")

if __name__ == "__main__":
    main()
