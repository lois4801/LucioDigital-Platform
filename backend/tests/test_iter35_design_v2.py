"""Iteration 35 — Framer-grade design_v2 default for new tenants + export parity."""
import io
import os
import zipfile

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}

V2_DEMO_APP = "app_5d6afc6e523f"
V2_PREVIEW_TOKEN = "pv_aa9819571f45f55298b8"
OLD_APPS = ["app_7a2cd286a360", "app_e3cb4f084785"]


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


# --- New tenants get V2 theme --------------------------------------------------
class TestNewTenantV2Default:
    def test_create_new_app_has_design_v2_true_with_sora_inter(self, admin_session):
        payload = {"name": "TEST_v2_default", "industry": "SaaS", "kind": "website"}
        r = admin_session.post(f"{API}/apps", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        app = r.json()
        app_id = app.get("app_id") or app.get("id")
        assert app_id

        # GET app -> theme.design_v2 true
        rg = admin_session.get(f"{API}/apps/{app_id}", timeout=30)
        assert rg.status_code == 200
        theme = rg.json().get("theme") or {}
        assert theme.get("design_v2") is True, theme
        assert theme.get("font_heading") == "Sora"
        assert theme.get("font_body") == "Inter"

        # cleanup
        admin_session.delete(f"{API}/apps/{app_id}", timeout=30)


# --- Existing tenants unchanged ------------------------------------------------
class TestExistingTenantsUnchanged:
    @pytest.mark.parametrize("app_id", OLD_APPS)
    def test_existing_app_still_not_v2(self, admin_session, app_id):
        r = admin_session.get(f"{API}/apps/{app_id}", timeout=30)
        if r.status_code == 404:
            pytest.skip(f"{app_id} not present in this env")
        assert r.status_code == 200, r.text[:300]
        theme = r.json().get("theme") or {}
        assert not theme.get("design_v2"), f"regression: {app_id} unexpectedly has design_v2 true: {theme}"


# --- Public preview of v2 demo tenant -----------------------------------------
class TestV2PublicPreview:
    def test_public_site_theme_v2(self):
        r = requests.get(f"{API}/public/site/{V2_PREVIEW_TOKEN}", timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        theme = data.get("theme") or {}
        assert theme.get("design_v2") is True
        # font is per-tenant editable; only require Sora/Inter on fresh tenants (tested elsewhere)
        assert len(data.get("pages") or []) >= 1


# --- Try another look / premium-rebuild ---------------------------------------
class TestPremiumRebuildUpgradesToV2:
    def test_premium_rebuild_flips_design_v2(self, admin_session):
        # create fresh app, force design_v2 off first to verify rebuild upgrades it
        r = admin_session.post(f"{API}/apps", json={"name": "TEST_v2_rebuild", "industry": "Studio", "kind": "website"}, timeout=30)
        assert r.status_code in (200, 201)
        app_id = r.json().get("app_id") or r.json().get("id")
        try:
            # unlock content lock
            ul = admin_session.post(f"{API}/apps/{app_id}/content-lock", json={"locked": False}, timeout=30)
            assert ul.status_code in (200, 204), ul.text[:200]

            # force old theme so rebuild really flips flag
            admin_session.put(f"{API}/apps/{app_id}/theme", json={"theme": {"design_v2": False, "font_heading": "Plus Jakarta Sans", "font_body": "Manrope"}}, timeout=30)

            pr = admin_session.post(f"{API}/apps/{app_id}/site/premium-rebuild", json={}, timeout=90)
            assert pr.status_code == 200, pr.text[:400]

            rg = admin_session.get(f"{API}/apps/{app_id}", timeout=30)
            theme = rg.json().get("theme") or {}
            assert theme.get("design_v2") is True, theme
        finally:
            admin_session.delete(f"{API}/apps/{app_id}", timeout=30)


# --- Export parity -------------------------------------------------------------
def _fetch_zip(session, app_id):
    r = session.get(f"{API}/apps/{app_id}/export/source", timeout=60)
    assert r.status_code == 200, f"{app_id} export {r.status_code}: {r.text[:200]}"
    return zipfile.ZipFile(io.BytesIO(r.content))


class TestExportSourceParity:
    def test_v2_export_contains_v2_tokens(self, admin_session):
        z = _fetch_zip(admin_session, V2_DEMO_APP)
        names = z.namelist()
        css_name = next((n for n in names if n.endswith("styles.css")), None)
        assert css_name, names[:20]
        css = z.read(css_name).decode("utf-8", "ignore")
        html_all = "\n".join(z.read(n).decode("utf-8", "ignore") for n in names if n.endswith(".html"))
        assert "--t-h1" in css, "v2 styles.css missing --t-h1 clamp token"
        assert "clamp(" in css
        assert "backdrop-filter" in css and "sticky" in css, "v2 styles.css missing sticky glass nav"
        assert ".fx-stagger" in css
        assert "fx-stagger" in html_all, "v2 html missing fx-stagger grids"
        assert "loading='lazy'" in html_all or 'loading="lazy"' in html_all, "v2 html missing lazy images"

    def test_non_v2_export_does_not_contain_v2_tokens(self, admin_session):
        target = None
        for app_id in OLD_APPS:
            r = admin_session.get(f"{API}/apps/{app_id}", timeout=30)
            if r.status_code == 200 and not (r.json().get("theme") or {}).get("design_v2"):
                target = app_id
                break
        if not target:
            pytest.skip("no non-v2 tenant available")
        z = _fetch_zip(admin_session, target)
        css_name = next((n for n in z.namelist() if n.endswith("styles.css")), None)
        assert css_name
        css = z.read(css_name).decode("utf-8", "ignore")
        assert "--t-h1" not in css, f"non-v2 tenant {target} unexpectedly exports v2 css tokens"
