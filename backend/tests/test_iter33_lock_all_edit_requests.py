"""Iter-33: Lock-all, ZIP import, Version Diff and Client Edit Request flow.

Covers:
- POST /apps/{id}/pages/lock-all locks/unlocks every page + tenant content lock
- Route order: lock-all is NOT swallowed by /pages/{page_id}/lock
- 403 for editor on lock-all; owner/admin OK
- Owner can save while all pages locked; editor gets 423
- Edit-request flow: create -> approve -> single-use save -> re-lock
- Version diff endpoint returns added/removed/edited
- ZIP import: 423 when locked (replace), succeeds when unlocked
"""
import io
import os
import time
import zipfile
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASS = "Lucio2026!"
EDITOR_EMAIL = "client.editor@example.com"
EDITOR_PASS = "ClientEdit2026!"
APP_ID = "app_7a2cd286a360"  # Zip Import Test — editor is a member here


# --------- fixtures ---------
def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def editor():
    return _login(EDITOR_EMAIL, EDITOR_PASS)


@pytest.fixture(autouse=True)
def reset_state(admin):
    """Ensure app starts unlocked before each test."""
    admin.post(f"{API}/apps/{APP_ID}/pages/lock-all", json={"locked": False}, timeout=15)
    yield
    admin.post(f"{API}/apps/{APP_ID}/pages/lock-all", json={"locked": False}, timeout=15)


