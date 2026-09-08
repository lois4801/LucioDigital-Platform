"""Iteration 38 — Convert to Web App: conversion + tenant auth + admin panel + member gate.

Covers content-preservation, repeated section collections, tenant visitor auth (register/login/
forgot/reset), signup modes, protected pages, form submissions, admin panel API, analytics,
and cross-tenant token isolation.
"""
import os
import io
import json
import time
import copy
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")

OWNER = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
EDITOR = {"email": "client.editor@example.com", "password": "ClientEdit2026!"}

NORTHWIND_APP = "app_6663b5de0007"
NORTHWIND_TOKEN = "pv_15f7e07b2d724b452e2a"
DESIGNV2_APP = "app_c18671970769"
AURA_APP = "app_abc693a75574"


def _s(user=None):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    if user:
        r = s.post(f"{BASE}/api/auth/login", json=user, timeout=30)
        assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def owner():
    return _s(OWNER)


@pytest.fixture(scope="module")
def editor():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE}/api/auth/login", json=EDITOR, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"editor login failed: {r.status_code}")
    return s


@pytest.fixture(scope="module")
def anon():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- 1. Convert endpoint (already, invalid mode, editor 403) ----------

class TestConvert:
    def test_convert_designv2_first_and_idempotent(self, owner):
        pre_pages = owner.get(f"{BASE}/api/apps/{DESIGNV2_APP}/pages").json()
        # snapshot for content-preservation check later
        pytest.pre_pages_designv2 = copy.deepcopy(pre_pages)

        r = owner.post(f"{BASE}/api/apps/{DESIGNV2_APP}/convert-to-webapp", json={"signup_mode": "open"})
        assert r.status_code == 200, r.text
        data = r.json()
        # Might be already=True if a prev agent converted it - still assert summary structure
        assert "summary" in data
        summary = data["summary"]
        for k in ("auth", "protected_pages", "public_pages", "collections",
                  "sections_bound", "forms_connected", "roles", "api_base", "emails"):
            assert k in summary, f"missing {k} in summary"
        assert summary["roles"] == ["admin", "user"]
        assert summary["api_base"] == f"/api/site/{data.get('token') or ''}" or "/api/site/" in summary["api_base"]

        # Second call must return already=True
        r2 = owner.post(f"{BASE}/api/apps/{DESIGNV2_APP}/convert-to-webapp", json={"signup_mode": "open"})
        assert r2.status_code == 200
        assert r2.json().get("already") is True

    def test_convert_invalid_signup_mode_400(self, owner):
        r = owner.post(f"{BASE}/api/apps/{AURA_APP}/convert-to-webapp", json={"signup_mode": "bogus"})
        assert r.status_code == 400, r.text

    def test_convert_editor_forbidden(self, editor):
        r = editor.post(f"{BASE}/api/apps/{NORTHWIND_APP}/convert-to-webapp", json={"signup_mode": "open"})
        assert r.status_code == 403, f"expected 403 got {r.status_code} {r.text}"


# ---------- 2. Content preservation ----------

def _strip_added_props(pages):
    """Remove props.collection / props.dynamic and pages.protected which are allowed additions."""
    pages = copy.deepcopy(pages)
    for pg in pages if isinstance(pages, list) else pages.get("pages", []):
        pg.pop("protected", None)
        for b in pg.get("blocks") or []:
            props = b.get("props") or {}
            props.pop("collection", None)
            props.pop("dynamic", None)
    return pages


class TestContentPreservation:
    def test_designv2_blocks_unchanged(self, owner):
        pre = getattr(pytest, "pre_pages_designv2", None)
        if pre is None:
            pytest.skip("no pre-snapshot")
        post = owner.get(f"{BASE}/api/apps/{DESIGNV2_APP}/pages").json()
        a = _strip_added_props(pre)
        b = _strip_added_props(post)
        # compare per-page block content
        pre_pages = a if isinstance(a, list) else a.get("pages", [])
        post_pages = b if isinstance(b, list) else b.get("pages", [])
        assert len(pre_pages) == len(post_pages), "page count changed"
        for p1, p2 in zip(sorted(pre_pages, key=lambda x: x.get("slug", "")),
                          sorted(post_pages, key=lambda x: x.get("slug", ""))):
            assert p1.get("slug") == p2.get("slug")
            b1 = p1.get("blocks") or []
            b2 = p2.get("blocks") or []
            assert len(b1) == len(b2), f"block count changed on {p1.get('slug')}"
            for bl1, bl2 in zip(b1, b2):
                assert bl1.get("type") == bl2.get("type")
                # Compare props content (title/text/image fields)
                p1props = bl1.get("props") or {}
                p2props = bl2.get("props") or {}
                for k in p1props:
                    if k in ("collection", "dynamic"):
                        continue
                    assert p1props.get(k) == p2props.get(k), f"prop '{k}' changed on {p1.get('slug')} / {bl1.get('type')}"


