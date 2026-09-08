"""Iteration 54 — Overview card title/description sync + label-override immunity + industry stability.

Covers:
  - Overview card title (label-overview-card-title): apps.name syncs to navbar brand
  - Overview card desc  (label-overview-card-desc):  apps.description syncs to hero description or subtitle
  - Hero 'description' takes precedence over 'subtitle' when both exist
  - ui_labels override for overview_card_title does NOT change apps.name / rendered title (frontend reads appDoc.name directly)
  - apps.industry is NOT polluted by Site Mode saves; stays the niche label
  - Landing showcase still shows tenant name + tags
  - Manual POST /site/sync-overview still works
"""
import os
import time
import copy
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
EMAIL = "jaybernabe@luciodigital.com"
PASSWORD = "Lucio2026!"

def _live_tenants():
    """Tenant ids are environment data, so resolve them at runtime instead of hardcoding."""
    sess = requests.Session()
    sess.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    rows = sess.get(f"{BASE}/api/apps", timeout=30).json()
    return [(a["app_id"], a.get("industry")) for a in rows]


TENANTS = _live_tenants()
PRIMARY = TENANTS[0][0] if TENANTS else ""


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


def _get_home(s, app_id):
    r = s.get(f"{BASE}/api/apps/{app_id}/pages", timeout=30)
    assert r.status_code == 200
    pages = r.json()
    return next((p for p in pages if p.get("slug") == "/"), pages[0])


def _patch_home_blocks(s, app_id, page_id, blocks):
    r = s.patch(f"{BASE}/api/apps/{app_id}/pages/{page_id}",
                json={"blocks": blocks}, timeout=30)
    assert r.status_code == 200, r.text


# ---------- 1. Overview card TITLE syncs (apps.name mirrors navbar brand) ----------
def test_overview_card_title_syncs_from_navbar_brand(s):
    app_id = PRIMARY
    home = _get_home(s, app_id)
    original_blocks = copy.deepcopy(home["blocks"])
    nav_idx = next(i for i, b in enumerate(home["blocks"]) if b.get("type") == "navbar")
    original_brand = original_blocks[nav_idx].get("props", {}).get("brand") \
        or _get_app(s, app_id).get("name")

    marker = f"Iter54Brand{int(time.time()) % 100000}"
    new_blocks = copy.deepcopy(original_blocks)
    new_blocks[nav_idx].setdefault("props", {})["brand"] = marker
    try:
        _patch_home_blocks(s, app_id, home["page_id"], new_blocks)
        app = _get_app(s, app_id)
        assert app.get("name") == marker, f"apps.name did not sync: {app.get('name')}"
        assert (app.get("site_snapshot") or {}).get("brand") == marker
    finally:
        restore = copy.deepcopy(original_blocks)
        restore[nav_idx].setdefault("props", {})["brand"] = original_brand
        _patch_home_blocks(s, app_id, home["page_id"], restore)
    # Confirm restore
    assert _get_app(s, app_id).get("name") == original_brand


# ---------- 2. Overview card DESC syncs from hero subtitle ----------
def test_overview_card_desc_syncs_from_hero_subtitle(s):
    app_id = PRIMARY
    home = _get_home(s, app_id)
    original_blocks = copy.deepcopy(home["blocks"])
    hero_idx = next(i for i, b in enumerate(home["blocks"]) if b.get("type") == "hero")
    original_desc = _get_app(s, app_id).get("description")

    marker = f"Iter54 subtitle marker {int(time.time())}"
    new_blocks = copy.deepcopy(original_blocks)
    # Clear description so subtitle wins
    if "description" in (new_blocks[hero_idx].get("props") or {}):
        new_blocks[hero_idx]["props"]["description"] = ""
    new_blocks[hero_idx].setdefault("props", {})["subtitle"] = marker
    try:
        _patch_home_blocks(s, app_id, home["page_id"], new_blocks)
        app = _get_app(s, app_id)
        assert app.get("description") == marker, \
            f"apps.description did not sync: got {app.get('description')!r}"
        assert (app.get("site_snapshot") or {}).get("subtitle") == marker
    finally:
        _patch_home_blocks(s, app_id, home["page_id"], original_blocks)
    # Confirm restore roughly
    app = _get_app(s, app_id)
    # description should have been restored via re-sync from original blocks
    assert app.get("description") is not None


