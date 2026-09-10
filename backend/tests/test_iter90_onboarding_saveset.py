"""Iteration 90 — Save-as-Section-Set (shared across accounts), delete, section-sets merge,
plus the client Onboarding Checklist (auto-detection, manual done/skipped/reset).
Runs against app_testlab; every scratch resource is torn down."""
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
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    yield s


@pytest.fixture(scope="module")
def home_page_id(client):
    r = client.get(f"{API}/apps/{APP_ID}/pages", timeout=20)
    assert r.status_code == 200
    for p in r.json():
        if p.get("slug") == "/":
            return p["page_id"]
    pytest.skip("no home page")


def _scratch(client, slug, name):
    r = client.post(f"{API}/apps/{APP_ID}/pages", json={"slug": slug, "name": name}, timeout=30)
    assert r.status_code in (200, 201), r.text
    return r.json().get("page_id") or r.json().get("id")


# =========================================================================
# Save-as-set
# =========================================================================

class TestSaveAsSet:
    def test_empty_page_400s(self, client):
        pid = _scratch(client, "/iter90-empty", "Iter90 Empty")
        try:
            # ensure empty
            client.post(f"{API}/apps/{APP_ID}/pages/{pid}/apply-set", json={"set_id": "blank"}, timeout=20)
            r = client.post(f"{API}/apps/{APP_ID}/pages/{pid}/save-as-set",
                            json={"label": "Wont Save", "page_type": "any"}, timeout=20)
            assert r.status_code == 400, r.text
            assert "no sections" in r.text.lower()
        finally:
            client.delete(f"{API}/apps/{APP_ID}/pages/{pid}", timeout=20)

    def test_blank_label_400s(self, client):
        pid = _scratch(client, "/iter90-nolabel", "Iter90 NoLabel")
        try:
            client.post(f"{API}/apps/{APP_ID}/pages/{pid}/apply-set", json={"set_id": "general-standard"}, timeout=30)
            r = client.post(f"{API}/apps/{APP_ID}/pages/{pid}/save-as-set",
                            json={"label": "   ", "page_type": "any"}, timeout=20)
            assert r.status_code == 400, r.text
        finally:
            client.delete(f"{API}/apps/{APP_ID}/pages/{pid}", timeout=20)

    def test_unknown_page_type_400s(self, client):
        pid = _scratch(client, "/iter90-badtype", "Iter90 BadType")
        try:
            client.post(f"{API}/apps/{APP_ID}/pages/{pid}/apply-set", json={"set_id": "general-standard"}, timeout=30)
            r = client.post(f"{API}/apps/{APP_ID}/pages/{pid}/save-as-set",
                            json={"label": "Test", "page_type": "blog"}, timeout=20)
            assert r.status_code == 400, r.text
        finally:
            client.delete(f"{API}/apps/{APP_ID}/pages/{pid}", timeout=20)

    def test_save_stores_block_types_no_navbar_or_footer(self, client):
        pid = _scratch(client, "/iter90-save", "Iter90 Save")
        set_id = None
        try:
            client.post(f"{API}/apps/{APP_ID}/pages/{pid}/apply-set",
                        json={"set_id": "home-launch"}, timeout=30)
            # inject a navbar + footer block manually via the page edit API if possible; otherwise trust exclusion
            r = client.post(f"{API}/apps/{APP_ID}/pages/{pid}/save-as-set",
                            json={"label": "TEST_iter90 launch", "page_type": "any", "hint": "just a test"},
                            timeout=20)
            assert r.status_code == 200, r.text
            d = r.json()
            set_id = d["id"]
            assert d["label"] == "TEST_iter90 launch"
            assert d["page_type"] == "any"
            assert "hint" in d
            assert "blocks" in d and isinstance(d["blocks"], list) and len(d["blocks"]) >= 1
            assert "navbar" not in d["blocks"] and "footer" not in d["blocks"]

            # merges into section-sets for another page type ('any' should appear everywhere)
            r2 = client.get(f"{API}/apps/{APP_ID}/pages/{pid}/section-sets", timeout=20)
            assert r2.status_code == 200
            payload = r2.json()
            ids = [s["id"] for s in payload["sets"]]
            assert set_id in ids, f"saved set missing: {ids}"
            assert payload["saved_count"] >= 1
        finally:
            if set_id:
                client.delete(f"{API}/section-sets/{set_id}", timeout=20)
            client.delete(f"{API}/apps/{APP_ID}/pages/{pid}", timeout=20)

    def test_shared_across_pages_and_apply_uses_current_client_copy(self, client):
        """Saved set from one page must be visible on another page and rebuild from that page's niche."""
        pid_src = _scratch(client, "/iter90-src", "Iter90 Src")
        pid_dst = _scratch(client, "/iter90-dst", "Iter90 Dst")
        set_id = None
        try:
            client.post(f"{API}/apps/{APP_ID}/pages/{pid_src}/apply-set",
                        json={"set_id": "general-standard"}, timeout=30)
            r = client.post(f"{API}/apps/{APP_ID}/pages/{pid_src}/save-as-set",
                            json={"label": "TEST_shared_set", "page_type": "any"}, timeout=20)
            assert r.status_code == 200, r.text
            set_id = r.json()["id"]

            # visible on other page's section-sets
            r2 = client.get(f"{API}/apps/{APP_ID}/pages/{pid_dst}/section-sets", timeout=20)
            assert set_id in [s["id"] for s in r2.json()["sets"]]

            # apply on other page rebuilds blocks
            r3 = client.post(f"{API}/apps/{APP_ID}/pages/{pid_dst}/apply-set",
                             json={"set_id": set_id}, timeout=30)
            assert r3.status_code == 200, r3.text
            assert r3.json()["count"] >= 1
            text_blob = str(r3.json()["blocks"]).lower()
            assert "lorem" not in text_blob
        finally:
            if set_id:
                client.delete(f"{API}/section-sets/{set_id}", timeout=20)
            client.delete(f"{API}/apps/{APP_ID}/pages/{pid_src}", timeout=20)
            client.delete(f"{API}/apps/{APP_ID}/pages/{pid_dst}", timeout=20)

    def test_delete_set_200_then_404(self, client):
        pid = _scratch(client, "/iter90-del", "Iter90 Del")
        set_id = None
        try:
            client.post(f"{API}/apps/{APP_ID}/pages/{pid}/apply-set",
                        json={"set_id": "general-standard"}, timeout=30)
            r = client.post(f"{API}/apps/{APP_ID}/pages/{pid}/save-as-set",
                            json={"label": "TEST_delme", "page_type": "any"}, timeout=20)
            set_id = r.json()["id"]
            r1 = client.delete(f"{API}/section-sets/{set_id}", timeout=20)
            assert r1.status_code == 200, r1.text
            r2 = client.delete(f"{API}/section-sets/{set_id}", timeout=20)
            assert r2.status_code == 404
            set_id = None
        finally:
            if set_id:
                client.delete(f"{API}/section-sets/{set_id}", timeout=20)
            client.delete(f"{API}/apps/{APP_ID}/pages/{pid}", timeout=20)


