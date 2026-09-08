"""Iter 47 smoke regression — dashboard/inbox/settings/export endpoints for owner."""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
OWNER_EMAIL = "jaybernabe@luciodigital.com"
OWNER_PASS = "Lucio2026!"
APP_ID = "app_6663b5de0007"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": OWNER_EMAIL, "password": OWNER_PASS}, timeout=60)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


def test_get_apps(session):
    r = session.get(f"{BASE_URL}/api/apps", timeout=30)
    assert r.status_code == 200
    apps = r.json()
    assert isinstance(apps, list) and len(apps) > 0
    assert any(a.get("app_id") == APP_ID for a in apps)


def test_get_inbox(session):
    r = session.get(f"{BASE_URL}/api/apps/{APP_ID}/inbox", timeout=30)
    assert r.status_code == 200
    body = r.json()
    # inbox returns dict with messages list
    assert isinstance(body, (dict, list))


def test_get_inbox_insights(session):
    r = session.get(f"{BASE_URL}/api/apps/{APP_ID}/inbox/insights?days=90", timeout=30)
    assert r.status_code == 200
    data = r.json()
    for k in ("days", "leads", "hot", "avg_score", "pages", "forms", "sources", "best"):
        assert k in data, f"missing key {k}"


def test_get_settings_email(session):
    r = session.get(f"{BASE_URL}/api/settings/email", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "configured" in data


def test_notifications(session):
    r = session.get(f"{BASE_URL}/api/notifications", timeout=30)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_export_start_returns_job_id(session):
    """Kick off export just to verify contract, don't wait for completion."""
    r = session.post(f"{BASE_URL}/api/apps/{APP_ID}/export/start",
                     json={"kind": "website"}, timeout=30)
    assert r.status_code in (200, 202), f"got {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert "job_id" in data or "id" in data, f"no job id: {data}"
