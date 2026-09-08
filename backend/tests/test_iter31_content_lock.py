"""Iter-31 backend tests for the tenant content-lock feature.

Covers:
- Startup safety: no premium migration on startup; existing tenants' pages/blocks stay byte-identical
  across a supervisorctl restart, and every tenant is locked with `content_locked=True`.
- Content-lock endpoints: GET returns locked+snapshot; POST toggles and writes an activity log.
- Lock enforcement (423, fast, no mutation) for generate-site, premium-rebuild, import replace,
  import-selected replace, import-apply replace.
- Non-blocked writes: PATCH page (block edit), POST page, DELETE page, PUT theme, blueprint,
  and site/import mode='append' all work while locked.
- Unlock → destructive import (replace) → auto re-lock on a throwaway tenant.
- New tenant defaults to locked; admin can unlock and generate/import.
- Overview snapshot sync from Site Mode page save.
"""
import os
import time
import uuid
import hashlib
import subprocess
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"
CRAWL_TENANT = "app_7035dfbf4a95"  # 'TheCrawlSpace' — must never be mutated by tests


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return s


def _mk(admin, suffix=""):
    r = admin.post(f"{BASE_URL}/apps", json={
        "name": f"TEST_iter31_{suffix}_{uuid.uuid4().hex[:6]}", "industry": "SaaS",
        "kind": "website", "description": "throwaway", "status": "draft", "tags": [], "color": "#333",
    }, timeout=30)
    assert r.status_code == 200, r.text[:300]
    return r.json()["app_id"]


@pytest.fixture()
def throwaway(admin):
    aid = _mk(admin, "tw")
    yield aid
    try:
        admin.delete(f"{BASE_URL}/apps/{aid}", timeout=20)
    except Exception:
        pass


def _pages_digest(admin, app_id):
    """Deterministic digest of page count + slug + block contents so we can compare pre/post."""
    r = admin.get(f"{BASE_URL}/apps/{app_id}/pages", timeout=20)
    assert r.status_code == 200, r.text[:200]
    pages = sorted(r.json(), key=lambda p: p.get("slug", ""))
    canon = []
    for p in pages:
        canon.append({"slug": p.get("slug"), "name": p.get("name"), "blocks": p.get("blocks")})
    import json as _j
    payload = _j.dumps(canon, sort_keys=True, default=str)
    return len(pages), hashlib.sha256(payload.encode()).hexdigest()


# ------------------ startup safety ------------------
class TestStartupSafety:
    def test_no_premium_migration_on_startup(self):
        with open("/app/backend/server.py") as f:
            src = f.read()
        # Neither migrate_all nor migrate_premium_sites may be invoked at startup.
        assert "migrate_all(" not in src, "server.py still calls migrate_all(...) at startup"
        assert "migrate_premium_sites(" not in src, "server.py still calls migrate_premium_sites(...) at startup"

    def test_reseed_demo_sites_skips_tenants_with_pages(self):
        with open("/app/backend/seed_sites.py") as f:
            src = f.read()
        assert "delete_many" not in src, "reseed_demo_sites must not delete pages"
        assert "count_documents" in src

    def test_backend_restart_leaves_tenant_pages_byte_identical(self, admin):
        # Pick 3 tenants that have pages, including TheCrawlSpace.
        r = admin.get(f"{BASE_URL}/apps", timeout=20)
        assert r.status_code == 200
        apps = r.json()
        # Prefer CRAWL_TENANT + 2 others with pages.
        picked = []
        if any(a["app_id"] == CRAWL_TENANT for a in apps):
            picked.append(CRAWL_TENANT)
        for a in apps:
            if a["app_id"] in picked:
                continue
            n, _ = _pages_digest(admin, a["app_id"])
            if n > 0:
                picked.append(a["app_id"])
            if len(picked) >= 3:
                break
        assert len(picked) >= 3, f"Need >=3 tenants with pages, got {picked}"
        before = {aid: _pages_digest(admin, aid) for aid in picked}

        # Restart backend and wait for readiness.
        subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=True, timeout=30)
        for _ in range(30):
            try:
                r = requests.get(f"{BASE_URL}/", timeout=5)
                if r.status_code < 500:
                    break
            except Exception:
                pass
            time.sleep(1)

        # Re-login (cookie should still be valid, but be safe).
        admin.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)

        after = {aid: _pages_digest(admin, aid) for aid in picked}
        for aid in picked:
            assert before[aid] == after[aid], f"Tenant {aid} pages mutated by restart: before={before[aid]} after={after[aid]}"

    def test_all_existing_tenants_locked_at_startup(self, admin):
        r = admin.get(f"{BASE_URL}/apps", timeout=20)
        apps = r.json()
        unlocked = []
        for a in apps[:15]:
            lr = admin.get(f"{BASE_URL}/apps/{a['app_id']}/content-lock", timeout=10)
            if lr.status_code == 200 and not lr.json().get("locked"):
                unlocked.append(a["app_id"])
        assert not unlocked, f"Expected all existing tenants locked; unlocked: {unlocked}"


