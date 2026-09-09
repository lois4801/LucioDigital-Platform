"""Iter61 — CTA modal form system across all industry templates.

Covers auto-provisioning, industry-aware field specs, public submit + inbox lead,
email-field protection, per-tenant isolation, rescan future-proof detection,
and client-editor simplified mode.
"""
import os
import time
import pytest
import requests

def _base():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        # Load from frontend/.env
        try:
            with open("/app/frontend/.env") as fh:
                for line in fh:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        return line.split("=", 1)[1].strip().rstrip("/")
        except Exception:
            pass
        raise RuntimeError("REACT_APP_BACKEND_URL not set")
    return url.rstrip("/")

BASE_URL = _base()
API = f"{BASE_URL}/api"

ADMIN = {"email": "jaybernabe@luciodigital.com", "password": "Lucio2026!"}
EDITOR = {"email": "client.editor@example.com", "password": "ClientEdit2026!"}


# --------- Expected industry field specs per Part 2 ----------
EXPECTED = {
    "real_estate": [
        ("name", "text", True), ("email", "email", True), ("phone", "phone", False),
        ("interest", "select", True), ("contact_time", "text", False), ("message", "textarea", False),
    ],
    "education": [
        ("name", "text", True), ("email", "email", True), ("phone", "phone", False),
        ("tour_date", "date", True), ("tour_time", "select", True),
        ("attendees", "number", True), ("questions", "textarea", False),
    ],
    "healthcare": [
        ("name", "text", True), ("email", "email", True), ("phone", "phone", True),
        ("reason", "textarea", True), ("appt_date", "date", True),
        ("appt_time", "select", True), ("payment_type", "toggle", True),
    ],
    "legal": [
        ("name", "text", True), ("email", "email", True), ("phone", "phone", True),
        ("matter", "select", True), ("consult_date", "date", True),
        ("consult_time", "select", True), ("description", "textarea", True),
    ],
    "hospitality": [
        ("name", "text", True), ("email", "email", True), ("phone", "phone", False),
        ("res_date", "date", True), ("party_size", "number", True), ("requests", "textarea", False),
    ],
    "construction": [
        ("name", "text", True), ("email", "email", True), ("phone", "phone", True),
        ("project_type", "text", True), ("start_date", "date", False),
        ("budget", "select", False), ("description", "textarea", True),
    ],
}

FALLBACK_EXPECTED = [
    ("name", "text", True), ("email", "email", True), ("phone", "phone", False),
    ("service", "text", False), ("preferred_date", "date", False),
    ("preferred_time", "select", False), ("message", "textarea", False),
]


@pytest.fixture(scope="session")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def created_apps(admin):
    """Track apps created so we can purge them at the end."""
    ids = []
    yield ids
    for aid in ids:
        try:
            admin.post(f"{API}/apps/{aid}/archive", json={"archived": True}, timeout=10)
            admin.delete(f"{API}/apps/{aid}/purge", timeout=15)
        except Exception:
            pass


def _create_tenant(admin, name, template_key, created_apps):
    r = admin.post(f"{API}/apps", json={
        "name": name, "industry": template_key, "template_key": template_key,
        "kind": "website", "status": "development", "tags": [], "color": "#111",
    }, timeout=30)
    assert r.status_code in (200, 201), f"create failed {r.status_code} {r.text}"
    doc = r.json()
    aid = doc["app_id"]
    created_apps.append(aid)
    return aid