# --------- tests ---------
def _pages(sess):
    r = sess.get(f"{API}/apps/{APP_ID}/pages", timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def _content_lock(sess):
    r = sess.get(f"{API}/apps/{APP_ID}/content-lock", timeout=15)
    assert r.status_code == 200
    return r.json()


def test_route_order_lock_all_not_shadowed(admin):
    """POST /pages/lock-all must NOT be interpreted as /pages/{page_id}/... — expect a real
    JSON response with {locked, pages, content_locked}, not a 404/422."""
    r = admin.post(f"{API}/apps/{APP_ID}/pages/lock-all", json={"locked": True}, timeout=15)
    assert r.status_code == 200, f"unexpected {r.status_code}: {r.text}"
    body = r.json()
    assert body["locked"] is True
    assert body["content_locked"] is True
    assert body["pages"] >= 1


def test_lock_all_locks_pages_and_content(admin):
    r = admin.post(f"{API}/apps/{APP_ID}/pages/lock-all", json={"locked": True}, timeout=15)
    assert r.status_code == 200
    pages = _pages(admin)
    assert pages, "app has no pages"
    assert all(p.get("locked") for p in pages), f"not all locked: {[(p['slug'], p.get('locked')) for p in pages]}"
    assert _content_lock(admin)["locked"] is True


def test_unlock_all_unlocks(admin):
    admin.post(f"{API}/apps/{APP_ID}/pages/lock-all", json={"locked": True}, timeout=15)
    r = admin.post(f"{API}/apps/{APP_ID}/pages/lock-all", json={"locked": False}, timeout=15)
    assert r.status_code == 200
    assert r.json()["locked"] is False
    assert all(not p.get("locked") for p in _pages(admin))
    assert _content_lock(admin)["locked"] is False


def test_editor_cannot_lock_all(editor):
    r = editor.post(f"{API}/apps/{APP_ID}/pages/lock-all", json={"locked": True}, timeout=15)
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"


def test_owner_can_save_while_all_locked(admin):
    admin.post(f"{API}/apps/{APP_ID}/pages/lock-all", json={"locked": True}, timeout=15)
    pages = _pages(admin)
    home = next(p for p in pages if p["slug"] == "/")
    # PATCH with same blocks — owner should still succeed even while locked
    r = admin.patch(f"{API}/apps/{APP_ID}/pages/{home['page_id']}",
                    json={"blocks": home.get("blocks") or []}, timeout=20)
    assert r.status_code == 200, f"owner save blocked while locked: {r.status_code} {r.text}"


def test_editor_gets_423_when_saving_locked_page(admin, editor):
    admin.post(f"{API}/apps/{APP_ID}/pages/lock-all", json={"locked": True}, timeout=15)
    pages = _pages(editor)
    home = next(p for p in pages if p["slug"] == "/")
    r = editor.patch(f"{API}/apps/{APP_ID}/pages/{home['page_id']}",
                     json={"blocks": home.get("blocks") or []}, timeout=20)
    assert r.status_code == 423, f"expected 423, got {r.status_code}: {r.text}"
    detail = (r.json().get("detail") or "").lower()
    assert "locked" in detail or "request" in detail


def test_edit_request_flow(admin, editor):
    """editor cannot save while locked -> requests change -> admin approves ->
    editor saves ONCE -> next save is blocked again (grant single-use)."""
    admin.post(f"{API}/apps/{APP_ID}/pages/lock-all", json={"locked": True}, timeout=15)
    pages = _pages(editor)
    home = next(p for p in pages if p["slug"] == "/")
    pid = home["page_id"]

    # editor requests change
    r = editor.post(f"{API}/apps/{APP_ID}/pages/{pid}/edit-request",
                    json={"description": "TEST_iter33 please tweak the hero copy"}, timeout=20)
    assert r.status_code == 200, r.text
    msg_id = r.json()["message_id"]

    # admin approves
    r = admin.post(f"{API}/apps/{APP_ID}/inbox/{msg_id}/edit-request/approve",
                   json={"reply": "ok, tweak away"}, timeout=20)
    assert r.status_code == 200, r.text
    assert r.json()["edit_request"]["state"] == "approved"

    # edit-access reflects grant
    r = editor.get(f"{API}/apps/{APP_ID}/pages/{pid}/edit-access", timeout=15)
    assert r.status_code == 200
    acc = r.json()
    assert acc["can_edit"] is True, f"editor should be able to edit after approval: {acc}"
    assert acc.get("grant"), "no active grant returned to editor"

    # editor saves once — success expected
    r = editor.patch(f"{API}/apps/{APP_ID}/pages/{pid}",
                     json={"blocks": home.get("blocks") or []}, timeout=20)
    assert r.status_code == 200, f"editor save with grant failed: {r.status_code} {r.text}"

    # second save should be blocked again (grant consumed)
    r = editor.patch(f"{API}/apps/{APP_ID}/pages/{pid}",
                     json={"blocks": home.get("blocks") or []}, timeout=20)
    assert r.status_code == 423, f"grant should be single-use, got {r.status_code}: {r.text}"


def test_version_diff_endpoint(admin):
    """Save a change to create a new version, then diff prior version vs current."""
    pages = _pages(admin)
    home = next(p for p in pages if p["slug"] == "/")
    pid = home["page_id"]

    # Get current version list
    r = admin.get(f"{API}/apps/{APP_ID}/pages/{pid}/versions", timeout=15)
    assert r.status_code == 200
    versions_before = r.json()["versions"]

    # Make an actual edit
    blocks = home.get("blocks") or []
    if not blocks:
        pytest.skip("home page has no blocks to edit")
    edited = [dict(b) for b in blocks]
    # tweak first hero title if possible
    for b in edited:
        if b.get("type") == "hero" and isinstance(b.get("props"), dict):
            b["props"] = {**b["props"], "title": f"TEST_iter33 diff {int(time.time())}"}
            break
    else:
        # no hero, just append a marker
        edited.append({"id": f"blk_test_{int(time.time())}", "type": "cta",
                       "props": {"title": "TEST_iter33", "subtitle": "diff test", "cta": "OK"}, "style": {}})

    r = admin.patch(f"{API}/apps/{APP_ID}/pages/{pid}", json={"blocks": edited}, timeout=20)
    assert r.status_code == 200

    # list versions again — a new one should have appeared
    r = admin.get(f"{API}/apps/{APP_ID}/pages/{pid}/versions", timeout=15)
    versions_after = r.json()["versions"]
    assert len(versions_after) > len(versions_before) or (versions_after and versions_after[0]["created_at"] != (versions_before[0]["created_at"] if versions_before else None))

    latest_version_id = versions_after[0]["version_id"]

    # diff — should return summary with added/removed/edited counts
    r = admin.get(f"{API}/apps/{APP_ID}/pages/{pid}/versions/{latest_version_id}/diff", timeout=15)
    assert r.status_code == 200, r.text
    diff = r.json()
    assert "summary" in diff and "changes" in diff
    for key in ("added", "removed", "edited", "sections_now", "sections_after", "identical"):
        assert key in diff["summary"], f"missing key {key} in diff summary"

    # restore back to original (best-effort cleanup)
    admin.patch(f"{API}/apps/{APP_ID}/pages/{pid}", json={"blocks": blocks}, timeout=20)


def test_zip_import_blocked_when_locked(admin):
    """POST /site/import-zip with mode=replace must 423 while content lock is on."""
    admin.post(f"{API}/apps/{APP_ID}/pages/lock-all", json={"locked": True}, timeout=15)
    # Build a tiny zip in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", "<html><head><title>Test</title></head><body><h1>Hi</h1></body></html>")
    buf.seek(0)
    r = admin.post(f"{API}/apps/{APP_ID}/site/import-zip",
                   files={"file": ("test.zip", buf.getvalue(), "application/zip")},
                   data={"mode": "replace", "apply_theme": "false"}, timeout=30)
    assert r.status_code == 423, f"expected 423 while locked, got {r.status_code}: {r.text[:200]}"


def test_zip_import_starts_when_unlocked(admin):
    """When unlocked, the ZIP import kicks off (returns a job_id)."""
    admin.post(f"{API}/apps/{APP_ID}/pages/lock-all", json={"locked": False}, timeout=15)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", "<html><head><title>TEST_iter33</title></head><body><h1>hero</h1><p>hello</p></body></html>")
    r = admin.post(f"{API}/apps/{APP_ID}/site/import-zip",
                   files={"file": ("test.zip", buf.getvalue(), "application/zip")},
                   data={"mode": "append", "apply_theme": "false"}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "job_id" in body
    # optional: poll job briefly
    for _ in range(10):
        time.sleep(1)
        j = admin.get(f"{API}/apps/{APP_ID}/site/import-progress/{body['job_id']}", timeout=10)
        if j.status_code == 200 and j.json().get("status") in ("done", "error"):
            break
    # not asserting final state — build/parse variance is fine; the 200 + job_id is the contract we care about


def test_edit_access_endpoint_shape(admin, editor):
    admin.post(f"{API}/apps/{APP_ID}/pages/lock-all", json={"locked": True}, timeout=15)
    pages = _pages(editor)
    pid = pages[0]["page_id"]
    r = editor.get(f"{API}/apps/{APP_ID}/pages/{pid}/edit-access", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["locked"] is True
    assert data["can_edit"] is False
    assert data["can_request"] is True
    assert data["role"] in ("editor", "viewer", "member")
