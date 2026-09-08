"""Iteration 53 — Overview auto-sync with Site Mode.

Covers:
  - Hero PATCH → site_snapshot.headline/subtitle/description update + fresh updated_at
  - Navbar brand PATCH → apps.name syncs to brand
  - Add/delete page and add/remove block → pages/sections/total_sections update
  - Premium rebuild → snapshot + thumbnail change
  - Theme save → updated_at refreshes
  - POST /apps/{id}/site/sync-overview: 200 with snap, 400 for no-pages tenant, 401 unauth
  - Platform-wide: 4 seeded tenants each carry a snapshot whose headline == home hero title and brand == navbar brand
"""
import os
import time
import copy
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
EMAIL = "jaybernabe@luciodigital.com"
PASSWORD = "Lucio2026!"

def _first_tenant_id():
    """Tenant ids are environment data — resolve one at runtime."""
    import requests as _rq
    _s = _rq.Session()
    _s.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    rows = _s.get(f"{BASE}/api/apps", timeout=30).json()
    return rows[0]["app_id"] if rows else ""


TENANT_ID = _first_tenant_id()


def _live_tenant_ids():
    """Tenant ids are environment data, so resolve them at runtime instead of hardcoding."""
    sess = requests.Session()
    sess.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    return [a["app_id"] for a in sess.get(f"{BASE}/api/apps", timeout=30).json()]


SEEDED = _live_tenant_ids()
PRIMARY = SEEDED[0] if SEEDED else ""


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{BASE}/api/auth/login",
                  json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return sess


