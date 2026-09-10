"""Iter93: Ribbon Live Line (review/offer/figure sources) + Client Edit Log.

Covers:
- GET /api/apps/{id}/marquee returns `live` and `figures`
- PUT with top_source=review => public site returns newest review quote as top_text, top_live=review
- PUT with bottom_source=figure + bottom_figure=1 => uppercase formatted metric, bottom_live=figure
- Unknown source => 400
- Offer window: (a) no dates -> shows, (b) offer_from in future -> static fallback, (c) offer_to in past -> static fallback, blank offer_text -> static
- Per-page override with its own top_source resolves per page in public site
- Edit log: entries with area labels, actor, role, is_you, newest-first; ?mine=true filters
- Non-content activity kinds excluded
"""
import os
from datetime import date, timedelta
from pathlib import Path

import pytest
import requests


def _load_frontend_url():
    env = Path("/app/frontend/.env").read_text()
    for line in env.splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip()
    return None


BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_url()).rstrip("/")
API = f"{BASE}/api"
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"
APP = "app_testlab"
TEST_SLUG = "/app-showcase-pro-4"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    yield s
    # Always leave master workspace clean
    try:
        s.delete(f"{API}/apps/{APP}/marquee/pages{TEST_SLUG}")
    except Exception:
        pass
    try:
        s.post(f"{API}/apps/{APP}/marquee/reset")
    except Exception:
        pass


@pytest.fixture(scope="module")
def preview_token(admin):
    apps = admin.get(f"{API}/apps").json()
    lst = apps if isinstance(apps, list) else apps.get("apps", [])
    tok = next((a.get("preview_token") for a in lst if a.get("app_id") == APP), None)
    assert tok
    return tok


def _public(tok):
    r = requests.get(f"{API}/public/site/{tok}")
    assert r.status_code == 200, r.text
    d = r.json()
    return (d.get("app") or d).get("marquee") or {}


# ── GET returns live + figures ────────────────────────────────────────
def test_get_marquee_returns_live_and_figures(admin):
    r = admin.get(f"{API}/apps/{APP}/marquee")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "live" in d and isinstance(d["live"], dict)
    for k in ("top_text", "bottom_text", "top_live", "bottom_live"):
        assert k in d["live"], f"missing {k} in live: {list(d['live'].keys())}"
    assert "figures" in d and isinstance(d["figures"], list)
    if d["figures"]:
        f = d["figures"][0]
        for k in ("index", "label", "value"):
            assert k in f


# ── Unknown source => 400 ─────────────────────────────────────────────
def test_unknown_source_returns_400(admin):
    r = admin.put(f"{API}/apps/{APP}/marquee", json={"top_source": "bogus"})
    assert r.status_code == 400, r.text


# ── review source resolves on public site ─────────────────────────────
def test_review_source_resolves_public(admin, preview_token):
    r = admin.put(f"{API}/apps/{APP}/marquee", json={"top_source": "review"})
    assert r.status_code == 200, r.text
    mq = _public(preview_token)
    assert mq.get("top_live") == "review", f"expected top_live=review, got {mq.get('top_live')} text={mq.get('top_text')}"
    # top_text should contain a quote-ish char (curly or straight)
    txt = mq.get("top_text") or ""
    assert "“" in txt or '"' in txt or txt, "top_text should be non-empty review quote"


# ── figure source resolves + uppercase formatting ─────────────────────
def test_figure_source_resolves_uppercase(admin, preview_token):
    # verify metric 1 exists
    d = admin.get(f"{API}/apps/{APP}/marquee").json()
    figures = d.get("figures") or []
    if len(figures) < 2:
        pytest.skip("not enough metrics on testlab")
    r = admin.put(f"{API}/apps/{APP}/marquee", json={"bottom_source": "figure", "bottom_figure": 1})
    assert r.status_code == 200, r.text
    mq = _public(preview_token)
    assert mq.get("bottom_live") == "figure", f"expected bottom_live=figure, got {mq.get('bottom_live')}"
    txt = mq.get("bottom_text") or ""
    assert txt == txt.upper(), f"figure text should be upper: {txt}"
    assert len(txt) > 0


# ── Offer window ──────────────────────────────────────────────────────
def test_offer_no_dates_shows(admin, preview_token):
    admin.post(f"{API}/apps/{APP}/marquee/reset")
    r = admin.put(f"{API}/apps/{APP}/marquee", json={
        "top_source": "offer", "offer_text": "SPRING SALE 20% OFF",
        "offer_from": "", "offer_to": ""})
    assert r.status_code == 200, r.text
    mq = _public(preview_token)
    assert mq.get("top_live") == "offer", f"got {mq.get('top_live')} text={mq.get('top_text')}"
    assert "SPRING SALE" in (mq.get("top_text") or "")


