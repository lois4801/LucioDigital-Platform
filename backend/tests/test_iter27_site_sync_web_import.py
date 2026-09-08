"""Iter-27: Site→App AI sync + Website import (scrape/preview/apply)."""
import os
import time
import uuid
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"
SEED_TENANT = "app_bdbf27abe643"  # Vote Banner Test Co (used for read-only + merge tests)


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="session")
def test_tenant(admin_session):
    """A throw-away tenant for destructive tests (import replace, cleanup)."""
    r = admin_session.post(f"{BASE_URL}/apps", json={
        "name": "TEST_iter27_tenant", "industry": "SaaS", "kind": "website",
        "description": "throwaway", "status": "draft", "tags": [], "color": "#333",
    }, timeout=30)
    assert r.status_code == 200, r.text[:200]
    app_id = r.json()["app_id"]
    yield app_id
    # cleanup
    try:
        admin_session.delete(f"{BASE_URL}/apps/{app_id}", timeout=20)
    except Exception:
        pass


@pytest.fixture(scope="session")
def viewer_session(admin_session, test_tenant):
    """Register a fresh user, then have admin invite them as viewer of test_tenant."""
    email = f"TEST_iter27_viewer_{uuid.uuid4().hex[:8]}@example.com"
    pwd = "ViewerPass2026!"
    reg = requests.Session()
    r = reg.post(f"{BASE_URL}/auth/register", json={
        "email": email, "password": pwd, "name": "Test Viewer"
    }, timeout=30)
    assert r.status_code == 200, r.text[:200]
    # invite as viewer
    inv = admin_session.post(f"{BASE_URL}/apps/{test_tenant}/members",
                             json={"email": email, "role": "viewer"}, timeout=20)
    assert inv.status_code == 200, inv.text[:200]
    # log in as viewer with fresh session
    s = requests.Session()
    lr = s.post(f"{BASE_URL}/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert lr.status_code == 200
    return s


# ---------- Site sync GET/POST toggle ----------
class TestSiteSyncToggle:
    def test_get_site_sync_shape(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/apps/{SEED_TENANT}/site-sync", timeout=20)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        for k in ("enabled", "last_sync", "last_summary", "has_spec"):
            assert k in data, f"missing key {k}"
        assert isinstance(data["enabled"], bool)
        assert isinstance(data["has_spec"], bool)

    def test_toggle_persists(self, admin_session):
        # enable
        r1 = admin_session.post(f"{BASE_URL}/apps/{SEED_TENANT}/site-sync",
                                json={"enabled": True}, timeout=20)
        assert r1.status_code == 200 and r1.json()["enabled"] is True
        g1 = admin_session.get(f"{BASE_URL}/apps/{SEED_TENANT}/site-sync", timeout=20)
        assert g1.json()["enabled"] is True
        # disable back
        r2 = admin_session.post(f"{BASE_URL}/apps/{SEED_TENANT}/site-sync",
                                json={"enabled": False}, timeout=20)
        assert r2.status_code == 200 and r2.json()["enabled"] is False
        g2 = admin_session.get(f"{BASE_URL}/apps/{SEED_TENANT}/site-sync", timeout=20)
        assert g2.json()["enabled"] is False


# ---------- website import: invalid URL handling ----------
class TestImportValidation:
    @pytest.mark.parametrize("url", ["not a url", "http://localhost:3000"])
    def test_bad_url_rejected_immediately(self, admin_session, test_tenant, url):
        r = admin_session.post(f"{BASE_URL}/apps/{test_tenant}/site/import-preview",
                               json={"url": url}, timeout=20)
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:200]}"
        assert "detail" in r.json()

    def test_nonexistent_domain_errors_via_job(self, admin_session, test_tenant):
        # nonexistent domain -> _fetch returns None -> scrape_site raises 400 inside the job
        r = admin_session.post(f"{BASE_URL}/apps/{test_tenant}/site/import-preview",
                               json={"url": "https://this-does-not-exist-xyz-9182734.example"}, timeout=20)
        assert r.status_code == 200, r.text[:200]
        job_id = r.json()["job_id"]
        status = None
        for _ in range(24):  # up to 2 min
            time.sleep(5)
            g = admin_session.get(f"{BASE_URL}/apps/{test_tenant}/site/import-job/{job_id}", timeout=20)
            assert g.status_code == 200
            status = g.json().get("status")
            if status in ("done", "error"):
                break
        assert status == "error", f"expected error, got {status}: {g.json()}"
        assert g.json().get("error")


