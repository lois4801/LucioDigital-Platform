"""Iter-27 SLOW: app-from-site (LLM ~50s) and full roto-rooter import (~2 min)."""
import os
import time
import uuid
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PASSWORD = "Lucio2026!"
SEED_TENANT = "app_bdbf27abe643"


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200
    return s


@pytest.fixture(scope="module")
def throwaway(admin):
    r = admin.post(f"{BASE_URL}/apps", json={
        "name": "TEST_iter27_slow", "industry": "Plumbing", "kind": "website",
        "description": "throwaway", "status": "draft", "tags": [], "color": "#333",
    }, timeout=30)
    assert r.status_code == 200
    app_id = r.json()["app_id"]
    yield app_id
    try:
        admin.delete(f"{BASE_URL}/apps/{app_id}", timeout=20)
    except Exception:
        pass


def test_app_from_site_overwrite_on_seeded_tenant(admin):
    """POST /ai/app-from-site mode=overwrite — should produce a spec reflecting the tenant's real business."""
    # verify seeded tenant has site content
    pages = admin.get(f"{BASE_URL}/apps/{SEED_TENANT}/pages", timeout=20).json()
    assert len(pages) > 0, "seed tenant has no pages"

    r = admin.post(
        f"{BASE_URL}/apps/{SEED_TENANT}/ai/app-from-site",
        json={"mode": "overwrite"},
        timeout=120,  # ingress caps 60s — this may 502
    )
    if r.status_code == 502:
        pytest.fail("REGRESSION: app-from-site 502'd at the ingress 60s cap — needs to be a background job like web import")
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
    data = r.json()
    assert "spec" in data and "summary" in data
    spec = data["spec"]
    assert spec.get("screens") and 4 <= len(spec["screens"]) <= 12
    assert spec.get("models") and 3 <= len(spec["models"]) <= 10
    assert isinstance(spec.get("name"), str) and spec["name"].strip()

    # verify persisted
    bp = admin.get(f"{BASE_URL}/apps/{SEED_TENANT}/blueprint", timeout=20)
    assert bp.status_code == 200
    persisted = bp.json()
    assert persisted and persisted.get("name") == spec["name"]

    # verify assistant message appended
    chat = admin.get(f"{BASE_URL}/apps/{SEED_TENANT}/ai/app-chat", timeout=20).json()
    assert any(m.get("role") == "assistant" and "Synced from Site Mode" in (m.get("content") or "") for m in chat[-5:]), \
        "no 'Synced from Site Mode' assistant message found in recent chat"


def test_app_from_site_merge_preserves_existing(admin):
    """After the overwrite above, run merge — screens/models should be largely preserved."""
    before = admin.get(f"{BASE_URL}/apps/{SEED_TENANT}/blueprint", timeout=20).json()
    if not before:
        pytest.skip("no existing spec")
    before_screen_names = {s.get("name") for s in before.get("screens", [])}
    before_model_names = {m.get("name") for m in before.get("models", [])}

    r = admin.post(
        f"{BASE_URL}/apps/{SEED_TENANT}/ai/app-from-site",
        json={"mode": "merge"},
        timeout=120,
    )
    if r.status_code == 502:
        pytest.fail("REGRESSION: merge 502'd at 60s")
    assert r.status_code == 200, r.text[:300]
    after = r.json()["spec"]
    after_screen_names = {s.get("name") for s in after.get("screens", [])}
    after_model_names = {m.get("name") for m in after.get("models", [])}

    # at least 50% of prior screens preserved by name
    preserved_screens = before_screen_names & after_screen_names
    ratio = len(preserved_screens) / max(1, len(before_screen_names))
    assert ratio >= 0.5, f"merge wiped too much: only {len(preserved_screens)}/{len(before_screen_names)} screens preserved: {before_screen_names - after_screen_names}"

    preserved_models = before_model_names & after_model_names
    mratio = len(preserved_models) / max(1, len(before_model_names))
    assert mratio >= 0.5, f"merge wiped too many models: only {len(preserved_models)}/{len(before_model_names)}"

    summary = r.json().get("summary")
    assert summary and isinstance(summary, str)


def test_roto_rooter_full_import(admin, throwaway):
    """Full scrape+LLM job → validate scraped brand/phone/colors and page shape."""
    r = admin.post(f"{BASE_URL}/apps/{throwaway}/site/import-preview",
                   json={"url": "https://www.roto-rooter.com"}, timeout=25)
    assert r.status_code == 200, r.text[:200]
    job_id = r.json()["job_id"]

    result = None
    err = None
    for i in range(36):  # up to 3 min
        time.sleep(5)
        g = admin.get(f"{BASE_URL}/apps/{throwaway}/site/import-job/{job_id}", timeout=20)
        assert g.status_code == 200
        j = g.json()
        if j.get("status") == "done":
            result = j["result"]
            break
        if j.get("status") == "error":
            err = j.get("error")
            break
    if err:
        pytest.fail(f"import errored: {err}")
    assert result, "import didn't complete in time"

    assert result["import_id"].startswith("imp_")
    src = result["source"]
    assert src["pages"] >= 1
    # scraped phones should include roto-rooter's number
    phones = " ".join(src.get("phones", []))
    assert "800-768-6911" in phones or "800.768.6911" in phones or "8007686911" in phones.replace("-", "").replace(".", ""), \
        f"expected 800-768-6911 in scraped phones, got {src.get('phones')}"

    biz = result["business"]
    assert biz.get("name")
    # scraped colours -> theme must be hex
    theme = result["theme"]
    assert theme["primary"].startswith("#") and len(theme["primary"]) in (4, 7)
    assert theme["secondary"].startswith("#")

    pages = result["pages"]
    assert 3 <= len(pages) <= 6
    for p in pages:
        assert p.get("slug")
        assert p.get("blocks", 0) >= 5

    # ---- apply append (no theme change) ----
    before = admin.get(f"{BASE_URL}/apps/{throwaway}/pages", timeout=20).json()
    before_ids = {p["page_id"] for p in before}
    ap = admin.post(f"{BASE_URL}/apps/{throwaway}/site/import-apply",
                    json={"import_id": result["import_id"], "mode": "append", "apply_theme": False},
                    timeout=30)
    assert ap.status_code == 200, ap.text[:200]

    after = admin.get(f"{BASE_URL}/apps/{throwaway}/pages", timeout=20).json()
    after_ids = {p["page_id"] for p in after}
    assert before_ids.issubset(after_ids), "append deleted existing pages!"
    new_pages = [p for p in after if p["page_id"] not in before_ids]
    assert len(new_pages) >= 3
    assert not any(p["slug"] == "/" for p in new_pages), "append should not clobber '/'"
    assert any(p["slug"].startswith("/imported-") for p in new_pages)

    # ---- apply replace with theme (only on throwaway) ----
    rep = admin.post(f"{BASE_URL}/apps/{throwaway}/site/import-apply",
                     json={"import_id": result["import_id"], "mode": "replace", "apply_theme": True},
                     timeout=30)
    assert rep.status_code == 200, rep.text[:200]
    after2 = admin.get(f"{BASE_URL}/apps/{throwaway}/pages", timeout=20).json()
    assert len(after2) == len(pages), f"replace should leave exactly {len(pages)} pages, got {len(after2)}"

    app_doc = admin.get(f"{BASE_URL}/apps/{throwaway}", timeout=20).json()
    assert app_doc.get("theme", {}).get("primary") == theme["primary"], "theme.primary not applied"
