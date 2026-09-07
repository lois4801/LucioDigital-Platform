"""Iter-25 backend tests: Tenant File & Media Library, quota, tenant isolation,
data-export ZIP contents (no password_hash), export/source bundle_media rewriter.

Focus areas (per E1 hints):
 - quota enforcement (413) via app.storage_quota_mb override
 - tenant isolation (uploads to app A never appear for app B)
 - people.json does NOT leak password_hash
 - export_source bundles /api/public/files/... references into site/assets/* and rewrites HTML
 - Regression: upload, list, usage, rename, soft-delete
"""
import io
import os
import time
import zipfile
import json
import requests
import pytest
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
APP_ID = "app_bdbf27abe643"
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def db():
    # Read DB_NAME from backend .env if not set in this shell
    global DB_NAME
    try:
        with open("/app/backend/.env") as f:
            for line in f:
                if line.startswith("DB_NAME="):
                    DB_NAME = line.split("=", 1)[1].strip().strip('"')
                if line.startswith("MONGO_URL="):
                    globals()["MONGO_URL"] = line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN)
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text}")
    return s


@pytest.fixture(scope="module")
def other_user():
    email = f"TEST_iter25_noaccess_{int(time.time())}@example.com"
    pw = "TestNoAccess2026!"
    reg = requests.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "TEST Iter25"})
    if reg.status_code not in (200, 201):
        reg = requests.post(f"{API}/auth/signup", json={"email": email, "password": pw, "name": "TEST Iter25"})
    if reg.status_code not in (200, 201):
        pytest.skip(f"cannot create user: {reg.status_code} {reg.text}")
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed: {r.status_code}")
    return s


@pytest.fixture(scope="module")
def scratch_app(admin, db):
    """Create a scratch tenant owned by admin for isolation + quota tests. Cleaned up after."""
    r = admin.post(f"{API}/apps", json={"name": f"TEST_iter25_scratch_{int(time.time())}", "industry": "test"})
    if r.status_code not in (200, 201):
        pytest.skip(f"cannot create scratch app: {r.status_code} {r.text}")
    app = r.json()
    app_id = app.get("app_id") or app.get("id")
    assert app_id, f"no app_id in {app}"
    yield app_id
    # cleanup: remove app doc and any files docs and quota
    db.apps.delete_one({"app_id": app_id})
    db.files.delete_many({"app_id": app_id})


