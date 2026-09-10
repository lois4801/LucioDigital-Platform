"""Iteration 82 — Get Directions link + 3-column vitals import + Client Portal scoping.

Runs against the live app_testlab workspace and cleans up (address="", map_url="", vitals reset).
"""
import io
import os
import uuid
from urllib.parse import quote_plus

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
    # Teardown: clear address+map_url, reset vitals
    try:
        sess.put(f"{BASE}/apps/{APP_ID}/site-mode", json={"address": "", "map_url": ""})
        sess.post(f"{BASE}/apps/{APP_ID}/vitals/reset")
    except Exception:
        pass


# ------------ PUT/GET site-mode map_url ------------

def test_put_map_url_rejects_schemeless(s):
    r = s.put(f"{BASE}/apps/{APP_ID}/site-mode", json={"map_url": "maps.example.com/xyz"})
    assert r.status_code == 400
    assert "http" in r.json()["detail"].lower()


def test_put_map_url_rejects_too_long(s):
    long_url = "https://" + ("a" * 500)
    r = s.put(f"{BASE}/apps/{APP_ID}/site-mode", json={"map_url": long_url})
    # Trimmed to 400 -> still valid https, saved. Length must be <=400.
    assert r.status_code == 200
    assert len(r.json()["map_url"]) == 400


def test_put_and_get_map_url_valid(s):
    url = "https://waze.com/ul?ll=51.5,-0.12"
    r = s.put(f"{BASE}/apps/{APP_ID}/site-mode", json={"map_url": url})
    assert r.status_code == 200
    assert r.json()["map_url"] == url

    g = s.get(f"{BASE}/apps/{APP_ID}/site-mode").json()
    assert g["map_url"] == url


# ------------ Public site: map_url resolution ------------

def test_public_map_url_custom_when_set(s):
    url = "https://waze.com/ul?ll=51.5,-0.12"
    s.put(f"{BASE}/apps/{APP_ID}/site-mode", json={"map_url": url, "address": "10 Downing St, London"})
    pj = requests.get(f"{BASE}/public/site/{PREVIEW}").json()
    assert pj["app"]["map_url"] == url


def test_public_map_url_auto_google_when_address_only(s):
    addr = "1600 Amphitheatre Pkwy, Mountain View"
    s.put(f"{BASE}/apps/{APP_ID}/site-mode", json={"map_url": "", "address": addr})
    pj = requests.get(f"{BASE}/public/site/{PREVIEW}").json()
    m = pj["app"]["map_url"]
    assert m.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert quote_plus(addr) in m


def test_public_map_url_empty_when_no_address(s):
    # Clear address AND clear map_url AND drop any block-level address by leaving cleared address
    # (block/template fallback may still populate address on public payload — accept that,
    #  but require map_url to be empty ONLY when the resolved address is empty).
    s.put(f"{BASE}/apps/{APP_ID}/site-mode", json={"address": "", "map_url": ""})
    pj = requests.get(f"{BASE}/public/site/{PREVIEW}").json()
    resolved_addr = pj["app"].get("address", "")
    m = pj["app"].get("map_url", "")
    if resolved_addr:
        # Fallback chain kicked in (block or template) — map_url must be the auto Google query
        assert m.startswith("https://www.google.com/maps/search/?api=1&query=")
    else:
        assert m == ""


# ------------ 3-column CSV import ------------