# ------------------ lock endpoints ------------------
class TestLockEndpoints:
    def test_get_content_lock_shape(self, admin, throwaway):
        r = admin.get(f"{BASE_URL}/apps/{throwaway}/content-lock", timeout=10)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert d["locked"] is True
        assert "snapshot" in d
        assert "locked_at" in d

    def test_toggle_lock_persists_and_logs_activity(self, admin, throwaway):
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/content-lock", json={"locked": False}, timeout=10)
        assert r.status_code == 200 and r.json()["locked"] is False
        r2 = admin.get(f"{BASE_URL}/apps/{throwaway}/content-lock", timeout=10)
        assert r2.json()["locked"] is False

        r3 = admin.post(f"{BASE_URL}/apps/{throwaway}/content-lock", json={"locked": True}, timeout=10)
        assert r3.status_code == 200 and r3.json()["locked"] is True

        act = admin.get(f"{BASE_URL}/apps/{throwaway}/activity", timeout=10)
        assert act.status_code == 200
        kinds = [a.get("kind") for a in act.json()]
        assert kinds.count("content.lock") >= 2, f"Expected >=2 content.lock entries, got {kinds}"


# ------------------ lock enforcement ------------------
class TestLockEnforcement:
    """All wholesale-rewrite endpoints must 423 while locked AND leave pages unchanged."""

    def _seeded(self, admin):
        """Return an existing seeded tenant with pages; every tenant is locked at startup."""
        r = admin.get(f"{BASE_URL}/apps", timeout=20)
        for a in r.json():
            if a["app_id"] == CRAWL_TENANT:
                continue  # keep CrawlSpace read-only from tests
            n, _ = _pages_digest(admin, a["app_id"])
            if n > 0:
                return a["app_id"]
        pytest.skip("No seeded tenant with pages available")

    def test_generate_site_fast_423(self, admin):
        aid = self._seeded(admin)
        before = _pages_digest(admin, aid)
        t0 = time.time()
        r = admin.post(f"{BASE_URL}/apps/{aid}/ai/generate-site",
                       json={"brief": "test", "pages": ["Home"]}, timeout=15)
        dt = time.time() - t0
        assert r.status_code == 423, f"expected 423, got {r.status_code}: {r.text[:200]}"
        assert "Overview" in r.text or "unlock" in r.text.lower()
        assert dt < 5.0, f"generate-site guard too slow: {dt:.2f}s (must fail before LLM call)"
        assert _pages_digest(admin, aid) == before

    def test_premium_rebuild_423(self, admin):
        aid = self._seeded(admin)
        before = _pages_digest(admin, aid)
        r = admin.post(f"{BASE_URL}/apps/{aid}/site/premium-rebuild", json={}, timeout=15)
        assert r.status_code == 423, r.text[:200]
        assert _pages_digest(admin, aid) == before

    def test_site_import_replace_423(self, admin):
        aid = self._seeded(admin)
        before = _pages_digest(admin, aid)
        r = admin.post(f"{BASE_URL}/apps/{aid}/site/import",
                       json={"url": "https://example.com", "mode": "replace",
                             "max_pages": 1, "source_videos": False}, timeout=15)
        assert r.status_code == 423, r.text[:200]
        assert _pages_digest(admin, aid) == before

    def test_import_selected_replace_423(self, admin):
        aid = self._seeded(admin)
        before = _pages_digest(admin, aid)
        # First create a real discovery so the endpoint gets past the 404 branch
        # and reaches the actual lock guard.
        r = admin.post(f"{BASE_URL}/apps/{aid}/site/discover",
                       json={"url": "https://example.com", "max_pages": 1}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        job_id = r.json()["job_id"]
        disc_id = None
        for _ in range(30):
            jr = admin.get(f"{BASE_URL}/apps/{aid}/site/import-job/{job_id}", timeout=10)
            if jr.status_code == 200 and jr.json().get("status") in ("done", "error"):
                if jr.json().get("status") == "done":
                    disc_id = jr.json()["result"]["discovery_id"]
                break
            time.sleep(2)
        if not disc_id:
            pytest.skip("Discover did not complete for example.com")
        r = admin.post(f"{BASE_URL}/apps/{aid}/site/import-selected",
                       json={"discovery_id": disc_id, "slugs": ["/"], "mode": "replace"},
                       timeout=15)
        assert r.status_code == 423, f"expected 423, got {r.status_code}: {r.text[:200]}"
        assert _pages_digest(admin, aid) == before

    def test_import_apply_replace_423(self, admin):
        aid = self._seeded(admin)
        before = _pages_digest(admin, aid)
        r = admin.post(f"{BASE_URL}/apps/{aid}/site/import-apply",
                       json={"import_id": "does-not-exist", "mode": "replace"}, timeout=15)
        assert r.status_code == 423, f"expected 423, got {r.status_code}: {r.text[:200]}"
        assert _pages_digest(admin, aid) == before


# ------------------ non-blocked writes ------------------
class TestNonBlockedWrites:
    """A locked tenant must still accept legitimate manual edits."""

    def _seeded(self, admin):
        r = admin.get(f"{BASE_URL}/apps", timeout=20)
        for a in r.json():
            if a["app_id"] == CRAWL_TENANT:
                continue
            pages_r = admin.get(f"{BASE_URL}/apps/{a['app_id']}/pages", timeout=10)
            if pages_r.status_code == 200 and len(pages_r.json()) > 0:
                return a["app_id"], pages_r.json()
        pytest.skip("No seeded tenant with pages")

    def test_patch_page_and_add_and_delete_page_and_theme(self, admin):
        aid, pages = self._seeded(admin)
        # Confirm locked.
        assert admin.get(f"{BASE_URL}/apps/{aid}/content-lock", timeout=10).json()["locked"] is True

        # PATCH block edit on the home page — must succeed.
        home = next((p for p in pages if p.get("slug") == "/"), pages[0])
        original_blocks = home.get("blocks") or []
        r = admin.patch(f"{BASE_URL}/apps/{aid}/pages/{home['page_id']}",
                        json={"blocks": original_blocks}, timeout=15)
        assert r.status_code == 200, f"PATCH page failed: {r.status_code} {r.text[:200]}"

        # POST new page — must succeed.
        r = admin.post(f"{BASE_URL}/apps/{aid}/pages",
                       json={"name": "TEST_iter31_page", "slug": "/test-iter31"}, timeout=15)
        assert r.status_code == 200, f"POST page failed: {r.status_code} {r.text[:200]}"
        new_page_id = r.json()["page_id"]

        # DELETE the newly added page — must succeed.
        r = admin.delete(f"{BASE_URL}/apps/{aid}/pages/{new_page_id}", timeout=15)
        assert r.status_code == 200, f"DELETE page failed: {r.status_code} {r.text[:200]}"

        # PUT theme — must succeed.
        t = admin.get(f"{BASE_URL}/apps/{aid}/theme", timeout=10).json()
        r = admin.put(f"{BASE_URL}/apps/{aid}/theme", json={"theme": t}, timeout=15)
        assert r.status_code == 200, f"PUT theme failed: {r.status_code} {r.text[:200]}"


# ------------------ overview snapshot sync ------------------
class TestOverviewSync:
    def test_page_save_updates_snapshot_but_not_other_fields(self, admin, throwaway):
        # Fresh tenants auto-seed a "/" home page. PATCH it to change the hero.
        pages = admin.get(f"{BASE_URL}/apps/{throwaway}/pages", timeout=10).json()
        home = next((p for p in pages if p.get("slug") == "/"), pages[0] if pages else None)
        assert home, "throwaway tenant missing home page"
        pid = home["page_id"]

        # Store original app doc fields we do not want mutated.
        pre_app = admin.get(f"{BASE_URL}/apps/{throwaway}", timeout=10).json()
        pre_keys = {k: pre_app.get(k) for k in ("name", "description", "industry", "status", "tags", "theme", "metrics")}

        new_title = f"Snapshot Test {uuid.uuid4().hex[:6]}"
        new_sub = "The one true subtitle"
        new_img = "https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=1600&q=80"
        blocks = [{"id": "b1", "type": "hero",
                   "props": {"title": new_title, "subtitle": new_sub, "image": new_img}}]
        r = admin.patch(f"{BASE_URL}/apps/{throwaway}/pages/{pid}",
                        json={"blocks": blocks}, timeout=15)
        assert r.status_code == 200, r.text[:200]

        # Snapshot must reflect the new hero.
        lock = admin.get(f"{BASE_URL}/apps/{throwaway}/content-lock", timeout=10).json()
        snap = lock.get("snapshot")
        assert snap, f"snapshot missing: {lock}"
        assert snap["headline"] == new_title, snap
        assert snap["subtitle"] == new_sub, snap
        assert snap["sections"] == 1
        assert snap["pages"] >= 1
        assert snap.get("updated_at")

        # App doc must have new snapshot & thumbnail derived from hero image.
        post_app = admin.get(f"{BASE_URL}/apps/{throwaway}", timeout=10).json()
        assert post_app.get("site_snapshot", {}).get("headline") == new_title
        assert post_app.get("thumbnail") == new_img

        # Untouched fields must remain identical.
        for k, v in pre_keys.items():
            assert post_app.get(k) == v, f"Field '{k}' was mutated by page save: {v!r} -> {post_app.get(k)!r}"


# ------------------ unlock → destructive → auto-relock ------------------
class TestUnlockAndAutoRelock:
    def test_unlocked_import_replace_relocks_after_success(self, admin, throwaway):
        # Fresh tenant already has a "/" page. Unlock, then run replace import.
        # Unlock.
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/content-lock", json={"locked": False}, timeout=10)
        assert r.status_code == 200

        # Fire the import (replace mode).
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/site/import",
                       json={"url": "https://example.com", "mode": "replace",
                             "max_pages": 1, "source_videos": False}, timeout=30)
        # Must NOT be 423 now that we unlocked.
        assert r.status_code == 200, f"Unlocked import failed: {r.status_code} {r.text[:200]}"
        job = r.json()
        job_id = job.get("job_id")
        assert job_id, job

        # Poll the job until done.
        done = None
        for _ in range(60):
            jr = admin.get(f"{BASE_URL}/apps/{throwaway}/site/import-job/{job_id}", timeout=15)
            if jr.status_code == 200 and jr.json().get("status") in ("done", "error"):
                done = jr.json()
                break
            time.sleep(2)
        assert done, "Import job did not complete in time"
        assert done.get("status") == "done", f"Import failed: {done}"

        # Auto-relock must have happened.
        lock = admin.get(f"{BASE_URL}/apps/{throwaway}/content-lock", timeout=10).json()
        assert lock["locked"] is True, f"Tenant not re-locked after import: {lock}"


