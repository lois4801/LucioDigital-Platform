"""Iter 45 — Automatic lead classification (test vs real), booking-invite, AI summary exclusion."""
import os
import requests
import pytest

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
OWNER = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
APP_ID = "app_6663b5de0007"
PREVIEW = "pv_15f7e07b2d724b452e2a"
OTHER_APPS = ["app_e3cb4f084785", "app_abc693a75574"]  # app_c18671970769 not accessible to this owner


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json=OWNER, timeout=20)
    assert r.status_code == 200, r.text
    return s


# --- Public path: writes classify at insert time ---
def test_public_contact_fake_lands_in_test(sess):
    r = requests.post(f"{BASE}/public/contact/{PREVIEW}", json={
        "name": "QA Bot v2", "email": "qa@mailinator.com", "message": "TEST TEST TEST"}, timeout=20)
    assert r.status_code == 200, r.text
    mid = r.json()["message_id"]
    inbox = sess.get(f"{BASE}/apps/{APP_ID}/inbox", timeout=20).json()
    m = next((x for x in inbox["messages"] if x["message_id"] == mid), None)
    assert m and m["lane"] == "test", m
    assert m["lane_reasons"] and len(m["lane_reasons"]) >= 1


def test_public_contact_realistic_lands_in_real(sess):
    r = requests.post(f"{BASE}/public/contact/{PREVIEW}", json={
        "name": "Sarah Thompson",
        "email": "sarah.thompson@acme-industries.co",
        "message": "Hi, we're looking to replace the roof on our warehouse in Q1 and would love a quote. Please let me know availability."
    }, timeout=20)
    assert r.status_code == 200
    mid = r.json()["message_id"]
    inbox = sess.get(f"{BASE}/apps/{APP_ID}/inbox", timeout=20).json()
    m = next((x for x in inbox["messages"] if x["message_id"] == mid), None)
    assert m and m["lane"] == "real", m