# ---------------- Upload / list / usage ----------------
class TestUploadListUsage:
    def test_upload_image_and_public_url(self, admin):
        # 1x1 PNG
        png = bytes.fromhex("89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4890000000A49444154789C6300010000000500010D0A2DB40000000049454E44AE426082")
        fd = {"file": ("TEST_iter25.png", png, "image/png")}
        r = admin.post(f"{API}/apps/{APP_ID}/files", files=fd)
        assert r.status_code == 200, r.text
        j = r.json()
        for k in ("file_id", "storage_path", "url", "size", "content_type"):
            assert k in j, f"missing {k} in {j}"
        assert j["content_type"] == "image/png"
        assert j["url"].startswith("/api/public/files/")
        # Downloadable
        d = requests.get(f"{BASE_URL}{j['url']}")
        assert d.status_code == 200
        assert d.content == png

    def test_upload_pdf_txt_video(self, admin):
        for name, ct, data in [
            ("TEST_iter25.txt", "text/plain", b"hello iter25"),
            ("TEST_iter25.pdf", "application/pdf", b"%PDF-1.4\n%EOF\n"),
            ("TEST_iter25.mp4", "video/mp4", b"\x00\x00\x00\x18ftypmp42tinytest"),
        ]:
            r = admin.post(f"{API}/apps/{APP_ID}/files", files={"file": (name, data, ct)})
            assert r.status_code == 200, f"{name}: {r.text}"
            assert r.json()["content_type"] == ct

    def test_unsupported_ext_400(self, admin):
        r = admin.post(f"{API}/apps/{APP_ID}/files", files={"file": ("bad.exe", b"MZ", "application/octet-stream")})
        assert r.status_code == 400
        assert "Unsupported" in r.text or "type" in r.text.lower()

    def test_over_15mb_400(self, admin):
        big = b"x" * (15 * 1024 * 1024 + 10)
        r = admin.post(f"{API}/apps/{APP_ID}/files", files={"file": ("TEST_iter25_big.txt", big, "text/plain")})
        assert r.status_code == 400
        assert "15" in r.text

    def test_unauthed_401(self):
        r = requests.post(f"{API}/apps/{APP_ID}/files", files={"file": ("x.txt", b"x", "text/plain")})
        assert r.status_code == 401

    def test_noaccess_403(self, other_user):
        r = other_user.post(f"{API}/apps/{APP_ID}/files", files={"file": ("x.txt", b"x", "text/plain")})
        assert r.status_code == 403

    def test_list_returns_usage_and_only_own_tenant(self, admin, scratch_app):
        # Upload one to scratch_app
        r = admin.post(f"{API}/apps/{scratch_app}/files", files={"file": ("TEST_iter25_scratch.txt", b"only-in-scratch", "text/plain")})
        assert r.status_code == 200
        sfid = r.json()["file_id"]
        # List scratch
        s = admin.get(f"{API}/apps/{scratch_app}/files")
        assert s.status_code == 200
        sj = s.json()
        assert "files" in sj and "usage" in sj
        u = sj["usage"]
        for k in ("used_bytes", "quota_bytes", "files", "percent"):
            assert k in u
        scratch_ids = {f["file_id"] for f in sj["files"]}
        assert sfid in scratch_ids
        # List main tenant — must NOT contain scratch file
        m = admin.get(f"{API}/apps/{APP_ID}/files").json()
        main_ids = {f["file_id"] for f in m["files"]}
        assert sfid not in main_ids, "TENANT ISOLATION BROKEN — scratch file appeared in main tenant list"
        # Newest first
        if len(m["files"]) >= 2:
            times = [f["created_at"] for f in m["files"]]
            assert times == sorted(times, reverse=True)

    def test_usage_endpoint_matches_list_and_reflects_new_upload(self, admin, scratch_app):
        u1 = admin.get(f"{API}/apps/{scratch_app}/files/usage").json()
        l1 = admin.get(f"{API}/apps/{scratch_app}/files").json()["usage"]
        assert u1["used_bytes"] == l1["used_bytes"]
        assert u1["files"] == l1["files"]
        # Upload
        payload = b"y" * 4096
        r = admin.post(f"{API}/apps/{scratch_app}/files", files={"file": ("TEST_iter25_usage.txt", payload, "text/plain")})
        assert r.status_code == 200
        u2 = admin.get(f"{API}/apps/{scratch_app}/files/usage").json()
        assert u2["used_bytes"] >= u1["used_bytes"] + len(payload)
        assert u2["files"] == u1["files"] + 1

    def test_default_quota_500mb(self, admin, scratch_app):
        u = admin.get(f"{API}/apps/{scratch_app}/files/usage").json()
        assert u["quota_bytes"] == 500 * 1024 * 1024


# ---------------- Quota enforcement ----------------
class TestQuotaEnforcement:
    def test_413_when_exceeded_and_no_record_created(self, admin, scratch_app, db):
        # Set a tiny quota (1 MB) directly in Mongo
        db.apps.update_one({"app_id": scratch_app}, {"$set": {"storage_quota_mb": 1}})
        u_before = admin.get(f"{API}/apps/{scratch_app}/files/usage").json()
        assert u_before["quota_bytes"] == 1 * 1024 * 1024
        # attempt upload of a 2MB file (well over the 1MB quota, but < the 15MB per-file cap)
        payload = b"z" * (2 * 1024 * 1024)
        n_before = db.files.count_documents({"app_id": scratch_app, "is_deleted": False})
        r = admin.post(f"{API}/apps/{scratch_app}/files", files={"file": ("TEST_iter25_quota.zip", payload, "application/zip")})
        assert r.status_code == 413, f"expected 413, got {r.status_code}: {r.text}"
        assert "quota" in r.text.lower()
        n_after = db.files.count_documents({"app_id": scratch_app, "is_deleted": False})
        assert n_after == n_before, "413 upload MUST NOT create a files record"
        # Cleanup override
        db.apps.update_one({"app_id": scratch_app}, {"$unset": {"storage_quota_mb": ""}})