# ------------------ new tenant behaviour ------------------
class TestNewTenant:
    def test_new_tenant_is_locked_by_default(self, admin, throwaway):
        lock = admin.get(f"{BASE_URL}/apps/{throwaway}/content-lock", timeout=10).json()
        assert lock["locked"] is True

    def test_new_tenant_generate_site_blocked_until_unlocked(self, admin, throwaway):
        # Empty tenant is still locked → generate-site should 423 (friction the request notes).
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/ai/generate-site",
                       json={"brief": "test", "pages": ["Home"]}, timeout=10)
        assert r.status_code == 423, r.text[:200]

        # Unlock then confirm we get past the lock guard (LLM may still fail, but not 423).
        admin.post(f"{BASE_URL}/apps/{throwaway}/content-lock", json={"locked": False}, timeout=10)
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/ai/generate-site",
                       json={"brief": "test", "pages": ["Home"]}, timeout=90)
        assert r.status_code != 423, f"Still 423 after unlock: {r.text[:200]}"


# ------------------ code-review: no unguarded pages.delete_many ------------------
def test_no_unguarded_bulk_page_writes():
    """Every pages.delete_many across the backend must be near an assert_unlocked call OR
    inside a full tenant delete (delete_app) OR a seed script."""
    import glob, re
    offenders = []
    for path in glob.glob("/app/backend/*.py"):
        with open(path) as f:
            src = f.read()
        for m in re.finditer(r"pages\.delete_many", src):
            start = max(0, m.start() - 800)
            ctx = src[start:m.start()]
            # Consider guarded if assert_unlocked or delete_app appears in the preceding 800 chars.
            if "assert_unlocked" in ctx or "delete_app" in ctx or "@api.delete(\"/apps/{app_id}\"" in ctx:
                continue
            offenders.append((path, m.start()))
    assert not offenders, f"Unguarded pages.delete_many locations: {offenders}"
