"""Iter 44 — three-way export system: website / fullstack / plugin.

Verifies:
- POST /api/apps/{id}/export/start?kind=... returns a job; polls to done
- Invalid kind → 400
- GET /jobs/{id}/download returns real application/zip
- Website ZIP: pages, styles.css, fonts.css, local font woff2, assets, form server, WP/Webflow, README
- Fullstack ZIP: backend/server.py + seed.py compile; data.json has real content; frontend jsx exist
- Plugin ZIP: plugin.json (format=omnistack.plugin) with all sections + manifest-summary + assets
- POST /api/site/import-plugin with plugin ZIP → new tenant with restored counts
- POST /api/site/import-plugin with non-plugin ZIP → 400
- POST /api/apps/{id}/site/import-zip with plugin ZIP → plugin:true restored counts
"""
import io
import os
import re
import subprocess
import tempfile
import time
import zipfile

import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
API = BASE_URL + "/api"
OWNER = ("jaybernabe@luciodigital.com", "Lucio2026!")
APP_ID = "app_6663b5de0007"

EXPORT_TIMEOUT = 240  # seconds


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def owner():
    return _login(*OWNER)


def _wait_job(sess, app_id, job_id, timeout=EXPORT_TIMEOUT):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = sess.get(f"{API}/apps/{app_id}/export/jobs/{job_id}", timeout=30)
        assert r.status_code == 200, f"job GET failed: {r.status_code} {r.text[:200]}"
        j = r.json()
        last = j
        if j.get("status") in ("done", "error"):
            return j
        time.sleep(3)
    raise AssertionError(f"job timeout after {timeout}s. last={last}")


def _start_and_wait(sess, kind):
    r = sess.post(f"{API}/apps/{APP_ID}/export/start?kind={kind}", timeout=30)
    assert r.status_code == 200, f"start {kind} failed: {r.status_code} {r.text[:200]}"
    job = r.json()
    assert job["status"] == "running"
    assert job["kind"] == kind
    assert isinstance(job.get("pct"), int)
    return _wait_job(sess, APP_ID, job["job_id"])


def _download_zip(sess, job) -> zipfile.ZipFile:
    r = sess.get(f"{API}/apps/{APP_ID}/export/jobs/{job['job_id']}/download", timeout=120)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/zip")
    assert len(r.content) > 10_000, f"suspiciously small zip: {len(r.content)}"
    return zipfile.ZipFile(io.BytesIO(r.content)), r.content


# Cached exports across the class
_cache = {}


class TestExportWebsite:
    def test_invalid_kind_400(self, owner):
        r = owner.post(f"{API}/apps/{APP_ID}/export/start?kind=bogus", timeout=15)
        assert r.status_code == 400

    def test_website_export_completes(self, owner):
        job = _start_and_wait(owner, "website")
        assert job["status"] == "done", f"job errored: {job.get('error')}"
        assert job["pct"] == 100
        assert job.get("file_count", 0) > 5
        assert job.get("size", 0) > 10_000
        _cache["website"] = job

    def test_website_zip_contents(self, owner):
        assert "website" in _cache, "prior test must have run"
        zf, raw = _download_zip(owner, _cache["website"])
        names = zf.namelist()
        # Find root
        roots = {n.split("/", 1)[0] for n in names}
        assert len(roots) == 1
        root = roots.pop()

        # Required files
        required = [
            f"{root}/site/styles.css",
            f"{root}/site/fonts.css",
            f"{root}/server/server.py",
            f"{root}/cms/wordpress-import.xml",
            f"{root}/cms/webflow-pages.csv",
            f"{root}/content/pages.json",
            f"{root}/README.md",
        ]
        for req in required:
            assert req in names, f"missing {req}"

        # At least one HTML page and index.html
        htmls = [n for n in names if n.startswith(f"{root}/site/") and n.endswith(".html")]
        assert len(htmls) >= 1
        assert any(n.endswith("/index.html") for n in htmls), "no index.html"

        # Local font woff2 present
        fonts = [n for n in names if "/assets/fonts/" in n and n.endswith(".woff2")]
        assert len(fonts) >= 1, "no local woff2 fonts embedded"

        # Local assets present
        assets = [n for n in names if f"{root}/site/assets/" in n and not n.endswith("/")]
        assert len(assets) >= 3, f"expected several local assets, got {len(assets)}"

        # Check HTMLs don't have remaining remote media hotlinks (unsplash/pexels/fal etc.)
        import sys
        if "/app/backend" not in sys.path:
            sys.path.insert(0, "/app/backend")
        from export_pkg import MEDIA_HOSTS, SKIP_HOSTS
        hot_re = re.compile(r"(?:src|poster)=['\"](https?://[^'\"]+)['\"]", re.I)
        skipped_list = _cache["website"].get("skipped") or []
        for h in htmls[:5]:
            body = zf.read(h).decode("utf-8", "ignore")
            for url in hot_re.findall(body):
                low = url.lower()
                if any(sh in low for sh in SKIP_HOSTS):
                    continue
                if any(mh in low for mh in MEDIA_HOSTS):
                    # allowed only if listed in skipped
                    assert any(url[:120] in s or s.startswith(url[:100]) for s in skipped_list), (
                        f"remaining hotlink not in skipped: {url} in {h}"
                    )

        # sanity: pages.json is valid JSON
        import json
        json.loads(zf.read(f"{root}/content/pages.json").decode("utf-8", "ignore"))


