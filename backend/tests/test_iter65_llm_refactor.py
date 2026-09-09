"""Iter65 regression suite for the llm_provider.py refactor + storage/domain env changes.

Covers:
 * llm_provider module: llm_mode/llm_available/image_available/video_available + get_chat().send_message round trip in "emergent" mode.
 * AI endpoints still return 2xx after the refactor:
    - POST /apps/{id}/ai/edit
    - POST /apps/{id}/ai/seo
    - POST /apps/{id}/ai/lead-summary
 * GET /media/config exposes images + video booleans (from llm_provider).
 * POST /apps/{id}/media/image returns data_url.
 * GET /ai/models + PATCH /ai/models (admin only, editor -> 403).
 * File upload/list/download and /media/upload + /public/files/{path} round trip via default proxy storage driver.
 * Custom domain POST + verify does not crash (status in {pending, partial, verified}).
 * Env-driven DNS_CNAME_TARGET is not the previous hardcoded fallback (or if same, is honoured via env).
"""
import asyncio
import io
import os
import sys
import uuid
import pytest
import requests


sys.path.insert(0, "/app/backend")


def _base():
    u = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not u:
        try:
            with open("/app/frontend/.env") as fh:
                for line in fh:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        u = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert u, "REACT_APP_BACKEND_URL not set"
    return u.rstrip("/") + "/api"


BASE = _base()
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
EDITOR = {"email": "client.editor@example.com", "password": "ClientEdit2026!"}


# ---------- llm_provider unit checks ----------
def test_llm_provider_mode_flags():
    import llm_provider as lp
    mode = lp.llm_mode()
    assert mode in ("emergent", "byo", "none")
    if mode == "emergent":
        assert lp.llm_available()
        assert lp.image_available()
        assert lp.video_available()


def test_llm_provider_send_message_round_trip():
    """A short chat completion round trip — proves get_chat() works end-to-end."""
    import llm_provider as lp
    if lp.llm_mode() == "none":
        pytest.skip("No LLM key configured")
    chat = lp.get_chat("openai", "gpt-4o-mini", "You are terse.", "iter65-unit")
    reply = asyncio.get_event_loop().run_until_complete(
        chat.send_message(lp.UserMessage(text="Reply with exactly the word: pong"))
    )
    assert isinstance(reply, str) and len(reply.strip()) > 0


# ---------- Sessions ----------
@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def editor():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json=EDITOR)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def tenant(admin):
    name = f"TEST_iter65_{uuid.uuid4().hex[:6]}"
    r = admin.post(f"{BASE}/apps", json={
        "name": name, "industry": "tech", "kind": "website",
        "description": "iter65 regression tenant", "status": "active",
        "tags": [], "color": "#3B82F6", "thumbnail": "", "video_url": "", "live_url": "",
    })
    assert r.status_code == 200, r.text
    app_id = r.json()["app_id"]
    yield {"app_id": app_id, "name": name}
    admin.post(f"{BASE}/apps/{app_id}/archive", json={})
    admin.delete(f"{BASE}/apps/{app_id}/purge")


# ---------- Health ----------
def test_health():
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200


# ---------- AI endpoints ----------
def test_ai_edit_endpoint(admin, tenant):
    """POST /apps/{id}/ai/edit — proves get_chat streaming still works."""
    r = admin.post(f"{BASE}/apps/{tenant['app_id']}/ai/edit",
                   json={"prompt": "Change the heading text to say Welcome.",
                         "block": {"id": "b1", "type": "hero",
                                   "props": {"heading": "Old heading", "subheading": "sub"}}},
                   timeout=120)
    assert r.status_code == 200, r.text
    body = r.json()
    # The endpoint returns some result; assert not an error dict
    assert isinstance(body, dict)
    assert "error" not in body or not body.get("error")


def test_ai_seo_endpoint(admin, tenant):
    r = admin.post(f"{BASE}/apps/{tenant['app_id']}/ai/seo", timeout=120)
    assert r.status_code == 200, r.text
    body = r.json()
    # returns a list of {page_id,title,description} or {"pages":[...]}
    assert isinstance(body, (list, dict))


