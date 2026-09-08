"""Iter-29: Full-site crawl importer.

Focuses on the negative paths + regressions the main agent asked for.  Read-only
assertions reuse the already-imported 'Crawl Final' tenant (roto-rooter) so we
don't burn LLM credits on repeated full crawls.  Destructive tests use tiny
throwaway tenants + example.com or short max_pages.
"""
import io
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
CRAWL_TENANT = "app_7035dfbf4a95"  # 'Crawl Final' — 5 pages of roto-rooter.com already imported


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return s


@pytest.fixture()
def throwaway(admin):
    r = admin.post(f"{BASE_URL}/apps", json={
        "name": f"TEST_iter29_{uuid.uuid4().hex[:6]}", "industry": "SaaS", "kind": "website",
        "description": "throwaway", "status": "draft", "tags": [], "color": "#333",
    }, timeout=30)
    assert r.status_code == 200, r.text[:200]
    aid = r.json()["app_id"]
    yield aid
    try:
        admin.delete(f"{BASE_URL}/apps/{aid}", timeout=20)
    except Exception:
        pass


@pytest.fixture(scope="session")
def viewer(admin):
    email = f"TEST_iter29_v_{uuid.uuid4().hex[:6]}@example.com"
    pwd = "ViewPass2026!"
    reg = requests.Session()
    r = reg.post(f"{BASE_URL}/auth/register", json={"email": email, "password": pwd, "name": "V"}, timeout=30)
    assert r.status_code == 200
    # create tenant + invite viewer
    r = admin.post(f"{BASE_URL}/apps", json={"name": f"TEST_iter29_vh_{uuid.uuid4().hex[:6]}", "industry": "S", "kind": "website"}, timeout=30)
    aid = r.json()["app_id"]
    inv = admin.post(f"{BASE_URL}/apps/{aid}/members", json={"email": email, "role": "viewer"}, timeout=20)
    assert inv.status_code == 200, inv.text[:200]
    s = requests.Session()
    lr = s.post(f"{BASE_URL}/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert lr.status_code == 200
    yield s, aid
    try:
        admin.delete(f"{BASE_URL}/apps/{aid}", timeout=20)
    except Exception:
        pass


def _wait_job(admin, app_id, job_id, timeout=250):
    """Poll import-job until done/error."""
    stages_seen = []
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = admin.get(f"{BASE_URL}/apps/{app_id}/site/import-job/{job_id}", timeout=30)
        assert r.status_code == 200, r.text[:200]
        j = r.json()
        st = j.get("stage")
        if st and (not stages_seen or stages_seen[-1] != st):
            stages_seen.append(st)
        if j.get("status") in ("done", "error"):
            return j, stages_seen
        time.sleep(1.5)
    pytest.fail(f"import job did not finish in {timeout}s; stages={stages_seen}")


# ---------------------------------------------------------------------------
# Read-only assertions on the pre-existing Crawl Final tenant
# ---------------------------------------------------------------------------
class TestCrawlFinalRegression:
    def test_app_persistence_flags(self, admin):
        r = admin.get(f"{BASE_URL}/apps/{CRAWL_TENANT}", timeout=20)
        assert r.status_code == 200
        a = r.json()
        assert a.get("premium_site_v") == 3, "premium_site_v must be 3 to block startup migration"
        assert a.get("imported_from") == "https://www.roto-rooter.com"
        th = a.get("theme") or {}
        assert th.get("primary", "").startswith("#") and len(th["primary"]) == 7, th
        assert th.get("secondary", "").startswith("#") and len(th["secondary"]) == 7, th
        # brand_profile scraped
        bp = a.get("brand_profile") or {}
        assert bp.get("phone") or bp.get("email") or bp.get("address"), bp

    def test_pages_and_no_external_images(self, admin):
        r = admin.get(f"{BASE_URL}/apps/{CRAWL_TENANT}/pages", timeout=20)
        assert r.status_code == 200
        pages = r.json()
        assert len(pages) == 5
        # every page starts with navbar and ends with footer
        for p in pages:
            blocks = p["blocks"]
            assert len(blocks) >= 5, f"{p['slug']} has {len(blocks)} blocks"
            assert blocks[0].get("type") == "navbar", p["slug"]
            assert blocks[-1].get("type") == "footer", p["slug"]
        # No external image URLs in any block prop; every image URL should be local
        import re
        HTTP_IMG = re.compile(r"https?://[^\"'\s]+\.(?:jpg|jpeg|png|gif|webp|svg)", re.I)
        found_local = False
        for p in pages:
            for b in p["blocks"]:
                props = b.get("props") or {}
                for k, v in props.items():
                    if isinstance(v, str):
                        if HTTP_IMG.search(v):
                            pytest.fail(f"external image url in {p['slug']}.{b.get('type')}.{k}: {v[:120]}")
                        if "/api/public/files/" in v and v.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
                            found_local = True
                    if isinstance(v, list):
                        for x in v:
                            if isinstance(x, dict) and isinstance(x.get("url"), str):
                                if HTTP_IMG.search(x["url"]):
                                    pytest.fail(f"external image in list {p['slug']}.{b.get('type')}.{k}: {x['url'][:120]}")
                                if "/api/public/files/" in x["url"]:
                                    found_local = True
        assert found_local, "no local /api/public/files image found — media library not wired"

    def test_footer_links_are_strings(self, admin):
        r = admin.get(f"{BASE_URL}/apps/{CRAWL_TENANT}/pages", timeout=20)
        pages = r.json()
        for p in pages:
            for b in p["blocks"]:
                if b.get("type") != "footer":
                    continue
                cols = (b.get("props") or {}).get("columns") or []
                for c in cols:
                    for l in (c.get("links") or []):
                        assert isinstance(l, str), f"footer link in {p['slug']} is {type(l).__name__}, must be str: {l!r}"

    def test_navbar_shared_and_dropdowns(self, admin):
        r = admin.get(f"{BASE_URL}/apps/{CRAWL_TENANT}/pages", timeout=20)
        pages = r.json()
        nav_signatures = set()
        has_dropdown = False
        for p in pages:
            nb = p["blocks"][0]
            assert nb.get("type") == "navbar"
            links = (nb.get("props") or {}).get("links") or []
            sig = tuple((l.get("label"), l.get("href")) for l in links if isinstance(l, dict))
            nav_signatures.add(sig)
            for l in links:
                if isinstance(l, dict) and l.get("children"):
                    has_dropdown = True
                    parent_href = l.get("href")
                    for ch in l["children"]:
                        assert ch.get("href") != parent_href, f"child href duplicates parent: {ch}"
        assert len(nav_signatures) == 1, f"navbar links differ across pages: {nav_signatures}"
        # note: real dropdowns depend on the source site — allow no dropdowns if the site has none
        # roto-rooter's parsed nav often has children, so warn (not fail) if none
        if not has_dropdown:
            print("WARN: no dropdown children[] present on any nav link")

    def test_string_props_not_dicts(self, admin):
        r = admin.get(f"{BASE_URL}/apps/{CRAWL_TENANT}/pages", timeout=20)
        pages = r.json()
        STRING_PROPS = ("cta", "cta2", "title", "subtitle", "heading", "brand", "badge",
                        "submit_label", "email", "phone", "address")
        for p in pages:
            for b in p["blocks"]:
                for k, v in (b.get("props") or {}).items():
                    if k in STRING_PROPS:
                        assert not isinstance(v, dict), f"{p['slug']}.{b.get('type')}.{k} is a dict: {v!r}"

    def test_form_block_shape(self, admin):
        r = admin.get(f"{BASE_URL}/apps/{CRAWL_TENANT}/pages", timeout=20)
        pages = r.json()
        forms = []
        for p in pages:
            for b in p["blocks"]:
                if b.get("type") == "form":
                    forms.append((p["slug"], b))
        assert forms, "no form block in Crawl Final"
        allowed_types = {"text", "email", "tel", "number", "url", "date", "textarea", "select", "checkbox", "radio"}
        for slug, b in forms:
            fields = (b.get("props") or {}).get("fields") or []
            assert fields, f"{slug} form has no fields"
            for f in fields:
                assert "name" in f and "label" in f and "type" in f, f
                assert f["type"] in allowed_types, f"bad type {f['type']} on {slug}"
                if f["type"] in ("select", "radio"):
                    assert isinstance(f.get("options"), list) and f["options"], f

    def test_form_submits_to_inbox(self, admin):
        # Find the form block + its fields on /contact-us; submit via /public/contact/{token}
        app = admin.get(f"{BASE_URL}/apps/{CRAWL_TENANT}", timeout=20).json()
        token = app.get("preview_token")
        assert token, "Crawl Final has no preview_token"
        pages = admin.get(f"{BASE_URL}/apps/{CRAWL_TENANT}/pages", timeout=20).json()
        form_block = None
        for p in pages:
            for b in p["blocks"]:
                if b.get("type") == "form":
                    form_block = b
                    break
            if form_block:
                break
        assert form_block
        fields = form_block["props"]["fields"]
        payload = {}
        marker = f"iter29-{uuid.uuid4().hex[:6]}"
        for f in fields:
            n, t = f["name"], f["type"]
            if t == "email":
                payload[n] = f"{marker}@example.com"
            elif t == "tel":
                payload[n] = "555-010-2030"
            elif t == "checkbox":
                payload[n] = True
            elif t == "select":
                payload[n] = (f.get("options") or ["a"])[0]
            elif t == "textarea":
                payload[n] = f"iter29 message {marker}"
            else:
                payload[n] = f"Iter29 {marker}"
        r = requests.post(f"{BASE_URL}/public/contact/{token}",
                          json={"fields": payload, "email": payload.get(next((f['name'] for f in fields if f['type'] == 'email'), 'email'), f'{marker}@example.com')},
                          timeout=30)
        # Allow either shape: {fields} or flattened
        if r.status_code >= 400:
            # try flattened
            r = requests.post(f"{BASE_URL}/public/contact/{token}", json=payload, timeout=30)
        assert r.status_code == 200, f"public contact failed: {r.status_code} {r.text[:200]}"
        time.sleep(1.0)
        inbox = admin.get(f"{BASE_URL}/apps/{CRAWL_TENANT}/inbox", timeout=20).json()
        rows = inbox if isinstance(inbox, list) else inbox.get("items") or inbox.get("messages") or []
        found = any(marker in str(row) for row in rows)
        assert found, f"marker {marker} not found in inbox (rows={len(rows)})"

    def test_media_library_lists_import(self, admin):
        r = admin.get(f"{BASE_URL}/apps/{CRAWL_TENANT}/files", timeout=20)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        files = data if isinstance(data, list) else data.get("files") or data.get("items") or []
        imports = [f for f in files if (f.get("uploaded_by") or "").lower() == "website import"]
        assert imports, "no 'website import' files in library"
        assert all(f.get("private") is False for f in imports), "imported images must be public"
        # verify one is downloadable
        f0 = imports[0]
        sp = f0.get("storage_path")
        assert sp
        pub = requests.get(f"{os.environ['REACT_APP_BACKEND_URL'].rstrip('/')}/api/public/files/{sp}", timeout=30)
        assert pub.status_code == 200, f"public file 404: {pub.status_code}"
        assert pub.headers.get("content-type", "").startswith("image/"), pub.headers.get("content-type")


# ---------------------------------------------------------------------------
# Negative paths — cheap (no LLM crawl)
# ---------------------------------------------------------------------------
class TestErrorsAndPermissions:
    def test_invalid_url(self, admin, throwaway):
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/site/import-preview",
                       json={"url": "not-a-url", "max_pages": 1}, timeout=20)
        # accept either inline 400 or a job that immediately errors
        if r.status_code == 200:
            j, _ = _wait_job(admin, throwaway, r.json()["job_id"], timeout=30)
            assert j["status"] == "error", j
        else:
            assert r.status_code == 400, r.text[:200]

    def test_localhost_blocked(self, admin, throwaway):
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/site/import-preview",
                       json={"url": "http://localhost:3000", "max_pages": 1}, timeout=20)
        assert r.status_code == 400, r.text[:200]

    def test_nonexistent_domain(self, admin, throwaway):
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/site/import-preview",
                       json={"url": "https://nonexistent-xyz-iter29.invalid", "max_pages": 1}, timeout=20)
        # DNS failure will be caught inside the job
        if r.status_code == 200:
            j, _ = _wait_job(admin, throwaway, r.json()["job_id"], timeout=45)
            assert j["status"] == "error", j
        else:
            assert r.status_code == 400

    def test_viewer_forbidden(self, viewer):
        vs, aid = viewer
        for path, body in [
            (f"/apps/{aid}/site/import-preview", {"url": "https://example.com", "max_pages": 1}),
            (f"/apps/{aid}/site/import", {"url": "https://example.com", "max_pages": 1}),
            (f"/apps/{aid}/site/import-apply", {"import_id": "imp_fake"}),
        ]:
            r = vs.post(f"{BASE_URL}{path}", json=body, timeout=20)
            assert r.status_code == 403, f"{path}: expected 403 got {r.status_code} {r.text[:200]}"