class TestExportFullstack:
    def test_fullstack_export_completes(self, owner):
        job = _start_and_wait(owner, "fullstack")
        assert job["status"] == "done", f"job errored: {job.get('error')}"
        _cache["fullstack"] = job

    def test_fullstack_zip_contents_and_compile(self, owner):
        assert "fullstack" in _cache
        zf, _ = _download_zip(owner, _cache["fullstack"])
        names = zf.namelist()
        root = names[0].split("/", 1)[0]
        required = [
            f"{root}/backend/server.py",
            f"{root}/backend/seed.py",
            f"{root}/backend/schema.sql",
            f"{root}/backend/.env.example",
            f"{root}/backend/data/data.json",
            f"{root}/frontend/src/App.jsx",
            f"{root}/frontend/src/Site.jsx",
            f"{root}/frontend/src/Auth.jsx",
            f"{root}/frontend/src/Admin.jsx",
            f"{root}/frontend/public/styles.css",
            f"{root}/frontend/public/fonts.css",
            f"{root}/frontend/public/app.css",
            f"{root}/docker-compose.yml",
            f"{root}/README.md",
        ]
        for req in required:
            assert req in names, f"missing {req}"

        # data.json has real content
        import json
        data = json.loads(zf.read(f"{root}/backend/data/data.json").decode("utf-8", "ignore"))
        assert len(data.get("pages") or []) >= 1
        assert isinstance(data.get("collections"), list)

        # Compile python files
        with tempfile.TemporaryDirectory() as td:
            for f in ("backend/server.py", "backend/seed.py"):
                path = os.path.join(td, os.path.basename(f))
                with open(path, "wb") as fh:
                    fh.write(zf.read(f"{root}/{f}"))
                res = subprocess.run(["python", "-m", "py_compile", path],
                                     capture_output=True, text=True)
                assert res.returncode == 0, f"{f} compile failed: {res.stderr}"


class TestExportPlugin:
    def test_plugin_export_completes(self, owner):
        job = _start_and_wait(owner, "plugin")
        assert job["status"] == "done", f"job errored: {job.get('error')}"
        _cache["plugin"] = job

    def test_plugin_zip_contents(self, owner):
        assert "plugin" in _cache
        zf, raw = _download_zip(owner, _cache["plugin"])
        _cache["plugin_raw"] = raw
        names = zf.namelist()
        root = names[0].split("/", 1)[0]
        required = [f"{root}/plugin.json", f"{root}/manifest-summary.json", f"{root}/README.md"]
        for req in required:
            assert req in names, f"missing {req}"

        import json
        manifest = json.loads(zf.read(f"{root}/plugin.json").decode("utf-8", "ignore"))
        assert manifest.get("format") == "omnistack.plugin"
        for k in ("pages", "cms_collections", "cms_items", "workflows",
                  "site_users", "submissions", "theme"):
            assert k in manifest, f"missing manifest key {k}"

        # Assets folder has files
        assets = [n for n in names if f"{root}/assets/" in n and not n.endswith("/README.txt")
                  and not n.endswith("/")]
        assert len(assets) >= 1, "no assets bundled"


class TestPluginImport:
    def test_import_plugin_creates_new_tenant(self, owner):
        assert "plugin_raw" in _cache, "plugin export must run first"
        raw = _cache["plugin_raw"]
        files = {"file": ("plugin.zip", raw, "application/zip")}
        data = {"name": "TEST_iter44_plugin_restore"}
        r = owner.post(f"{API}/site/import-plugin", files=files, data=data, timeout=180)
        assert r.status_code == 200, f"import-plugin failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert "app" in body and "restored" in body
        new_app = body["app"]
        assert new_app["app_id"] != APP_ID
        assert new_app["name"] == "TEST_iter44_plugin_restore"
        restored = body["restored"]
        assert restored.get("pages", 0) >= 1
        assert restored.get("collections", 0) >= 1
        _cache["restored_app_id"] = new_app["app_id"]

        # Verify content matches: fetch pages of new tenant
        r2 = owner.get(f"{API}/apps/{new_app['app_id']}/pages", timeout=30)
        assert r2.status_code == 200
        pages = r2.json()
        # source has 4 pages
        assert len(pages) >= 1

    def test_import_non_plugin_zip_returns_400(self, owner):
        # Create a bogus zip
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("index.html", "<html></html>")
        buf.seek(0)
        files = {"file": ("bogus.zip", buf.getvalue(), "application/zip")}
        r = owner.post(f"{API}/site/import-plugin", files=files, timeout=60)
        assert r.status_code == 400

    def test_import_zip_route_detects_plugin(self, owner):
        assert "plugin_raw" in _cache
        # Use the restored tenant so we don't overwrite the source
        target = _cache.get("restored_app_id") or APP_ID
        files = {"file": ("plugin.zip", _cache["plugin_raw"], "application/zip")}
        data = {"mode": "append", "apply_theme": "false"}
        r = owner.post(f"{API}/apps/{target}/site/import-zip",
                       files=files, data=data, timeout=180)
        assert r.status_code == 200, f"import-zip failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert body.get("plugin") is True, f"expected plugin:true, got {body}"
        assert body.get("status") == "done"
        assert "restored" in body
        assert body["restored"].get("pages", 0) >= 1
