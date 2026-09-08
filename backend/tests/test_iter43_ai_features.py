"""Iter 43 — AI lead summary, booking follow-ups, digest AI section, and PATCH /api/ai/models admin gate fix."""
import os
import time
import requests
import pytest

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
API = BASE_URL + "/api"

OWNER = ("jaybernabe@luciodigital.com", "Lucio2026!")
EDITOR = ("client.editor@example.com", "ClientEdit2026!")
APP_ID = "app_6663b5de0007"
TOKEN = "pv_15f7e07b2d724b452e2a"  # Northwind converted webapp token


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def owner():
    return _login(*OWNER)


@pytest.fixture(scope="module")
def editor():
    return _login(*EDITOR)


# ---------- Iter 42 P0 fix: PATCH /api/ai/models admin gate ----------
class TestAdminGateFix:
    def test_owner_patch_valid_returns_200(self, owner):
        r = owner.patch(f"{API}/ai/models", json={"model": "gemini-3-flash-preview"}, timeout=20)
        assert r.status_code == 200, f"owner PATCH failed: {r.status_code} {r.text[:300]}"

    def test_unknown_model_returns_400(self, owner):
        r = owner.patch(f"{API}/ai/models", json={"model": "junk-model-x"}, timeout=20)
        assert r.status_code == 400

    def test_unknown_feature_returns_400(self, owner):
        r = owner.patch(f"{API}/ai/models", json={"features": {"bogus": "claude-sonnet-5"}}, timeout=20)
        assert r.status_code == 400

    def test_editor_still_forbidden(self, editor):
        r = editor.patch(f"{API}/ai/models", json={"model": "claude-sonnet-5"}, timeout=20)
        assert r.status_code == 403


# ---------- Lead summary ----------
class TestLeadSummary:
    def test_post_generates_and_persists(self, owner):
        # Ensure tenant override sets lead_scoring model resolution deterministic
        owner.patch(f"{API}/apps/{APP_ID}/ai-model",
                    json={"model": "gemini-3-flash-preview",
                          "features": {"site_generation": "gemini-3.1-pro-preview"}}, timeout=20)
        t0 = time.time()
        r = owner.post(f"{API}/apps/{APP_ID}/ai/lead-summary", timeout=180)
        elapsed = time.time() - t0
        assert r.status_code == 200, f"lead-summary failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        for k in ("summary", "counts", "model", "generated_at"):
            assert k in data, f"missing {k} in {data}"
        counts = data["counts"]
        for ck in ("leads", "hot", "days", "sources", "unread"):
            assert ck in counts, f"missing counts.{ck}"
        assert counts["days"] == 7
        assert isinstance(counts["sources"], dict)
        assert isinstance(data["summary"], str) and data["summary"]
        print(f"lead-summary model={data['model']} leads={counts['leads']} took {elapsed:.1f}s")
        # Verify persistence via GET
        g = owner.get(f"{API}/apps/{APP_ID}/ai/lead-summary", timeout=20)
        assert g.status_code == 200
        cached = g.json()
        assert cached.get("summary") == data["summary"]
        assert cached.get("model") == data["model"]

    def test_model_respects_lead_scoring_resolution(self, owner):
        # Set tenant feature override for lead_scoring to a distinct model
        r = owner.patch(f"{API}/apps/{APP_ID}/ai-model",
                        json={"model": "gemini-3-flash-preview",
                              "features": {"lead_scoring": "claude-haiku-4-5-20251001",
                                           "site_generation": "gemini-3.1-pro-preview"}}, timeout=20)
        assert r.status_code == 200
        # Verify resolution
        eff = owner.get(f"{API}/apps/{APP_ID}/ai-model", timeout=20).json()["effective"]
        assert eff["lead_scoring"]["model"] == "claude-haiku-4-5-20251001"
        # Regenerate summary and confirm model matches
        r = owner.post(f"{API}/apps/{APP_ID}/ai/lead-summary", timeout=180)
        assert r.status_code == 200
        data = r.json()
        # counts.leads may be 0 (then model may be "" per code). Only assert when >0
        if data["counts"]["leads"] > 0:
            assert data["model"] == "claude-haiku-4-5-20251001", (
                f"expected lead_scoring model, got {data['model']}")
        # Restore
        owner.patch(f"{API}/apps/{APP_ID}/ai-model",
                    json={"model": "gemini-3-flash-preview",
                          "features": {"site_generation": "gemini-3.1-pro-preview"}}, timeout=20)