def test_offer_future_from_falls_back_static(admin, preview_token):
    future = (date.today() + timedelta(days=30)).isoformat()
    r = admin.put(f"{API}/apps/{APP}/marquee", json={
        "top_source": "offer", "offer_text": "FUTURE OFFER", "offer_from": future})
    assert r.status_code == 200, r.text
    mq = _public(preview_token)
    assert mq.get("top_live") == "static", f"expected static fallback, got {mq.get('top_live')}"
    assert "FUTURE OFFER" not in (mq.get("top_text") or "")


def test_offer_past_to_falls_back_static(admin, preview_token):
    past = (date.today() - timedelta(days=30)).isoformat()
    r = admin.put(f"{API}/apps/{APP}/marquee", json={
        "top_source": "offer", "offer_text": "OLD OFFER", "offer_from": "", "offer_to": past})
    assert r.status_code == 200, r.text
    mq = _public(preview_token)
    assert mq.get("top_live") == "static"


def test_offer_blank_text_falls_back_static(admin, preview_token):
    r = admin.put(f"{API}/apps/{APP}/marquee", json={
        "top_source": "offer", "offer_text": "", "offer_from": "", "offer_to": ""})
    assert r.status_code == 200, r.text
    mq = _public(preview_token)
    assert mq.get("top_live") == "static"
    # cleanup after offer tests
    admin.post(f"{API}/apps/{APP}/marquee/reset")


# ── Per-page override with its own source ─────────────────────────────
def test_per_page_source_resolves(admin, preview_token):
    # site-wide static, page-level figure
    admin.post(f"{API}/apps/{APP}/marquee/reset")
    d = admin.get(f"{API}/apps/{APP}/marquee").json()
    if len(d.get("figures") or []) < 1:
        pytest.skip("no metrics")
    r = admin.put(f"{API}/apps/{APP}/marquee/pages{TEST_SLUG}",
                  json={"top_source": "figure", "top_figure": 0})
    assert r.status_code == 200, r.text
    site = requests.get(f"{API}/public/site/{preview_token}").json()
    mq = (site.get("app") or site).get("marquee") or {}
    pages = mq.get("pages") or {}
    pg = pages.get(TEST_SLUG) or {}
    assert pg.get("top_live") == "figure", f"page top_live expected figure, got {pg.get('top_live')} pg={pg}"
    # site-wide untouched
    assert mq.get("top_live") in (None, "static")
    admin.delete(f"{API}/apps/{APP}/marquee/pages{TEST_SLUG}")


# ── Edit log ──────────────────────────────────────────────────────────
def test_edit_log_shape_and_ordering(admin):
    # generate one entry
    admin.post(f"{API}/apps/{APP}/marquee/reset")
    r = admin.get(f"{API}/apps/{APP}/edit-log")
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("entries", "areas", "count"):
        assert k in d
    assert isinstance(d["entries"], list)
    assert isinstance(d["areas"], list)
    if d["entries"]:
        first = d["entries"][0]
        for k in ("kind", "area", "message", "created_at", "actor", "role", "is_you"):
            assert k in first, f"missing {k} in entry: {first}"
        # areas should include known labels
        known = {"Text ribbon", "Reviews", "Figures & charts", "Design & motion", "Pages", "Content",
                 "Onboarding", "Animations", "Branding", "Files & media", "Forms", "Domain", "Change requests"}
        assert set(d["areas"]).issubset(known | {""}), f"unknown area label: {d['areas']}"
        # newest first
        times = [e.get("created_at") for e in d["entries"] if e.get("created_at")]
        assert times == sorted(times, reverse=True), "entries not newest-first"


def test_edit_log_mine_filter(admin):
    all_r = admin.get(f"{API}/apps/{APP}/edit-log").json()
    mine_r = admin.get(f"{API}/apps/{APP}/edit-log?mine=true").json()
    assert mine_r["count"] <= all_r["count"]
    for e in mine_r["entries"]:
        assert e["is_you"] is True


def test_edit_log_excludes_non_content(admin):
    r = admin.get(f"{API}/apps/{APP}/edit-log?limit=60")
    assert r.status_code == 200, f"edit-log crashed: {r.status_code} {r.text[:200]}"
    d = r.json()
    for e in d["entries"]:
        # every returned kind must map to a non-empty area label
        assert e["area"], f"non-content kind leaked: {e.get('kind')}"


def test_edit_log_high_limit_does_not_crash(admin):
    """Regression: some legacy activity_logs rows have user_id stored as a dict,
    which crashes the set comprehension when the query pulls them in."""
    r = admin.get(f"{API}/apps/{APP}/edit-log?limit=200")
    assert r.status_code == 200, (
        f"edit-log crashes on limit=200 (legacy dict user_id in activity_logs): "
        f"{r.status_code} {r.text[:200]}"
    )


def test_edit_log_role_agency_for_owner(admin):
    d = admin.get(f"{API}/apps/{APP}/edit-log?mine=true").json()
    # admin owns app_testlab, so their own entries should be role=agency
    for e in d["entries"]:
        assert e["role"] == "agency", f"expected agency for owner, got {e}"
