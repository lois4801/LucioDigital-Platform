"""
Iteration 37 — Design Upgrade + Section Style Presets

Tests two features:
1. POST /api/apps/{id}/site/upgrade-design (single) and /api/site/upgrade-design-all (bulk)
   - Content must remain byte-identical (pages payload)
   - Font swap only for the old default pair
   - Restore point created
   - Editor gets 403
2. Section style presets — persistence + export parity (styles.css + index.html)
"""
import os
import io
import json
import copy
import zipfile
import pytest
import requests

def _load_base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert v, "REACT_APP_BACKEND_URL not configured"
    return v.rstrip("/")

BASE = _load_base()
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
EDITOR = {"email": "client.editor@example.com", "password": "ClientEdit2026!"}
EDITOR_APP = "app_6663b5de0007"


def _login(email, password):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def owner():
    return _login(ADMIN["email"], ADMIN["password"])


@pytest.fixture(scope="module")
def editor():
    try:
        return _login(EDITOR["email"], EDITOR["password"])
    except AssertionError as e:
        pytest.skip(f"Editor login failed: {e}")


def _create_tenant(sess, name, industry="services"):
    r = sess.post(f"{BASE}/api/apps", json={
        "name": name, "industry": industry, "kind": "website",
        "description": "TEST_iter37", "status": "active", "tags": ["TEST_iter37"],
        "color": "#F97316"
    }, timeout=30)
    assert r.status_code in (200, 201), r.text[:300]
    return r.json()["app_id"]


def _put_theme(sess, app_id, theme):
    r = sess.put(f"{BASE}/api/apps/{app_id}/theme", json={"theme": theme}, timeout=20)
    assert r.status_code == 200, r.text[:300]
    return r.json()


def _get_pages(sess, app_id):
    r = sess.get(f"{BASE}/api/apps/{app_id}/pages", timeout=20)
    assert r.status_code == 200, r.text[:300]
    return r.json()


def _pages_stable(pages):
    """Strip volatile fields (updated_at) and return a stable canonical JSON."""
    clone = copy.deepcopy(pages)
    for p in clone:
        p.pop("updated_at", None)
    return json.dumps(clone, sort_keys=True)


@pytest.fixture(scope="module")
def cleanup_ids():
    ids = []
    yield ids
    # teardown
    try:
        sess = _login(ADMIN["email"], ADMIN["password"])
        for aid in ids:
            try:
                sess.delete(f"{BASE}/api/apps/{aid}", timeout=15)
            except Exception:
                pass
    except Exception:
        pass


# ================== Design Upgrade ==================

