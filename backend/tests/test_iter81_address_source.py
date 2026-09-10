"""Iteration 81 — Tenant address (Site Mode → map + contact/footer + fallback chain)
and chart Source labels (source_label / source_label2). All tests run against the
live app_testlab workspace; teardown resets vitals and clears the address.
"""
import os
import time
import pytest
import requests


def _read_env():
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _read_env()).rstrip("/") + "/api"
APP_ID = "app_testlab"
PREVIEW = "pv_c3b797fcdafc58d4e70e320f"
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{BASE}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    yield sess
    # Teardown: reset vitals and clear address
    try:
        sess.post(f"{BASE}/apps/{APP_ID}/vitals/reset")
        sess.put(f"{BASE}/apps/{APP_ID}/site-mode", json={"address": ""})
    except Exception:
        pass


# ---------- Address: GET returns both address + template_address ----------

def test_site_mode_returns_address_and_template_address(s):
    r = s.get(f"{BASE}/apps/{APP_ID}/site-mode")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "address" in d
    assert "template_address" in d
    # template_address should be non-empty for a template-backed tenant
    assert isinstance(d["template_address"], str)


# ---------- Address: PUT saves, trims, limits, propagates to blocks ----------

def test_put_address_saves_and_propagates_to_contact_footer(s):
    new_addr = "  221B Baker Street, London  "  # padded — should be trimmed
    r = s.put(f"{BASE}/apps/{APP_ID}/site-mode", json={"address": new_addr})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["address"] == "221B Baker Street, London"

    # GET reflects it
    r2 = s.get(f"{BASE}/apps/{APP_ID}/site-mode")
    assert r2.json()["address"] == "221B Baker Street, London"

    # Public site: app.address equals it AND at least one contact/footer block has it
    p = requests.get(f"{BASE}/public/site/{PREVIEW}")
    assert p.status_code == 200
    pj = p.json()
    assert pj["app"]["address"] == "221B Baker Street, London"
    hits = 0
    total_with_addr = 0
    for pg in pj.get("pages", []):
        for b in pg.get("blocks") or []:
            if b.get("type") in ("contact", "footer"):
                props = b.get("props") or {}
                if "address" in props:
                    total_with_addr += 1
                    if props["address"] == "221B Baker Street, London":
                        hits += 1
    assert total_with_addr > 0, "Expected at least one contact/footer block with an address prop"
    assert hits == total_with_addr, f"Expected all {total_with_addr} address blocks updated; only {hits} were"


def test_put_address_trims_to_160_chars(s):
    long_addr = "A" * 300
    r = s.put(f"{BASE}/apps/{APP_ID}/site-mode", json={"address": long_addr})
    assert r.status_code == 200
    assert len(r.json()["address"]) == 160


# ---------- Address fallback chain ----------

def test_address_fallback_to_contact_block_then_template(s):
    # Clear tenant address; contact/footer blocks were overwritten in a prior test to the new value
    r = s.put(f"{BASE}/apps/{APP_ID}/site-mode", json={"address": ""})
    assert r.status_code == 200
    assert r.json()["address"] == ""

    p = requests.get(f"{BASE}/public/site/{PREVIEW}").json()
    fallback = p["app"]["address"]
    assert fallback, "Fallback address must never be blank for a template-backed tenant"
    # Should fall back to a contact/footer block (which was set to 160 A's OR to Baker St)
    # OR to template sample if no block has address.
    sm = s.get(f"{BASE}/apps/{APP_ID}/site-mode").json()
    template_addr = sm.get("template_address") or ""

    # Confirm fallback is either a block address or the template address
    block_addrs = []
    for pg in p.get("pages", []):
        for b in pg.get("blocks") or []:
            if b.get("type") in ("contact", "footer"):
                a = (b.get("props") or {}).get("address")
                if isinstance(a, str) and a.strip():
                    block_addrs.append(a.strip())
    assert fallback in block_addrs or fallback == template_addr, (
        f"Fallback '{fallback}' not from blocks {block_addrs} nor template '{template_addr}'"
    )


# ---------- Vitals source labels persist + reset ----------

def test_put_vitals_source_labels_persist_and_public_exposes(s):
    payload = {"source_label": "Internal CRM", "source_label2": "Billing export"}
    r = s.put(f"{BASE}/apps/{APP_ID}/vitals", json=payload)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["source_label"] == "Internal CRM"
    assert d["source_label2"] == "Billing export"

    # GET returns them
    g = s.get(f"{BASE}/apps/{APP_ID}/vitals").json()
    assert g["source_label"] == "Internal CRM"
    assert g["source_label2"] == "Billing export"

    # Public payload exposes them
    pj = requests.get(f"{BASE}/public/site/{PREVIEW}").json()
    v = pj["app"]["vitals"]
    assert v["source_label"] == "Internal CRM"
    assert v["source_label2"] == "Billing export"


def test_reset_vitals_clears_source_labels(s):
    r = s.post(f"{BASE}/apps/{APP_ID}/vitals/reset")
    assert r.status_code == 200
    d = r.json()
    assert d["source_label"] == ""
    assert d["source_label2"] == ""

    # Public payload has blanks
    pj = requests.get(f"{BASE}/public/site/{PREVIEW}").json()
    v = pj["app"]["vitals"]
    assert v.get("source_label", "") == ""
    assert v.get("source_label2", "") == ""


# ---------- Spec includes empty source labels by default ----------

def test_public_spec_has_empty_source_labels_by_default():
    r = requests.get(f"{BASE}/public/vitals/hvac")
    assert r.status_code == 200
    d = r.json()
    assert "source_label" in d and d["source_label"] == ""
    assert "source_label2" in d and d["source_label2"] == ""
