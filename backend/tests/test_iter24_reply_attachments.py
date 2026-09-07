"""Iter-24 backend tests: /apps/{id}/attachments upload + reply-with-attachments flow.

Covers:
 - POST /apps/{app_id}/attachments upload success (.txt/.png), size, url, name, content_type
 - Returned /api/public/files/... downloads content
 - .exe rejected 400
 - >15MB rejected 400
 - Unauthed 401 / no-access 403
 - POST /apps/{id}/inbox/{msg}/reply w/ attachments stored + retrievable
 - reply w/ empty body + attachment succeeds
 - reply w/ neither body nor attachment => 400
 - When lead has from_email, delivery flag == email_sent|email_queued and 'Attachments:' section appears in outgoing email body (indirectly: reply stored with attachments).
"""
import io
import os
import time
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


@pytest.fixture(scope="module")
def other_user():
    """A user with NO access to APP_ID → should get 403."""
    email = f"TEST_noaccess_{int(time.time())}@example.com"
    pw = "TestNoAccess2026!"
    reg = requests.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "TEST NoAccess"})
    if reg.status_code not in (200, 201):
        reg = requests.post(f"{API}/auth/signup", json={"email": email, "password": pw, "name": "TEST NoAccess"})
    if reg.status_code not in (200, 201):
        pytest.skip(f"cannot create user: {reg.status_code} {reg.text}")
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed: {r.status_code}")
    return s


@pytest.fixture(scope="module")
def a_message(admin):
    """Get one existing message on APP_ID (there are 8+ leads seeded)."""
    r = admin.get(f"{API}/apps/{APP_ID}/inbox")
    assert r.status_code == 200, r.text
    msgs = r.json().get("messages", [])
    if not msgs:
        pytest.skip("No messages in inbox to reply to")
    return msgs[0]


# ---------- Attachment upload ----------

class TestAttachmentUpload:
    def test_upload_txt_ok(self, admin):
        content = b"TEST_iter24 quote attachment content"
        r = admin.post(f"{API}/apps/{APP_ID}/attachments",
                       files={"file": ("TEST_quote.txt", content, "text/plain")})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] == "TEST_quote.txt"
        assert d["size"] == len(content)
        assert d["content_type"] == "text/plain"
        assert d["url"].startswith("/api/public/files/")
        # Verify download works
        dl = requests.get(BASE_URL + d["url"])
        assert dl.status_code == 200
        assert dl.content == content

    def test_upload_png_ok(self, admin):
        # 1x1 png
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
        r = admin.post(f"{API}/apps/{APP_ID}/attachments",
                       files={"file": ("TEST_pixel.png", png, "image/png")})
        assert r.status_code == 200, r.text
        assert r.json()["content_type"] == "image/png"

    def test_upload_exe_rejected(self, admin):
        r = admin.post(f"{API}/apps/{APP_ID}/attachments",
                       files={"file": ("TEST_bad.exe", b"MZ\x00", "application/octet-stream")})
        assert r.status_code == 400
        assert "Allowed" in r.text or "allowed" in r.text.lower() or "images" in r.text.lower()

    def test_upload_too_large_rejected(self, admin):
        big = b"a" * (15 * 1024 * 1024 + 100)
        r = admin.post(f"{API}/apps/{APP_ID}/attachments",
                       files={"file": ("TEST_big.txt", big, "text/plain")})
        assert r.status_code == 400
        assert "15" in r.text or "MB" in r.text or "under" in r.text.lower()

    def test_upload_unauthed_401(self):
        r = requests.post(f"{API}/apps/{APP_ID}/attachments",
                          files={"file": ("x.txt", b"x", "text/plain")})
        assert r.status_code in (401, 403), r.text

    def test_upload_no_access_403(self, other_user):
        r = other_user.post(f"{API}/apps/{APP_ID}/attachments",
                            files={"file": ("x.txt", b"x", "text/plain")})
        assert r.status_code == 403, r.text


# ---------- Reply with attachments ----------

class TestReplyAttachments:
    def test_reply_with_attachment_stored(self, admin, a_message):
        # Upload first
        up = admin.post(f"{API}/apps/{APP_ID}/attachments",
                        files={"file": ("TEST_mockup.txt", b"MOCKUP", "text/plain")}).json()
        r = admin.post(f"{API}/apps/{APP_ID}/inbox/{a_message['message_id']}/reply",
                       json={"body": "Here is the quote", "attachments": [{"name": up["name"], "url": up["url"]}]})
        assert r.status_code == 200, r.text
        msg = r.json()
        last = msg["replies"][-1]
        assert last["body"] == "Here is the quote"
        assert last["attachments"] == [{"name": "TEST_mockup.txt", "url": up["url"]}]
        # If lead has email, delivery should be email_sent or email_queued
        if a_message.get("from_email"):
            assert last["delivery"] in ("email_sent", "email_queued"), last

        # Re-GET the message to verify persistence
        g = admin.get(f"{API}/apps/{APP_ID}/inbox")
        found = next(m for m in g.json()["messages"] if m["message_id"] == a_message["message_id"])
        assert any(rp.get("attachments") for rp in found["replies"])

    def test_reply_empty_body_with_attachment_ok(self, admin, a_message):
        up = admin.post(f"{API}/apps/{APP_ID}/attachments",
                        files={"file": ("TEST_only.txt", b"ONLY", "text/plain")}).json()
        r = admin.post(f"{API}/apps/{APP_ID}/inbox/{a_message['message_id']}/reply",
                       json={"body": "", "attachments": [{"name": up["name"], "url": up["url"]}]})
        assert r.status_code == 200, r.text
        last = r.json()["replies"][-1]
        assert last.get("body", "") == ""
        assert last["attachments"][0]["name"] == "TEST_only.txt"

    def test_reply_empty_body_no_attachment_400(self, admin, a_message):
        r = admin.post(f"{API}/apps/{APP_ID}/inbox/{a_message['message_id']}/reply",
                       json={"body": "   ", "attachments": []})
        assert r.status_code == 400, r.text

    def test_reply_max_10_attachments(self, admin, a_message):
        atts = [{"name": f"f{i}.txt", "url": "/api/public/files/x/y.txt"} for i in range(15)]
        r = admin.post(f"{API}/apps/{APP_ID}/inbox/{a_message['message_id']}/reply",
                       json={"body": "many", "attachments": atts})
        assert r.status_code == 200, r.text
        last = r.json()["replies"][-1]
        assert len(last["attachments"]) == 10
