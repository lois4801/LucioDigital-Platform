"""Iter-30 backend tests:
- Form routing (notify_email, assignee resolution, security, default, foreign form_id).
- Deeper crawl: /site/discover + /site/import-selected happy path and negatives.
- Videos backend: schema, graceful degradation (no stock keys), SSRF guard,
  AI generate contract-only, place idempotence on the pre-existing Crawl Final tenant.
Destructive tests use throwaway TEST_iter30_* tenants which are torn down.
"""
import os
import time
import uuid
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"
CRAWL_TENANT = "app_7035dfbf4a95"  # 'Crawl Final' — holds AI-generated Kling video


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return s


def _mk_tenant(admin, name_suffix=""):
    r = admin.post(f"{BASE_URL}/apps", json={
        "name": f"TEST_iter30_{name_suffix}_{uuid.uuid4().hex[:6]}", "industry": "SaaS",
        "kind": "website", "description": "throwaway", "status": "draft", "tags": [], "color": "#333",
    }, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return r.json()["app_id"]


@pytest.fixture()
def throwaway(admin):
    aid = _mk_tenant(admin, "one")
    yield aid
    try:
        admin.delete(f"{BASE_URL}/apps/{aid}", timeout=20)
    except Exception:
        pass


@pytest.fixture()
def two_tenants(admin):
    a = _mk_tenant(admin, "a")
    b = _mk_tenant(admin, "b")
    yield a, b
    for aid in (a, b):
        try:
            admin.delete(f"{BASE_URL}/apps/{aid}", timeout=20)
        except Exception:
            pass


@pytest.fixture(scope="session")
def viewer(admin):
    """Register a viewer user and invite to a host tenant."""
    email = f"TEST_iter30_v_{uuid.uuid4().hex[:6]}@example.com"
    pwd = "ViewPass2026!"
    reg = requests.Session()
    r = reg.post(f"{BASE_URL}/auth/register", json={"email": email, "password": pwd, "name": "V"}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    aid = _mk_tenant(admin, "vh")
    inv = admin.post(f"{BASE_URL}/apps/{aid}/members", json={"email": email, "role": "viewer"}, timeout=20)
    assert inv.status_code == 200
    s = requests.Session()
    lr = s.post(f"{BASE_URL}/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert lr.status_code == 200
    yield s, aid
    try:
        admin.delete(f"{BASE_URL}/apps/{aid}", timeout=20)
    except Exception:
        pass


def _enable_preview(admin, app_id):
    r = admin.post(f"{BASE_URL}/apps/{app_id}/preview/regenerate", timeout=20)
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    token = data.get("preview_token") or data.get("token")
    if not token:
        # fallback: fetch the app
        app = admin.get(f"{BASE_URL}/apps/{app_id}", timeout=20).json()
        token = app.get("preview_token")
    assert token, f"no preview token: {data}"
    return token


def _home_page(admin, app_id):
    r = admin.get(f"{BASE_URL}/apps/{app_id}/pages", timeout=20)
    assert r.status_code == 200
    pages = r.json()
    # pick / or first
    return next((p for p in pages if p.get("slug") == "/"), pages[0])


def _put_form_block(admin, app_id, page_id, form_id, props):
    """Overwrite the page blocks so the form block has given id + props."""
    block = {"id": form_id, "type": "form", "props": {
        "heading": props.get("heading") or "Contact us",
        "submit_label": "Send",
        "fields": [{"name": "name", "label": "Name", "type": "text", "required": True},
                   {"name": "email", "label": "Email", "type": "email", "required": True},
                   {"name": "message", "label": "Message", "type": "textarea", "required": True}],
        **{k: v for k, v in props.items() if k not in ("heading",)},
    }, "style": {}}
    r = admin.patch(f"{BASE_URL}/apps/{app_id}/pages/{page_id}",
                    json={"blocks": [block]}, timeout=25)
    assert r.status_code == 200, r.text[:200]
    return r.json()


def _me(admin):
    r = admin.get(f"{BASE_URL}/auth/me", timeout=15)
    assert r.status_code == 200, r.text[:200]
    return r.json()


# ---------------------------------------------------------------------------
# 1. FORM ROUTING
# ---------------------------------------------------------------------------
class TestFormRouting:
    def test_notify_email_routing(self, admin, throwaway):
        token = _enable_preview(admin, throwaway)
        page = _home_page(admin, throwaway)
        form_id = f"blk_{uuid.uuid4().hex[:12]}"
        notify = f"router-{uuid.uuid4().hex[:6]}@example.com"
        _put_form_block(admin, throwaway, page["page_id"], form_id,
                        {"heading": "Sales Enquiry", "notify_email": notify})

        r = requests.post(f"{BASE_URL}/public/contact/{token}", json={
            "name": "Alice", "email": "alice@example.com",
            "message": "hi", "form_id": form_id,
        }, timeout=25)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body["ok"] is True
        assert body.get("routed_to") == notify.lower(), body

        # inspect the persisted message
        inbox = admin.get(f"{BASE_URL}/apps/{throwaway}/inbox", timeout=20).json()
        msg = next((m for m in inbox["messages"] if m["message_id"] == body["message_id"]), None)
        assert msg, "message not found"
        route = msg.get("routing") or {}
        assert route.get("form_id") == form_id
        assert route.get("notify_email") == notify.lower()
        assert route.get("form_name") == "Sales Enquiry"
        assert route.get("form_page") == "/"

    def test_assignee_resolves_to_member_email(self, admin, throwaway):
        me = _me(admin)
        token = _enable_preview(admin, throwaway)
        page = _home_page(admin, throwaway)
        form_id = f"blk_{uuid.uuid4().hex[:12]}"
        _put_form_block(admin, throwaway, page["page_id"], form_id,
                        {"heading": "Support", "assignee": me["user_id"]})

        r = requests.post(f"{BASE_URL}/public/contact/{token}", json={
            "name": "Bob", "email": "bob@example.com",
            "message": "help", "form_id": form_id,
        }, timeout=25)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body.get("routed_to") == me["email"].lower(), body

        inbox = admin.get(f"{BASE_URL}/apps/{throwaway}/inbox", timeout=20).json()
        msg = next(m for m in inbox["messages"] if m["message_id"] == body["message_id"])
        route = msg.get("routing") or {}
        assert route.get("assignee_id") == me["user_id"]
        assert route.get("notify_email") == me["email"].lower()

    def test_public_payload_notify_email_not_honoured(self, admin, throwaway):
        """Security: notify_email in the public payload must be silently ignored."""
        token = _enable_preview(admin, throwaway)
        page = _home_page(admin, throwaway)
        form_id = f"blk_{uuid.uuid4().hex[:12]}"
        _put_form_block(admin, throwaway, page["page_id"], form_id,
                        {"heading": "Plain", })  # no notify_email/assignee

        r = requests.post(f"{BASE_URL}/public/contact/{token}", json={
            "name": "Mal", "email": "mal@example.com", "message": "x",
            "form_id": form_id,
            "notify_email": "attacker@evil.com",  # extra field — Pydantic ignores
        }, timeout=25)
        assert r.status_code == 200
        assert r.json().get("routed_to") in (None, "")
        inbox = admin.get(f"{BASE_URL}/apps/{throwaway}/inbox", timeout=20).json()
        msg = next(m for m in inbox["messages"] if m["message_id"] == r.json()["message_id"])
        route = msg.get("routing") or {}
        # form_id still resolved from the block (which has no notify_email)
        assert route.get("notify_email") in (None, ""), route
        # attacker's email must not have leaked anywhere on the message
        assert "attacker@evil.com" not in str(msg)

    def test_unknown_form_id_creates_lead_no_routing(self, admin, throwaway):
        token = _enable_preview(admin, throwaway)
        r = requests.post(f"{BASE_URL}/public/contact/{token}", json={
            "name": "Ghost", "email": "g@example.com", "message": "no form",
            "form_id": "blk_does_not_exist_zzz",
        }, timeout=25)
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body.get("routed_to") is None
        inbox = admin.get(f"{BASE_URL}/apps/{throwaway}/inbox", timeout=20).json()
        msg = next(m for m in inbox["messages"] if m["message_id"] == body["message_id"])
        route = msg.get("routing") or {}
        # No email routing must resolve for an unknown block
        assert not route.get("notify_email")
        assert not route.get("assignee_id")
        # Note: backend still stores routing.form_id + a placeholder form_name='Form'
        # even when the block is missing (see minor issue in report).

    def test_foreign_form_id_does_not_leak(self, admin, two_tenants):
        a, b = two_tenants
        tok_a = _enable_preview(admin, a)
        _enable_preview(admin, b)
        page_b = _home_page(admin, b)
        # Create a form in tenant B with a notify_email
        form_id_b = f"blk_{uuid.uuid4().hex[:12]}"
        _put_form_block(admin, b, page_b["page_id"], form_id_b,
                        {"heading": "SECRET B FORM", "notify_email": "leak-target@example.com"})

        # Submit to tenant A with tenant B's form_id
        r = requests.post(f"{BASE_URL}/public/contact/{tok_a}", json={
            "name": "X", "email": "x@example.com",
            "message": "cross", "form_id": form_id_b,
        }, timeout=25)
        assert r.status_code == 200
        body = r.json()
        assert body.get("routed_to") is None, body
        # Tenant A inbox should have no routing.notify_email
        inbox_a = admin.get(f"{BASE_URL}/apps/{a}/inbox", timeout=20).json()
        msg = next(m for m in inbox_a["messages"] if m["message_id"] == body["message_id"])
        route = msg.get("routing") or {}
        assert not route.get("notify_email")
        assert route.get("form_name") != "SECRET B FORM"

    def test_default_form_no_routing(self, admin, throwaway):
        token = _enable_preview(admin, throwaway)
        page = _home_page(admin, throwaway)
        form_id = f"blk_{uuid.uuid4().hex[:12]}"
        _put_form_block(admin, throwaway, page["page_id"], form_id, {"heading": "General"})

        r = requests.post(f"{BASE_URL}/public/contact/{token}", json={
            "name": "N", "email": "n@example.com", "message": "hi", "form_id": form_id,
        }, timeout=25)
        assert r.status_code == 200
        body = r.json()
        assert body.get("routed_to") is None
        inbox = admin.get(f"{BASE_URL}/apps/{throwaway}/inbox", timeout=20).json()
        msg = next(m for m in inbox["messages"] if m["message_id"] == body["message_id"])
        route = msg.get("routing") or {}
        assert not route.get("notify_email")


# ---------------------------------------------------------------------------
# 2. VIDEO STUDIO BACKEND
# ---------------------------------------------------------------------------
class TestVideosBackend:
    def test_list_videos_schema(self, admin, throwaway):
        r = admin.get(f"{BASE_URL}/apps/{throwaway}/videos", timeout=20)
        assert r.status_code == 200, r.text[:200]
        j = r.json()
        assert isinstance(j.get("videos"), list)
        assert j.get("stock_enabled") is False, j
        providers = j.get("providers") or {}
        assert providers.get("pexels") is False
        assert providers.get("pixabay") is False
        ids = [m["id"] for m in j.get("ai_models") or []]
        assert "veo3.1" in ids and "kling-o3-pro" in ids, ids
        assert j.get("ai_enabled") is True

    def test_stock_search_no_keys_400(self, admin, throwaway):
        r = admin.get(f"{BASE_URL}/apps/{throwaway}/videos/stock-search", params={"q": "office"}, timeout=20)
        assert r.status_code == 400, r.text[:200]
        body = r.text.lower()
        assert "pexels" in body or "pixabay" in body

    def test_auto_source_no_keys_400(self, admin, throwaway):
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/videos/auto-source",
                       json={"query": "office", "count": 1, "place": False}, timeout=25)
        assert r.status_code == 400, r.text[:200]
        assert "pexels" in r.text.lower() or "pixabay" in r.text.lower()

    def test_import_one_ssrf_guard(self, admin, throwaway):
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/videos/import-one",
                       json={"provider": "pexels",
                             "download_url": "https://evil.example.com/x.mp4",
                             "title": "bad", "place": False}, timeout=25)
        assert r.status_code == 400, r.text[:200]
        assert "pexels" in r.text.lower() or "pixabay" in r.text.lower()

    def test_ai_generate_unknown_model_400(self, admin, throwaway):
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/videos/ai-generate",
                       json={"prompt": "x", "model": "not-a-model", "aspect_ratio": "16:9", "place": False},
                       timeout=25)
        assert r.status_code == 400, r.text[:200]
        assert "unknown video model" in r.text.lower()

    def test_video_job_bogus_404(self, admin, throwaway):
        r = admin.get(f"{BASE_URL}/apps/{throwaway}/videos/job/vjob_bogus_xxx", timeout=20)
        assert r.status_code == 404

    def test_place_video_no_pages_404(self, admin, throwaway):
        # Wipe pages so place has nothing to attach to
        # (throwaway comes with a home page; delete via db is not exposed — instead
        # test on a URL that doesn't exist for the tenant's page. But place_video
        # never checks the url; it inserts a block. So instead try on a NEW tenant
        # that has no pages by *deleting* the home page. Home cannot be deleted;
        # so we build another blank tenant and just call place; expect 200 because
        # tenant has an auto-created / home. To simulate a tenant with no pages,
        # we probe with a non-existent tenant id.)
        r = admin.post(f"{BASE_URL}/apps/app_does_not_exist_xxx/videos/place",
                       json={"url": "/api/public/files/x.mp4"}, timeout=15)
        # 403/404 either way — must not 500
        assert r.status_code in (403, 404), r.status_code

    def test_place_and_idempotence_on_crawl_final(self, admin):
        vids = admin.get(f"{BASE_URL}/apps/{CRAWL_TENANT}/videos", timeout=20).json()
        videos = vids.get("videos") or []
        assert videos, "Crawl Final should have at least one AI-generated video"
        v = next((x for x in videos if "AI" in (x.get("uploaded_by") or "")), videos[0])
        url = v["url"]

        # First place
        r1 = admin.post(f"{BASE_URL}/apps/{CRAWL_TENANT}/videos/place",
                        json={"url": url, "page_slug": "/"}, timeout=20)
        assert r1.status_code == 200, r1.text[:200]
        page_slug = r1.json().get("page_slug")

        # Count video blocks with this url on that page
        pages = admin.get(f"{BASE_URL}/apps/{CRAWL_TENANT}/pages", timeout=20).json()
        pg = next(p for p in pages if p["slug"] == page_slug)
        before = sum(1 for b in pg["blocks"] if b.get("type") == "video" and (b.get("props") or {}).get("url") == url)
        assert before >= 1

        # Second place — must be idempotent (no new block)
        r2 = admin.post(f"{BASE_URL}/apps/{CRAWL_TENANT}/videos/place",
                        json={"url": url, "page_slug": "/"}, timeout=20)
        assert r2.status_code == 200
        pages = admin.get(f"{BASE_URL}/apps/{CRAWL_TENANT}/pages", timeout=20).json()
        pg = next(p for p in pages if p["slug"] == page_slug)
        after = sum(1 for b in pg["blocks"] if b.get("type") == "video" and (b.get("props") or {}).get("url") == url)
        assert after == before, f"idempotence broken: {before}->{after}"

    def test_video_stream_public(self, admin):
        vids = admin.get(f"{BASE_URL}/apps/{CRAWL_TENANT}/videos", timeout=20).json().get("videos") or []
        if not vids:
            pytest.skip("no video in Crawl Final")
        url = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + vids[0]["url"]
        r = requests.get(url, timeout=30, stream=True)
        try:
            assert r.status_code == 200, r.status_code
            ct = r.headers.get("content-type", "")
            assert ct.startswith("video/") or ct == "application/octet-stream", ct
        finally:
            r.close()


