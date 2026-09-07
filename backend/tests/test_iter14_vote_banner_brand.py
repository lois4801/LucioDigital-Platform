"""Iter14: retest banner hide + brand placeholder handling."""
import os, requests, pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
EMAIL = "jaybernabe@luciodigital.com"
PWD = "Lucio2026!"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PWD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture()
def app_id(sess):
    r = sess.post(f"{BASE_URL}/api/apps", json={"name": "TEST_iter14 Retest Co", "industry": "Legal", "kind": "website"})
    assert r.status_code in (200, 201), r.text
    aid = r.json()["app_id"]
    yield aid
    sess.delete(f"{BASE_URL}/api/apps/{aid}")


def test_vote_preview_apply_flow(sess, app_id):
    # 1. Cast look-vote for finance
    r = sess.post(f"{BASE_URL}/api/apps/{app_id}/site/look-vote", json={"niche": "finance"})
    assert r.status_code == 200, r.text

    # 2. Preview finance — preserved should NOT contain hello@example.com; pages[0].blocks[0] (navbar) must NOT have null logo
    r = sess.post(f"{BASE_URL}/api/apps/{app_id}/site/niche-preview", json={"niche": "finance"})
    assert r.status_code == 200, r.text
    body = r.json()
    preserved = body.get("preserved", {})
    # preserved may contain name (from app.name) — but no example.com
    for k, v in preserved.items():
        assert "example.com" not in str(v).lower(), f"placeholder leaked into preserved.{k}={v}"
    assert preserved.get("name") == "TEST_iter14 Retest Co"
    # No email/phone/address in preserved (fresh app has none real)
    assert "email" not in preserved or preserved["email"] is None
    # navbar block: 'logo' key absent OR non-null
    navbar = body["pages"][0]["blocks"][0]
    assert navbar["type"] == "navbar"
    props = navbar.get("props", {})
    if "logo" in props:
        assert props["logo"] is not None, "navbar.props.logo must never be null"

    # 3. Premium rebuild — look_vote.applied becomes True
    r = sess.post(f"{BASE_URL}/api/apps/{app_id}/site/premium-rebuild", json={"niche": "finance"})
    assert r.status_code == 200, r.text

    r = sess.get(f"{BASE_URL}/api/apps/{app_id}")
    assert r.status_code == 200
    doc = r.json()
    assert doc.get("look_vote", {}).get("applied") is True
    assert doc.get("site_niche") == "finance"


def test_default_contact_placeholder_not_preserved(sess, app_id):
    """Default seed contact block uses hello@example.com — must be filtered out in preserved."""
    r = sess.post(f"{BASE_URL}/api/apps/{app_id}/site/niche-preview", json={"niche": "finance"})
    assert r.status_code == 200
    preserved = r.json().get("preserved", {})
    assert not any("example.com" in str(v).lower() for v in preserved.values())
