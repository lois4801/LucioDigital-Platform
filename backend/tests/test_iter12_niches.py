"""iter12 - Test niche switcher: site-niches, niche-preview, premium-rebuild industry mapping"""
import os, pytest, requests, uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
EMAIL = "jaybernabe@luciodigital.com"
PASSWORD = "Lucio2026!"

NEW_NICHES = ["legal", "education", "real_estate", "restaurant", "events"]
EXPECTED_BRANDS = {
    "legal": "Whitfield & Grant LLP",
    "education": "Brightwater Academy",
    "real_estate": "Harbour & Vale Realty",
    "restaurant": "Ember & Oak",
    "events": "Lumen Events Co.",
}


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def website_app(session):
    """Pick a non-demo website app or create one."""
    r = session.get(f"{BASE_URL}/api/apps")
    assert r.status_code == 200
    apps = r.json()
    # try to find a non-demo (not APP_MAP name)
    demo = {"Nexus Commerce", "Orbit SaaS Portal", "Fleet Command", "Aura Wellness", "Ledger AI Portfolio", "Studio Booking"}
    non_demo = [a for a in apps if a.get("name") not in demo and a.get("kind", "website") == "website"]
    if non_demo:
        return non_demo[0]
    # create
    r = session.post(f"{BASE_URL}/api/apps", json={"name": f"TEST_iter12_{uuid.uuid4().hex[:6]}", "kind": "website", "industry": "SaaS Portals"})
    assert r.status_code in (200, 201), r.text
    return r.json()


# ---- /api/site-niches ----
def test_site_niches_lists_16_including_new(session):
    r = session.get(f"{BASE_URL}/api/site-niches")
    assert r.status_code == 200
    niches = r.json()
    assert isinstance(niches, list)
    assert len(niches) == 16, f"expected 16 niches, got {len(niches)}"
    keys = {n["key"] for n in niches}
    for nk in NEW_NICHES:
        assert nk in keys, f"missing {nk} in niches"
    # each niche has required fields
    required = {"key", "brand", "industry", "mood", "primary", "secondary", "hero", "title", "sections"}
    for n in niches:
        assert required.issubset(n.keys()), f"niche {n.get('key')} missing fields: {required - set(n.keys())}"


# ---- niche-preview per niche ----
@pytest.mark.parametrize("niche", NEW_NICHES)
def test_niche_preview_returns_expected_brand_and_pages(session, website_app, niche):
    app_id = website_app["app_id"]
    # snapshot before
    before = session.get(f"{BASE_URL}/api/apps/{app_id}/pages").json()
    r = session.post(f"{BASE_URL}/api/apps/{app_id}/site/niche-preview", json={"niche": niche})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["niche"] == niche
    assert body["brand"] == EXPECTED_BRANDS[niche]
    assert body["theme"]["mode"] == "dark"
    pages = body["pages"]
    assert len(pages) == 4
    for p in pages:
        assert "blocks" in p and len(p["blocks"]) > 0
    # verify home has expected block types
    home = next(p for p in pages if p["slug"] == "/")
    types = [b["type"] for b in home["blocks"]]
    for t in ("hero", "stats", "testimonials", "video", "cta"):
        assert t in types, f"[{niche}] home missing block type '{t}': {types}"
    hero = next(b for b in home["blocks"] if b["type"] == "hero")
    assert hero["props"].get("variant") == "cover"
    # non-destructive: pages unchanged
    after = session.get(f"{BASE_URL}/api/apps/{app_id}/pages").json()
    assert before == after, f"[{niche}] preview modified pages!"


def test_niche_preview_unknown_returns_404(session, website_app):
    r = session.post(f"{BASE_URL}/api/apps/{website_app['app_id']}/site/niche-preview", json={"niche": "nonexistent_niche_xyz"})
    assert r.status_code == 404


