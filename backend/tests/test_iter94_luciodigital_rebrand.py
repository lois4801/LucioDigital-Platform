"""Iter94 — LucioDigital rebrand backend tests."""
import os, re, pytest, requests
from pathlib import Path

def _load_env():
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
_load_env()
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PW = "Lucio2026!"
PREVIEW_TOKEN = "pv_c3b797fcdafc58d4e70e320f"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# Favicon
def test_favicon_svg_loads():
    r = requests.get(f"{BASE}/favicon.svg", timeout=15)
    assert r.status_code == 200
    assert "svg" in r.headers.get("content-type", "").lower()
    assert "<svg" in r.text


# No 'Lois-Tech' in public API responses
def test_public_site_has_no_loistech():
    r = requests.get(f"{BASE}/api/public/site/{PREVIEW_TOKEN}", timeout=20)
    assert r.status_code == 200
    body = r.text
    # allow the css class name lois-reviews since it's not user-visible copy
    stripped = re.sub(r"lois-reviews", "", body, flags=re.I)
    for token in ["Lois-Tech", "Lois Tech", "lois-tech"]:
        assert token.lower() not in stripped.lower(), f"Found {token!r} in /api/public/site response"


def test_admin_landing_no_loistech(session):
    # /public/landing is the public read endpoint; /admin/landing is PUT-only
    r = session.get(f"{BASE}/api/public/landing", timeout=15)
    assert r.status_code == 200
    body = r.text.lower()
    body_stripped = re.sub(r"lois-reviews", "", body)
    for token in ["lois-tech", "lois tech"]:
        assert token not in body_stripped, f"Found {token!r} in /api/public/landing"


# Auth providers still works and brands as LucioDigital
def test_auth_providers():
    r = requests.get(f"{BASE}/api/auth/providers", timeout=15)
    assert r.status_code == 200
    data = r.json()
    # from_name should be LucioDigital
    if isinstance(data, dict) and "from_name" in data:
        assert "LucioDigital" in data["from_name"] or data["from_name"] == "LucioDigital"


def test_magic_link_endpoint_reachable():
    # do NOT need a real send — just verify endpoint responds (allow 4xx from throttling)
    r = requests.post(f"{BASE}/api/auth/magic-link", json={"email": "delivered@resend.dev"}, timeout=20)
    assert r.status_code < 500, f"magic-link 5xx: {r.status_code} {r.text[:200]}"


# Lime accent still reserved for platform
def test_lime_accent_rejected_on_client_site_mode(session):
    r = session.put(
        f"{BASE}/api/apps/app_testlab/site-mode",
        json={"accent": "#84FF00"},
        timeout=15,
    )
    assert r.status_code == 400, f"expected 400 for lime accent, got {r.status_code}: {r.text[:200]}"


# Dashboard/clients still load
def test_dashboard_apps_load(session):
    r = session.get(f"{BASE}/api/apps", timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, (list, dict))