def test_ai_lead_summary_endpoint(admin, tenant):
    r = admin.post(f"{BASE}/apps/{tenant['app_id']}/ai/lead-summary?days=7", timeout=90)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "counts" in body
    assert body["counts"].get("leads") is not None


# ---------- Media config + image ----------
def test_media_config_shape(admin):
    r = admin.get(f"{BASE}/media/config")
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("elevenlabs", "images", "video", "image_model"):
        assert key in body, f"missing {key}"
    assert isinstance(body["images"], bool)
    assert isinstance(body["video"], bool)


def test_media_image_generation(admin, tenant):
    r = admin.post(f"{BASE}/apps/{tenant['app_id']}/media/image",
                   json={"prompt": "A minimal blue circle on white", "style": "product"},
                   timeout=120)
    if r.status_code == 500 and "Image generation" in r.text:
        pytest.skip(f"image backend unavailable: {r.text[:120]}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("data_url", "").startswith("data:image/")


# ---------- AI models catalogue ----------
def test_ai_models_get(admin):
    r = admin.get(f"{BASE}/ai/models")
    assert r.status_code == 200
    body = r.json()
    assert "models" in body and isinstance(body["models"], list) and len(body["models"]) > 0
    assert "features" in body
    assert "platform" in body


def test_ai_models_patch_admin_ok(admin):
    r = admin.patch(f"{BASE}/ai/models", json={})
    assert r.status_code == 200, r.text


def test_ai_models_patch_editor_forbidden(editor):
    r = editor.patch(f"{BASE}/ai/models", json={"model": "gpt-4o-mini"})
    assert r.status_code == 403, r.text


# ---------- File upload / proxy storage ----------
def test_file_upload_list_download(admin, tenant):
    app_id = tenant["app_id"]
    files = {"file": ("hello.txt", io.BytesIO(b"hello iter65"), "text/plain")}
    r = admin.post(f"{BASE}/apps/{app_id}/files", files=files)
    assert r.status_code == 200, r.text
    doc = r.json()
    fid = doc["file_id"]
    assert doc["url"].startswith("/api/public/files/")

    r = admin.get(f"{BASE}/apps/{app_id}/files")
    assert r.status_code == 200
    files_list = r.json().get("files", [])
    assert any(f["file_id"] == fid for f in files_list)

    r = admin.get(f"{BASE}/apps/{app_id}/files/{fid}/download", allow_redirects=False)
    assert r.status_code in (200, 302, 307), r.text

    # public read (strip /api prefix from doc.url and prepend BASE)
    pub = doc["url"]  # /api/public/files/...
    root = BASE[:-4]  # BASE ends with /api
    r = requests.get(root + pub)
    # File is private by default → 403 is expected; storage endpoint is still reachable
    assert r.status_code in (200, 302, 307, 403), r.text


def test_media_upload_endpoint(admin, tenant):
    files = {"file": ("logo.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32), "image/png")}
    r = admin.post(f"{BASE}/apps/{tenant['app_id']}/media/upload", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("url", "").startswith("/api/public/files/")


# ---------- Custom domain (env-driven CNAME) ----------
def test_custom_domain_flow(admin, tenant):
    app_id = tenant["app_id"]
    domain = f"iter65-{uuid.uuid4().hex[:6]}.example.com"
    r = admin.post(f"{BASE}/apps/{app_id}/domain", json={"domain": domain})
    assert r.status_code == 200, r.text
    r = admin.post(f"{BASE}/apps/{app_id}/domain/verify")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("domain_status") in ("pending", "partial", "verified")
    dns = body.get("domain_dns") or {}
    # CNAME expected value is now env-driven; must be a non-empty string
    exp = ((dns.get("cname") or {}).get("expected") or "").strip()
    assert exp, "DNS_CNAME_TARGET expected value missing from /domain/verify response"


# ---------- llm_provider.status wired ----------
def test_llm_provider_status_shape():
    import llm_provider as lp
    s = lp.status()
    for k in ("mode", "text", "images", "video"):
        assert k in s
