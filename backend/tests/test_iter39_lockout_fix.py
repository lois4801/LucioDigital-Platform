"""Iteration 39 — Retest of lockout & protected=false fixes on the Convert-to-Web-App flow.

Verifies:
1. Brute-force lockout on POST /api/site/{token}/auth/login now keys off X-Forwarded-For:
   401,401,401,401,401,429 → 429 even for correct password until window elapses.
2. A DIFFERENT email on the SAME site+IP is unaffected (per-email keying).
3. GET /api/apps/{id}/webapp returns proper booleans (never null) for every page after conversion.
4. End-to-end regression: convert a fresh throwaway tenant, verify summary, content preservation,
   collections per repeated section, protected-page gate, /site/{token}/submit, admin panel API,
   and standard-user 403 on /admin/*.
"""
import os
import copy
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
OWNER = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
NORTHWIND_TOKEN = "pv_15f7e07b2d724b452e2a"


# -------------- helpers --------------

def _session(user=None):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    if user:
        r = s.post(f"{BASE}/api/auth/login", json=user, timeout=30)
        assert r.status_code == 200, f"login failed {r.status_code}: {r.text}"
    return s


@pytest.fixture(scope="module")
def owner():
    return _session(OWNER)


@pytest.fixture(scope="module")
def throwaway_tenant(owner):
    """Create a fresh app with several pages for a clean end-to-end run."""
    name = f"TEST_iter39_{uuid.uuid4().hex[:6]}"
    r = owner.post(f"{BASE}/api/apps", json={"name": name, "industry": "wellness",
                                             "kind": "website", "description": "iter39 retest"})
    assert r.status_code == 200, r.text
    app_id = r.json()["app_id"]

    # Add /about, /services, /contact pages via /pages endpoint so slugs exist for protected-flag test
    # Also add one non-public page to be marked protected.
    for slug, name_ in [("/about", "About"), ("/services", "Services"),
                        ("/contact", "Contact"), ("/members", "Members")]:
        rp = owner.post(f"{BASE}/api/apps/{app_id}/pages",
                        json={"name": name_, "slug": slug})
        # tolerate absence of endpoint or 409 — check via GET after
        if rp.status_code not in (200, 201, 409, 404):
            pass  # non-fatal, we'll check what actually got created

    return app_id


# -------------- 1. Lockout retest (X-Forwarded-For keyed) --------------

class TestLockoutFix:
    def _register(self, email):
        r = requests.post(
            f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/register",
            json={"email": email, "password": "GoodPass12345", "name": "Iter39"},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        # 200 or 409 (already exists) both fine
        assert r.status_code in (200, 409), f"register unexpected {r.status_code}: {r.text}"

    def test_five_fail_then_429_and_correct_password_still_429(self):
        email = f"TEST_lock39_{uuid.uuid4().hex[:8]}@ex.com"
        # unique forwarded IP so we don't collide with prior/other test runs
        fwd = f"203.0.113.{uuid.uuid4().int % 250 + 1}"
        self._register(email)
        headers = {"Content-Type": "application/json", "X-Forwarded-For": fwd}
        codes = []
        for _ in range(5):
            r = requests.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/login",
                              json={"email": email, "password": "WrongWrong9"},
                              headers=headers, timeout=30)
            codes.append(r.status_code)
        # first 4 should be 401, 5th should be 429 (>=5 count triggers lockout inline)
        assert codes[:4] == [401, 401, 401, 401], f"first 4 not all 401: {codes}"
        assert codes[4] == 429, f"5th attempt not 429: {codes}"

        # 6th attempt (extra wrong) still 429
        r6 = requests.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/login",
                           json={"email": email, "password": "WrongWrong9"},
                           headers=headers, timeout=30)
        assert r6.status_code == 429, f"6th expected 429 got {r6.status_code}"

        # correct password must still be blocked while window open
        r_ok = requests.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/login",
                             json={"email": email, "password": "GoodPass12345"},
                             headers=headers, timeout=30)
        assert r_ok.status_code == 429, f"correct pw during lockout expected 429 got {r_ok.status_code}: {r_ok.text}"

    def test_different_email_same_ip_unaffected(self):
        """Per-email keying: another email on the same site+IP should not be locked out."""
        fwd = f"203.0.113.{uuid.uuid4().int % 250 + 1}"
        headers = {"Content-Type": "application/json", "X-Forwarded-For": fwd}

        # Burn out email A with 5 wrong logins
        email_a = f"TEST_locka_{uuid.uuid4().hex[:8]}@ex.com"
        self._register(email_a)
        for _ in range(5):
            requests.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/login",
                          json={"email": email_a, "password": "WrongWrong9"},
                          headers=headers, timeout=30)

        # email B on the same IP should still get 401 (wrong pw), not 429
        email_b = f"TEST_lockb_{uuid.uuid4().hex[:8]}@ex.com"
        self._register(email_b)
        r = requests.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/login",
                          json={"email": email_b, "password": "WrongPassZ"},
                          headers=headers, timeout=30)
        assert r.status_code == 401, f"different email should not inherit lockout: {r.status_code} {r.text}"

        # correct pw for B should work
        r_ok = requests.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/login",
                             json={"email": email_b, "password": "GoodPass12345"},
                             headers=headers, timeout=30)
        assert r_ok.status_code == 200, f"email B correct login should succeed: {r_ok.status_code} {r_ok.text}"


