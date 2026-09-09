"""Iter64 — Studio 2026 platform skin + 16 new templates + per-tenant Studio site skin.

Coverage:
  - PUT /api/me/ui-skin persists {classic,studio} on the user and echoes {skin}
  - GET /api/public/templates returns exactly 32 templates; 16 studio:true; new keys present
  - GET /api/public/templates/{key} for every studio key -> 4 pages + theme.site_skin == 'studio'
  - Creating a tenant from a new studio template sets theme.site_skin == 'studio' and builds 4 pages
  - Public /api/site/{token} works after preview regenerate (basic path used by frontend)

Owns and purges only tenants it created (TEST_iter64_*).
"""
import os
import pytest
import requests

def _load_base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            for line in open("/app/frontend/.env"):
                if line.startswith("REACT_APP_BACKEND_URL="):
                    v = line.split("=", 1)[1].strip()
                    break
        except FileNotFoundError:
            pass
    assert v, "REACT_APP_BACKEND_URL missing"
    return v.rstrip("/")

BASE_URL = _load_base()
API = f"{BASE_URL}/api"

ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}

NEW_KEYS = ["veterinary", "dental", "accounting", "landscaping", "photography", "automotive",
            "beauty", "insurance", "pet_grooming", "hvac_plumbing", "coworking", "wellness",
            "cleaning", "music_school", "nonprofit", "architecture"]


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")
    return s


@pytest.fixture(scope="module")
def created_apps():
    ids = []
    yield ids
    # teardown — purge only what we created
    s = requests.Session()
    s.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    for aid in ids:
        try:
            s.post(f"{API}/apps/{aid}/archive", json={"archived": True}, timeout=15)
            s.delete(f"{API}/apps/{aid}", timeout=15)
        except Exception:
            pass


