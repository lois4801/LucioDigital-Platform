"""Iter-22 backend tests: Cursor Effects Engine.

Covers:
- PATCH /api/me/preferences (cursor_effect) auth + validation + persistence via /api/auth/me
- PUT /api/apps/{id}/theme cursor_effect persistence + GET theme + public site exposure
- Export ZIP contains cursor engine when cursor_effect is set, absent when 'none'
"""
import io
import os
import zipfile
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
APP_ID = "app_bdbf27abe643"
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN)
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text}")
    return s


# ---------- User preferences ----------

class TestUserPreferences:
    def test_unauth_returns_401(self):
        r = requests.patch(f"{API}/me/preferences", json={"cursor_effect": "fairy"})
        assert r.status_code == 401, r.text

    def test_unknown_value_returns_400(self, admin):
        r = admin.patch(f"{API}/me/preferences", json={"cursor_effect": "sparkles-of-doom"})
        assert r.status_code == 400, r.text

    def test_set_and_persist_roundtrip(self, admin):
        r = admin.patch(f"{API}/me/preferences", json={"cursor_effect": "fairy"})
        assert r.status_code == 200, r.text
        assert r.json().get("cursor_effect") == "fairy"
        me = admin.get(f"{API}/auth/me")
        assert me.status_code == 200
        assert me.json().get("cursor_effect") == "fairy"

    def test_change_and_reset_to_none(self, admin):
        r = admin.patch(f"{API}/me/preferences", json={"cursor_effect": "plasma"})
        assert r.status_code == 200
        assert admin.get(f"{API}/auth/me").json().get("cursor_effect") == "plasma"
        # reset (cleanup per request)
        r = admin.patch(f"{API}/me/preferences", json={"cursor_effect": "none"})
        assert r.status_code == 200
        assert admin.get(f"{API}/auth/me").json().get("cursor_effect") == "none"


# ---------- App theme cursor_effect ----------

class TestAppTheme:
    def test_put_theme_persists_cursor_effect(self, admin):
        r = admin.get(f"{API}/apps/{APP_ID}/theme")
        assert r.status_code == 200, r.text
        theme = r.json()
        theme["cursor_effect"] = "plasma"
        r = admin.put(f"{API}/apps/{APP_ID}/theme", json={"theme": theme})
        assert r.status_code == 200, r.text
        assert r.json().get("cursor_effect") == "plasma"

        r = admin.get(f"{API}/apps/{APP_ID}/theme")
        assert r.status_code == 200
        assert r.json().get("cursor_effect") == "plasma"

    def test_public_site_exposes_cursor_effect(self, admin):
        # ensure plasma set
        theme = admin.get(f"{API}/apps/{APP_ID}/theme").json()
        theme["cursor_effect"] = "plasma"
        admin.put(f"{API}/apps/{APP_ID}/theme", json={"theme": theme})
        app = admin.get(f"{API}/apps/{APP_ID}").json()
        tok = app.get("preview_token")
        if not tok:
            pytest.skip("no preview_token")
        if not app.get("preview_enabled"):
            admin.put(f"{API}/apps/{APP_ID}", json={"preview_enabled": True})
        r = requests.get(f"{API}/public/site/{tok}")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("theme", {}).get("cursor_effect") == "plasma"


# ---------- Export ZIP ----------

class TestExportZip:
    def _get_zip(self, admin):
        r = admin.get(f"{API}/apps/{APP_ID}/export/source")
        assert r.status_code == 200, r.text
        return zipfile.ZipFile(io.BytesIO(r.content))

    def test_export_contains_cursor_engine_when_set(self, admin):
        theme = admin.get(f"{API}/apps/{APP_ID}/theme").json()
        theme["cursor_effect"] = "matrix"
        admin.put(f"{API}/apps/{APP_ID}/theme", json={"theme": theme})

        z = self._get_zip(admin)
        idx = None
        for n in z.namelist():
            if n.endswith("index.html") and n.startswith("site/"):
                idx = z.read(n).decode("utf-8", errors="ignore")
                break
        assert idx is not None, f"no site/index.html found in {z.namelist()[:20]}"
        assert "data-cursor-fx='matrix'" in idx or 'data-cursor-fx="matrix"' in idx, "body missing data-cursor-fx"
        # engine script marker
        assert "cursorFx" in idx or "data-cursor-fx" in idx
        assert "canvas" in idx.lower(), "cursor canvas script missing"

    def test_export_omits_cursor_engine_when_none(self, admin):
        theme = admin.get(f"{API}/apps/{APP_ID}/theme").json()
        theme["cursor_effect"] = "none"
        admin.put(f"{API}/apps/{APP_ID}/theme", json={"theme": theme})

        z = self._get_zip(admin)
        idx = None
        for n in z.namelist():
            if n.endswith("index.html") and n.startswith("site/"):
                idx = z.read(n).decode("utf-8", errors="ignore")
                break
        assert idx is not None
        assert "data-cursor-fx='none'" in idx or 'data-cursor-fx="none"' in idx
        # canvas cursor script must be absent when none
        # CURSOR_FX_JS is only injected when != none — verify by checking a signature substring
        assert "document.body.dataset.cursorFx" not in idx


# ---------- Cleanup ----------

def test_zzz_cleanup(admin=None):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN)
    if r.status_code != 200:
        return
    s.patch(f"{API}/me/preferences", json={"cursor_effect": "none"})
    theme = s.get(f"{API}/apps/{APP_ID}/theme").json()
    theme["cursor_effect"] = "none"
    s.put(f"{API}/apps/{APP_ID}/theme", json={"theme": theme})