# ---------- 3. Northwind collections (already converted) ----------

class TestCollections:
    def test_services_collection_returns_items(self, anon):
        r = anon.get(f"{BASE}/api/site/{NORTHWIND_TOKEN}/content/services")
        # If services collection exists it returns items; per context it should exist
        if r.status_code == 404:
            pytest.skip("services collection not present for northwind")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_no_duplicate_intra_collection(self, owner):
        # Fetch collections via admin API
        r = owner.get(f"{BASE}/api/site/{NORTHWIND_TOKEN}/admin/collections")
        assert r.status_code == 200, r.text
        cols = r.json().get("collections", [])
        for c in cols:
            titles = [i.get("title") for i in c.get("items", [])]
            # No exact duplicates within a single collection
            assert len(titles) == len(set(titles)) or len(titles) <= 1, \
                f"duplicated titles in collection {c.get('slug')}: {titles}"


# ---------- 4. Visitor auth on Northwind ----------

class TestVisitorAuth:
    def test_register_short_password_400(self, anon):
        r = anon.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/register",
                      json={"email": f"TEST_short_{uuid.uuid4().hex[:6]}@ex.com", "password": "short"})
        assert r.status_code == 400

    def test_register_and_login_and_me(self, anon):
        email = f"TEST_visitor_{uuid.uuid4().hex[:6]}@ex.com"
        pw = "TestPass12345"
        r = anon.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/register",
                      json={"email": email, "password": pw, "name": "Test"})
        assert r.status_code == 200, r.text
        tok = r.json().get("token")
        assert tok
        pytest.tenant_token = tok
        pytest.tenant_email = email

        # duplicate
        r2 = anon.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/register",
                       json={"email": email, "password": pw})
        assert r2.status_code == 409

        # login wrong password
        r3 = anon.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/login",
                       json={"email": email, "password": "WrongPass111"})
        assert r3.status_code == 401

        # login correct
        r4 = anon.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/login",
                       json={"email": email, "password": pw})
        assert r4.status_code == 200
        tok2 = r4.json()["token"]

        # me with bearer
        r5 = requests.get(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/me",
                          headers={"Authorization": f"Bearer {tok2}"})
        assert r5.status_code == 200
        assert r5.json()["user"]["email"] == email.lower()

    def test_lockout_after_5_failures(self, anon):
        email = f"TEST_lock_{uuid.uuid4().hex[:6]}@ex.com"
        anon.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/register",
                  json={"email": email, "password": "TestPass12345"})
        # 5 bad attempts
        codes = []
        for i in range(6):
            r = anon.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/login",
                          json={"email": email, "password": "WrongWrong9"})
            codes.append(r.status_code)
        assert 429 in codes, f"no lockout observed: {codes}"

    def test_forgot_always_sent_true(self, anon):
        r = anon.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/forgot",
                      json={"email": "nobody_xyz@nowhere.com"})
        assert r.status_code == 200
        assert r.json().get("sent") is True

    def test_reset_bad_token_400(self, anon):
        r = anon.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/reset",
                      json={"token": "not-a-real-token", "password": "NewPassword123"})
        assert r.status_code == 400


# ---------- 5. Cross-tenant / cross-scope token isolation ----------

