"""Iteration 87 — Reviews & testimonials.
Tests: public template sets (34 keys, 20 reviews each, uniqueness across templates),
tenant get/put/reset, list-length cap, admin generate + status endpoints, non-member 403/404."""
import os
import pytest
import requests


def _load_url():
    v = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if v:
        return v.rstrip("/")
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    return ""


BASE_URL = _load_url()
API = f"{BASE_URL}/api"
APP_ID = "app_testlab"
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}

TEMPLATE_KEYS = [
    "hvac", "healthcare", "construction", "fitness", "retail", "hospitality",
    "finance", "it_services", "creative_studio", "logistics", "saas", "legal",
    "education", "real_estate", "restaurant", "events", "veterinary", "dental",
    "accounting", "landscaping", "photography", "automotive", "beauty", "insurance",
    "pet_grooming", "hvac_plumbing", "coworking", "wellness", "cleaning",
    "music_school", "nonprofit", "architecture", "test_template", "luciodigital",
]


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    yield s


# ---------- Public template sets ----------

class TestPublicReviews:
    def test_all_34_keys_have_20_ai_reviews(self):
        for key in TEMPLATE_KEYS:
            r = requests.get(f"{API}/public/reviews/{key}", timeout=20)
            assert r.status_code == 200, f"{key}: {r.status_code}"
            data = r.json()
            reviews = data.get("reviews") or []
            assert len(reviews) == 20, f"{key}: got {len(reviews)} reviews"
            assert data.get("source") == "ai", f"{key}: source={data.get('source')}"
            for i, rv in enumerate(reviews):
                for f in ("name", "title", "company", "company_desc", "quote", "photo", "city", "country", "flag"):
                    assert rv.get(f), f"{key}[{i}] missing {f}"
                assert len(rv.get("tags") or []) == 2, f"{key}[{i}] tags={rv.get('tags')}"
                assert rv.get("rating") == 5
                assert len(rv["flag"]) == 2 and rv["flag"].islower(), f"{key}[{i}] flag={rv['flag']}"

    def test_no_two_templates_share_review_content(self):
        # Consumer-business shared labels like "Homeowner"/"Parent of two" are allowed by prompt.
        GENERIC_COMPANY = {"homeowner", "parent of two", "parent of three", "parent of four",
                           "parent of one", "parent", "customer", "client", "resident",
                           "member", "patient", "student", "pet owner", "owner", "guest",
                           "tenant", "diner", "shopper", "visitor", "freelancer",
                           "self-employed", "retiree", "small business owner", "solo founder",
                           "solopreneur", "cat rescue volunteer", "volunteer",
                           "dog rescue volunteer", "animal rescue volunteer"}
        # also treat any 'parent of X' / '... volunteer' as generic
        def _is_generic(c: str) -> bool:
            return (c in GENERIC_COMPANY or c.startswith("parent of ")
                    or c.endswith(" volunteer") or c == "volunteer")
        seen_quotes: dict = {}
        seen_names: dict = {}
        seen_companies: dict = {}
        quote_col, name_col, company_col = [], [], []
        s = requests.Session()
        for key in TEMPLATE_KEYS:
            data = None
            for attempt in range(3):
                try:
                    r = s.get(f"{API}/public/reviews/{key}", timeout=40)
                    data = r.json()
                    break
                except Exception:
                    if attempt == 2:
                        raise
            for rv in data.get("reviews", []):
                q = (rv.get("quote") or "").strip().lower()
                n = (rv.get("name") or "").strip().lower()
                c = (rv.get("company") or "").strip().lower()
                if q and q in seen_quotes and seen_quotes[q] != key:
                    quote_col.append((q[:60], seen_quotes[q], key))
                if n and n in seen_names and seen_names[n] != key:
                    name_col.append((n, seen_names[n], key))
                if c and not _is_generic(c) and c in seen_companies and seen_companies[c] != key:
                    company_col.append((c, seen_companies[c], key))
                seen_quotes.setdefault(q, key)
                seen_names.setdefault(n, key)
                seen_companies.setdefault(c, key)
        # Quotes MUST be unique cross-template (highest priority).
        assert not quote_col, f"cross-template QUOTE collisions ({len(quote_col)}): {quote_col[:5]}"
        # Names and non-generic companies should also be unique — report but don't hard-fail if minor.
        assert not name_col, f"cross-template NAME collisions ({len(name_col)}): {name_col[:8]}"
        assert not company_col, f"cross-template COMPANY collisions ({len(company_col)}): {company_col[:8]}"


# ---------- Tenant reviews ----------

class TestTenantReviews:
    def test_get_returns_template_set_by_default(self, client):
        client.post(f"{API}/apps/{APP_ID}/reviews/reset", timeout=20)
        r = client.get(f"{API}/apps/{APP_ID}/reviews", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data["reviews"]) == 20
        assert data["template_key"] == "saas"
        assert "style" in data and "accent" in data["style"]

    def test_put_saves_edits_and_returns_custom_source(self, client):
        r = client.get(f"{API}/apps/{APP_ID}/reviews", timeout=20)
        rv = r.json()["reviews"]
        # Edit first review's quote
        rv[0]["quote"] = "TEST_ITER87 custom quote just for testing."
        rv[0]["name"] = "TEST_ITER87 Reviewer"
        payload = {"reviews": rv, "style": {"accent": "#ff00aa", "title": "Custom Title", "subtitle": "Custom sub"}}
        r = client.put(f"{API}/apps/{APP_ID}/reviews", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["source"] == "custom"
        assert data["reviews"][0]["quote"].startswith("TEST_ITER87")
        assert data["style"]["accent"] == "#ff00aa"
        assert data["style"]["title"] == "Custom Title"
        # verify persistence
        r2 = client.get(f"{API}/apps/{APP_ID}/reviews", timeout=20)
        assert r2.json()["reviews"][0]["quote"].startswith("TEST_ITER87")

    def test_put_rejects_more_than_60(self, client):
        big = [{"name": f"N{i}", "quote": "q", "company": "c", "tags": ["a", "b"]} for i in range(61)]
        r = client.put(f"{API}/apps/{APP_ID}/reviews", json={"reviews": big}, timeout=20)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"

    def test_reset_restores_template_set(self, client):
        r = client.post(f"{API}/apps/{APP_ID}/reviews/reset", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["source"] == "ai"
        assert not data["reviews"][0]["quote"].startswith("TEST_ITER87")
        # style should be defaults (empty accent)
        assert data["style"].get("accent") in ("", None)

    def test_non_member_gets_403_or_404(self):
        # Unauthenticated session
        s = requests.Session()
        r1 = s.get(f"{API}/apps/{APP_ID}/reviews", timeout=20)
        r2 = s.put(f"{API}/apps/{APP_ID}/reviews", json={"reviews": []}, timeout=20)
        r3 = s.post(f"{API}/apps/{APP_ID}/reviews/reset", timeout=20)
        for r in (r1, r2, r3):
            assert r.status_code in (401, 403, 404), f"got {r.status_code}"


# ---------- Admin endpoints ----------

class TestAdminReviews:
    def test_status_reports_34_generated_zero_missing(self, client):
        r = client.get(f"{API}/admin/reviews/status", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 34
        assert len(data["missing"]) == 0, f"missing: {data['missing']}"
        assert len(data["generated"]) == 34
        for k, count in data["generated"].items():
            assert count == 20, f"{k}: count={count}"

    def test_generate_unknown_key_400s(self, client):
        r = client.post(f"{API}/admin/reviews/generate/not_a_real_key", timeout=20)
        assert r.status_code == 400, f"got {r.status_code}: {r.text[:200]}"
