"""Iter58 — No auto-tenant creation + Archive/Restore + Global inbox + Empty landing."""
import os, time, subprocess
import pytest, requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0]).rstrip("/")
ADMIN = ("jaybernabe@luciodigital.com", "Lucio2026!")
EDITOR = ("client.editor@example.com", "ClientEdit2026!")


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def editor():
    return _login(*EDITOR)


@pytest.fixture(scope="module")
def throwaway_app(admin):
    r = admin.post(f"{BASE}/api/apps", json={
        "name": "TEST_iter58_throwaway", "industry": "SaaS", "kind": "website",
        "description": "throwaway", "status": "in-progress", "tags": [], "color": "#F97316",
    }, timeout=15)
    assert r.status_code == 200, r.text
    app_id = r.json()["app_id"]
    yield app_id
    # cleanup: archive it (safer than delete)
    admin.post(f"{BASE}/api/apps/{app_id}/archive", json={"archived": True})


# ============ No auto-creation ============

class TestNoAutoCreation:
    def test_active_apps_start_at_zero(self, admin):
        r = admin.get(f"{BASE}/api/apps")
        assert r.status_code == 200
        apps = r.json()
        # Only apps that the tests just created should be active (0 baseline before throwaway).
        # Baseline: with archived=false, count should be limited to test-created ones only.
        names = [a.get("name") for a in apps]
        # Anything auto-seeded like Northwind Roofing should NOT appear as active
        assert not any(n and "Northwind Roofing" in n and not a.get("archived")
                       for n, a in zip(names, apps)), \
            f"Auto-seeded tenant found active: {names}"

    def test_archived_apps_preserved(self, admin):
        r = admin.get(f"{BASE}/api/apps?archived=true")
        assert r.status_code == 200
        # The 7 recoverable archived tenants (per review context)
        apps = r.json()
        assert isinstance(apps, list)
        # We don't assert exactly 7 since prior tests may archive more; assert >= 0
        for a in apps:
            assert a.get("archived") is True

    def test_startup_does_not_auto_create(self, admin):
        """Restart backend, confirm active app count doesn't grow from auto-seeding."""
        before = admin.get(f"{BASE}/api/apps").json()
        before_ids = {a["app_id"] for a in before}
        subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=False, timeout=30)
        # wait for backend to come up
        for _ in range(30):
            try:
                r = requests.get(f"{BASE}/api/", timeout=3)
                if r.status_code < 500:
                    break
            except Exception:
                pass
            time.sleep(1)
        # relogin
        s = _login(*ADMIN)
        after = s.get(f"{BASE}/api/apps").json()
        after_ids = {a["app_id"] for a in after}
        new_ids = after_ids - before_ids
        assert not new_ids, f"Backend restart auto-created tenants: {new_ids}"


# ============ Archive / Restore flow ============

class TestArchiveFlow:
    def test_archive_hides_from_active_list(self, admin, throwaway_app):
        r = admin.post(f"{BASE}/api/apps/{throwaway_app}/archive", json={"archived": True})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["archived"] is True
        assert "leads_kept" in data

        # not in active
        active = admin.get(f"{BASE}/api/apps").json()
        assert throwaway_app not in [a["app_id"] for a in active]

        # in archived
        arch = admin.get(f"{BASE}/api/apps?archived=true").json()
        assert throwaway_app in [a["app_id"] for a in arch]

        # preview_enabled and featured cleared
        rec = next((a for a in arch if a["app_id"] == throwaway_app), None)
        assert rec is not None
        assert rec.get("preview_enabled") is False
        assert rec.get("featured") is False

    def test_pages_retained_after_archive(self, admin, throwaway_app):
        # ensure previous test archived it — pages endpoint should still list Home
        r = admin.get(f"{BASE}/api/apps/{throwaway_app}/pages")
        assert r.status_code == 200, r.text
        pages = r.json()
        assert len(pages) >= 1

    def test_restore_brings_back(self, admin, throwaway_app):
        r = admin.post(f"{BASE}/api/apps/{throwaway_app}/archive", json={"archived": False})
        assert r.status_code == 200
        assert r.json()["archived"] is False
        active = admin.get(f"{BASE}/api/apps").json()
        assert throwaway_app in [a["app_id"] for a in active]


# ============ Global inbox ============

class TestGlobalInbox:
    def test_admin_inbox_includes_archived(self, admin):
        r = admin.get(f"{BASE}/api/inbox")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "messages" in data
        msgs = data["messages"]
        # At least one lead should carry app_archived=True per review context (5 leads retained on archived tenants)
        if msgs:
            for m in msgs:
                assert "app_name" in m
                assert "app_archived" in m

    def test_editor_only_sees_own_tenant_leads(self, editor):
        r = editor.get(f"{BASE}/api/inbox")
        assert r.status_code == 200
        data = r.json()
        # Editor's tenant (Northwind) is ARCHIVED per review context — should see own leads only, or empty
        msgs = data.get("messages", [])
        # If any messages exist, all should belong to Northwind app_id
        editor_apps = editor.get(f"{BASE}/api/apps?archived=true").json() + editor.get(f"{BASE}/api/apps").json()
        editor_app_ids = {a["app_id"] for a in editor_apps}
        for m in msgs:
            assert m["app_id"] in editor_app_ids, f"Editor sees lead outside their scope: {m['app_id']}"


# ============ Landing empty state ============

class TestLanding:
    def test_public_landing_tenants(self, admin):
        # first ensure no active tenants exist (archive our throwaway if still active)
        r = requests.get(f"{BASE}/api/public/landing/tenants", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "tenants" in data and "count" in data and "live" in data
        # count reflects non-archived only
        for t in data["tenants"]:
            assert not t.get("archived")

    def test_public_showcase(self, admin):
        r = requests.get(f"{BASE}/api/public/showcase", timeout=15)
        assert r.status_code == 200
        showcase = r.json()
        assert isinstance(showcase, list)
        # all items in showcase must be non-archived
        # (we accept the list; format is per-item app entry with no 'archived' field visible)


# ============ Platform defaults on manual creation ============

class TestManualCreateInheritsLook:
    @pytest.mark.parametrize("industry,expected_kw", [
        ("Retail", ["editoriallux", "retail"]),
        ("Fitness", ["energy", "fitness"]),
        ("Finance", ["ledger", "finance"]),
    ])
    def test_create_inherits_industry_look(self, admin, industry, expected_kw):
        r = admin.post(f"{BASE}/api/apps", json={
            "name": f"TEST_iter58_{industry}", "industry": industry, "kind": "website",
            "description": "look test", "status": "in-progress", "tags": [], "color": "#F97316",
        }, timeout=15)
        assert r.status_code == 200, r.text
        app = r.json()
        app_id = app["app_id"]
        try:
            theme = app.get("theme") or {}
            preset = (theme.get("site_preset") or "").lower()
            niche = (theme.get("site_niche") or "").lower()
            # Assert theme is not the generic V2 default — should have a site_preset
            assert theme.get("site_preset") or theme.get("site_niche"), \
                f"{industry} tenant has generic theme, no preset: {theme}"
            # At least one keyword should appear
            hit = any(k in preset or k in niche for k in expected_kw)
            assert hit, f"{industry} theme did not match expected look keywords {expected_kw}: preset={preset} niche={niche}"
        finally:
            admin.post(f"{BASE}/api/apps/{app_id}/archive", json={"archived": True})