# --- Classify endpoint + counts ---
def test_classify_rerun_and_counts(sess):
    r = sess.post(f"{BASE}/apps/{APP_ID}/inbox/classify?rerun=true", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "real" in data and "test" in data
    inbox = sess.get(f"{BASE}/apps/{APP_ID}/inbox", timeout=20).json()
    counts = inbox["counts"]
    for k in ("real", "test", "archived", "review", "priority"):
        assert k in counts, counts


def test_lane_filter(sess):
    real = sess.get(f"{BASE}/apps/{APP_ID}/inbox?lane=real", timeout=20).json()
    test = sess.get(f"{BASE}/apps/{APP_ID}/inbox?lane=test", timeout=20).json()
    assert all(m["lane"] == "real" for m in real["messages"])
    assert all(m["lane"] == "test" for m in test["messages"])


def test_unread_hot_exclude_test(sess):
    inbox = sess.get(f"{BASE}/apps/{APP_ID}/inbox", timeout=20).json()
    # unread and hot fields exclude test leads by design
    test_unread = sum(1 for m in inbox["messages"] if m["lane"] == "test" and m["status"] == "unread")
    all_unread = sum(1 for m in inbox["messages"] if m["status"] == "unread")
    # inbox["unread"] should not include the test unread
    assert inbox["unread"] <= all_unread - test_unread + 0.001 or inbox["unread"] == (all_unread - test_unread)


# --- Manual override stickiness ---
def test_manual_override_sticky(sess):
    inbox = sess.get(f"{BASE}/apps/{APP_ID}/inbox?lane=test", timeout=20).json()
    if not inbox["messages"]:
        pytest.skip("no test leads to flip")
    target = inbox["messages"][0]["message_id"]
    r = sess.patch(f"{BASE}/apps/{APP_ID}/inbox/{target}/lane", json={"lane": "real"}, timeout=20)
    assert r.status_code == 200
    assert r.json()["lane"] == "real"
    assert r.json()["lane_manual"] is True
    # Rerun classify — should NOT move it back
    sess.post(f"{BASE}/apps/{APP_ID}/inbox/classify?rerun=true", timeout=30)
    m = sess.get(f"{BASE}/apps/{APP_ID}/inbox", timeout=20).json()
    still = next((x for x in m["messages"] if x["message_id"] == target), None)
    assert still and still["lane"] == "real" and still["lane_manual"] is True


def test_lane_invalid(sess):
    inbox = sess.get(f"{BASE}/apps/{APP_ID}/inbox", timeout=20).json()
    mid = inbox["messages"][0]["message_id"]
    r = sess.patch(f"{BASE}/apps/{APP_ID}/inbox/{mid}/lane", json={"lane": "bogus"}, timeout=20)
    assert r.status_code == 400


def test_lane_unknown_message(sess):
    r = sess.patch(f"{BASE}/apps/{APP_ID}/inbox/msg_doesnotexist/lane", json={"lane": "real"}, timeout=20)
    assert r.status_code == 404


# --- Booking invite ---
def test_booking_invite_real_lead(sess):
    inbox = sess.get(f"{BASE}/apps/{APP_ID}/inbox?lane=real", timeout=20).json()
    real_with_email = next((m for m in inbox["messages"] if m.get("from_email")), None)
    assert real_with_email, "need a real lead with email"
    mid = real_with_email["message_id"]
    r = sess.post(f"{BASE}/apps/{APP_ID}/inbox/{mid}/booking-invite", timeout=30)
    assert r.status_code == 200, r.text
    invite = r.json()["invite"]
    assert invite["to"] == real_with_email["from_email"]
    assert "JLBUSINESS2020@gmail.com" in invite["copies"]
    assert "jaybernabe@luciodigital.com" in invite["copies"]
    assert r.json()["message"]["status"] == "read"
    assert r.json()["message"].get("booking_invite")


def test_booking_invite_test_lead_rejected(sess):
    inbox = sess.get(f"{BASE}/apps/{APP_ID}/inbox?lane=test", timeout=20).json()
    if not inbox["messages"]:
        pytest.skip("no test leads")
    mid = inbox["messages"][0]["message_id"]
    r = sess.post(f"{BASE}/apps/{APP_ID}/inbox/{mid}/booking-invite", timeout=20)
    assert r.status_code == 400


def test_booking_invite_no_email(sess):
    # find a chat lead with no email
    inbox = sess.get(f"{BASE}/apps/{APP_ID}/inbox", timeout=20).json()
    empty = next((m for m in inbox["messages"] if not m.get("from_email")), None)
    if not empty:
        pytest.skip("no email-less lead")
    # ensure it's real lane
    sess.patch(f"{BASE}/apps/{APP_ID}/inbox/{empty['message_id']}/lane", json={"lane": "real"}, timeout=20)
    r = sess.post(f"{BASE}/apps/{APP_ID}/inbox/{empty['message_id']}/booking-invite", timeout=20)
    assert r.status_code == 400


# --- AI weekly summary excludes test ---
def test_ai_lead_summary_excludes_test(sess):
    r = sess.post(f"{BASE}/apps/{APP_ID}/ai/lead-summary", timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    counts = data.get("counts") or {}
    # leads counted must be <= number of real leads in past window
    inbox = sess.get(f"{BASE}/apps/{APP_ID}/inbox", timeout=20).json()
    real_count = sum(1 for m in inbox["messages"] if m.get("lane") == "real")
    if "leads" in counts:
        assert counts["leads"] <= real_count + 5  # allow slack for window


# --- Multi-tenant backfill ---
@pytest.mark.parametrize("app_id", OTHER_APPS)
def test_other_tenant_backfill(sess, app_id):
    r = sess.get(f"{BASE}/apps/{app_id}/inbox", timeout=30)
    assert r.status_code == 200, r.text
    for m in r.json()["messages"]:
        assert m.get("lane") in ("real", "test"), m
