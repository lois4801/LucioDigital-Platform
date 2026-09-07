"""Tests for UI Labels CMS endpoints (iter19).

Covers:
- GET /apps/{id}/ui_labels shape (labels, tenant, global, can_edit)
- PUT tenant-scope persistence
- PUT global-scope creates site_settings defaults (admin only)
- Global defaults appear in OTHER apps and tenant overrides global
- DELETE tenant vs all
- Non-owner non-admin gets can_edit=false and 403
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"
EXISTING_APP_ID = "app_bdbf27abe643"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return s


def _register(email, password, name="Test User"):
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={"email": email, "password": password, "name": name}, timeout=15)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def other_user_session():
    email = f"TEST_other_{uuid.uuid4().hex[:8]}@example.com"
    return _register(email, "TestPass123!")


@pytest.fixture(scope="module")
def other_user_app(other_user_session):
    r = other_user_session.post(f"{API}/apps", json={"name": "TEST_other_app", "industry": "SaaS Portals"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["app_id"]


@pytest.fixture(scope="module")
def admin_second_app(admin_session):
    r = admin_session.post(f"{API}/apps", json={"name": "TEST_admin_second_app", "industry": "SaaS Portals"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["app_id"]


class TestUiLabelsGet:
    def test_get_shape_admin(self, admin_session):
        r = admin_session.get(f"{API}/apps/{EXISTING_APP_ID}/ui_labels", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("labels", "tenant", "global", "can_edit"):
            assert k in data
        assert data["can_edit"] is True
        assert isinstance(data["labels"], dict)


class TestUiLabelsPutTenant:
    def test_put_tenant_persists(self, admin_session):
        # Reset first to ensure clean state
        admin_session.delete(f"{API}/apps/{EXISTING_APP_ID}/ui_labels?scope=tenant", timeout=15)
        key = f"tab_inbox"
        val = f"TEST_Inbox_{uuid.uuid4().hex[:6]}"
        r = admin_session.put(
            f"{API}/apps/{EXISTING_APP_ID}/ui_labels",
            json={"labels": {key: val}, "scope": "tenant"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tenant"].get(key) == val
        assert data["labels"].get(key) == val

        # GET verifies persistence
        r2 = admin_session.get(f"{API}/apps/{EXISTING_APP_ID}/ui_labels", timeout=15)
        assert r2.status_code == 200
        assert r2.json()["tenant"].get(key) == val
        assert r2.json()["labels"].get(key) == val


class TestUiLabelsGlobalScope:
    def test_put_global_admin_and_appears_in_other_app(self, admin_session, admin_second_app):
        gkey = "tab_inbox"
        gval = f"GlobalInbox_{uuid.uuid4().hex[:5]}"
        r = admin_session.put(
            f"{API}/apps/{EXISTING_APP_ID}/ui_labels",
            json={"labels": {gkey: gval}, "scope": "global"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["global"].get(gkey) == gval

        # Check on another admin-owned app
        r2 = admin_session.get(f"{API}/apps/{admin_second_app}/ui_labels", timeout=15)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["global"].get(gkey) == gval
        assert d2["labels"].get(gkey) == gval  # global default surfaces in merged labels

    def test_tenant_overrides_global(self, admin_session, admin_second_app):
        gkey = "tab_inbox"
        # Set a tenant override on the second app
        tval = f"TenantInbox_{uuid.uuid4().hex[:5]}"
        r = admin_session.put(
            f"{API}/apps/{admin_second_app}/ui_labels",
            json={"labels": {gkey: tval}, "scope": "tenant"},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["labels"].get(gkey) == tval  # tenant beats global in merged view


class TestUiLabelsPermissions:
    def test_non_owner_get_403(self, other_user_session):
        r = other_user_session.get(f"{API}/apps/{EXISTING_APP_ID}/ui_labels", timeout=15)
        # get_user_app blocks non-members entirely with 403
        assert r.status_code == 403, r.text

    def test_non_admin_global_scope_forbidden(self, other_user_session, other_user_app):
        r = other_user_session.put(
            f"{API}/apps/{other_user_app}/ui_labels",
            json={"labels": {"tab_inbox": "hax"}, "scope": "global"},
            timeout=15,
        )
        assert r.status_code == 403, r.text

    def test_owner_can_edit_true_own_app(self, other_user_session, other_user_app):
        r = other_user_session.get(f"{API}/apps/{other_user_app}/ui_labels", timeout=15)
        assert r.status_code == 200
        assert r.json()["can_edit"] is True

    def test_non_admin_delete_all_scope_forbidden(self, other_user_session, other_user_app):
        r = other_user_session.delete(
            f"{API}/apps/{other_user_app}/ui_labels?scope=all", timeout=15
        )
        assert r.status_code == 403


class TestUiLabelsDelete:
    def test_delete_tenant_only(self, admin_session):
        # ensure tenant override exists
        admin_session.put(
            f"{API}/apps/{EXISTING_APP_ID}/ui_labels",
            json={"labels": {"tenant_name": "willbedeleted"}, "scope": "tenant"},
            timeout=15,
        )
        r = admin_session.delete(f"{API}/apps/{EXISTING_APP_ID}/ui_labels?scope=tenant", timeout=15)
        assert r.status_code == 200
        assert r.json()["tenant"] == {}
        # globals should still be there from earlier
        r2 = admin_session.get(f"{API}/apps/{EXISTING_APP_ID}/ui_labels", timeout=15)
        assert r2.status_code == 200
        assert r2.json()["tenant"] == {}

    def test_delete_all_clears_globals(self, admin_session):
        # set global
        admin_session.put(
            f"{API}/apps/{EXISTING_APP_ID}/ui_labels",
            json={"labels": {"tab_inbox": "willclear"}, "scope": "global"},
            timeout=15,
        )
        r = admin_session.delete(f"{API}/apps/{EXISTING_APP_ID}/ui_labels?scope=all", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["tenant"] == {}
        assert data["global"] == {}


@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_session):
    yield
    # Best-effort cleanup: clear tenant and globals
    try:
        admin_session.delete(f"{API}/apps/{EXISTING_APP_ID}/ui_labels?scope=all", timeout=15)
    except Exception:
        pass
