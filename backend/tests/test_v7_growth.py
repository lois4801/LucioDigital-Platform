"""v7 growth tests: AI gating for clients, magic link, analytics, export effects/cursor, AI blog writer, portal invites."""
import os
import io
import re
import time
import zipfile
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://app-showcase-pro-4.preview.emergentagent.com"
# Test uses this backend directly (comes from /app/frontend/.env)
API = f"{BASE_URL}/api"

OWNER_EMAIL = "jaybernabe@luciodigital.com"
OWNER_PW = "Lucio2026!"
CLIENT_EMAIL = "client.qa@example.com"

with open("/app/memory/nexus_id") as f:
    NEXUS_ID = f.read().strip()

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def owner_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PW}, timeout=30)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def preview_token(owner_session):
    r = owner_session.get(f"{API}/apps/{NEXUS_ID}", timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json().get("preview_token")
    # Ensure preview enabled
    if not r.json().get("preview_enabled"):
        owner_session.patch(f"{API}/apps/{NEXUS_ID}", json={"preview_enabled": True})
    assert tok
    return tok


@pytest.fixture(scope="module")
def client_session(owner_session, db):
    # Send invite for client.qa@example.com (viewer)
    r = owner_session.post(f"{API}/apps/{NEXUS_ID}/portal/invite",
                           json={"email": CLIENT_EMAIL, "role": "viewer"}, timeout=30)
    assert r.status_code == 200, r.text
    # Find latest magic link token in Mongo for that user
    u = db.users.find_one({"email": CLIENT_EMAIL})
    assert u is not None
    ml = db.magic_links.find({"user_id": u["user_id"]}).sort("created_at", -1).limit(1)
    ml = list(ml)
    assert ml, "no magic link found"
    token = ml[0]["token"]
    # Follow magic link WITHOUT auto redirect to keep cookies
    s = requests.Session()
    r = s.get(f"{API}/auth/magic/{token}", allow_redirects=False, timeout=30)
    assert r.status_code in (302, 307), r.status_code
    assert "/portal" in r.headers.get("location", "")
    # Cookie(s) should be set
    assert "access_token" in s.cookies or any("access_token" in c.name for c in s.cookies)
    return s


# ===== 1. AI gating =====
class TestAIGating:
    def test_client_ai_edit_forbidden(self, client_session):
        r = client_session.post(f"{API}/apps/{NEXUS_ID}/ai/edit",
                                json={"prompt": "make hero blue", "block": {"type": "hero", "props": {}}}, timeout=30)
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text[:200]}"
        assert "agency" in r.text.lower()

    def test_client_media_image_forbidden(self, client_session):
        r = client_session.post(f"{API}/apps/{NEXUS_ID}/media/image",
                                json={"prompt": "sunset", "count": 1}, timeout=30)
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text[:200]}"

    def test_client_pages_allowed(self, client_session):
        r = client_session.get(f"{API}/apps/{NEXUS_ID}/pages", timeout=30)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)


# ===== 2. Magic link =====
class TestMagicLink:
    def test_magic_link_second_use_invalid(self, owner_session, db):
        # Use a NEW invite so we control the token
        owner_session.post(f"{API}/apps/{NEXUS_ID}/portal/invite",
                           json={"email": "client.qa2@example.com", "role": "viewer"}, timeout=30)
        u = db.users.find_one({"email": "client.qa2@example.com"})
        ml = list(db.magic_links.find({"user_id": u["user_id"]}).sort("created_at", -1).limit(1))
        token = ml[0]["token"]
        s1 = requests.Session()
        r1 = s1.get(f"{API}/auth/magic/{token}", allow_redirects=False, timeout=30)
        assert r1.status_code in (302, 307)
        assert "/portal" in r1.headers.get("location", "")
        cookies_set = "set-cookie" in {k.lower() for k in r1.headers.keys()}
        assert cookies_set
        # Second use
        s2 = requests.Session()
        r2 = s2.get(f"{API}/auth/magic/{token}", allow_redirects=False, timeout=30)
        assert r2.status_code in (302, 307)
        assert "magic_link_invalid" in r2.headers.get("location", "")


# ===== 3. Analytics =====
class TestAnalytics:
    def test_track_and_read(self, owner_session, preview_token):
        r = requests.post(f"{API}/public/track/{preview_token}",
                          json={"path": "/pricing", "event": "view", "session": "qa-x"}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        time.sleep(0.5)
        a = owner_session.get(f"{API}/apps/{NEXUS_ID}/analytics", timeout=30)
        assert a.status_code == 200, a.text
        data = a.json()
        assert data.get("views", 0) >= 1
        paths = [t["path"] for t in data.get("top_pages", [])]
        assert "/pricing" in paths
        for k in ("visitors", "chat_conversations", "leads", "daily"):
            assert k in data


# ===== 4. Export with fx/cursor =====
class TestExport:
    def _download_zip(self, session):
        r = session.get(f"{API}/apps/{NEXUS_ID}/export/source", timeout=60)
        assert r.status_code == 200, r.text
        return zipfile.ZipFile(io.BytesIO(r.content))

    def _index_html(self, zf):
        names = [n for n in zf.namelist() if n.endswith("site/index.html") or n == "site/index.html"]
        assert names, f"no site/index.html in {zf.namelist()[:20]}"
        return zf.read(names[0]).decode()

    def test_export_default_has_fx_and_cursor(self, owner_session):
        # Ensure theme motion/cursor on
        owner_session.put(f"{API}/apps/{NEXUS_ID}/theme",
                          json={"theme": {"motion": True, "cursor": True}}, timeout=30)
        zf = self._download_zip(owner_session)
        html = self._index_html(zf)
        assert "fx-reveal" in html
        assert "os-cur" in html

    def test_export_theme_off_removes_fx(self, owner_session):
        owner_session.put(f"{API}/apps/{NEXUS_ID}/theme",
                          json={"theme": {"motion": False, "cursor": False}}, timeout=30)
        zf = self._download_zip(owner_session)
        html = self._index_html(zf)
        # Ensure no block <div> has fx-reveal class (script may still reference selector)
        div_classes = re.findall(r"<div class='([^']*)'", html)
        assert not any("fx-reveal" in c for c in div_classes), f"unexpected fx-reveal in {div_classes[:5]}"
        assert "data-cursor='off'" in html or 'data-cursor="off"' in html
        # Restore
        owner_session.put(f"{API}/apps/{NEXUS_ID}/theme",
                          json={"theme": {"motion": True, "cursor": True}}, timeout=30)


# ===== 5. AI blog writer (ONCE) =====
class TestAIBlog:
    def test_ai_write_once(self, owner_session, db):
        cols = owner_session.get(f"{API}/apps/{NEXUS_ID}/cms", timeout=30).json()
        blog = next((c for c in cols if c["slug"] == "blog"), None) or cols[0]
        r = owner_session.post(f"{API}/apps/{NEXUS_ID}/cms/{blog['collection_id']}/ai-write",
                               json={"topic": "Why headless commerce beats monoliths",
                                     "with_cover": False}, timeout=300)
        assert r.status_code == 200, r.text[:500]
        item = r.json()
        assert item.get("title")
        assert len(item.get("body", "")) > 300
        assert item.get("published") is False
        assert item.get("ai_generated") is True


# ===== 6. Portal invite endpoint response =====
class TestPortalInvite:
    def test_invite_ok(self, owner_session):
        r = owner_session.post(f"{API}/apps/{NEXUS_ID}/portal/invite",
                               json={"email": "qa.invite@example.com", "role": "viewer"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        assert "delivery" in d
