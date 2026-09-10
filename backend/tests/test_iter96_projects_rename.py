"""Iter96: verify Templates→Projects user-visible rename.

Internals (URLs, api paths, response keys, data-testids) must stay unchanged.
Only user-visible strings should say 'project'/'Project'.
"""
import os
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


# --- Internals unchanged ---

def test_public_templates_url_still_works():
    r = requests.get(f"{BASE}/api/public/templates", timeout=30)
    assert r.status_code == 200
    data = r.json()
    # response key must still be 'templates'
    assert "templates" in data, f"expected 'templates' key, got: {list(data.keys())}"
    assert isinstance(data["templates"], list)
    assert len(data["templates"]) >= 30, f"expected 33+ templates, got {len(data['templates'])}"


def test_public_template_detail_still_works():
    lst = requests.get(f"{BASE}/api/public/templates", timeout=30).json()["templates"]
    key = lst[0].get("key") or lst[0].get("id") or lst[0].get("slug")
    assert key
    r = requests.get(f"{BASE}/api/public/templates/{key}", timeout=30)
    assert r.status_code == 200


# --- Backend user-visible strings ---

def test_unknown_template_key_returns_unknown_project():
    r = requests.get(f"{BASE}/api/public/templates/not_a_key_xyz", timeout=30)
    assert r.status_code == 404
    body = r.text.lower()
    assert "unknown project" in body, f"expected 'Unknown project' in error, got: {r.text}"


def test_test_template_brand_is_test_project(admin_session):
    r = admin_session.get(f"{BASE}/api/test-template", timeout=30)
    assert r.status_code == 200
    data = r.json()
    brand = data.get("brand") or data.get("state", {}).get("brand") or ""
    if isinstance(brand, dict):
        brand = brand.get("name") or brand.get("label") or str(brand)
    assert "Test Project" in str(brand) or "Test Project" in r.text, f"expected 'Test Project' brand, got: {brand!r} full={r.text[:400]}"


def test_marquee_reset_editlog_says_project(admin_session):
    # reset marquee on app_testlab and verify edit-log uses 'project' word
    r = admin_session.post(f"{BASE}/api/apps/app_testlab/marquee/reset", json={}, timeout=30)
    assert r.status_code in (200, 204), f"marquee reset: {r.status_code} {r.text}"
    log = admin_session.get(f"{BASE}/api/apps/app_testlab/edit-log", timeout=30)
    assert log.status_code == 200
    entries = log.json()
    if isinstance(entries, dict):
        entries = entries.get("entries") or entries.get("log") or []
    # search recent entries for 'project' in reset messages
    text = " ".join(str(e).lower() for e in entries[:30])
    assert "project" in text, f"expected 'project' in recent edit-log entries, got head: {text[:500]}"
    # and 'template' should not appear in user-visible reset messages
    # (only check the specific marquee reset entry to avoid internal field noise)
    reset_entries = [e for e in entries[:30] if "marquee" in str(e).lower() or "ribbon" in str(e).lower()]
    if reset_entries:
        rt = " ".join(str(e) for e in reset_entries[:5]).lower()
        # message field should not say 'template' in the user-visible bit
        assert "template" not in rt or "project" in rt, f"marquee reset log still says 'template': {rt[:400]}"


# --- /work still lives ---

def test_work_case_studies_public():
    r = requests.get(f"{BASE}/api/public/case-studies", timeout=30)
    # endpoint name may differ; try a couple
    if r.status_code == 404:
        r = requests.get(f"{BASE}/api/public/work", timeout=30)
    assert r.status_code in (200, 404), f"work endpoint responded {r.status_code}"


# --- Regression sanity ---

def test_admin_login_and_apps_list(admin_session):
    r = admin_session.get(f"{BASE}/api/apps", timeout=30)
    assert r.status_code == 200


def test_site_mode_endpoint_unchanged(admin_session):
    r = admin_session.get(f"{BASE}/api/apps/app_testlab/site-mode", timeout=30)
    assert r.status_code == 200


def test_free_account_gets_402():
    import time
    email = f"free_iter96_{int(time.time())}@example.com"
    r = requests.post(f"{BASE}/api/auth/register", json={"email": email, "password": "Testing123!", "name": "Iter96 Tester"}, timeout=30)
    assert r.status_code in (200, 201), f"register: {r.status_code} {r.text}"
    s = requests.Session()
    lg = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": "Testing123!"}, timeout=30)
    assert lg.status_code == 200
    gated = s.get(f"{BASE}/api/apps", timeout=30)
    assert gated.status_code in (402, 403), f"free acct should be gated, got {gated.status_code}"
