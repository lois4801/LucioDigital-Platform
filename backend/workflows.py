import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, Depends
from pydantic import BaseModel

logger = logging.getLogger("agency.workflows")

TRIGGERS = ["form_submitted", "chat_lead", "payment_succeeded", "member_invited", "page_published", "change_requested"]
OPS = {"==": lambda a, b: str(a).lower() == str(b).lower(), "!=": lambda a, b: str(a).lower() != str(b).lower(),
       "contains": lambda a, b: str(b).lower() in str(a).lower(), ">": lambda a, b: float(a or 0) > float(b or 0), "<": lambda a, b: float(a or 0) < float(b or 0)}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def uid(p):
    import uuid
    return f"{p}_{uuid.uuid4().hex[:12]}"


def tpl(s: str, payload: dict) -> str:
    out = str(s or "")
    for k, v in payload.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


class WorkflowIn(BaseModel):
    name: str
    trigger: str
    conditions: List[Dict[str, Any]] = []  # {field, op, value}
    actions: List[Dict[str, Any]] = []     # {type: email|db_write|webhook|notify, ...}
    enabled: bool = True


class TestRunIn(BaseModel):
    payload: Optional[Dict[str, Any]] = None


class ResendIn(BaseModel):
    api_key: str
    sender: str


SAMPLE = {"form_submitted": {"name": "Jane Doe", "email": "jane@example.com", "message": "Interested in the Pro plan", "tier": "pro", "country": "Canada"},
          "chat_lead": {"name": "Website visitor", "email": "", "message": "Do you offer refunds?"},
          "payment_succeeded": {"email": "client@example.com", "plan": "Pro", "amount": 99, "tier": "pro"},
          "member_invited": {"email": "editor@example.com", "role": "editor"},
          "page_published": {"page": "Home", "slug": "/"},
          "change_requested": {"name": "Client", "email": "client@example.com", "title": "Update hero copy", "details": "Please change the headline."}}


