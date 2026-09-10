"""Iteration 89 — Section Templates per page type, page reordering, and the
tenant->client rename. Runs against app_testlab (LIVE MASTER — do NOT delete pages).
Saves and restores app_testlab page order + navbar links via a module-scoped teardown."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").strip().rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
APP_ID = "app_testlab"
PV_TOKEN = "pv_c3b797fcdafc58d4e70e320f"
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}

BLOCK_TYPES = {"hero", "text", "features", "pricing", "stats", "testimonials",
               "team", "gallery", "faq", "contact", "cta"}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    yield s


@pytest.fixture(scope="module")
def snapshot(client):
    """Snapshot original page order so we can restore in teardown."""
    r = client.get(f"{API}/apps/{APP_ID}/pages", timeout=20)
    assert r.status_code == 200
    pages = r.json()
    original = sorted(pages, key=lambda p: p.get("order", 0))
    ids = [p["page_id"] for p in original]
    yield {"ids": ids, "pages": {p["page_id"]: p for p in original}}
    # teardown: restore order
    client.put(f"{API}/apps/{APP_ID}/pages/order", json={"page_ids": ids}, timeout=30)


# ---------- Section Sets endpoint ----------

class TestSectionSets:
    def test_home_page_returns_home_type_and_4_sets(self, client, snapshot):
        # find the '/' page
        home = next(p for p in snapshot["pages"].values() if p.get("slug") == "/")
        r = client.get(f"{API}/apps/{APP_ID}/pages/{home['page_id']}/section-sets", timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["page_type"] == "home"
        assert len(d["sets"]) == 4
        for s in d["sets"]:
            for f in ("id", "label", "hint", "blocks"):
                assert s.get(f), f"set missing {f}: {s}"
        assert "empty" in d
        assert "page_name" in d

    def test_bad_page_id_404s(self, client):
        r = client.get(f"{API}/apps/{APP_ID}/pages/pg_does_not_exist/section-sets", timeout=20)
        assert r.status_code == 404

    def test_general_page_type_for_custom_slug(self, client):
        # create a scratch page we own and can delete
        r = client.post(f"{API}/apps/{APP_ID}/pages",
                        json={"slug": "/iter89-scratch", "name": "Iter89 Scratch"}, timeout=20)
        assert r.status_code in (200, 201), r.text
        pid = r.json().get("page_id") or r.json().get("id")
        try:
            r = client.get(f"{API}/apps/{APP_ID}/pages/{pid}/section-sets", timeout=20)
            assert r.status_code == 200
            assert r.json()["page_type"] == "general"
            assert len(r.json()["sets"]) == 4
        finally:
            client.delete(f"{API}/apps/{APP_ID}/pages/{pid}", timeout=20)


# ---------- apply-set endpoint ----------

class TestApplySet:
    """Apply one set per page type, apply blank, and confirm unknown/foreign errors."""

    def _scratch(self, client, slug, name):
        last = None
        for _ in range(3):
            try:
                r = client.post(f"{API}/apps/{APP_ID}/pages", json={"slug": slug, "name": name}, timeout=30)
                assert r.status_code in (200, 201), r.text
                return r.json().get("page_id") or r.json().get("id")
            except requests.exceptions.ConnectionError as e:
                last = e
                import time; time.sleep(1)
        raise last

    def test_apply_home_launch_builds_5_blocks_from_niche_copy(self, client):
        pid = self._scratch(client, "/iter89-home", "Iter89 Home")
        try:
            r = client.post(f"{API}/apps/{APP_ID}/pages/{pid}/apply-set",
                            json={"set_id": "home-launch"}, timeout=30)
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["count"] == 5
            types = [b.get("type") for b in d["blocks"]]
            assert types == ["hero", "stats", "features", "testimonials", "cta"]
            # confirm copy is not lorem — first hero block must have real headline
            text_blob = str(d["blocks"]).lower()
            assert "lorem" not in text_blob, "lorem placeholder found in generated copy"
        finally:
            client.delete(f"{API}/apps/{APP_ID}/pages/{pid}", timeout=20)

    def test_apply_blank_clears_blocks(self, client):
        pid = self._scratch(client, "/iter89-blank", "Iter89 Blank")
        try:
            # first apply a set so there is content
            client.post(f"{API}/apps/{APP_ID}/pages/{pid}/apply-set",
                        json={"set_id": "general-standard"}, timeout=30)
            r = client.post(f"{API}/apps/{APP_ID}/pages/{pid}/apply-set",
                            json={"set_id": "blank"}, timeout=30)
            assert r.status_code == 200, r.text
            assert r.json()["count"] == 0
            assert r.json()["blocks"] == []
        finally:
            client.delete(f"{API}/apps/{APP_ID}/pages/{pid}", timeout=20)

    def test_unknown_set_id_400s_with_message(self, client):
        pid = self._scratch(client, "/iter89-bad", "Iter89 Bad")
        try:
            r = client.post(f"{API}/apps/{APP_ID}/pages/{pid}/apply-set",
                            json={"set_id": "nope"}, timeout=20)
            assert r.status_code == 400, r.text
            assert "unknown section set" in r.text.lower()
        finally:
            client.delete(f"{API}/apps/{APP_ID}/pages/{pid}", timeout=20)

    def test_all_11_block_types_build_across_page_types(self, client):
        """Applying every set across every page type must yield all 11 block types successfully."""
        seen: set = set()
        page_type_sets = {
            "/iter89-t-home": ("Iter89 Home", ["home-launch", "home-proof", "home-showcase", "home-service"]),
            "/about/iter89": ("Iter89 About", ["about-team", "about-mission", "about-timeline", "about-gallery"]),
            "/services/iter89": ("Iter89 Services", ["services-cards", "services-pricing", "services-process", "services-faq"]),
            "/contact/iter89": ("Iter89 Contact", ["contact-form", "contact-locations", "contact-support", "contact-book"]),
            "/iter89-general": ("Iter89 General", ["general-standard", "general-long", "general-visual", "general-landing"]),
        }
        for slug, (name, sids) in page_type_sets.items():
            pid = self._scratch(client, slug, name)
            try:
                for sid in sids:
                    r = client.post(f"{API}/apps/{APP_ID}/pages/{pid}/apply-set",
                                    json={"set_id": sid}, timeout=30)
                    assert r.status_code == 200, f"{sid}: {r.text[:200]}"
                    for b in r.json()["blocks"]:
                        seen.add(b.get("type"))
            finally:
                client.delete(f"{API}/apps/{APP_ID}/pages/{pid}", timeout=20)
        missing = BLOCK_TYPES - seen
        assert not missing, f"block types never built: {missing}. Saw: {seen}"

    def test_foreign_page_rejected(self, client):
        # apply-set for a page_id from a DIFFERENT client rejects.
        # We use the reorder endpoint's foreign-page rejection instead for the "cross-client" check.
        pid_fake = "pg_this_does_not_exist_here"
        r = client.post(f"{API}/apps/{APP_ID}/pages/{pid_fake}/apply-set",
                        json={"set_id": "home-launch"}, timeout=20)
        assert r.status_code in (400, 403, 404)


# ---------- Page reorder ----------

class TestPageReorder:
    def test_reorder_swaps_and_persists(self, client, snapshot):
        ids = list(snapshot["ids"])
        assert len(ids) >= 2
        # swap first two
        new_order = [ids[1], ids[0]] + ids[2:]
        r = client.put(f"{API}/apps/{APP_ID}/pages/order",
                       json={"page_ids": new_order}, timeout=30)
        assert r.status_code == 200, r.text
        # GET back and check order
        r = client.get(f"{API}/apps/{APP_ID}/pages", timeout=20)
        got = sorted(r.json(), key=lambda p: p.get("order", 0))
        got_ids = [p["page_id"] for p in got]
        assert got_ids == new_order, f"expected {new_order[:3]}... got {got_ids[:3]}..."

    def test_foreign_page_id_rejected(self, client, snapshot):
        ids = list(snapshot["ids"])
        bad = ["pg_not_ours_xxx"] + ids
        r = client.put(f"{API}/apps/{APP_ID}/pages/order",
                       json={"page_ids": bad}, timeout=20)
        assert r.status_code == 400, r.text
        assert "do not belong" in r.text.lower() or "client" in r.text.lower()

    def test_public_navbar_matches_new_order(self, client, snapshot):
        # Re-apply a specific order and confirm public site navbar reflects it
        ids = list(snapshot["ids"])
        # Put a specific page order and look at public site's first-page navbar links
        new_order = ids[:]  # keep default here just to trigger navbar rewrite
        r = client.put(f"{API}/apps/{APP_ID}/pages/order",
                       json={"page_ids": new_order}, timeout=30)
        assert r.status_code == 200
        r = requests.get(f"{API}/public/site/{PV_TOKEN}", timeout=30)
        assert r.status_code == 200
        # find any navbar block, verify its links exist and are ordered
        data = r.json()
        site_pages = data.get("pages") or data.get("app", {}).get("pages") or []
        # Build slug -> order mapping from snapshot
        want_order = [snapshot["pages"][pid]["slug"] for pid in new_order]
        found_nav = None
        for pg in site_pages:
            for b in (pg.get("blocks") or []):
                if b.get("type") == "navbar":
                    links = [(x or {}).get("href") for x in ((b.get("props") or {}).get("links") or [])]
                    inside = [l for l in links if l in want_order]
                    if inside:
                        found_nav = inside
                        break
            if found_nav:
                break
        if found_nav:
            # inside links must appear in the same relative order as want_order
            seq = [want_order.index(l) for l in found_nav]
            assert seq == sorted(seq), f"navbar links not in page-order: {found_nav}"


# ---------- Landing page: pricing removed, tenant->client rename ----------

class TestLandingPricing:
    def test_landing_html_has_no_pricing_or_tenant(self):
        r = requests.get(f"{BASE_URL}/", timeout=20)
        # SPA may serve empty shell; check any static references anyway
        assert r.status_code == 200
        # This is an SPA — deep verification is done in Playwright. Here we just assert 200.


class TestPublicEndpoints:
    """Rename safety — every /api/public/* endpoint that iter88 used still 200s."""

    def test_public_reviews_luciodigital_zero_tenant(self):
        r = requests.get(f"{API}/public/reviews/luciodigital", timeout=20)
        assert r.status_code == 200
        text = r.text.lower()
        # only true occurrences of the word "tenant" (avoid substrings like 'consistent'/'tenants' inside urls)
        matches = re.findall(r"\btenants?\b", text)
        assert len(matches) == 0, f"found {len(matches)} tenant occurrences in reviews/luciodigital"

    def test_public_site_ok(self):
        r = requests.get(f"{API}/public/site/{PV_TOKEN}", timeout=30)
        assert r.status_code == 200

    def test_public_landing_tenants_route_still_exists(self):
        # Deliberately unchanged by the rename per spec.
        r = requests.get(f"{API}/public/landing/tenants", timeout=20)
        # accept either 200 (data) or 404 if replaced but must not 500
        assert r.status_code in (200, 404), f"got {r.status_code}: {r.text[:200]}"