# ---------------------------------------------------------------------------
# max_pages clamp — cheapest LLM crawl (1 page of example.com)
# ---------------------------------------------------------------------------
class TestMaxPagesClamp:
    def test_max_pages_1_produces_one_page(self, admin, throwaway):
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/site/import-preview",
                       json={"url": "https://example.com", "max_pages": 1}, timeout=20)
        assert r.status_code == 200, r.text[:200]
        j, stages = _wait_job(admin, throwaway, r.json()["job_id"], timeout=240)
        assert j["status"] == "done", j.get("error")
        res = j["result"]
        assert res["report"]["pages_imported"] == 1
        assert res["report"]["crawled"] == 1
        # stage progression sanity
        assert "scanning" in stages or "reading" in stages

    def test_max_pages_zero_does_not_crash(self, admin, throwaway):
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/site/import-preview",
                       json={"url": "https://example.com", "max_pages": 0}, timeout=20)
        assert r.status_code == 200, r.text[:200]
        j, _ = _wait_job(admin, throwaway, r.json()["job_id"], timeout=240)
        # server clamps min 1
        assert j["status"] == "done", j.get("error")
        assert j["result"]["report"]["pages_imported"] >= 1


# ---------------------------------------------------------------------------
# Own-file upload path used by the WebImport dialog
# ---------------------------------------------------------------------------
class TestOwnFileUpload:
    def _tiny_png(self):
        # 1x1 transparent PNG
        return bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000d49444154789c6300010000000500010d0a2db40000000049454e44"
            "ae426082"
        )

    def _tiny_mp4(self):
        # 200 bytes of zeros with mp4 signature is not really a valid mp4 but MIME check + magic isn't enforced.
        # Use an ftyp header prefix so type sniffers accept it.
        return bytes.fromhex("0000001c66747970697336366d000000006973366d") + b"\x00" * 400

    def test_upload_image(self, admin, throwaway):
        files = {"file": ("iter29.png", self._tiny_png(), "image/png")}
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/files", files=files, timeout=30)
        assert r.status_code == 200, r.text[:200]
        fid = r.json().get("file_id") or r.json().get("id")
        assert fid
        # appears in library
        lib = admin.get(f"{BASE_URL}/apps/{throwaway}/files", timeout=20).json()
        rows = lib if isinstance(lib, list) else lib.get("files") or lib.get("items") or []
        assert any((f.get("file_id") == fid or f.get("id") == fid or f.get("original_filename") == "iter29.png") for f in rows)

    def test_upload_mp4(self, admin, throwaway):
        files = {"file": ("iter29.mp4", self._tiny_mp4(), "video/mp4")}
        r = admin.post(f"{BASE_URL}/apps/{throwaway}/files", files=files, timeout=30)
        # some backends only allow images — accept 200 or 400 with clear message
        if r.status_code != 200:
            pytest.fail(f"mp4 upload rejected: {r.status_code} {r.text[:300]}")