def register(api, db, get_current_user, get_user_app, log_activity):

    EMAIL_BASE_URL = "https://integrations.emergentagent.com"
    EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY", "")
    EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "OmniStack AI")
    EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")

    def _assert_safe_email(subject: str, text: str):
        low = f"{subject}\n{text}".lower()
        for p in ("password", "cvv", "card number", "seed phrase", "social security"):
            if p in low:
                raise ValueError("Email content not allowed")
        if "<form" in low or "<input" in low or "http://" in low:
            raise ValueError("Email content not allowed")

    async def send_email(to: str, subject: str, body: str) -> dict:
        if not EMAIL_KEY or not to or "@" not in to:
            return {"status": "queued", "reason": "email not configured" if not EMAIL_KEY else "no recipient"}
        try:
            _assert_safe_email(subject, body)
        except ValueError as e:
            return {"status": "failed", "detail": str(e)}
        from html import escape
        html = (f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif;color:#0F172A">'
                f'<p style="white-space:pre-wrap">{escape(body)}</p>'
                f'<p style="font-size:12px;color:#888">Sent by {escape(EMAIL_FROM_NAME)}. We never ask for passwords or payment details by email.</p></td></tr></table>')
        payload = {"to": [to], "subject": subject[:200], "html": html, "from_name": EMAIL_FROM_NAME}
        if EMAIL_REPLY_TO:
            payload["contact_email"] = EMAIL_REPLY_TO
        try:
            async with httpx.AsyncClient(timeout=30) as http:
                r = await http.post(f"{EMAIL_BASE_URL}/api/v1/email/send", headers={"X-Email-Key": EMAIL_KEY}, json=payload)
            return {"status": "sent" if r.status_code in (200, 202) else "failed", "detail": None if r.status_code < 300 else r.text[:160], "id": (r.json().get("id") if r.status_code < 300 else None)}
        except Exception as e:
            return {"status": "failed", "detail": str(e)[:120]}

    @api.get("/settings/email")
    async def get_email_cfg(user: dict = Depends(get_current_user)):
        return {"configured": bool(EMAIL_KEY), "from_name": EMAIL_FROM_NAME, "reply_to": EMAIL_REPLY_TO}

    async def run_workflow(wf: dict, payload: dict, test: bool = False) -> dict:
        steps = []
        for c in wf.get("conditions", []):
            ok = OPS.get(c.get("op", "=="), OPS["=="])(payload.get(c.get("field"), ""), c.get("value"))
            steps.append({"kind": "condition", "detail": f"{c.get('field')} {c.get('op')} {c.get('value')}", "result": "pass" if ok else "stop"})
            if not ok:
                return {"status": "skipped", "steps": steps}
        for a in wf.get("actions", []):
            t = a.get("type")
            try:
                if t == "email":
                    to = str(payload.get("email") or "")  # recipient always from server-side event data
                    res = await send_email(to, tpl(a.get("subject", "Update from {{name}}"), payload), tpl(a.get("body", ""), payload))
                    steps.append({"kind": "email", "detail": f"to {to or '(no email in event)'}", "result": res["status"], "info": res.get("reason") or res.get("detail")})
                elif t == "db_write":
                    await db.workflow_records.insert_one({"record_id": uid("rec"), "app_id": wf["app_id"], "collection": a.get("collection", "records"), "data": payload, "test": test, "created_at": now_iso()})
                    steps.append({"kind": "db_write", "detail": a.get("collection", "records"), "result": "written"})
                elif t == "webhook":
                    url = a.get("url", "")
                    if not url.startswith("http"):
                        raise ValueError("invalid url")
                    async with httpx.AsyncClient(timeout=10) as http:
                        r = await http.post(url, json={"event": wf["trigger"], "payload": payload, "test": test})
                    steps.append({"kind": "webhook", "detail": url, "result": f"HTTP {r.status_code}"})
                elif t == "notify":
                    await log_activity(wf["app_id"], "workflow", "workflow.notify", tpl(a.get("message", "Workflow fired"), payload), "info")
                    steps.append({"kind": "notify", "detail": tpl(a.get("message", ""), payload), "result": "logged"})
                else:
                    steps.append({"kind": t, "result": "unknown action"})
            except Exception as e:
                steps.append({"kind": t, "result": "error", "info": str(e)[:120]})
        return {"status": "completed", "steps": steps}

    async def fire_event(app_id: str, trigger: str, payload: dict):
        wfs = await db.workflows.find({"app_id": app_id, "trigger": trigger, "enabled": True}, {"_id": 0}).to_list(50)
        for wf in wfs:
            try:
                res = await run_workflow(wf, payload)
                await db.workflows.update_one({"workflow_id": wf["workflow_id"]}, {"$set": {"last_run": {**res, "at": now_iso(), "payload": payload}}, "$inc": {"runs": 1}})
            except Exception:
                logger.exception("workflow failed")

    @api.get("/apps/{app_id}/workflows")
    async def list_wf(app_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        return {"workflows": await db.workflows.find({"app_id": app_id}, {"_id": 0}).sort("created_at", -1).to_list(100), "triggers": TRIGGERS, "samples": SAMPLE}

    @api.post("/apps/{app_id}/workflows")
    async def create_wf(app_id: str, body: WorkflowIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        if body.trigger not in TRIGGERS:
            raise HTTPException(400, "Unknown trigger")
        doc = {"workflow_id": uid("wf"), "app_id": app_id, **body.model_dump(), "runs": 0, "last_run": None, "created_at": now_iso()}
        await db.workflows.insert_one(dict(doc))
        await log_activity(app_id, user["user_id"], "workflow.created", f"Workflow '{body.name}' created")
        return doc

    @api.put("/apps/{app_id}/workflows/{wid}")
    async def update_wf(app_id: str, wid: str, body: WorkflowIn, user: dict = Depends(get_current_user)):
        doc_app = await get_user_app(app_id, user)
        from locks import assert_item_editable, consume_if_grant
        grant = await assert_item_editable(db, doc_app, "workflow", wid, user, body.name)
        await db.workflows.update_one({"app_id": app_id, "workflow_id": wid}, {"$set": body.model_dump()})
        await consume_if_grant(db, grant, app_id, user, log_activity)
        return await db.workflows.find_one({"workflow_id": wid}, {"_id": 0})

    @api.delete("/apps/{app_id}/workflows/{wid}")
    async def delete_wf(app_id: str, wid: str, user: dict = Depends(get_current_user)):
        doc_app = await get_user_app(app_id, user)
        from locks import assert_item_editable
        await assert_item_editable(db, doc_app, "workflow", wid, user)
        await db.workflows.delete_one({"app_id": app_id, "workflow_id": wid})
        return {"ok": True}

    @api.post("/apps/{app_id}/workflows/{wid}/test")
    async def test_wf(app_id: str, wid: str, body: TestRunIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        wf = await db.workflows.find_one({"app_id": app_id, "workflow_id": wid}, {"_id": 0})
        if not wf:
            raise HTTPException(404, "Workflow not found")
        payload = body.payload or SAMPLE.get(wf["trigger"], {})
        res = await run_workflow(wf, payload, test=True)
        await db.workflows.update_one({"workflow_id": wid}, {"$set": {"last_run": {**res, "at": now_iso(), "payload": payload, "test": True}}})
        return res

    # ===== DEPLOYMENT HUB =====
    @api.get("/deployments")
    async def deployments(user: dict = Depends(get_current_user)):
        memberships = await db.memberships.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(500)
        apps = await db.apps.find({"$or": [{"owner_id": user["user_id"]}, {"app_id": {"$in": [m["app_id"] for m in memberships]}}]}, {"_id": 0}).sort("created_at", -1).to_list(500)
        out = []
        for a in apps:
            pages = await db.pages.count_documents({"app_id": a["app_id"]})
            out.append({"app_id": a["app_id"], "name": a["name"], "kind": a.get("kind", "website"), "color": a.get("color"), "status": a.get("status"),
                        "published": bool(a.get("preview_enabled") and a.get("preview_token")), "preview_token": a.get("preview_token"),
                        "custom_domain": a.get("custom_domain"), "domain_status": a.get("domain_status"), "github": a.get("github"), "github_autosync": a.get("github_autosync", False),
                        "plan": a.get("plan"), "pages": pages, "updated_at": a.get("updated_at")})
        return out

    return {"fire_event": fire_event, "send_email": send_email}
