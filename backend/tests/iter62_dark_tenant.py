"""Iter62 — create a throwaway dark tenant, print its preview token + primary."""
import os, time, requests, json, sys

BASE = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()
API = BASE.rstrip("/") + "/api"

s = requests.Session()
r = s.post(f"{API}/auth/login", json={"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}, timeout=15)
assert r.status_code == 200, r.text

tpl = sys.argv[1] if len(sys.argv) > 1 else "fitness"
r = s.post(f"{API}/apps", json={
    "name": f"TEST_dark_{tpl}_{int(time.time())%100000}", "industry": tpl,
    "template_key": tpl, "kind": "website", "status": "development", "tags": [], "color": "#111",
}, timeout=30)
assert r.status_code in (200, 201), r.text
aid = r.json()["app_id"]

r2 = s.post(f"{API}/apps/{aid}/preview/regenerate", timeout=15)
tok = r2.json()["preview_token"]

# fetch site to get theme
r3 = requests.get(f"{API}/public/site/{tok}", timeout=15)
site = r3.json()
print(json.dumps({"app_id": aid, "token": tok, "theme": site["theme"]}))