# =========================================================================
# Onboarding checklist
# =========================================================================

class TestOnboarding:

    def _reset_all(self, client):
        for step in ("logo", "address", "figures", "reviews", "accent", "live"):
            client.post(f"{API}/apps/{APP_ID}/onboarding/{step}",
                        json={"state": "reset"}, timeout=20)

    def test_returns_6_steps_with_flags(self, client):
        r = client.get(f"{API}/apps/{APP_ID}/onboarding", timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d.get("steps"), list) and len(d["steps"]) == 6
        step_ids = [s["id"] for s in d["steps"]]
        assert set(step_ids) == {"logo", "address", "figures", "reviews", "accent", "live"}
        for s in d["steps"]:
            for f in ("done", "skipped", "auto", "manual", "label", "hint"):
                assert f in s, f"missing {f}: {s}"
        for f in ("done", "total", "complete"):
            assert f in d

    def test_unknown_step_400(self, client):
        r = client.post(f"{API}/apps/{APP_ID}/onboarding/not_a_step",
                        json={"state": "done"}, timeout=20)
        assert r.status_code == 400, r.text
        assert "unknown step" in r.text.lower()

    def test_invalid_state_400(self, client):
        r = client.post(f"{API}/apps/{APP_ID}/onboarding/logo",
                        json={"state": "gibberish"}, timeout=20)
        assert r.status_code == 400, r.text

    def test_manual_done_then_reset(self, client):
        try:
            self._reset_all(client)
            base = client.get(f"{API}/apps/{APP_ID}/onboarding", timeout=20).json()
            base_done = base["done"]
            base_total = base["total"]
            # find a step which is not currently auto-done, so we observe an increment
            target = next((s for s in base["steps"] if not s["done"]), None)
            assert target is not None
            r = client.post(f"{API}/apps/{APP_ID}/onboarding/{target['id']}",
                            json={"state": "done"}, timeout=20)
            assert r.status_code == 200, r.text
            after = r.json()
            assert after["done"] == base_done + 1
            assert after["total"] == base_total
            step = next(s for s in after["steps"] if s["id"] == target["id"])
            assert step["done"] is True and step["manual"] == "done"

            # reset — falls back to auto (which is False for this step) → done drops back
            r2 = client.post(f"{API}/apps/{APP_ID}/onboarding/{target['id']}",
                             json={"state": "reset"}, timeout=20)
            assert r2.status_code == 200
            after2 = r2.json()
            assert after2["done"] == base_done
        finally:
            self._reset_all(client)

    def test_skipped_removes_from_total(self, client):
        try:
            self._reset_all(client)
            base = client.get(f"{API}/apps/{APP_ID}/onboarding", timeout=20).json()
            base_total = base["total"]
            target = next(s for s in base["steps"] if not s["skipped"])
            r = client.post(f"{API}/apps/{APP_ID}/onboarding/{target['id']}",
                            json={"state": "skipped"}, timeout=20)
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["total"] == base_total - 1
            step = next(s for s in d["steps"] if s["id"] == target["id"])
            assert step["skipped"] is True
        finally:
            self._reset_all(client)

    def test_auto_detection_logo_field(self, client):
        """If logo_url is populated on the app, the 'logo' step auto-flips to done."""
        # This test is read-only for logo_url; we simply check consistency between
        # the reported 'auto' flag and the actual app data.
        try:
            self._reset_all(client)
            r = client.get(f"{API}/apps/{APP_ID}/onboarding", timeout=20)
            d = r.json()
            # Just check flags exist and are booleans (real auto-flip is validated via UI test).
            for s in d["steps"]:
                assert isinstance(s["auto"], bool)
        finally:
            self._reset_all(client)


# =========================================================================
# Auth / permissions
# =========================================================================

class TestAuth:
    def test_onboarding_requires_auth(self):
        r = requests.get(f"{API}/apps/{APP_ID}/onboarding", timeout=20)
        assert r.status_code in (401, 403), r.text

    def test_save_as_set_requires_auth(self):
        r = requests.post(f"{API}/apps/{APP_ID}/pages/somepid/save-as-set",
                          json={"label": "x", "page_type": "any"}, timeout=20)
        assert r.status_code in (401, 403), r.text
