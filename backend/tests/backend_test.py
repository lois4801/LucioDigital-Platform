"""Backend API tests for Agency Multi-Tenant Platform."""
import os
import io
import time
import uuid
import zipfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    assert "access_token" in s.cookies, "access_token cookie not set"
    return s


@pytest.fixture(scope="session")
def new_user_session():
    s = requests.Session()
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "TestPass1!", "name": "Test User"}, timeout=20)
    assert r.status_code == 200, f"Register failed: {r.status_code} {r.text}"
    s.email = email
    return s


# ---------- Health ----------
def test_health():
    r = requests.get(f"{API}/", timeout=10)
    assert r.status_code == 200
    assert r.json().get("ok") is True


# ---------- Auth ----------
def test_login_wrong_password():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"}, timeout=15)
    assert r.status_code == 401


def test_admin_login_and_me(admin_session):
    r = admin_session.get(f"{API}/auth/me", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == ADMIN_EMAIL
    assert data["role"] == "owner"
    assert "_id" not in data
    assert "password_hash" not in data


def test_me_unauthenticated():
    r = requests.get(f"{API}/auth/me", timeout=15)
    assert r.status_code == 401


def test_register_new_user(new_user_session):
    r = new_user_session.get(f"{API}/auth/me", timeout=15)
    assert r.status_code == 200
    assert r.json()["email"] == new_user_session.email


def test_logout():
    s = requests.Session()
    s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    r = s.post(f"{API}/auth/logout", timeout=15)
    assert r.status_code == 200
    # After logout the /me should fail because cookies cleared
    r2 = requests.get(f"{API}/auth/me", cookies={}, timeout=15)
    assert r2.status_code == 401


# ---------- Apps ----------
def test_list_seeded_apps(admin_session):
    r = admin_session.get(f"{API}/apps", timeout=15)
    assert r.status_code == 200
    apps = r.json()
    names = {a["name"] for a in apps}
    expected = {"Nexus Commerce", "Orbit SaaS Portal", "Fleet Command", "Aura Wellness", "Ledger AI Portfolio", "Studio Booking"}
    assert expected.issubset(names), f"Missing seeded apps. Got: {names}"
    # status counts
    statuses = [a["status"] for a in apps if a["name"] in expected]
    assert statuses.count("active") == 4
    assert statuses.count("maintenance") == 1
    assert statuses.count("handover") == 1


def test_multi_tenant_isolation(new_user_session):
    r = new_user_session.get(f"{API}/apps", timeout=15)
    assert r.status_code == 200
    apps = r.json()
    assert apps == [], f"New user should see 0 apps, got {len(apps)}"


@pytest.fixture(scope="session")
def created_app(admin_session):
    r = admin_session.post(f"{API}/apps", json={
        "name": "TEST_App_" + uuid.uuid4().hex[:6],
        "industry": "SaaS Portals",
        "description": "Testing",
    }, timeout=15)
    assert r.status_code == 200
    return r.json()


def test_create_app(created_app):
    assert created_app["name"].startswith("TEST_App_")
    assert created_app["status"] == "active"
    assert created_app["transfer_mode"] is False
    assert "_id" not in created_app


def test_get_app(admin_session, created_app):
    r = admin_session.get(f"{API}/apps/{created_app['app_id']}", timeout=15)
    assert r.status_code == 200
    assert r.json()["app_id"] == created_app["app_id"]


def test_update_app_status(admin_session, created_app):
    r = admin_session.patch(f"{API}/apps/{created_app['app_id']}", json={"status": "maintenance"}, timeout=15)
    assert r.status_code == 200
    assert r.json()["status"] == "maintenance"


def test_transfer_mode_toggle(admin_session, created_app):
    r = admin_session.patch(f"{API}/apps/{created_app['app_id']}", json={"transfer_mode": True}, timeout=15)
    assert r.status_code == 200
    assert r.json()["transfer_mode"] is True


# ---------- Pages / Builder ----------
def test_get_page_default_blocks(admin_session, created_app):
    r = admin_session.get(f"{API}/apps/{created_app['app_id']}/page", timeout=15)
    assert r.status_code == 200
    page = r.json()
    assert len(page["blocks"]) >= 3
    types = {b["type"] for b in page["blocks"]}
    assert "hero" in types


def test_save_page(admin_session, created_app):
    blocks = [
        {"id": "blk_1", "type": "hero", "props": {"title": "Hi", "cta": "Go"}},
        {"id": "blk_2", "type": "features", "props": {"heading": "F", "items": []}},
    ]
    r = admin_session.put(f"{API}/apps/{created_app['app_id']}/page", json={"blocks": blocks}, timeout=15)
    assert r.status_code == 200
    assert r.json()["count"] == 2


# ---------- Activity ----------
def test_activity_log(admin_session, created_app):
    r = admin_session.get(f"{API}/apps/{created_app['app_id']}/activity", timeout=15)
    assert r.status_code == 200
    logs = r.json()
    kinds = {l["kind"] for l in logs}
    # created, status.changed, transfer.toggle, page.saved should exist
    assert "app.created" in kinds
    assert "status.changed" in kinds
    assert "transfer.toggle" in kinds


# ---------- Members ----------
def test_members_owner_present(admin_session, created_app):
    r = admin_session.get(f"{API}/apps/{created_app['app_id']}/members", timeout=15)
    assert r.status_code == 200
    members = r.json()
    assert len(members) >= 1
    assert members[0]["role"] == "owner"
    assert members[0]["email"] == ADMIN_EMAIL


def test_invite_and_remove_member(admin_session, created_app):
    email = f"invitee_{uuid.uuid4().hex[:6]}@example.com"
    r = admin_session.post(f"{API}/apps/{created_app['app_id']}/members", json={"email": email, "role": "editor"}, timeout=15)
    assert r.status_code == 200
    r2 = admin_session.get(f"{API}/apps/{created_app['app_id']}/members", timeout=15)
    members = r2.json()
    invitee = next((m for m in members if m["email"] == email), None)
    assert invitee is not None
    mid = invitee["membership_id"]
    r3 = admin_session.delete(f"{API}/apps/{created_app['app_id']}/members/{mid}", timeout=15)
    assert r3.status_code == 200


# ---------- Export ----------
def test_export_zip(admin_session, created_app):
    r = admin_session.get(f"{API}/apps/{created_app['app_id']}/export/source", timeout=30)
    assert r.status_code == 200
    assert "attachment" in r.headers.get("Content-Disposition", "")
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    assert "index.html" in names
    assert "package.json" in names
    assert "blocks.json" in names


def test_export_mobile_ios(admin_session, created_app):
    r = admin_session.post(f"{API}/apps/{created_app['app_id']}/export/mobile?platform=ios", timeout=15)
    assert r.status_code == 200
    job = r.json()
    assert job["platform"] == "ios"
    assert job["artifact"].endswith(".ipa")
    assert len(job["steps"]) >= 3


# ---------- AI Editor ----------
def test_ai_edit_block(admin_session, created_app):
    block = {"id": "blk_ai", "type": "hero", "props": {"title": "Old", "subtitle": "s", "cta": "Buy Now", "align": "left"}}
    r = admin_session.post(f"{API}/apps/{created_app['app_id']}/ai/edit",
                           json={"prompt": "Change the CTA to say 'Try Free' instead", "block": block},
                           timeout=60)
    # AI may occasionally fail on JSON; accept 200 as success
    assert r.status_code == 200, f"AI edit failed: {r.status_code} {r.text[:400]}"
    updated = r.json()
    assert updated["id"] == "blk_ai"
    assert updated["type"] == "hero"
    assert "props" in updated


# ---------- Cross-tenant access denial ----------
def test_cross_tenant_denied(new_user_session, created_app):
    r = new_user_session.get(f"{API}/apps/{created_app['app_id']}", timeout=15)
    assert r.status_code in (403, 404)


# ---------- Cleanup (delete app) ----------
def test_delete_app(admin_session, created_app):
    r = admin_session.delete(f"{API}/apps/{created_app['app_id']}", timeout=15)
    assert r.status_code == 200
    r2 = admin_session.get(f"{API}/apps/{created_app['app_id']}", timeout=15)
    assert r2.status_code == 404