def _get_app(s, app_id):
    r = s.get(f"{BASE}/api/apps/{app_id}", timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _get_home_page(s, app_id):
    r = s.get(f"{BASE}/api/apps/{app_id}/pages", timeout=30)
    assert r.status_code == 200, r.text
    pages = r.json()
    # find slug "/" or first
    home = next((p for p in pages if p.get("slug") == "/"), pages[0])
    return home


# ---------- 1. Hero sync ----------
def test_hero_patch_syncs_snapshot(s):
    app_id = PRIMARY
    home = _get_home_page(s, app_id)
    original_blocks = copy.deepcopy(home["blocks"])
    hero_idx = next(i for i, b in enumerate(home["blocks"]) if b.get("type") == "hero")
    new_blocks = copy.deepcopy(home["blocks"])
    marker = f"ITER53-{int(time.time())}"
    new_blocks[hero_idx]["props"]["title"] = f"Head {marker}"
    new_blocks[hero_idx]["props"]["subtitle"] = f"Sub {marker}"
    new_blocks[hero_idx]["props"]["description"] = f"Desc {marker}"

    before = _get_app(s, app_id).get("site_snapshot", {}).get("updated_at")

    try:
        r = s.patch(f"{BASE}/api/apps/{app_id}/pages/{home['page_id']}",
                    json={"blocks": new_blocks}, timeout=30)
        assert r.status_code == 200, r.text

        app = _get_app(s, app_id)
        snap = app.get("site_snapshot") or {}
        assert snap.get("headline") == f"Head {marker}", snap
        assert snap.get("subtitle") == f"Sub {marker}", snap
        assert snap.get("description") == f"Desc {marker}", snap
        assert snap.get("updated_at") and snap.get("updated_at") != before
    finally:
        s.patch(f"{BASE}/api/apps/{app_id}/pages/{home['page_id']}",
                json={"blocks": original_blocks}, timeout=30)


# ---------- 2. Navbar brand → tenant name ----------
def test_navbar_brand_syncs_tenant_name(s):
    app_id = PRIMARY
    home = _get_home_page(s, app_id)
    original_blocks = copy.deepcopy(home["blocks"])
    nav_idx = next(i for i, b in enumerate(home["blocks"]) if b.get("type") == "navbar")
    original_name = _get_app(s, app_id).get("name")
    original_brand = original_blocks[nav_idx].get("props", {}).get("brand") or original_name

    new_blocks = copy.deepcopy(home["blocks"])
    marker = f"Brand{int(time.time()) % 100000}"
    new_blocks[nav_idx].setdefault("props", {})["brand"] = marker
    try:
        r = s.patch(f"{BASE}/api/apps/{app_id}/pages/{home['page_id']}",
                    json={"blocks": new_blocks}, timeout=30)
        assert r.status_code == 200, r.text
        app = _get_app(s, app_id)
        assert app.get("name") == marker, app.get("name")
        assert (app.get("site_snapshot") or {}).get("brand") == marker
    finally:
        # Restore: patch blocks first, which will re-sync name to original brand
        restore_blocks = copy.deepcopy(original_blocks)
        restore_blocks[nav_idx].setdefault("props", {})["brand"] = original_brand
        s.patch(f"{BASE}/api/apps/{app_id}/pages/{home['page_id']}",
                json={"blocks": restore_blocks}, timeout=30)


# ---------- 3. Counts and timestamp on add/remove page + block ----------
def test_page_add_delete_updates_counts(s):
    app_id = PRIMARY
    before = (_get_app(s, app_id).get("site_snapshot") or {}).get("pages")
    r = s.post(f"{BASE}/api/apps/{app_id}/pages",
               json={"name": "Iter53 Throwaway", "slug": "/iter53-tmp", "blocks": []}, timeout=30)
    assert r.status_code in (200, 201), r.text
    new_page = r.json()
    page_id = new_page.get("page_id") or new_page.get("id")
    try:
        after = (_get_app(s, app_id).get("site_snapshot") or {}).get("pages")
        assert after == before + 1, f"pages {before}->{after}"
    finally:
        d = s.delete(f"{BASE}/api/apps/{app_id}/pages/{page_id}", timeout=30)
        assert d.status_code in (200, 204), d.text
    restored = (_get_app(s, app_id).get("site_snapshot") or {}).get("pages")
    assert restored == before, f"pages didn't restore: {before} -> {restored}"


def test_block_add_remove_updates_sections(s):
    app_id = PRIMARY
    home = _get_home_page(s, app_id)
    original_blocks = copy.deepcopy(home["blocks"])
    snap_before = _get_app(s, app_id).get("site_snapshot") or {}
    sections_before = snap_before.get("sections")
    total_before = snap_before.get("total_sections")

    new_blocks = copy.deepcopy(home["blocks"]) + [{"type": "text", "props": {"text": "Iter53 tmp block"}}]
    try:
        r = s.patch(f"{BASE}/api/apps/{app_id}/pages/{home['page_id']}",
                    json={"blocks": new_blocks}, timeout=30)
        assert r.status_code == 200, r.text
        snap = _get_app(s, app_id).get("site_snapshot") or {}
        assert snap.get("sections") == sections_before + 1
        assert snap.get("total_sections") == total_before + 1
    finally:
        s.patch(f"{BASE}/api/apps/{app_id}/pages/{home['page_id']}",
                json={"blocks": original_blocks}, timeout=30)
    snap = _get_app(s, app_id).get("site_snapshot") or {}
    assert snap.get("sections") == sections_before


# ---------- 4. Theme save refreshes updated_at ----------
def test_theme_save_updates_snapshot(s):
    app_id = PRIMARY
    app = _get_app(s, app_id)
    theme = app.get("theme") or {}
    before = (app.get("site_snapshot") or {}).get("updated_at")
    time.sleep(1.1)
    r = s.put(f"{BASE}/api/apps/{app_id}/theme",
              json={"theme": theme or {"primary": "#111827"}}, timeout=30)
    assert r.status_code == 200, r.text
    after = (_get_app(s, app_id).get("site_snapshot") or {}).get("updated_at")
    assert after and after != before


# ---------- 5. Manual resync endpoint ----------
def test_resync_endpoint_ok(s):
    app_id = PRIMARY
    r = s.post(f"{BASE}/api/apps/{app_id}/site/sync-overview", timeout=30)
    assert r.status_code == 200, r.text
    snap = r.json()
    assert "headline" in snap and "updated_at" in snap


def test_resync_endpoint_unauth():
    r = requests.post(f"{BASE}/api/apps/{TENANT_ID}/site/sync-overview", timeout=30)
    assert r.status_code in (401, 403), r.status_code


def test_resync_endpoint_empty_tenant(s):
    """Creating a throwaway tenant with no pages should 400 on sync-overview."""
    r = s.post(f"{BASE}/api/apps", json={"name": "Iter53 EmptyTenant", "industry": "consulting"}, timeout=30)
    assert r.status_code in (200, 201), r.text
    new_app = r.json()
    app_id = new_app.get("app_id") or new_app.get("id")
    try:
        # Ensure no pages
        pages = s.get(f"{BASE}/api/apps/{app_id}/pages", timeout=30).json()
        if pages:
            pytest.skip("New tenant seeded with pages; can't test 400 path")
        r2 = s.post(f"{BASE}/api/apps/{app_id}/site/sync-overview", timeout=30)
        assert r2.status_code == 400, r2.text
    finally:
        # Per test-credentials rule: do NOT delete tenants
        pass


# ---------- 6. Platform-wide backfill ----------
@pytest.mark.parametrize("app_id", SEEDED)
def test_seeded_tenants_have_snapshot(s, app_id):
    app = _get_app(s, app_id)
    snap = app.get("site_snapshot") or {}
    assert snap, f"{app_id} has no site_snapshot"
    home = _get_home_page(s, app_id)
    hero = next((b for b in home["blocks"] if b.get("type") == "hero"), None)
    nav = next((b for b in home["blocks"] if b.get("type") == "navbar"), None)
    if hero:
        assert snap.get("headline") == str((hero.get("props") or {}).get("title") or "")[:160]
    if nav:
        brand = str((nav.get("props") or {}).get("brand") or "").strip()[:120]
        assert snap.get("brand") == brand
        if brand:
            assert app.get("name") == brand


# ---------- 7. Premium rebuild regenerates snapshot ----------
def test_premium_rebuild_updates_snapshot(s):
    """Use a throwaway tenant so we don't churn seeded content."""
    r = s.post(f"{BASE}/api/apps", json={"name": "Iter53 Rebuild", "industry": "consulting"}, timeout=30)
    assert r.status_code in (200, 201), r.text
    app_id = r.json().get("app_id") or r.json().get("id")

    # Unlock to allow rebuild
    s.post(f"{BASE}/api/apps/{app_id}/content-lock", json={"locked": False}, timeout=30)

    # Give it a starter site by calling build/rebuild
    r2 = s.post(f"{BASE}/api/apps/{app_id}/site/premium-rebuild",
                json={"niche": "hvac"}, timeout=60)
    if r2.status_code == 404:
        pytest.skip("premium-rebuild endpoint not present on this build")
    assert r2.status_code in (200, 201), r2.text

    snap_a = _get_app(s, app_id).get("site_snapshot") or {}
    assert snap_a, "no snapshot after first rebuild"
    head_a = snap_a.get("headline")
    thumb_a = snap_a.get("thumbnail")

    # switch look
    s.post(f"{BASE}/api/apps/{app_id}/content-lock", json={"locked": False}, timeout=30)
    r3 = s.post(f"{BASE}/api/apps/{app_id}/site/premium-rebuild",
                json={"niche": "healthcare"}, timeout=60)
    assert r3.status_code in (200, 201), r3.text
    snap_b = _get_app(s, app_id).get("site_snapshot") or {}
    assert snap_b, "no snapshot after second rebuild"
    # Either headline or thumbnail should differ between designs; at minimum updated_at differs
    assert snap_b.get("updated_at") != snap_a.get("updated_at")
    # loose expectation: something visible changed
    changed = (snap_b.get("headline") != head_a) or (snap_b.get("thumbnail") != thumb_a) \
              or (snap_b.get("sections") != snap_a.get("sections"))
    assert changed, f"design switch produced identical snapshot: {snap_a} vs {snap_b}"
