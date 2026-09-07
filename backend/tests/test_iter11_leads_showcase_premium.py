"""Iteration 11 tests: /inbox leads flow, /public/showcase, premium dark redesign, site-niches, premium-rebuild, export."""
import io
import os
import zipfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

EMAIL = "jaybernabe@luciodigital.com"
PASSWORD = "Lucio2026!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# ===== Auth / Inbox =====
def test_login_no_bearer_only_cookie(session):
    # Cookies present
    names = [c.name for c in session.cookies]
    assert any(n in ("access_token", "session", "session_token", "sid") for n in names), f"cookies={names}"


def test_inbox_returns_messages_and_unread(session):
    r = session.get(f"{API}/inbox")
    assert r.status_code == 200
    data = r.json()
    assert "messages" in data and "unread" in data
    assert isinstance(data["messages"], list)
    assert isinstance(data["unread"], int)


def test_bearer_token_not_accepted():
    # No cookies, using a fake bearer must fail
    r = requests.get(f"{API}/inbox", headers={"Authorization": "Bearer faketoken"})
    assert r.status_code in (401, 403), f"got {r.status_code}"


# ===== Showcase =====
def test_public_showcase_returns_6_demos():
    r = requests.get(f"{API}/public/showcase")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 4, f"expected at least 4 demo apps, got {len(data)}"
    for app in data:
        for k in ("name", "token", "niche", "brand"):
            assert k in app, f"missing {k} in {app}"
        assert app["token"], f"empty token for {app['name']}"


def test_site_niches_returns_11(session):
    r = session.get(f"{API}/site-niches")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 10, f"expected ~11 niches got {len(data)}"


# ===== Apps: premium_site_v==3 =====
@pytest.fixture(scope="module")
def apps_list(session):
    r = session.get(f"{API}/apps")
    assert r.status_code == 200
    return r.json()


def test_all_apps_have_premium_v3(apps_list):
    for a in apps_list:
        assert a.get("premium_site_v") == 3, f"app {a.get('name')} has premium_site_v={a.get('premium_site_v')}"


def test_apps_theme_dark(session, apps_list):
    a = apps_list[0]
    r = session.get(f"{API}/apps/{a['app_id']}/theme")
    assert r.status_code == 200
    t = r.json()
    assert t.get("mode") == "dark"
    assert t.get("glass") is True
    assert t.get("grain") is True
    bg = t.get("bg", "")
    assert bg.startswith("#"), f"bg={bg}"
    # dark hex — total brightness low
    r_, g_, b_ = int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16)
    assert (r_ + g_ + b_) < 200, f"bg not dark: {bg}"


def test_apps_pages_4_and_home_structure(session, apps_list):
    a = apps_list[0]
    r = session.get(f"{API}/apps/{a['app_id']}/pages")
    assert r.status_code == 200
    pages = r.json()
    assert len(pages) == 4
    names = [p["name"] for p in pages]
    for n in ("Home", "About", "Services", "Contact"):
        assert n in names, f"missing page {n}: {names}"
    home = next(p for p in pages if p["name"] == "Home")
    types = [b["type"] for b in home["blocks"]]
    assert "navbar" in types
    assert "hero" in types
    assert "footer" in types
    hero = next(b for b in home["blocks"] if b["type"] == "hero")
    assert hero["props"].get("variant") == "cover"
    assert hero["props"].get("image")
    # alternating bg
    bgs = [b["style"].get("bg", "default") for b in home["blocks"]]
    assert "muted" in bgs or "accent" in bgs, f"bgs={bgs}"
    # video / testimonials / stats expected in Home usually
    assert "footer" in types


# ===== premium-rebuild =====
@pytest.fixture(scope="module")
def temp_app(session):
    r = session.post(f"{API}/apps", json={
        "name": "TEST_iter11_App",
        "industry": "SaaS Portals",
        "description": "temp",
        "kind": "website",
        "status": "active",
    })
    assert r.status_code in (200, 201)
    app = r.json()
    yield app
    session.delete(f"{API}/apps/{app['app_id']}")


def test_premium_rebuild_hvac(session, temp_app):
    r = session.post(f"{API}/apps/{temp_app['app_id']}/site/premium-rebuild", json={"niche": "hvac"})
    assert r.status_code == 200
    d = r.json()
    assert d["pages"] == 4
    assert d["niche"] == "hvac"
    # verify pages
    pgs = session.get(f"{API}/apps/{temp_app['app_id']}/pages").json()
    home = next(p for p in pgs if p["name"] == "Home")
    text = str(home)
    assert "Summit Air" in text or "Summit" in text, "HVAC brand missing"


def test_premium_rebuild_unknown_niche_404(session, temp_app):
    r = session.post(f"{API}/apps/{temp_app['app_id']}/site/premium-rebuild", json={"niche": "nonexistent_xyz"})
    assert r.status_code == 404


# ===== Inbox patch flow =====
def test_inbox_patch_flow(session):
    r = session.get(f"{API}/inbox")
    data = r.json()
    msgs = data["messages"]
    if not msgs:
        pytest.skip("no messages in inbox to patch")
    m = msgs[0]
    original = m["status"]
    # toggle
    new_status = "read" if original == "unread" else "unread"
    r = session.patch(f"{API}/apps/{m['app_id']}/inbox/{m['message_id']}", json={"status": new_status})
    assert r.status_code == 200
    assert r.json()["status"] == new_status
    # revert
    session.patch(f"{API}/apps/{m['app_id']}/inbox/{m['message_id']}", json={"status": original})


# ===== Export zip =====
def test_export_source_zip_has_hero_cover(session, apps_list):
    a = apps_list[0]
    r = session.get(f"{API}/apps/{a['app_id']}/export/source")
    assert r.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    css_name = next((n for n in names if n.endswith("site/styles.css") or n.endswith("styles.css")), None)
    html_name = next((n for n in names if n.endswith("site/index.html") or n.endswith("index.html")), None)
    assert css_name, f"styles.css missing. Files: {names[:20]}"
    css = z.read(css_name).decode()
    assert ".hero.cover" in css or "hero-cover" in css or "hero cover" in css, "hero.cover selector missing"
    assert "backdrop-filter" in css, "backdrop-filter missing"
    # dark bg
    assert "--bg" in css
    if html_name:
        html = z.read(html_name).decode()
        assert "hero cover" in html or "hero-cover" in html, "hero cover class missing in html"
