"""v6 tests: CMS, Portal, Workflow Templates, Brief Upload."""
import io
import os
import time
import zipfile
import pytest
import requests

def _get_base():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        with open("/app/frontend/.env") as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    url = line.split("=", 1)[1].strip()
                    break
    return url.rstrip("/") + "/api"

BASE = _get_base()
EMAIL = "jaybernabe@luciodigital.com"
PASS = "Lucio2026!"

with open("/app/memory/nexus_id") as f:
    NEXUS = f.read().strip()
BLUEPRINT_APP = "app_627d86264eac"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASS})
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    if tok:
        sess.headers["Authorization"] = f"Bearer {tok}"
    return sess


# ===== CMS =====
class TestCMS:
    def test_list_defaults(self, s):
        r = s.get(f"{BASE}/apps/{NEXUS}/cms")
        assert r.status_code == 200, r.text
        cols = r.json()
        slugs = {c["slug"] for c in cols}
        assert "blog" in slugs and "case-studies" in slugs
        # keep collection ids for reuse
        blog = next(c for c in cols if c["slug"] == "blog")
        assert isinstance(blog["items"], list)
        pytest.blog_col_id = blog["collection_id"]

    def test_create_update_delete_item(self, s):
        cid = pytest.blog_col_id
        # CREATE
        r = s.post(f"{BASE}/apps/{NEXUS}/cms/{cid}/items", json={
            "title": "TEST_v6 Post", "excerpt": "hello", "body": "world body", "published": True
        })
        assert r.status_code == 200, r.text
        item = r.json()
        iid = item["item_id"]
        assert item["published"] is True
        pytest.item_id = iid
        pytest.item_slug = item["slug"]
        # UPDATE toggle published false
        r = s.put(f"{BASE}/apps/{NEXUS}/cms/{cid}/items/{iid}", json={
            "title": item["title"], "excerpt": "hello", "body": "world body", "published": False
        })
        assert r.status_code == 200
        assert r.json()["published"] is False
        # Re-publish so export test finds it
        r = s.put(f"{BASE}/apps/{NEXUS}/cms/{cid}/items/{iid}", json={
            "title": item["title"], "excerpt": "hello", "body": "world body", "published": True
        })
        assert r.status_code == 200 and r.json()["published"] is True

    def test_duplicate_collection_400(self, s):
        # First create a fresh collection then attempt duplicate
        base_name = "TEST_DupCol_v6"
        r0 = s.post(f"{BASE}/apps/{NEXUS}/cms", json={"name": base_name})
        assert r0.status_code == 200, r0.text
        cid = r0.json()["collection_id"]
        try:
            r = s.post(f"{BASE}/apps/{NEXUS}/cms", json={"name": base_name})
            assert r.status_code == 400, f"Expected 400 on duplicate name, got {r.status_code}: {r.text}"
        finally:
            s.delete(f"{BASE}/apps/{NEXUS}/cms/{cid}")
        # Also test against default collection name (bug: current code compares slug only)
        r2 = s.post(f"{BASE}/apps/{NEXUS}/cms", json={"name": "Blog posts"})
        if r2.status_code == 200:
            # cleanup and note bug
            s.delete(f"{BASE}/apps/{NEXUS}/cms/{r2.json()['collection_id']}")
            pytest.fail("Duplicate default name 'Blog posts' accepted (slugified to 'blog-posts' != default slug 'blog')")

    def test_public_site_includes_published(self, s):
        # get preview token
        app = s.get(f"{BASE}/apps/{NEXUS}").json()
        tok = app.get("preview_token")
        if not tok:
            r = s.post(f"{BASE}/apps/{NEXUS}/preview/regenerate")
            tok = r.json().get("preview_token")
        assert tok
        r = requests.get(f"{BASE}/public/site/{tok}")
        assert r.status_code == 200, r.text
        data = r.json()
        cols = data.get("collections") or []
        assert cols, "expected collections in public site payload"
        blog = next((c for c in cols if c["slug"] == "blog"), None)
        assert blog and any(i["item_id"] == pytest.item_id for i in blog["items"])
        # unpublished should be excluded — create one and check
        cid = pytest.blog_col_id
        d = s.post(f"{BASE}/apps/{NEXUS}/cms/{cid}/items", json={
            "title": "TEST_v6 Draft", "excerpt": "x", "body": "y", "published": False
        }).json()
        r2 = requests.get(f"{BASE}/public/site/{tok}").json()
        blog2 = next(c for c in r2["collections"] if c["slug"] == "blog")
        assert not any(i["item_id"] == d["item_id"] for i in blog2["items"])
        # cleanup draft
        s.delete(f"{BASE}/apps/{NEXUS}/cms/{cid}/items/{d['item_id']}")

    def test_export_has_collection_html(self, s):
        r = s.get(f"{BASE}/apps/{NEXUS}/export/source")
        assert r.status_code == 200, r.text
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = z.namelist()
        expect = f"site/blog/{pytest.item_slug}.html"
        assert any(n.endswith(expect) or n == expect for n in names), f"missing {expect} in {[n for n in names if 'blog' in n]}"

    def test_delete_item_cleanup(self, s):
        r = s.delete(f"{BASE}/apps/{NEXUS}/cms/{pytest.blog_col_id}/items/{pytest.item_id}")
        assert r.status_code == 200


