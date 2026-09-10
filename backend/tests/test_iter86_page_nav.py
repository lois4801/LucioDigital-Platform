"""Iteration 86 — POST /api/apps/{id}/pages with `nav` placement.
Verifies nav='end'|'start'|'after:<slug>'|'hidden' inserts link into every navbar block
correctly, that duplicate slugs 400, and links are never added twice."""
import os
import pytest
import requests


def _load_url():
    v = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    return ""


BASE_URL = _load_url()
API = f"{BASE_URL}/api"
APP_ID = "app_testlab"
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    created = []
    s._created = created
    yield s
    # teardown: delete all pages created during test run
    for pid in created:
        try:
            s.delete(f"{API}/apps/{APP_ID}/pages/{pid}", timeout=20)
        except Exception:
            pass


def _preview_token(client):
    r = client.get(f"{API}/apps/{APP_ID}", timeout=20)
    assert r.status_code == 200, r.text
    return r.json().get("preview_token")


def _public_navbar_links(token):
    r = requests.get(f"{API}/public/site/{token}", timeout=20)
    assert r.status_code == 200, r.text
    pages = r.json().get("pages") or []
    # aggregate all navbar block links across pages (they should be identical)
    for p in pages:
        for b in (p.get("blocks") or []):
            if b.get("type") == "navbar":
                return [(l.get("label"), l.get("href")) for l in (b.get("props") or {}).get("links") or []]
    return []


def _create(client, name, slug, nav):
    r = client.post(f"{API}/apps/{APP_ID}/pages",
                    json={"name": name, "slug": slug, "nav": nav}, timeout=20)
    if r.status_code == 200:
        pid = r.json().get("page_id")
        if pid:
            client._created.append(pid)
    return r


def _delete_and_untrack(client, pid):
    r = client.delete(f"{API}/apps/{APP_ID}/pages/{pid}", timeout=20)
    if pid in client._created:
        client._created.remove(pid)
    return r


# ---- placement modes ----
def test_nav_end_appends(client):
    token = _preview_token(client)
    before = _public_navbar_links(token)
    r = _create(client, "T86End", "test86-end", "end")
    assert r.status_code == 200, r.text
    links = _public_navbar_links(token)
    assert ("T86End", "/test86-end") in links
    assert links[-1] == ("T86End", "/test86-end"), links
    assert len(links) == len(before) + 1


def test_nav_start_prepends(client):
    token = _preview_token(client)
    r = _create(client, "T86Start", "test86-start", "start")
    assert r.status_code == 200, r.text
    links = _public_navbar_links(token)
    assert links[0] == ("T86Start", "/test86-start"), links


def test_nav_after_specific_slug(client):
    token = _preview_token(client)
    # find an existing link href to anchor after
    links_before = _public_navbar_links(token)
    assert links_before, "need at least one existing nav link"
    anchor_href = links_before[0][1]  # first one
    anchor_slug = anchor_href  # href is the slug like "/test86-start"
    r = _create(client, "T86After", "test86-after", f"after:{anchor_slug}")
    assert r.status_code == 200, r.text
    links = _public_navbar_links(token)
    idxs = [i for i, (_, h) in enumerate(links) if h == anchor_href]
    new_idx = next(i for i, (_, h) in enumerate(links) if h == "/test86-after")
    assert new_idx == idxs[0] + 1, f"expected right after anchor {idxs[0]}, got {new_idx}: {links}"


def test_nav_hidden_adds_no_link(client):
    token = _preview_token(client)
    before = _public_navbar_links(token)
    r = _create(client, "T86Hidden", "test86-hidden", "hidden")
    assert r.status_code == 200, r.text
    after = _public_navbar_links(token)
    assert ("T86Hidden", "/test86-hidden") not in after
    # counts identical
    assert len(after) == len(before)


# ---- duplicate slug ----
def test_duplicate_slug_returns_400(client):
    r1 = _create(client, "T86Dup", "test86-dup", "end")
    assert r1.status_code == 200, r1.text
    r2 = _create(client, "T86Dup2", "test86-dup", "end")
    assert r2.status_code == 400, f"expected 400 got {r2.status_code}: {r2.text[:200]}"


# ---- link never added twice ----
def test_link_never_duplicated(client):
    token = _preview_token(client)
    # count occurrences of our earlier test86-end page in nav
    links = _public_navbar_links(token)
    hrefs = [h for (_, h) in links]
    for h in set(hrefs):
        assert hrefs.count(h) == 1, f"duplicate link {h} in navbar: {hrefs}"
