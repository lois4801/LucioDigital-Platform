"""V4 tests: Inbox/Leads, Chat embed, GitHub sync (mocked), Export additions, Seed uniqueness, kind filter."""
import io
import os
import re
import uuid
import zipfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, r.text[:300]
    return s


@pytest.fixture(scope="module")
def apps(admin):
    r = admin.get(f"{API}/apps", timeout=20)
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="module")
def nexus(apps):
    """Nexus Commerce seeded app."""
    a = next((x for x in apps if x.get("name") == "Nexus Commerce"), None)
    assert a, f"Nexus Commerce app not found. Names: {[x.get('name') for x in apps]}"
    return a


# ============ INBOX / LEADS ============
class TestInboxContact:
    def test_public_contact_creates_lead(self, admin, nexus):
        token = nexus["preview_token"]
        r = requests.post(f"{API}/public/contact/{token}",
                          json={"name": "QA Tester", "email": "qa-inbox@example.com",
                                "message": "Testing contact form v4", "subject": "QA subject"},
                          timeout=20)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("ok") is True
        mid = r.json().get("message_id")
        assert mid and mid.startswith("msg_")

        # verify appears in app inbox unread
        r2 = admin.get(f"{API}/apps/{nexus['app_id']}/inbox", timeout=20)
        assert r2.status_code == 200
        d = r2.json()
        assert d["unread"] >= 1
        found = next((m for m in d["messages"] if m["message_id"] == mid), None)
        assert found is not None
        assert found["status"] == "unread"
        assert found["source"] == "contact"
        assert found["from_email"] == "qa-inbox@example.com"

    def test_global_inbox_lists_with_app_name(self, admin, nexus):
        r = admin.get(f"{API}/inbox", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "messages" in d and "unread" in d
        assert d["unread"] >= 0
        # at least one message from nexus should have app_name
        nx_msgs = [m for m in d["messages"] if m["app_id"] == nexus["app_id"]]
        assert nx_msgs, "no nexus messages in global inbox"
        assert nx_msgs[0].get("app_name") == "Nexus Commerce"

    def test_patch_status_read_and_star(self, admin, nexus):
        r = admin.get(f"{API}/apps/{nexus['app_id']}/inbox", timeout=20).json()
        m = r["messages"][0]
        mid = m["message_id"]
        # read
        p = admin.patch(f"{API}/apps/{nexus['app_id']}/inbox/{mid}", json={"status": "read"}, timeout=15)
        assert p.status_code == 200
        assert p.json()["status"] == "read"
        # star
        p2 = admin.patch(f"{API}/apps/{nexus['app_id']}/inbox/{mid}", json={"starred": True}, timeout=15)
        assert p2.status_code == 200
        assert p2.json()["starred"] is True
        # invalid status
        p3 = admin.patch(f"{API}/apps/{nexus['app_id']}/inbox/{mid}", json={"status": "junk"}, timeout=15)
        assert p3.status_code == 400

    def test_reply_and_delete(self, admin, nexus):
        # Create a fresh contact lead so we can safely delete it
        token = nexus["preview_token"]
        r = requests.post(f"{API}/public/contact/{token}",
                          json={"name": "Delete Me", "email": "delme@example.com",
                                "message": "please delete"}, timeout=20)
        mid = r.json()["message_id"]
        # reply
        rr = admin.post(f"{API}/apps/{nexus['app_id']}/inbox/{mid}/reply",
                        json={"body": "Thanks for reaching out!"}, timeout=20)
        assert rr.status_code == 200
        body = rr.json()
        assert len(body["replies"]) >= 1
        assert body["replies"][-1]["body"].startswith("Thanks")
        assert body["status"] == "read"
        # archive
        pa = admin.patch(f"{API}/apps/{nexus['app_id']}/inbox/{mid}", json={"status": "archived"}, timeout=15)
        assert pa.status_code == 200
        # filter archived
        fa = admin.get(f"{API}/apps/{nexus['app_id']}/inbox?status=archived", timeout=15).json()
        assert any(m["message_id"] == mid for m in fa["messages"])
        # delete
        d = admin.delete(f"{API}/apps/{nexus['app_id']}/inbox/{mid}", timeout=15)
        assert d.status_code == 200


class TestChatLead:
    def test_chat_creates_lead_and_upserts(self, admin, nexus):
        token = nexus["preview_token"]
        sid = "lead-qa-" + uuid.uuid4().hex[:6]
        # first turn
        r = requests.post(f"{API}/public/chat/{token}",
                          json={"session_id": sid, "message": "Do you offer refunds?"},
                          timeout=60)
        assert r.status_code == 200, r.text[:300]
        # count chat msgs with this session_id
        inbox1 = admin.get(f"{API}/apps/{nexus['app_id']}/inbox", timeout=20).json()
        chat_msgs = [m for m in inbox1["messages"] if m.get("session_id") == sid]
        assert len(chat_msgs) == 1
        m1 = chat_msgs[0]
        assert m1["source"] == "chat"
        assert "Visitor:" in m1["body"]
        # second turn same session -> same doc, body appended
        r2 = requests.post(f"{API}/public/chat/{token}",
                           json={"session_id": sid, "message": "What about shipping speed?"},
                           timeout=60)
        assert r2.status_code == 200
        inbox2 = admin.get(f"{API}/apps/{nexus['app_id']}/inbox", timeout=20).json()
        chat_msgs2 = [m for m in inbox2["messages"] if m.get("session_id") == sid]
        assert len(chat_msgs2) == 1  # same doc
        assert chat_msgs2[0]["body"].count("Visitor:") == 2


# ============ CHAT EMBED ============
class TestEmbed:
    def test_embed_js(self):
        r = requests.get(f"{API}/public/embed.js", timeout=15)
        assert r.status_code == 200
        assert "javascript" in r.headers.get("content-type", "")
        assert "embed/chat/" in r.text


# ============ GITHUB SYNC ============
class TestGithub:
    def test_status_disconnected(self, admin):
        # Ensure disconnected for this test
        admin.delete(f"{API}/settings/github", timeout=15)
        r = admin.get(f"{API}/settings/github", timeout=15)
        assert r.status_code == 200
        assert r.json()["connected"] is False

    def test_invalid_token_rejected(self, admin):
        r = admin.post(f"{API}/settings/github",
                       json={"token": "ghp_invalidtoken12345678901234"}, timeout=30)
        assert r.status_code == 400

    def test_mocked_push(self, admin, nexus):
        r = admin.post(f"{API}/apps/{nexus['app_id']}/github/push", json={}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["status"] == "mocked"
        assert d["files"] > 0

    def test_autosync_toggle(self, admin, nexus):
        r = admin.post(f"{API}/apps/{nexus['app_id']}/github/autosync", json={"enabled": True}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("github_autosync") is True
        r2 = admin.post(f"{API}/apps/{nexus['app_id']}/github/autosync", json={"enabled": False}, timeout=15)
        assert r2.json().get("github_autosync") is False


# ============ EXPORT ADDITIONS ============
class TestExport:
    def test_export_nexus_has_site_mobile_and_embed(self, admin, nexus):
        r = admin.get(f"{API}/apps/{nexus['app_id']}/export/source", timeout=60)
        assert r.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        # site/index.html contains embed.js
        idx = next((n for n in names if n.endswith("site/index.html")), None)
        assert idx, f"site/index.html missing. names={names[:20]}"
        html = zf.read(idx).decode()
        assert "embed.js" in html
        # mobile artifacts
        assert any(n.endswith("mobile/capacitor.config.json") for n in names)
        assert any(n.endswith("mobile/README.md") for n in names)

    def test_export_blueprint_app_has_schema(self, admin):
        # Blueprint app_id from problem statement
        app_id = "app_627d86264eac"
        r = admin.get(f"{API}/apps/{app_id}/export/source", timeout=60)
        if r.status_code == 404:
            pytest.skip(f"blueprint app {app_id} not found in this env")
        assert r.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        schema = next((n for n in names if n.endswith("app/backend/schema.sql")), None)
        assert schema, f"schema.sql missing. subset={[n for n in names if 'app/' in n][:15]}"
        content = zf.read(schema).decode().lower()
        assert "create table" in content


# ============ SEED UNIQUENESS + KIND ============
class TestSeed:
    def test_apps_have_kind_and_unique_themes(self, apps):
        # Only look at seeded apps (skip TEST_* remnants from prior iterations)
        seeded = [a for a in apps if not a.get("name", "").startswith("TEST_")]
        assert len(seeded) >= 2
        for a in seeded:
            assert a.get("kind") in ("website", "app"), f"kind missing on {a.get('name')}: {a.get('kind')}"
        primaries = [(a.get("theme") or {}).get("primary") for a in seeded]
        primaries = [p for p in primaries if p]
        assert len(set(primaries)) >= max(2, len(primaries) - 1), f"themes not unique enough: {primaries}"

    def test_seeded_home_pages_have_media_blocks(self, admin, apps):
        seeded = [a for a in apps if not a.get("name", "").startswith("TEST_")]
        checked = 0
        for a in seeded[:6]:
            r = admin.get(f"{API}/apps/{a['app_id']}/pages", timeout=20)
            if r.status_code != 200:
                continue
            body = r.json()
            pages = body if isinstance(body, list) else body.get("pages", [])
            if len(pages) < 4:
                continue
            home = next((p for p in pages if (p.get("slug") in ("/", "") or p.get("is_home"))), pages[0])
            blocks = home.get("blocks", [])
            types = [b.get("type") for b in blocks]
            assert "navbar" in types, f"navbar missing in {a['name']}"
            # hero with image
            hero = next((b for b in blocks if b.get("type") == "hero"), None)
            assert hero, f"hero missing in {a['name']}"
            hero_img = (hero.get("props") or {}).get("image") or (hero.get("props") or {}).get("imageUrl")
            assert hero_img, f"hero image missing in {a['name']}"
            # video block
            video = next((b for b in blocks if b.get("type") == "video"), None)
            assert video, f"video block missing in {a['name']}"
            v_url = (video.get("props") or {}).get("url") or (video.get("props") or {}).get("src")
            assert v_url, f"video url missing in {a['name']}"
            # gallery
            assert "gallery" in types, f"gallery missing in {a['name']}"
            checked += 1
            if checked >= 2:
                break
        assert checked >= 2, f"only checked {checked} seeded apps"

    def test_create_app_kind_stored(self, admin):
        r = admin.post(f"{API}/apps",
                       json={"name": "TEST_v4_kind_" + uuid.uuid4().hex[:5],
                             "industry": "SaaS Portals", "kind": "app"}, timeout=20)
        assert r.status_code == 200
        aid = r.json()["app_id"]
        try:
            assert r.json().get("kind") == "app"
            # fetch again
            g = admin.get(f"{API}/apps/{aid}", timeout=15)
            assert g.json().get("kind") == "app"
        finally:
            admin.delete(f"{API}/apps/{aid}", timeout=15)
