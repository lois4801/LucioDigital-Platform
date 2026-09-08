"""Iteration 36 — Retest of iteration 35 HIGH/LOW fixes.

FIX 4: PUT /api/apps/{id}/theme with font_body='Inter' must persist as 'Inter'
       (previously silently rewritten to Manrope by _clean_theme font guard).
FIX 4b: v2 demo tenant app_5d6afc6e523f should now render Sora headings + Inter body.
"""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
V2_DEMO_APP = "app_5d6afc6e523f"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text[:200]
    tok = r.json().get("token") or r.json().get("access_token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


class TestInterFontPersistence:
    def test_put_theme_font_body_inter_persists(self, admin_session):
        # Create throwaway tenant
        r = admin_session.post(f"{API}/apps", json={"name": "TEST_inter_font", "industry": "SaaS", "kind": "website"}, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        app_id = r.json().get("app_id") or r.json().get("id")
        try:
            # Force font_body to something else first, then set to Inter
            admin_session.put(f"{API}/apps/{app_id}/theme", json={"theme": {"font_body": "Manrope"}}, timeout=30)
            # Now PUT Inter
            put = admin_session.put(f"{API}/apps/{app_id}/theme", json={"theme": {"font_body": "Inter"}}, timeout=30)
            assert put.status_code == 200, put.text[:300]
            body = put.json()
            theme = body.get("theme") or body
            assert theme.get("font_body") == "Inter", f"font_body silently rewritten: {theme.get('font_body')}"

            # GET verifies persistence
            g = admin_session.get(f"{API}/apps/{app_id}", timeout=30)
            gtheme = g.json().get("theme") or {}
            assert gtheme.get("font_body") == "Inter", f"GET returned {gtheme.get('font_body')} instead of Inter"
        finally:
            admin_session.delete(f"{API}/apps/{app_id}", timeout=30)

    def test_v2_demo_tenant_has_sora_and_inter(self, admin_session):
        r = admin_session.get(f"{API}/apps/{V2_DEMO_APP}", timeout=30)
        assert r.status_code == 200, r.text[:200]
        theme = r.json().get("theme") or {}
        assert theme.get("design_v2") is True, theme
        assert theme.get("font_heading") == "Sora", f"font_heading={theme.get('font_heading')}"
        assert theme.get("font_body") == "Inter", f"font_body={theme.get('font_body')}"
