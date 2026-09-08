"""Iter 42 - Gemini AI models registry, resolution, tenant override, and SEO write."""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
API = BASE_URL + "/api"

OWNER = ("jaybernabe@luciodigital.com", "Lucio2026!")
EDITOR = ("client.editor@example.com", "ClientEdit2026!")
APP_ID = "app_6663b5de0007"

EXPECTED_MODELS = {
    "claude-sonnet-5", "claude-haiku-4-5-20251001",
    "gemini-3-flash-preview", "gemini-3.1-pro-preview",
    "gpt-5.4", "gpt-5.4-mini",
}
EXPECTED_FEATURES = {"site_generation", "chat_widget", "lead_scoring", "copy_rewrite", "seo"}


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def owner():
    return _login(*OWNER)


@pytest.fixture(scope="module")
def editor():
    return _login(*EDITOR)


# ---------- GET /api/ai/models registry ----------
class TestModelRegistry:
    def test_list_models(self, owner):
        r = owner.get(f"{API}/ai/models", timeout=20)
        assert r.status_code == 200
        data = r.json()
        ids = {m["id"] for m in data["models"]}
        assert ids == EXPECTED_MODELS, f"expected {EXPECTED_MODELS} got {ids}"
        # provider + label present
        for m in data["models"]:
            assert m["provider"] in {"anthropic", "gemini", "openai"}
            assert isinstance(m["label"], str) and m["label"]
        assert set(data["features"]) == EXPECTED_FEATURES
        # feature defaults
        fd = data["feature_defaults"]
        assert fd["site_generation"] == "gemini-3.1-pro-preview"
        assert fd["chat_widget"] == "gemini-3-flash-preview"
        assert fd["seo"] == "gemini-3-flash-preview"
        # platform block
        assert "platform" in data and "model" in data["platform"]
        # nano banana image model id
        assert data["image_model"] == "gemini-2.5-flash-image-preview"


# ---------- PATCH /api/ai/models (platform default) ----------
class TestPlatformDefault:
    def test_editor_forbidden(self, editor):
        r = editor.patch(f"{API}/ai/models", json={"model": "claude-sonnet-5"}, timeout=20)
        assert r.status_code == 403, r.text

    def test_unknown_model_rejected(self, owner):
        r = owner.patch(f"{API}/ai/models", json={"model": "junk-model-x"}, timeout=20)
        assert r.status_code == 400
        assert "unknown model" in r.text.lower()

    def test_unknown_feature_rejected(self, owner):
        r = owner.patch(f"{API}/ai/models", json={"features": {"bogus": "claude-sonnet-5"}}, timeout=20)
        assert r.status_code == 400

    def test_set_platform_default_and_verify_list(self, owner):
        r = owner.patch(f"{API}/ai/models",
                        json={"model": "gemini-3-flash-preview",
                              "features": {"seo": "gemini-3.1-pro-preview"}},
                        timeout=20)
        assert r.status_code == 200, r.text
        # Verify via GET
        g = owner.get(f"{API}/ai/models", timeout=20).json()
        assert g["platform"]["model"] == "gemini-3-flash-preview"
        assert g["platform"]["features"]["seo"] == "gemini-3.1-pro-preview"


