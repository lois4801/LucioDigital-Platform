"""Iter 49: master /leads inbox lanes, manual override, edit_request lane pinning."""
import os
import time
import pytest
import requests

def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
        except OSError:
            pass
    assert url, "REACT_APP_BACKEND_URL not set"
    return url.rstrip("/")

BASE_URL = _load_backend_url()

OWNER = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
CLIENT = {"email": "client.editor@example.com", "password": "ClientEdit2026!"}
CLIENT_APP = "app_6663b5de0007"


@pytest.fixture(scope="module")
def owner_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=OWNER, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def client_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=CLIENT, timeout=15)
    assert r.status_code == 200, r.text
    return s


# ==== global /api/inbox ====
class TestGlobalInbox:
    def test_returns_lane_on_every_message(self, owner_session):
        r = owner_session.get(f"{BASE_URL}/api/inbox", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "messages" in data and "unread" in data
        msgs = data["messages"]
        assert len(msgs) > 0
        missing_lane = [m["message_id"] for m in msgs if "lane" not in m or m["lane"] not in ("real", "test")]
        assert not missing_lane, f"messages missing lane: {missing_lane[:5]}"

    def test_unread_excludes_test_lane(self, owner_session):
        r = owner_session.get(f"{BASE_URL}/api/inbox", timeout=15).json()
        real_unread = sum(1 for m in r["messages"] if m.get("status") == "unread" and m.get("lane") != "test")
        assert r["unread"] == real_unread, f"unread {r['unread']} != real-lane unread {real_unread}"

    def test_lanes_populated_across_tenants(self, owner_session):
        r = owner_session.get(f"{BASE_URL}/api/inbox", timeout=15).json()
        app_ids = {m["app_id"] for m in r["messages"]}
        assert len(app_ids) >= 2, "expected messages from multiple tenants"


# ==== manual lane override ====
class TestManualLaneOverride:
    def test_move_lead_between_lanes_persists(self, owner_session):
        r = owner_session.get(f"{BASE_URL}/api/inbox", timeout=15).json()
        # pick a non-edit-request message
        target = next((m for m in r["messages"] if m.get("kind") != "edit_request"), None)
        assert target, "no non-edit-request message found"
        original = target.get("lane", "real")
        flipped = "test" if original == "real" else "real"

        # flip
        r1 = owner_session.patch(
            f"{BASE_URL}/api/apps/{target['app_id']}/inbox/{target['message_id']}/lane",
            json={"lane": flipped}, timeout=15,
        )
        assert r1.status_code == 200, r1.text
        assert r1.json()["lane"] == flipped
        assert r1.json().get("lane_manual") is True

        # persists via global inbox
        r2 = owner_session.get(f"{BASE_URL}/api/inbox", timeout=15).json()
        after = next(m for m in r2["messages"] if m["message_id"] == target["message_id"])
        assert after["lane"] == flipped

        # restore
        r3 = owner_session.patch(
            f"{BASE_URL}/api/apps/{target['app_id']}/inbox/{target['message_id']}/lane",
            json={"lane": original}, timeout=15,
        )
        assert r3.status_code == 200
        assert r3.json()["lane"] == original

    def test_invalid_lane_rejected(self, owner_session):
        r = owner_session.get(f"{BASE_URL}/api/inbox", timeout=15).json()
        m = r["messages"][0]
        bad = owner_session.patch(
            f"{BASE_URL}/api/apps/{m['app_id']}/inbox/{m['message_id']}/lane",
            json={"lane": "spam"}, timeout=15,
        )
        assert bad.status_code == 400


# ==== edit_request pinned to real ====
class TestEditRequestLane:
    def test_client_edit_request_lands_in_real_lane(self, client_session, owner_session):
        # find a locked page for the client tenant
        pages = owner_session.get(f"{BASE_URL}/api/apps/{CLIENT_APP}/pages", timeout=15).json()
        # pages may be dict or list
        page_list = pages if isinstance(pages, list) else pages.get("pages", [])
        locked = next((p for p in page_list if p.get("locked")), None)
        if not locked:
            # try lock the first page as owner
            first = page_list[0]
            lk = owner_session.post(
                f"{BASE_URL}/api/apps/{CLIENT_APP}/locks/item",
                json={"kind": "page", "item_id": first["page_id"], "locked": True}, timeout=15,
            )
            assert lk.status_code == 200, lk.text
            locked = first

        payload = {"description": "This is a test test test change request to see if lane is pinned real"}
        r = client_session.post(
            f"{BASE_URL}/api/apps/{CLIENT_APP}/pages/{locked['page_id']}/edit-request",
            json=payload, timeout=20,
        )
        assert r.status_code == 200, r.text
        msg = r.json()
        assert msg["kind"] == "edit_request"
        assert msg["lane"] == "real", f"expected real, got {msg['lane']}"

        # confirm via master inbox
        time.sleep(1)
        gi = owner_session.get(f"{BASE_URL}/api/inbox", timeout=15).json()
        found = next((m for m in gi["messages"] if m["message_id"] == msg["message_id"]), None)
        assert found is not None
        assert found["lane"] == "real"

    def test_generic_edit_request_also_real(self, client_session):
        # try creating a generic item edit-request; if the kind list rejects, skip
        r = client_session.post(
            f"{BASE_URL}/api/apps/{CLIENT_APP}/edit-request",
            json={"kind": "page", "item_id": "nope", "item_name": "TEST edit", "description": "test test test"},
            timeout=15,
        )
        # kind 'page' is valid; even if page_id doesn't exist, the endpoint just creates a message
        assert r.status_code == 200, r.text
        assert r.json()["lane"] == "real"


# ==== per-tenant inbox regression ====
class TestTenantInboxRegression:
    def test_tenant_inbox_counts(self, owner_session):
        r = owner_session.get(f"{BASE_URL}/api/apps/{CLIENT_APP}/inbox", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert set(["real", "test", "archived", "review", "priority"]).issubset(data["counts"].keys())
        for m in data["messages"]:
            assert m.get("lane") in ("real", "test")