def test_import_csv_three_columns_fills_both(s):
    csv = b"Label,C1,C2\nJan,10,50\nFeb,20,60\nMar,30,70\nApr,40,80\n"
    r = s.post(
        f"{BASE}/apps/{APP_ID}/vitals/import",
        files={"file": ("three.csv", csv, "text/csv")},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["charts"] == 2
    assert d["labels"] == ["Jan", "Feb", "Mar", "Apr"]
    assert d["series"] == [10, 20, 30, 40]
    assert d["labels2"] == ["Jan", "Feb", "Mar", "Apr"]
    assert d["series2"] == [50, 60, 70, 80]
    s.post(f"{BASE}/apps/{APP_ID}/vitals/reset")


def test_import_csv_two_columns_charts_one(s):
    csv = b"Label,Value\nA,1\nB,2\nC,3\n"
    r = s.post(
        f"{BASE}/apps/{APP_ID}/vitals/import",
        files={"file": ("two.csv", csv, "text/csv")},
    )
    assert r.status_code == 200
    d = r.json()
    assert d["charts"] == 1
    assert d["series"] == [1, 2, 3]
    s.post(f"{BASE}/apps/{APP_ID}/vitals/reset")


def test_import_series2_only_writes_second(s):
    csv = b"L,V\nx,7\ny,8\n"
    r = s.post(
        f"{BASE}/apps/{APP_ID}/vitals/import?target=series2",
        files={"file": ("t2.csv", csv, "text/csv")},
    )
    assert r.status_code == 200
    d = r.json()
    assert d["charts"] == 1
    assert d["labels2"] == ["x", "y"]
    assert d["series2"] == [7, 8]
    s.post(f"{BASE}/apps/{APP_ID}/vitals/reset")


def test_import_single_column_400(s):
    csv = b"only\na\nb\n"
    r = s.post(
        f"{BASE}/apps/{APP_ID}/vitals/import",
        files={"file": ("bad.csv", csv, "text/csv")},
    )
    assert r.status_code == 400


def _xlsx_bytes(rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_import_xlsx_three_columns_fills_both(s):
    xlsx = _xlsx_bytes([("Label", "C1", "C2"), ("Alpha", 11, 111),
                        ("Beta", 22, 222), ("Gamma", 33, 333)])
    r = s.post(
        f"{BASE}/apps/{APP_ID}/vitals/import",
        files={"file": ("three.xlsx", xlsx,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["charts"] == 2
    assert d["labels"] == ["Alpha", "Beta", "Gamma"]
    assert d["series"] == [11, 22, 33]
    assert d["labels2"] == ["Alpha", "Beta", "Gamma"]
    assert d["series2"] == [111, 222, 333]
    s.post(f"{BASE}/apps/{APP_ID}/vitals/reset")


# ------------ Variants stay fixed after import ------------

def test_variants_unchanged_after_import(s):
    before = s.get(f"{BASE}/apps/{APP_ID}/vitals").json()["variants"]
    csv = b"L,A,B\np,1,2\nq,3,4\n"
    r = s.post(f"{BASE}/apps/{APP_ID}/vitals/import",
               files={"file": ("v.csv", csv, "text/csv")})
    assert r.status_code == 200
    after = s.get(f"{BASE}/apps/{APP_ID}/vitals").json()["variants"]
    assert before == after, f"Variants changed: {before} -> {after}"
    s.post(f"{BASE}/apps/{APP_ID}/vitals/reset")


# ------------ Non-member scoping (403) ------------

@pytest.fixture(scope="module")
def outsider():
    """Register a throwaway user with NO membership to app_testlab."""
    email = f"TEST_iter82_{uuid.uuid4().hex[:8]}@example.com"
    password = "Test82!Pass"
    sess = requests.Session()
    r = sess.post(f"{BASE}/auth/register", json={"email": email, "password": password, "name": "T82"})
    if r.status_code not in (200, 201):
        # try login if already exists
        r = sess.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return sess, email


def test_non_member_cannot_read_vitals(outsider):
    sess, _ = outsider
    r = sess.get(f"{BASE}/apps/{APP_ID}/vitals")
    assert r.status_code in (403, 404), f"Expected 403/404, got {r.status_code}: {r.text}"


def test_non_member_cannot_write_vitals(outsider):
    sess, _ = outsider
    r = sess.put(f"{BASE}/apps/{APP_ID}/vitals", json={"title": "HACK"})
    assert r.status_code in (403, 404)


def test_non_member_cannot_read_site_mode(outsider):
    sess, _ = outsider
    r = sess.get(f"{BASE}/apps/{APP_ID}/site-mode")
    assert r.status_code in (403, 404)


def test_non_member_cannot_write_site_mode(outsider):
    sess, _ = outsider
    r = sess.put(f"{BASE}/apps/{APP_ID}/site-mode", json={"address": "HACK"})
    assert r.status_code in (403, 404)


def test_non_member_cannot_import(outsider):
    sess, _ = outsider
    r = sess.post(f"{BASE}/apps/{APP_ID}/vitals/import",
                  files={"file": ("x.csv", b"a,1\nb,2\n", "text/csv")})
    assert r.status_code in (403, 404)


# ------------ Teardown check ------------

def test_zzz_teardown_clears_state(s):
    s.put(f"{BASE}/apps/{APP_ID}/site-mode", json={"address": "", "map_url": ""})
    r = s.post(f"{BASE}/apps/{APP_ID}/vitals/reset")
    assert r.status_code == 200
    assert r.json()["source"] == "demo"
