"""Iteration 18: media upload + landing CMS text update (pricing/demo/bento keys)."""
import os
import io
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASS = "Lucio2026!"
APP_ID = "app_bdbf27abe643"

PNG_1x1 = bytes.fromhex(
    "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
    "890000000D49444154789C6300010000000500010D0A2DB40000000049454E44"
    "AE426082"
)


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def anon_session():
    return requests.Session()


# ---------------- media upload ----------------
class TestMediaUpload:
    def test_upload_png_ok(self, admin_session):
        r = admin_session.post(
            f"{BASE}/apps/{APP_ID}/media/upload",
            files={"file": ("qa.png", io.BytesIO(PNG_1x1), "image/png")},
        )
        assert r.status_code == 200, r.text
        url = r.json().get("url")
        assert url and url.startswith(f"/api/public/files/omnistack/images/{APP_ID}/"), url
        # Fetch via public endpoint (strip leading /api since BASE already has /api)
        full = BASE.rsplit("/api", 1)[0] + url
        g = requests.get(full)
        assert g.status_code == 200, g.status_code
        assert g.headers.get("content-type", "").startswith("image/")

    def test_upload_txt_rejected(self, admin_session):
        r = admin_session.post(
            f"{BASE}/apps/{APP_ID}/media/upload",
            files={"file": ("bad.txt", io.BytesIO(b"nope"), "text/plain")},
        )
        assert r.status_code == 400, r.text

    def test_upload_unauth_401(self, anon_session):
        r = anon_session.post(
            f"{BASE}/apps/{APP_ID}/media/upload",
            files={"file": ("qa.png", io.BytesIO(PNG_1x1), "image/png")},
        )
        assert r.status_code in (401, 403), r.status_code


# ---------------- landing CMS texts ----------------
class TestLandingCms:
    def test_admin_put_texts_persist(self, admin_session):
        payload = {"texts": {
            "pricing_1_price": "$129",
            "demo_0_video": "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "bento_0_title": "QA Bento",
        }}
        r = admin_session.put(f"{BASE}/admin/landing", json=payload)
        assert r.status_code == 200, r.text
        # GET public confirms persistence
        g = requests.get(f"{BASE}/public/landing")
        assert g.status_code == 200
        t = g.json()["texts"]
        assert t.get("pricing_1_price") == "$129"
        assert t.get("demo_0_video") == "https://www.youtube.com/embed/dQw4w9WgXcQ"
        assert t.get("bento_0_title") == "QA Bento"

    def test_unauth_put_rejected(self, anon_session):
        r = anon_session.put(f"{BASE}/admin/landing", json={"texts": {"pricing_1_price": "$1"}})
        assert r.status_code in (401, 403), r.status_code

    def test_restore_defaults(self, admin_session):
        payload = {"texts": {
            "pricing_1_price": "$99",
            "demo_0_video": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4",
            "bento_0_title": "Drag-and-drop builder",
        }}
        r = admin_session.put(f"{BASE}/admin/landing", json=payload)
        assert r.status_code == 200
        g = requests.get(f"{BASE}/public/landing").json()["texts"]
        assert g["pricing_1_price"] == "$99"
        assert g["bento_0_title"] == "Drag-and-drop builder"
