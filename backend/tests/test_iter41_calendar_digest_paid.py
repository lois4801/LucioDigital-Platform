"""Iteration 41: bookings calendar, weekly digest cron, paid members area."""
import os
import time
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

TOKEN = "pv_15f7e07b2d724b452e2a"
APP_ID = "app_6663b5de0007"
OWNER = ("jaybernabe@luciodigital.com", "Lucio2026!")
EDITOR = ("client.editor@example.com", "ClientEdit2026!")
MEMBER = ("member1@example.com", "MemberPass123")
CRON = "pH-EBnKfcWvHU87RXSr0H_6ldoUm3gRUikekU71zXRAwn79ieLxmjg"


def _login_session(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"
    return s


def _site_login_bearer(email, password):
    r = requests.post(f"{API}/site/{TOKEN}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"site login: {r.status_code} {r.text[:200]}"
    return r.json().get("token")


@pytest.fixture(scope="module")
def owner_h():
    s = _login_session(*OWNER)
    return s  # session with cookie


@pytest.fixture(scope="module")
def editor_h():
    return _login_session(*EDITOR)


@pytest.fixture(scope="module")
def member_h():
    t = _site_login_bearer(*MEMBER)
    return {"Authorization": f"Bearer {t}"}


# ---------- bookings ----------
class TestBookings:
    def test_create_edit_cancel(self, owner_h):
        payload = {"name": "TEST_Auto Tester", "email": "test.autotester@example.com",
                   "phone": "555-0100", "service": "Consult", "date": "2026-09-08",
                   "slot": "14:00", "duration_min": 45, "notes": "auto test", "notify": True}
        r = owner_h.post(f"{API}/site/{TOKEN}/admin/bookings", json=payload, timeout=20)
        assert r.status_code == 200, r.text[:200]
        sid = r.json()["booking"]["submission_id"]
        assert r.json()["booking"]["booking"]["duration_min"] == 45

        # edit -> move slot
        r2 = owner_h.put(f"{API}/site/{TOKEN}/admin/bookings/{sid}",
                          json={"slot": "15:00", "duration_min": 60, "notify": False},
                          timeout=20)
        assert r2.status_code == 200
        assert r2.json()["booking"]["slot"] == "15:00"

        # cancel quiet
        r3 = owner_h.delete(f"{API}/site/{TOKEN}/admin/bookings/{sid}?notify_client=false",
                             timeout=20)
        assert r3.status_code == 200
        assert r3.json()["booking"]["status"] == "cancelled"

    def test_duration_clamp(self, owner_h):
        r = owner_h.post(f"{API}/site/{TOKEN}/admin/bookings", timeout=20,
                          json={"name": "TEST_clamp", "date": "2026-09-09", "slot": "09:00",
                                "duration_min": 9999, "service": "X", "notify": False})
        assert r.status_code == 200
        assert r.json()["booking"]["booking"]["duration_min"] == 480

    def test_bad_submission_404(self, owner_h):
        r = owner_h.put(f"{API}/site/{TOKEN}/admin/bookings/sub_does_not_exist",
                         json={"slot": "10:00"}, timeout=20)
        assert r.status_code == 404

    def test_auth_guards(self, member_h):
        # anonymous
        r_anon = requests.post(f"{API}/site/{TOKEN}/admin/bookings",
                               json={"name": "x", "date": "2026-09-09"}, timeout=20)
        assert r_anon.status_code in (401, 403)
        # member token (site user, non-admin)
        r_m = requests.post(f"{API}/site/{TOKEN}/admin/bookings", headers=member_h,
                            json={"name": "x", "date": "2026-09-09"}, timeout=20)
        assert r_m.status_code in (401, 403)

    def test_member_cannot_reach_apps(self, member_h):
        # Site member JWT must NOT reach any /api/apps/... endpoint
        r = requests.get(f"{API}/apps/{APP_ID}/paid-members", headers=member_h, timeout=20)
        assert r.status_code in (401, 403)
        r2 = requests.get(f"{API}/apps/{APP_ID}/digest/preview", headers=member_h, timeout=20)
        assert r2.status_code in (401, 403)


# ---------- digest ----------
class TestDigest:
    def test_settings_save_and_reject_bad_hour(self, owner_h):
        r = owner_h.patch(f"{API}/apps/{APP_ID}/webapp/digest", timeout=20,
                           json={"enabled": True, "hour": 8, "recipients": []})
        assert r.status_code == 200
        r_bad = owner_h.patch(f"{API}/apps/{APP_ID}/webapp/digest", timeout=20,
                               json={"enabled": True, "hour": 99, "recipients": []})
        assert r_bad.status_code == 400

    def test_preview(self, owner_h):
        r = owner_h.get(f"{API}/apps/{APP_ID}/digest/preview", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "counts" in d and "recipients" in d and "text" in d
        assert isinstance(d["recipients"], list)
        assert "Northwind" in (d.get("text") or "") or (d.get("app") or {}).get("name")

    def test_test_send(self, owner_h):
        r = owner_h.post(f"{API}/apps/{APP_ID}/digest/test", timeout=30)
        assert r.status_code == 200
        assert r.json().get("sent_to") == OWNER[0]

    def test_cron_auth(self):
        r_no = requests.post(f"{API}/cron/weekly-digest", timeout=10)
        assert r_no.status_code == 401
        r_bad = requests.post(f"{API}/cron/weekly-digest",
                              headers={"Authorization": "Bearer wrong"}, timeout=10)
        assert r_bad.status_code == 401
        r_ok = requests.post(f"{API}/cron/weekly-digest",
                             headers={"Authorization": f"Bearer {CRON}"}, timeout=20)
        assert r_ok.status_code == 200
        assert r_ok.json().get("accepted") is True


# ---------- paid area ----------
class TestPaid:
    def test_reject_bad_mode_and_zero(self, owner_h):
        r = owner_h.patch(f"{API}/apps/{APP_ID}/webapp/paid", timeout=20,
                           json={"enabled": True, "mode": "bogus", "price": 29})
        assert r.status_code == 400
        r0 = owner_h.patch(f"{API}/apps/{APP_ID}/webapp/paid", timeout=20,
                            json={"enabled": True, "mode": "one_time", "price": 0})
        assert r0.status_code == 400

    def test_editor_forbidden(self, editor_h):
        r = editor_h.patch(f"{API}/apps/{APP_ID}/webapp/paid", timeout=20,
                           json={"enabled": True, "mode": "one_time", "price": 29})
        assert r.status_code == 403

    def test_paywall_info_and_toggle_off_then_on(self, owner_h):
        # get current settings to restore later
        pm = owner_h.get(f"{API}/apps/{APP_ID}/paid-members", timeout=20)
        assert pm.status_code == 200
        original = pm.json().get("paid") or {}
        pages_before = original.get("page_ids") or []

        # gated page currently (paid=true): confirm requires_payment
        r_gate = requests.get(f"{API}/site/{TOKEN}/page/services", timeout=20)
        assert r_gate.status_code == 200
        j = r_gate.json()
        assert j.get("paid") is True and j.get("requires_payment") is True, j

        # Disable
        rd = owner_h.patch(f"{API}/apps/{APP_ID}/webapp/paid", timeout=30,
                            json={"enabled": False, "mode": original.get("mode", "one_time"),
                                  "price": original.get("price", 29), "currency": original.get("currency", "usd"),
                                  "page_ids": []})
        assert rd.status_code == 200

        # After disable, /services must return full content (no requires_payment)
        r_open = requests.get(f"{API}/site/{TOKEN}/page/services", timeout=20)
        assert r_open.status_code == 200
        jo = r_open.json()
        assert not jo.get("requires_payment"), f"page should be public after disable: {jo}"

        # Re-enable to restore
        re = owner_h.patch(f"{API}/apps/{APP_ID}/webapp/paid", timeout=30,
                            json={"enabled": True, "mode": original.get("mode", "one_time"),
                                  "price": original.get("price", 29), "currency": original.get("currency", "usd"),
                                  "page_ids": pages_before})
        assert re.status_code == 200, re.text[:200]

    def test_paywall_endpoints(self, member_h):
        # anonymous paywall info
        r_anon = requests.get(f"{API}/site/{TOKEN}/paywall", timeout=20)
        assert r_anon.status_code == 200
        assert r_anon.json()["signed_in"] is False

        # member signed-in but no access
        r_mi = requests.get(f"{API}/site/{TOKEN}/paywall", headers=member_h, timeout=20)
        assert r_mi.status_code == 200
        assert r_mi.json()["signed_in"] is True
        assert r_mi.json()["has_access"] is False

        # checkout without token
        r_noauth = requests.post(f"{API}/site/{TOKEN}/paywall/checkout",
                                 json={"origin_url": BASE}, timeout=20)
        assert r_noauth.status_code == 401

        # checkout as member returns Stripe url
        r_co = requests.post(f"{API}/site/{TOKEN}/paywall/checkout", headers=member_h,
                             json={"origin_url": BASE}, timeout=30)
        assert r_co.status_code == 200, r_co.text[:200]
        j = r_co.json()
        assert "checkout.stripe.com" in j["checkout_url"]
        sid = j["session_id"]

        # status stays pending
        r_st = requests.get(f"{API}/site/{TOKEN}/paywall/status/{sid}", timeout=20)
        assert r_st.status_code == 200
        assert r_st.json()["payment_status"] == "pending"

    def test_paid_members_shape(self, owner_h):
        r = owner_h.get(f"{API}/apps/{APP_ID}/paid-members", timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert "members" in j and "payments" in j and "paid" in j

    def test_anon_gate_no_content(self):
        r = requests.get(f"{API}/site/{TOKEN}/page/services", timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert j.get("requires_payment") is True
        # No blocks/content for anonymous visitor
        assert not j.get("blocks"), f"blocks leaked: {list(j.keys())}"


# ---------- live sync (poll after external create) ----------
class TestLiveSync:
    def test_new_booking_appears_in_list(self, owner_h):
        payload = {"name": "TEST_Sync Sam", "email": "sync.sam@example.com",
                   "date": "2026-09-10", "slot": "11:00", "duration_min": 30,
                   "service": "Sync", "notify": False}
        r = owner_h.post(f"{API}/site/{TOKEN}/admin/bookings", json=payload, timeout=20)
        assert r.status_code == 200
        sid = r.json()["booking"]["submission_id"]

        # list bookings via panel submissions
        found = False
        for _ in range(3):
            lr = owner_h.get(f"{API}/site/{TOKEN}/admin/submissions", timeout=20)
            if lr.status_code == 200:
                if any(s.get("submission_id") == sid for s in lr.json().get("submissions", [])):
                    found = True
                    break
            time.sleep(1)
        # cleanup
        owner_h.delete(f"{API}/site/{TOKEN}/admin/bookings/{sid}?notify_client=false", timeout=20)
        assert found, "created booking not reflected in submissions list"
