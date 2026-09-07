"""Tests for UI Labels *styles* additions (iter20).

Covers the new per-tenant/global font+color styles round-trip and permissions.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
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
def other_session():
    email = f"TEST_iter20_other_{uuid.uuid4().hex[:8]}@example.com"
    return _register(email, "TestPass123!")


@pytest.fixture(scope="module")
def admin_second_app(admin_session):
    r = admin_session.post(f"{API}/apps", json={"name": "TEST_iter20_secondapp", "industry": "SaaS Portals"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["app_id"]


class TestStylesShape:
    def test_get_returns_styles_keys(self, admin_session):
        r = admin_session.get(f"{API}/apps/{EXISTING_APP_ID}/ui_labels", timeout=15)
        assert r.status_code == 200
        data = r.json()
        for k in ("styles", "tenant_styles", "global_styles"):
            assert k in data, f"missing {k} in response"


class TestStylesTenantRoundTrip:
    def test_put_styles_only_no_labels(self, admin_session):
        admin_session.delete(f"{API}/apps/{EXISTING_APP_ID}/ui_labels?scope=tenant", timeout=15)
        key = "analytics_heading"
        style = {"font": "'Playfair Display', serif", "color": "#ff8800"}
        r = admin_session.put(
            f"{API}/apps/{EXISTING_APP_ID}/ui_labels",
            json={"styles": {key: style}, "scope": "tenant"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tenant_styles"].get(key) == {"font": style["font"], "color": style["color"]}
        assert data["styles"].get(key) == {"font": style["font"], "color": style["color"]}

        # verify persistence via GET
        r2 = admin_session.get(f"{API}/apps/{EXISTING_APP_ID}/ui_labels", timeout=15)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["tenant_styles"].get(key) == {"font": style["font"], "color": style["color"]}

    def test_put_labels_and_styles_together(self, admin_session):
        key = "tab_inbox"
        label = f"TEST_Inbox_{uuid.uuid4().hex[:6]}"
        style = {"font": "'Inter', sans-serif", "color": "#00ccff"}
        r = admin_session.put(
            f"{API}/apps/{EXISTING_APP_ID}/ui_labels",
            json={"labels": {key: label}, "styles": {key: style}, "scope": "tenant"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["tenant"].get(key) == label
        assert d["tenant_styles"].get(key)["color"] == "#00ccff"

    def test_put_empty_returns_400(self, admin_session):
        r = admin_session.put(
            f"{API}/apps/{EXISTING_APP_ID}/ui_labels",
            json={"scope": "tenant"},
            timeout=15,
        )
        assert r.status_code == 400, r.text

    def test_key_dot_sanitized(self, admin_session):
        # Key 'a.b' must be sanitized to 'a_b' so it becomes a top-level flat key
        r = admin_session.put(
            f"{API}/apps/{EXISTING_APP_ID}/ui_labels",
            json={"labels": {"a.b": "flat_val"}, "scope": "tenant"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["tenant"].get("a_b") == "flat_val"
        assert "a.b" not in d["tenant"]


class TestStylesGlobalScope:
    def test_global_styles_surface_on_other_app(self, admin_session, admin_second_app):
        gkey = "analytics_heading"
        gstyle = {"font": "'Sora', sans-serif", "color": "#22aaff"}
        r = admin_session.put(
            f"{API}/apps/{EXISTING_APP_ID}/ui_labels",
            json={"styles": {gkey: gstyle}, "scope": "global"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["global_styles"].get(gkey)["color"] == "#22aaff"

        r2 = admin_session.get(f"{API}/apps/{admin_second_app}/ui_labels", timeout=15)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["global_styles"].get(gkey)["color"] == "#22aaff"
        # merged styles field surfaces the global
        assert d2["styles"].get(gkey)["color"] == "#22aaff"

    def test_tenant_style_overrides_global(self, admin_session, admin_second_app):
        gkey = "analytics_heading"
        tstyle = {"font": "'DM Sans', sans-serif", "color": "#111111"}
        r = admin_session.put(
            f"{API}/apps/{admin_second_app}/ui_labels",
            json={"styles": {gkey: tstyle}, "scope": "tenant"},
            timeout=15,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["styles"].get(gkey)["color"] == "#111111"  # tenant wins


class TestStylesPermissions:
    def test_non_owner_put_styles_forbidden(self, other_session):
        r = other_session.put(
            f"{API}/apps/{EXISTING_APP_ID}/ui_labels",
            json={"styles": {"tab_inbox": {"font": "hax", "color": "#000"}}, "scope": "tenant"},
            timeout=15,
        )
        assert r.status_code == 403, r.text

    def test_non_admin_global_styles_forbidden(self, other_session):
        # Register their own app
        rc = other_session.post(f"{API}/apps", json={"name": "TEST_iter20_own", "industry": "SaaS Portals"}, timeout=15)
        assert rc.status_code == 200
        aid = rc.json()["app_id"]
        r = other_session.put(
            f"{API}/apps/{aid}/ui_labels",
            json={"styles": {"x": {"font": "y", "color": "#fff"}}, "scope": "global"},
            timeout=15,
        )
        assert r.status_code == 403, r.text


class TestStylesDelete:
    def test_delete_tenant_clears_both_labels_and_styles(self, admin_session):
        # seed both
        admin_session.put(
            f"{API}/apps/{EXISTING_APP_ID}/ui_labels",
            json={"labels": {"tenant_name": "willdelete"}, "styles": {"tenant_name": {"font": "'Outfit', sans-serif", "color": "#abcdef"}}, "scope": "tenant"},
            timeout=15,
        )
        r = admin_session.delete(f"{API}/apps/{EXISTING_APP_ID}/ui_labels?scope=tenant", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["tenant"] == {}
        assert d["tenant_styles"] == {}

    def test_delete_all_clears_global_styles(self, admin_session):
        admin_session.put(
            f"{API}/apps/{EXISTING_APP_ID}/ui_labels",
            json={"styles": {"tab_inbox": {"font": "'Roboto', sans-serif", "color": "#123456"}}, "scope": "global"},
            timeout=15,
        )
        r = admin_session.delete(f"{API}/apps/{EXISTING_APP_ID}/ui_labels?scope=all", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["global"] == {}
        assert d["global_styles"] == {}
        assert d["tenant_styles"] == {}


@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_session):
    yield
    try:
        admin_session.delete(f"{API}/apps/{EXISTING_APP_ID}/ui_labels?scope=all", timeout=15)
    except Exception:
        pass