# ---------- Auto-provisioning ----------
@pytest.mark.parametrize("tpl", ["real_estate", "education", "healthcare", "legal", "hospitality", "construction", "saas"])
def test_auto_provision_per_template(admin, created_apps, tpl):
    aid = _create_tenant(admin, f"TEST_{tpl}_{int(time.time()*1000)%100000}", tpl, created_apps)
    r = admin.get(f"{API}/apps/{aid}/cta-forms", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    forms = data["forms"]
    assert len(forms) >= 1, f"expected at least one CTA form for {tpl}"
    for f in forms:
        # Non-qualifying labels like 'Patient portal' or 'Our story' must NOT be provisioned.
        assert f["label"].strip(), "label empty"
        low = f["label"].lower()
        assert not any(x in low for x in ["patient portal", "our story", "about us", "read more"]), \
            f"Non-qualifying label got a form: {f['label']}"


# ---------- Industry-aware field specs ----------
@pytest.mark.parametrize("tpl", list(EXPECTED.keys()))
def test_industry_field_specs(admin, created_apps, tpl):
    aid = _create_tenant(admin, f"TEST_spec_{tpl}_{int(time.time()*1000)%100000}", tpl, created_apps)
    r = admin.get(f"{API}/apps/{aid}/cta-forms", timeout=15)
    assert r.status_code == 200
    forms = r.json()["forms"]
    assert forms
    fields = forms[0]["fields"]
    actual = [(f["name"], f["type"], f["required"]) for f in fields]
    assert actual == EXPECTED[tpl], f"{tpl} mismatch:\n  expected {EXPECTED[tpl]}\n  got {actual}"

    # Options checks
    by = {f["name"]: f for f in fields}
    if tpl == "real_estate":
        assert by["interest"]["options"] == ["Buying", "Selling", "Investing"]
    if tpl == "education":
        assert by["tour_time"]["options"] == ["Morning 9am-12pm", "Afternoon 12pm-3pm", "Late Afternoon 3pm-5pm"]
    if tpl == "healthcare":
        assert by["payment_type"]["options"] == ["Insurance", "Self-Pay"]
        assert by["appt_time"]["options"] == ["Morning", "Afternoon", "Evening"]
    if tpl == "legal":
        assert by["matter"]["options"] == ["Family", "Corporate", "Real Estate", "Criminal", "Other"]
    if tpl == "construction":
        assert by["budget"]["options"] == ["Under $10K", "$10K-$50K", "$50K-$100K", "$100K+"]


def test_fallback_field_spec(admin, created_apps):
    """A tenant on a non-mapped industry gets the FALLBACK field set."""
    aid = _create_tenant(admin, f"TEST_fallback_{int(time.time()*1000)%100000}", "saas", created_apps)
    r = admin.get(f"{API}/apps/{aid}/cta-forms", timeout=15)
    forms = r.json()["forms"]
    assert forms
    actual = [(f["name"], f["type"], f["required"]) for f in forms[0]["fields"]]
    assert actual == FALLBACK_EXPECTED, f"fallback mismatch: {actual}"


# ---------- Public site: forms exposure + submit + lead ----------
def _enable_preview(admin, aid):
    r = admin.post(f"{API}/apps/{aid}/preview/regenerate", timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["preview_token"]


def test_public_forms_submit_and_lead(admin, created_apps):
    aid = _create_tenant(admin, f"TEST_pub_{int(time.time()*1000)%100000}", "healthcare", created_apps)
    tok = _enable_preview(admin, aid)

    # Public forms fetch (no auth)
    r = requests.get(f"{API}/public/site/{tok}/cta-forms", timeout=15)
    assert r.status_code == 200
    forms_map = r.json()["forms"]
    assert forms_map, "public forms empty"
    key, form = next(iter(forms_map.items()))
    form_id = form["form_id"]
    form_label = form["label"]

    # Missing required -> 400
    r_bad = requests.post(f"{API}/public/site/{tok}/cta-forms/{form_id}/submit",
                          json={"values": {"name": "Test"}}, timeout=15)
    assert r_bad.status_code == 400, f"expected 400 got {r_bad.status_code} {r_bad.text}"

    # Full submit
    values = {
        "name": "TEST Submitter", "email": "test.submit@example.com", "phone": "4165550188",
        "reason": "Yearly checkup", "appt_date": "2026-02-15", "appt_time": "Morning",
        "payment_type": "Insurance",
    }
    r_ok = requests.post(f"{API}/public/site/{tok}/cta-forms/{form_id}/submit",
                         json={"values": values}, timeout=15)
    assert r_ok.status_code == 200, r_ok.text
    j = r_ok.json()
    assert j.get("ok") is True
    assert "24 hours" in (j.get("success_message") or "")

    # Confirm lead appears in tenant inbox with form_label
    time.sleep(0.5)
    r_msgs = admin.get(f"{API}/apps/{aid}/inbox", timeout=15)
    assert r_msgs.status_code == 200
    payload_msgs = r_msgs.json()
    msgs = payload_msgs if isinstance(payload_msgs, list) else payload_msgs.get("messages", [])
    hits = [m for m in msgs if m.get("form_label") == form_label or m.get("cta_form_id") == form_id]
    assert hits, f"no lead with form_label={form_label}: sample={msgs[:2]}"


# ---------- Email field protection & type validation ----------
def test_email_field_protection_and_bad_type(admin, created_apps):
    aid = _create_tenant(admin, f"TEST_email_{int(time.time()*1000)%100000}", "real_estate", created_apps)
    forms = admin.get(f"{API}/apps/{aid}/cta-forms", timeout=15).json()["forms"]
    form_id = forms[0]["form_id"]
    fields = forms[0]["fields"]

    # Try removing email
    no_email = [f for f in fields if f["name"] != "email"]
    payload = {"fields": [{"name": f["name"], "label": f["label"], "type": f["type"],
                           "required": f["required"], "placeholder": f.get("placeholder", ""),
                           "options": f.get("options", [])} for f in no_email]}
    r = admin.put(f"{API}/apps/{aid}/cta-forms/{form_id}", json=payload, timeout=15)
    assert r.status_code == 400, f"expected 400 removing email got {r.status_code}"

    # Try unsupported type
    bad = [{"name": f["name"], "label": f["label"], "type": f["type"],
            "required": f["required"], "placeholder": "", "options": f.get("options", [])} for f in fields]
    bad[0]["type"] = "hologram"
    r2 = admin.put(f"{API}/apps/{aid}/cta-forms/{form_id}", json={"fields": bad}, timeout=15)
    assert r2.status_code == 400, f"expected 400 bad type got {r2.status_code}"


# ---------- Per-tenant isolation ----------
def test_per_tenant_isolation(admin, created_apps):
    a = _create_tenant(admin, f"TEST_isoA_{int(time.time()*1000)%100000}", "hospitality", created_apps)
    b = _create_tenant(admin, f"TEST_isoB_{int(time.time()*1000)%100000}", "hospitality", created_apps)
    fa = admin.get(f"{API}/apps/{a}/cta-forms", timeout=15).json()["forms"]
    fb = admin.get(f"{API}/apps/{b}/cta-forms", timeout=15).json()["forms"]
    assert fa and fb
    fid = fa[0]["form_id"]
    original_b_title = fb[0]["title"]

    r = admin.put(f"{API}/apps/{a}/cta-forms/{fid}",
                  json={"title": "ISOLATION-TEST-TITLE"}, timeout=15)
    assert r.status_code == 200

    fb2 = admin.get(f"{API}/apps/{b}/cta-forms", timeout=15).json()["forms"]
    assert fb2[0]["title"] == original_b_title, "tenant B was mutated by tenant A edit!"
    fa2 = admin.get(f"{API}/apps/{a}/cta-forms", timeout=15).json()["forms"]
    assert any(f["form_id"] == fid and f["title"] == "ISOLATION-TEST-TITLE" for f in fa2)


# ---------- Rescan detects new qualifying CTAs ----------
def test_rescan_adds_new_form_with_fallback(admin, created_apps):
    aid = _create_tenant(admin, f"TEST_scan_{int(time.time()*1000)%100000}", "saas", created_apps)
    # Add a new page with a qualifying CTA
    r_pages = admin.get(f"{API}/apps/{aid}/pages", timeout=15)
    assert r_pages.status_code == 200
    pages = r_pages.json()
    # Grab home
    home = next((p for p in pages if p.get("slug") == "/"), pages[0])
    new_blocks = list(home.get("blocks") or []) + [
        {"type": "cta", "props": {"title": "Ready?", "cta": "Request a callback"}}
    ]
    r_upd = admin.patch(f"{API}/apps/{aid}/pages/{home['page_id']}",
                        json={"blocks": new_blocks}, timeout=15)
    assert r_upd.status_code == 200, r_upd.text

    before = admin.get(f"{API}/apps/{aid}/cta-forms", timeout=15).json()["forms"]
    r = admin.post(f"{API}/apps/{aid}/cta-forms/scan", timeout=15)
    assert r.status_code == 200
    after = r.json()["forms"]
    assert len(after) >= len(before)
    new_form = next((f for f in after if f["label"].lower() == "request a callback"), None)
    assert new_form is not None, f"rescan did not add 'Request a callback': labels={[f['label'] for f in after]}"
    # Fallback field set
    actual = [(f["name"], f["type"], f["required"]) for f in new_form["fields"]]
    # saas maps to fallback set
    assert actual == FALLBACK_EXPECTED, f"new form did not use fallback: {actual}"

    # Non-qualifying label should not create a form
    non_qual = list(new_blocks) + [{"type": "cta", "props": {"title": "History", "cta": "Our story"}}]
    admin.patch(f"{API}/apps/{aid}/pages/{home['page_id']}", json={"blocks": non_qual}, timeout=15)
    r2 = admin.post(f"{API}/apps/{aid}/cta-forms/scan", timeout=15)
    labels = [f["label"].lower() for f in r2.json()["forms"]]
    assert "our story" not in labels, "Non-qualifying 'Our story' created a form!"


# ---------- Client editor simplified mode ----------
def test_client_editor_simplified(admin, created_apps):
    aid = _create_tenant(admin, f"TEST_editor_{int(time.time()*1000)%100000}", "real_estate", created_apps)
    # Invite client editor
    r_inv = admin.post(f"{API}/apps/{aid}/members",
                       json={"email": EDITOR["email"], "role": "editor"}, timeout=15)
    assert r_inv.status_code == 200, r_inv.text

    editor_sess = requests.Session()
    r_login = editor_sess.post(f"{API}/auth/login", json=EDITOR, timeout=15)
    if r_login.status_code != 200:
        pytest.skip(f"editor login failed: {r_login.status_code} {r_login.text}")

    r = editor_sess.get(f"{API}/apps/{aid}/cta-forms", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("simplified") is True, f"expected simplified=true got {data.get('simplified')}"
    assert data.get("can_edit") is True

    # Editor can PUT a title change
    fid = data["forms"][0]["form_id"]
    r_put = editor_sess.put(f"{API}/apps/{aid}/cta-forms/{fid}",
                            json={"title": "Edited by client editor"}, timeout=15)
    assert r_put.status_code == 200, r_put.text

    # Editor sees other tenants' forms as 403/404
    # Create another tenant as admin, do not invite editor
    other_aid = _create_tenant(admin, f"TEST_other_{int(time.time()*1000)%100000}", "legal", created_apps)
    r_other = editor_sess.get(f"{API}/apps/{other_aid}/cta-forms", timeout=15)
    assert r_other.status_code in (403, 404), f"editor should not see other tenant, got {r_other.status_code}"