# ---------------- Rename / delete ----------------
class TestRenameDelete:
    def test_rename_and_soft_delete(self, admin, db):
        # upload a fresh file
        r = admin.post(f"{API}/apps/{APP_ID}/files", files={"file": ("TEST_iter25_rn.txt", b"rename-me-iter25", "text/plain")})
        assert r.status_code == 200
        j = r.json()
        fid = j["file_id"]
        original_path = j["storage_path"]
        # rename
        r2 = admin.patch(f"{API}/apps/{APP_ID}/files/{fid}", json={"name": "TEST_iter25_renamed.txt"})
        assert r2.status_code == 200
        assert r2.json()["original_filename"] == "TEST_iter25_renamed.txt"
        assert r2.json()["storage_path"] == original_path
        # soft delete
        r3 = admin.delete(f"{API}/apps/{APP_ID}/files/{fid}")
        assert r3.status_code == 200
        # Not in list anymore
        listed = admin.get(f"{API}/apps/{APP_ID}/files").json()["files"]
        assert fid not in {f["file_id"] for f in listed}
        # Record still present in Mongo with is_deleted True (soft delete)
        rec = db.files.find_one({"file_id": fid})
        assert rec is not None
        assert rec.get("is_deleted") is True

    def test_rename_unknown_404(self, admin):
        r = admin.patch(f"{API}/apps/{APP_ID}/files/does_not_exist_xyz", json={"name": "x"})
        assert r.status_code == 404

    def test_delete_unknown_404(self, admin):
        r = admin.delete(f"{API}/apps/{APP_ID}/files/does_not_exist_xyz")
        assert r.status_code == 404


# ---------------- Data export ----------------
class TestDataExport:
    def test_data_export_zip_contents_and_no_password_hash(self, admin):
        r = admin.get(f"{API}/apps/{APP_ID}/data-export")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/zip")
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = set(z.namelist())
        required = {
            "data/app.json", "data/pages.json", "data/cms_collections.json", "data/cms_items.json",
            "data/messages.json", "data/memberships.json", "data/activity_logs.json",
            "data/workflows.json", "data/site_analytics.json", "data/people.json",
            "files/manifest.json", "README.md",
        }
        missing = required - names
        assert not missing, f"data-export ZIP missing: {missing}"
        # people.json must NOT contain password_hash
        people = json.loads(z.read("data/people.json"))
        blob = json.dumps(people).lower()
        assert "password_hash" not in blob, "password_hash LEAKED in data-export people.json"
        # At least one files/<id>-<name> binary
        file_entries = [n for n in names if n.startswith("files/") and n != "files/manifest.json"]
        # manifest must map cleanly
        manifest = json.loads(z.read("files/manifest.json"))
        for m in manifest:
            assert m["file"] in names, f"manifest points to missing file: {m['file']}"
        # at least one binary present if manifest has entries
        if manifest:
            assert file_entries, "manifest lists files but no binaries in ZIP"

    def test_data_export_non_member_403(self, other_user):
        r = other_user.get(f"{API}/apps/{APP_ID}/data-export")
        assert r.status_code == 403


