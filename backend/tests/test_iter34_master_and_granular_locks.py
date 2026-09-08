"""Iter-34: Master + granular lock system across every kind, and generic edit-request flow.

Covers:
- POST /apps/{id}/locks/all locks/unlocks every item (state=locked/partial/unlocked, master flag)
- POST /apps/{id}/locks/item granular per (kind,item_id); 400 on unknown kind; 403 for editor
- GET /apps/{id}/locks returns state + locks map + role + can_manage
- GET /locks/summary rolls up per-tenant states for the dashboard
- GET /apps/{id}/edit-access?kind=&item_id= for owner/editor
- 423 gates: page save with a changed locked section, CMS item PUT, workflow PUT/DELETE (editor)
- Owner is never blocked
- Generic POST /apps/{id}/edit-request creates edit_request Inbox message; approve → single-use grant;
  after one successful edit the grant is consumed and the item is locked again.
- No route shadowing between /locks/all vs /locks/item, and edit-access page vs generic.
"""
import os
import time
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASS = "Lucio2026!"
EDITOR_EMAIL = "client.editor@example.com"
EDITOR_PASS = "ClientEdit2026!"
APP_ID = "app_7a2cd286a360"  # Zip Import Test — editor is a member


# ---------- fixtures ----------
def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} → {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def editor():
    return _login(EDITOR_EMAIL, EDITOR_PASS)


@pytest.fixture(autouse=True)
def _reset_locks(admin):
    """Guarantee tenant starts fully unlocked so tests are independent."""
    admin.post(f"{API}/apps/{APP_ID}/locks/all", json={"locked": False}, timeout=20)
    yield
    admin.post(f"{API}/apps/{APP_ID}/locks/all", json={"locked": False}, timeout=20)


# ---------- helpers ----------
def _summary(sess):
    r = sess.get(f"{API}/apps/{APP_ID}/locks", timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def _first_page(sess):
    r = sess.get(f"{API}/apps/{APP_ID}/pages", timeout=15)
    assert r.status_code == 200, r.text
    pages = r.json()
    assert pages, "tenant must have at least one page"
    return pages[0]


def _ensure_collection(admin):
    r = admin.get(f"{API}/apps/{APP_ID}/cms", timeout=15)
    assert r.status_code == 200, r.text
    cols = r.json()
    if cols:
        return cols[0]
    r = admin.post(f"{API}/apps/{APP_ID}/cms", json={"name": f"TEST_col_{uuid.uuid4().hex[:6]}"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def _ensure_item(admin, collection_id):
    r = admin.get(f"{API}/apps/{APP_ID}/cms", timeout=15)
    for c in r.json():
        if c["collection_id"] == collection_id and c.get("items"):
            return c["items"][0]
    body = {"title": f"TEST_item_{uuid.uuid4().hex[:6]}", "slug": "", "body": "hello",
            "excerpt": "", "cover_url": "", "date": "", "tags": [], "status": "published"}
    r = admin.post(f"{API}/apps/{APP_ID}/cms/{collection_id}/items", json=body, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def _ensure_workflow(admin):
    r = admin.get(f"{API}/apps/{APP_ID}/workflows", timeout=15)
    assert r.status_code == 200, r.text
    wfs = r.json().get("workflows") or []
    if wfs:
        return wfs[0]
    body = {"name": f"TEST_wf_{uuid.uuid4().hex[:6]}", "trigger": "lead.created",
            "actions": [], "enabled": True}
    r = admin.post(f"{API}/apps/{APP_ID}/workflows", json=body, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- tests ----------
class TestMasterLockAll:
    def test_lock_all_then_unlock_all(self, admin):
        r = admin.post(f"{API}/apps/{APP_ID}/locks/all", json={"locked": True}, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["items"] > 0
        assert data["state"] == "locked"
        assert data["master"] is True
        assert data["locked"] == data["total"] and data["total"] > 0
        # summary agrees
        s = _summary(admin)
        assert s["state"] == "locked" and s["master"] is True and s["locked"] == s["total"]
        # unlock
        r = admin.post(f"{API}/apps/{APP_ID}/locks/all", json={"locked": False}, timeout=20)
        assert r.status_code == 200
        s = _summary(admin)
        assert s["state"] == "unlocked" and s["master"] is False and s["locked"] == 0

    def test_editor_forbidden_on_lock_all(self, editor):
        r = editor.post(f"{API}/apps/{APP_ID}/locks/all", json={"locked": True}, timeout=15)
        assert r.status_code == 403, r.text


class TestGranularLocks:
    def test_lock_single_item_shows_partial(self, admin):
        col = _ensure_collection(admin)
        r = admin.post(f"{API}/apps/{APP_ID}/locks/item",
                       json={"kind": "cms_collection", "item_id": col["collection_id"], "locked": True}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("kind") == "cms_collection"
        s = _summary(admin)
        assert s["state"] == "partial"
        assert s["locks"].get("cms_collection", {}).get(col["collection_id"]) is True
        # unlock
        admin.post(f"{API}/apps/{APP_ID}/locks/item",
                   json={"kind": "cms_collection", "item_id": col["collection_id"], "locked": False}, timeout=15)

    def test_unknown_kind_returns_400(self, admin):
        r = admin.post(f"{API}/apps/{APP_ID}/locks/item",
                       json={"kind": "nonsense", "item_id": "x", "locked": True}, timeout=15)
        assert r.status_code == 400, r.text

    def test_editor_forbidden_on_lock_item(self, editor):
        r = editor.post(f"{API}/apps/{APP_ID}/locks/item",
                        json={"kind": "workflow", "item_id": "x", "locked": True}, timeout=15)
        assert r.status_code == 403, r.text

    def test_route_order_all_vs_item(self, admin):
        # /locks/all must not be swallowed by /locks/item (which expects "item" as path)
        r = admin.post(f"{API}/apps/{APP_ID}/locks/all", json={"locked": False}, timeout=15)
        assert r.status_code == 200 and "state" in r.json()


class TestEditAccess:
    def test_owner_can_edit_locked(self, admin):
        wf = _ensure_workflow(admin)
        admin.post(f"{API}/apps/{APP_ID}/locks/item",
                   json={"kind": "workflow", "item_id": wf["workflow_id"], "locked": True}, timeout=15)
        r = admin.get(f"{API}/apps/{APP_ID}/edit-access",
                      params={"kind": "workflow", "item_id": wf["workflow_id"]}, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["locked"] is True and j["can_edit"] is True and j["can_request"] is False
        assert j["role"] in ("owner", "admin")

    def test_editor_locked_cannot_edit_can_request(self, admin, editor):
        wf = _ensure_workflow(admin)
        admin.post(f"{API}/apps/{APP_ID}/locks/item",
                   json={"kind": "workflow", "item_id": wf["workflow_id"], "locked": True}, timeout=15)
        r = editor.get(f"{API}/apps/{APP_ID}/edit-access",
                       params={"kind": "workflow", "item_id": wf["workflow_id"]}, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["locked"] is True and j["can_edit"] is False and j["can_request"] is True

    def test_page_edit_access_route_not_shadowed(self, admin):
        pg = _first_page(admin)
        r = admin.get(f"{API}/apps/{APP_ID}/pages/{pg['page_id']}/edit-access", timeout=15)
        assert r.status_code == 200, r.text
        assert "locked" in r.json() and "role" in r.json()


class TestGates423:
    def test_editor_cannot_edit_locked_cms_item(self, admin, editor):
        col = _ensure_collection(admin)
        it = _ensure_item(admin, col["collection_id"])
        admin.post(f"{API}/apps/{APP_ID}/locks/item",
                   json={"kind": "cms_item", "item_id": it["item_id"], "locked": True}, timeout=15)
        body = {"title": it["title"] + " (edit)", "slug": it.get("slug") or "",
                "body": it.get("body") or "", "excerpt": it.get("excerpt") or "",
                "cover_url": it.get("cover_url") or "", "date": it.get("date") or "",
                "tags": it.get("tags") or [], "status": it.get("status") or "published"}
        r = editor.put(f"{API}/apps/{APP_ID}/cms/{col['collection_id']}/items/{it['item_id']}", json=body, timeout=15)
        assert r.status_code == 423, f"expected 423, got {r.status_code}: {r.text[:200]}"

    def test_owner_can_edit_locked_cms_item(self, admin):
        col = _ensure_collection(admin)
        it = _ensure_item(admin, col["collection_id"])
        admin.post(f"{API}/apps/{APP_ID}/locks/item",
                   json={"kind": "cms_item", "item_id": it["item_id"], "locked": True}, timeout=15)
        body = {"title": it["title"] + " admin-edit", "slug": it.get("slug") or "",
                "body": "updated by admin", "excerpt": it.get("excerpt") or "",
                "cover_url": "", "date": it.get("date") or "", "tags": [], "status": "published"}
        r = admin.put(f"{API}/apps/{APP_ID}/cms/{col['collection_id']}/items/{it['item_id']}", json=body, timeout=15)
        assert r.status_code == 200, r.text

    def test_editor_cannot_edit_or_delete_locked_workflow(self, admin, editor):
        wf = _ensure_workflow(admin)
        admin.post(f"{API}/apps/{APP_ID}/locks/item",
                   json={"kind": "workflow", "item_id": wf["workflow_id"], "locked": True}, timeout=15)
        body = {"name": wf["name"] + " x", "trigger": wf["trigger"],
                "actions": wf.get("actions") or [], "enabled": bool(wf.get("enabled", True))}
        r = editor.put(f"{API}/apps/{APP_ID}/workflows/{wf['workflow_id']}", json=body, timeout=15)
        assert r.status_code == 423, r.text
        r = editor.delete(f"{API}/apps/{APP_ID}/workflows/{wf['workflow_id']}", timeout=15)
        assert r.status_code == 423, r.text

    def test_owner_can_save_page_while_all_locked(self, admin):
        admin.post(f"{API}/apps/{APP_ID}/locks/all", json={"locked": True}, timeout=15)
        pg = _first_page(admin)
        r = admin.patch(f"{API}/apps/{APP_ID}/pages/{pg['page_id']}",
                      json={"blocks": pg.get("blocks") or []}, timeout=20)
        assert r.status_code == 200, r.text


class TestLocksSummaryDashboard:
    def test_summary_reports_this_tenant(self, admin):
        admin.post(f"{API}/apps/{APP_ID}/locks/all", json={"locked": True}, timeout=20)
        r = admin.get(f"{API}/locks/summary", timeout=20)
        assert r.status_code == 200, r.text
        tenants = r.json().get("tenants") or {}
        assert APP_ID in tenants, "our tenant must appear in dashboard rollup"
        me = tenants[APP_ID]
        assert me["state"] == "locked" and me["locked"] == me["total"]
        # unlock and reread
        admin.post(f"{API}/apps/{APP_ID}/locks/all", json={"locked": False}, timeout=20)
        r = admin.get(f"{API}/locks/summary", timeout=20)
        assert r.json()["tenants"][APP_ID]["state"] == "unlocked"


class TestGenericEditRequestFlow:
    def test_request_approve_single_use_grant(self, admin, editor):
        col = _ensure_collection(admin)
        it = _ensure_item(admin, col["collection_id"])
        # lock the CMS item
        admin.post(f"{API}/apps/{APP_ID}/locks/item",
                   json={"kind": "cms_item", "item_id": it["item_id"], "locked": True}, timeout=15)

        # editor requests change via generic endpoint
        r = editor.post(f"{API}/apps/{APP_ID}/edit-request",
                        json={"kind": "cms_item", "item_id": it["item_id"],
                              "item_name": it["title"], "description": "please tweak this copy"}, timeout=20)
        assert r.status_code == 200, r.text
        msg = r.json()
        assert msg["kind"] == "edit_request" and msg["edit_request"]["state"] == "pending"
        assert msg["edit_request"]["item_kind"] == "cms_item"
        message_id = msg["message_id"]

        # admin approves
        r = admin.post(f"{API}/apps/{APP_ID}/inbox/{message_id}/edit-request/approve",
                       json={"reply": "ok"}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["grant"]["grant_id"]

        # edit-access should now report can_edit true for editor
        r = editor.get(f"{API}/apps/{APP_ID}/edit-access",
                       params={"kind": "cms_item", "item_id": it["item_id"]}, timeout=15)
        assert r.status_code == 200
        assert r.json()["can_edit"] is True

        # first PUT succeeds
        body = {"title": it["title"] + " (client)", "slug": it.get("slug") or "",
                "body": "client-edited body", "excerpt": "", "cover_url": "",
                "date": it.get("date") or "", "tags": [], "status": "published"}
        r = editor.put(f"{API}/apps/{APP_ID}/cms/{col['collection_id']}/items/{it['item_id']}", json=body, timeout=20)
        assert r.status_code == 200, f"first edit should pass, got {r.status_code}: {r.text[:200]}"

        # second PUT is blocked again (grant consumed, item still locked)
        r = editor.put(f"{API}/apps/{APP_ID}/cms/{col['collection_id']}/items/{it['item_id']}", json=body, timeout=20)
        assert r.status_code == 423, f"expected re-lock after single-use, got {r.status_code}: {r.text[:200]}"

    def test_generic_edit_request_unknown_kind(self, editor):
        r = editor.post(f"{API}/apps/{APP_ID}/edit-request",
                        json={"kind": "nonsense", "item_id": "x", "description": "hi"}, timeout=15)
        assert r.status_code == 400, r.text