# ---------- permissions ----------
class TestPermissions:
    def test_viewer_forbidden_app_from_site(self, viewer_session, test_tenant):
        r = viewer_session.post(f"{BASE_URL}/apps/{test_tenant}/ai/app-from-site",
                                json={"mode": "merge"}, timeout=30)
        assert r.status_code == 403, f"got {r.status_code}: {r.text[:200]}"

    def test_viewer_forbidden_import_preview(self, viewer_session, test_tenant):
        r = viewer_session.post(f"{BASE_URL}/apps/{test_tenant}/site/import-preview",
                                json={"url": "https://example.com"}, timeout=20)
        assert r.status_code == 403, f"got {r.status_code}: {r.text[:200]}"

    def test_viewer_forbidden_import_apply(self, viewer_session, test_tenant):
        r = viewer_session.post(f"{BASE_URL}/apps/{test_tenant}/site/import-apply",
                                json={"import_id": "imp_fake", "mode": "append", "apply_theme": False}, timeout=20)
        assert r.status_code == 403, f"got {r.status_code}"

    def test_cross_tenant_denied(self, admin_session):
        """A brand-new user with no membership on SEED_TENANT should get 403."""
        email = f"TEST_iter27_outsider_{uuid.uuid4().hex[:8]}@example.com"
        pwd = "Outsider2026!"
        s = requests.Session()
        rr = s.post(f"{BASE_URL}/auth/register", json={"email": email, "password": pwd, "name": "out"}, timeout=20)
        assert rr.status_code == 200
        r = s.get(f"{BASE_URL}/apps/{SEED_TENANT}/site-sync", timeout=20)
        assert r.status_code in (403, 404), f"expected 403/404 got {r.status_code}"


# ---------- Website import full happy path (job + preview + apply append + cleanup) ----------
class TestImportRotoRooter:
    """Uses roto-rooter.com per the ask. Marked slow (up to ~2 min for scrape+LLM)."""

    def test_full_flow_append_and_cleanup(self, admin_session, test_tenant):
        # start job
        r = admin_session.post(f"{BASE_URL}/apps/{test_tenant}/site/import-preview",
                               json={"url": "https://www.roto-rooter.com"}, timeout=25)
        assert r.status_code == 200, r.text[:200]
        job = r.json()
        assert job.get("status") == "running"
        job_id = job["job_id"]

        # poll
        result = None
        for _ in range(30):  # up to ~2.5 min
            time.sleep(5)
            g = admin_session.get(f"{BASE_URL}/apps/{test_tenant}/site/import-job/{job_id}", timeout=20)
            assert g.status_code == 200
            data = g.json()
            if data.get("status") == "done":
                result = data.get("result")
                break
            if data.get("status") == "error":
                pytest.fail(f"job errored: {data.get('error')}")
        assert result, "import job did not finish in time"

        # shape assertions
        assert result.get("import_id", "").startswith("imp_")
        src = result.get("source") or {}
        for k in ("pages", "images", "colors", "phones"):
            assert k in src, f"missing source.{k}"
        biz = result.get("business") or {}
        theme = result.get("theme") or {}
        assert theme.get("primary", "").startswith("#")
        assert theme.get("secondary", "").startswith("#")
        pages = result.get("pages") or []
        assert 3 <= len(pages) <= 6, f"expected 3-5 pages, got {len(pages)}"
        for p in pages:
            assert p.get("slug"), "page missing slug"
            assert p.get("blocks", 0) >= 5, f"page {p.get('slug')} has {p.get('blocks')} blocks (<5)"

        # apply append (no theme change) — test_tenant already has a Home page from seed
        existing_before = admin_session.get(f"{BASE_URL}/apps/{test_tenant}/pages", timeout=20).json()
        before_ids = {p["page_id"] for p in existing_before}
        ap = admin_session.post(f"{BASE_URL}/apps/{test_tenant}/site/import-apply",
                                json={"import_id": result["import_id"], "mode": "append", "apply_theme": False},
                                timeout=30)
        assert ap.status_code == 200, ap.text[:200]
        applied = ap.json()
        assert len(applied.get("pages", [])) >= 3

        # verify pages persisted, existing pages preserved, and slug collision handled (imported- prefix)
        after = admin_session.get(f"{BASE_URL}/apps/{test_tenant}/pages", timeout=20).json()
        after_ids = {p["page_id"] for p in after}
        assert before_ids.issubset(after_ids), "existing pages were deleted on append!"
        new_pages = [p for p in after if p["page_id"] not in before_ids]
        assert len(new_pages) >= 3
        # root slug '/' should have been remapped since it already exists
        root_collisions = [p for p in new_pages if p["slug"] == "/"]
        assert not root_collisions, "append should not create duplicate '/' slug"
        assert any(p["slug"].startswith("/imported-") for p in new_pages), \
            "expected at least one imported- prefixed slug for collision"

        # theme should NOT have changed (apply_theme=false)
        app_doc = admin_session.get(f"{BASE_URL}/apps/{test_tenant}", timeout=20).json()
        # we can't easily know the pre-theme, but ensure imported_from was recorded
        assert app_doc.get("imported_from") == "https://www.roto-rooter.com" or \
            app_doc.get("imported_from", "").startswith("https://www.roto-rooter.com")

        # cleanup: delete the appended pages
        for p in new_pages:
            admin_session.delete(f"{BASE_URL}/apps/{test_tenant}/pages/{p['page_id']}", timeout=20)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
