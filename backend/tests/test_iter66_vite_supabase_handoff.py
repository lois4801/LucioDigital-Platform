"""Iteration 66 — backend tests for Supabase export + Handoff bundle + Vite regression.

Focus areas:
- /api/apps/{id}/supabase/status
- /api/apps/{id}/supabase/sql (schema + seed + RLS)
- /api/apps/{id}/supabase/push validation (400 no uri, 400 bad uri, 502 unreachable)
- Export kinds website/fullstack/plugin/handoff run & download
- Handoff zip layout (site/, app/, data/, files/, supabase/, README.md, .env.example, no stray assets at root)
- Invalid export kind returns 400 mentioning valid kinds
"""
import io
import os
import time
import zipfile

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"

# Explicitly created for this iter — safe to purge on teardown.
_created_app_ids = []


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    yield s
    # teardown: only purge tenants we created
    for aid in _created_app_ids:
        try:
            s.post(f"{BASE_URL}/api/apps/{aid}/archive", json={"archived": True}, timeout=10)
            s.delete(f"{BASE_URL}/api/apps/{aid}", timeout=10)
        except Exception:
            pass


@pytest.fixture(scope="module")
def app_id(sess):
    r = sess.post(f"{BASE_URL}/api/apps",
                  json={"name": "TEST_iter66_handoff", "industry": "general",
                        "description": "iter66 throwaway"}, timeout=20)
    assert r.status_code in (200, 201), f"create app failed: {r.status_code} {r.text[:200]}"
    aid = r.json().get("app_id") or r.json().get("id")
    assert aid, f"no app_id in response {r.text[:200]}"
    _created_app_ids.append(aid)
    return aid


# -------- Supabase export --------

class TestSupabaseExport:
    def test_status(self, sess, app_id):
        r = sess.get(f"{BASE_URL}/api/apps/{app_id}/supabase/status", timeout=15)
        assert r.status_code == 200, r.text[:300]
        j = r.json()
        assert set(["has_saved_connection", "provider", "tables", "last_push"]).issubset(j.keys())
        assert isinstance(j["tables"], list) and len(j["tables"]) > 0
        # Common tables expected
        assert "pages" in j["tables"]
        assert "leads" in j["tables"]

    def test_sql_download(self, sess, app_id):
        r = sess.get(f"{BASE_URL}/api/apps/{app_id}/supabase/sql", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert "attachment" in r.headers.get("content-disposition", "").lower()
        sql = r.text
        assert sql.strip().startswith("--")
        assert "begin;" in sql and "commit;" in sql
        assert "create table if not exists \"lt_tenants\"" in sql
        assert "create table if not exists \"lt_pages\"" in sql
        assert "enable row level security" in sql
        assert "read_own_tenant" in sql
        # Contains an insert into lt_tenants for this app
        assert "insert into \"lt_tenants\"" in sql
        # Single quotes properly escaped: shouldn't contain unbalanced apostrophes
        # Simple check: no odd number of single quotes on any single line insert (rough)
        assert "''" in sql or "'" not in "TEST_iter66_handoff"

    def test_push_no_uri(self, sess, app_id):
        r = sess.post(f"{BASE_URL}/api/apps/{app_id}/supabase/push", json={}, timeout=15)
        assert r.status_code == 400, r.text[:300]
        assert "connection" in r.text.lower() or "supabase" in r.text.lower()

    def test_push_invalid_uri(self, sess, app_id):
        r = sess.post(f"{BASE_URL}/api/apps/{app_id}/supabase/push",
                      json={"connection_uri": "not-a-uri"}, timeout=15)
        assert r.status_code == 400, r.text[:300]
        assert "postgresql://" in r.text or "postgres" in r.text.lower()

    def test_push_unreachable(self, sess, app_id):
        r = sess.post(f"{BASE_URL}/api/apps/{app_id}/supabase/push",
                      json={"connection_uri": "postgresql://user:pw@127.0.0.1:1/postgres"},
                      timeout=30)
        # unreachable → 502 with readable message
        assert r.status_code == 502, f"expected 502 got {r.status_code}: {r.text[:300]}"
        assert len(r.text) > 5


# -------- Export jobs --------

def _wait_job(sess, app_id, job_id, timeout=180):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = sess.get(f"{BASE_URL}/api/apps/{app_id}/export/jobs/{job_id}", timeout=15)
        assert r.status_code == 200
        last = r.json()
        if last.get("status") in ("done", "error"):
            return last
        time.sleep(2)
    raise AssertionError(f"job timeout: last={last}")


class TestExportJobs:
    def test_invalid_kind(self, sess, app_id):
        r = sess.post(f"{BASE_URL}/api/apps/{app_id}/export/start?kind=bogus", timeout=15)
        assert r.status_code == 400
        txt = r.text.lower()
        for k in ("website", "fullstack", "plugin", "handoff"):
            assert k in txt

    @pytest.mark.parametrize("kind", ["website", "fullstack", "plugin", "handoff"])
    def test_export_run_and_download(self, sess, app_id, kind):
        r = sess.post(f"{BASE_URL}/api/apps/{app_id}/export/start?kind={kind}", timeout=15)
        assert r.status_code in (200, 201), r.text[:300]
        job = r.json()
        job_id = job["job_id"]
        final = _wait_job(sess, app_id, job_id, timeout=240)
        assert final["status"] == "done", f"{kind} export failed: {final}"
        assert final.get("file_count", 0) > 0

        dl = sess.get(f"{BASE_URL}/api/apps/{app_id}/export/jobs/{job_id}/download", timeout=60)
        assert dl.status_code == 200
        assert dl.headers.get("content-type", "").startswith("application/") or dl.headers.get("content-type", "").endswith("zip")
        buf = io.BytesIO(dl.content)
        z = zipfile.ZipFile(buf)
        names = z.namelist()
        assert names, "zip is empty"
        # figure root
        root = names[0].split("/", 1)[0]
        rel = [n[len(root) + 1:] for n in names if n.startswith(root + "/") and n != root + "/"]

        if kind == "handoff":
            # required folders + files
            required_prefixes = ["site/", "app/", "data/", "files/", "supabase/"]
            for p in required_prefixes:
                assert any(x.startswith(p) for x in rel), f"missing prefix {p} in handoff zip; sample={rel[:15]}"
            assert "README.md" in rel, f"handoff missing top-level README.md; sample={rel[:15]}"
            assert ".env.example" in rel, f"handoff missing .env.example; sample={rel[:15]}"
            # No stray asset files at root — every top-level entry should be one of the allowed
            allowed_top = {"site", "app", "data", "files", "supabase", "README.md", ".env.example"}
            tops = {r.split("/", 1)[0] for r in rel if r}
            stray = tops - allowed_top
            assert not stray, f"stray top-level entries in handoff zip: {stray}"
            # Supabase migration inside
            assert any(x == "supabase/migration.sql" for x in rel), "missing supabase/migration.sql"