# ---------- 3. Hero description takes precedence over subtitle ----------
def test_hero_description_takes_precedence(s):
    app_id = PRIMARY
    home = _get_home(s, app_id)
    original_blocks = copy.deepcopy(home["blocks"])
    hero_idx = next(i for i, b in enumerate(home["blocks"]) if b.get("type") == "hero")

    desc_marker = f"Iter54 DESC wins {int(time.time())}"
    sub_marker = f"Iter54 SUB should lose {int(time.time())}"
    new_blocks = copy.deepcopy(original_blocks)
    new_blocks[hero_idx].setdefault("props", {})["description"] = desc_marker
    new_blocks[hero_idx]["props"]["subtitle"] = sub_marker
    try:
        _patch_home_blocks(s, app_id, home["page_id"], new_blocks)
        app = _get_app(s, app_id)
        assert app.get("description") == desc_marker, \
            f"description did not win over subtitle: {app.get('description')!r}"
        assert (app.get("site_snapshot") or {}).get("description") == desc_marker
    finally:
        _patch_home_blocks(s, app_id, home["page_id"], original_blocks)


# ---------- 4. Stale ui_labels override for overview_card_title does NOT shadow ----------
def test_ui_label_override_does_not_shadow_overview_title(s):
    app_id = PRIMARY
    home = _get_home(s, app_id)
    original_blocks = copy.deepcopy(home["blocks"])
    nav_idx = next(i for i, b in enumerate(home["blocks"]) if b.get("type") == "navbar")
    original_brand = original_blocks[nav_idx].get("props", {}).get("brand") \
        or _get_app(s, app_id).get("name")

    stale_label = f"STALE-Override-{int(time.time()) % 100000}"
    live_brand = f"Iter54Live{int(time.time()) % 100000}"

    # 1) Save a ui_labels override for overview_card_title
    put = s.put(f"{BASE}/api/apps/{app_id}/ui_labels",
                json={"labels": {"overview_card_title": stale_label}, "scope": "tenant"},
                timeout=30)
    assert put.status_code in (200, 201, 204), put.text

    try:
        # 2) Change navbar brand -> apps.name must be live_brand (NOT stale_label)
        new_blocks = copy.deepcopy(original_blocks)
        new_blocks[nav_idx].setdefault("props", {})["brand"] = live_brand
        _patch_home_blocks(s, app_id, home["page_id"], new_blocks)
        app = _get_app(s, app_id)
        assert app.get("name") == live_brand, \
            f"stale label shadowed apps.name: {app.get('name')}"
    finally:
        # cleanup: delete override + restore blocks
        s.delete(f"{BASE}/api/apps/{app_id}/ui_labels?scope=tenant",
                 timeout=30)
        restore = copy.deepcopy(original_blocks)
        restore[nav_idx].setdefault("props", {})["brand"] = original_brand
        _patch_home_blocks(s, app_id, home["page_id"], restore)


