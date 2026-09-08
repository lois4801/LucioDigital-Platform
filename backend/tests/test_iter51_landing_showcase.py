"""Iteration 51 — dynamic landing showcase (templates + tenants)."""
import os
import time
import requests
import pytest

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASS = "Lucio2026!"

EXPECTED_NICHE_TITLES = {  # from site_content.NICHES — allow platform variants
    "Construction", "Creative Studio", "E-commerce", "Education", "Events",
    "Finance", "Fitness", "HVAC", "Healthcare", "Hospitality", "IT Services",
    "Legal", "Real Estate", "SaaS",
}


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return s


# ---------- /public/landing/templates ----------
def test_public_templates_returns_16_sorted():
    r = requests.get(f"{BASE}/api/public/landing/templates")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 16, f"expected 16 niches, got {d['count']}"
    titles = [t["title"] for t in d["templates"]]
    assert titles == sorted(titles), "templates must be sorted by title"
    # each row has the required keys
    for t in d["templates"]:
        for k in ("key", "title", "brand", "description", "image", "primary", "sections"):
            assert k in t, f"missing key {k} in template"
        assert t["image"].startswith("http")
        assert isinstance(t["sections"], int)
    # broadly matches platform niches (allow 'Restaurants'/'Restaurant', 'SaaS Portals'/'SaaS')
    joined = " ".join(titles)
    for expected in EXPECTED_NICHE_TITLES:
        assert expected.split()[0] in joined, f"missing niche keyword {expected} — titles={titles}"


# ---------- /public/landing/tenants ----------
def test_public_tenants_shape_and_owner_match(admin_session):
    r = requests.get(f"{BASE}/api/public/landing/tenants")
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d["tenants"], list)
    assert d["count"] == len(d["tenants"])
    assert d["live"] == sum(1 for t in d["tenants"] if t["status"] == "LIVE")
    for t in d["tenants"]:
        assert t["status"] in ("LIVE", "TEMPLATE")
        for k in ("app_id", "name", "tag", "cover", "niche", "summary"):
            assert k in t
    # Compare vs admin-owned apps
    me = admin_session.get(f"{BASE}/api/apps").json()
    owned_ids = {a["app_id"] for a in (me if isinstance(me, list) else me.get("apps", []))
                 if not a.get("is_deleted")}
    endpoint_ids = {t["app_id"] for t in d["tenants"]}
    # endpoint tenants must be a subset of admin-owned, non-deleted apps
    assert endpoint_ids.issubset(owned_ids), f"endpoint has apps not owned by admin: {endpoint_ids-owned_ids}"


# ---------- auto-sync on create + delete + status flip ----------
@pytest.fixture(scope="module")
def throwaway_app(admin_session):
    name = f"TEST_iter51_{int(time.time())}"
    r = admin_session.post(f"{BASE}/api/apps", json={"name": name, "industry": "E-commerce", "kind": "website"})
    assert r.status_code in (200, 201), r.text
    app = r.json()
    yield app
    # teardown — best-effort delete
    admin_session.delete(f"{BASE}/api/apps/{app['app_id']}")


def _fetch_landing_tenants():
    return requests.get(f"{BASE}/api/public/landing/tenants").json()


def test_create_tenant_appears_as_template(admin_session, throwaway_app):
    # Since iteration 52 the showcase shows starred tenants when any are starred,
    # so star the throwaway app to assert it surfaces publicly.
    admin_session.patch(f"{BASE}/api/apps/{throwaway_app['app_id']}/showcase", json={"featured": True})
    time.sleep(0.5)
    d = _fetch_landing_tenants()
    match = [t for t in d["tenants"] if t["app_id"] == throwaway_app["app_id"]]
    assert match, f"throwaway app {throwaway_app['app_id']} missing from landing tenants"
    assert match[0]["status"] == "TEMPLATE", f"new app should default to TEMPLATE, got {match[0]['status']}"
    assert match[0]["name"] == throwaway_app["name"]


def test_status_flips_to_live_when_active_and_preview(admin_session, throwaway_app):
    # Enable preview (POST toggle) and set status=active via PATCH
    admin_session.patch(f"{BASE}/api/apps/{throwaway_app['app_id']}/showcase", json={"featured": True})
    tog = admin_session.post(f"{BASE}/api/apps/{throwaway_app['app_id']}/preview/toggle")
    assert tog.status_code == 200, tog.text
    assert tog.json().get("preview_enabled") is True
    r = admin_session.patch(f"{BASE}/api/apps/{throwaway_app['app_id']}", json={"status": "active"})
    assert r.status_code in (200, 204), r.text
    time.sleep(0.3)
    d = _fetch_landing_tenants()
    m = [t for t in d["tenants"] if t["app_id"] == throwaway_app["app_id"]][0]
    assert m["status"] == "LIVE", f"expected LIVE after active+preview, got {m['status']}"
    assert m["token"], "preview token should be exposed when preview_enabled=true"


def test_status_flips_back_to_template(admin_session, throwaway_app):
    # Toggle preview OFF => flips to TEMPLATE
    admin_session.patch(f"{BASE}/api/apps/{throwaway_app['app_id']}/showcase", json={"featured": True})
    tog = admin_session.post(f"{BASE}/api/apps/{throwaway_app['app_id']}/preview/toggle")
    assert tog.status_code == 200, tog.text
    assert tog.json().get("preview_enabled") is False
    time.sleep(0.3)
    d = _fetch_landing_tenants()
    m = [t for t in d["tenants"] if t["app_id"] == throwaway_app["app_id"]][0]
    assert m["status"] == "TEMPLATE"
    assert m["token"] in (None, ""), "token should NOT leak when preview disabled"


def test_delete_tenant_disappears(admin_session, throwaway_app):
    r = admin_session.delete(f"{BASE}/api/apps/{throwaway_app['app_id']}")
    assert r.status_code in (200, 204), r.text
    time.sleep(0.5)
    d = _fetch_landing_tenants()
    assert throwaway_app["app_id"] not in {t["app_id"] for t in d["tenants"]}, \
        "deleted app must disappear from public tenants endpoint"


# ---------- endpoint is public (no auth) ----------
def test_endpoints_are_public():
    for path in ("/api/public/landing/templates", "/api/public/landing/tenants"):
        r = requests.get(f"{BASE}{path}")
        assert r.status_code == 200, f"{path} not public: {r.status_code}"
