"""Iter63 regression suite for the circular-import refactor.

Covers:
  * Backend imports (both orders) and /api/health
  * Lock system: get_locks, master toggle, granular toggle for every kind, invalid kind rejection,
    editor 423 vs owner pass on a locked page
  * Edit-request + grant flow: create request -> admin approves -> single-use grant lets the editor
    save once, and the grant is consumed so the next save is blocked again.
"""
import importlib
import os
import sys
import uuid
import requests
import pytest

def _base():
    u = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not u:
        # fall back to frontend/.env for local pytest runs
        try:
            with open("/app/frontend/.env") as fh:
                for line in fh:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        u = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert u, "REACT_APP_BACKEND_URL not set"
    return u.rstrip("/") + "/api"


BASE = _base()
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
EDITOR = {"email": "client.editor@example.com", "password": "ClientEdit2026!"}


# ---------- Import-order sanity ----------
def test_import_order_locks_first():
    """`locks` must not need `edit_requests` at import time and vice versa."""
    sys.path.insert(0, "/app/backend")
    for m in ("locks", "edit_requests", "lock_shared"):
        sys.modules.pop(m, None)
    importlib.import_module("locks")
    importlib.import_module("edit_requests")
    importlib.import_module("lock_shared")


def test_import_order_edit_requests_first():
    sys.path.insert(0, "/app/backend")
    for m in ("locks", "edit_requests", "lock_shared"):
        sys.modules.pop(m, None)
    importlib.import_module("edit_requests")
    importlib.import_module("locks")


# ---------- Session fixtures ----------
@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def editor():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json=EDITOR)
    if r.status_code != 200:
        r = s.post(f"{BASE}/auth/register",
                   json={**EDITOR, "name": "Client Editor"})
    assert r.status_code == 200, r.text
    return s


# ---------- Throwaway tenant lifecycle ----------
@pytest.fixture(scope="module")
def tenant(admin, editor):
    name = f"TEST_iter63_{uuid.uuid4().hex[:6]}"
    r = admin.post(f"{BASE}/apps", json={
        "name": name, "industry": "tech", "kind": "website",
        "description": "iter63 regression tenant", "status": "active",
        "tags": [], "color": "#3B82F6", "thumbnail": "", "video_url": "", "live_url": "",
    })
    assert r.status_code == 200, r.text
    app_id = r.json()["app_id"]
    # get editor user_id
    me = editor.get(f"{BASE}/auth/me").json()
    editor_uid = me["user_id"]
    # invite editor
    inv = admin.post(f"{BASE}/apps/{app_id}/members",
                     json={"email": EDITOR["email"], "role": "editor"})
    assert inv.status_code in (200, 201), inv.text
    yield {"app_id": app_id, "editor_uid": editor_uid}
    # Cleanup: archive then purge
    admin.post(f"{BASE}/apps/{app_id}/archive", json={})
    admin.delete(f"{BASE}/apps/{app_id}/purge")


# ---------- Health ----------
def test_health():
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200


# ---------- Lock endpoints ----------
def test_get_locks_shape(admin, tenant):
    r = admin.get(f"{BASE}/apps/{tenant['app_id']}/locks")
    assert r.status_code == 200
    body = r.json()
    for k in ("state", "locked", "total", "master", "locks", "role", "can_manage"):
        assert k in body
    assert body["can_manage"] is True
    assert body["state"] in ("unlocked", "partial", "locked")


def test_master_toggle(admin, tenant):
    r = admin.post(f"{BASE}/apps/{tenant['app_id']}/locks/all", json={"locked": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["master"] is True
    assert body["state"] == "locked"
    # Unlock again
    r2 = admin.post(f"{BASE}/apps/{tenant['app_id']}/locks/all", json={"locked": False})
    assert r2.status_code == 200
    assert r2.json()["master"] is False


KINDS = ("page", "block", "form", "cms_collection", "cms_item", "workflow",
         "data_destination", "app_mode", "overview")


@pytest.mark.parametrize("kind", KINDS)
def test_granular_toggle_every_kind(admin, tenant, kind):
    item_id = f"test_{kind}_{uuid.uuid4().hex[:6]}"
    r = admin.post(f"{BASE}/apps/{tenant['app_id']}/locks/item",
                   json={"kind": kind, "item_id": item_id, "locked": True})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["kind"] == kind and j["locked"] is True
    # Unlock
    r2 = admin.post(f"{BASE}/apps/{tenant['app_id']}/locks/item",
                    json={"kind": kind, "item_id": item_id, "locked": False})
    assert r2.status_code == 200 and r2.json()["locked"] is False


def test_invalid_kind_rejected(admin, tenant):
    r = admin.post(f"{BASE}/apps/{tenant['app_id']}/locks/item",
                   json={"kind": "not_a_kind", "item_id": "x", "locked": True})
    assert r.status_code == 400


# ---------- Lock enforcement + edit-request/grant flow ----------
@pytest.fixture(scope="module")
def home_page(admin, tenant):
    r = admin.get(f"{BASE}/apps/{tenant['app_id']}/pages")
    assert r.status_code == 200, r.text
    pages = r.json()
    home = next((p for p in pages if p.get("slug") == "/"), pages[0] if pages else None)
    assert home, "no home page"
    return home


def test_editor_blocked_on_locked_page_and_grant_flow(admin, editor, tenant, home_page):
    app_id = tenant["app_id"]
    page_id = home_page["page_id"]
    # Lock the page
    lock = admin.post(f"{BASE}/apps/{app_id}/locks/item",
                      json={"kind": "page", "item_id": page_id, "locked": True})
    assert lock.status_code == 200

    blocks = home_page.get("blocks") or []

    # Editor tries to save -> 423
    r = editor.patch(f"{BASE}/apps/{app_id}/pages/{page_id}", json={"blocks": blocks})
    assert r.status_code == 423, f"expected 423 got {r.status_code}: {r.text}"

    # Owner (admin) still passes
    r_owner = admin.patch(f"{BASE}/apps/{app_id}/pages/{page_id}", json={"blocks": blocks})
    assert r_owner.status_code == 200, r_owner.text

    # Editor creates an edit request
    er = editor.post(f"{BASE}/apps/{app_id}/pages/{page_id}/edit-request",
                     json={"description": "Please change hero copy"})
    assert er.status_code == 200, er.text
    message_id = er.json()["message_id"]

    # Admin approves -> grant issued
    ap = admin.post(f"{BASE}/apps/{app_id}/inbox/{message_id}/edit-request/approve",
                    json={"reply": "ok"})
    assert ap.status_code == 200, ap.text
    grant = ap.json().get("grant")
    assert grant and grant.get("grant_id")

    # Editor can save once (grant consumed)
    r2 = editor.patch(f"{BASE}/apps/{app_id}/pages/{page_id}", json={"blocks": blocks})
    assert r2.status_code == 200, f"grant should permit save, got {r2.status_code}: {r2.text}"

    # Second save should be blocked again (grant consumed)
    r3 = editor.patch(f"{BASE}/apps/{app_id}/pages/{page_id}", json={"blocks": blocks})
    assert r3.status_code == 423, f"expected 423 after grant consumed, got {r3.status_code}: {r3.text}"

    # Cleanup: unlock
    admin.post(f"{BASE}/apps/{app_id}/locks/item",
               json={"kind": "page", "item_id": page_id, "locked": False})


def test_locks_summary(admin):
    r = admin.get(f"{BASE}/locks/summary")
    assert r.status_code == 200
    assert "tenants" in r.json()