# ===== TEMPLATES =====
class TestTemplates:
    def test_list_templates(self, s):
        r = s.get(f"{BASE}/workflows/templates")
        assert r.status_code == 200
        keys = {t["key"] for t in r.json()}
        assert keys == {"welcome_lead", "slack_ping", "thank_payment", "log_chat", "pro_alert", "change_request"}

    def test_install_unknown_404(self, s):
        r = s.post(f"{BASE}/apps/{NEXUS}/workflows/templates/does_not_exist")
        assert r.status_code == 404

    def test_new_app_has_3_defaults_and_change_trigger(self, s):
        r = s.post(f"{BASE}/apps", json={"name": "TEST_QA_v6", "industry": "SaaS Portals", "kind": "app"})
        assert r.status_code == 200, r.text
        aid = r.json()["app_id"]
        pytest.new_app_id = aid
        r = s.get(f"{BASE}/apps/{aid}/workflows")
        assert r.status_code == 200
        data = r.json()
        wfs = data.get("workflows") or data.get("items") or (data if isinstance(data, list) else [])
        templates = {w.get("template") for w in wfs}
        assert {"welcome_lead", "log_chat", "change_request"}.issubset(templates), templates
        triggers = data.get("triggers") if isinstance(data, dict) else None
        if triggers is not None:
            assert "change_requested" in triggers


# ===== PORTAL =====
class TestPortal:
    def test_portal_shape(self, s):
        r = s.get(f"{BASE}/portal")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "user" in d and "apps" in d and d["apps"]
        nexus = next((a for a in d["apps"] if a["app_id"] == NEXUS), None)
        assert nexus and nexus["role"] == "owner"
        for k in ["invoices", "leads", "requests", "activity"]:
            assert k in nexus, k

    def test_request_creates_message_and_fires_wf(self, s):
        # Ensure change_request template installed on nexus
        wfs_before = s.get(f"{BASE}/apps/{NEXUS}/workflows").json()
        wf_list = wfs_before.get("workflows") or wfs_before.get("items") or (wfs_before if isinstance(wfs_before, list) else [])
        cr = next((w for w in wf_list if w.get("template") == "change_request"), None)
        if not cr:
            r = s.post(f"{BASE}/apps/{NEXUS}/workflows/templates/change_request")
            assert r.status_code == 200
            cr = r.json()
        runs_before = cr.get("runs", 0)
        # Submit request
        r = s.post(f"{BASE}/portal/{NEXUS}/request", json={"title": "Update hero", "details": "Please change headline"})
        assert r.status_code == 200, r.text
        msg = r.json()
        assert msg["source"] == "request"
        # Inbox has it
        r = s.get(f"{BASE}/apps/{NEXUS}/inbox")
        inbox = r.json()
        msgs = inbox.get("messages") or inbox if isinstance(inbox, list) else inbox.get("messages", [])
        if isinstance(inbox, dict) and "messages" in inbox:
            msgs = inbox["messages"]
        assert any(m.get("message_id") == msg["message_id"] for m in msgs)
        # Workflow runs incremented (allow small delay)
        for _ in range(6):
            time.sleep(1)
            wfs = s.get(f"{BASE}/apps/{NEXUS}/workflows").json()
            wf_list2 = wfs.get("workflows") or wfs.get("items") or (wfs if isinstance(wfs, list) else [])
            cr2 = next((w for w in wf_list2 if w.get("workflow_id") == cr["workflow_id"]), None)
            if cr2 and cr2.get("runs", 0) > runs_before:
                break
        assert cr2 and cr2.get("runs", 0) > runs_before, f"runs did not increment: {cr2}"


# ===== BRIEF UPLOAD =====
class TestBrief:
    def test_txt_ok(self, s):
        content = b"This is a longer than twenty chars brief for the app."
        r = s.post(f"{BASE}/apps/{NEXUS}/ai/brief-upload",
                   files={"file": ("brief.txt", content, "text/plain")})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["chars"] >= 20 and "text" in d

    def test_docx_ok(self, s):
        import docx
        doc = docx.Document()
        doc.add_paragraph("Hello from a docx brief with enough characters here.")
        buf = io.BytesIO()
        doc.save(buf)
        r = s.post(f"{BASE}/apps/{NEXUS}/ai/brief-upload",
                   files={"file": ("brief.docx", buf.getvalue(),
                                   "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
        assert r.status_code == 200, r.text
        assert "docx" in r.json()["text"].lower() or r.json()["chars"] > 20

    def test_exe_rejected(self, s):
        r = s.post(f"{BASE}/apps/{NEXUS}/ai/brief-upload",
                   files={"file": ("bad.exe", b"MZ" + b"\x00" * 100, "application/x-msdownload")})
        assert r.status_code == 400


@pytest.fixture(scope="module", autouse=True)
def cleanup(s):
    yield
    aid = getattr(pytest, "new_app_id", None)
    if aid:
        try:
            s.delete(f"{BASE}/apps/{aid}")
        except Exception:
            pass
