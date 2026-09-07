"""Tests for the extras module: AI Media, Billing, Domain, Preview."""
import io
import os
import time
import uuid
import pytest
import requests
import openpyxl

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://app-showcase-pro-4.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200
    return s


@pytest.fixture(scope="module")
def app_id(admin):
    r = admin.post(f"{API}/apps", json={"name": "TEST_Extras_" + uuid.uuid4().hex[:6],
                                        "industry": "SaaS Portals", "description": "extras"}, timeout=20)
    assert r.status_code == 200
    aid = r.json()["app_id"]
    yield aid
    admin.delete(f"{API}/apps/{aid}", timeout=15)


# ========== AI MEDIA ==========
class TestMediaConfig:
    def test_media_config(self, admin):
        r = admin.get(f"{API}/media/config", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["elevenlabs"] is False
        assert d["images"] is True

    def test_eleven_bogus_key_400(self, admin):
        r = admin.post(f"{API}/media/config/elevenlabs", json={"api_key": "bogus_key_that_definitely_wont_work_abcdef"}, timeout=30)
        assert r.status_code == 400

    def test_eleven_short_key_400(self, admin):
        r = admin.post(f"{API}/media/config/elevenlabs", json={"api_key": "short"}, timeout=15)
        assert r.status_code == 400

    def test_voice_gen_503(self, admin, app_id):
        r = admin.post(f"{API}/apps/{app_id}/media/voice", json={"text": "hi"}, timeout=15)
        assert r.status_code == 503


class TestMediaImage:
    def test_image_generation(self, admin, app_id):
        r = admin.post(f"{API}/apps/{app_id}/media/image",
                       json={"prompt": "minimal emerald abstract shape"}, timeout=180)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d["kind"] == "image"
        assert d["data_url"].startswith("data:image/png;base64,")
        assert len(d["data_url"]) > 1000

    def test_media_list(self, admin, app_id):
        r = admin.get(f"{API}/apps/{app_id}/media", timeout=20)
        assert r.status_code == 200
        assets = r.json()
        assert any(a["kind"] == "image" for a in assets)


class TestMediaVideo:
    def test_video_task_created(self, admin, app_id):
        r = admin.post(f"{API}/apps/{app_id}/media/video",
                       json={"prompt": "glowing dashboard", "duration": "6"}, timeout=30)
        assert r.status_code == 200
        t = r.json()
        assert t["status"] == "running"
        assert t["task_id"].startswith("task_")
        # poll once
        r2 = admin.get(f"{API}/apps/{app_id}/media/tasks/{t['task_id']}", timeout=15)
        assert r2.status_code == 200
        assert r2.json()["task_id"] == t["task_id"]
        assert r2.json()["status"] in ("running", "done", "failed")


# ========== BILLING ==========
class TestBillingPlans:
    def test_get_default_plans(self, admin):
        r = admin.get(f"{API}/billing/plans", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert len(d["plans"]) == 3
        names = {p["name"] for p in d["plans"]}
        assert names == {"Starter", "Pro", "Scale"}
        for p in d["plans"]:
            assert "lookup_key" in p and p["lookup_key"]

    def test_checkout_and_transactions(self, admin, app_id):
        plans = admin.get(f"{API}/billing/plans", timeout=60).json()["plans"]
        starter = next(p for p in plans if p["name"] == "Starter")
        r = admin.post(f"{API}/billing/checkout",
                       json={"lookup_key": starter["lookup_key"], "app_id": app_id,
                             "origin_url": "https://example.com"}, timeout=30)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert "checkout.stripe.com" in d["checkout_url"]
        sid = d["session_id"]
        # status
        r2 = admin.get(f"{API}/billing/status/{sid}", timeout=20)
        assert r2.status_code == 200
        assert r2.json()["payment_status"] in ("pending", "initiated")
        # transactions
        r3 = admin.get(f"{API}/billing/transactions?app_id={app_id}", timeout=20)
        assert r3.status_code == 200
        txns = r3.json()
        assert any(t["session_id"] == sid for t in txns)


class TestBillingImport:
    def _xlsx_bytes(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Plan", "Price", "Interval", "Features", "Description"])
        ws.append(["TEST_Import_A", 19, "month", "Feat 1; Feat 2", "Small"])
        ws.append(["TEST_Import_B", 79, "month", "Feat 3; Feat 4", "Big"])
        bio = io.BytesIO()
        wb.save(bio)
        return bio.getvalue()

    def test_import_xlsx(self, admin):
        content = self._xlsx_bytes()
        files = {"file": ("pricing.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = admin.post(f"{API}/billing/plans/import", files=files, timeout=90)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d["count"] == 2
        assert all("lookup_key" in p for p in d["plans"])
        # verify source now 'import'
        r2 = admin.get(f"{API}/billing/plans", timeout=30)
        assert r2.json()["source"] == "import"

    def test_import_csv(self, admin):
        csv_data = "Plan,Price,Interval,Features,Description\nTEST_CSV_A,15,month,x;y,desc\nTEST_CSV_B,55,year,a;b,desc\n"
        files = {"file": ("pricing.csv", csv_data.encode(), "text/csv")}
        r = admin.post(f"{API}/billing/plans/import", files=files, timeout=90)
        assert r.status_code == 200, r.text[:400]
        assert r.json()["count"] == 2

    def test_restore_defaults(self, admin):
        payload = {"plans": [
            {"name": "Starter", "price": 29.0, "interval": "month", "features": ["1 hosted tenant", "Custom domain", "Email support"], "description": "Single hosted tenant"},
            {"name": "Pro", "price": 99.0, "interval": "month", "features": ["10 hosted tenants", "AI Media Studio", "Priority support"], "description": "Growing client portfolio"},
            {"name": "Scale", "price": 299.0, "interval": "month", "features": ["Unlimited tenants", "Dedicated SLA", "White-label handoff"], "description": "Agency at scale"},
        ]}
        r = admin.put(f"{API}/billing/plans", json=payload, timeout=90)
        assert r.status_code == 200
        assert len(r.json()["plans"]) == 3


# ========== DOMAIN ==========
class TestDomain:
    def test_set_invalid_domain(self, admin, app_id):
        r = admin.post(f"{API}/apps/{app_id}/domain", json={"domain": "notadomain"}, timeout=15)
        assert r.status_code == 400

    def test_set_valid_domain(self, admin, app_id):
        r = admin.post(f"{API}/apps/{app_id}/domain", json={"domain": "www.github.com"}, timeout=20)
        assert r.status_code == 200
        assert r.json()["custom_domain"] == "www.github.com"
        assert r.json()["domain_status"] == "pending"

    def test_verify_domain(self, admin, app_id):
        r = admin.post(f"{API}/apps/{app_id}/domain/verify", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["domain_dns"] is not None
        # www.github.com resolves as CNAME to github.com
        found = d["domain_dns"]["cname"]["found"]
        assert any("github.com" in f for f in found), f"Expected github.com in CNAME, got {found}"

    def test_remove_domain(self, admin, app_id):
        r = admin.delete(f"{API}/apps/{app_id}/domain", timeout=15)
        assert r.status_code == 200
        assert "custom_domain" not in r.json() or not r.json().get("custom_domain")


# ========== PREVIEW ==========
class TestPreview:
    def test_regenerate_and_public_preview(self, admin, app_id):
        r = admin.post(f"{API}/apps/{app_id}/preview/regenerate", timeout=15)
        assert r.status_code == 200
        token1 = r.json()["preview_token"]
        assert r.json()["preview_enabled"] is True

        # Public unauth GET
        rp = requests.get(f"{API}/public/preview/{token1}", timeout=15)
        assert rp.status_code == 200
        body = rp.json()
        assert "app" in body and "blocks" in body

        # Regenerate again -> old token 404
        r2 = admin.post(f"{API}/apps/{app_id}/preview/regenerate", timeout=15)
        token2 = r2.json()["preview_token"]
        assert token2 != token1
        rp_old = requests.get(f"{API}/public/preview/{token1}", timeout=15)
        assert rp_old.status_code == 404

        # Toggle off -> new token 404
        rt = admin.post(f"{API}/apps/{app_id}/preview/toggle", timeout=15)
        assert rt.status_code == 200
        assert rt.json()["preview_enabled"] is False
        rp2 = requests.get(f"{API}/public/preview/{token2}", timeout=15)
        assert rp2.status_code == 404
