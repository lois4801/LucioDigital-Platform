"""Iter92: Per-page marquee overrides + client portal (text-only) access.

Covers:
- GET /api/apps/{id}/marquee returns pages + pages_list (home first)
- PUT /api/apps/{id}/marquee/pages/{slug} stores only supplied non-blank fields
- Range validation (speed 0.2-3, opacity 0.05-1, font_size 0.5-2.5) and text 160 cap
- Blank string removes an override field (inherits site-wide)
- DELETE clears whole page override
- GET /api/public/site/{token} exposes marquee.pages map
- Site-wide PUT does NOT wipe page overrides
"""
import os
import pytest
import requests
from pathlib import Path


def _load_frontend_url():
    env = Path("/app/frontend/.env").read_text()
    for line in env.splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip()
    return None


BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_url()).rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"
APP = "app_testlab"
TEST_SLUG = "/app-showcase-pro-4"   # per review request


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    yield s
    # Cleanup: clear any page override we may have left behind
    try:
        s.delete(f"{API}/apps/{APP}/marquee/pages{TEST_SLUG}")
    except Exception:
        pass


# ── GET returns pages + pages_list ────────────────────────────────────
def test_get_marquee_returns_pages_and_list(admin):
    r = admin.get(f"{API}/apps/{APP}/marquee")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "pages" in d and isinstance(d["pages"], dict)
    assert "pages_list" in d and isinstance(d["pages_list"], list)
    assert len(d["pages_list"]) > 0
    # home '/' first
    assert d["pages_list"][0]["slug"] == "/", f"home should be first: {d['pages_list'][:2]}"
    # each entry has slug + name
    for p in d["pages_list"]:
        assert "slug" in p and "name" in p


# ── PUT /marquee/pages/{slug} stores only supplied non-blank fields ──
def test_put_page_stores_only_supplied_fields(admin):
    admin.delete(f"{API}/apps/{APP}/marquee/pages{TEST_SLUG}")  # start clean
    r = admin.put(f"{API}/apps/{APP}/marquee/pages{TEST_SLUG}", json={"top_text": "TEST_PAGE_TOP"})
    assert r.status_code == 200, r.text
    d = r.json()
    pg = (d.get("pages") or {}).get(TEST_SLUG) or {}
    assert pg == {"top_text": "TEST_PAGE_TOP"}, f"expected only top_text, got {pg}"


def test_put_page_range_validation(admin):
    for field, value in [("speed", 0.1), ("speed", 3.5),
                         ("stroke_opacity", 0.01), ("stroke_opacity", 1.5),
                         ("font_size", 0.4), ("font_size", 2.6)]:
        r = admin.put(f"{API}/apps/{APP}/marquee/pages{TEST_SLUG}", json={field: value})
        assert r.status_code == 400, f"expected 400 for {field}={value}, got {r.status_code}"


def test_put_page_caps_text_at_160(admin):
    long = "B" * 300
    r = admin.put(f"{API}/apps/{APP}/marquee/pages{TEST_SLUG}", json={"top_text": long})
    assert r.status_code == 200
    pg = (r.json().get("pages") or {}).get(TEST_SLUG) or {}
    assert len(pg.get("top_text", "")) == 160


# ── Blank string removes that override field ─────────────────────────
def test_blank_removes_override_field(admin):
    # set both then blank top_text -> only bottom_text should remain
    admin.put(f"{API}/apps/{APP}/marquee/pages{TEST_SLUG}", json={"top_text": "T", "bottom_text": "B"})
    r = admin.put(f"{API}/apps/{APP}/marquee/pages{TEST_SLUG}", json={"top_text": ""})
    assert r.status_code == 200
    pg = (r.json().get("pages") or {}).get(TEST_SLUG) or {}
    assert "top_text" not in pg
    assert pg.get("bottom_text") == "B"


# ── DELETE clears whole page override ─────────────────────────────────
def test_delete_page_clears_override(admin):
    admin.put(f"{API}/apps/{APP}/marquee/pages{TEST_SLUG}", json={"top_text": "X", "bottom_text": "Y"})
    r = admin.delete(f"{API}/apps/{APP}/marquee/pages{TEST_SLUG}")
    assert r.status_code == 200
    pages = r.json().get("pages") or {}
    assert TEST_SLUG not in pages


# ── Public site exposes pages map ────────────────────────────────────
def test_public_site_includes_pages_map(admin):
    # seed one override
    admin.put(f"{API}/apps/{APP}/marquee/pages{TEST_SLUG}", json={"top_text": "PUBLIC_TEST_TOP"})
    apps = admin.get(f"{API}/apps").json()
    lst = apps if isinstance(apps, list) else apps.get("apps", [])
    tok = next((a.get("preview_token") for a in lst if a.get("app_id") == APP), None)
    assert tok, "no preview_token for testlab"
    r = requests.get(f"{API}/public/site/{tok}")
    assert r.status_code == 200, r.text
    d = r.json()
    app = d.get("app") or d
    mq = app.get("marquee") or {}
    assert "pages" in mq, f"marquee.pages missing: keys={list(mq.keys())}"
    pg = mq["pages"].get(TEST_SLUG) or {}
    assert pg.get("top_text") == "PUBLIC_TEST_TOP"
    # cleanup
    admin.delete(f"{API}/apps/{APP}/marquee/pages{TEST_SLUG}")


# ── Site-wide PUT preserves page overrides ───────────────────────────
def test_sitewide_put_does_not_wipe_pages(admin):
    admin.put(f"{API}/apps/{APP}/marquee/pages{TEST_SLUG}", json={"top_text": "KEEP_ME"})
    r = admin.put(f"{API}/apps/{APP}/marquee", json={"top_text": "SITE_WIDE_TOP"})
    assert r.status_code == 200
    d = r.json()
    pg = (d.get("pages") or {}).get(TEST_SLUG) or {}
    assert pg.get("top_text") == "KEEP_ME", f"page override lost: {pg}"
    # verify via GET too
    g = admin.get(f"{API}/apps/{APP}/marquee").json()
    assert (g.get("pages") or {}).get(TEST_SLUG, {}).get("top_text") == "KEEP_ME"
    # cleanup
    admin.delete(f"{API}/apps/{APP}/marquee/pages{TEST_SLUG}")
    admin.post(f"{API}/apps/{APP}/marquee/reset")


# ── Slug without leading slash still resolves ────────────────────────
def test_put_page_slug_no_leading_slash(admin):
    # Endpoint uses {slug:path} so trailing slug can be with or without leading '/'
    r = admin.put(f"{API}/apps/{APP}/marquee/pages/some-other-page", json={"top_text": "SLUGTEST"})
    assert r.status_code == 200
    pages = r.json().get("pages") or {}
    assert "/some-other-page" in pages
    admin.delete(f"{API}/apps/{APP}/marquee/pages/some-other-page")
