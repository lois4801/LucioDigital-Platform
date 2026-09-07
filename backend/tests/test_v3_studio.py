"""Tests for v3 studio: multi-page builder, theme, AI generate-site/app, public site + chat + tts."""
import io
import os
import time
import uuid
import zipfile
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200
    return s


@pytest.fixture(scope="module")
def app_id(admin):
    r = admin.post(f"{API}/apps", json={
        "name": "TEST_V3_" + uuid.uuid4().hex[:6],
        "industry": "Fitness Studios",
        "description": "v3 studio testing",
    }, timeout=20)
    assert r.status_code == 200
    aid = r.json()["app_id"]
    yield aid
    admin.delete(f"{API}/apps/{aid}", timeout=15)


# ============ PAGES ============
class TestPages:
    def test_list_pages_home_first(self, admin, app_id):
        r = admin.get(f"{API}/apps/{app_id}/pages", timeout=15)
        assert r.status_code == 200, r.text[:300]
        pages = r.json()
        assert len(pages) >= 1
        assert pages[0]["slug"] == "/"

    def test_create_page(self, admin, app_id):
        r = admin.post(f"{API}/apps/{app_id}/pages", json={"name": "Team", "slug": "team"}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["name"] == "Team"
        assert d["slug"] == "/team"
        assert len(d["blocks"]) >= 1

    def test_update_page_name_and_blocks(self, admin, app_id):
        pages = admin.get(f"{API}/apps/{app_id}/pages").json()
        team = next(p for p in pages if p["slug"] == "/team")
        r = admin.patch(f"{API}/apps/{app_id}/pages/{team['page_id']}",
                        json={"name": "Our Team",
                              "blocks": [{"type": "hero", "props": {"title": "Meet us"}}]},
                        timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["name"] == "Our Team"
        assert len(d["blocks"]) == 1
        assert d["blocks"][0]["id"].startswith("blk_")

    def test_delete_home_forbidden(self, admin, app_id):
        pages = admin.get(f"{API}/apps/{app_id}/pages").json()
        home = next(p for p in pages if p["slug"] == "/")
        r = admin.delete(f"{API}/apps/{app_id}/pages/{home['page_id']}", timeout=15)
        assert r.status_code == 400

    def test_delete_non_home_ok(self, admin, app_id):
        pages = admin.get(f"{API}/apps/{app_id}/pages").json()
        team = next(p for p in pages if p["slug"] == "/team")
        r = admin.delete(f"{API}/apps/{app_id}/pages/{team['page_id']}", timeout=15)
        assert r.status_code == 200
        pages2 = admin.get(f"{API}/apps/{app_id}/pages").json()
        assert not any(p["slug"] == "/team" for p in pages2)


# ============ THEME ============
class TestTheme:
    def test_get_theme_defaults(self, admin, app_id):
        r = admin.get(f"{API}/apps/{app_id}/theme", timeout=15)
        assert r.status_code == 200
        t = r.json()
        assert t["primary"] == "#F97316"
        assert t["mode"] == "light"

    def test_put_theme_radius_lg_coerce(self, admin, app_id):
        r = admin.put(f"{API}/apps/{app_id}/theme",
                      json={"theme": {"radius": "lg", "primary": "#123456", "secondary": "notacolor"}},
                      timeout=15)
        assert r.status_code == 200
        t = r.json()
        assert t["radius"] == 16
        assert t["primary"] == "#123456"
        # invalid color dropped -> falls back to default secondary
        assert t["secondary"] == "#14B8A6"


# ============ AI GENERATE SITE ============
class TestAIGenerateSite:
    def test_generate_site(self, admin, app_id):
        r = admin.post(f"{API}/apps/{app_id}/ai/generate-site",
                       json={"brief": "Boutique fitness studio in Austin",
                             "pages": ["Home", "Pricing"]},
                       timeout=300)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        pages = d["pages"]
        assert len(pages) >= 2
        home = pages[0]
        assert home["slug"] == "/"
        types = [b.get("type") for b in home["blocks"]]
        assert "navbar" in types, f"navbar missing on home: {types}"
        assert "footer" in types, f"footer missing on home: {types}"


# ============ AI GENERATE APP + EXPORT ============
class TestAIGenerateApp:
    def test_generate_app_and_blueprint_and_export(self, admin, app_id):
        r = admin.post(f"{API}/apps/{app_id}/ai/generate-app",
                       json={"brief": "Gym membership app with members, classes, payments"},
                       timeout=300)
        assert r.status_code == 200, r.text[:400]
        spec = r.json()
        assert spec.get("screens")
        assert spec.get("models")
        assert spec.get("api")

        # blueprint GET
        r2 = admin.get(f"{API}/apps/{app_id}/blueprint", timeout=15)
        assert r2.status_code == 200
        assert r2.json().get("screens")

        # export zip
        r3 = admin.get(f"{API}/apps/{app_id}/export/source", timeout=30)
        assert r3.status_code == 200
        z = zipfile.ZipFile(io.BytesIO(r3.content))
        names = z.namelist()
        assert "site/index.html" in names, names
        assert "site/styles.css" in names
        assert "app/backend/server.py" in names, names
        assert "app/frontend/src/App.jsx" in names
        assert "app/blueprint.json" in names


# ============ PUBLIC SITE + CHAT + TTS ============
class TestPublicSiteChat:
    @pytest.fixture(scope="class")
    def preview_token(self, admin, app_id):
        r = admin.post(f"{API}/apps/{app_id}/preview/regenerate", timeout=15)
        assert r.status_code == 200
        return r.json()["preview_token"]

    def test_public_site(self, preview_token):
        r = requests.get(f"{API}/public/site/{preview_token}", timeout=15)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "app" in d and "theme" in d and "pages" in d

    def test_chat_and_history(self, preview_token):
        sid = "qa1_" + uuid.uuid4().hex[:6]
        r = requests.post(f"{API}/public/chat/{preview_token}",
                          json={"session_id": sid, "message": "What services do you offer?"},
                          timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("reply")
        r2 = requests.post(f"{API}/public/chat/{preview_token}",
                           json={"session_id": sid, "message": "Do you have trials?"},
                           timeout=120)
        assert r2.status_code == 200
        h = requests.get(f"{API}/public/chat/{preview_token}/history/{sid}", timeout=15)
        assert h.status_code == 200
        msgs = h.json()
        assert len(msgs) >= 4, f"expected >=4 got {len(msgs)}"

    def test_chat_studio_token(self):
        sid = "studio_" + uuid.uuid4().hex[:6]
        r = requests.post(f"{API}/public/chat/studio",
                          json={"session_id": sid, "message": "What plans do you offer?"},
                          timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("reply")

    def test_tts(self):
        r = requests.post(f"{API}/public/tts", json={"text": "Hello from QA"}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        url = r.json()["audio_url"]
        assert url.startswith("/api/public/tts/") and url.endswith(".mp3")
        r2 = requests.get(f"{BASE_URL}{url}", timeout=30)
        assert r2.status_code == 200
        assert r2.headers.get("content-type") == "audio/mpeg"
        assert len(r2.content) > 500


# ============ REGRESSION: legacy /page ============
class TestLegacyPage:
    def test_legacy_page_still_returns_home(self, admin, app_id):
        r = admin.get(f"{API}/apps/{app_id}/page", timeout=15)
        assert r.status_code == 200
        page = r.json()
        assert "blocks" in page
