"""Iteration 85 — Animation speed control + per-section animations.
Tests PUT/GET /api/apps/{id}/site-mode {box_speed, box_stagger, box_anim_sections}:
- box_speed 0.5..2.0 accepted, out-of-range rejected 400
- box_stagger 0..200 accepted, out-of-range rejected 400
- box_anim_sections: 9 valid keys, strips empties, rejects unknown section/animation
- GET returns box_speed (default 1.0), box_stagger (default 90), box_anim_sections
- options.box_sections lists the 9 section keys
- Public /api/public/site/{token} exposes all three fields
- Non-member gets 403/404 on site-mode writes
"""
import os
import pytest
import requests


def _load_url():
    v = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    return ""


BASE_URL = _load_url()
API = f"{BASE_URL}/api"
APP_ID = "app_testlab"
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}

SECTIONS = ("hero", "services", "testimonials", "team", "pricing",
            "stats", "gallery", "faq", "contact")

SOME_ANIMS = ("zoom", "blinds", "bounce", "fade", "spin", "wipe",
              "checkerboard", "dissolve", "spiral-in")


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    yield s
    # teardown - restore defaults
    s.put(f"{API}/apps/{APP_ID}/site-mode", json={
        "box_anim": "", "box_speed": 1.0, "box_stagger": 90, "box_anim_sections": {}
    }, timeout=20)


# --- GET defaults / options.box_sections ---
def test_get_defaults_and_options(client):
    # ensure a clean baseline
    client.put(f"{API}/apps/{APP_ID}/site-mode", json={
        "box_speed": 1.0, "box_stagger": 90, "box_anim_sections": {}
    }, timeout=20)
    r = client.get(f"{API}/apps/{APP_ID}/site-mode", timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("box_speed") == 1.0, d.get("box_speed")
    assert d.get("box_stagger") == 90, d.get("box_stagger")
    assert d.get("box_anim_sections") == {}, d.get("box_anim_sections")
    opts = d.get("options") or {}
    bs = opts.get("box_sections") or []
    assert len(bs) == 9, f"expected 9, got {len(bs)}: {bs}"
    assert set(bs) == set(SECTIONS)


# --- box_speed range ---
@pytest.mark.parametrize("v", [0.5, 1.0, 1.5, 2.0])
def test_box_speed_accepts_valid(client, v):
    r = client.put(f"{API}/apps/{APP_ID}/site-mode", json={"box_speed": v}, timeout=20)
    assert r.status_code == 200, r.text
    g = client.get(f"{API}/apps/{APP_ID}/site-mode", timeout=20).json()
    assert abs(float(g["box_speed"]) - v) < 1e-6


@pytest.mark.parametrize("v", [0.49, 0.1, 2.01, 3.0, -1.0])
def test_box_speed_rejects_out_of_range(client, v):
    r = client.put(f"{API}/apps/{APP_ID}/site-mode", json={"box_speed": v}, timeout=20)
    assert r.status_code == 400, f"expected 400 for {v}, got {r.status_code}: {r.text[:200]}"
    detail = (r.json().get("detail") or "")
    assert "Entrance speed must be between 0.5x and 2x" in detail, detail


# --- box_stagger range ---
@pytest.mark.parametrize("v", [0, 40, 90, 200])
def test_box_stagger_accepts_valid(client, v):
    r = client.put(f"{API}/apps/{APP_ID}/site-mode", json={"box_stagger": v}, timeout=20)
    assert r.status_code == 200, r.text
    g = client.get(f"{API}/apps/{APP_ID}/site-mode", timeout=20).json()
    assert int(g["box_stagger"]) == v


@pytest.mark.parametrize("v", [-1, -50, 201, 500])
def test_box_stagger_rejects_out_of_range(client, v):
    r = client.put(f"{API}/apps/{APP_ID}/site-mode", json={"box_stagger": v}, timeout=20)
    assert r.status_code == 400, f"expected 400 for {v}, got {r.status_code}: {r.text[:200]}"
    detail = (r.json().get("detail") or "")
    assert "Stagger must be between 0 and 200ms" in detail, detail


# --- box_anim_sections ---
def test_sections_accept_valid_map(client):
    payload = {s: SOME_ANIMS[i] for i, s in enumerate(SECTIONS)}
    r = client.put(f"{API}/apps/{APP_ID}/site-mode",
                   json={"box_anim_sections": payload}, timeout=20)
    assert r.status_code == 200, r.text
    g = client.get(f"{API}/apps/{APP_ID}/site-mode", timeout=20).json()
    got = g.get("box_anim_sections") or {}
    assert got == payload, got


def test_sections_strip_empty_values(client):
    # seed with values
    client.put(f"{API}/apps/{APP_ID}/site-mode",
               json={"box_anim_sections": {"hero": "zoom", "services": "blinds"}},
               timeout=20)
    # empty string should clear that section (strip)
    r = client.put(f"{API}/apps/{APP_ID}/site-mode",
                   json={"box_anim_sections": {"hero": "", "services": "blinds"}},
                   timeout=20)
    assert r.status_code == 200, r.text
    g = client.get(f"{API}/apps/{APP_ID}/site-mode", timeout=20).json()
    got = g.get("box_anim_sections") or {}
    assert "hero" not in got, f"hero should have been stripped: {got}"
    assert got.get("services") == "blinds", got


def test_sections_reject_unknown_section(client):
    r = client.put(f"{API}/apps/{APP_ID}/site-mode",
                   json={"box_anim_sections": {"foobar": "zoom"}}, timeout=20)
    assert r.status_code == 400, r.text
    detail = (r.json().get("detail") or "")
    assert "Unknown section" in detail and "foobar" in detail, detail


def test_sections_reject_unknown_animation(client):
    r = client.put(f"{API}/apps/{APP_ID}/site-mode",
                   json={"box_anim_sections": {"hero": "wobble-xyz"}}, timeout=20)
    assert r.status_code == 400, r.text
    detail = (r.json().get("detail") or "").lower()
    assert "unknown" in detail and "box" in detail, detail


# --- Public payload exposes all three ---
def test_public_site_exposes_new_fields(client):
    client.put(f"{API}/apps/{APP_ID}/site-mode", json={
        "box_speed": 1.5, "box_stagger": 40,
        "box_anim_sections": {"hero": "zoom", "services": "blinds"}
    }, timeout=20)
    sm = client.get(f"{API}/apps/{APP_ID}/site-mode", timeout=20).json()
    token = sm.get("preview_token")
    assert token, "no preview_token"
    pub = requests.get(f"{API}/public/site/{token}", timeout=20)
    assert pub.status_code == 200, pub.text[:200]
    j = pub.json()
    app_block = j.get("app") or j.get("site") or j
    smode = (app_block.get("site_mode") if isinstance(app_block, dict) else None) \
            or j.get("site_mode") or {}
    assert abs(float(smode.get("box_speed", 0)) - 1.5) < 1e-6, smode
    assert int(smode.get("box_stagger", 0)) == 40, smode
    secs = smode.get("box_anim_sections") or {}
    assert secs.get("hero") == "zoom" and secs.get("services") == "blinds", secs


# --- Permission check: unauthenticated / non-member ---
def test_unauth_cannot_write_site_mode():
    """Anonymous session should be blocked from writes on the new fields."""
    anon = requests.Session()
    r = anon.put(f"{API}/apps/{APP_ID}/site-mode",
                 json={"box_speed": 1.5}, timeout=20)
    assert r.status_code in (401, 403, 404), \
        f"expected 401/403/404 for anon PUT, got {r.status_code}: {r.text[:200]}"