class TestTokenIsolation:
    def test_tenant_token_not_valid_on_agency_endpoints(self):
        tok = getattr(pytest, "tenant_token", None)
        if not tok:
            pytest.skip("no tenant token available")
        # should be 401/403 on agency endpoint
        r = requests.get(f"{BASE}/api/apps", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code in (401, 403), f"tenant token accepted on agency route: {r.status_code}"

    def test_tenant_token_not_valid_on_other_tenant(self, anon):
        tok = getattr(pytest, "tenant_token", None)
        if not tok:
            pytest.skip("no tenant token")
        # ensure design v2 tenant is converted (or attempt)
        cfg = anon.get(f"{BASE}/api/site/pv_5e8a111a9471561ed15a/config").json()
        if not cfg.get("converted"):
            pytest.skip("design v2 not converted")
        r = requests.get(f"{BASE}/api/site/pv_5e8a111a9471561ed15a/auth/me",
                         headers={"Authorization": f"Bearer {tok}"})
        # audience matches (SITE_AUD) but app id mismatch => current_site_user returns None => 401
        assert r.status_code == 401


# ---------- 6. Signup modes ----------

class TestSignupModes:
    def test_switch_to_approval_and_registration_pending(self, owner, anon):
        r = owner.patch(f"{BASE}/api/apps/{NORTHWIND_APP}/webapp/settings",
                        json={"signup_mode": "approval"})
        assert r.status_code == 200
        assert r.json()["signup_mode"] == "approval"

        email = f"TEST_appr_{uuid.uuid4().hex[:6]}@ex.com"
        pw = "TestPass12345"
        r2 = anon.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/register",
                       json={"email": email, "password": pw})
        assert r2.status_code == 200
        assert r2.json().get("pending") is True

        # login should be 403 while pending
        r3 = anon.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/login",
                       json={"email": email, "password": pw})
        assert r3.status_code == 403

    def test_switch_to_invite_only_rejects_register(self, owner, anon):
        r = owner.patch(f"{BASE}/api/apps/{NORTHWIND_APP}/webapp/settings",
                        json={"signup_mode": "invite"})
        assert r.status_code == 200
        r2 = anon.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/auth/register",
                       json={"email": f"TEST_inv_{uuid.uuid4().hex[:6]}@ex.com", "password": "TestPass12345"})
        assert r2.status_code == 403

    def test_admin_invite_creates_user(self, owner):
        email = f"TEST_invited_{uuid.uuid4().hex[:6]}@ex.com"
        r = owner.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/admin/users/invite",
                       json={"email": email, "role": "user"})
        assert r.status_code == 200, r.text
        assert r.json()["invited"]["email"] == email.lower()

    def test_restore_mode_to_open(self, owner):
        r = owner.patch(f"{BASE}/api/apps/{NORTHWIND_APP}/webapp/settings",
                        json={"signup_mode": "open"})
        assert r.status_code == 200


# ---------- 7. Members-only pages / page access ----------

class TestPageAccess:
    def test_public_page_no_auth_required(self, anon):
        r = anon.get(f"{BASE}/api/site/{NORTHWIND_TOKEN}/page/")
        assert r.status_code == 200
        assert not r.json().get("requires_login")

    def test_toggle_page_protected_and_gate(self, owner, anon):
        # find /about page id
        w = owner.get(f"{BASE}/api/apps/{NORTHWIND_APP}/webapp").json()
        about = next((p for p in w["pages"] if p["slug"] == "/about"), None)
        if not about:
            pytest.skip("no /about page")
        # protect it
        r = owner.post(f"{BASE}/api/apps/{NORTHWIND_APP}/webapp/pages/{about['page_id']}/access",
                       json={"protected": True})
        assert r.status_code == 200
        try:
            r2 = anon.get(f"{BASE}/api/site/{NORTHWIND_TOKEN}/page/about")
            assert r2.status_code == 200
            data = r2.json()
            assert data.get("protected") is True
            assert data.get("requires_login") is True
            assert "blocks" not in data, "content leaked while protected"

            # with member token full page returns
            tok = getattr(pytest, "tenant_token", None)
            if tok:
                r3 = requests.get(f"{BASE}/api/site/{NORTHWIND_TOKEN}/page/about",
                                  headers={"Authorization": f"Bearer {tok}"})
                assert r3.status_code == 200
                assert "blocks" in r3.json()
        finally:
            owner.post(f"{BASE}/api/apps/{NORTHWIND_APP}/webapp/pages/{about['page_id']}/access",
                       json={"protected": False})


# ---------- 8. Form submissions ----------

