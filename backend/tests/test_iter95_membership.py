"""Iter95 — Membership gating, payments (Stripe + Interac), admin members, Stripe keys."""
import os, secrets, pytest, requests, time
from pathlib import Path


def _load_env():
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PW = "Lucio2026!"
GRANDFATHERED_EMAIL = "lois4801@gmail.com"


def _new_email():
    return f"test_iter95_{int(time.time())}_{secrets.token_hex(3)}@example.com"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def free_user():
    s = requests.Session()
    email = _new_email()
    pw = "FreeTest2026!"
    r = s.post(f"{BASE}/api/auth/register",
               json={"email": email, "password": pw, "name": "Iter95 Free"}, timeout=20)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text[:200]}"
    # ensure logged in
    if not s.cookies:
        r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=20)
        assert r.status_code == 200
    s._email = email  # type: ignore
    s._password = pw  # type: ignore
    return s


# ---------- Anonymous / Public ----------

def test_public_templates_no_auth():
    r = requests.get(f"{BASE}/api/public/templates", timeout=20)
    assert r.status_code == 200
    data = r.json()
    # should be a list-like structure
    items = data if isinstance(data, list) else data.get("templates") or data.get("items") or []
    assert len(items) >= 1, f"expected >=1 public templates, got {len(items)}"


def test_anonymous_gated_returns_402_or_401():
    r = requests.get(f"{BASE}/api/apps", timeout=15, allow_redirects=False)
    assert r.status_code in (401, 402, 403), f"expected 401/402/403 for anon on /api/apps, got {r.status_code}"


