"""Iteration 72 — Public Motion Index + Template Isolation Preview.
Tests: public reel (44 rows, active/reserved counts, industries), preview 200/404,
public pick create/validation, admin-only picks endpoint, and pick-apply persistence.
"""
import os
import requests
import pytest

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0]).rstrip("/")
API = f"{BASE}/api"
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
APP_ID = "app_testlab"


@pytest.fixture(scope="module")
def anon():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return s


# --- Public motion reel (no auth) ---
def test_motion_reel_public_no_auth(anon):
    r = anon.get(f"{API}/public/motion-reel")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] >= 44, f"Expected >=44 rows, got {d['total']}"
    assert d["active"] + d["reserved"] == d["total"]
    # Every row has required fields
    for row in d["heroes"]:
        assert "hero" in row and "industry" in row and "status" in row
        assert row["status"] in ("active", "reserved")
        assert "tenant_count" in row
    # Industries list non-empty
    assert len(d["industries"]) >= 20


def test_motion_reel_active_counts_match(anon):
    d = anon.get(f"{API}/public/motion-reel").json()
    a = sum(1 for r in d["heroes"] if r["status"] == "active")
    res = sum(1 for r in d["heroes"] if r["status"] == "reserved")
    assert a == d["active"]
    assert res == d["reserved"]


# --- Preview per template ---
def test_motion_preview_valid_key(anon):
    d = anon.get(f"{API}/public/motion-reel").json()
    keyed = [r for r in d["heroes"] if r.get("template_key")]
    assert keyed, "Expected at least one row with template_key"
    key = keyed[0]["template_key"]
    r = anon.get(f"{API}/public/motion-preview/{key}")
    assert r.status_code == 200, r.text
    pv = r.json()
    assert pv["template_key"] == key
    assert pv["profile"]["hero"]
    assert pv["status"] in ("active", "reserved")


def test_motion_preview_unknown_key_404(anon):
    r = anon.get(f"{API}/public/motion-preview/definitely-not-a-real-template")
    assert r.status_code == 404


# --- Public pick create + validation ---
def test_public_pick_create_and_validation(anon):
    d = anon.get(f"{API}/public/motion-reel").json()
    hero = d["heroes"][0]["hero"]
    # Empty email → 400
    r = anon.post(f"{API}/public/motion-picks", json={"hero": hero, "email": "", "name": "t"})
    assert r.status_code == 400
    # Unknown hero → 400
    r = anon.post(f"{API}/public/motion-picks", json={"hero": "not-a-hero", "email": "x@y.com"})
    assert r.status_code == 400
    # Success
    r = anon.post(f"{API}/public/motion-picks", json={
        "hero": hero, "email": "TEST_iter72@example.com",
        "name": "TEST_iter72", "speed": 1.25, "intensity": 0.9
    })
    assert r.status_code == 200
    assert r.json().get("ok") is True


# --- Admin-only picks listing ---
def test_motion_picks_requires_auth(anon):
    r = anon.get(f"{API}/motion-picks")
    assert r.status_code in (401, 403)


def test_motion_picks_admin_ok(admin):
    r = admin.get(f"{API}/motion-picks")
    assert r.status_code == 200
    body = r.json()
    assert "picks" in body and "total" in body


# --- Site-mode apply persists pick's speed/intensity ---
def test_site_mode_apply_persistence(admin):
    # Save current
    cur = admin.get(f"{API}/apps/{APP_ID}/site-mode").json()
    hero = cur.get("hero") or "aurora-wave"
    # Apply new speed/intensity mimicking pick apply
    r = admin.put(f"{API}/apps/{APP_ID}/site-mode", json={
        "hero": hero, "style": "editorial", "motion_speed": 1.08, "motion_intensity": 1.0,
    })
    assert r.status_code == 200
    after = admin.get(f"{API}/apps/{APP_ID}/site-mode").json()
    assert abs(float(after["motion_speed"]) - 1.08) < 0.01
    assert abs(float(after["motion_intensity"]) - 1.0) < 0.01
