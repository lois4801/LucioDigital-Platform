"""Iteration 71 — Motion Showcase Reel + Hero motion tuning persistence."""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
TOKEN = "pv_c3b797fcdafc58d4e70e320f"
APP_ID = "app_testlab"
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PW = "Lucio2026!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=15)
    assert r.status_code == 200, r.text
    return s


# ---------------- Public motion reel ----------------
def test_public_motion_reel():
    r = requests.get(f"{BASE_URL}/api/public/motion-reel", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert len(d.get("heroes", [])) >= 40
    assert len(d.get("industries", [])) >= 40
    h = d["heroes"][0]
    for k in ("hero", "industry", "accent"):
        assert k in h, f"missing {k} on hero"


def test_public_motion_pick_validation():
    # empty email should be rejected
    r = requests.post(f"{BASE_URL}/api/public/motion-picks",
                      json={"hero": "aurora-wave", "name": "Test", "email": ""}, timeout=15)
    assert r.status_code in (400, 422), r.status_code


def test_public_motion_pick_create_and_list(session):
    unique = f"TEST_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "hero": "aurora-wave", "name": "TEST_Bot", "email": unique,
        "industry": "SaaS", "speed": 1.25, "intensity": 0.8, "accent": "#22D3EE",
    }
    r = requests.post(f"{BASE_URL}/api/public/motion-picks", json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    resp = r.json()
    assert resp.get("ok") is True or "id" in resp

    # list from dashboard side
    lr = session.get(f"{BASE_URL}/api/motion-picks", timeout=15)
    assert lr.status_code == 200, lr.text
    picks = lr.json().get("picks", lr.json() if isinstance(lr.json(), list) else [])
    assert any((p.get("email") or "").lower() == unique.lower() for p in picks), "created pick not returned in /api/motion-picks"


# ---------------- Site-mode motion_speed / motion_intensity persistence ----------------
def test_sitemode_speed_intensity_validation(session):
    r = session.put(f"{BASE_URL}/api/apps/{APP_ID}/site-mode",
                    json={"motion_speed": 9}, timeout=15)
    assert r.status_code == 400, f"expected 400 for out-of-range speed, got {r.status_code}: {r.text}"

    r2 = session.put(f"{BASE_URL}/api/apps/{APP_ID}/site-mode",
                     json={"motion_intensity": 5}, timeout=15)
    assert r2.status_code == 400, f"expected 400 for out-of-range intensity, got {r2.status_code}: {r2.text}"


def test_sitemode_speed_intensity_persist_and_public_reflects(session):
    # Save specific values
    payload = {"hero": "pipe-flow-trace", "motion_speed": 1.5, "motion_intensity": 1.1}
    r = session.put(f"{BASE_URL}/api/apps/{APP_ID}/site-mode", json=payload, timeout=15)
    assert r.status_code == 200, r.text

    # GET site-mode from dashboard
    g = session.get(f"{BASE_URL}/api/apps/{APP_ID}/site-mode", timeout=15)
    assert g.status_code == 200
    sm = g.json()
    assert sm.get("motion_speed") == 1.5
    assert sm.get("motion_intensity") == 1.1
    assert sm.get("hero") == "pipe-flow-trace"
    assert sm.get("preview_token")

    # Public /public/site/{token} should reflect these values under motion_profile + site_mode
    pr = requests.get(f"{BASE_URL}/api/public/site/{TOKEN}", timeout=15)
    assert pr.status_code == 200
    body = pr.json()
    app = body.get("app", {})
    mp = app.get("motion_profile", {})
    smp = app.get("site_mode", {})
    assert mp.get("hero") == "pipe-flow-trace"
    assert mp.get("speed") == 1.5
    assert mp.get("intensity") == 1.1
    assert smp.get("hero") == "pipe-flow-trace"


def test_sitemode_hero_override_wins_over_template(session):
    # Change to a different hero and confirm public shows overridden hero
    r = session.put(f"{BASE_URL}/api/apps/{APP_ID}/site-mode",
                    json={"hero": "aurora-wave", "motion_speed": 1.0, "motion_intensity": 1.0}, timeout=15)
    assert r.status_code == 200
    time.sleep(0.5)
    pr = requests.get(f"{BASE_URL}/api/public/site/{TOKEN}", timeout=15)
    assert pr.status_code == 200
    app = pr.json().get("app", {})
    assert app.get("motion_profile", {}).get("hero") == "aurora-wave"
    assert app.get("site_mode", {}).get("hero") == "aurora-wave"

    # Restore sensible defaults so downstream UI tests aren't confused
    session.put(f"{BASE_URL}/api/apps/{APP_ID}/site-mode",
                json={"hero": "pipe-flow-trace", "motion_speed": 1.5, "motion_intensity": 1.1}, timeout=15)