class TestUpgradeDesignSingle:
    def test_upgrade_legacy_tenant_preserves_pages_and_swaps_default_fonts(self, owner, cleanup_ids):
        app_id = _create_tenant(owner, "TEST_iter37_legacy_default_fonts")
        cleanup_ids.append(app_id)
        # Downgrade to legacy with the OLD default font pair
        _put_theme(owner, app_id, {
            "font_heading": "Plus Jakarta Sans", "font_body": "Manrope",
            "primary": "#F97316", "design_v2": False,
        })
        before_pages = _get_pages(owner, app_id)
        assert len(before_pages) >= 1, "Should have seeded starter page"
        before_sig = _pages_stable(before_pages)

        r = owner.post(f"{BASE}/api/apps/{app_id}/site/upgrade-design", timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("already") is False, f"Expected already=False, got {data}"
        assert data.get("theme", {}).get("design_v2") is True
        assert data["theme"]["font_heading"] == "Sora"
        assert data["theme"]["font_body"] == "Inter"
        assert "restore_point" in data and data["restore_point"], "Restore point missing"

        # PAGES BYTE-IDENTICAL CHECK
        after_pages = _get_pages(owner, app_id)
        after_sig = _pages_stable(after_pages)
        assert before_sig == after_sig, "Pages payload changed after upgrade-design!"

        # Second call is idempotent
        r2 = owner.post(f"{BASE}/api/apps/{app_id}/site/upgrade-design", timeout=20)
        assert r2.status_code == 200
        assert r2.json().get("already") is True

        # Restore point visible in history
        rp = owner.get(f"{BASE}/api/apps/{app_id}/site/restore-points", timeout=20)
        assert rp.status_code == 200
        reasons = [x.get("reason") for x in rp.json().get("restore_points", [])]
        assert any("before design upgrade" in (rz or "") for rz in reasons), f"reasons={reasons}"

    def test_upgrade_preserves_custom_font_pair(self, owner, cleanup_ids):
        app_id = _create_tenant(owner, "TEST_iter37_custom_fonts")
        cleanup_ids.append(app_id)
        _put_theme(owner, app_id, {
            "font_heading": "Space Grotesk", "font_body": "Manrope",
            "primary": "#7C3AED", "design_v2": False,
        })
        r = owner.post(f"{BASE}/api/apps/{app_id}/site/upgrade-design", timeout=30)
        assert r.status_code == 200, r.text[:300]
        theme = r.json()["theme"]
        assert theme["design_v2"] is True
        # Custom pair should be preserved (only Plus Jakarta Sans + Manrope pair triggers swap)
        assert theme["font_heading"] == "Space Grotesk", theme
        assert theme["font_body"] == "Manrope", theme

    def test_upgrade_already_v2_returns_already_true(self, owner, cleanup_ids):
        app_id = _create_tenant(owner, "TEST_iter37_already_v2")
        cleanup_ids.append(app_id)
        # Fresh tenants are v2 by default
        r = owner.post(f"{BASE}/api/apps/{app_id}/site/upgrade-design", timeout=20)
        assert r.status_code == 200
        assert r.json().get("already") is True

    def test_restore_batch_undoes_upgrade(self, owner, cleanup_ids):
        app_id = _create_tenant(owner, "TEST_iter37_restore")
        cleanup_ids.append(app_id)
        _put_theme(owner, app_id, {
            "font_heading": "Plus Jakarta Sans", "font_body": "Manrope", "design_v2": False,
        })
        r = owner.post(f"{BASE}/api/apps/{app_id}/site/upgrade-design", timeout=30)
        assert r.status_code == 200
        rp = owner.get(f"{BASE}/api/apps/{app_id}/site/restore-points", timeout=20)
        pts = [p for p in rp.json().get("restore_points", []) if "before design upgrade" in (p.get("reason") or "")]
        assert pts, "no design upgrade restore point"
        batch_id = pts[0]["batch_id"]
        rr = owner.post(f"{BASE}/api/apps/{app_id}/site/restore-batch",
                        json={"batch_id": batch_id}, timeout=30)
        assert rr.status_code == 200, rr.text[:300]
        assert rr.json().get("pages"), "restore returned no pages"

    def test_editor_gets_403(self, editor):
        r = editor.post(f"{BASE}/api/apps/{EDITOR_APP}/site/upgrade-design", timeout=20)
        # Either 403 forbidden or 404 if editor has no access at all — must NOT be 200
        assert r.status_code in (403, 404), f"Editor got {r.status_code} — should be denied"
        assert r.status_code == 403, f"Expected 403 specifically, got {r.status_code}: {r.text[:200]}"


class TestUpgradeDesignBulk:
    def test_bulk_upgrade_count_and_skips_v2(self, owner, cleanup_ids):
        # Create one legacy and one v2 throwaway
        legacy_id = _create_tenant(owner, "TEST_iter37_bulk_legacy")
        cleanup_ids.append(legacy_id)
        _put_theme(owner, legacy_id, {"design_v2": False, "font_heading": "Plus Jakarta Sans", "font_body": "Manrope"})

        v2_id = _create_tenant(owner, "TEST_iter37_bulk_v2")
        cleanup_ids.append(v2_id)

        r = owner.post(f"{BASE}/api/site/upgrade-design-all", timeout=60)
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        assert "count" in data and "upgraded" in data
        upgraded_ids = {u["app_id"] for u in data["upgraded"]}
        assert legacy_id in upgraded_ids, f"legacy tenant not in upgraded: {upgraded_ids}"
        assert v2_id not in upgraded_ids, "already-v2 tenant should be skipped"

        # Second call — legacy_id no longer in list
        r2 = owner.post(f"{BASE}/api/site/upgrade-design-all", timeout=60)
        assert r2.status_code == 200
        assert legacy_id not in {u["app_id"] for u in r2.json()["upgraded"]}


# ================== Presets ==================

class TestPresetsExportParity:
    def test_preset_persistence_and_export(self, owner, cleanup_ids):
        app_id = _create_tenant(owner, "TEST_iter37_presets")
        cleanup_ids.append(app_id)
        pages = _get_pages(owner, app_id)
        assert pages, "starter page missing"
        page = pages[0]
        page_id = page["page_id"]
        blocks = page["blocks"]
        assert blocks, "starter page has no blocks"

        # Apply a different preset to each of the first 4 blocks (if available)
        wanted = ["editorial", "bold", "minimal", "luxe"]
        applied = {}
        for i, b in enumerate(blocks[: len(wanted)]):
            b.setdefault("style", {})
            b["style"]["preset"] = wanted[i]
            applied[b.get("id") or i] = wanted[i]

        r = owner.patch(f"{BASE}/api/apps/{app_id}/pages/{page_id}",
                      json={"blocks": blocks}, timeout=30)
        assert r.status_code == 200, r.text[:400]

        # Reload pages and confirm preset persisted
        after = _get_pages(owner, app_id)
        target = next(p for p in after if p["page_id"] == page_id)
        presets_seen = [b.get("style", {}).get("preset") for b in target["blocks"][: len(wanted)]]
        for i, p in enumerate(wanted):
            assert presets_seen[i] == p, f"block {i} preset didn't persist: got {presets_seen[i]}"

        # Export source .zip
        rz = owner.get(f"{BASE}/api/apps/{app_id}/export/source", timeout=60)
        assert rz.status_code == 200, rz.text[:200]
        z = zipfile.ZipFile(io.BytesIO(rz.content))
        names = z.namelist()
        styles_name = next((n for n in names if n.endswith("styles.css")), None)
        assert styles_name, f"styles.css not in zip: {names[:20]}"
        css = z.read(styles_name).decode("utf-8", "ignore")
        for p in wanted:
            assert f".pr-{p}" in css, f".pr-{p} rule missing from styles.css"

        # Check index.html carries pr-<preset> on some section
        html_files = [n for n in names if n.endswith(".html")]
        assert html_files, "no html files exported"
        combined_html = "\n".join(z.read(n).decode("utf-8", "ignore") for n in html_files)
        for p in wanted:
            assert f"pr-{p}" in combined_html, f"pr-{p} class not rendered on any section: {[n for n in html_files]}"
