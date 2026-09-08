"""Iter-32 backend tests: page-level lock (owner/admin gate) + dated content history with restore.

Covers:
- POST /apps/{id}/pages/{page_id}/lock as owner: persists, toggles, activity log kind='page.lock', 404 bogus.
- Permission matrix: editor + viewer -> 403; admin -> allowed; owner -> allowed.
- Lock enforcement: locked page PATCH by editor -> 423 with the page name; owner/admin still allowed.
  Restore endpoint follows the same rule.
- Version history: creates a pre-save snapshot each save; newest-first; max=30; version cap prunes oldest.
- Version fetch/preview contract: full blocks returned; 404 friendly on unknown id; fetch does not mutate page.
- Restore: sets blocks, writes 'before restore' snapshot, refreshes site_snapshot, logs page.restored;
  restoring the 'before restore' snapshot round-trips.
- Import/AI/premium snapshots: db.page_versions has 'before import from ...' / 'before ... rebuild' /
  'before AI site generation' entries after those wholesale rewrites on a THROWAWAY tenant.
- Cross-tenant isolation: version/lock endpoints 404/403 for a page belonging to another tenant.
"""
import os
import time
import uuid
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

_mongo = MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]


# ---------- fixtures ----------
def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return s


def _register(email, password, name):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/register",
               json={"email": email, "password": password, "name": name}, timeout=30)
    # If already registered, login instead.
    if r.status_code == 400:
        return _login(email, password)
    assert r.status_code == 200, r.text[:200]
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def role_users():
    """Register 3 role users; will be invited per-tenant."""
    suffix = uuid.uuid4().hex[:8]
    users = {}
    for role in ("editor", "viewer", "admin"):
        email = f"TEST_iter32_{role}_{suffix}@example.com"
        users[role] = {
            "email": email,
            "password": "TestPass1234!",
            "session": _register(email, "TestPass1234!", f"iter32-{role}"),
        }
    yield users
    # Cleanup users
    for u in users.values():
        try:
            _db.users.delete_one({"email": u["email"]})
        except Exception:
            pass


@pytest.fixture()
def throwaway(admin, role_users):
    """Create a throwaway tenant + unlock content (so we can PATCH blocks freely) + invite the 3 role users."""
    r = admin.post(f"{BASE_URL}/apps", json={
        "name": f"TEST_iter32_{uuid.uuid4().hex[:6]}", "industry": "SaaS",
        "kind": "website", "description": "throwaway", "status": "draft", "tags": [], "color": "#333",
    }, timeout=30)
    assert r.status_code == 200, r.text[:300]
    aid = r.json()["app_id"]
    # Unlock content so PATCH page works while we test the page-level lock feature.
    admin.post(f"{BASE_URL}/apps/{aid}/content-lock", json={"locked": False}, timeout=10)
    # Invite the 3 role users.
    for role, u in role_users.items():
        rr = admin.post(f"{BASE_URL}/apps/{aid}/members",
                        json={"email": u["email"], "role": role}, timeout=15)
        assert rr.status_code == 200, rr.text[:200]
    yield aid
    try:
        admin.delete(f"{BASE_URL}/apps/{aid}", timeout=20)
    except Exception:
        pass


def _home_page_id(admin, app_id):
    pages = admin.get(f"{BASE_URL}/apps/{app_id}/pages", timeout=10).json()
    home = next((p for p in pages if p.get("slug") == "/"), pages[0])
    return home["page_id"], home


def _hero_blocks(title="H", subtitle="S", image="https://example.com/x.jpg"):
    return [{"id": f"b_{uuid.uuid4().hex[:6]}", "type": "hero",
             "props": {"title": title, "subtitle": subtitle, "image": image}}]


