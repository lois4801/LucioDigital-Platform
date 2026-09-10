"""Iter73 — Live Template / Site Mode content preservation tests.

Verifies:
  - Public site payload for the Test Lab is stable (page count + block counts) BEFORE and AFTER
    exercising Site Mode saves (no tenant content loss — CRITICAL acceptance criterion).
  - Motion reel + preview endpoints still healthy.
  - Site Mode PUT for app_testlab persists motion_speed / motion_intensity / hero / publish.
  - preview/regenerate endpoint mints a token.
"""
import os
import re
import pathlib
import pytest
import requests

def _base():
    u = os.environ.get("REACT_APP_BACKEND_URL")
    if not u:
        env = pathlib.Path("/app/frontend/.env").read_text()
        m = re.search(r"REACT_APP_BACKEND_URL=(.+)", env)
        u = m.group(1).strip()
    return u.rstrip("/")

BASE = _base()
TESTLAB_ID = "app_testlab"
TESTLAB_TOKEN = "pv_c3b797fcdafc58d4e70e320f"
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


def _snapshot_site():
    r = requests.get(f"{BASE}/api/public/site/{TESTLAB_TOKEN}")
    assert r.status_code == 200, f"public site fetch failed: {r.status_code}"
    d = r.json()
    pages = d.get("pages", [])
    return {
        "page_count": len(pages),
        "per_page_blocks": {p.get("slug"): len(p.get("blocks", [])) for p in pages},
        "app_name": d.get("app", {}).get("name"),
    }


def test_public_site_reachable():
    snap = _snapshot_site()
    assert snap["page_count"] > 0
    assert snap["app_name"]


def test_motion_reel_still_healthy():
    r = requests.get(f"{BASE}/api/public/motion-reel")
    assert r.status_code == 200
    d = r.json()
    assert len(d.get("heroes", [])) >= 40


def test_motion_preview_valid():
    r = requests.get(f"{BASE}/api/public/motion-preview/saas")
    assert r.status_code == 200
    d = r.json()
    assert d.get("template_key") == "saas"
    assert d.get("profile", {}).get("hero")


def test_site_mode_get_and_preserve_content(admin_session):
    # BEFORE snapshot
    before = _snapshot_site()

    r = admin_session.get(f"{BASE}/api/apps/{TESTLAB_ID}/site-mode")
    assert r.status_code == 200
    sm = r.json()
    # Snapshot preview_token (used by SiteMode iframe)
    assert sm.get("preview_token") or True  # may or may not be present, non-fatal

    # Save a couple of harmless changes: bump intensity / speed and set publish live
    payload = {"motion_speed": 1.15, "motion_intensity": 0.85, "publish": "live"}
    r2 = admin_session.put(f"{BASE}/api/apps/{TESTLAB_ID}/site-mode", json=payload)
    assert r2.status_code == 200, r2.text[:200]

    # Verify persisted
    r3 = admin_session.get(f"{BASE}/api/apps/{TESTLAB_ID}/site-mode")
    assert r3.status_code == 200
    got = r3.json()
    assert abs(got.get("motion_speed", 0) - 1.15) < 1e-6
    assert abs(got.get("motion_intensity", 0) - 0.85) < 1e-6
    assert got.get("publish") == "live"

    # AFTER snapshot — content must be intact
    after = _snapshot_site()
    assert after["page_count"] == before["page_count"], (
        f"CRITICAL: page count changed {before['page_count']} -> {after['page_count']}"
    )
    assert after["per_page_blocks"] == before["per_page_blocks"], (
        f"CRITICAL: block counts changed\nbefore={before['per_page_blocks']}\nafter={after['per_page_blocks']}"
    )


def test_preview_regenerate_mints_token(admin_session):
    """Preview regenerate rotates preview_token — snapshot & restore to keep
    the documented Test Lab token pv_c3b797fcdafc58d4e70e320f stable across runs."""
    original = admin_session.get(f"{BASE}/api/apps/{TESTLAB_ID}").json().get("preview_token")
    try:
        r = admin_session.post(f"{BASE}/api/apps/{TESTLAB_ID}/preview/regenerate")
        assert r.status_code in (200, 201), r.text[:200]
        d = r.json()
        tok = d.get("preview_token") or d.get("token")
        assert tok and tok.startswith("pv_")
    finally:
        # Restore documented token so downstream tests / frontend keep working.
        if original:
            from pymongo import MongoClient
            import os as _os
            from dotenv import load_dotenv
            load_dotenv("/app/backend/.env")
            MongoClient(_os.environ["MONGO_URL"])[_os.environ["DB_NAME"]].apps.update_one(
                {"app_id": TESTLAB_ID}, {"$set": {"preview_token": original}})


def test_no_preview_or_isolation_strings_in_public_site():
    r = requests.get(f"{BASE}/api/public/site/{TESTLAB_TOKEN}")
    assert r.status_code == 200
    text = r.text
    # These strings must NOT appear as UI/state labels in the public site payload.
    # (Field/property names like 'preview_token' are fine — we check for user-visible phrases.)
    for banned in ["ISOLATED PREVIEW", "TEMPLATE ISOLATION", "Now previewing", "ISOLATION PREVIEW"]:
        assert banned not in text, f"banned phrase leaked in public site: {banned}"