# ---------------- Export source w/ media bundling ----------------
class TestExportSourceBundleMedia:
    def test_source_bundle_rewrites_public_file_urls_to_assets(self, admin, db):
        """Upload an image, inject a reference into a page block, export source, verify
        the ZIP contains site/assets/<file> and the HTML uses assets/... instead of /api/public/files/..."""
        # 1x1 GIF (small + valid)
        gif = bytes.fromhex("47494638396101000100800000FFFFFF00000021F90401000000002C00000000010001000002024401003B")
        r = admin.post(f"{API}/apps/{APP_ID}/files", files={"file": ("TEST_iter25_bundle.gif", gif, "image/gif")})
        assert r.status_code == 200
        rec = r.json()
        public_url = rec["url"]  # /api/public/files/omnistack/library/<app_id>/<uuid>.gif

        # Get first page and inject an image block that references the public URL
        pages = list(db.pages.find({"app_id": APP_ID}))
        if not pages:
            pytest.skip("no pages on APP_ID")
        pg = pages[0]
        original_blocks = pg.get("blocks", [])
        marker = f"TEST_ITER25_BUNDLE_{int(time.time())}"
        new_block = {
            "id": f"TEST_iter25_{int(time.time())}",
            "type": "image",
            "props": {"src": public_url, "alt": marker, "caption": marker},
        }
        db.pages.update_one({"page_id": pg["page_id"]}, {"$set": {"blocks": original_blocks + [new_block]}})
        try:
            r2 = admin.get(f"{API}/apps/{APP_ID}/export/source")
            assert r2.status_code == 200
            z = zipfile.ZipFile(io.BytesIO(r2.content))
            names = z.namelist()
            # Assets directory must exist
            assets = [n for n in names if n.startswith("site/assets/")]
            assert assets, f"export/source did not bundle media into site/assets/ (names sample: {names[:15]})"
            # The GIF bytes should be present in one of them
            found_bytes = False
            asset_basenames = []
            for a in assets:
                b = z.read(a)
                asset_basenames.append(a.split("/")[-1])
                if b == gif:
                    found_bytes = True
            assert found_bytes, "bundled asset bytes don't match the uploaded GIF"
            # HTML/CSS files must not contain the /api/public/files/... URL for our upload
            storage_key = rec["storage_path"]
            html_or_css = [n for n in names if n.startswith("site/") and (n.endswith(".html") or n.endswith(".css"))]
            for n in html_or_css:
                content = z.read(n).decode("utf-8", errors="ignore")
                assert storage_key not in content, f"{n} still references storage URL {storage_key}"
            # And SOMEWHERE the rewritten assets/<name> path should appear
            joined = "".join(z.read(n).decode("utf-8", errors="ignore") for n in html_or_css)
            assert any(f"assets/{bn}" in joined for bn in asset_basenames), \
                "no rewritten assets/... reference found in exported HTML/CSS"
        finally:
            # restore the page
            db.pages.update_one({"page_id": pg["page_id"]}, {"$set": {"blocks": original_blocks}})

    def test_source_export_survives_unreachable_url(self, admin, db):
        """A block referencing an /api/public/files/... URL whose object no longer exists
        must NOT crash export/source — the URL should be left as-is."""
        pages = list(db.pages.find({"app_id": APP_ID}))
        if not pages:
            pytest.skip("no pages on APP_ID")
        pg = pages[0]
        bad_url = "/api/public/files/omnistack/library/nonexistent/deadbeef.png"
        block = {"id": f"TEST_iter25_bad_{int(time.time())}", "type": "hero",
                 "props": {"title": "TEST_iter25_bad", "subtitle": f"see {bad_url} here", "cta": "ok"}}
        original = pg.get("blocks", [])
        db.pages.update_one({"page_id": pg["page_id"]}, {"$set": {"blocks": original + [block]}})
        try:
            r = admin.get(f"{API}/apps/{APP_ID}/export/source")
            assert r.status_code == 200, r.text
            z = zipfile.ZipFile(io.BytesIO(r.content))
            joined = "".join(
                z.read(n).decode("utf-8", errors="ignore")
                for n in z.namelist() if n.startswith("site/") and n.endswith(".html")
            )
            # bad URL should still appear (left as-is)
            assert bad_url in joined or "deadbeef.png" in joined
        finally:
            db.pages.update_one({"page_id": pg["page_id"]}, {"$set": {"blocks": original}})


# ---------------- Regression sanity ----------------
class TestRegression:
    def test_logo_upload_still_works(self, admin):
        png = bytes.fromhex("89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4890000000A49444154789C6300010000000500010D0A2DB40000000049454E44AE426082")
        r = admin.post(f"{API}/apps/{APP_ID}/brand/logo", files={"file": ("TEST_iter25_logo.png", png, "image/png")})
        assert r.status_code == 200
        assert r.json().get("logo", "").startswith("/api/public/files/")

    def test_chat_upload_still_works(self):
        r = requests.post(f"{API}/public/chat/studio/upload",
                          files={"file": ("TEST_iter25_chat.txt", b"chat-hi", "text/plain")})
        assert r.status_code == 200
        assert r.json()["url"].startswith("/api/public/files/")

    def test_reply_attachment_still_works(self, admin):
        r = admin.post(f"{API}/apps/{APP_ID}/attachments",
                       files={"file": ("TEST_iter25_attach.txt", b"reply-attach", "text/plain")})
        assert r.status_code == 200
        assert r.json()["url"].startswith("/api/public/files/")
