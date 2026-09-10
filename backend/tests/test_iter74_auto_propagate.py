"""Iter74 — always-live auto propagation, no pending state, master workspace rebrand."""
import os
import pytest
import requests
from pathlib import Path

def _load_base():
    b = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not b:
        envp = Path("/app/frontend/.env")
        if envp.exists():
            for line in envp.read_text().splitlines():
                if line.startswith("REACT_APP_BACKEND_URL="):
                    b = line.split("=", 1)[1].strip()
                    break
    return b.rstrip("/")

BASE = _load_base()
ADMIN_EMAIL = "jaybernabe@luciodigital.com"
ADMIN_PW = "Lucio2026!"
MASTER = "app_testlab"
PV = "pv_c3b797fcdafc58d4e70e320f"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, r.text
    return s


# ---- baseline snapshot (before) ----
@pytest.fixture(scope="module")
def baseline():
    r = requests.get(f"{BASE}/api/public/site/{PV}", timeout=30)
    assert r.status_code == 200
    data = r.json()
    pages = data.get("pages") or []
    blocks = {p.get("slug") or p.get("id"): len(p.get("blocks") or []) for p in pages}
    return {"pages": len(pages), "blocks": blocks, "raw": data}


# ---- auto-propagate endpoints ----
def test_auto_propagate_status(sess):
    r = sess.get(f"{BASE}/api/auto-propagate/status", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("auto") is True
    assert d.get("pending") == 0


def test_auto_propagate_run(sess):
    r = sess.post(f"{BASE}/api/auto-propagate/run", timeout=120)
    assert r.status_code == 200
    d = r.json()
    assert d.get("ok") is True
    assert d.get("templates") == 33, f"expected 33 templates, got {d.get('templates')}"


def test_auto_propagate_one_template(sess):
    r = sess.post(f"{BASE}/api/auto-propagate/templates/saas", timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert d.get("ok") is True
    assert d.get("key") == "saas"
    assert "tenants" in d


def test_templates_rollout_status_all_live(sess):
    r = sess.get(f"{BASE}/api/templates/rollout-status", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("pending", 0) == 0
    templates = d.get("templates") or []
    assert len(templates) > 0
    bad = [t for t in templates if t.get("status") != "live"]
    assert not bad, f"non-live templates: {bad[:5]}"


def test_test_lab_pending_zero(sess):
    r = sess.get(f"{BASE}/api/test-lab/pending", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("total", 0) == 0
    assert d.get("tenants") == {} or d.get("tenants") == [] or not d.get("tenants")


# ---- Test Lab tags / master workspace ----
def test_master_workspace_tags_and_description(sess):
    r = sess.get(f"{BASE}/api/apps/{MASTER}", timeout=30)
    assert r.status_code == 200
    d = r.json()
    tags = [t.lower() for t in (d.get("tags") or [])]
    assert "internal tools" in tags, f"missing 'internal tools' tag: {tags}"
    assert "website" in tags, f"missing 'website' tag: {tags}"
    assert "test" not in tags, f"'test' tag should be removed: {tags}"
    desc = (d.get("description") or "").lower()
    assert "test" not in desc and "sandbox" not in desc, f"description still references test/sandbox: {desc}"


# ---- Site Mode PUT propagates ----
def test_site_mode_put_propagates_animation_reduced(sess, baseline):
    # capture current
    r0 = sess.get(f"{BASE}/api/apps/{MASTER}/site-mode", timeout=30)
    assert r0.status_code == 200
    original = r0.json().get("site_mode") or r0.json()

    r = sess.put(f"{BASE}/api/apps/{MASTER}/site-mode", json={"animation": "reduced"}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    # propagated_to should exist somewhere in the response
    assert "propagated_to" in body or "propagated" in body, f"missing propagated_to key: {body.keys()}"

    r2 = sess.get(f"{BASE}/api/apps/{MASTER}/site-mode", timeout=30)
    sm = r2.json().get("site_mode") or r2.json()
    assert sm.get("animation") == "reduced"

    # public site still works
    r3 = requests.get(f"{BASE}/api/public/site/{PV}", timeout=30)
    assert r3.status_code == 200

    # revert
    sess.put(f"{BASE}/api/apps/{MASTER}/site-mode", json={"animation": "full"}, timeout=30)
    r4 = sess.get(f"{BASE}/api/apps/{MASTER}/site-mode", timeout=30)
    sm4 = r4.json().get("site_mode") or r4.json()
    assert sm4.get("animation") == "full"


# ---- editorial template change stays live ----
def test_editorial_template_hero_change_stays_live(sess):
    r = sess.put(f"{BASE}/api/editorial/templates/saas/hero",
                 json={"hero": "aurora-wave"}, timeout=30)
    assert r.status_code in (200, 204), r.text
    # rollout still 0 pending
    r2 = sess.get(f"{BASE}/api/templates/rollout-status", timeout=30)
    assert r2.status_code == 200
    d = r2.json()
    assert d.get("pending", 0) == 0, f"pending after hero change: {d.get('pending')}"
    saas = [t for t in (d.get("templates") or []) if t.get("key") == "saas"]
    if saas:
        assert saas[0].get("status") == "live"
    # revert
    sess.put(f"{BASE}/api/editorial/templates/saas/hero",
             json={"hero": "particle-network"}, timeout=30)


# ---- CONTENT PRESERVATION: after everything above ----
def test_content_preservation(sess, baseline):
    # Re-run one propagate to be safe
    sess.post(f"{BASE}/api/auto-propagate/run", timeout=120)
    r = requests.get(f"{BASE}/api/public/site/{PV}", timeout=30)
    assert r.status_code == 200
    data = r.json()
    pages = data.get("pages") or []
    blocks = {p.get("slug") or p.get("id"): len(p.get("blocks") or []) for p in pages}

    assert len(pages) == baseline["pages"], f"page count changed: {baseline['pages']} -> {len(pages)}"
    total_before = sum(baseline["blocks"].values())
    total_after = sum(blocks.values())
    assert total_after == total_before, f"total blocks changed: {total_before} -> {total_after}"
    # per-page identity
    assert blocks == baseline["blocks"], f"per-page block counts changed"


def test_public_site_expected_counts(baseline):
    # Spec says expect 33 pages / 366 blocks
    total = sum(baseline["blocks"].values())
    print(f"BASELINE pages={baseline['pages']} blocks={total}")
    assert baseline["pages"] == 33, f"expected 33 pages, got {baseline['pages']}"
    assert total == 366, f"expected 366 blocks, got {total}"