# ---------- 5. Industry chip stays niche label, not polluted by Site Mode ----------
@pytest.mark.parametrize("app_id,expected_industry", TENANTS)
def test_industry_not_polluted_by_site_mode(s, app_id, expected_industry):
    """After a hero PATCH, apps.industry stays the niche label; site_snapshot doesn't leak into it."""
    app_before = _get_app(s, app_id)
    industry_before = app_before.get("industry")
    tags_before = app_before.get("tags") or []
    # allow niche label case-insensitive match
    assert industry_before and industry_before.strip().lower() == expected_industry.strip().lower(), \
        f"Expected {expected_industry!r} pre-sync, got {industry_before!r}"

    home = _get_home(s, app_id)
    original_blocks = copy.deepcopy(home["blocks"])
    hero_idx = next((i for i, b in enumerate(home["blocks"]) if b.get("type") == "hero"), None)
    if hero_idx is None:
        pytest.skip("no hero block")

    # Push a hero badge-like string that must NOT become industry
    badge = "ISO 45001 · COR™ Certified · Bonded"
    new_blocks = copy.deepcopy(original_blocks)
    new_blocks[hero_idx].setdefault("props", {})["badge"] = badge
    new_blocks[hero_idx]["props"]["subtitle"] = f"Iter54 industry probe {int(time.time())}"

    try:
        _patch_home_blocks(s, app_id, home["page_id"], new_blocks)
        app = _get_app(s, app_id)
        assert app.get("industry", "").strip().lower() == expected_industry.strip().lower(), \
            f"industry polluted: {app.get('industry')!r}"
        assert badge not in (app.get("industry") or "")
        # Tags must be untouched
        assert (app.get("tags") or []) == tags_before, \
            f"tags churned: before={tags_before} after={app.get('tags')}"
    finally:
        _patch_home_blocks(s, app_id, home["page_id"], original_blocks)
    # Post-restore: still correct industry
    assert _get_app(s, app_id).get("industry", "").strip().lower() == expected_industry.strip().lower()


# ---------- 6. Cross-tenant brand + hero-subtitle sync ----------
@pytest.mark.parametrize("app_id,_ind", TENANTS)
def test_cross_tenant_brand_and_subtitle_sync(s, app_id, _ind):
    home = _get_home(s, app_id)
    original_blocks = copy.deepcopy(home["blocks"])
    nav_idx = next((i for i, b in enumerate(home["blocks"]) if b.get("type") == "navbar"), None)
    hero_idx = next((i for i, b in enumerate(home["blocks"]) if b.get("type") == "hero"), None)
    if nav_idx is None or hero_idx is None:
        pytest.skip("no navbar/hero block")

    original_brand = original_blocks[nav_idx].get("props", {}).get("brand") \
        or _get_app(s, app_id).get("name")

    brand_marker = f"Iter54N{int(time.time()) % 100000}"
    sub_marker = f"Iter54 sub {app_id[-4:]} {int(time.time())}"
    new_blocks = copy.deepcopy(original_blocks)
    new_blocks[nav_idx].setdefault("props", {})["brand"] = brand_marker
    new_blocks[hero_idx].setdefault("props", {})["subtitle"] = sub_marker
    # clear description so subtitle wins
    if "description" in (new_blocks[hero_idx].get("props") or {}):
        new_blocks[hero_idx]["props"]["description"] = ""

    try:
        _patch_home_blocks(s, app_id, home["page_id"], new_blocks)
        app = _get_app(s, app_id)
        assert app.get("name") == brand_marker
        assert app.get("description") == sub_marker
    finally:
        restore = copy.deepcopy(original_blocks)
        restore[nav_idx].setdefault("props", {})["brand"] = original_brand
        _patch_home_blocks(s, app_id, home["page_id"], restore)


# ---------- 7. Landing showcase still shows tenant name + niche tag ----------
def test_landing_shows_names_and_niches(s):
    r = requests.get(f"{BASE}/api/public/landing/tenants", timeout=30)
    assert r.status_code == 200, r.text
    payload = r.json()
    items = payload if isinstance(payload, list) else payload.get("tenants") or payload.get("items") or []
    assert items, f"landing tenants empty: {payload}"
    # Each starred tenant should have a non-empty name and either an industry or a tag
    for it in items:
        assert it.get("name"), it
        # niche or tags array present
        assert it.get("industry") or it.get("niche") or it.get("tags"), it


# ---------- 8. Manual sync-overview endpoint still works ----------
def test_sync_overview_endpoint_still_works(s):
    r = s.post(f"{BASE}/api/apps/{PRIMARY}/site/sync-overview", timeout=30)
    assert r.status_code == 200, r.text
    snap = r.json()
    assert "headline" in snap and "updated_at" in snap