# ---- industry-specific content ----
def test_legal_has_practice_areas_and_case_results(session, website_app):
    r = session.post(f"{BASE_URL}/api/apps/{website_app['app_id']}/site/niche-preview", json={"niche": "legal"})
    home = next(p for p in r.json()["pages"] if p["slug"] == "/")
    # features with "Practice Areas" heading
    features = [b for b in home["blocks"] if b["type"] == "features"]
    assert any("Practice Areas" in (b["props"].get("heading") or "") for b in features), f"features headings: {[b['props'].get('heading') for b in features]}"
    charts = [b for b in home["blocks"] if b["type"] == "chart"]
    assert any("Case" in (b["props"].get("heading") or "") or "Results" in (b["props"].get("heading") or "") for b in charts)


def test_restaurant_has_private_dining_pricing(session, website_app):
    r = session.post(f"{BASE_URL}/api/apps/{website_app['app_id']}/site/niche-preview", json={"niche": "restaurant"})
    home = next(p for p in r.json()["pages"] if p["slug"] == "/")
    pricing = [b for b in home["blocks"] if b["type"] == "pricing"]
    assert pricing, "restaurant home has no pricing block"
    joined = " ".join((b["props"].get("heading") or "") for b in pricing)
    assert "Private Dining" in joined or "Events" in joined, f"pricing headings: {joined}"


def test_events_has_planning_packages(session, website_app):
    r = session.post(f"{BASE_URL}/api/apps/{website_app['app_id']}/site/niche-preview", json={"niche": "events"})
    home = next(p for p in r.json()["pages"] if p["slug"] == "/")
    pricing = [b for b in home["blocks"] if b["type"] == "pricing"]
    joined = " ".join((b["props"].get("heading") or "") for b in pricing)
    assert "Planning Packages" in joined, f"events pricing headings: {joined}"


# ---- premium-rebuild with explicit niche on non-demo app ----
def test_premium_rebuild_restaurant_on_non_demo(session):
    # create a fresh non-demo app
    r = session.post(f"{BASE_URL}/api/apps", json={"name": f"TEST_iter12_rebuild_{uuid.uuid4().hex[:6]}", "kind": "website", "industry": "SaaS Portals"})
    assert r.status_code in (200, 201), r.text
    app_id = r.json()["app_id"]
    r = session.post(f"{BASE_URL}/api/apps/{app_id}/site/premium-rebuild", json={"niche": "restaurant"})
    assert r.status_code == 200, r.text
    assert r.json()["niche"] == "restaurant"
    # verify pages now have restaurant content (brand = Ember & Oak on demo-map names, or app's own name otherwise)
    pages = session.get(f"{BASE_URL}/api/apps/{app_id}/pages").json()
    home = next(p for p in pages if p["slug"] == "/")
    types = [b["type"] for b in home["blocks"]]
    assert "hero" in types and "pricing" in types
    # cleanup
    session.delete(f"{BASE_URL}/api/apps/{app_id}")


# ---- industry auto-mapping via premium-rebuild without niche ----
@pytest.mark.parametrize("industry,expected", [
    ("Legal", "legal"), ("Education", "education"), ("Real Estate", "real_estate"),
    ("Restaurants", "restaurant"), ("Events", "events"),
])
def test_industry_auto_maps_to_niche(session, industry, expected):
    r = session.post(f"{BASE_URL}/api/apps", json={"name": f"TEST_iter12_map_{uuid.uuid4().hex[:6]}", "kind": "website", "industry": industry})
    assert r.status_code in (200, 201), r.text
    app_id = r.json()["app_id"]
    try:
        r = session.post(f"{BASE_URL}/api/apps/{app_id}/site/premium-rebuild", json={})
        assert r.status_code == 200, r.text
        assert r.json()["niche"] == expected, f"industry {industry} → expected {expected}, got {r.json()['niche']}"
    finally:
        session.delete(f"{BASE_URL}/api/apps/{app_id}")
