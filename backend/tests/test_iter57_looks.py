"""Iter57 - Per-template unique visual identity + mode toggle + retheme_all coverage."""
import os
import pytest
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0]).rstrip("/")
API = f"{BASE}/api"

ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
EDITOR = {"email": "client.editor@example.com", "password": "ClientEdit2026!"}

# Expected fingerprints for the six canonical demo tenants + Northwind
EXPECTED = {
    "app_009e5e117f77": {"niche": "retail", "mode": "light", "font_heading": "Cormorant Garamond", "preset": "editoriallux"},
    "app_04366e4b6d97": {"niche": "saas", "mode": "dark", "font_heading": "Plus Jakarta Sans", "preset": "saas"},
    "app_cca4d5dd736d": {"niche": "logistics", "mode": "dark", "font_heading": "Barlow Condensed", "preset": "freight"},
    "app_b86054a26f34": {"niche": "fitness", "mode": "dark", "font_heading": "Syne", "preset": "energy"},
    "app_77d30fefb622": {"niche": "finance", "mode": "dark", "font_heading": "Lora", "preset": "ledger"},
    "app_b96a63e4b700": {"niche": "creative_studio", "mode": "dark", "font_heading": "Syne", "preset": "noir"},
    "app_6663b5de0007": {"niche": "construction", "mode": "dark", "font_heading": "Oswald", "preset": "concrete"},
}


@pytest.fixture(scope="module")
def admin_sess():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def editor_sess():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=EDITOR, timeout=15)
    assert r.status_code == 200, r.text
    return s


# --- 1. auth / basics ---
def test_admin_login(admin_sess):
    r = admin_sess.get(f"{API}/apps", timeout=15)
    assert r.status_code == 200
    assert len(r.json()) >= 7


def test_editor_sees_only_northwind(editor_sess):
    r = editor_sess.get(f"{API}/apps", timeout=15)
    assert r.status_code == 200
    apps = r.json()
    assert len(apps) == 1, f"editor should see 1 tenant, got {len(apps)}"
    assert apps[0]["app_id"] == "app_6663b5de0007"


# --- 2. Each canonical tenant carries the expected unique theme ---
@pytest.mark.parametrize("app_id,expected", list(EXPECTED.items()))
def test_tenant_unique_theme(admin_sess, app_id, expected):
    r = admin_sess.get(f"{API}/apps/{app_id}", timeout=15)
    assert r.status_code == 200, f"{app_id}: {r.status_code}"
    app = r.json()
    assert app.get("site_niche") == expected["niche"], f"{app_id} niche"
    theme = app.get("theme") or {}
    assert theme.get("mode") == expected["mode"], f"{app_id} mode {theme.get('mode')}"
    assert theme.get("font_heading") == expected["font_heading"], f"{app_id} font"
    assert theme.get("site_preset") == expected["preset"], f"{app_id} preset"
    assert theme.get("look_v") == 1, f"{app_id} look_v"


# --- 3. All 7 look_v are unique combinations ---
def test_themes_are_visually_distinct(admin_sess):
    fingerprints = set()
    for app_id in EXPECTED:
        r = admin_sess.get(f"{API}/apps/{app_id}", timeout=15)
        t = r.json().get("theme") or {}
        fp = (t.get("primary"), t.get("bg"), t.get("font_heading"), t.get("site_preset"), t.get("radius"))
        fingerprints.add(fp)
    assert len(fingerprints) == len(EXPECTED), f"themes not all unique: {fingerprints}"


# --- 4. Template apply maps to unique theme (throwaway tenant) ---
@pytest.fixture(scope="module")
def throwaway(admin_sess):
    r = admin_sess.post(f"{API}/apps", json={"name": "TEST_iter57_throwaway", "description": "temp", "industry": "SaaS"}, timeout=15)
    assert r.status_code in (200, 201), r.text
    app_id = r.json()["app_id"]
    yield app_id
    admin_sess.delete(f"{API}/apps/{app_id}", timeout=15)


@pytest.mark.parametrize("key,expected_preset,expected_font", [
    ("retail", "editoriallux", "Cormorant Garamond"),
    ("fitness", "energy", "Syne"),
    ("finance", "ledger", "Lora"),
    ("logistics", "freight", "Barlow Condensed"),
])
def test_template_apply_sets_unique_theme(admin_sess, throwaway, key, expected_preset, expected_font):
    r = admin_sess.post(f"{API}/apps/{throwaway}/templates/{key}/apply", timeout=20)
    assert r.status_code == 200, r.text
    theme = r.json().get("theme") or {}
    assert theme.get("site_preset") == expected_preset
    assert theme.get("font_heading") == expected_font
    # verify persisted
    g = admin_sess.get(f"{API}/apps/{throwaway}", timeout=15).json()
    assert (g.get("theme") or {}).get("site_preset") == expected_preset
    assert g.get("site_niche") == key


# --- 5. Mode toggle + save via PUT /apps/{id}/theme persists ---
def test_theme_mode_toggle_persists(admin_sess, throwaway):
    # apply light retail first
    admin_sess.post(f"{API}/apps/{throwaway}/templates/retail/apply", timeout=15)
    # Now switch to dark & manually override primary
    r = admin_sess.put(f"{API}/apps/{throwaway}/theme", json={"theme": {"mode": "dark", "primary": "#FF00AA"}}, timeout=15)
    assert r.status_code == 200, r.text
    g = admin_sess.get(f"{API}/apps/{throwaway}", timeout=15).json()
    theme = g.get("theme") or {}
    assert theme.get("mode") == "dark"
    assert theme.get("primary") == "#FF00AA"


# --- 6. Public preview endpoints reachable ---
PREVIEW_TOKENS = {
    "pv_62958c58ce0422a1a58b": "retail",  # Maison Verde
}


def test_public_showcase_returns_tenants():
    r = requests.get(f"{API}/public/showcase", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 6


def test_public_landing_tenants():
    r = requests.get(f"{API}/public/landing/tenants", timeout=15)
    assert r.status_code == 200
    data = r.json()
    tenants = data["tenants"] if isinstance(data, dict) else data
    assert len(tenants) >= 1
