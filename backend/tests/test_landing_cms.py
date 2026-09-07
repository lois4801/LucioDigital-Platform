"""Landing CMS backend tests"""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"

DEFAULT_CARDS = [
    {"id": "card_ecom", "title": "E-commerce", "description": "Storefronts with featured products, offers and loyalty built in.", "image": "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=900&q=80"},
    {"id": "card_saas", "title": "SaaS dashboards", "description": "Data-dense product dashboards with billing and client portals.", "image": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=900&q=80"},
    {"id": "card_wellness", "title": "Wellness apps", "description": "Class schedules, trainers, memberships and free-trial funnels.", "image": "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=900&q=80"},
    {"id": "card_logistics", "title": "Logistics tools", "description": "Fleet, dispatch and freight quoting with live tracking.", "image": "https://images.unsplash.com/photo-1601584115197-04ecc0da31d7?w=900&q=80"},
]
DEFAULT_MARQUEE = ["Nexus", "Orbit", "Fleet", "Aura", "Ledger", "Studio", "Vanta", "Halo"]


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return s


@pytest.fixture(scope="module")
def visitor_session():
    return requests.Session()


@pytest.fixture(scope="module")
def nonadmin_session():
    s = requests.Session()
    email = f"TEST_nonadmin_{int(time.time())}@example.com"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "Pass1234!", "name": "NonAdmin"})
    assert r.status_code == 200, f"register failed: {r.text}"
    s._email = email
    return s


# ---- Public landing ----
def test_public_landing_no_auth(visitor_session):
    r = visitor_session.get(f"{API}/public/landing")
    assert r.status_code == 200
    data = r.json()
    assert "cards" in data and "marquee" in data and "texts" in data
    assert len(data["cards"]) >= 1
    assert "hero_caption_title" in data["texts"]


def test_put_landing_no_auth_rejected(visitor_session):
    r = visitor_session.put(f"{API}/admin/landing", json={"texts": {"hero_caption_title": "hack"}})
    assert r.status_code in (401, 403), r.text


# ---- Auth me ----
def test_admin_me_is_admin(admin_session):
    r = admin_session.get(f"{API}/auth/me")
    assert r.status_code == 200
    assert r.json().get("is_admin") is True


def test_nonadmin_me_not_admin(nonadmin_session):
    r = nonadmin_session.get(f"{API}/auth/me")
    assert r.status_code == 200
    assert r.json().get("is_admin") is False


def test_nonadmin_put_landing_forbidden(nonadmin_session):
    r = nonadmin_session.put(f"{API}/admin/landing", json={"texts": {"hero_caption_title": "hack"}})
    assert r.status_code == 403


# ---- Admin PUT flows ----
def test_admin_update_text_and_persist(admin_session, visitor_session):
    r = admin_session.put(f"{API}/admin/landing", json={"texts": {"hero_caption_title": "QA Title"}})
    assert r.status_code == 200, r.text
    assert r.json()["texts"]["hero_caption_title"] == "QA Title"
    r2 = visitor_session.get(f"{API}/public/landing")
    assert r2.json()["texts"]["hero_caption_title"] == "QA Title"


def test_admin_unknown_text_key_ignored(admin_session):
    r = admin_session.put(f"{API}/admin/landing", json={"texts": {"nonexistent_key_xyz": "ignored"}})
    assert r.status_code == 200
    assert "nonexistent_key_xyz" not in r.json()["texts"]


def test_admin_remove_one_card(admin_session, visitor_session):
    cur = visitor_session.get(f"{API}/public/landing").json()
    three = cur["cards"][:3]
    r = admin_session.put(f"{API}/admin/landing", json={"cards": three})
    assert r.status_code == 200
    assert len(r.json()["cards"]) == 3
    r2 = visitor_session.get(f"{API}/public/landing")
    assert len(r2.json()["cards"]) == 3


def test_admin_update_marquee(admin_session, visitor_session):
    new_m = ["Alpha", "Beta", "Gamma"]
    r = admin_session.put(f"{API}/admin/landing", json={"marquee": new_m})
    assert r.status_code == 200
    assert r.json()["marquee"] == new_m
    assert visitor_session.get(f"{API}/public/landing").json()["marquee"] == new_m


# ---- Restore defaults ----
def test_zzz_restore_defaults(admin_session, visitor_session):
    r = admin_session.put(f"{API}/admin/landing", json={
        "cards": DEFAULT_CARDS,
        "marquee": DEFAULT_MARQUEE,
        "texts": {"hero_caption_title": "B2B Success Analytics"},
    })
    assert r.status_code == 200
    data = visitor_session.get(f"{API}/public/landing").json()
    assert len(data["cards"]) == 4
    assert data["marquee"] == DEFAULT_MARQUEE
    assert data["texts"]["hero_caption_title"] == "B2B Success Analytics"