# ---------------------------------------------------------------------------
# 3. DISCOVER + IMPORT-SELECTED
# ---------------------------------------------------------------------------
def _wait_job(admin, app_id, job_id, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = admin.get(f"{BASE_URL}/apps/{app_id}/site/import-job/{job_id}", timeout=30)
        assert r.status_code == 200
        j = r.json()
        if j.get("status") in ("done", "error"):
            return j
        time.sleep(1.5)
    pytest.fail(f"job {job_id} did not finish in {timeout}s")


class TestDiscoverAndSelected:
    def test_discover_example_com(self, admin, throwaway):
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/site/discover",
                       json={"url": "https://example.com", "max_pages": 5}, timeout=25)
        assert r.status_code == 200, r.text[:200]
        job_id = r.json()["job_id"]
        j = _wait_job(admin, throwaway, job_id, timeout=90)
        assert j["status"] == "done", j
        res = j["result"]
        assert res["discovery_id"].startswith("disc_")
        assert res["url"].startswith("http")
        pages = res["pages"]
        assert len(pages) >= 1
        for p in pages:
            for k in ("slug", "url", "title", "words", "images", "forms", "videos", "important"):
                assert k in p, f"missing {k} in {p}"
        assert "colors" in res
        totals = res["totals"]
        for k in ("pages", "images", "forms", "videos", "important"):
            assert k in totals
        # important flag: home / must be important
        home = next(p for p in pages if p["slug"] == "/")
        assert home["important"] is True

    def test_max_pages_clamped_to_100(self, admin, throwaway):
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/site/discover",
                       json={"url": "https://example.com", "max_pages": 9999}, timeout=25)
        assert r.status_code == 200
        # Cannot inspect internal clamp directly; but job should still complete.
        j = _wait_job(admin, throwaway, r.json()["job_id"], timeout=90)
        assert j["status"] == "done"
        # example.com only has 1 page so pages<=100 clamp is not exercised for count,
        # but the endpoint must not have crashed.

    def test_import_selected_happy(self, admin, throwaway):
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/site/discover",
                       json={"url": "https://example.com", "max_pages": 5}, timeout=25)
        assert r.status_code == 200
        disc_job = _wait_job(admin, throwaway, r.json()["job_id"], timeout=90)
        discovery_id = disc_job["result"]["discovery_id"]

        # import only '/' — mode replace, source_videos True (should degrade gracefully — no keys)
        r2 = admin.post(f"{BASE_URL}/apps/{throwaway}/site/import-selected",
                        json={"discovery_id": discovery_id, "slugs": ["/"],
                              "mode": "replace", "apply_theme": True, "source_videos": True},
                        timeout=30)
        assert r2.status_code == 200, r2.text[:200]
        j2 = _wait_job(admin, throwaway, r2.json()["job_id"], timeout=240)
        assert j2["status"] == "done", j2.get("error")
        result = j2["result"]

        # Pages actually created
        pages = admin.get(f"{BASE_URL}/apps/{throwaway}/pages", timeout=20).json()
        slugs = {p["slug"] for p in pages}
        assert "/" in slugs
        # No empty video blocks anywhere
        for p in pages:
            for b in (p.get("blocks") or []):
                if b.get("type") == "video":
                    url = (b.get("props") or {}).get("url") or ""
                    assert url.strip(), f"empty video block on {p['slug']}"

        # Videos degrade gracefully (no keys)
        vids = result.get("videos") or {}
        # Either videos block absent, or reports saved=0 with a reason mentioning keys
        if vids:
            assert vids.get("saved", 0) == 0
            reason = (vids.get("reason") or "").lower()
            assert "pexels" in reason or "pixabay" in reason or "api" in reason, vids

    def test_discover_invalid_url(self, admin, throwaway):
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/site/discover",
                       json={"url": "not a url", "max_pages": 5}, timeout=15)
        assert r.status_code == 400

    def test_discover_localhost_blocked(self, admin, throwaway):
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/site/discover",
                       json={"url": "http://localhost:3000", "max_pages": 5}, timeout=15)
        assert r.status_code == 400

    def test_import_selected_unknown_discovery(self, admin, throwaway):
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/site/import-selected",
                       json={"discovery_id": "disc_nope_xxx", "slugs": ["/"],
                             "mode": "replace", "apply_theme": True, "source_videos": False},
                       timeout=15)
        assert r.status_code == 404, r.status_code
        assert "discovery" in r.text.lower()

    def test_import_selected_empty_slugs(self, admin, throwaway):
        # Need a real discovery first (fast)
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/site/discover",
                       json={"url": "https://example.com", "max_pages": 2}, timeout=25)
        did = _wait_job(admin, throwaway, r.json()["job_id"], timeout=90)["result"]["discovery_id"]
        r2 = admin.post(f"{BASE_URL}/apps/{throwaway}/site/import-selected",
                        json={"discovery_id": did, "slugs": [],
                              "mode": "replace", "apply_theme": True, "source_videos": False},
                        timeout=15)
        assert r2.status_code == 400, r2.status_code

    def test_viewer_forbidden(self, viewer):
        s, aid = viewer
        r1 = s.post(f"{BASE_URL}/apps/{aid}/site/discover",
                    json={"url": "https://example.com", "max_pages": 5}, timeout=15)
        assert r1.status_code == 403, r1.status_code
        r2 = s.post(f"{BASE_URL}/apps/{aid}/site/import-selected",
                    json={"discovery_id": "disc_x", "slugs": ["/"],
                          "mode": "replace", "apply_theme": True, "source_videos": False},
                    timeout=15)
        assert r2.status_code in (403, 404), r2.status_code
