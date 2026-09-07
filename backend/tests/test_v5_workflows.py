"""V5: Workflow Engine, Deployment Hub, App-Mode Chat refine, Inbox email reply delivery."""
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


BASE = os.environ.get("REACT_APP_BACKEND_URL", _read_env()).rstrip("/")
API = f"{BASE}/api"
EMAIL = "jaybernabe@luciodigital.com"
PASSWORD = "Lucio2026!"

NEXUS_ID_FILE = "/app/memory/nexus_id"
BLUEPRINT_APP_ID = "app_627d86264eac"


@pytest.fixture(scope="session")
def nexus_id():
    with open(NEXUS_ID_FILE) as f:
        return f.read().strip()


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    r = sess.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    if tok:
        sess.headers["Authorization"] = f"Bearer {tok}"
    return sess


# ============ Workflows CRUD ============
def test_list_workflows_shape(s, nexus_id):
    r = s.get(f"{API}/apps/{nexus_id}/workflows")
    assert r.status_code == 200, r.text
    d = r.json()
    assert isinstance(d["workflows"], list)
    assert d["triggers"] == ["form_submitted", "chat_lead", "payment_succeeded", "member_invited", "page_published"]
    assert "form_submitted" in d["samples"]


@pytest.fixture(scope="session")
def created_wf(s, nexus_id):
    body = {
        "name": "TEST_QA_v5_workflow",
        "trigger": "form_submitted",
        "conditions": [{"field": "message", "op": "contains", "value": "pro"}],
        "actions": [
            {"type": "notify", "message": "New lead from {{name}}"},
            {"type": "db_write", "collection": "leads"},
            {"type": "email", "subject": "Thanks {{name}}", "body": "We got your message: {{message}}"},
        ],
        "enabled": True,
    }
    r = s.post(f"{API}/apps/{nexus_id}/workflows", json=body)
    assert r.status_code in (200, 201), r.text
    doc = r.json()
    assert doc["workflow_id"].startswith("wf_")
    yield doc
    s.delete(f"{API}/apps/{nexus_id}/workflows/{doc['workflow_id']}")


def test_create_workflow_invalid_trigger(s, nexus_id):
    r = s.post(f"{API}/apps/{nexus_id}/workflows", json={"name": "x", "trigger": "bogus", "conditions": [], "actions": []})
    assert r.status_code == 400


def test_test_workflow_completed(s, nexus_id, created_wf):
    payload = {"name": "QA", "email": "delivered@resend.dev", "message": "pro plan please"}
    r = s.post(f"{API}/apps/{nexus_id}/workflows/{created_wf['workflow_id']}/test", json={"payload": payload})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "completed"
    kinds = {s["kind"]: s for s in d["steps"]}
    assert "email" in kinds
    assert kinds["email"]["result"] in ("sent", "queued", "failed")
    assert "db_write" in kinds
    assert kinds["db_write"]["result"] == "written"


def test_test_workflow_skipped(s, nexus_id, created_wf):
    r = s.post(f"{API}/apps/{nexus_id}/workflows/{created_wf['workflow_id']}/test", json={"payload": {"name": "x", "email": "a@b.co", "message": "hello"}})
    assert r.status_code == 200
    assert r.json()["status"] == "skipped"


def test_put_toggle(s, nexus_id, created_wf):
    body = dict(created_wf)
    body["enabled"] = False
    body = {k: body[k] for k in ("name", "trigger", "conditions", "actions", "enabled")}
    r = s.put(f"{API}/apps/{nexus_id}/workflows/{created_wf['workflow_id']}", json=body)
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    body["enabled"] = True
    r = s.put(f"{API}/apps/{nexus_id}/workflows/{created_wf['workflow_id']}", json=body)
    assert r.json()["enabled"] is True


# ============ End-to-end trigger via public contact ============
def test_e2e_form_submitted_trigger(s, nexus_id, created_wf):
    # get preview_token
    app = s.get(f"{API}/apps/{nexus_id}").json()
    token = app.get("preview_token")
    assert token
    if not app.get("preview_enabled"):
        s.post(f"{API}/apps/{nexus_id}/preview/toggle", json={"enabled": True})
    r0 = s.get(f"{API}/apps/{nexus_id}/workflows").json()
    wf_before = next(w for w in r0["workflows"] if w["workflow_id"] == created_wf["workflow_id"])
    runs_before = wf_before.get("runs", 0)
    r = requests.post(f"{API}/public/contact/{token}", json={"name": "QA v5 E2E", "email": "delivered@resend.dev", "message": "I want the pro tier"})
    assert r.status_code == 200, r.text
    time.sleep(2)
    r1 = s.get(f"{API}/apps/{nexus_id}/workflows").json()
    wf_after = next(w for w in r1["workflows"] if w["workflow_id"] == created_wf["workflow_id"])
    assert wf_after.get("runs", 0) > runs_before
    assert wf_after.get("last_run") is not None


# ============ Deployments ============
def test_deployments_list(s):
    r = s.get(f"{API}/deployments")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 1
    row = rows[0]
    for k in ("app_id", "name", "published", "preview_token", "custom_domain", "github"):
        assert k in row


def test_settings_email_configured(s):
    r = s.get(f"{API}/settings/email")
    assert r.status_code == 200
    assert r.json()["configured"] is True


# ============ Refine-app (Claude, ONE call only) ============
def test_refine_app_once(s):
    # get blueprint to pick first screen/component
    bp = s.get(f"{API}/apps/{BLUEPRINT_APP_ID}/blueprint").json()
    assert bp and bp.get("screens"), "Blueprint app must have spec"
    screen = bp["screens"][0]["name"]
    comp = (bp["screens"][0].get("components") or [{"label": "Table"}])[0].get("label", "Table")
    r = s.post(
        f"{API}/apps/{BLUEPRINT_APP_ID}/ai/refine-app",
        json={"message": "Add a status filter dropdown to the appointments table", "target": {"screen": screen, "component": comp}},
        timeout=300,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["spec"]["screens"]
    assert isinstance(d["summary"], str) and len(d["summary"]) > 0
    # verify chat history
    r2 = s.get(f"{API}/apps/{BLUEPRINT_APP_ID}/ai/app-chat")
    assert r2.status_code == 200
    hist = r2.json()
    roles = [m["role"] for m in hist]
    assert "user" in roles and "assistant" in roles


# ============ Inbox reply email delivery ============
def test_inbox_reply_email_sent(s, nexus_id):
    # ensure we have a message with a real from_email (fire a contact submission)
    app = s.get(f"{API}/apps/{nexus_id}").json()
    token = app.get("preview_token")
    requests.post(f"{API}/public/contact/{token}", json={"name": "Email Reply QA", "email": "delivered@resend.dev", "message": "test reply email"})
    time.sleep(1)
    inb = s.get(f"{API}/apps/{nexus_id}/inbox").json()
    msg = next((m for m in inb["messages"] if m.get("from_email")), None)
    assert msg, "need a message with from_email"
    r = s.post(f"{API}/apps/{nexus_id}/inbox/{msg['message_id']}/reply", json={"body": "Thanks for reaching out"})
    assert r.status_code == 200, r.text
    m = r.json()
    last = m["replies"][-1]
    assert last["delivery"] in ("email_sent", "email_queued"), last
    print(f"[reply delivery] {last['delivery']}")
