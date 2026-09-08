"""Iteration 52 — Featured toggle + showcase ordering."""
import os
import time
import requests
import pytest

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASS = "Lucio2026!"

# The 4 admin-owned tenants from test_credentials.md
NORTHWIND = "app_6663b5de0007"
NEXUS = "app_1cb6f2b89eb6"
AURA = "app_abc693a75574"
STUDIO = "app_e3cb4f084785"
ALL = [NORTHWIND, NEXUS, AURA, STUDIO]


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module", autouse=True)
def restore_state(admin):
    """Snapshot featured/order state and restore afterwards.
    Review-request says: leave at least one tenant starred at the end.
    """
    apps = admin.get(f"{BASE}/api/apps").json()
    apps = apps if isinstance(apps, list) else apps.get("apps", [])
    snap = {a["app_id"]: (bool(a.get("featured")), a.get("showcase_order", 0))
            for a in apps if a["app_id"] in ALL}
    yield
    # Unstar all first
    for aid in ALL:
        admin.patch(f"{BASE}/api/apps/{aid}/showcase", json={"featured": False})
    # Restore prior featured tenants in prior order
    prev_featured = sorted([aid for aid, (f, _) in snap.items() if f],
                           key=lambda aid: snap[aid][1])
    for aid in prev_featured:
        admin.patch(f"{BASE}/api/apps/{aid}/showcase", json={"featured": True})
    if prev_featured:
        admin.put(f"{BASE}/api/apps/showcase/order", json={"app_ids": prev_featured})
    else:
        # ensure at least one starred at the end per review request
        admin.patch(f"{BASE}/api/apps/{NEXUS}/showcase", json={"featured": True})


def _reset_all(admin):
    for aid in ALL:
        admin.patch(f"{BASE}/api/apps/{aid}/showcase", json={"featured": False})


# ---------- PATCH /apps/{id}/showcase ----------
def test_patch_requires_auth():
    r = requests.patch(f"{BASE}/api/apps/{NORTHWIND}/showcase", json={"featured": True})
    assert r.status_code in (401, 403), f"expected 401/403 without auth, got {r.status_code}"


def test_patch_404_for_not_owned(admin):
    r = admin.patch(f"{BASE}/api/apps/app_does_not_exist_xyz/showcase", json={"featured": True})
    assert r.status_code == 404


def test_star_assigns_max_plus_one(admin):
    _reset_all(admin)
    r1 = admin.patch(f"{BASE}/api/apps/{NORTHWIND}/showcase", json={"featured": True})
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1.get("featured") is True
    assert d1.get("showcase_order") == 0

    r2 = admin.patch(f"{BASE}/api/apps/{NEXUS}/showcase", json={"featured": True})
    d2 = r2.json()
    assert d2.get("featured") is True
    assert d2.get("showcase_order") == 1

    r3 = admin.patch(f"{BASE}/api/apps/{AURA}/showcase", json={"featured": True})
    assert r3.json().get("showcase_order") == 2


def test_unstar(admin):
    r = admin.patch(f"{BASE}/api/apps/{AURA}/showcase", json={"featured": False})
    assert r.status_code == 200
    assert r.json().get("featured") is False


# ---------- GET /public/landing/tenants ----------
def test_public_starred_only_and_sorted(admin):
    # State: Northwind order 0, Nexus order 1 (Aura unstarred above)
    d = requests.get(f"{BASE}/api/public/landing/tenants").json()
    ids = [t["app_id"] for t in d["tenants"]]
    assert ids == [NORTHWIND, NEXUS], f"expected only starred sorted, got {ids}"
    for t in d["tenants"]:
        assert t["featured"] is True
        assert "order" in t


def test_public_fallback_when_none_starred(admin):
    _reset_all(admin)
    d = requests.get(f"{BASE}/api/public/landing/tenants").json()
    ids = [t["app_id"] for t in d["tenants"]]
    # All admin apps should show, newest-first (>=4)
    assert len(ids) >= 4
    for aid in ALL:
        assert aid in ids
    # None should be featured
    assert all(not t["featured"] for t in d["tenants"])


# ---------- PUT /apps/showcase/order ----------
def test_reorder_empty_400(admin):
    r = admin.put(f"{BASE}/api/apps/showcase/order", json={"app_ids": []})
    assert r.status_code == 400
    r2 = admin.put(f"{BASE}/api/apps/showcase/order", json={})
    assert r2.status_code == 400


def test_reorder_not_owned_404(admin):
    r = admin.put(f"{BASE}/api/apps/showcase/order", json={"app_ids": ["app_bogus_xxx"]})
    assert r.status_code == 404


def test_reorder_and_public_reflects(admin):
    _reset_all(admin)
    for aid in [NORTHWIND, NEXUS, AURA]:
        admin.patch(f"{BASE}/api/apps/{aid}/showcase", json={"featured": True})

    # Send only two in explicit order; third should be appended keeping featured=True
    r = admin.put(f"{BASE}/api/apps/showcase/order", json={"app_ids": [AURA, NORTHWIND]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ordered"] == 2
    seq = d["sequence"]
    assert seq[0] == AURA and seq[1] == NORTHWIND
    assert NEXUS in seq  # appended
    # unique orders
    time.sleep(0.2)
    pub = requests.get(f"{BASE}/api/public/landing/tenants").json()
    orders = [t["order"] for t in pub["tenants"]]
    assert len(set(orders)) == len(orders), f"duplicate orders: {orders}"
    pub_ids = [t["app_id"] for t in pub["tenants"]]
    assert pub_ids == seq, f"public order mismatch: pub={pub_ids} seq={seq}"
    # all remain featured
    for t in pub["tenants"]:
        assert t["featured"] is True


def test_reorder_reverse_round_trip(admin):
    # Star all 3 and PUT order [N, Nex, A]; then reverse
    _reset_all(admin)
    for aid in [NORTHWIND, NEXUS, AURA]:
        admin.patch(f"{BASE}/api/apps/{aid}/showcase", json={"featured": True})
    r = admin.put(f"{BASE}/api/apps/showcase/order", json={"app_ids": [NORTHWIND, NEXUS, AURA]})
    assert r.json()["sequence"] == [NORTHWIND, NEXUS, AURA]
    pub_ids = [t["app_id"] for t in requests.get(f"{BASE}/api/public/landing/tenants").json()["tenants"]]
    assert pub_ids == [NORTHWIND, NEXUS, AURA]

    r2 = admin.put(f"{BASE}/api/apps/showcase/order", json={"app_ids": [AURA, NEXUS, NORTHWIND]})
    assert r2.json()["sequence"] == [AURA, NEXUS, NORTHWIND]
    pub_ids2 = [t["app_id"] for t in requests.get(f"{BASE}/api/public/landing/tenants").json()["tenants"]]
    assert pub_ids2 == [AURA, NEXUS, NORTHWIND]


def test_unstar_removes_and_no_collision(admin):
    # From previous test, order is [AURA, NEXUS, NORTHWIND]
    r = admin.patch(f"{BASE}/api/apps/{NEXUS}/showcase", json={"featured": False})
    assert r.status_code == 200
    pub = requests.get(f"{BASE}/api/public/landing/tenants").json()
    ids = [t["app_id"] for t in pub["tenants"]]
    assert NEXUS not in ids
    assert AURA in ids and NORTHWIND in ids
    orders = [t["order"] for t in pub["tenants"]]
    assert len(set(orders)) == len(orders), f"collisions after unstar: {orders}"
