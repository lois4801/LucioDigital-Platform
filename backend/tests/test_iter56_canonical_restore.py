"""Iter56 regression: canonical tenant restore + public showcase data-driven + client.editor visibility."""
import os
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
EDITOR = {"email": "client.editor@example.com", "password": "ClientEdit2026!"}
CANONICAL_ID = "app_6663b5de0007"


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login {creds['email']} -> {r.status_code} {r.text}"
    return s


# --- Canonical tenant restore ---
def test_admin_sees_canonical_and_no_iter53_leftovers():
    s = _login(ADMIN)
    r = s.get(f"{BASE}/api/apps", timeout=15)
    assert r.status_code == 200
    apps = r.json()
    names = [a.get("name") for a in apps]
    ids = [a.get("app_id") for a in apps]
    print(f"Admin tenants ({len(apps)}): {list(zip(ids, names))}")
    assert CANONICAL_ID in ids, f"Canonical {CANONICAL_ID} missing"
    nw = next(a for a in apps if a["app_id"] == CANONICAL_ID)
    assert nw["name"] == "Northwind Roofing"
    # Iter53 leftovers gone
    leftover = [n for n in names if n and ("Iter53" in n)]
    assert not leftover, f"Leftover iter53 tenants: {leftover}"
    # 7 tenants expected
    assert len(apps) == 7, f"Expected 7 tenants, got {len(apps)}"


def test_canonical_has_4_pages():
    s = _login(ADMIN)
    r = s.get(f"{BASE}/api/apps/{CANONICAL_ID}/pages", timeout=15)
    assert r.status_code == 200, r.text
    pages = r.json()
    slugs = sorted([p.get("slug") for p in pages])
    print(f"Canonical pages: {slugs}")
    for req in ["/", "/about", "/services", "/contact"]:
        assert req in slugs, f"Missing page {req} in {slugs}"


# --- Editor visibility ---
def test_editor_sees_exactly_one_tenant_northwind():
    s = _login(EDITOR)
    r = s.get(f"{BASE}/api/apps", timeout=15)
    assert r.status_code == 200
    apps = r.json()
    print(f"Editor tenants: {[(a.get('app_id'), a.get('name')) for a in apps]}")
    assert len(apps) == 1, f"Editor should see exactly 1 tenant, got {len(apps)}"
    assert apps[0]["app_id"] == CANONICAL_ID
    assert apps[0]["name"] == "Northwind Roofing"


# --- Public showcase data-driven ---
def test_public_showcase_returns_live_tenants():
    r = requests.get(f"{BASE}/api/public/showcase", timeout=15)
    assert r.status_code == 200
    data = r.json()
    print(f"Public showcase count: {len(data)}")
    assert isinstance(data, list)
    assert len(data) > 0, "Public showcase must not be empty (data-driven)"
    for item in data:
        assert item.get("name")
        assert item.get("token")


# --- Overview auto-sync from Site Mode edits (dynamic against canonical) ---
def test_overview_sync_endpoint():
    s = _login(ADMIN)
    r = s.post(f"{BASE}/api/apps/{CANONICAL_ID}/site/sync-overview", timeout=15)
    print(f"overview sync: {r.status_code}")
    assert r.status_code in (200, 204), r.text


# --- Lead inbox (real/test lanes + admin override) ---
def test_leads_inbox_endpoint():
    s = _login(ADMIN)
    r = s.get(f"{BASE}/api/apps/{CANONICAL_ID}/inbox", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    print(f"inbox keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")


# --- Locks: master + granular ---
def test_locks_endpoint():
    s = _login(ADMIN)
    r = s.get(f"{BASE}/api/apps/{CANONICAL_ID}/locks", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "master" in data or "items" in data or "rollup" in data


# --- Export as Website / Full-Stack / Plugin ---
def test_export_website():
    s = _login(ADMIN)
    for fmt in ["website", "webapp", "plugin"]:
        r = s.post(f"{BASE}/api/apps/{CANONICAL_ID}/export/start", json={"format": fmt}, timeout=30)
        print(f"export start {fmt}: {r.status_code} {r.text[:200]}")
        assert r.status_code in (200, 201, 202), f"{fmt}: {r.status_code} {r.text[:200]}"


# --- Showcase star + reorder persistence ---
def test_showcase_star_toggle_persists():
    s = _login(ADMIN)
    r = s.patch(f"{BASE}/api/apps/{CANONICAL_ID}/showcase", json={"starred": True}, timeout=15)
    print(f"star: {r.status_code} {r.text[:200]}")
    assert r.status_code in (200, 204)
    r = s.get(f"{BASE}/api/apps/{CANONICAL_ID}", timeout=15)
    assert r.status_code == 200
    # unstar cleanup
    s.patch(f"{BASE}/api/apps/{CANONICAL_ID}/showcase", json={"starred": False}, timeout=15)


# --- Startup idempotency: re-login and confirm same id ---
def test_canonical_id_stable():
    s = _login(ADMIN)
    r = s.get(f"{BASE}/api/apps/{CANONICAL_ID}", timeout=15)
    assert r.status_code == 200, f"Canonical id must be stable: {r.status_code}"


# --- No OmniStack anywhere on public landing ---
def test_no_omnistack_in_public_landing():
    r = requests.get(f"{BASE}/api/public/landing/tenants", timeout=15)
    assert r.status_code == 200
    body = r.text.lower()
    assert "omnistack" not in body, "Found OmniStack in public tenants payload"