def test_membership_plans_public():
    r = requests.get(f"{BASE}/api/membership/plans", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "plans" in data and len(data["plans"]) == 2
    kinds = {p["kind"] for p in data["plans"]}
    assert kinds == {"setup", "monthly"}
    assert "card" in data["methods"] and "bank" in data["methods"] and "interac" in data["methods"]


# ---------- Free account gating ----------

def test_free_membership_me(free_user):
    r = free_user.get(f"{BASE}/api/membership/me", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["access"] == "free", f"expected access=free, got {d.get('access')}"
    assert d["full_access"] is False


def test_free_gated_apis_return_402(free_user):
    for path in ("/api/apps", "/api/apps/app_testlab"):
        r = free_user.get(f"{BASE}{path}", timeout=15)
        assert r.status_code == 402, f"expected 402 on {path}, got {r.status_code} {r.text[:120]}"
        j = r.json()
        # accept upgrade_required flag or upgrade in detail
        body = str(j).lower()
        assert "upgrade" in body, f"missing 'upgrade' hint: {j}"

    r = free_user.post(f"{BASE}/api/apps", json={"name": "TEST_iter95"}, timeout=15)
    assert r.status_code == 402


def test_free_favorites_persist(free_user):
    key = "template-iter95"
    r = free_user.post(f"{BASE}/api/membership/favorites/{key}", timeout=15)
    assert r.status_code == 200
    assert key in r.json()["favorites"]
    r2 = free_user.get(f"{BASE}/api/membership/me", timeout=15)
    assert key in r2.json().get("favorites") or []
    # toggle off
    r3 = free_user.post(f"{BASE}/api/membership/favorites/{key}", timeout=15)
    assert key not in r3.json()["favorites"]


# ---------- Checkout ordering + method validation ----------

def test_checkout_monthly_before_setup_rejected(free_user):
    r = free_user.post(f"{BASE}/api/membership/checkout",
                       json={"kind": "monthly", "method": "card",
                             "origin_url": BASE}, timeout=20)
    assert r.status_code == 400
    assert "setup" in r.text.lower()


def test_checkout_unknown_kind(free_user):
    r = free_user.post(f"{BASE}/api/membership/checkout",
                       json={"kind": "nope", "method": "card",
                             "origin_url": BASE}, timeout=20)
    assert r.status_code == 400


def test_checkout_unknown_method(free_user):
    r = free_user.post(f"{BASE}/api/membership/checkout",
                       json={"kind": "setup", "method": "crypto",
                             "origin_url": BASE}, timeout=20)
    assert r.status_code == 400


def test_checkout_setup_card_returns_stripe_url(free_user):
    r = free_user.post(f"{BASE}/api/membership/checkout",
                       json={"kind": "setup", "method": "card",
                             "origin_url": BASE}, timeout=45)
    assert r.status_code == 200, f"card checkout: {r.status_code} {r.text[:300]}"
    d = r.json()
    assert d.get("checkout_url", "").startswith("https://"), d
    assert "stripe" in d["checkout_url"].lower()
    assert d.get("session_id", "").startswith("cs_")


def test_checkout_setup_bank_returns_stripe_url(free_user):
    r = free_user.post(f"{BASE}/api/membership/checkout",
                       json={"kind": "setup", "method": "bank",
                             "origin_url": BASE}, timeout=45)
    assert r.status_code == 200, f"bank checkout: {r.status_code} {r.text[:300]}"
    d = r.json()
    assert d.get("checkout_url", "").startswith("https://")


# ---------- Interac flow ----------

@pytest.fixture(scope="module")
def interac_user():
    """A fresh free user we will use for the Interac -> admin confirm -> paid path."""
    s = requests.Session()
    email = _new_email()
    pw = "InteracTest2026!"
    r = s.post(f"{BASE}/api/auth/register",
               json={"email": email, "password": pw, "name": "Iter95 Interac"}, timeout=20)
    assert r.status_code in (200, 201)
    if not s.cookies:
        s.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=20)
    s._email = email  # type: ignore
    return s


def test_interac_setup_flow_admin_confirm(interac_user, admin):
    # 1) member declares
    r = interac_user.post(f"{BASE}/api/membership/interac",
                          json={"kind": "setup"}, timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert d.get("reference", "").startswith("LD-")
    assert d.get("send_to")
    manual_id = d["manual_id"]

    # 2) shows in /membership/me pending_manual
    me = interac_user.get(f"{BASE}/api/membership/me", timeout=15).json()
    assert any(p["manual_id"] == manual_id for p in me.get("pending_manual", []))

    # 3) admin sees it
    q = admin.get(f"{BASE}/api/admin/manual-payments?status=pending", timeout=15)
    assert q.status_code == 200
    assert any(p["manual_id"] == manual_id for p in q.json())

    # 4) admin confirms setup -> status setup_paid, still 402 on gated
    c = admin.post(f"{BASE}/api/admin/manual-payments/{manual_id}/confirm", timeout=20)
    assert c.status_code == 200
    me2 = interac_user.get(f"{BASE}/api/membership/me", timeout=15).json()
    assert me2["status"] == "setup_paid"
    assert me2["full_access"] is False
    gated = interac_user.get(f"{BASE}/api/apps", timeout=15)
    assert gated.status_code == 402

    # 5) member declares monthly
    r = interac_user.post(f"{BASE}/api/membership/interac",
                          json={"kind": "monthly"}, timeout=20)
    assert r.status_code == 200
    monthly_id = r.json()["manual_id"]

    # 6) admin confirms monthly -> active/paid, gated APIs 200
    c2 = admin.post(f"{BASE}/api/admin/manual-payments/{monthly_id}/confirm", timeout=20)
    assert c2.status_code == 200
    me3 = interac_user.get(f"{BASE}/api/membership/me", timeout=15).json()
    assert me3["access"] == "paid", me3
    assert me3["full_access"] is True
    assert me3.get("current_period_end")
    gated2 = interac_user.get(f"{BASE}/api/apps", timeout=15)
    assert gated2.status_code == 200


def test_interac_reject(interac_user, admin):
    """Reject path — declare, admin rejects, no membership change."""
    r = interac_user.post(f"{BASE}/api/membership/interac",
                          json={"kind": "setup", "note": "for reject test"}, timeout=20)
    assert r.status_code == 200
    mid = r.json()["manual_id"]
    rej = admin.post(f"{BASE}/api/admin/manual-payments/{mid}/reject", timeout=15)
    assert rej.status_code == 200
    assert rej.json()["status"] == "rejected"


# ---------- Suspend / Reactivate (using the now-paid interac_user) ----------

def test_suspend_and_reactivate(interac_user, admin):
    # find user_id
    q = admin.get(f"{BASE}/api/admin/members?q={interac_user._email}", timeout=15).json()  # type: ignore
    rows = q["members"]
    row = next((r for r in rows if r["email"] == interac_user._email), None)  # type: ignore
    assert row, f"member not listed: {rows}"
    uid = row["user_id"]

    s = admin.post(f"{BASE}/api/admin/members/{uid}/suspend", timeout=15)
    assert s.status_code == 200
    assert s.json()["access"] == "suspended"

    me = interac_user.get(f"{BASE}/api/membership/me", timeout=15).json()
    assert me["access"] == "suspended"
    assert me["full_access"] is False
    assert interac_user.get(f"{BASE}/api/apps", timeout=15).status_code == 402

    ra = admin.post(f"{BASE}/api/admin/members/{uid}/reactivate", timeout=15)
    assert ra.status_code == 200
    assert interac_user.get(f"{BASE}/api/apps", timeout=15).status_code == 200


def test_admin_cannot_suspend_self(admin):
    q = admin.get(f"{BASE}/api/admin/members?q={ADMIN_EMAIL}", timeout=15).json()
    row = next((r for r in q["members"] if r["email"] == ADMIN_EMAIL), None)
    assert row
    r = admin.post(f"{BASE}/api/admin/members/{row['user_id']}/suspend", timeout=15)
    assert r.status_code == 400


# ---------- Grandfathering ----------

def test_admin_row_is_admin(admin):
    q = admin.get(f"{BASE}/api/admin/members?q={ADMIN_EMAIL}", timeout=15).json()
    row = next((r for r in q["members"] if r["email"] == ADMIN_EMAIL), None)
    assert row and row["access"] == "admin"


def test_grandfathered_agency_paid(admin):
    q = admin.get(f"{BASE}/api/admin/members?q={GRANDFATHERED_EMAIL}", timeout=15).json()
    row = next((r for r in q["members"] if r["email"] == GRANDFATHERED_EMAIL), None)
    assert row, f"{GRANDFATHERED_EMAIL} not present"
    assert row["access"] == "paid", f"expected paid, got {row['access']}"


# ---------- Admin-only guards for non-admin ----------

def test_non_admin_cannot_hit_admin_endpoints(free_user):
    for path in ("/api/admin/members", "/api/admin/manual-payments", "/api/admin/stripe-keys"):
        r = free_user.get(f"{BASE}{path}", timeout=15)
        assert r.status_code in (402, 403), f"{path} returned {r.status_code}"


# ---------- Stripe keys round-trip ----------

def test_stripe_keys_roundtrip(admin):
    r = admin.get(f"{BASE}/api/admin/stripe-keys", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "publishable_key" in d
    assert "secret_key" not in d  # never returned in the clear
    assert "secret_key_set" in d

    # invalid secret rejected
    bad = admin.put(f"{BASE}/api/admin/stripe-keys",
                    json={"secret_key": "not_a_stripe_key"}, timeout=15)
    assert bad.status_code == 400

    # PUT publishable + interac fields (do NOT overwrite the working secret)
    ok = admin.put(f"{BASE}/api/admin/stripe-keys",
                   json={"publishable_key": "pk_test_iter95_roundtrip",
                         "interac_email": "billing@luciodigital.com",
                         "interac_instructions": "Send with the reference in the memo."},
                   timeout=15)
    assert ok.status_code == 200
    d2 = ok.json()
    assert d2["publishable_key"] == "pk_test_iter95_roundtrip"
    assert d2["interac_email"] == "billing@luciodigital.com"


# ---------- Admin email member ----------

def test_admin_email_member(admin, free_user):
    q = admin.get(f"{BASE}/api/admin/members?q={free_user._email}", timeout=15).json()  # type: ignore
    row = next((r for r in q["members"] if r["email"] == free_user._email), None)  # type: ignore
    assert row
    r = admin.post(f"{BASE}/api/admin/members/{row['user_id']}/email",
                   json={"subject": "TEST iter95", "body": "Hello there."}, timeout=30)
    assert r.status_code == 200
    assert r.json().get("sent") is True

    # empty subject rejected
    r2 = admin.post(f"{BASE}/api/admin/members/{row['user_id']}/email",
                    json={"subject": "", "body": ""}, timeout=15)
    assert r2.status_code == 400
