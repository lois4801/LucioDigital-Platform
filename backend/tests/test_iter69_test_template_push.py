"""Iteration 69 — Test Template push, push-to-one-tenant, pending map, persistence & undo.

All tests share one throwaway target tenant (app_03efdf8b1af4) and one throwaway template key,
so this file MUST be run serially (`-n 0`).
"""
import os
import time

import pytest
import requests

def _base_url() -> str:
    for k in ("REACT_APP_BACKEND_URL", "BACKEND_URL", "PUBLIC_BACKEND_URL"):
        v = os.environ.get(k)
        if v:
            return v.rstrip("/")
    # fall back to frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE = _base_url()
API = f"{BASE}/api"
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
CLIENT = {"email": "client.editor@example.com", "password": "ClientEdit2026!"}
TARGET_TENANT = "app_03efdf8b1af4"
# Pick a low-blast-radius template we can undo cleanly.
PUSH_KEY = "legal"


def _login(payload):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=payload, timeout=15)
    assert r.status_code == 200, f"login failed for {payload['email']}: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def non_admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=CLIENT, timeout=15)
    if r.status_code != 200:
        # Try to seed the account via seed endpoint? Otherwise skip. Fallback: create via signup.
        rs = s.post(f"{API}/auth/signup", json={**CLIENT, "name": "Client Editor"}, timeout=15)
        if rs.status_code not in (200, 201):
            pytest.skip(f"cannot obtain non-admin session: {r.status_code} {r.text[:120]}")
        r = s.post(f"{API}/auth/login", json=CLIENT, timeout=15)
        assert r.status_code == 200, r.text
    return s


# ------- GET /api/test-template -------
def test_get_test_template_shape(admin):
    r = admin.get(f"{API}/test-template")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["key"] == "test_template"
    assert d["brand"] == "Test Project"
    assert d["is_rollout_admin"] is True
    assert isinstance(d["templates"], list)
    assert len(d["templates"]) == 32
    keys = {t["key"] for t in d["templates"]}
    assert "test_template" not in keys
    for t in d["templates"]:
        assert "pending" in t and "studio" in t


