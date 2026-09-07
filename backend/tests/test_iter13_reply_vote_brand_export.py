"""Iteration 13 backend tests: Lead reply/AI-draft, look voting, brand preservation, export starter."""
import io
import os
import time
import zipfile
import pytest
import requests
from dotenv import load_dotenv
load_dotenv("/app/frontend/.env")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
EMAIL = "jaybernabe@luciodigital.com"
PASSWORD = "Lucio2026!"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def fresh_app(sess):
    name = f"TEST_iter13_{int(time.time())}"
    r = sess.post(f"{BASE}/apps", json={"name": name, "industry": "Plumbing", "description": "Test"})
    assert r.status_code in (200, 201), r.text
    app_id = r.json()["app_id"]
    yield app_id, name
    try:
        sess.delete(f"{BASE}/apps/{app_id}")
    except Exception:
        pass


# =====  Lead reply / AI-draft  =====
def test_ai_draft_and_reply(sess, fresh_app):
    app_id, _ = fresh_app
    # Need preview_token so /public/contact works
    a = sess.get(f"{BASE}/apps/{app_id}").json()
    token = a.get("preview_token")
    if not token:
        # rebuild premium to get token
        sess.post(f"{BASE}/apps/{app_id}/site/premium-rebuild", json={})
        a = sess.get(f"{BASE}/apps/{app_id}").json()
        token = a["preview_token"]
    # Create a message via public contact
    r = sess.post(f"{BASE}/public/contact/{token}", json={
        "name": "Jane Doe", "email": "jane@example.com",
        "subject": "Need pipe repair", "message": "My kitchen sink is leaking, can you quote me?"
    })
    assert r.status_code == 200, r.text
    msg_id = r.json()["message_id"]
    # AI draft
    r = sess.post(f"{BASE}/apps/{app_id}/inbox/{msg_id}/ai-draft")
    assert r.status_code == 200, r.text
    draft = r.json().get("draft", "")
    assert isinstance(draft, str) and len(draft.strip()) > 20, f"Draft empty/short: {draft!r}"
    # Reply
    r = sess.post(f"{BASE}/apps/{app_id}/inbox/{msg_id}/reply", json={"body": draft[:500]})
    assert r.status_code == 200, r.text
    msg = r.json()
    assert msg["status"] == "read"
    assert len(msg.get("replies", [])) >= 1
    delivery = msg["replies"][-1]["delivery"]
    assert delivery in ("in_app", "email_sent", "email_queued"), delivery


# =====  Look voting  =====
def test_look_options_and_vote(sess, fresh_app):
    app_id, name = fresh_app
    r = sess.get(f"{BASE}/apps/{app_id}/site/look-options")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "current" in data and "options" in data
    assert len(data["options"]) == 5
    keys_required = {"key", "brand", "sample", "industry", "mood", "primary", "secondary", "hero", "title", "bg", "font"}
    for o in data["options"]:
        assert keys_required.issubset(o.keys()), f"Missing keys in option: {o}"
        assert o["brand"] == name, f"Brand should be tenant app name, got {o['brand']}"
    assert data["options"][0]["key"] == data["current"], "First option should equal current niche"

    # Unknown niche
    r = sess.post(f"{BASE}/apps/{app_id}/site/look-vote", json={"niche": "not-a-real-niche"})
    assert r.status_code == 404

    # Valid vote — pick 2nd option
    vote_niche = data["options"][1]["key"]
    r = sess.post(f"{BASE}/apps/{app_id}/site/look-vote", json={"niche": vote_niche, "note": "Love this"})
    assert r.status_code == 200, r.text
    vote = r.json()
    assert vote["niche"] == vote_niche
    assert vote["applied"] is False

    # Notifications should include look.voted
    n = sess.get(f"{BASE}/notifications").json()
    items = n if isinstance(n, list) else n.get("items", [])
    found = any((it.get("type") == "look.voted" or it.get("action") == "look.voted" or it.get("kind") == "look.voted") for it in items)
    assert found, f"look.voted not found in notifications: {items[:3]}"

    # premium-rebuild with voted niche → applied True
    r = sess.post(f"{BASE}/apps/{app_id}/site/premium-rebuild", json={"niche": vote_niche})
    assert r.status_code == 200, r.text
    a = sess.get(f"{BASE}/apps/{app_id}").json()
    assert a.get("look_vote", {}).get("applied") is True


