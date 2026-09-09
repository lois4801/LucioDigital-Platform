"""Iteration 68 — Diff viewer + Rollout history + Undo.

Scope (per review request):
  - GET /api/test-lab/diff — aggregated diff with all fields; empty when nothing differs.
  - POST /api/test-lab/rollout with `changes:[...]` applies only picked change ids.
  - GET /api/test-lab/rollout/history — newest first, exactly one can_undo=true.
  - POST /api/test-lab/rollout/jobs/{job_id}/undo — validation + restore.
  - Template rollout writes a history job doc with kind='template'.
  - Regression: tenant content (name, description, pages, leads) never mutated.

Safety: never delete/rename existing tenants. Uses app_testlab (theme mutations only) and
app_03efdf8b1af4 as rollout target.
"""
import os
import time
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
EDITOR = {"email": "client.editor@example.com", "password": "ClientEdit2026!"}

TEST_LAB_ID = "app_testlab"
TARGET_ID = "app_03efdf8b1af4"


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


def _poll_job(admin, job_id, key="status", target="done", timeout=45):
    deadline = time.time() + timeout
    final = None
    while time.time() < deadline:
        r = admin.get(f"{API}/test-lab/rollout/jobs/{job_id}", timeout=10)
        if r.status_code == 200:
            final = r.json()
            if final.get(key) == target:
                return final
        time.sleep(0.5)
    return final


def _force_theme_diff(admin, primary="#ff00aa", secondary="#00ff88", cursor_effect="sparkles"):
    """Mutate the TARGET tenant's theme (via PUT /apps/{id}/theme) so that it differs from the
    Test Lab. We do NOT modify the Test Lab because the backend re-themes it on restart."""
    r = admin.get(f"{API}/apps/{TARGET_ID}/theme", timeout=10)
    assert r.status_code == 200, r.text
    theme = dict(r.json() or {})
    theme["primary"] = primary
    theme["secondary"] = secondary
    r = admin.put(f"{API}/apps/{TARGET_ID}/theme", json={"theme": theme}, timeout=10)
    assert r.status_code == 200, f"seed theme failed: {r.status_code} {r.text}"
    # cursor_effect lives on the app doc directly — try a couple of common endpoints
    for path, method in [(f"{API}/apps/{TARGET_ID}", "patch"),
                         (f"{API}/apps/{TARGET_ID}/settings", "put")]:
        try:
            rr = getattr(admin, method)(path, json={"cursor_effect": cursor_effect}, timeout=10)
            if rr.status_code < 400:
                break
        except Exception:
            pass