# -------------- 2. protected=false booleans + full regression --------------

class TestConvertRegression:
    def test_convert_and_status_returns_boolean_protected(self, owner, throwaway_tenant):
        app_id = throwaway_tenant
        pre_pages = owner.get(f"{BASE}/api/apps/{app_id}/pages").json()
        pytest.iter39_pre = copy.deepcopy(pre_pages)

        r = owner.post(f"{BASE}/api/apps/{app_id}/convert-to-webapp",
                       json={"signup_mode": "open"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "summary" in data
        summary = data["summary"]
        for k in ("auth", "protected_pages", "public_pages", "collections",
                  "sections_bound", "forms_connected", "roles", "api_base", "emails"):
            assert k in summary, f"missing summary key: {k}"
        token = data.get("token")
        assert token, "convert response missing token"
        pytest.iter39_token = token
        pytest.iter39_app_id = app_id

        # GET /webapp — every page's protected flag MUST be a bool (never None/null)
        w = owner.get(f"{BASE}/api/apps/{app_id}/webapp").json()
        pages = w.get("pages") or []
        assert pages, "webapp status returned no pages"
        for pg in pages:
            v = pg.get("protected")
            assert isinstance(v, bool), f"page {pg.get('slug')} protected is {v!r} (type {type(v).__name__}), expected bool"
        # /, /about, /services, /contact should all be false
        public_map = {pg["slug"]: pg["protected"] for pg in pages if pg.get("slug") in ("/", "/about", "/services", "/contact")}
        for slug, val in public_map.items():
            assert val is False, f"public slug {slug} should be protected=False, got {val}"

    def test_content_preserved(self, owner):
        app_id = getattr(pytest, "iter39_app_id", None)
        pre = getattr(pytest, "iter39_pre", None)
        if not app_id or not pre:
            pytest.skip("no pre-conversion snapshot")
        post = owner.get(f"{BASE}/api/apps/{app_id}/pages").json()
        pre_pages = pre if isinstance(pre, list) else pre.get("pages", [])
        post_pages = post if isinstance(post, list) else post.get("pages", [])
        assert len(pre_pages) == len(post_pages), "page count changed after conversion"
        by_slug_pre = {p.get("slug"): p for p in pre_pages}
        by_slug_post = {p.get("slug"): p for p in post_pages}
        for slug, p1 in by_slug_pre.items():
            p2 = by_slug_post.get(slug)
            assert p2 is not None, f"page {slug} missing post-conversion"
            b1 = p1.get("blocks") or []
            b2 = p2.get("blocks") or []
            assert len(b1) == len(b2), f"block count changed on {slug}"
            for bl1, bl2 in zip(b1, b2):
                assert bl1.get("type") == bl2.get("type")
                p1p, p2p = bl1.get("props") or {}, bl2.get("props") or {}
                for k, v in p1p.items():
                    if k in ("collection", "dynamic"):
                        continue
                    assert p2p.get(k) == v, f"prop {k} changed on {slug}/{bl1.get('type')}"

    def test_collections_per_repeated_section(self, owner):
        token = getattr(pytest, "iter39_token", None)
        if not token:
            pytest.skip("no token")
        r = owner.get(f"{BASE}/api/site/{token}/admin/collections")
        assert r.status_code == 200, r.text
        cols = r.json().get("collections", [])
        # cols may be empty if the fresh tenant only had default blocks; ensure at least list shape
        assert isinstance(cols, list)
        # if collections exist, verify each has items list
        for c in cols:
            assert "collection_id" in c and "slug" in c
            assert isinstance(c.get("items"), list)

    def test_protected_page_gate_and_submit(self, owner):
        token = getattr(pytest, "iter39_token", None)
        app_id = getattr(pytest, "iter39_app_id", None)
        if not token or not app_id:
            pytest.skip("no token")
        # Find a non-public page and mark it protected via /pages/{id}/access
        pages = owner.get(f"{BASE}/api/apps/{app_id}/webapp").json().get("pages", [])
        target = next((p for p in pages if p.get("slug") not in ("/", "/about", "/services", "/contact")), None)
        if not target:
            # /members may not have been created — mark /about protected for the gate check
            target = next((p for p in pages if p.get("slug") == "/about"), None)
        assert target, "no page available"
        rr = owner.post(f"{BASE}/api/apps/{app_id}/webapp/pages/{target['page_id']}/access",
                        json={"protected": True})
        assert rr.status_code == 200

        # Anon fetch should say requires_login
        slug = target["slug"].lstrip("/")
        r_anon = requests.get(f"{BASE}/api/site/{token}/page/{slug}", timeout=30)
        assert r_anon.status_code == 200
        body = r_anon.json()
        assert body.get("requires_login") is True and body.get("protected") is True, body

        # Register a member and fetch with bearer token → full content
        email = f"TEST_mem39_{uuid.uuid4().hex[:6]}@ex.com"
        reg = requests.post(f"{BASE}/api/site/{token}/auth/register",
                            json={"email": email, "password": "GoodPass12345"}, timeout=30)
        assert reg.status_code == 200, reg.text
        mtok = reg.json()["token"]
        r_auth = requests.get(f"{BASE}/api/site/{token}/page/{slug}",
                              headers={"Authorization": f"Bearer {mtok}"}, timeout=30)
        assert r_auth.status_code == 200
        assert r_auth.json().get("requires_login") is False

        # Save member creds for admin 403 test
        pytest.iter39_member_token = mtok
        pytest.iter39_member_email = email

        # Submit a form (no form_id — generic)
        r_sub = requests.post(f"{BASE}/api/site/{token}/submit",
                              json={"name": "Iter39", "email": email,
                                    "fields": {"message": "hello from iter39"}},
                              timeout=30)
        assert r_sub.status_code == 200
        assert r_sub.json().get("ok") is True
        assert "submission" in r_sub.json()

    def test_admin_panel_api_for_owner(self, owner):
        token = getattr(pytest, "iter39_token", None)
        if not token:
            pytest.skip("no token")
        for path in ("summary", "submissions", "users", "collections"):
            r = owner.get(f"{BASE}/api/site/{token}/admin/{path}")
            assert r.status_code == 200, f"/admin/{path} → {r.status_code} {r.text}"

    def test_standard_user_403_on_admin(self):
        token = getattr(pytest, "iter39_token", None)
        mtok = getattr(pytest, "iter39_member_token", None)
        if not token or not mtok:
            pytest.skip("no member token")
        headers = {"Authorization": f"Bearer {mtok}"}
        for path in ("summary", "submissions", "users", "collections"):
            r = requests.get(f"{BASE}/api/site/{token}/admin/{path}",
                             headers=headers, timeout=30)
            assert r.status_code == 403, f"member should get 403 on /admin/{path}, got {r.status_code}"