# =====  Brand preservation  =====
def test_brand_preservation_flow(sess):
    name = "Acme Plumbing Co"
    r = sess.post(f"{BASE}/apps", json={"name": name, "industry": "Plumbing", "description": "Test brand"})
    assert r.status_code in (200, 201), r.text
    app_id = r.json()["app_id"]
    try:
        # First find the seed Home page and patch its contact block BEFORE premium-rebuild
        pages0 = sess.get(f"{BASE}/apps/{app_id}/pages").json()
        home0 = pages0[0]
        blocks0 = list(home0["blocks"])
        patched_any = False
        for b in blocks0:
            if b.get("type") == "contact":
                b["props"]["email"] = "owner@acmeplumbing.com"
                b["props"]["phone"] = "+1 555 0100"
                b["props"]["address"] = "12 Main St"
                patched_any = True
        assert patched_any, "No contact block in seed page"
        r = sess.patch(f"{BASE}/apps/{app_id}/pages/{home0['page_id']}", json={"blocks": blocks0})
        assert r.status_code == 200, r.text

        # premium-rebuild empty body
        r = sess.post(f"{BASE}/apps/{app_id}/site/premium-rebuild", json={})
        assert r.status_code == 200, r.text
        rb = r.json()
        assert "name" in rb.get("preserved", {}), f"preserved should include name: {rb}"
        assert rb["preserved"]["name"] == name

        # Check navbar brand
        pages = sess.get(f"{BASE}/apps/{app_id}/pages").json()
        home = next(p for p in pages if p["slug"] == "/")
        nav = next(b for b in home["blocks"] if b["type"] == "navbar")
        assert nav["props"]["brand"] == name, f"Navbar brand mismatch: {nav['props']['brand']}"
        assert nav["props"]["brand"] != "Summit Air & Heat"

        # niche-preview legal — should preserve our patched contact info
        r = sess.post(f"{BASE}/apps/{app_id}/site/niche-preview", json={"niche": "legal"})
        assert r.status_code == 200, r.text
        p = r.json()
        preserved = p["preserved"]
        assert preserved.get("email") == "owner@acmeplumbing.com"
        assert preserved.get("phone") == "+1 555 0100"
        assert preserved.get("address") == "12 Main St"
        assert preserved.get("name") == name
        # Contact block + footer in preview pages use these
        preview_pages = p["pages"]
        found_contact = False
        for pg in preview_pages:
            for blk in pg["blocks"]:
                if blk["type"] == "navbar":
                    assert blk["props"]["brand"] == name
                if blk["type"] == "contact" and blk["props"].get("email") == "owner@acmeplumbing.com":
                    found_contact = True
                    assert blk["props"]["phone"] == "+1 555 0100"
        assert found_contact, "Contact block with preserved email not found"

        # Apply legal then preview restaurant — sample email must not appear
        sess.post(f"{BASE}/apps/{app_id}/site/premium-rebuild", json={"niche": "legal"})
        r = sess.post(f"{BASE}/apps/{app_id}/site/niche-preview", json={"niche": "restaurant"})
        assert r.status_code == 200, r.text
        p2 = r.json()
        preserved2 = p2["preserved"]
        # None of the preserved values should be sample pack values like hello@emberandoak.ca
        for v in preserved2.values():
            if isinstance(v, str):
                assert "emberandoak" not in v.lower(), f"Sample value leaked into preserved: {v}"
        # Preserved name still equals tenant app name
        assert preserved2.get("name") == name
    finally:
        sess.delete(f"{BASE}/apps/{app_id}")


# =====  Export starter  =====
def test_export_source_has_light_and_toggle(sess):
    name = f"TEST_iter13_export_{int(time.time())}"
    r = sess.post(f"{BASE}/apps", json={"name": name, "industry": "Construction"})
    assert r.status_code in (200, 201), r.text
    app_id = r.json()["app_id"]
    try:
        # Apply construction template (gives app_spec)
        r = sess.post(f"{BASE}/apps/{app_id}/templates/construction/apply")
        assert r.status_code == 200, r.text
        # Export
        r = sess.get(f"{BASE}/apps/{app_id}/export/source")
        assert r.status_code == 200, r.text
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = z.namelist()

        def find(suffix):
            hits = [n for n in names if n.endswith(suffix)]
            assert hits, f"Missing {suffix} in export: {names[:20]}"
            return z.read(hits[0]).decode()

        html = find("frontend/public/index.html")
        assert "class='light'" in html or 'class="light"' in html, "index.html missing light class"
        app_jsx = find("frontend/src/App.jsx")
        assert "setDark" in app_jsx, "App.jsx missing setDark"
        assert "onClick" in app_jsx and ("Dark mode" in app_jsx or "Light mode" in app_jsx), "App.jsx missing toggle button"
        css = find("frontend/src/styles.css")
        assert ".dark{" in css, ".dark{ selector missing in styles.css"
        assert ".reveal" in css, ".reveal missing in styles.css"
    finally:
        sess.delete(f"{BASE}/apps/{app_id}")
