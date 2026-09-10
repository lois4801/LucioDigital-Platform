"""Iteration 80 — Per-template industry vitals + editor + CSV/XLSX import."""
import io
import os
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
ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
TEMPLATE_KEYS = [
    "hvac","healthcare","construction","fitness","retail","hospitality","finance",
    "it_services","creative_studio","logistics","saas","legal","education",
    "real_estate","restaurant","events","veterinary","dental","accounting",
    "landscaping","photography","automotive","beauty","insurance","pet_grooming",
    "hvac_plumbing","coworking","wellness","cleaning","music_school","nonprofit",
    "architecture","test_template",
]


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{BASE}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return sess


# --- Public vitals per template ---

def test_public_vitals_unique_per_template():
    specs = {}
    for k in TEMPLATE_KEYS:
        r = requests.get(f"{BASE}/public/vitals/{k}")
        assert r.status_code == 200, f"{k}: {r.status_code}"
        d = r.json()
        assert d["title"] != "By the numbers", f"{k} returned generic fallback"
        assert len(d["metrics"]) == 3
        assert len(d["series"]) >= 2 and len(d["series2"]) >= 2
        assert len(d["variants"]) == 2
        specs[k] = d

    titles = [d["title"] for d in specs.values()]
    assert len(set(titles)) == len(titles), "Titles must be unique across 33 templates"
    # Series signatures unique
    sigs = [(tuple(d["series"]), tuple(d["series2"])) for d in specs.values()]
    assert len(set(sigs)) == len(sigs), "Series pairs must be unique across templates"


# --- GET/PUT/reset flow ---

def test_get_vitals_returns_demo_baseline(s):
    r = s.get(f"{BASE}/apps/{APP_ID}/vitals")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "demo" in d and d["demo"]["source"] == "demo"
    assert d["title"] and len(d["metrics"]) == 3


def test_put_and_reset_vitals(s):
    # Ensure clean baseline
    s.post(f"{BASE}/apps/{APP_ID}/vitals/reset")

    payload = {
        "title": "TEST_iter80 figures",
        "metrics": [
            {"label": "A", "prefix": "", "value": 11, "suffix": "%"},
            {"label": "B", "prefix": "$", "value": 22, "suffix": ""},
            {"label": "C", "prefix": "", "value": 33, "suffix": " ms"},
        ],
        "series_label": "S1",
        "labels": ["a", "b", "c"], "series": [1, 2, 3],
        "series2_label": "S2",
        "labels2": ["x", "y"], "series2": [4, 5],
    }
    r = s.put(f"{BASE}/apps/{APP_ID}/vitals", json=payload)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["title"] == "TEST_iter80 figures"
    assert d["labels"] == ["a", "b", "c"] and d["series"] == [1, 2, 3]
    assert d["labels2"] == ["x", "y"] and d["series2"] == [4, 5]

    # GET verifies persistence
    d2 = s.get(f"{BASE}/apps/{APP_ID}/vitals").json()
    assert d2["title"] == "TEST_iter80 figures"
    assert d2["series"] == [1, 2, 3]

    # Reset restores demo
    r = s.post(f"{BASE}/apps/{APP_ID}/vitals/reset")
    assert r.status_code == 200
    d3 = r.json()
    assert d3["source"] == "demo"
    assert d3["title"] != "TEST_iter80 figures"


# --- Import: CSV ---

def test_import_csv_with_header(s):
    csv = b"Label,Value\nJan,100\nFeb,200\nMar,300\nApr,400\n"
    r = s.post(
        f"{BASE}/apps/{APP_ID}/vitals/import",
        files={"file": ("figures.csv", csv, "text/csv")},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["points"] == 4
    assert d["labels"] == ["Jan", "Feb", "Mar", "Apr"]
    assert d["series"] == [100, 200, 300, 400]
    assert d["source"] == "imported"
    assert d["imported_file"] == "figures.csv"
    s.post(f"{BASE}/apps/{APP_ID}/vitals/reset")


def test_import_csv_single_column_rejected(s):
    csv = b"OnlyOne\nJan\nFeb\n"
    r = s.post(
        f"{BASE}/apps/{APP_ID}/vitals/import",
        files={"file": ("bad.csv", csv, "text/csv")},
    )
    assert r.status_code == 400
    assert "two rows" in r.json()["detail"].lower()


def test_import_xls_rejected(s):
    r = s.post(
        f"{BASE}/apps/{APP_ID}/vitals/import",
        files={"file": ("old.xls", b"garbage", "application/vnd.ms-excel")},
    )
    assert r.status_code == 400
    assert ".xls" in r.json()["detail"].lower() or "xlsx" in r.json()["detail"].lower()


# --- Import: XLSX into series2 ---

def _xlsx_bytes(rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_import_xlsx_no_header_into_series2(s):
    xlsx = _xlsx_bytes([("Alpha", 11), ("Beta", 22), ("Gamma", 33)])
    r = s.post(
        f"{BASE}/apps/{APP_ID}/vitals/import?target=series2",
        files={"file": ("mix.xlsx", xlsx,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["points"] == 3
    assert d["labels2"] == ["Alpha", "Beta", "Gamma"]
    assert d["series2"] == [11, 22, 33]
    # series1 should remain demo-untouched
    assert d["source"] == "imported"
    s.post(f"{BASE}/apps/{APP_ID}/vitals/reset")


def test_import_xlsx_with_header_row(s):
    xlsx = _xlsx_bytes([("Label", "Value"), ("Mon", 5), ("Tue", 6), ("Wed", 7)])
    r = s.post(
        f"{BASE}/apps/{APP_ID}/vitals/import",
        files={"file": ("hdr.xlsx", xlsx,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["points"] == 3
    assert d["labels"] == ["Mon", "Tue", "Wed"]
    s.post(f"{BASE}/apps/{APP_ID}/vitals/reset")


def test_import_unauthenticated_rejected():
    csv = b"a,1\nb,2\n"
    r = requests.post(
        f"{BASE}/apps/{APP_ID}/vitals/import",
        files={"file": ("x.csv", csv, "text/csv")},
    )
    assert r.status_code in (401, 403)


# --- Public site payload reflects import ---

def test_public_site_reflects_import(s):
    # Get preview token
    site = s.get(f"{BASE}/apps/{APP_ID}/site-mode").json()
    token = site.get("preview_token") or site.get("token")
    assert token, f"No preview token: {site}"

    csv = b"Label,Value\nA1,111\nB1,222\nC1,333\n"
    r = s.post(
        f"{BASE}/apps/{APP_ID}/vitals/import",
        files={"file": ("live.csv", csv, "text/csv")},
    )
    assert r.status_code == 200

    pub = requests.get(f"{BASE}/public/site/{token}")
    assert pub.status_code == 200, pub.text
    body = pub.json()
    # search vitals anywhere in the payload
    import json as _j
    text = _j.dumps(body)
    assert "A1" in text and "111" in text, "Imported labels/values not in public payload"

    s.post(f"{BASE}/apps/{APP_ID}/vitals/reset")


# --- Teardown: leave testlab reset to demo ---

def test_zzz_leave_testlab_on_demo(s):
    r = s.post(f"{BASE}/apps/{APP_ID}/vitals/reset")
    assert r.status_code == 200
    assert r.json()["source"] == "demo"