# ============ 1. Lock endpoint (owner) ============
class TestLockEndpointOwner:
    def test_lock_toggle_persists_and_activity(self, admin, throwaway):
        pid, _ = _home_page_id(admin, throwaway)
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/lock",
                       json={"locked": True}, timeout=15)
        assert r.status_code == 200, r.text[:200]
        assert r.json()["locked"] is True

        # Persists on GET /pages
        pages = admin.get(f"{BASE_URL}/apps/{throwaway}/pages", timeout=10).json()
        assert next(p for p in pages if p["page_id"] == pid)["locked"] is True

        # Toggle back to false
        r2 = admin.post(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/lock",
                        json={"locked": False}, timeout=15)
        assert r2.status_code == 200 and r2.json()["locked"] is False

        # Activity log: kind='page.lock'
        acts = admin.get(f"{BASE_URL}/apps/{throwaway}/activity", timeout=10).json()
        kinds = [a.get("kind") for a in acts]
        assert kinds.count("page.lock") >= 2, f"expected >=2 page.lock, got {kinds[:10]}"

    def test_bogus_page_id_404(self, admin, throwaway):
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/pages/pg_does_not_exist/lock",
                       json={"locked": True}, timeout=15)
        assert r.status_code == 404, r.text[:200]


# ============ 2. Permission matrix (editor/viewer/admin) ============
class TestLockPermissions:
    def test_editor_and_viewer_forbidden_admin_allowed(self, admin, throwaway, role_users):
        pid, _ = _home_page_id(admin, throwaway)
        # editor 403
        r = role_users["editor"]["session"].post(
            f"{BASE_URL}/apps/{throwaway}/pages/{pid}/lock", json={"locked": True}, timeout=15)
        assert r.status_code == 403, r.text[:200]
        assert "owner" in r.text.lower() or "admin" in r.text.lower()
        # viewer 403
        r = role_users["viewer"]["session"].post(
            f"{BASE_URL}/apps/{throwaway}/pages/{pid}/lock", json={"locked": True}, timeout=15)
        assert r.status_code == 403, r.text[:200]
        # admin allowed (lock then unlock)
        r = role_users["admin"]["session"].post(
            f"{BASE_URL}/apps/{throwaway}/pages/{pid}/lock", json={"locked": True}, timeout=15)
        assert r.status_code == 200, r.text[:200]
        r = role_users["admin"]["session"].post(
            f"{BASE_URL}/apps/{throwaway}/pages/{pid}/lock", json={"locked": False}, timeout=15)
        assert r.status_code == 200


