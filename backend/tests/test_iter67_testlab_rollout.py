"""Iteration 67 — Test Lab + rollout gap tests.

Focus (per main-agent note): 403 for non-admin, pending badge state, snapshot writing,
rollout does NOT mutate tenant pages/name/description/leads, protection endpoints.

Safety: this test MUST NOT delete or rename any tenant it did not create. It reuses the
existing target `app_03efdf8b1af4` (Rollout Target Demo) as a rollout target and never
purges it. `app_testlab` is never touched.
"""
import os
import time
import copy
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
EDITOR = {"email": "client.editor@example.com", "password": "ClientEdit2026!"}
TEST_LAB_ID = "app_testlab"
KNOWN_TARGET = "app_03efdf8b1af4"


def _login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def editor():
    return _login(EDITOR)


# ---------- Test Lab exists + 32 pages + protection ----------
class TestLabTenant:
    def test_get_test_lab(self, admin):
        r = admin.get(f"{API}/test-lab", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        app = data["app"]
        assert app["app_id"] == TEST_LAB_ID
        assert app["name"] == "LucioDigital Test Lab"
        assert app.get("is_test_lab") is True
        assert app.get("protected") is True
        assert app.get("archived") is False
        assert data["template_pages"] == 32, f"expected 32 preloaded template pages, got {data['template_pages']}"
        assert data["is_rollout_admin"] is True
        assert len(data["scopes"]) == 6
        scope_keys = {s["key"] for s in data["scopes"]}
        assert scope_keys == {"theme", "mode", "skin", "motion", "labels", "forms"}

    def test_archive_blocked(self, admin):
        r = admin.post(f"{API}/apps/{TEST_LAB_ID}/archive", json={"archived": True}, timeout=15)
        assert r.status_code == 400, f"archive should be blocked, got {r.status_code} {r.text}"

    def test_purge_blocked(self, admin):
        r = admin.delete(f"{API}/apps/{TEST_LAB_ID}/purge", timeout=15)
        assert r.status_code == 400, f"purge should be blocked, got {r.status_code} {r.text}"

    def test_delete_blocked(self, admin):
        r = admin.delete(f"{API}/apps/{TEST_LAB_ID}", timeout=15)
        assert r.status_code == 400, f"delete should be blocked, got {r.status_code} {r.text}"


# ---------- 403 for non-admin ----------
class TestNonAdmin403:
    def test_rollout_forbidden_for_editor(self, editor):
        r = editor.post(f"{API}/test-lab/rollout",
                        json={"scopes": ["theme"], "confirm": "CONFIRM"}, timeout=15)
        assert r.status_code == 403, f"editor must get 403 on test-lab rollout, got {r.status_code} {r.text}"

    def test_template_rollout_forbidden_for_editor(self, editor):
        # pick any template key that exists
        r = editor.post(f"{API}/templates/saas/rollout",
                        json={"scopes": [], "confirm": "CONFIRM"}, timeout=15)
        assert r.status_code == 403, f"editor must get 403 on template rollout, got {r.status_code} {r.text}"


# ---------- Rollout API validation ----------
class TestRolloutValidation:
    def test_wrong_confirm(self, admin):
        r = admin.post(f"{API}/test-lab/rollout",
                       json={"scopes": ["theme"], "confirm": "yes"}, timeout=15)
        assert r.status_code == 400

    def test_no_scopes(self, admin):
        r = admin.post(f"{API}/test-lab/rollout",
                       json={"scopes": [], "confirm": "CONFIRM"}, timeout=15)
        assert r.status_code == 400


# ---------- Full rollout: verify snapshots + tenant content untouched ----------
class TestRolloutIntegrity:
    def test_rollout_theme_applies_and_content_unchanged(self, admin):
        # Capture BEFORE state of a known target: name, description, pages, leads count
        before_app = admin.get(f"{API}/apps/{KNOWN_TARGET}", timeout=15)
        assert before_app.status_code == 200, before_app.text
        b_app = before_app.json()
        b_name = b_app.get("name")
        b_desc = b_app.get("description")

        before_pages = admin.get(f"{API}/apps/{KNOWN_TARGET}/pages", timeout=15)
        assert before_pages.status_code == 200
        b_pages = before_pages.json()
        b_pages_sig = [(p.get("page_id"), p.get("name"), p.get("slug"), len(p.get("blocks") or [])) for p in b_pages]

        # Leads count (endpoint may be /api/apps/{id}/leads)
        before_leads = admin.get(f"{API}/apps/{KNOWN_TARGET}/leads", timeout=15)
        b_leads_count = None
        if before_leads.status_code == 200:
            try:
                jd = before_leads.json()
                b_leads_count = len(jd if isinstance(jd, list) else jd.get("leads", []))
            except Exception:
                b_leads_count = None

        # Lab theme
        lab = admin.get(f"{API}/apps/{TEST_LAB_ID}", timeout=15).json()
        lab_theme = lab.get("theme") or {}

        # Kick off rollout with theme+mode scopes
        r = admin.post(f"{API}/test-lab/rollout",
                       json={"scopes": ["theme", "mode"], "confirm": "CONFIRM"}, timeout=20)
        assert r.status_code == 200, r.text
        job = r.json()
        job_id = job["job_id"]
        assert job["status"] == "running"

        # Poll job to done
        deadline = time.time() + 30
        final = None
        while time.time() < deadline:
            jr = admin.get(f"{API}/test-lab/rollout/jobs/{job_id}", timeout=10)
            assert jr.status_code == 200
            final = jr.json()
            if final.get("status") == "done":
                break
            time.sleep(0.5)
        assert final and final.get("status") == "done", f"job did not finish: {final}"
        assert final.get("pct") == 100

        # Verify tenant theme now matches lab on theme keys
        after_app = admin.get(f"{API}/apps/{KNOWN_TARGET}", timeout=15).json()
        after_theme = after_app.get("theme") or {}
        for k in ("primary", "secondary", "bg", "fg"):
            if k in lab_theme:
                assert after_theme.get(k) == lab_theme[k], f"theme.{k} not rolled out"

        # Content should be untouched
        assert after_app.get("name") == b_name, "tenant NAME was mutated by rollout"
        assert after_app.get("description") == b_desc, "tenant DESCRIPTION was mutated by rollout"

        after_pages = admin.get(f"{API}/apps/{KNOWN_TARGET}/pages", timeout=15).json()
        a_pages_sig = [(p.get("page_id"), p.get("name"), p.get("slug"), len(p.get("blocks") or [])) for p in after_pages]
        assert a_pages_sig == b_pages_sig, "tenant PAGES changed after rollout"

        if b_leads_count is not None:
            after_leads = admin.get(f"{API}/apps/{KNOWN_TARGET}/leads", timeout=15).json()
            a_leads_count = len(after_leads if isinstance(after_leads, list) else after_leads.get("leads", []))
            assert a_leads_count == b_leads_count, "leads count changed after rollout"

        # Snapshot check via a dedicated endpoint or via jobs collection: use jobs list
        jobs = admin.get(f"{API}/test-lab/rollout/jobs", timeout=10).json()
        assert any(j["job_id"] == job_id for j in jobs.get("jobs", []))


# ---------- Template rollout status + pending badge ----------
class TestTemplateRollout:
    def test_rollout_status_has_32(self, admin):
        r = admin.get(f"{API}/templates/rollout-status", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert len(data["templates"]) == 32
        for t in data["templates"]:
            assert "key" in t and "status" in t and "tenants_using" in t

    def test_template_rollout_wrong_confirm(self, admin):
        r = admin.post(f"{API}/templates/saas/rollout",
                       json={"scopes": [], "confirm": "wrong"}, timeout=10)
        assert r.status_code == 400

    def test_template_rollout_unknown_key(self, admin):
        r = admin.post(f"{API}/templates/nonexistent_key_zzz/rollout",
                       json={"scopes": [], "confirm": "CONFIRM"}, timeout=10)
        assert r.status_code == 404

    def test_template_discard_sets_live(self, admin):
        r = admin.post(f"{API}/templates/saas/discard", timeout=10)
        assert r.status_code == 200
        assert r.json()["status"] == "live"


# ---------- Rollout admins CRUD ----------
class TestRolloutAdmins:
    TEST_EMAIL = "TEST_iter67_extra_admin@example.com"

    def test_list_admins(self, admin):
        r = admin.get(f"{API}/rollout-admins", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["owner"] == "jaybernabe@luciodigital.com"
        assert d["is_rollout_admin"] is True

    def test_add_and_remove_admin(self, admin):
        r = admin.post(f"{API}/rollout-admins", json={"email": self.TEST_EMAIL}, timeout=10)
        assert r.status_code == 200
        assert self.TEST_EMAIL.lower() in r.json()["extra"]

        r = admin.delete(f"{API}/rollout-admins/{self.TEST_EMAIL}", timeout=10)
        assert r.status_code == 200
        assert self.TEST_EMAIL.lower() not in r.json()["extra"]

    def test_add_invalid_email(self, admin):
        r = admin.post(f"{API}/rollout-admins", json={"email": "not-an-email"}, timeout=10)
        assert r.status_code == 400
