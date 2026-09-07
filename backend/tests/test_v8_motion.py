"""V8 premium motion/design upgrade backend tests.
- Seeded apps carry demo_site_v == 2 and a theme
- Home blocks each have style.effects with reveal True; features/gallery/etc have hover True
- New apps default theme radius is 20
"""
import os
import pytest
import requests
from pathlib import Path

def _load_frontend_env():
    p = Path("/app/frontend/.env")
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("REACT_APP_BACKEND_URL", "")

BASE_URL = _load_frontend_env().rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not found"
EMAIL = "jaybernabe@luciodigital.com"
PASSWORD = "Lucio2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


class TestSeededAppsV8:
    def test_apps_have_demo_site_v2_and_theme(self, client):
        r = client.get(f"{BASE_URL}/api/apps", timeout=30)
        assert r.status_code == 200
        apps = r.json()
        assert isinstance(apps, list) and len(apps) >= 6
        seeded = [a for a in apps if a.get("demo_site_v") == 2]
        assert len(seeded) >= 6, f"expected >=6 apps with demo_site_v==2, got {len(seeded)} of {len(apps)}"
        for a in seeded[:6]:
            # theme present and radius == 20 (default) unless customized
            assert a.get("theme") is not None, f"{a.get('name')} missing theme"

    def test_home_blocks_effects_reveal_and_features_hover(self, client):
        r = client.get(f"{BASE_URL}/api/apps", timeout=30)
        apps = r.json()
        seeded = [a for a in apps if a.get("demo_site_v") == 2][:6]
        assert seeded, "no seeded apps"
        for a in seeded:
            aid = a["app_id"]
            pr = client.get(f"{BASE_URL}/api/apps/{aid}/pages", timeout=30)
            assert pr.status_code == 200, f"{aid} pages: {pr.status_code}"
            pages = pr.json()
            home = next((p for p in pages if p.get("slug") in ("home", "/", "")), pages[0] if pages else None)
            assert home is not None, f"{aid} no home page"
            blocks = home.get("blocks", [])
            assert len(blocks) > 0, f"{aid} home has no blocks"
            for b in blocks:
                eff = (b.get("style") or {}).get("effects")
                assert eff is not None, f"{aid} block {b.get('type')} missing style.effects"
                assert eff.get("reveal") is True, f"{aid} {b.get('type')} reveal not True: {eff}"
            # at least one 'features' block should exist and have hover True
            feats = [b for b in blocks if b.get("type") in ("features", "gallery", "testimonials", "pricing", "collection_list", "logos")]
            if feats:
                for f in feats:
                    assert (f.get("style") or {}).get("effects", {}).get("hover") is True, \
                        f"{aid} {f['type']} hover not True"


class TestDefaultThemeRadius20:
    def test_new_app_theme_radius_is_20(self, client):
        r = client.post(f"{BASE_URL}/api/apps", json={
            "name": "TEST_v8_radius_app",
            "industry": "Testing",
            "color": "#10B981",
        }, timeout=30)
        assert r.status_code in (200, 201), f"create app: {r.status_code} {r.text}"
        app = r.json()
        aid = app.get("app_id") or app.get("id")
        assert aid, f"app missing id: {app}"
        try:
            tr = client.get(f"{BASE_URL}/api/apps/{aid}/theme", timeout=30)
            assert tr.status_code == 200, f"theme: {tr.status_code} {tr.text}"
            theme = tr.json()
            assert theme.get("radius") == 20, f"radius not 20: {theme}"
            assert theme.get("motion") is True
            assert theme.get("cursor") is True
        finally:
            client.delete(f"{BASE_URL}/api/apps/{aid}", timeout=30)


class TestNexusPreviewToken:
    def test_nexus_public_preview_token(self, client):
        with open("/app/memory/nexus_id") as f:
            nexus_id = f.read().strip()
        r = client.get(f"{BASE_URL}/api/apps/{nexus_id}", timeout=30)
        assert r.status_code == 200
        data = r.json()
        token = data.get("preview_token")
        assert token, f"nexus missing preview_token: {list(data.keys())}"
        pr = requests.get(f"{BASE_URL}/api/public/site/{token}", timeout=30)
        assert pr.status_code == 200, f"public site: {pr.status_code}"
        site = pr.json()
        assert "pages" in site
        # Check first page blocks have effects
        pages = site["pages"]
        assert len(pages) > 0
        blocks = pages[0].get("blocks", [])
        assert any((b.get("style") or {}).get("effects", {}).get("reveal") is True for b in blocks), \
            "public preview: no block has effects.reveal=True"
