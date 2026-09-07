"""Iter-21 backend tests: chat attachment upload endpoints."""
import os
import io
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

APP_ID = "app_bdbf27abe643"


@pytest.fixture(scope="module")
def preview_token():
    # get preview token for app_bdbf27abe643 by logging in as admin, or fetch public info
    # Try login as admin then GET app
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"})
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code}")
    r = s.get(f"{API}/apps/{APP_ID}")
    assert r.status_code == 200, r.text
    tok = r.json().get("preview_token")
    enabled = r.json().get("preview_enabled")
    if not tok:
        pytest.skip("no preview_token on app")
    if not enabled:
        # enable preview
        s.put(f"{API}/apps/{APP_ID}", json={"preview_enabled": True})
    return tok


class TestStudioUpload:
    """POST /api/public/chat/studio/upload"""

    def test_upload_txt_ok(self):
        files = {"file": ("hello.txt", b"hello world", "text/plain")}
        r = requests.post(f"{API}/public/chat/studio/upload", files=files)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["filename"] == "hello.txt"
        assert data["url"].startswith("/api/public/files/")
        assert data["size"] == len(b"hello world")
        # Download the file
        dl = requests.get(f"{BASE_URL}{data['url']}")
        assert dl.status_code == 200
        assert dl.content == b"hello world"

    def test_upload_png_ok(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        files = {"file": ("t.png", png, "image/png")}
        r = requests.post(f"{API}/public/chat/studio/upload", files=files)
        assert r.status_code == 200, r.text
        assert r.json()["content_type"].startswith("image/")

    def test_upload_pdf_ok(self):
        pdf = b"%PDF-1.4\n%test"
        files = {"file": ("doc.pdf", pdf, "application/pdf")}
        r = requests.post(f"{API}/public/chat/studio/upload", files=files)
        assert r.status_code == 200, r.text
        assert r.json()["content_type"] == "application/pdf"

    def test_upload_disallowed_exe_400(self):
        files = {"file": ("bad.exe", b"MZ....", "application/octet-stream")}
        r = requests.post(f"{API}/public/chat/studio/upload", files=files)
        assert r.status_code == 400, r.text
        assert "Allowed" in r.text or "detail" in r.text.lower()

    def test_upload_too_large_400(self):
        big = b"a" * (10 * 1024 * 1024 + 10)
        files = {"file": ("big.txt", big, "text/plain")}
        r = requests.post(f"{API}/public/chat/studio/upload", files=files)
        assert r.status_code == 400, r.text
        assert "10" in r.text or "large" in r.text.lower() or "under" in r.text.lower()


class TestTenantUpload:
    """POST /api/public/chat/{token}/upload"""

    def test_upload_with_valid_token(self, preview_token):
        files = {"file": ("greet.txt", b"hi tenant", "text/plain")}
        r = requests.post(f"{API}/public/chat/{preview_token}/upload", files=files)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["filename"] == "greet.txt"
        # verify download
        dl = requests.get(f"{BASE_URL}{d['url']}")
        assert dl.status_code == 200
        assert dl.content == b"hi tenant"

    def test_upload_invalid_token_404(self):
        files = {"file": ("x.txt", b"x", "text/plain")}
        r = requests.post(f"{API}/public/chat/tok_does_not_exist_xyz/upload", files=files)
        assert r.status_code == 404, r.text


class TestChatFlowWithAttachment:
    def test_normal_chat_send_still_works(self):
        r = requests.post(f"{API}/public/chat/studio", json={"session_id": "s_test_iter21", "message": "hello"})
        assert r.status_code == 200, r.text
        assert "reply" in r.json()

    def test_history_endpoint(self):
        r = requests.get(f"{API}/public/chat/studio/history/s_test_iter21")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