# ---------- GET /test-lab/diff ----------
class TestDiff:
    def test_diff_shape(self, admin):
        _force_theme_diff(admin)
        r = admin.get(f"{API}/test-lab/diff", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "changes" in data and "by_category" in data
        assert data["target_count"] >= 1
        # Must have at least one changed field (primary at minimum)
        assert data["total"] >= 1, f"expected diff rows, got {data}"
        # Verify row structure
        row = data["changes"][0]
        for key in ("id", "category", "label", "old", "new", "kind", "tenants", "variance"):
            assert key in row, f"row missing {key}: {row}"
        # Each id appears exactly once
        ids = [r["id"] for r in data["changes"]]
        assert len(ids) == len(set(ids)), "diff rows contain duplicate ids"

    def test_diff_categories_valid(self, admin):
        r = admin.get(f"{API}/test-lab/diff", timeout=15)
        assert r.status_code == 200
        data = r.json()
        for row in data["changes"]:
            assert row["category"] in ("Design", "Animations", "Content", "Features", "Forms"), row


# ---------- POST /test-lab/rollout with changes ----------
class TestChangesRollout:
    def test_wrong_confirm(self, admin):
        r = admin.post(f"{API}/test-lab/rollout",
                       json={"changes": ["design.primary"], "confirm": "yes"}, timeout=10)
        assert r.status_code == 400

    def test_empty_changes_400(self, admin):
        # After seeding diff, providing no picks should fail
        _force_theme_diff(admin)
        r = admin.post(f"{API}/test-lab/rollout",
                       json={"changes": [], "confirm": "CONFIRM"}, timeout=10)
        # Empty list falls back through scopes path → "Choose at least one thing"
        assert r.status_code == 400, r.text

    def test_invalid_change_ids_400(self, admin):
        _force_theme_diff(admin)
        r = admin.post(f"{API}/test-lab/rollout",
                       json={"changes": ["design.doesnotexist", "bogus.thing"], "confirm": "CONFIRM"}, timeout=15)
        assert r.status_code == 400, r.text

    def test_non_admin_forbidden(self, editor):
        r = editor.post(f"{API}/test-lab/rollout",
                        json={"changes": ["design.primary"], "confirm": "CONFIRM"}, timeout=10)
        assert r.status_code == 403

    def test_partial_rollout_only_touches_picked_fields(self, admin):
        # Seed a diff on TWO fields (primary + secondary)
        _force_theme_diff(admin, primary="#123456", secondary="#654321")

        # Capture the target's secondary BEFORE the rollout
        before = admin.get(f"{API}/apps/{TARGET_ID}", timeout=10).json()
        b_theme = before.get("theme") or {}
        b_secondary = b_theme.get("secondary")
        b_name = before.get("name")
        b_desc = before.get("description")

        # Roll out only design.primary
        r = admin.post(f"{API}/test-lab/rollout",
                       json={"changes": ["design.primary"], "confirm": "CONFIRM"}, timeout=15)
        assert r.status_code == 200, r.text
        job = r.json()
        assert job["changes"] == ["design.primary"]
        assert "diff" in job and job["diff"]["total"] == 1
        assert "Design" in job["categories"]
        final = _poll_job(admin, job["job_id"])
        assert final and final["status"] == "done", f"job did not finish: {final}"

        # After: primary should now match the lab; secondary should be UNCHANGED
        lab = admin.get(f"{API}/apps/{TEST_LAB_ID}", timeout=10).json()
        after = admin.get(f"{API}/apps/{TARGET_ID}", timeout=10).json()
        a_theme = after.get("theme") or {}
        assert a_theme.get("primary") == (lab.get("theme") or {}).get("primary"), "primary not rolled out"
        assert a_theme.get("secondary") == b_secondary, "secondary was mutated but was NOT selected"
        # Content invariance
        assert after.get("name") == b_name
        assert after.get("description") == b_desc

    def test_legacy_scopes_still_works(self, admin):
        _force_theme_diff(admin, primary="#aabbcc")
        r = admin.post(f"{API}/test-lab/rollout",
                       json={"scopes": ["theme"], "confirm": "CONFIRM"}, timeout=15)
        assert r.status_code == 200, r.text
        job = r.json()
        assert job["status"] in ("running", "done")
        final = _poll_job(admin, job["job_id"])
        assert final and final["status"] == "done"


# ---------- GET /test-lab/rollout/history ----------
class TestHistory:
    def test_history_shape_and_single_undoable(self, admin):
        r = admin.get(f"{API}/test-lab/rollout/history", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        entries = data["entries"]
        assert len(entries) >= 1
        # newest first — created_at descending
        created = [e.get("created_at") for e in entries]
        assert created == sorted(created, reverse=True), "history not newest-first"
        # required fields on each entry
        for e in entries:
            assert "job_id" in e and "status" in e
            # by_email + categories may be missing on legacy jobs from earlier iterations
            # diff may be missing on very old jobs — accept but note
        # exactly ONE can_undo=True
        undoable = [e for e in entries if e.get("can_undo")]
        assert len(undoable) == 1, f"expected exactly 1 undoable entry, got {len(undoable)}"
        # and it must be the newest completed
        assert undoable[0]["status"] in ("done", "partial")
        assert not undoable[0].get("undone_at")

    def test_history_admin_flag(self, admin, editor):
        r = admin.get(f"{API}/test-lab/rollout/history", timeout=10)
        assert r.status_code == 200
        assert r.json()["is_rollout_admin"] is True

        r = editor.get(f"{API}/test-lab/rollout/history", timeout=10)
        assert r.status_code == 200
        assert r.json()["is_rollout_admin"] is False


# ---------- Undo ----------
class TestUndo:
    def test_undo_wrong_confirm(self, admin):
        hist = admin.get(f"{API}/test-lab/rollout/history", timeout=10).json()
        job_id = next(e["job_id"] for e in hist["entries"] if e.get("can_undo"))
        r = admin.post(f"{API}/test-lab/rollout/jobs/{job_id}/undo",
                       json={"confirm": "no"}, timeout=10)
        assert r.status_code == 400

    def test_undo_older_job_400(self, admin):
        # Trigger another rollout so the previously-undoable one is no longer newest
        _force_theme_diff(admin, primary="#eeeeee")
        r = admin.post(f"{API}/test-lab/rollout",
                       json={"changes": ["design.primary"], "confirm": "CONFIRM"}, timeout=15)
        assert r.status_code == 200
        _poll_job(admin, r.json()["job_id"])

        hist = admin.get(f"{API}/test-lab/rollout/history", timeout=10).json()
        entries = hist["entries"]
        newest_id = next(e["job_id"] for e in entries if e.get("can_undo"))
        # find an older completed job that is NOT the newest_id
        older = next((e for e in entries[1:]
                      if e.get("status") in ("done", "partial") and e["job_id"] != newest_id
                      and not e.get("undone_at")), None)
        if not older:
            pytest.skip("No older job available to test 'only newest can be undone'")
        r = admin.post(f"{API}/test-lab/rollout/jobs/{older['job_id']}/undo",
                       json={"confirm": "CONFIRM"}, timeout=10)
        assert r.status_code == 400
        assert "most recent" in r.text.lower()

    def test_undo_restores_and_flips_can_undo(self, admin):
        # Seed a distinctive theme on the target, rollout will overwrite it, undo should restore
        distinct_primary = "#deadbe"
        _force_theme_diff(admin, primary=distinct_primary)
        # Capture BEFORE
        before = admin.get(f"{API}/apps/{TARGET_ID}", timeout=10).json()
        b_primary = (before.get("theme") or {}).get("primary")
        b_name = before.get("name")
        b_desc = before.get("description")
        b_pages = admin.get(f"{API}/apps/{TARGET_ID}/pages", timeout=10).json()
        b_pages_sig = [(p.get("page_id"), p.get("name"), p.get("slug"), len(p.get("blocks") or []))
                       for p in b_pages]

        # Rollout of design.primary from Test Lab
        r = admin.post(f"{API}/test-lab/rollout",
                       json={"changes": ["design.primary"], "confirm": "CONFIRM"}, timeout=15)
        assert r.status_code == 200
        job_id = r.json()["job_id"]
        _poll_job(admin, job_id)

        # confirm target primary changed
        after_apply = admin.get(f"{API}/apps/{TARGET_ID}", timeout=10).json()
        assert (after_apply.get("theme") or {}).get("primary") != b_primary

        # Now undo
        hist = admin.get(f"{API}/test-lab/rollout/history", timeout=10).json()
        newest = next((e for e in hist["entries"] if e.get("can_undo")), None)
        assert newest and newest["job_id"] == job_id, "the rollout we just did should be undoable"

        r = admin.post(f"{API}/test-lab/rollout/jobs/{job_id}/undo",
                       json={"confirm": "CONFIRM"}, timeout=10)
        assert r.status_code == 200, r.text

        # Poll for undone status
        deadline = time.time() + 30
        undone = None
        while time.time() < deadline:
            jr = admin.get(f"{API}/test-lab/rollout/jobs/{job_id}", timeout=10).json()
            if jr.get("status") == "undone":
                undone = jr
                break
            time.sleep(0.5)
        assert undone, "undo did not complete"
        assert undone.get("undo_pct") == 100
        assert undone.get("undone_by")
        assert undone.get("undone_at")

        # Verify target primary restored to b_primary
        restored = admin.get(f"{API}/apps/{TARGET_ID}", timeout=10).json()
        assert (restored.get("theme") or {}).get("primary") == b_primary, "undo did not restore primary"
        # Content invariance across the whole rollout+undo
        assert restored.get("name") == b_name
        assert restored.get("description") == b_desc
        a_pages = admin.get(f"{API}/apps/{TARGET_ID}/pages", timeout=10).json()
        a_pages_sig = [(p.get("page_id"), p.get("name"), p.get("slug"), len(p.get("blocks") or []))
                       for p in a_pages]
        assert a_pages_sig == b_pages_sig, "pages were mutated by rollout/undo"

        # can_undo must now be false for that job
        hist2 = admin.get(f"{API}/test-lab/rollout/history", timeout=10).json()
        this_entry = next(e for e in hist2["entries"] if e["job_id"] == job_id)
        assert this_entry.get("can_undo") is False


# ---------- Template rollout writes history ----------
class TestTemplateHistory:
    def test_template_rollout_creates_job(self, admin):
        r = admin.post(f"{API}/templates/saas/rollout",
                       json={"scopes": [], "confirm": "CONFIRM"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        job_id = data["job_id"]
        # Should appear in history
        hist = admin.get(f"{API}/test-lab/rollout/history", timeout=10).json()
        entry = next((e for e in hist["entries"] if e["job_id"] == job_id), None)
        assert entry, f"template rollout job {job_id} not in history"
        assert entry.get("kind") == "template"
        assert entry.get("template_key") == "saas"
        assert entry.get("status") == "done"
        assert "Design" in (entry.get("categories") or [])
        assert entry.get("diff", {}).get("total", 0) > 0

    def test_template_rollout_non_admin_forbidden(self, editor):
        r = editor.post(f"{API}/templates/saas/rollout",
                        json={"confirm": "CONFIRM"}, timeout=10)
        assert r.status_code == 403


# ---------- Regression: Test Lab is still protected + 32 pages ----------
class TestRegression:
    def test_test_lab_still_protected(self, admin):
        r = admin.get(f"{API}/test-lab", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["template_pages"] == 32
        assert d["app"]["is_test_lab"] is True

        assert admin.post(f"{API}/apps/{TEST_LAB_ID}/archive",
                          json={"archived": True}, timeout=10).status_code == 400
        assert admin.delete(f"{API}/apps/{TEST_LAB_ID}/purge", timeout=10).status_code == 400
        assert admin.delete(f"{API}/apps/{TEST_LAB_ID}", timeout=10).status_code == 400

    def test_templates_status_lists_32(self, admin):
        r = admin.get(f"{API}/templates/rollout-status", timeout=10)
        assert r.status_code == 200
        assert len(r.json()["templates"]) == 32