class TestSubmissions:
    def test_submit_and_appears_in_admin(self, owner, anon):
        marker = f"TEST_sub_{uuid.uuid4().hex[:6]}"
        r = anon.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/submit",
                      json={"form_name": marker, "name": marker,
                            "email": f"{marker.lower()}@ex.com",
                            "fields": {"message": "hello"}})
        assert r.status_code == 200, r.text
        assert r.json().get("ok")

        r2 = owner.get(f"{BASE}/api/site/{NORTHWIND_TOKEN}/admin/submissions", params={"q": marker})
        assert r2.status_code == 200
        rows = r2.json()["submissions"]
        assert any(row.get("name") == marker for row in rows), "submission not returned in admin search"
        pytest.sub_id = next(row["submission_id"] for row in rows if row.get("name") == marker)

    def test_mark_handled(self, owner):
        sid = getattr(pytest, "sub_id", None)
        if not sid:
            pytest.skip("no submission id")
        r = owner.patch(f"{BASE}/api/site/{NORTHWIND_TOKEN}/admin/submissions/{sid}",
                        json={"status": "handled"})
        assert r.status_code == 200
        assert r.json()["status"] == "handled"

    def test_csv_export(self, owner):
        r = owner.get(f"{BASE}/api/apps/{NORTHWIND_APP}/submissions", params={"export": "true"})
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert "created_at" in r.text


# ---------- 9. Admin panel access + user management ----------

class TestAdminPanel:
    def test_owner_can_access_admin_summary(self, owner):
        r = owner.get(f"{BASE}/api/site/{NORTHWIND_TOKEN}/admin/summary")
        assert r.status_code == 200
        data = r.json()
        for k in ("site", "me", "totals", "submissions_daily", "signups_daily"):
            assert k in data

    def test_standard_user_403_on_admin(self):
        tok = getattr(pytest, "tenant_token", None)
        if not tok:
            pytest.skip("no user token")
        r = requests.get(f"{BASE}/api/site/{NORTHWIND_TOKEN}/admin/summary",
                         headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 403

    def test_admin_cannot_demote_self(self, owner):
        summary = owner.get(f"{BASE}/api/site/{NORTHWIND_TOKEN}/admin/summary").json()
        my_id = summary["me"].get("site_user_id")
        if not my_id:
            pytest.skip("no self id")
        r = owner.patch(f"{BASE}/api/site/{NORTHWIND_TOKEN}/admin/users/{my_id}",
                        json={"role": "user"})
        # Owner acts through agency session → me.site_user_id is user_id string, may or may not be in site_users;
        # backend blocks demotion only when site_user_id matches. Accept 400 or 404.
        assert r.status_code in (400, 404)

    def test_no_admin_endpoint_anonymous(self, anon):
        r = anon.get(f"{BASE}/api/site/{NORTHWIND_TOKEN}/admin/summary")
        assert r.status_code in (401, 403)


# ---------- 10. Content CRUD ----------

class TestContentTab:
    def test_create_update_delete_item(self, owner):
        cols = owner.get(f"{BASE}/api/site/{NORTHWIND_TOKEN}/admin/collections").json()["collections"]
        if not cols:
            pytest.skip("no collections to test")
        col = cols[0]
        # create
        r = owner.post(f"{BASE}/api/site/{NORTHWIND_TOKEN}/admin/collections/{col['slug']}/items",
                       json={"title": "TEST_temp_item", "excerpt": "x", "body": "y", "published": True})
        assert r.status_code == 200
        item = r.json()
        item_id = item["item_id"]
        # update
        r2 = owner.put(f"{BASE}/api/site/{NORTHWIND_TOKEN}/admin/items/{item_id}",
                       json={"title": "TEST_temp_item_renamed", "excerpt": "x", "body": "y",
                             "cover": "", "published": False, "fields": {}})
        assert r2.status_code == 200
        assert r2.json()["title"] == "TEST_temp_item_renamed"
        assert r2.json()["published"] is False
        # delete
        r3 = owner.delete(f"{BASE}/api/site/{NORTHWIND_TOKEN}/admin/items/{item_id}")
        assert r3.status_code == 200


# ---------- 11. Route shadow / _id serialization ----------

class TestPlumbing:
    def test_no_mongo_id_leakage(self, anon, owner):
        for path in [f"/api/site/{NORTHWIND_TOKEN}/config",
                     f"/api/site/{NORTHWIND_TOKEN}/content/services",
                     f"/api/site/{NORTHWIND_TOKEN}/page/"]:
            r = anon.get(f"{BASE}{path}")
            if r.status_code == 200:
                assert '"_id"' not in r.text, f"_id leaked at {path}"
        r = owner.get(f"{BASE}/api/site/{NORTHWIND_TOKEN}/admin/collections")
        assert r.status_code == 200
        assert '"_id"' not in r.text

    def test_health(self, anon):
        # convert route registered — 405 not 404 for GET
        r = anon.get(f"{BASE}/api/apps/{NORTHWIND_APP}/convert-to-webapp")
        assert r.status_code in (401, 403, 405)