# ---------- Digest AI section ----------
class TestDigestAiSummary:
    def test_digest_preview_has_ai_summary(self, owner):
        r = owner.get(f"{API}/apps/{APP_ID}/digest/preview", timeout=180)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "ai_summary" in data, f"missing ai_summary key: {list(data.keys())}"
        # text field: either 'text', 'body' — find it
        text_field = None
        for k in ("text", "body", "preview", "email"):
            v = data.get(k)
            if isinstance(v, str) and v:
                text_field = v
                break
        assert text_field is not None, f"no text body in digest preview: {list(data.keys())}"
        # ai_summary should be present in text if non-empty
        if data["ai_summary"]:
            assert "AI SUMMARY OF YOUR LEADS" in text_field, (
                f"AI SUMMARY OF YOUR LEADS not in digest text; ai_summary={data['ai_summary'][:80]!r}")


# ---------- Booking follow-ups (site panel, cookie auth via owner) ----------
def _find_booking(sess):
    """Find a submission with a booking via owner API."""
    r = sess.get(f"{API}/apps/{APP_ID}/submissions", timeout=20)
    if r.status_code == 200:
        subs = r.json() if isinstance(r.json(), list) else r.json().get("submissions", [])
        for s in subs:
            if s.get("booking"):
                return s
    return None


@pytest.fixture(scope="module")
def a_booking(owner):
    b = _find_booking(owner)
    if not b:
        pytest.skip("no booking submission found on tenant")
    return b


class TestBookingFollowups:
    def test_draft_reminder(self, owner, a_booking):
        sid = a_booking["submission_id"]
        r = owner.post(f"{API}/site/{TOKEN}/admin/bookings/{sid}/ai-followup?kind=reminder", timeout=180)
        assert r.status_code == 200, f"draft reminder failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert data.get("kind") == "reminder"
        assert isinstance(data.get("body"), str) and data["body"]
        assert data.get("drafted_at")
        # Persistence — GET submissions and check followups
        r2 = owner.get(f"{API}/apps/{APP_ID}/submissions", timeout=20)
        subs = r2.json() if isinstance(r2.json(), list) else r2.json().get("submissions", [])
        row = next((s for s in subs if s["submission_id"] == sid), None)
        assert row and row.get("booking", {}).get("followups", {}).get("reminder", {}).get("body")

    def test_draft_thankyou(self, owner, a_booking):
        sid = a_booking["submission_id"]
        r = owner.post(f"{API}/site/{TOKEN}/admin/bookings/{sid}/ai-followup?kind=thankyou", timeout=180)
        assert r.status_code == 200
        data = r.json()
        assert data.get("kind") == "thankyou"
        assert data.get("body")

    def test_invalid_kind_400(self, owner, a_booking):
        sid = a_booking["submission_id"]
        r = owner.post(f"{API}/site/{TOKEN}/admin/bookings/{sid}/ai-followup?kind=nope", timeout=30)
        assert r.status_code == 400

    def test_unknown_submission_404(self, owner):
        r = owner.post(f"{API}/site/{TOKEN}/admin/bookings/does_not_exist/ai-followup?kind=reminder", timeout=30)
        assert r.status_code == 404

    def test_unauthenticated_401_or_403(self):
        s = requests.Session()
        r = s.post(f"{API}/site/{TOKEN}/admin/bookings/anything/ai-followup?kind=reminder", timeout=20)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_send_ok_and_records_sent_at(self, owner, a_booking):
        sid = a_booking["submission_id"]
        # First ensure booking has an email; if not, we skip
        if not a_booking.get("email"):
            pytest.skip("booking has no email; covered by test_send_no_email_400")
        r = owner.post(f"{API}/site/{TOKEN}/admin/bookings/{sid}/followup-send",
                       json={"kind": "reminder", "body": "Test send from iter43 — please ignore."}, timeout=30)
        assert r.status_code == 200, f"send failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert data.get("sent_at")
        assert data.get("kind") == "reminder"

    def test_send_empty_body_400(self, owner, a_booking):
        sid = a_booking["submission_id"]
        r = owner.post(f"{API}/site/{TOKEN}/admin/bookings/{sid}/followup-send",
                       json={"kind": "reminder", "body": ""}, timeout=30)
        assert r.status_code == 400

    def test_send_no_email_400(self, owner):
        """Find any booking submission without an email (or skip)."""
        r = owner.get(f"{API}/apps/{APP_ID}/submissions", timeout=20)
        subs = r.json() if isinstance(r.json(), list) else r.json().get("submissions", [])
        target = next((s for s in subs if s.get("booking") and not s.get("email")), None)
        if not target:
            pytest.skip("no booking without email available")
        r = owner.post(f"{API}/site/{TOKEN}/admin/bookings/{target['submission_id']}/followup-send",
                       json={"kind": "reminder", "body": "hi"}, timeout=30)
        assert r.status_code == 400


# ---------- Restore tenant state ----------
def test_zz_restore_tenant(owner):
    r = owner.patch(f"{API}/apps/{APP_ID}/ai-model",
                    json={"model": "gemini-3-flash-preview",
                          "features": {"site_generation": "gemini-3.1-pro-preview"}}, timeout=20)
    assert r.status_code == 200