# ---------- Public templates listing ----------
class TestTemplateListing:
    def test_lists_32_templates(self, sess):
        r = sess.get(f"{API}/public/templates", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 32, f"expected 32 got {data['count']}"
        assert len(data["templates"]) == 32

    def test_16_studio_flagged(self, sess):
        r = sess.get(f"{API}/public/templates", timeout=15)
        studio = [t for t in r.json()["templates"] if t.get("studio")]
        assert len(studio) == 16, f"expected 16 studio templates, got {len(studio)}"
        keys = {t["key"] for t in studio}
        assert set(NEW_KEYS).issubset(keys), f"missing: {set(NEW_KEYS)-keys}"

    def test_17_categories(self, sess):
        r = sess.get(f"{API}/public/templates", timeout=15)
        cats = r.json()["categories"]
        assert len(cats) == 17, f"expected 17 categories got {len(cats)}: {cats}"

    def test_distinct_palettes_and_fonts(self, sess):
        r = sess.get(f"{API}/public/templates", timeout=15)
        studio = [t for t in r.json()["templates"] if t["key"] in NEW_KEYS]
        # every new template has its own primary + font_heading combo
        combos = {(t["primary"], t["font_heading"]) for t in studio}
        # allow small overlap; at least 12 unique combos out of 16
        assert len(combos) >= 12, f"too few unique palette/font combos: {combos}"


# ---------- Per-template detail (4 pages, studio site_skin) ----------
class TestTemplateDetails:
    @pytest.mark.parametrize("key", NEW_KEYS)
    def test_studio_template_detail(self, sess, key):
        r = sess.get(f"{API}/public/templates/{key}", timeout=20)
        assert r.status_code == 200, f"{key} -> {r.status_code}"
        d = r.json()
        assert len(d["pages"]) == 4, f"{key} expected 4 pages got {len(d['pages'])}"
        assert d["theme"].get("site_skin") == "studio", f"{key} site_skin={d['theme'].get('site_skin')}"
        # each page has blocks
        for p in d["pages"]:
            assert len(p["blocks"]) > 0, f"{key} page {p['slug']} empty"

    def test_classic_template_detail_not_studio(self, sess):
        r = sess.get(f"{API}/public/templates/hospitality", timeout=15)
        assert r.status_code == 200
        assert r.json()["theme"].get("site_skin") == "classic"


# ---------- PUT /me/ui-skin ----------
class TestUiSkin:
    def test_set_studio(self, sess):
        r = sess.put(f"{API}/me/ui-skin", json={"skin": "studio"}, timeout=10)
        assert r.status_code == 200
        assert r.json() == {"skin": "studio"}

    def test_set_classic(self, sess):
        r = sess.put(f"{API}/me/ui-skin", json={"skin": "classic"}, timeout=10)
        assert r.status_code == 200
        assert r.json() == {"skin": "classic"}

    def test_invalid_normalises_to_classic(self, sess):
        r = sess.put(f"{API}/me/ui-skin", json={"skin": "purple"}, timeout=10)
        assert r.status_code == 200
        assert r.json()["skin"] == "classic"

    def test_persists_on_user(self, sess):
        sess.put(f"{API}/me/ui-skin", json={"skin": "studio"}, timeout=10)
        r = sess.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json().get("ui_skin") == "studio"
        # reset
        sess.put(f"{API}/me/ui-skin", json={"skin": "classic"}, timeout=10)


# ---------- Tenant creation from new + original templates ----------
class TestTenantFromStudioTemplate:
    def test_create_from_new_template_applies_studio(self, sess, created_apps):
        payload = {"name": "TEST_iter64_vet", "industry": "Veterinary",
                   "description": "test", "template_key": "veterinary",
                   "status": "draft", "tags": [], "color": "#4F46E5",
                   "thumbnail": "", "video_url": "", "live_url": "", "kind": "website"}
        r = sess.post(f"{API}/apps", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:400]
        app = r.json()
        aid = app["app_id"]
        created_apps.append(aid)
        assert app["theme"].get("site_skin") == "studio", f"site_skin={app['theme'].get('site_skin')}"
        # verify 4 pages built
        pr = sess.get(f"{API}/apps/{aid}/pages", timeout=15)
        assert pr.status_code == 200
        pages = pr.json() if isinstance(pr.json(), list) else pr.json().get("pages", [])
        assert len(pages) >= 4, f"expected >=4 pages, got {len(pages)}"

    def test_create_from_original_template_stays_classic(self, sess, created_apps):
        payload = {"name": "TEST_iter64_hosp", "industry": "Hospitality",
                   "description": "test", "template_key": "hospitality",
                   "status": "draft", "tags": [], "color": "#4F46E5",
                   "thumbnail": "", "video_url": "", "live_url": "", "kind": "website"}
        r = sess.post(f"{API}/apps", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:400]
        app = r.json()
        created_apps.append(app["app_id"])
        assert app["theme"].get("site_skin") == "classic"


# ---------- Per-tenant site skin toggle (theme update) ----------
class TestTenantSkinToggle:
    def test_toggle_original_tenant_to_studio(self, sess, created_apps):
        # Reuse the hospitality tenant created above if present, else create
        if len(created_apps) < 2:
            payload = {"name": "TEST_iter64_toggle", "industry": "Hospitality",
                       "description": "t", "template_key": "hospitality", "status": "draft",
                       "tags": [], "color": "#4F46E5", "thumbnail": "", "video_url": "",
                       "live_url": "", "kind": "website"}
            r = sess.post(f"{API}/apps", json=payload, timeout=30)
            created_apps.append(r.json()["app_id"])
        aid = created_apps[-1]
        # get current theme via studio endpoint
        g = sess.get(f"{API}/apps/{aid}/theme", timeout=10)
        assert g.status_code == 200
        theme = g.json()
        theme["site_skin"] = "studio"
        u = sess.put(f"{API}/apps/{aid}/theme", json={"theme": theme}, timeout=15)
        assert u.status_code == 200, u.text[:300]
        after = sess.get(f"{API}/apps/{aid}/theme", timeout=10).json()
        assert after.get("site_skin") == "studio", (
            f"BUG: PUT /apps/{{id}}/theme drops site_skin. Got theme keys: {list(after.keys())}. "
            f"_clean_theme filters unknown keys; site_skin must be added to DEFAULT_THEME."
        )

        # switch back
        theme["site_skin"] = "classic"
        sess.put(f"{API}/apps/{aid}/theme", json={"theme": theme}, timeout=15)
        back = sess.get(f"{API}/apps/{aid}", timeout=10).json()
        assert back["theme"].get("site_skin") == "classic"