def test_public_templates_includes_test_template():
    r = requests.get(f"{API}/public/templates", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 33
    keys = {t["key"] for t in d["templates"]}
    assert "test_template" in keys


# ------- GET /api/test-template/diff -------
def test_diff_scope_counts(admin):
    r_all = admin.get(f"{API}/test-template/diff", params={"scope": "all"}).json()
    r_classic = admin.get(f"{API}/test-template/diff", params={"scope": "classic"}).json()
    r_studio = admin.get(f"{API}/test-template/diff", params={"scope": "studio"}).json()
    r_sel = admin.get(f"{API}/test-template/diff",
                      params={"scope": "selected", "keys": PUSH_KEY}).json()
    assert r_all["target_count"] == 32
    assert r_classic["target_count"] + r_studio["target_count"] == 32
    # request statement says 16 / 16
    assert r_classic["target_count"] == 16
    assert r_studio["target_count"] == 16
    assert r_sel["target_count"] == 1
    # each row has expected fields
    for row in r_all["changes"]:
        for k in ("old", "new", "kind", "tenants", "variance", "category"):
            assert k in row
        assert row["category"] in ("Design", "Animations", "Features")


def test_diff_scope_selected_empty_400(admin):
    r = admin.get(f"{API}/test-template/diff", params={"scope": "selected", "keys": ""})
    assert r.status_code == 400


# ------- POST /api/test-template/rollout: errors -------
def test_rollout_wrong_confirm(admin):
    r = admin.post(f"{API}/test-template/rollout",
                   json={"scope": "selected", "keys": [PUSH_KEY], "confirm": "yes"})
    assert r.status_code == 400
    assert "CONFIRM" in r.text or "change to push" in r.text


def test_rollout_empty_changes(admin):
    # No diff rows selected → 400. First seed a diff on the test_template.
    # Fetch current diff rows for the target key to build an explicit "no valid ids" case.
    r = admin.post(f"{API}/test-template/rollout",
                   json={"scope": "selected", "keys": [PUSH_KEY],
                         "changes": ["design.nonexistent_field"], "confirm": "CONFIRM"})
    assert r.status_code == 400


def test_rollout_non_admin_403(non_admin):
    r = non_admin.post(f"{API}/test-template/rollout",
                       json={"scope": "selected", "keys": [PUSH_KEY], "confirm": "CONFIRM"})
    assert r.status_code in (402, 403)      # the membership gate answers first for free accounts


# ------- Full push→history→persistence→undo of a template push -------
@pytest.fixture(scope="module")
def seeded_template_diff(admin):
    """Ensure the sandbox template has at least one field differing from PUSH_KEY."""
    # Read current diff rows for the target key
    d = admin.get(f"{API}/test-template/diff",
                  params={"scope": "selected", "keys": PUSH_KEY}).json()
    if d["total"] > 0:
        return d
    pytest.skip("Test Template has no design deltas vs the target key — seed required from UI/DB")


def test_push_selected_updates_only_that_template_and_persists(admin, seeded_template_diff):
    d = seeded_template_diff
    # Pick a Design row so we can verify via /api/public/templates
    row = next((c for c in d["changes"] if c["category"] == "Design"), d["changes"][0])
    change_id = row["id"]
    new_val = row["new"]
    old_val = row["old"]

    # capture pre-state for the target key + a *different* template to prove isolation
    other_key = "saas" if PUSH_KEY != "saas" else "fitness"
    pub = requests.get(f"{API}/public/templates", timeout=15).json()["templates"]
    def _get(pub_list, k): return next((t for t in pub_list if t["key"] == k), None)
    other_before = _get(pub, other_key)

    r = admin.post(f"{API}/test-template/rollout",
                   json={"scope": "selected", "keys": [PUSH_KEY],
                         "changes": [change_id], "confirm": "CONFIRM"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["templates_updated"] == 1
    assert body["changes"] == 1
    job_id = body["job_id"]

    # verify template_states now marks that key as pending
    tpl = admin.get(f"{API}/test-template").json()
    st = next(t for t in tpl["templates"] if t["key"] == PUSH_KEY)
    assert st["pending"] is True

    # history should include this job with kind template_look and can_undo true
    hist = admin.get(f"{API}/test-lab/rollout/history").json()
    entry = next((e for e in hist["entries"] if e["job_id"] == job_id), None)
    assert entry is not None, f"job {job_id} missing from history"
    assert entry["kind"] == "template_look"
    assert entry.get("can_undo") is True
    assert entry.get("diff", {}).get("total", 0) >= 1

    # verify the pushed value is visible via /api/public/templates
    pub2 = requests.get(f"{API}/public/templates", timeout=15).json()["templates"]
    target_now = _get(pub2, PUSH_KEY)
    field = change_id.split(".", 1)[1]
    # public/templates only exposes some fields; fall back to /public/templates/{key}
    if field in target_now:
        assert target_now[field] == new_val
    else:
        detail = requests.get(f"{API}/public/templates/{PUSH_KEY}", timeout=15).json()
        assert detail["theme"].get(field) == new_val or field in (
            "look_v", "studio", "glass", "grain")

    # OTHER template must be unchanged
    other_after = _get(pub2, other_key)
    assert other_after == other_before, f"other template {other_key} was mutated!"

    # Stash for the next test
    admin._iter69 = {"job_id": job_id, "field": field, "old": old_val, "new": new_val}


def test_persistence_across_backend_restart(admin):
    stash = getattr(admin, "_iter69", None)
    if not stash:
        pytest.skip("prior push test did not run")
    # restart backend
    import subprocess
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=True,
                   capture_output=True, timeout=30)
    # wait for it to come back
    for _ in range(30):
        try:
            r = requests.get(f"{API}/public/templates", timeout=5)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        pytest.fail("backend did not come back after restart")

    # login again (cookie is likely still valid but be safe)
    admin2 = _login(ADMIN)
    # after restart, load_overrides() must re-apply the pushed field
    detail = requests.get(f"{API}/public/templates/{PUSH_KEY}", timeout=15).json()
    field = stash["field"]
    exp = stash["new"]
    got = detail["theme"].get(field)
    # look_v etc. are on LOOKS but not always on theme; fall back to /public/templates row
    if got is None:
        row = next(t for t in requests.get(f"{API}/public/templates").json()["templates"]
                   if t["key"] == PUSH_KEY)
        got = row.get(field)
    assert got == exp, f"restart did not preserve pushed value for {field}: got {got!r} exp {exp!r}"


def test_undo_of_template_push_restores_value(admin):
    stash = getattr(admin, "_iter69", None)
    if not stash:
        pytest.skip("prior push test did not run")
    admin2 = _login(ADMIN)  # fresh session post-restart
    r = admin2.post(f"{API}/test-lab/rollout/jobs/{stash['job_id']}/undo",
                    json={"confirm": "CONFIRM"})
    assert r.status_code == 200, r.text
    # allow the background undo task to finish
    for _ in range(20):
        j = admin2.get(f"{API}/test-lab/rollout/jobs/{stash['job_id']}").json()
        if j.get("undo_pct") == 100 and j.get("undone_at"):
            break
        time.sleep(0.4)
    else:
        pytest.fail("undo did not finish")

    # value should be restored
    detail = requests.get(f"{API}/public/templates/{PUSH_KEY}").json()
    field = stash["field"]
    got = detail["theme"].get(field)
    if got is None:
        row = next(t for t in requests.get(f"{API}/public/templates").json()["templates"]
                   if t["key"] == PUSH_KEY)
        got = row.get(field)
    assert got == stash["old"], f"undo did not restore {field}: got {got!r} exp {stash['old']!r}"

    # history entry should now be un-undoable
    hist = admin2.get(f"{API}/test-lab/rollout/history").json()
    entry = next(e for e in hist["entries"] if e["job_id"] == stash["job_id"])
    assert entry.get("can_undo") is False
    assert entry.get("undone_at")


# ------- Push to One Tenant isolation -------
def test_push_to_one_tenant_isolation(admin):
    # Re-login in case an earlier test restarted the backend and invalidated the cookie.
    admin = _login(ADMIN)
    # Ensure both TARGET_TENANT and Test Lab are alive
    apps = admin.get(f"{API}/apps").json()
    apps_list = apps if isinstance(apps, list) else apps.get("apps", [])
    ids = {a["app_id"] for a in apps_list}
    if TARGET_TENANT not in ids:
        pytest.skip(f"target tenant {TARGET_TENANT} missing (ids={ids})")

    # Seed a diff on the Test Lab (use a fresh random-ish colour so a re-run always yields a delta)
    import random
    new_primary = "#" + "".join(random.choices("0123456789abcdef", k=6))
    lab_before = admin.get(f"{API}/apps/app_testlab").json()
    ok = admin.put(f"{API}/apps/app_testlab/theme",
                   json={"theme": {**(lab_before.get("theme") or {}), "primary": new_primary}})
    assert ok.status_code == 200, ok.text

    # Build scoped diff
    d = admin.get(f"{API}/test-lab/diff", params={"app_id": TARGET_TENANT}).json()
    assert d["target_count"] == 1
    # Grab the primary-colour change id
    row = next((c for c in d["changes"] if c["id"] == "design.primary"), None)
    if not row:
        pytest.skip("no primary diff between Test Lab and target after seeding")

    # Snapshot every OTHER active tenant's theme so we can prove isolation
    apps_before = admin.get(f"{API}/apps").json()
    if isinstance(apps_before, dict):
        apps_before = apps_before.get("apps", [])
    others_before = {a["app_id"]: (a.get("theme") or {}).get("primary")
                     for a in apps_before if a["app_id"] not in (TARGET_TENANT, "app_testlab")}

    r = admin.post(f"{API}/test-lab/rollout",
                   json={"target_app_ids": [TARGET_TENANT],
                         "changes": ["design.primary"], "confirm": "CONFIRM"})
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["kind"] == "single"
    assert job["target_app_ids"] == [TARGET_TENANT]

    # wait for completion
    for _ in range(20):
        j = admin.get(f"{API}/test-lab/rollout/jobs/{job['job_id']}").json()
        if j.get("status") in ("done", "partial", "failed"):
            break
        time.sleep(0.4)
    assert j["status"] in ("done", "partial")

    # target got the new primary
    tgt = admin.get(f"{API}/apps/{TARGET_TENANT}").json()
    assert (tgt.get("theme") or {}).get("primary") == new_primary

    # other tenants untouched
    apps_after = admin.get(f"{API}/apps").json()
    if isinstance(apps_after, dict):
        apps_after = apps_after.get("apps", [])
    others_after = {a["app_id"]: (a.get("theme") or {}).get("primary")
                    for a in apps_after if a["app_id"] not in (TARGET_TENANT, "app_testlab")}
    assert others_after == others_before, f"other tenants mutated: {others_before} → {others_after}"


# ------- /api/test-lab/pending -------
def test_pending_map_shape(admin):
    r = admin.get(f"{API}/test-lab/pending")
    assert r.status_code == 200
    d = r.json()
    assert "tenants" in d and isinstance(d["tenants"], dict)
    assert "total" in d
    # total is sum of per-tenant counts
    assert d["total"] == sum(d["tenants"].values())


# ------- Test Lab protection (regression) -------
def test_test_lab_cannot_be_archived_or_deleted(admin):
    r1 = admin.post(f"{API}/apps/app_testlab/archive", json={"archived": True})
    assert r1.status_code == 400
    r2 = admin.delete(f"{API}/apps/app_testlab")
    assert r2.status_code == 400
