"""48-hour AI lead follow-ups — queued as drafts for one-click approval."""
import os
import hmac
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import HTTPException, Depends, Request
from pydantic import BaseModel

logger = logging.getLogger("agency.followups")
FOLLOWUP_HOURS = int(os.environ.get("FOLLOWUP_HOURS", "48"))


def _now():
    return datetime.now(timezone.utc)


def _iso():
    return _now().isoformat()


def _uid(p):
    return f"{p}_{uuid.uuid4().hex[:12]}"


def _parse(ts) -> Optional[datetime]:
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


class ToggleIn(BaseModel):
    enabled: bool


class ApproveIn(BaseModel):
    body: Optional[str] = None


def register(api, db, get_current_user, get_user_app, log_activity, send_email, notify=None):
    async def _draft(app_doc: dict, msg: dict, kind: str) -> str:
        from studio import _claude
        waited = FOLLOWUP_HOURS
        if kind == "no_reply":
            ctx = (f"Nobody from the business has replied to this lead in {waited} hours. Write a short apologetic-but-confident first "
                   "follow-up: acknowledge the delay lightly, answer or address what they asked, and offer one concrete next step.")
        else:
            ctx = (f"The business replied {waited}+ hours ago and the lead has gone quiet. Write a brief, friendly nudge that adds one new "
                   "useful detail or offer, restates the next step, and makes it easy to reply with a single line.")
        system = (f"You write follow-up emails on behalf of {app_doc.get('name')} ({app_doc.get('industry', '')}). {ctx} "
                  "Under 110 words, plain text, no subject line, no placeholders like [Name] — use the real name if given, otherwise 'Hi there'. "
                  "Sign off with the business name.")
        prior = "\n\n".join(f"Our reply ({r.get('created_at')}):\n{r.get('body', '')[:800]}" for r in (msg.get("replies") or [])[-2:])
        prompt = f"Lead: {msg.get('from_name') or 'there'} <{msg.get('from_email')}>\nSubject: {msg.get('subject', '')}\nTheir message:\n{(msg.get('body') or '')[:2000]}\n\n{prior}"
        return (await _claude(system, prompt, f"followup-{msg['message_id']}")).strip()

    async def make_followup(app_id: str, message_id: str, force: bool = False) -> Optional[dict]:
        msg = await db.messages.find_one({"app_id": app_id, "message_id": message_id}, {"_id": 0})
        if not msg or not msg.get("from_email"):
            return None
        if not force and (msg.get("followup") or {}).get("status") in ("draft", "sent", "dismissed"):
            return None
        app_doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0}) or {}
        kind = "replied" if (msg.get("replies") or []) else "no_reply"
        try:
            body = await _draft(app_doc, msg, kind)
        except Exception as e:
            logger.exception("followup draft failed")
            raise HTTPException(500, f"Draft failed: {str(e)[:120]}")
        fu = {"status": "draft", "kind": kind, "body": body, "drafted_at": _iso()}
        await db.messages.update_one({"message_id": message_id}, {"$set": {"followup": fu, "updated_at": _iso()}})
        await log_activity(app_id, "ai", "lead.followup.draft", f"Follow-up draft ready for {msg.get('from_name') or msg.get('from_email')}", "info")
        return fu

    async def scan_due(limit: int = 40) -> dict:
        """Find leads that have gone quiet for FOLLOWUP_HOURS and queue one draft each."""
        cutoff = _now() - timedelta(hours=FOLLOWUP_HOURS)
        apps = await db.apps.find({"followups_enabled": True}, {"_id": 0, "app_id": 1}).to_list(500)
        queued, checked = [], 0
        for a in apps:
            msgs = await db.messages.find({"app_id": a["app_id"], "status": {"$ne": "archived"},
                                           "from_email": {"$nin": ["", None]}, "followup": {"$exists": False}},
                                          {"_id": 0}).sort("updated_at", -1).limit(80).to_list(80)
            for m in msgs:
                checked += 1
                replies = m.get("replies") or []
                last = _parse(replies[-1].get("created_at")) if replies else _parse(m.get("created_at"))
                if not last or last > cutoff:
                    continue
                try:
                    if await make_followup(a["app_id"], m["message_id"]):
                        queued.append(m["message_id"])
                except Exception:
                    logger.exception("followup queue failed")
                if len(queued) >= limit:
                    return {"checked": checked, "queued": len(queued)}
        return {"checked": checked, "queued": len(queued)}

    @api.get("/apps/{app_id}/inbox/followups")
    async def get_followups(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        pending = await db.messages.count_documents({"app_id": app_id, "followup.status": "draft"})
        return {"enabled": bool(doc.get("followups_enabled")), "hours": FOLLOWUP_HOURS, "pending_drafts": pending}

    @api.post("/apps/{app_id}/inbox/followups")
    async def set_followups(app_id: str, body: ToggleIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        await db.apps.update_one({"app_id": app_id}, {"$set": {"followups_enabled": body.enabled}})
        await log_activity(app_id, user["user_id"], "lead.followup.toggle", f"48h auto follow-ups {'enabled' if body.enabled else 'disabled'}")
        return {"enabled": body.enabled}

    @api.post("/apps/{app_id}/inbox/{message_id}/followup-draft")
    async def followup_draft(app_id: str, message_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        fu = await make_followup(app_id, message_id, force=True)
        if not fu:
            raise HTTPException(400, "This lead has no email address to follow up on")
        return await db.messages.find_one({"message_id": message_id}, {"_id": 0})

    @api.post("/apps/{app_id}/inbox/{message_id}/followup-approve")
    async def followup_approve(app_id: str, message_id: str, body: ApproveIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        msg = await db.messages.find_one({"app_id": app_id, "message_id": message_id}, {"_id": 0})
        if not msg or (msg.get("followup") or {}).get("status") != "draft":
            raise HTTPException(404, "No follow-up draft to send")
        text = (body.body or msg["followup"]["body"]).strip()[:4000]
        if not text:
            raise HTTPException(400, "Follow-up is empty")
        res = await send_email(msg["from_email"], f"Following up — {msg.get('subject', 'your enquiry')}", text)
        reply = {"reply_id": _uid("rp"), "by": f"{user.get('name') or user['email']} (follow-up)", "body": text,
                 "created_at": _iso(), "delivery": "email_sent" if res.get("status") == "sent" else "email_queued", "followup": True}
        await db.messages.update_one({"message_id": message_id}, {"$push": {"replies": reply},
                                     "$set": {"followup": {**msg["followup"], "status": "sent", "body": text, "sent_at": _iso()}, "status": "read", "updated_at": _iso()}})
        await log_activity(app_id, user["user_id"], "lead.followup.sent", f"Follow-up sent to {msg.get('from_name') or msg['from_email']}")
        return await db.messages.find_one({"message_id": message_id}, {"_id": 0})

    @api.post("/apps/{app_id}/inbox/{message_id}/followup-dismiss")
    async def followup_dismiss(app_id: str, message_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        msg = await db.messages.find_one({"app_id": app_id, "message_id": message_id}, {"_id": 0})
        if not msg or not msg.get("followup"):
            raise HTTPException(404, "No follow-up draft")
        await db.messages.update_one({"message_id": message_id}, {"$set": {"followup": {**msg["followup"], "status": "dismissed", "dismissed_at": _iso()}, "updated_at": _iso()}})
        return await db.messages.find_one({"message_id": message_id}, {"_id": 0})

    @api.post("/cron/lead-followups")
    async def cron_lead_followups(request: Request):
        # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
        secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
        auth = request.headers.get("authorization", "")
        token = auth[7:] if auth.lower().startswith("bearer ") else ""
        if not secret or not token or not hmac.compare_digest(token, secret):
            raise HTTPException(401, "Unauthorized")
        run_id = request.headers.get("x-webhook-id") or _uid("run")
        existing = await db.cron_runs.find_one({"run_id": run_id})
        if existing:
            return {"ok": True, "duplicate": True}
        await db.cron_runs.insert_one({"run_id": run_id, "job": "lead-followups", "created_at": _iso()})

        async def run():
            try:
                res = await scan_due()
                await db.cron_runs.update_one({"run_id": run_id}, {"$set": {"result": res, "finished_at": _iso()}})
            except Exception:
                logger.exception("followup cron failed")
        asyncio.create_task(run())
        return {"ok": True, "run_id": run_id}

    return {"scan_due": scan_due, "make_followup": make_followup}
