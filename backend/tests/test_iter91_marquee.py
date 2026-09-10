"""Marquee ribbon tests: public spec, per-app resolve, PUT validation, reset, and template/site payloads."""
import os
import pytest
import requests
from pathlib import Path

def _load_frontend_url():
    env = Path("/app/frontend/.env").read_text()
    for line in env.splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip()
    return None

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_url()).rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"
TESTLAB_APP = "app_testlab"


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Login failed {r.status_code} {r.text}"
    return s


# ── Public marquee spec by template key ──────────────────────────────
@pytest.mark.parametrize("key", ["hvac", "dental", "saas", "test_template"])
def test_public_marquee_known_keys(key):
    r = requests.get(f"{API}/public/marquee/{key}")
    assert r.status_code == 200
    d = r.json()
    for f in ("top_text", "bottom_text", "speed", "stroke_opacity", "font_size", "enabled"):
        assert f in d, f"Missing {f} in {d}"
    assert isinstance(d["top_text"], str) and len(d["top_text"]) > 0
    assert isinstance(d["bottom_text"], str) and len(d["bottom_text"]) > 0
    assert d["enabled"] is True


def test_public_marquee_fallback_unknown():
    r = requests.get(f"{API}/public/marquee/does_not_exist_xyz")
    assert r.status_code == 200
    d = r.json()
    assert d["top_text"] and d["bottom_text"]
    assert 0.2 <= d["speed"] <= 3
    assert 0.05 <= d["stroke_opacity"] <= 1


# ── Per-app marquee (master workspace app_testlab) ────────────────────
def test_get_app_marquee_testlab(admin_session):
    r = admin_session.get(f"{API}/apps/{TESTLAB_APP}/marquee")
    assert r.status_code == 200
    d = r.json()
    for f in ("top_text", "bottom_text", "speed", "stroke_opacity", "font_size", "enabled"):
        assert f in d


def test_put_marquee_saves_and_persists(admin_session):
    payload = {"top_text": "TEST_TOP_RIBBON", "bottom_text": "TEST_BOTTOM_RIBBON",
               "speed": 1.2, "stroke_opacity": 0.4, "font_size": 1.1, "enabled": True}
    r = admin_session.put(f"{API}/apps/{TESTLAB_APP}/marquee", json=payload)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["top_text"] == "TEST_TOP_RIBBON"
    assert d["bottom_text"] == "TEST_BOTTOM_RIBBON"
    assert d["speed"] == 1.2
    # verify persistence
    g = admin_session.get(f"{API}/apps/{TESTLAB_APP}/marquee").json()
    assert g["top_text"] == "TEST_TOP_RIBBON"
    assert g["speed"] == 1.2


@pytest.mark.parametrize("field,value", [
    ("speed", 0.1), ("speed", 3.5),
    ("stroke_opacity", 0.01), ("stroke_opacity", 1.5),
    ("font_size", 0.4), ("font_size", 2.6),
])
def test_put_marquee_rejects_out_of_range(admin_session, field, value):
    r = admin_session.put(f"{API}/apps/{TESTLAB_APP}/marquee", json={field: value})
    assert r.status_code == 400, f"Expected 400 for {field}={value}, got {r.status_code}"


def test_put_marquee_caps_text_at_160(admin_session):
    long = "A" * 300
    r = admin_session.put(f"{API}/apps/{TESTLAB_APP}/marquee", json={"top_text": long})
    assert r.status_code == 200
    assert len(r.json()["top_text"]) == 160


def test_reset_marquee_restores_template(admin_session):
    # Save something custom
    admin_session.put(f"{API}/apps/{TESTLAB_APP}/marquee", json={"top_text": "OVERRIDE"})
    r = admin_session.post(f"{API}/apps/{TESTLAB_APP}/marquee/reset")
    assert r.status_code == 200
    d = r.json()
    # Should be the template phrase, not OVERRIDE
    assert d["top_text"] != "OVERRIDE"
    assert "LUCIODIGITAL" in d["top_text"].upper() or len(d["top_text"]) > 0


# ── Public template detail includes marquee ──────────────────────────
def test_template_detail_includes_marquee():
    r = requests.get(f"{API}/public/templates/hvac")
    assert r.status_code == 200, r.text
    body = r.json()
    site = body.get("site") or body
    assert "marquee" in site, f"marquee missing in template detail: keys={list(body.keys())}"
    m = site["marquee"]
    assert m.get("top_text") and m.get("bottom_text")


# ── Public site (master workspace) exposes app.marquee ────────────────
def test_public_site_includes_marquee(admin_session):
    # find preview_token for app_testlab
    apps = admin_session.get(f"{API}/apps").json()
    app_list = apps if isinstance(apps, list) else apps.get("apps", [])
    tok = None
    for a in app_list:
        if a.get("app_id") == TESTLAB_APP:
            tok = a.get("preview_token")
            break
    assert tok, "no preview_token for testlab"
    r = requests.get(f"{API}/public/site/{tok}")
    assert r.status_code == 200, r.text
    d = r.json()
    app = d.get("app") or {}
    assert "marquee" in app or "marquee" in d, f"marquee missing; top keys={list(d.keys())}"
