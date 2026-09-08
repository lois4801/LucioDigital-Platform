"""Iter-26 backend tests: Per-tenant Data & Storage destinations.

Covers:
 - GET default (platform) destination
 - Test connection returns success for platform
 - PostgreSQL save with valid URI succeeds; GET response never contains the URI/secret
 - Supabase rejects non-pooler URIs (400)
 - Supabase accepts pooler.supabase.com:6543 URI
 - Reset (DELETE) returns to platform workspace
 - Non-owner tenant member cannot GET/PUT/POST-test/DELETE (403 or 404)
"""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
APP_ID = "app_bdbf27abe643"
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN)
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text}")
    return s


@pytest.fixture(scope="module")
def outsider():
    """A separate user with no membership on APP_ID."""
    email = f"TEST_iter26_outsider_{int(time.time())}@example.com"
    pw = "TestOutsider2026!"
    for path in ("/auth/register", "/auth/signup"):
        r = requests.post(f"{API}{path}", json={"email": email, "password": pw, "name": "TEST Iter26"})
        if r.status_code in (200, 201):
            break
    else:
        pytest.skip(f"cannot create outsider user: {r.status_code} {r.text}")
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"outsider login failed: {r.status_code}")
    return s


@pytest.fixture(autouse=True)
def _reset_after(admin):
    """Ensure destination is reset to platform after every test."""
    yield
    try:
        admin.delete(f"{API}/apps/{APP_ID}/data-destination")
    except Exception:
        pass


class TestDefaultAndPlatform:
    def test_get_default_is_platform(self, admin):
        r = admin.get(f"{API}/apps/{APP_ID}/data-destination")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["provider"] == "platform"
        assert data["status"] == "active"
        assert data["can_test"] is True
        assert data["missing_fields"] == []
        assert data["secret_fields"] == []

    def test_platform_test_returns_success(self, admin):
        r = admin.post(f"{API}/apps/{APP_ID}/data-destination/test")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert "OmniStack" in body.get("message", "")


class TestPostgresSaveAndSecrecy:
    def test_save_postgres_and_secret_hidden(self, admin):
        fake_uri = "postgresql://TESTUSER:TESTSECRET_iter26@db.example.com:5432/testdb"
        r = admin.put(
            f"{API}/apps/{APP_ID}/data-destination",
            json={
                "provider": "postgres",
                "label": "TEST_iter26 pg",
                "configuration": {},
                "secrets": {"connection_uri": fake_uri},
            },
        )
        assert r.status_code == 200, r.text
        saved = r.json()
        assert saved["provider"] == "postgres"
        assert saved["status"] == "ready_to_verify"
        assert "connection_uri" in saved["secret_fields"]
        # Secret must not leak in save response
        blob = r.text
        assert "TESTSECRET_iter26" not in blob
        assert fake_uri not in blob

        # GET must also hide the secret and URI
        r2 = admin.get(f"{API}/apps/{APP_ID}/data-destination")
        assert r2.status_code == 200
        body = r2.text
        assert "TESTSECRET_iter26" not in body
        assert fake_uri not in body
        d = r2.json()
        assert d["provider"] == "postgres"
        assert "connection_uri" in d["secret_fields"]
        assert d.get("configuration", {}).get("connection_uri") is None

    def test_reset_returns_to_platform(self, admin):
        fake_uri = "postgresql://u:p@db.example.com:5432/x"
        admin.put(
            f"{API}/apps/{APP_ID}/data-destination",
            json={"provider": "postgres", "secrets": {"connection_uri": fake_uri}},
        )
        r = admin.delete(f"{API}/apps/{APP_ID}/data-destination")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["provider"] == "platform"
        assert d["status"] == "active"

    def test_postgres_invalid_uri_rejected(self, admin):
        r = admin.put(
            f"{API}/apps/{APP_ID}/data-destination",
            json={"provider": "postgres", "secrets": {"connection_uri": "mysql://x@y/z"}},
        )
        assert r.status_code == 400


class TestSupabaseValidation:
    def test_direct_uri_rejected(self, admin):
        # Direct URI (not the pooler) must be rejected
        r = admin.put(
            f"{API}/apps/{APP_ID}/data-destination",
            json={
                "provider": "supabase",
                "secrets": {"connection_uri": "postgresql://postgres:pw@db.abcd.supabase.co:5432/postgres"},
            },
        )
        assert r.status_code == 400, r.text
        assert "pooler" in r.json().get("detail", "").lower()

    def test_wrong_port_rejected(self, admin):
        r = admin.put(
            f"{API}/apps/{APP_ID}/data-destination",
            json={
                "provider": "supabase",
                "secrets": {"connection_uri": "postgresql://postgres:pw@aws-0.pooler.supabase.com:5432/postgres"},
            },
        )
        assert r.status_code == 400

    def test_pooler_uri_accepted(self, admin):
        good = "postgresql://postgres.abcd:TESTSUPA_iter26@aws-0.pooler.supabase.com:6543/postgres"
        r = admin.put(
            f"{API}/apps/{APP_ID}/data-destination",
            json={"provider": "supabase", "secrets": {"connection_uri": good}},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["provider"] == "supabase"
        assert d["status"] == "ready_to_verify"
        # No leak
        assert "TESTSUPA_iter26" not in r.text
        r2 = admin.get(f"{API}/apps/{APP_ID}/data-destination")
        assert "TESTSUPA_iter26" not in r2.text


class TestPermissions:
    def test_outsider_cannot_get(self, outsider):
        r = outsider.get(f"{API}/apps/{APP_ID}/data-destination")
        assert r.status_code in (403, 404), r.text

    def test_outsider_cannot_save(self, outsider):
        r = outsider.put(
            f"{API}/apps/{APP_ID}/data-destination",
            json={"provider": "platform"},
        )
        assert r.status_code in (403, 404)

    def test_outsider_cannot_test(self, outsider):
        r = outsider.post(f"{API}/apps/{APP_ID}/data-destination/test")
        assert r.status_code in (403, 404)

    def test_outsider_cannot_reset(self, outsider):
        r = outsider.delete(f"{API}/apps/{APP_ID}/data-destination")
        assert r.status_code in (403, 404)
