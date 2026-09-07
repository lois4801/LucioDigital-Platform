"""v9 AI Lead Scoring - inbox auto-scoring + batch/single scoring endpoints."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
EMAIL = "jaybernabe@luciodigital.com"
PASSWORD = "Lucio2026!"

with open("/app/memory/nexus_id") as f:
    NEXUS_ID = f.read().strip()


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def preview_token(client):
    r = client.get(f"{BASE_URL}/api/apps/{NEXUS_ID}")
    assert r.status_code == 200, r.text
    tok = r.json().get("preview_token")
    assert tok, "Nexus preview token missing"
    # ensure preview is enabled
    return tok


def _wait_for_score(client, message_id, timeout=30):
    """Poll inbox until message has non-null score."""
    for _ in range(timeout):
        r = client.get(f"{BASE_URL}/api/apps/{NEXUS_ID}/inbox")
        assert r.status_code == 200
        for m in r.json()["messages"]:
            if m["message_id"] == message_id and m.get("score") is not None:
                return m, r.json()
        time.sleep(1)
    return None, None


def test_high_intent_contact_scored_hot(client, preview_token):
    """Post high-intent contact -> scored >=70, hot=True, intent=buy, sorted first."""
    # Fit lead to Nexus Commerce (e-commerce dashboard) business context
    body = {
        "name": "Priya Ramaswamy",
        "email": "priya@northwind-retail.com",
        "subject": "Enterprise plan - $95k budget, migrating from Shopify Plus in Q1",
        "message": ("Hi Nexus team, I'm Head of E-Commerce at Northwind Retail (12 stores, $40M GMV). "
                    "We need to migrate our Shopify Plus storefront to Nexus Commerce and centralize our order/inventory "
                    "dashboard across all channels. Approved budget is $80-95k for year one. Timeline: kickoff by "
                    "January 30, go-live by March 15. Please send your enterprise contract and schedule a demo this week. "
                    "I am the decision-maker.")
    }
    r = requests.post(f"{BASE_URL}/api/public/contact/{preview_token}", json=body)
    assert r.status_code == 200, r.text
    mid = r.json()["message_id"]

    msg, inbox = _wait_for_score(client, mid, timeout=35)
    assert msg is not None, f"Message {mid} was never scored within 35s"
    assert msg["score"] >= 70, f"Expected hot score >=70, got {msg['score']}"
    assert msg["hot"] is True
    assert msg.get("intent") == "buy", f"Expected intent=buy, got {msg.get('intent')}"
    assert isinstance(msg.get("score_reason"), str) and len(msg["score_reason"]) > 0

    # inbox response includes hot count >= 1
    assert inbox["hot"] >= 1

    # top of list should be a hot lead (sorted by hot desc, score desc)
    assert inbox["messages"][0]["hot"] is True


def test_low_intent_contact_scored_low(client, preview_token):
    """Post spammy/vague -> score <40, sorted below hot leads."""
    body = {"name": "test", "email": "test@test.tt", "subject": "hi", "message": "hello test"}
    r = requests.post(f"{BASE_URL}/api/public/contact/{preview_token}", json=body)
    assert r.status_code == 200, r.text
    mid = r.json()["message_id"]

    msg, inbox = _wait_for_score(client, mid, timeout=35)
    assert msg is not None
    assert msg["score"] < 40, f"Expected low score <40, got {msg['score']}"
    assert msg["hot"] is False

    # Find its position in the sorted list - should not be first (hot ones first)
    ids = [m["message_id"] for m in inbox["messages"]]
    pos = ids.index(mid)
    # any hot msg should appear before it
    hot_positions = [i for i, m in enumerate(inbox["messages"]) if m.get("hot")]
    if hot_positions:
        assert min(hot_positions) < pos, "Low-intent message should be sorted after hot leads"


def test_batch_score_endpoint(client):
    r = client.post(f"{BASE_URL}/api/apps/{NEXUS_ID}/inbox/score")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "scored" in data and "remaining" in data
    assert isinstance(data["scored"], int)
    assert isinstance(data["remaining"], int)


def test_rescore_single_message(client):
    # find any existing scored message
    r = client.get(f"{BASE_URL}/api/apps/{NEXUS_ID}/inbox")
    msgs = [m for m in r.json()["messages"] if m.get("score") is not None]
    assert msgs, "No scored messages to rescore"
    mid = msgs[0]["message_id"]
    r = client.post(f"{BASE_URL}/api/apps/{NEXUS_ID}/inbox/{mid}/score")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["message_id"] == mid
    assert body.get("score") is not None
    assert isinstance(body.get("score"), int)


def test_inbox_sort_hot_first_and_hot_count(client):
    r = client.get(f"{BASE_URL}/api/apps/{NEXUS_ID}/inbox")
    assert r.status_code == 200
    data = r.json()
    assert "hot" in data
    msgs = data["messages"]
    # all hot msgs must come before any non-hot
    seen_non_hot = False
    for m in msgs:
        if m.get("hot"):
            assert not seen_non_hot, "Found hot message after a non-hot one - sort broken"
        else:
            seen_non_hot = True
