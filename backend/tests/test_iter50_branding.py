"""Iteration 50 — Branding rename (OmniStack -> LucioDigital) + plugin export/import round-trip.

Covers:
- served <title>/<meta description> use LucioDigital
- GET /api/settings/email reports from_name == 'LucioDigital'
- Plugin export ZIP on app_6663b5de0007 contains 'LucioDigital' and does NOT contain
  the user-visible 'OmniStack' string (the internal 'omnistack.plugin' format id
  and 'omnistack' storage prefix are intentionally kept)
- Plugin import of the freshly-exported ZIP still restores as a new tenant
"""
import io
import os
import re
import time
import zipfile
import requests
import pytest

def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    url = line.split("=", 1)[1].strip()
                    break
    assert url
    return url.rstrip("/")

BASE_URL = _load_backend_url()
OWNER_EMAIL = "jaybernabe@luciodigital.com"
OWNER_PASS = "Lucio2026!"
TARGET_APP = "app_6663b5de0007"


@pytest.fixture(scope="module")
def owner():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# ---------- Static HTML head ----------
class TestServedHtml:
    def test_title_and_meta_lois_tech(self):
        r = requests.get(f"{BASE_URL}/", timeout=30)
        assert r.status_code == 200
        html = r.text
        assert "<title>LucioDigital</title>" in html, "title missing LucioDigital"
        assert 'content="LucioDigital' in html, "meta description missing LucioDigital"
        assert "OmniStack" not in html, "raw HTML head still contains 'OmniStack'"


# ---------- Settings/email ----------
class TestEmailSettings:
    def test_email_from_name_is_lois_tech(self, owner):
        r = owner.get(f"{BASE_URL}/api/settings/email", timeout=30)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        assert data.get("from_name") == "LucioDigital", f"from_name={data.get('from_name')!r}"


# ---------- Plugin export round-trip ----------
class TestPluginExportImport:
    def _start_and_wait(self, owner, app_id, timeout_s=180):
        r = owner.post(f"{BASE_URL}/api/apps/{app_id}/export/start", params={"kind": "plugin"}, timeout=60)
        assert r.status_code in (200, 201, 202), f"start export: {r.status_code} {r.text[:200]}"
        data = r.json()
        job_id = data.get("job_id")
        assert job_id, f"no job_id in start response: {data}"
        start = time.time()
        while time.time() - start < timeout_s:
            j = owner.get(f"{BASE_URL}/api/apps/{app_id}/export/jobs/{job_id}", timeout=30)
            if j.status_code == 200:
                js = j.json()
                status = js.get("status")
                if status == "done":
                    return job_id, js
                if status in ("error", "failed"):
                    pytest.fail(f"export failed: {js}")
            time.sleep(4)
        pytest.fail(f"export did not finish in {timeout_s}s")

    def _download(self, owner, app_id, job_id):
        r = owner.get(f"{BASE_URL}/api/apps/{app_id}/export/jobs/{job_id}/download", timeout=180)
        assert r.status_code == 200, f"download: {r.status_code}"
        return r.content

    def test_export_zip_uses_lois_tech(self, owner):
        job_id, _ = self._start_and_wait(owner, TARGET_APP, timeout_s=240)
        zip_bytes = self._download(owner, TARGET_APP, job_id)
        assert len(zip_bytes) > 1000, f"zip too small: {len(zip_bytes)}"
        # cache for the next test
        TestPluginExportImport._cached_zip = zip_bytes  # type: ignore

        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        names = zf.namelist()
        # Look at README / manifest text files for user-visible strings
        found_lois = False
        offending = []
        for n in names:
            if not (n.lower().endswith(".md") or n.lower().endswith(".txt") or n.lower().endswith(".json")):
                continue
            try:
                content = zf.read(n).decode("utf-8", errors="ignore")
            except Exception:
                continue
            if "LucioDigital" in content:
                found_lois = True
            # allow the intentional format id and storage prefix
            # (case-sensitive 'OmniStack' is user-visible branding)
            for m in re.finditer(r"OmniStack", content):
                offending.append((n, content[max(0, m.start() - 30): m.end() + 30]))
        assert found_lois, "no file in plugin ZIP contains 'LucioDigital'"
        assert not offending, f"user-visible 'OmniStack' found in ZIP: {offending[:3]}"

    def test_import_zip_restores_new_tenant(self, owner):
        zip_bytes = getattr(TestPluginExportImport, "_cached_zip", None)
        if not zip_bytes:
            pytest.skip("no cached export ZIP")
        files = {"file": ("plugin.zip", zip_bytes, "application/zip")}
        r = owner.post(f"{BASE_URL}/api/site/import-plugin", files=files, timeout=180)
        assert r.status_code in (200, 201), f"import failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        new_id = (data.get("app") or {}).get("app_id") or data.get("app_id")
        assert new_id and new_id != TARGET_APP, f"unexpected app id: {data}"
        # confirm the new app exists
        r2 = owner.get(f"{BASE_URL}/api/apps/{new_id}", timeout=30)
        assert r2.status_code == 200, f"new app not readable: {r2.status_code}"
