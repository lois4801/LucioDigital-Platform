"""Iteration 88 — Retest of iter87 + new: colour validation on PUT /reviews and photo-pool widening."""
import os
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
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, r.text
    yield s
    # teardown — restore tenant to template defaults
    s.post(f"{API}/apps/{APP_ID}/reviews/reset", timeout=20)


# ----- Colour validation on PUT /api/apps/{id}/reviews -----

class TestColourValidation:
    @pytest.mark.parametrize("field", ["accent", "card_bg", "title_color"])
    def test_invalid_colour_rejected(self, client, field):
        payload = {"style": {field: "not-a-colour"}}
        r = client.put(f"{API}/apps/{APP_ID}/reviews", json=payload, timeout=20)
        assert r.status_code == 400, f"{field}: got {r.status_code}: {r.text[:200]}"
        assert field in r.text and ("hex" in r.text.lower() or "rgb" in r.text.lower())

    @pytest.mark.parametrize("colour", ["#FF7A00", "#fff", "#112233aa",
                                        "rgb(10, 20, 30)", "rgba(255, 0, 0, 0.5)"])
    def test_valid_colours_accepted(self, client, colour):
        payload = {"style": {"accent": colour, "card_bg": colour, "title_color": colour}}
        r = client.put(f"{API}/apps/{APP_ID}/reviews", json=payload, timeout=20)
        assert r.status_code == 200, f"{colour}: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert data["style"]["accent"] == colour
        assert data["style"]["card_bg"] == colour
        assert data["style"]["title_color"] == colour

    def test_title_and_subtitle_are_free_text(self, client):
        payload = {"style": {"title": "Any Free Text 🌟!!", "subtitle": "sub-line #not#a#colour"}}
        r = client.put(f"{API}/apps/{APP_ID}/reviews", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["style"]["title"] == "Any Free Text 🌟!!"
        assert data["style"]["subtitle"] == "sub-line #not#a#colour"

    def test_reset_clears_colour_overrides(self, client):
        client.put(f"{API}/apps/{APP_ID}/reviews",
                   json={"style": {"accent": "#FF7A00", "card_bg": "#000000", "title_color": "#FFFFFF"}},
                   timeout=20)
        r = client.post(f"{API}/apps/{APP_ID}/reviews/reset", timeout=20)
        assert r.status_code == 200
        st = r.json()["style"]
        assert st.get("accent") in ("", None)
        assert st.get("card_bg") in ("", None)
        assert st.get("title_color") in ("", None)


# ----- Photo pool widening (17 -> 25) -----

class TestPhotoPool:
    def test_saas_template_has_at_least_8_unique_photos(self):
        r = requests.get(f"{API}/public/reviews/saas", timeout=20)
        assert r.status_code == 200
        reviews = r.json()["reviews"]
        assert len(reviews) == 20
        photos = {(rv.get("photo") or "").split("?")[0] for rv in reviews}
        assert len(photos) >= 8, f"only {len(photos)} unique photo urls (expected >= 8)"

    def test_every_photo_url_loads_200(self):
        r = requests.get(f"{API}/public/reviews/saas", timeout=20)
        urls = {rv["photo"] for rv in r.json()["reviews"]}
        for u in urls:
            hr = requests.head(u, timeout=20, allow_redirects=True)
            # Unsplash sometimes 405s HEAD → fallback to GET
            if hr.status_code >= 400:
                hr = requests.get(u, timeout=20, stream=True)
            assert hr.status_code == 200, f"{u} -> {hr.status_code}"

    def test_multiple_templates_use_photos_from_widened_pool(self):
        # Aggregate photo urls across a handful of templates and assert we see >17 distinct
        seen = set()
        for key in ["saas", "hvac", "healthcare", "finance", "creative_studio", "retail",
                    "fitness", "hospitality", "legal", "education"]:
            r = requests.get(f"{API}/public/reviews/{key}", timeout=20)
            for rv in r.json()["reviews"]:
                seen.add((rv.get("photo") or "").split("?")[0])
        assert len(seen) >= 20, f"pool coverage looks narrow: {len(seen)} distinct urls"