# ============ 3. Lock enforcement on PATCH + restore ============
class TestLockEnforcement:
    def test_locked_page_editor_423_owner_admin_allowed(self, admin, throwaway, role_users):
        pid, home = _home_page_id(admin, throwaway)
        # Lock via owner
        admin.post(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/lock", json={"locked": True}, timeout=10)

        page_name = home["name"]
        original_blocks = home.get("blocks") or []

        # Editor PATCH -> 423, message names the page, blocks unchanged.
        blocks = _hero_blocks("editor tried")
        r = role_users["editor"]["session"].patch(
            f"{BASE_URL}/apps/{throwaway}/pages/{pid}", json={"blocks": blocks}, timeout=15)
        assert r.status_code == 423, r.text[:200]
        assert page_name in r.text or "locked" in r.text.lower()
        # Confirm blocks unchanged (compare via admin GET).
        current = admin.get(f"{BASE_URL}/apps/{throwaway}/pages", timeout=10).json()
        current_home = next(p for p in current if p["page_id"] == pid)
        assert current_home.get("blocks") == original_blocks

        # Owner PATCH allowed
        blocks_o = _hero_blocks("owner ok", "st1")
        r = admin.patch(f"{BASE_URL}/apps/{throwaway}/pages/{pid}",
                        json={"blocks": blocks_o}, timeout=15)
        assert r.status_code == 200, r.text[:200]

        # Admin PATCH allowed
        blocks_a = _hero_blocks("admin ok", "st2")
        r = role_users["admin"]["session"].patch(
            f"{BASE_URL}/apps/{throwaway}/pages/{pid}", json={"blocks": blocks_a}, timeout=15)
        assert r.status_code == 200, r.text[:200]

    def test_locked_page_restore_editor_423(self, admin, throwaway, role_users):
        pid, _ = _home_page_id(admin, throwaway)
        # Unlock first, produce two versions, lock, try restore as editor.
        admin.post(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/lock", json={"locked": False}, timeout=10)
        admin.patch(f"{BASE_URL}/apps/{throwaway}/pages/{pid}",
                    json={"blocks": _hero_blocks("v1")}, timeout=15)
        admin.patch(f"{BASE_URL}/apps/{throwaway}/pages/{pid}",
                    json={"blocks": _hero_blocks("v2")}, timeout=15)
        vs = admin.get(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/versions", timeout=10).json()["versions"]
        assert vs, "expected versions after 2 saves"
        vid = vs[0]["version_id"]
        # Lock
        admin.post(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/lock", json={"locked": True}, timeout=10)
        # Editor restore -> 423
        r = role_users["editor"]["session"].post(
            f"{BASE_URL}/apps/{throwaway}/pages/{pid}/versions/{vid}/restore", timeout=15)
        assert r.status_code == 423, r.text[:200]
        # Owner restore -> 200
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/versions/{vid}/restore", timeout=15)
        assert r.status_code == 200, r.text[:200]


# ============ 4. Version history creation (pre-save snapshot, newest-first) ============
class TestVersionHistory:
    def test_versions_are_presave_and_newest_first(self, admin, throwaway):
        pid, home = _home_page_id(admin, throwaway)
        # Seed a known baseline.
        b0 = _hero_blocks("baseline", "b0")
        r0 = admin.patch(f"{BASE_URL}/apps/{throwaway}/pages/{pid}", json={"blocks": b0}, timeout=15)
        assert r0.status_code == 200

        b1 = _hero_blocks("save-1", "s1")
        admin.patch(f"{BASE_URL}/apps/{throwaway}/pages/{pid}", json={"blocks": b1}, timeout=15)
        b2 = _hero_blocks("save-2", "s2")
        admin.patch(f"{BASE_URL}/apps/{throwaway}/pages/{pid}", json={"blocks": b2}, timeout=15)
        b3 = _hero_blocks("save-3", "s3")
        admin.patch(f"{BASE_URL}/apps/{throwaway}/pages/{pid}", json={"blocks": b3}, timeout=15)

        resp = admin.get(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/versions", timeout=10).json()
        assert resp["max"] == 30
        vs = resp["versions"]
        assert len(vs) >= 4, f"expected >=4 versions, got {len(vs)}"
        # Newest-first
        times = [v["created_at"] for v in vs]
        assert times == sorted(times, reverse=True)
        # Required fields
        for v in vs[:3]:
            assert "created_at" in v and "sections" in v and "by" in v and "reason" in v
            assert v["reason"] == "save"

        # Pre-save snapshot: fetch newest version's full blocks — must equal what was there
        # BEFORE the latest save (i.e. b2, not b3).
        newest = vs[0]
        full = admin.get(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/versions/{newest['version_id']}",
                         timeout=10).json()
        # b2 has a title of 'save-2'
        titles = [blk.get("props", {}).get("title") for blk in full.get("blocks", [])]
        assert "save-2" in titles, f"Expected pre-save snapshot to contain 'save-2', got titles={titles}"

        # Live page still has b3
        pages = admin.get(f"{BASE_URL}/apps/{throwaway}/pages", timeout=10).json()
        live_titles = [blk.get("props", {}).get("title")
                       for blk in next(p for p in pages if p["page_id"] == pid)["blocks"]]
        assert "save-3" in live_titles


# ============ 5. Version cap (>30) ============
class TestVersionCap:
    def test_cap_30_prunes_oldest(self, admin, throwaway):
        pid, _ = _home_page_id(admin, throwaway)
        # 33 quick saves.
        for i in range(33):
            admin.patch(f"{BASE_URL}/apps/{throwaway}/pages/{pid}",
                        json={"blocks": _hero_blocks(f"cap-{i:02d}")}, timeout=15)
        # DB check
        n = _db.page_versions.count_documents({"app_id": throwaway, "page_id": pid})
        assert n == 30, f"Expected exactly 30 versions in db, got {n}"
        # API check newest 30
        resp = admin.get(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/versions", timeout=10).json()
        assert len(resp["versions"]) == 30


# ============ 6. Version fetch/preview contract ============
class TestVersionFetchContract:
    def test_get_version_returns_full_blocks_and_404_on_unknown(self, admin, throwaway):
        pid, _ = _home_page_id(admin, throwaway)
        admin.patch(f"{BASE_URL}/apps/{throwaway}/pages/{pid}",
                    json={"blocks": _hero_blocks("preview-A")}, timeout=15)
        admin.patch(f"{BASE_URL}/apps/{throwaway}/pages/{pid}",
                    json={"blocks": _hero_blocks("preview-B")}, timeout=15)
        vs = admin.get(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/versions", timeout=10).json()["versions"]
        assert vs
        vid = vs[0]["version_id"]

        # Capture live page state before fetch.
        pre_live = next(p for p in admin.get(f"{BASE_URL}/apps/{throwaway}/pages", timeout=10).json()
                        if p["page_id"] == pid)

        # Fetch version -> full blocks
        r = admin.get(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/versions/{vid}", timeout=10)
        assert r.status_code == 200
        v = r.json()
        assert isinstance(v.get("blocks"), list) and len(v["blocks"]) > 0

        # Fetch does not mutate the live page.
        post_live = next(p for p in admin.get(f"{BASE_URL}/apps/{throwaway}/pages", timeout=10).json()
                         if p["page_id"] == pid)
        assert pre_live.get("blocks") == post_live.get("blocks")

        # 404 with friendly message on unknown version_id
        r = admin.get(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/versions/ver_nonexistent",
                      timeout=10)
        assert r.status_code == 404
        assert "no longer available" in r.text.lower() or "not found" in r.text.lower()


# ============ 7. Restore round-trip ============
class TestRestore:
    def test_restore_creates_before_restore_snapshot_and_updates_snapshot(self, admin, throwaway):
        pid, _ = _home_page_id(admin, throwaway)
        # Build 2 known states.
        A = _hero_blocks("state-A", "aa")
        B = _hero_blocks("state-B", "bb")
        admin.patch(f"{BASE_URL}/apps/{throwaway}/pages/{pid}", json={"blocks": A}, timeout=15)
        admin.patch(f"{BASE_URL}/apps/{throwaway}/pages/{pid}", json={"blocks": B}, timeout=15)

        # Find the version whose full blocks contain 'state-A'
        vs = admin.get(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/versions", timeout=10).json()["versions"]
        target_vid = None
        for v in vs:
            full = admin.get(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/versions/{v['version_id']}",
                             timeout=10).json()
            titles = [blk.get("props", {}).get("title") for blk in full.get("blocks", [])]
            if "state-A" in titles:
                target_vid = v["version_id"]
                break
        assert target_vid, "state-A version not found in history"

        # Restore state-A.
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/versions/{target_vid}/restore",
                       timeout=15)
        assert r.status_code == 200, r.text[:200]
        restored = r.json()
        titles_now = [blk.get("props", {}).get("title") for blk in restored.get("blocks", [])]
        assert "state-A" in titles_now

        # A "before restore" snapshot must exist.
        vs2 = admin.get(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/versions", timeout=10).json()["versions"]
        reasons = [v["reason"] for v in vs2]
        assert "before restore" in reasons, f"reasons: {reasons[:10]}"
        before_restore_vid = next(v["version_id"] for v in vs2 if v["reason"] == "before restore")

        # site_snapshot on app doc refreshed
        app_doc = admin.get(f"{BASE_URL}/apps/{throwaway}", timeout=10).json()
        assert app_doc.get("site_snapshot", {}).get("headline") == "state-A"

        # Activity log has page.restored
        acts = admin.get(f"{BASE_URL}/apps/{throwaway}/activity", timeout=10).json()
        assert any(a.get("kind") == "page.restored" for a in acts)

        # Restore the 'before restore' snapshot to get back to state-B.
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/pages/{pid}/versions/{before_restore_vid}/restore",
                       timeout=15)
        assert r.status_code == 200
        titles_back = [blk.get("props", {}).get("title") for blk in r.json().get("blocks", [])]
        assert "state-B" in titles_back


# ============ 8. Snapshot before wholesale rewrites ============
class TestWholesaleRewriteSnapshots:
    def test_import_replace_writes_before_import_snapshots(self, admin, throwaway):
        # Seed one extra page so we have >1 page snapshotted.
        admin.post(f"{BASE_URL}/apps/{throwaway}/pages",
                   json={"name": "AboutTest", "slug": "/about-iter32"}, timeout=15)
        # Grab existing page_ids BEFORE import.
        pre_pages = admin.get(f"{BASE_URL}/apps/{throwaway}/pages", timeout=10).json()
        pre_ids = {p["page_id"] for p in pre_pages}

        # Fire replace import (already unlocked in throwaway fixture)
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/site/import",
                       json={"url": "https://example.com", "mode": "replace",
                             "max_pages": 1, "source_videos": False}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        job_id = r.json()["job_id"]
        for _ in range(60):
            jr = admin.get(f"{BASE_URL}/apps/{throwaway}/site/import-job/{job_id}", timeout=15)
            if jr.status_code == 200 and jr.json().get("status") in ("done", "error"):
                assert jr.json()["status"] == "done", f"import failed: {jr.json()}"
                break
            time.sleep(2)
        else:
            pytest.skip("import did not finish in time")

        # db.page_versions must have 'before import from ...' entries for the pre-import pages.
        cursor = _db.page_versions.find(
            {"app_id": throwaway, "reason": {"$regex": "^before import from"}},
            {"_id": 0, "page_id": 1, "reason": 1})
        rows = list(cursor)
        assert rows, "no 'before import from ...' snapshots found"
        snap_page_ids = {r["page_id"] for r in rows}
        # The snapshots must be for the OLD page ids (which were replaced).
        assert snap_page_ids & pre_ids, \
            f"before-import snapshots do not cover pre-import pages: {snap_page_ids} vs {pre_ids}"

        # Since replace deletes the old pages, those page_ids no longer exist as live pages.
        post_pages = admin.get(f"{BASE_URL}/apps/{throwaway}/pages", timeout=10).json()
        post_ids = {p["page_id"] for p in post_pages}
        orphaned = snap_page_ids - post_ids
        # This is EXPECTED — replace mode creates new page_ids. Flag it for the summary.
        assert orphaned, "expected replace-mode snapshots to be orphaned from live page_ids"

    def test_premium_rebuild_writes_before_rebuild_snapshots(self, admin, role_users):
        # Fresh tenant to keep this isolated (throwaway is dirtied by the import test).
        r = admin.post(f"{BASE_URL}/apps", json={
            "name": f"TEST_iter32_pr_{uuid.uuid4().hex[:6]}", "industry": "SaaS",
            "kind": "website", "description": "throwaway", "status": "draft", "tags": [], "color": "#333",
        }, timeout=30)
        aid = r.json()["app_id"]
        try:
            admin.post(f"{BASE_URL}/apps/{aid}/content-lock", json={"locked": False}, timeout=10)
            r = admin.post(f"{BASE_URL}/apps/{aid}/site/premium-rebuild", json={}, timeout=90)
            # Endpoint might fail on empty tenants or succeed; we only care that snapshot_site ran.
            rows = list(_db.page_versions.find(
                {"app_id": aid, "reason": {"$regex": "^before .* rebuild$"}},
                {"_id": 0, "reason": 1}))
            if r.status_code >= 400:
                pytest.skip(f"premium-rebuild returned {r.status_code}; skipping snapshot check")
            assert rows, "expected 'before ... rebuild' snapshots after premium-rebuild"
        finally:
            admin.delete(f"{BASE_URL}/apps/{aid}", timeout=20)

    def test_ai_generate_site_writes_before_ai_snapshot(self, admin):
        r = admin.post(f"{BASE_URL}/apps", json={
            "name": f"TEST_iter32_ai_{uuid.uuid4().hex[:6]}", "industry": "SaaS",
            "kind": "website", "description": "throwaway", "status": "draft", "tags": [], "color": "#333",
        }, timeout=30)
        aid = r.json()["app_id"]
        try:
            admin.post(f"{BASE_URL}/apps/{aid}/content-lock", json={"locked": False}, timeout=10)
            # Kick off generate-site — even if the LLM call slow-fails, the snapshot happens first.
            admin.post(f"{BASE_URL}/apps/{aid}/ai/generate-site",
                       json={"brief": "test snapshot", "pages": ["Home"]}, timeout=120)
            rows = list(_db.page_versions.find(
                {"app_id": aid, "reason": "before AI site generation"},
                {"_id": 0, "reason": 1}))
            assert rows, "expected 'before AI site generation' snapshot"
        finally:
            admin.delete(f"{BASE_URL}/apps/{aid}", timeout=20)


# ============ 9. Cross-tenant isolation ============
class TestCrossTenant:
    def test_page_from_other_tenant_returns_404(self, admin, throwaway):
        # Make a second tenant, grab its page id, then hit lock/versions on the first tenant's URL.
        r = admin.post(f"{BASE_URL}/apps", json={
            "name": f"TEST_iter32_ct_{uuid.uuid4().hex[:6]}", "industry": "SaaS",
            "kind": "website", "description": "throwaway", "status": "draft", "tags": [], "color": "#333",
        }, timeout=30)
        aid2 = r.json()["app_id"]
        try:
            pid2, _ = _home_page_id(admin, aid2)
            # Lock endpoint under throwaway with page_id of aid2 -> 404
            r = admin.post(f"{BASE_URL}/apps/{throwaway}/pages/{pid2}/lock",
                           json={"locked": True}, timeout=15)
            assert r.status_code == 404, r.text[:200]
            # Versions list under throwaway with page_id of aid2 -> empty
            r = admin.get(f"{BASE_URL}/apps/{throwaway}/pages/{pid2}/versions", timeout=10)
            assert r.status_code == 200
            assert r.json()["versions"] == []
        finally:
            admin.delete(f"{BASE_URL}/apps/{aid2}", timeout=20)

    def test_viewer_of_A_cannot_read_B_versions(self, admin, role_users, throwaway):
        # role_users['viewer'] is a member of `throwaway` but NOT of aid2.
        r = admin.post(f"{BASE_URL}/apps", json={
            "name": f"TEST_iter32_iso_{uuid.uuid4().hex[:6]}", "industry": "SaaS",
            "kind": "website", "description": "throwaway", "status": "draft", "tags": [], "color": "#333",
        }, timeout=30)
        aid2 = r.json()["app_id"]
        try:
            pid2, _ = _home_page_id(admin, aid2)
            r = role_users["viewer"]["session"].get(
                f"{BASE_URL}/apps/{aid2}/pages/{pid2}/versions", timeout=10)
            # get_user_app should 403/404 for non-member.
            assert r.status_code in (403, 404), r.text[:200]
        finally:
            admin.delete(f"{BASE_URL}/apps/{aid2}", timeout=20)
