"""iter15 — Tenant Logo Upload feature tests.

Covers: POST/DELETE /apps/{id}/brand/logo, public file serving, page block propagation,
niche-preview brand preservation, premium-rebuild logo retention, export bundling
(site/assets/logo.<ext>, starter app sidebar).
"""
import io
import os
import struct
import time
import zlib
import zipfile
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
EMAIL = "jaybernabe@luciodigital.com"
PASSWORD = "Lucio2026!"


def _png_bytes(w=8, h=8):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff\x88\x22" * w for _ in range(h))
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    return sess


@pytest.fixture(scope="module")
def app_id(s):
    r = s.post(f"{BASE}/api/apps", json={"name": "TEST_iter15 Logo Co", "industry": "Legal", "product_type": "website"}, timeout=30)
    assert r.status_code == 200, r.text
    aid = r.json()["app_id"]
    # Wait for site build to populate pages; if not, force a premium rebuild
    for _ in range(30):
        pg = s.get(f"{BASE}/api/apps/{aid}/pages", timeout=15).json()
        if pg and any(b.get("type") in ("navbar", "footer") for p in pg for b in p.get("blocks", [])):
            break
        time.sleep(1)
    else:
        s.post(f"{BASE}/api/apps/{aid}/site/premium-rebuild", json={}, timeout=90)
    yield aid
    s.delete(f"{BASE}/api/apps/{aid}", timeout=15)


class TestLogoUpload:
    def test_upload_png_propagates_and_serves(self, s, app_id):
        png = _png_bytes()
        r = s.post(f"{BASE}/api/apps/{app_id}/brand/logo", files={"file": ("logo.png", png, "image/png")}, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["logo"].startswith("/api/public/files/omnistack/logos/")
        assert j["pages_updated"] > 0
        url = j["logo"]

        # Public GET
        img = requests.get(f"{BASE}{url}", timeout=20)
        assert img.status_code == 200
        assert img.headers.get("content-type", "").startswith("image/png")
        assert img.content[:8] == b"\x89PNG\r\n\x1a\n"

        # app doc reflects logo + brand_profile.logo
        app = s.get(f"{BASE}/api/apps/{app_id}", timeout=15).json()
        assert app.get("logo") == url
        assert (app.get("brand_profile") or {}).get("logo") == url

        # every navbar/footer has props.logo == url
        pages = s.get(f"{BASE}/api/apps/{app_id}/pages", timeout=15).json()
        nf_blocks = [b for p in pages for b in p.get("blocks", []) if b.get("type") in ("navbar", "footer")]
        assert nf_blocks, "no navbar/footer blocks found"
        for b in nf_blocks:
            assert b.get("props", {}).get("logo") == url, f"block {b.get('type')} missing logo"

    def test_reject_txt(self, s, app_id):
        r = s.post(f"{BASE}/api/apps/{app_id}/brand/logo", files={"file": ("bad.txt", b"hello", "text/plain")}, timeout=15)
        assert r.status_code == 400

    def test_reject_oversize(self, s, app_id):
        big = b"\x00" * (2 * 1024 * 1024 + 10)
        r = s.post(f"{BASE}/api/apps/{app_id}/brand/logo", files={"file": ("big.png", big, "image/png")}, timeout=30)
        assert r.status_code == 400

    def test_niche_preview_preserves_logo(self, s, app_id):
        r = s.post(f"{BASE}/api/apps/{app_id}/site/niche-preview", json={"niche": "hvac"}, timeout=60)
        assert r.status_code == 200, r.text
        j = r.json()
        logo = (j.get("preserved") or {}).get("logo")
        assert logo, f"preserved.logo missing in {j.get('preserved')}"
        first_block = j["pages"][0]["blocks"][0]
        assert first_block.get("type") == "navbar"
        assert first_block["props"].get("logo") == logo

    def test_premium_rebuild_keeps_logo(self, s, app_id):
        r = s.post(f"{BASE}/api/apps/{app_id}/site/premium-rebuild", json={}, timeout=90)
        assert r.status_code == 200, r.text
        pages = s.get(f"{BASE}/api/apps/{app_id}/pages", timeout=15).json()
        app = s.get(f"{BASE}/api/apps/{app_id}", timeout=15).json()
        logo = app["logo"]
        assert logo
        nf = [b for p in pages for b in p.get("blocks", []) if b.get("type") in ("navbar", "footer")]
        assert nf
        for b in nf:
            assert b["props"].get("logo") == logo

    def test_export_bundles_logo(self, s, app_id):
        r = s.get(f"{BASE}/api/apps/{app_id}/export/source", timeout=90)
        assert r.status_code == 200, r.text[:200]
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        logo_files = [n for n in names if n.startswith("site/assets/logo.")]
        assert logo_files, f"no site/assets/logo.* in export. Names sample: {names[:20]}"
        idx = zf.read("site/index.html").decode()
        assert "/assets/logo." in idx, "index.html doesn't reference /assets/logo.*"

    def test_delete_logo_clears_everything(self, s, app_id):
        r = s.delete(f"{BASE}/api/apps/{app_id}/brand/logo", timeout=20)
        assert r.status_code == 200
        assert r.json()["logo"] is None
        app = s.get(f"{BASE}/api/apps/{app_id}", timeout=15).json()
        assert app.get("logo") in (None, "")
        pages = s.get(f"{BASE}/api/apps/{app_id}/pages", timeout=15).json()
        for p in pages:
            for b in p.get("blocks", []):
                if b.get("type") in ("navbar", "footer"):
                    assert "logo" not in b.get("props", {}) or not b["props"].get("logo")

    def test_reupload_after_delete(self, s, app_id):
        png = _png_bytes(4, 4)
        r = s.post(f"{BASE}/api/apps/{app_id}/brand/logo", files={"file": ("logo2.png", png, "image/png")}, timeout=30)
        assert r.status_code == 200
        url2 = r.json()["logo"]
        assert url2 and url2.startswith("/api/public/files/")
        img = requests.get(f"{BASE}{url2}", timeout=15)
        assert img.status_code == 200