# ---------- tenant override ----------
class TestTenantOverride:
    def test_editor_forbidden(self, editor):
        r = editor.patch(f"{API}/apps/{APP_ID}/ai-model",
                         json={"model": "gemini-3-flash-preview"}, timeout=20)
        assert r.status_code == 403

    def test_unknown_model_rejected(self, owner):
        r = owner.patch(f"{API}/apps/{APP_ID}/ai-model", json={"model": "no-such"}, timeout=20)
        assert r.status_code == 400

    def test_unknown_feature_rejected(self, owner):
        r = owner.patch(f"{API}/apps/{APP_ID}/ai-model",
                        json={"features": {"nope": "claude-sonnet-5"}}, timeout=20)
        assert r.status_code == 400

    def test_override_and_effective_resolution(self, owner):
        # Platform default was set in previous class to gemini-3-flash-preview
        # with platform.features.seo = gemini-3.1-pro-preview.
        # Set tenant override: whole-tenant claude-haiku, per-feature site_generation=gemini-3.1-pro-preview
        payload = {"model": "claude-haiku-4-5-20251001",
                   "features": {"site_generation": "gemini-3.1-pro-preview"}}
        r = owner.patch(f"{API}/apps/{APP_ID}/ai-model", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        # Get resolved effective
        eff = owner.get(f"{API}/apps/{APP_ID}/ai-model", timeout=20).json()
        assert eff["override"]["model"] == "claude-haiku-4-5-20251001"
        assert eff["override"]["features"]["site_generation"] == "gemini-3.1-pro-preview"
        e = eff["effective"]
        # tenant-feature wins for site_generation
        assert e["site_generation"]["model"] == "gemini-3.1-pro-preview"
        assert e["site_generation"]["provider"] == "gemini"
        # tenant-model wins for anything without a tenant-feature entry (chat_widget, lead_scoring, copy_rewrite, seo)
        # NB: platform.features.seo=gemini-3.1-pro-preview should be OVERRIDDEN by tenant-model
        assert e["chat_widget"]["model"] == "claude-haiku-4-5-20251001"
        assert e["seo"]["model"] == "claude-haiku-4-5-20251001", (
            f"tenant-model should take precedence over platform-feature, got {e['seo']}")
        assert e["lead_scoring"]["model"] == "claude-haiku-4-5-20251001"

    def test_platform_feature_wins_when_no_tenant_override(self, owner):
        # Clear tenant override entirely
        r = owner.patch(f"{API}/apps/{APP_ID}/ai-model", json={}, timeout=20)
        assert r.status_code == 200
        eff = owner.get(f"{API}/apps/{APP_ID}/ai-model", timeout=20).json()["effective"]
        # platform.model=gemini-3-flash-preview, platform.features.seo=gemini-3.1-pro-preview
        assert eff["seo"]["model"] == "gemini-3.1-pro-preview"  # platform-feature
        assert eff["chat_widget"]["model"] == "gemini-3-flash-preview"  # platform-model


# ---------- Fallback when platform doc empty ----------
class TestFallback:
    def test_falls_back_to_builtin_defaults(self, owner):
        # Empty platform doc entirely
        r = owner.patch(f"{API}/ai/models", json={}, timeout=20)
        assert r.status_code == 200
        # And clear tenant override
        owner.patch(f"{API}/apps/{APP_ID}/ai-model", json={}, timeout=20)
        eff = owner.get(f"{API}/apps/{APP_ID}/ai-model", timeout=20).json()["effective"]
        # Should hit FEATURE_DEFAULTS
        assert eff["site_generation"]["model"] == "gemini-3.1-pro-preview"
        assert eff["chat_widget"]["model"] == "gemini-3-flash-preview"
        assert eff["seo"]["model"] == "gemini-3-flash-preview"
        assert eff["copy_rewrite"]["model"] == "claude-sonnet-5"


# ---------- Actual Gemini call: SEO ----------
class TestSEOGemini:
    def test_seo_run_writes_pages(self, owner):
        # Set tenant to gemini-3-flash-preview whole-tenant (matches required restored state)
        r = owner.patch(f"{API}/apps/{APP_ID}/ai-model",
                        json={"model": "gemini-3-flash-preview",
                              "features": {"site_generation": "gemini-3.1-pro-preview"}}, timeout=20)
        assert r.status_code == 200
        # Run SEO
        t0 = time.time()
        r = owner.post(f"{API}/apps/{APP_ID}/ai/seo", timeout=180)
        elapsed = time.time() - t0
        assert r.status_code == 200, f"seo failed {r.status_code}: {r.text[:400]}"
        data = r.json()
        assert data["model"] == "gemini-3-flash-preview"
        assert data["provider"] == "gemini"
        assert len(data["pages"]) >= 1, f"expected >=1 pages, got {data}"
        print(f"SEO wrote {len(data['pages'])} pages in {elapsed:.1f}s")
        # Verify persistence on page docs
        pgs = owner.get(f"{API}/apps/{APP_ID}/pages", timeout=20).json()
        # pgs may be a list or dict
        page_list = pgs if isinstance(pgs, list) else pgs.get("pages", [])
        assert page_list, "no pages returned"
        seo_ct = 0
        for p in page_list:
            seo = p.get("seo")
            if seo:
                seo_ct += 1
                assert seo.get("model") == "gemini-3-flash-preview"
                # title/description non-empty on at least some
        assert seo_ct >= 1, f"no persisted seo objects; sample page: {page_list[0].keys()}"

    def test_seo_did_not_alter_block_content(self, owner):
        # Just confirm pages still have blocks (non-empty)
        pgs = owner.get(f"{API}/apps/{APP_ID}/pages", timeout=20).json()
        page_list = pgs if isinstance(pgs, list) else pgs.get("pages", [])
        assert any((p.get("blocks") or []) for p in page_list), "blocks were wiped"


# ---------- Routing smoke: AI editor works under Gemini and under Claude ----------
class TestEditorRouting:
    def _first_page_and_block(self, sess):
        pgs = sess.get(f"{API}/apps/{APP_ID}/pages", timeout=20).json()
        page_list = pgs if isinstance(pgs, list) else pgs.get("pages", [])
        for p in page_list:
            blocks = p.get("blocks") or []
            for b in blocks:
                if b.get("id") and b.get("type"):
                    return p, b
        return None, None

    def test_ai_edit_under_gemini(self, owner):
        # Tenant already gemini-3-flash-preview from previous test
        p, b = self._first_page_and_block(owner)
        if not b:
            pytest.skip("no block to edit")
        r = owner.post(f"{API}/apps/{APP_ID}/ai/edit",
                       json={"prompt": "keep as is", "block": b}, timeout=90)
        assert r.status_code == 200, f"gemini editor call failed: {r.status_code} {r.text[:300]}"
        out = r.json()
        assert out.get("id") == b["id"] and out.get("type") == b["type"]

    def test_ai_edit_under_claude(self, owner):
        # switch to claude-sonnet-5
        r = owner.patch(f"{API}/apps/{APP_ID}/ai-model",
                        json={"model": "claude-sonnet-5"}, timeout=20)
        assert r.status_code == 200
        p, b = self._first_page_and_block(owner)
        if not b:
            pytest.skip("no block to edit")
        r = owner.post(f"{API}/apps/{APP_ID}/ai/edit",
                       json={"prompt": "keep as is", "block": b}, timeout=90)
        assert r.status_code == 200, f"claude editor failed: {r.status_code} {r.text[:300]}"


# ---------- Restore tenant to required state ----------
def test_zz_restore_tenant_gemini(request):
    s = _login(*OWNER)
    r = s.patch(f"{API}/apps/{APP_ID}/ai-model",
                json={"model": "gemini-3-flash-preview",
                      "features": {"site_generation": "gemini-3.1-pro-preview"}}, timeout=20)
    assert r.status_code == 200
    # Also wipe platform default so we don't leave junk
    r = s.patch(f"{API}/ai/models", json={}, timeout=20)
    assert r.status_code == 200
