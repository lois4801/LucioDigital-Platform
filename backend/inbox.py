import os
import re
import json
import base64
import asyncio
import logging
import hmac
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, Depends, Request, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr

logger = logging.getLogger("agency.inbox")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def uid(prefix):
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ContactIn(BaseModel):
    name: str
    email: EmailStr
    message: str
    subject: Optional[str] = None
    form_id: Optional[str] = None


class InboxPatch(BaseModel):
    status: Optional[str] = None  # unread | read | archived
    starred: Optional[bool] = None


class ReplyAttachment(BaseModel):
    name: str
    url: str


class ReplyIn(BaseModel):
    body: str
    attachments: Optional[List[ReplyAttachment]] = None


class GithubTokenIn(BaseModel):
    token: str


class GithubPushIn(BaseModel):
    repo_name: Optional[str] = None
    private: bool = True


class AutoSyncIn(BaseModel):
    enabled: bool


class LaneIn(BaseModel):
    lane: str


AGENCY_COPY_EMAILS = [e.strip() for e in os.environ.get(
    "AGENCY_COPY_EMAILS", "JLBUSINESS2020@gmail.com,jaybernabe@luciodigital.com").split(",") if e.strip()]


EMBED_JS = """(function(){var s=document.currentScript;var t=s.getAttribute('data-token');var o=s.getAttribute('data-origin')||new URL(s.src).origin;
var f=document.createElement('iframe');f.src=o+'/embed/chat/'+t;f.title='Chat';f.setAttribute('allow','microphone; autoplay');
f.style.cssText='position:fixed;right:0;bottom:0;width:420px;height:640px;max-width:100vw;max-height:100vh;border:0;background:transparent;z-index:2147483000;color-scheme:normal';
document.body.appendChild(f);})();"""


def register(api, db, get_current_user, get_user_app, log_activity, build_export_files, wf=None):
    wf = wf or {}

    # ===== LEADS / INBOX =====
    async def _new_message(app_id: str, source: str, name: str, email: str, subject: str, body: str, session_id: str = None, meta: dict = None):
        from lead_class import classify
        cls = classify(name, email, body, subject, source, meta)
        doc = {"message_id": uid("msg"), "app_id": app_id, "source": source, "from_name": name, "from_email": email,
               "subject": subject, "body": body, "status": "unread", "starred": False, "replies": [],
               "session_id": session_id, "score": None, "score_reason": None, "hot": False,
               "lane": cls["lane"], "lane_reasons": cls["reasons"], "lane_manual": False,
               "review": cls.get("review", False), "review_reasons": cls.get("review_reasons", []),
               "created_at": now_iso(), "updated_at": now_iso()}
        await db.messages.insert_one(dict(doc))
        await log_activity(app_id, "public", "lead.new", f"New {source} lead from {name or email}", "info")
        asyncio.create_task(score_message(doc["message_id"]))
        return doc

    async def score_message(message_id: str) -> Optional[dict]:
        """AI lead scoring 0-100 (intent, budget signals, urgency, fit)."""
        msg = await db.messages.find_one({"message_id": message_id}, {"_id": 0})
        if not msg or not os.environ.get("EMERGENT_LLM_KEY"):
            return None
        try:
            from studio import _claude, _parse_json
            app_doc = await db.apps.find_one({"app_id": msg["app_id"]}, {"_id": 0, "name": 1, "industry": 1, "description": 1}) or {}
            system = ("You score inbound leads for an agency's client business. Return ONLY JSON {\"score\": 0-100 integer, \"intent\": \"buy|evaluate|support|spam|other\", \"reason\": \"<=18 words\"}. "
                      "High scores: clear buying intent, budget/timeline mentioned, specific service asked, business email. Low: spam, vague, support-only.")
            prompt = f"Business: {app_doc.get('name')} ({app_doc.get('industry', '')}). {app_doc.get('description', '')}\nSource: {msg['source']}\nFrom: {msg.get('from_name')} <{msg.get('from_email')}>\nSubject: {msg.get('subject')}\nMessage:\n{msg.get('body', '')[:2500]}"
            data = _parse_json(await _claude(system, prompt, f"score-{message_id}"))
            score = max(0, min(100, int(data.get("score", 0))))
            upd = {"score": score, "score_reason": str(data.get("reason", ""))[:160], "intent": data.get("intent", "other"), "hot": score >= 70, "scored_at": now_iso()}
            await db.messages.update_one({"message_id": message_id}, {"$set": upd})
            if score >= 70:
                await log_activity(msg["app_id"], "ai", "lead.hot", f"Hot lead ({score}): {msg.get('from_name') or msg.get('from_email')}", "info")
            return upd
        except Exception:
            logger.exception("lead scoring failed")
            return None

    @api.post("/apps/{app_id}/inbox/score")
    async def score_inbox(app_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        pending = await db.messages.find({"app_id": app_id, "score": None}, {"_id": 0, "message_id": 1}).limit(15).to_list(15)
        results = await asyncio.gather(*[score_message(m["message_id"]) for m in pending])
        return {"scored": sum(1 for r in results if r), "remaining": max(0, await db.messages.count_documents({"app_id": app_id, "score": None}))}

    @api.post("/apps/{app_id}/inbox/{message_id}/score")
    async def score_one(app_id: str, message_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        r = await score_message(message_id)
        if not r:
            raise HTTPException(500, "Scoring unavailable")
        return await db.messages.find_one({"message_id": message_id}, {"_id": 0})

    @api.post("/public/contact/{token}")
    async def public_contact(token: str, body: ContactIn):
        app_doc = await db.apps.find_one({"preview_token": token, "preview_enabled": True}, {"_id": 0})
        if not app_doc:
            raise HTTPException(404, "Site not found")
        app_id = app_doc["app_id"]
        route = {}
        if body.form_id:
            # Routing is resolved from the stored block, never from the public payload.
            page = await db.pages.find_one({"app_id": app_id, "blocks.id": body.form_id}, {"_id": 0, "blocks": 1, "slug": 1})
            block = next((b for b in (page or {}).get("blocks", []) if b.get("id") == body.form_id), None)
            props = (block or {}).get("props") or {}
            if block:
                route = {"form_id": body.form_id, "form_name": str(props.get("heading") or "Form")[:80],
                         "form_page": (page or {}).get("slug"),
                         "notify_email": (props.get("notify_email") or "").strip().lower() or None,
                         "assignee_id": props.get("assignee") or None}
                if route["assignee_id"] and not route["notify_email"]:
                    member = await db.users.find_one({"user_id": route["assignee_id"]}, {"_id": 0, "email": 1, "name": 1})
                    if member:
                        route["notify_email"] = member["email"]
                        route["assignee_name"] = member.get("name")
        doc = await _new_message(app_id, "contact", body.name.strip()[:120], body.email.lower(), (body.subject or f"Website inquiry from {body.name.strip()}")[:160], body.message.strip()[:4000])
        if route.get("form_id"):
            await db.messages.update_one({"message_id": doc["message_id"]}, {"$set": {"routing": route}})
        if route.get("notify_email") and wf.get("send_email"):
            try:
                await wf["send_email"](route["notify_email"], f"[{route['form_name']}] {doc['subject']}",
                                       f"New submission from {doc['from_name']} <{doc['from_email']}>\nForm: {route['form_name']} ({route.get('form_page') or ''})\n\n{doc['body']}")
            except Exception:
                logger.exception("form routing email failed")
        if wf.get("fire_event"):
            await wf["fire_event"](app_id, "form_submitted", {"name": body.name.strip(), "email": body.email.lower(), "message": body.message.strip()[:500], "subject": doc["subject"], **{k: v for k, v in route.items() if v}})
        return {"ok": True, "message_id": doc["message_id"], "routed_to": route.get("notify_email")}

    async def upsert_chat_lead(app_id: str, session_id: str, user_msg: str, reply: str):
        existing = await db.messages.find_one({"app_id": app_id, "session_id": session_id})
        line = f"Visitor: {user_msg}\nAssistant: {reply}"
        if existing:
            await db.messages.update_one({"message_id": existing["message_id"]},
                                         {"$set": {"body": (existing["body"] + "\n\n" + line)[-8000:], "updated_at": now_iso(), "status": "unread" if existing["status"] != "archived" else "archived"}})
        else:
            await _new_message(app_id, "chat", "Website visitor", "", f"Chat: {user_msg[:60]}", line, session_id)
            if wf.get("fire_event"):
                await wf["fire_event"](app_id, "chat_lead", {"name": "Website visitor", "email": "", "message": user_msg[:500]})

    @api.get("/inbox")
    async def global_inbox(status: Optional[str] = None, user: dict = Depends(get_current_user)):
        memberships = await db.memberships.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(500)
        apps = await db.apps.find({"$or": [{"owner_id": user["user_id"]}, {"app_id": {"$in": [m["app_id"] for m in memberships]}}]}, {"_id": 0, "app_id": 1, "name": 1, "color": 1}).to_list(500)
        names = {a["app_id"]: a for a in apps}
        await _classify_pending()
        q = {"app_id": {"$in": list(names)}}
        if status:
            q["status"] = status
        msgs = await db.messages.find(q, {"_id": 0}).sort([("hot", -1), ("score", -1), ("updated_at", -1)]).limit(300).to_list(300)
        for m in msgs:
            m["app_name"] = names.get(m["app_id"], {}).get("name")
            m["app_color"] = names.get(m["app_id"], {}).get("color")
        unread = await db.messages.count_documents({"app_id": {"$in": list(names)}, "status": "unread",
                                                    "lane": {"$ne": "test"}})
        return {"messages": msgs, "unread": unread}

    async def _classify_pending(app_id: Optional[str] = None) -> int:
        """Backfills lane/review on any lead that has never been classified (all tenants, lazily)."""
        from lead_class import classify
        from pymongo import UpdateOne
        q = {"lane": {"$exists": False}}
        if app_id:
            q["app_id"] = app_id
        rows = await db.messages.find(q, {"_id": 0}).to_list(500)
        ops = []
        for m in rows:
            if m.get("kind") == "edit_request":
                # Client change requests come from authenticated editors — always a real lane.
                cls = {"lane": "real", "reasons": [], "review": False, "review_reasons": []}
            else:
                cls = classify(m.get("from_name"), m.get("from_email"), m.get("body"), m.get("subject"),
                               m.get("source"), m.get("meta"))
            ops.append(UpdateOne({"message_id": m["message_id"]}, {"$set": {
                "lane": cls["lane"], "lane_reasons": cls["reasons"], "lane_manual": False,
                "review": cls.get("review", False), "review_reasons": cls.get("review_reasons", [])}}))
        if ops:
            await db.messages.bulk_write(ops, ordered=False)
        return len(rows)

    @api.post("/apps/{app_id}/inbox/classify")
    async def classify_inbox(app_id: str, rerun: bool = False, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        if rerun:
            await db.messages.update_many({"app_id": app_id, "lane_manual": {"$ne": True}},
                                          {"$unset": {"lane": "", "review": ""}})
        moved = await _classify_pending(app_id)
        return {"classified": moved,
                "real": await db.messages.count_documents({"app_id": app_id, "lane": "real"}),
                "test": await db.messages.count_documents({"app_id": app_id, "lane": "test"})}

    @api.get("/apps/{app_id}/inbox/insights")
    async def lead_insights(app_id: str, days: int = 90, user: dict = Depends(get_current_user)):
        """Which pages, forms and channels produce the highest-scoring real leads."""
        await get_user_app(app_id, user)
        await _classify_pending(app_id)
        days = max(1, min(365, days))
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.messages.find({"app_id": app_id, "lane": {"$ne": "test"},
                                       "kind": {"$ne": "edit_request"},
                                       "created_at": {"$gte": since}}, {"_id": 0}).to_list(2000)

        def bucket(rows_, key):
            out = {}
            for m in rows_:
                k = key(m) or "—"
                b = out.setdefault(k, {"key": k, "leads": 0, "scored": 0, "score_total": 0,
                                       "hot": 0, "replied": 0, "best": 0, "invites": 0})
                b["leads"] += 1
                if m.get("score") is not None:
                    b["scored"] += 1
                    b["score_total"] += m["score"]
                    b["best"] = max(b["best"], m["score"])
                if m.get("hot"):
                    b["hot"] += 1
                if m.get("replies"):
                    b["replied"] += 1
                if m.get("booking_invite"):
                    b["invites"] += 1
            for b in out.values():
                b["avg_score"] = round(b["score_total"] / b["scored"]) if b["scored"] else None
                b["reply_rate"] = round(100 * b["replied"] / b["leads"]) if b["leads"] else 0
                b.pop("score_total")
            return sorted(out.values(), key=lambda b: (b["avg_score"] or -1, b["leads"]), reverse=True)[:12]

        pages = bucket(rows, lambda m: (m.get("routing") or {}).get("form_page"))
        forms = bucket(rows, lambda m: (m.get("routing") or {}).get("form_name"))
        sources = bucket(rows, lambda m: m.get("source"))
        scored = [m for m in rows if m.get("score") is not None]
        return {"days": days, "leads": len(rows), "hot": sum(1 for m in rows if m.get("hot")),
                "avg_score": round(sum(m["score"] for m in scored) / len(scored)) if scored else None,
                "pages": pages, "forms": forms, "sources": sources,
                "best": sorted(scored, key=lambda m: m["score"], reverse=True)[:5] and [
                    {"name": m.get("from_name") or m.get("from_email"), "score": m["score"],
                     "page": (m.get("routing") or {}).get("form_page") or m.get("source"),
                     "message_id": m["message_id"]}
                    for m in sorted(scored, key=lambda m: m["score"], reverse=True)[:5]]}

    async def _archive_stale_test(app_id: Optional[str] = None, days: int = 30) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q = {"lane": "test", "status": {"$ne": "archived"},
             "$or": [{"updated_at": {"$lt": cutoff}}, {"created_at": {"$lt": cutoff}}]}
        if app_id:
            q["app_id"] = app_id
        res = await db.messages.update_many(q, {"$set": {"status": "archived", "auto_archived_at": now_iso()}})
        return res.modified_count

    @api.post("/apps/{app_id}/inbox/archive-test")
    async def archive_test_leads(app_id: str, days: int = 30, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        days = max(1, min(365, days))
        n = await _archive_stale_test(app_id, days)
        if n:
            await log_activity(app_id, user["user_id"], "lead.autoarchive",
                               f"Archived {n} test lead(s) older than {days} days")
        return {"archived": n, "days": days}

    async def _run_archive_all(days: int):
        try:
            n = await _archive_stale_test(None, days)
            logger.info("auto-archived %s stale test lead(s) across all tenants", n)
        except Exception:
            logger.exception("test lead auto-archive failed")

    @api.post("/cron/archive-test-leads")
    async def cron_archive_test_leads(request: Request, tasks: BackgroundTasks, days: int = 30):
        # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
        secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
        auth = request.headers.get("Authorization", "")
        if not secret or not auth.startswith("Bearer ") or not hmac.compare_digest(auth[7:], secret):
            raise HTTPException(401, "Unauthorized")
        tasks.add_task(_run_archive_all, max(1, min(365, days)))
        return {"accepted": True, "run_id": request.headers.get("X-Webhook-Id") or uid("run")}

    @api.patch("/apps/{app_id}/inbox/{message_id}/lane")
    async def set_lane(app_id: str, message_id: str, body: LaneIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        if body.lane not in ("real", "test"):
            raise HTTPException(400, "lane must be 'real' or 'test'")
        msg = await db.messages.find_one({"app_id": app_id, "message_id": message_id}, {"_id": 0})
        if not msg:
            raise HTTPException(404, "Message not found")
        await db.messages.update_one({"message_id": message_id}, {"$set": {
            "lane": body.lane, "lane_manual": True,
            "lane_reasons": [f"moved to {body.lane} by {user.get('name') or user['email']}"],
            "updated_at": now_iso()}})
        await log_activity(app_id, user["user_id"], "lead.lane",
                           f"{msg.get('from_name') or msg.get('from_email') or 'Lead'} moved to {body.lane} leads")
        return await db.messages.find_one({"message_id": message_id}, {"_id": 0})

    @api.post("/apps/{app_id}/inbox/{message_id}/booking-invite")
    async def booking_invite(app_id: str, message_id: str, user: dict = Depends(get_current_user)):
        """Emails a real lead an invitation to book, and copies the agency's own addresses."""
        app_doc = await get_user_app(app_id, user)
        msg = await db.messages.find_one({"app_id": app_id, "message_id": message_id}, {"_id": 0})
        if not msg:
            raise HTTPException(404, "Message not found")
        if not msg.get("from_email"):
            raise HTTPException(400, "This lead has no email address")
        if msg.get("lane") == "test":
            raise HTTPException(400, "That lead is in the Test tab — move it to Real Leads first")
        link = f"{FRONTEND_URL}/p/{app_doc.get('preview_token')}#contact" if app_doc.get("preview_token") else FRONTEND_URL
        body = (f"Hi {msg.get('from_name') or 'there'},\n\nThanks for getting in touch with {app_doc.get('name')}. "
                f"Pick a time that suits you and we'll take it from there:\n\n{link}\n\n"
                f"If none of the slots work, just reply to this email.\n\n{app_doc.get('name')}")
        subject = f"Book a time with {app_doc.get('name')}"
        sent_to, copies = None, []
        if not wf.get("send_email"):
            raise HTTPException(503, "Email delivery is not configured on this workspace")
        if wf.get("send_email"):
            try:
                await wf["send_email"](msg["from_email"], subject, body)
                sent_to = msg["from_email"]
                for addr in AGENCY_COPY_EMAILS:
                    await wf["send_email"](addr, f"[copy] {subject} — {msg.get('from_name') or msg['from_email']}", body)
                    copies.append(addr)
            except Exception:
                logger.exception("booking invite email failed")
                raise HTTPException(502, "Could not send the invitation just now")
        invite = {"sent_at": now_iso(), "to": sent_to, "copies": copies, "link": link,
                  "by": user.get("name") or user["email"]}
        await db.messages.update_one({"message_id": message_id},
                                     {"$set": {"booking_invite": invite, "status": "read", "updated_at": now_iso()}})
        await log_activity(app_id, user["user_id"], "lead.booking_invite",
                           f"Booking invite sent to {msg.get('from_name') or msg['from_email']}")
        return {"invite": invite, "message": await db.messages.find_one({"message_id": message_id}, {"_id": 0})}

    @api.get("/apps/{app_id}/inbox")
    async def app_inbox(app_id: str, status: Optional[str] = None, lane: Optional[str] = None,
                        user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        await _classify_pending(app_id)
        q = {"app_id": app_id}
        if status:
            q["status"] = status
        if lane in ("real", "test"):
            q["lane"] = lane
        msgs = await db.messages.find(q, {"_id": 0}).sort([("hot", -1), ("score", -1), ("updated_at", -1)]).limit(300).to_list(300)
        live = {"status": {"$ne": "archived"}}
        counts = {
            "real": await db.messages.count_documents({"app_id": app_id, "lane": "real", **live}),
            "test": await db.messages.count_documents({"app_id": app_id, "lane": "test", **live}),
            "archived": await db.messages.count_documents({"app_id": app_id, "status": "archived"}),
            "review": await db.messages.count_documents({"app_id": app_id, "lane": "real",
                                                         "$or": [{"score": {"$lt": 30}}, {"review": True}], **live}),
            "priority": await db.messages.count_documents({"app_id": app_id, "lane": "real", "score": {"$gt": 60}, **live}),
        }
        unread = await db.messages.count_documents({"app_id": app_id, "status": "unread", "lane": {"$ne": "test"}})
        hot = await db.messages.count_documents({"app_id": app_id, "hot": True, "lane": {"$ne": "test"}, **live})
        return {"messages": msgs, "unread": unread, "hot": hot, "counts": counts}

    @api.patch("/apps/{app_id}/inbox/{message_id}")
    async def patch_message(app_id: str, message_id: str, body: InboxPatch, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        upd = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
        if "status" in upd and upd["status"] not in ("unread", "read", "archived"):
            raise HTTPException(400, "Bad status")
        upd["updated_at"] = now_iso()
        await db.messages.update_one({"app_id": app_id, "message_id": message_id}, {"$set": upd})
        return await db.messages.find_one({"message_id": message_id}, {"_id": 0})

    @api.post("/apps/{app_id}/inbox/{message_id}/ai-draft")
    async def ai_draft(app_id: str, message_id: str, user: dict = Depends(get_current_user)):
        app_doc = await get_user_app(app_id, user)
        msg = await db.messages.find_one({"app_id": app_id, "message_id": message_id}, {"_id": 0})
        if not msg:
            raise HTTPException(404, "Message not found")
        from studio import _claude
        system = (f"You write short, warm, professional email replies on behalf of {app_doc['name']} ({app_doc.get('industry', '')}). "
                  "Answer the lead's actual questions, propose one concrete next step (call, quote, booking), keep it under 120 words, plain text, no subject line, sign off with the business name.")
        prompt = f"Lead name: {msg.get('from_name') or 'there'}\nSubject: {msg.get('subject', '')}\nMessage:\n{(msg.get('body') or '')[:3000]}"
        try:
            draft = (await _claude(system, prompt, f"draft-{message_id}")).strip()
        except Exception as e:
            raise HTTPException(500, f"Draft failed: {str(e)[:120]}")
        return {"draft": draft}

    @api.post("/apps/{app_id}/inbox/{message_id}/reply")
    async def reply_message(app_id: str, message_id: str, body: ReplyIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        msg = await db.messages.find_one({"app_id": app_id, "message_id": message_id})
        if not msg:
            raise HTTPException(404, "Message not found")
        reply = {"reply_id": uid("rp"), "by": user.get("name") or user["email"], "body": body.body.strip()[:4000], "created_at": now_iso(), "delivery": "in_app"}
        atts = [{"name": a.name.strip()[:160], "url": a.url.strip()[:500]} for a in (body.attachments or [])][:10]
        if atts:
            reply["attachments"] = atts
        if not reply["body"] and not atts:
            raise HTTPException(400, "Add a message or an attachment")
        if msg.get("from_email") and wf.get("send_email"):
            email_body = reply["body"]
            if atts:
                email_body += "\n\nAttachments:\n" + "\n".join(f"· {a['name']}: {FRONTEND_URL}{a['url']}" for a in atts)
            res = await wf["send_email"](msg["from_email"], f"Re: {msg.get('subject', 'your message')}", email_body)
            reply["delivery"] = "email_sent" if res["status"] == "sent" else "email_queued"
        await db.messages.update_one({"message_id": message_id}, {"$push": {"replies": reply}, "$set": {"status": "read", "updated_at": now_iso()}})
        await log_activity(app_id, user["user_id"], "lead.replied", f"Replied to {msg.get('from_name') or 'lead'}")
        return await db.messages.find_one({"message_id": message_id}, {"_id": 0})

    @api.delete("/apps/{app_id}/inbox/{message_id}")
    async def delete_message(app_id: str, message_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        await db.messages.delete_one({"app_id": app_id, "message_id": message_id})
        return {"ok": True}

    # ===== CHAT EMBED =====
    @api.get("/public/embed.js")
    async def embed_js():
        return Response(content=EMBED_JS, media_type="application/javascript", headers={"Cache-Control": "public, max-age=3600"})

    # ===== GITHUB SYNC =====
    async def _gh_token() -> str:
        s = await db.settings.find_one({"key": "github_token"}, {"_id": 0})
        return (s or {}).get("value") or os.environ.get("GITHUB_TOKEN", "")

    @api.get("/settings/github")
    async def github_status(user: dict = Depends(get_current_user)):
        s = await db.settings.find_one({"key": "github_token"}, {"_id": 0})
        return {"connected": bool((s or {}).get("value")), "login": (s or {}).get("login"), "avatar": (s or {}).get("avatar")}

    @api.post("/settings/github")
    async def github_connect(body: GithubTokenIn, user: dict = Depends(get_current_user)):
        token = body.token.strip()
        async with httpx.AsyncClient(timeout=20) as http:
            r = await http.get("https://api.github.com/user", headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
        if r.status_code != 200:
            raise HTTPException(400, "GitHub rejected this token. Use a Personal Access Token with 'repo' scope.")
        u = r.json()
        await db.settings.update_one({"key": "github_token"}, {"$set": {"value": token, "login": u.get("login"), "avatar": u.get("avatar_url"), "updated_at": now_iso()}}, upsert=True)
        return {"connected": True, "login": u.get("login"), "avatar": u.get("avatar_url")}

    @api.delete("/settings/github")
    async def github_disconnect(user: dict = Depends(get_current_user)):
        await db.settings.delete_one({"key": "github_token"})
        return {"connected": False}

    async def push_to_github(app_id: str, user_id: str, repo_name: Optional[str], private: bool) -> dict:
        token = await _gh_token()
        app_doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0})
        files = await build_export_files(app_doc)
        slug = re.sub(r"[^a-z0-9-]+", "-", (repo_name or app_doc["name"]).lower()).strip("-") or "site"
        if not token:
            # MOCKED until a token is connected
            result = {"status": "mocked", "repo": f"github.com/<your-account>/{slug}", "files": len(files), "commit": None,
                      "message": "No GitHub token connected — push simulated. Connect a token in Handoff → GitHub Sync to push for real.", "pushed_at": now_iso()}
            await db.apps.update_one({"app_id": app_id}, {"$set": {"github": result}})
            await log_activity(app_id, user_id, "github.push", f"MOCKED push of {len(files)} files to {slug}", "warning")
            return result
        H = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        async with httpx.AsyncClient(timeout=60, headers=H) as http:
            me = (await http.get("https://api.github.com/user")).json()
            login = me["login"]
            r = await http.get(f"https://api.github.com/repos/{login}/{slug}")
            if r.status_code == 404:
                r = await http.post("https://api.github.com/user/repos", json={"name": slug, "private": private, "auto_init": True, "description": f"{app_doc['name']} — exported from Lois-Tech"})
                if r.status_code not in (200, 201):
                    raise HTTPException(500, f"GitHub repo create failed: {r.text[:160]}")
                await asyncio.sleep(2)
            repo = (await http.get(f"https://api.github.com/repos/{login}/{slug}")).json()
            branch = repo.get("default_branch", "main")
            ref = await http.get(f"https://api.github.com/repos/{login}/{slug}/git/ref/heads/{branch}")
            if ref.status_code != 200:
                raise HTTPException(500, "Could not read default branch")
            head_sha = ref.json()["object"]["sha"]
            base_tree = (await http.get(f"https://api.github.com/repos/{login}/{slug}/git/commits/{head_sha}")).json()["tree"]["sha"]
            tree = []
            for path, content in files.items():
                b = await http.post(f"https://api.github.com/repos/{login}/{slug}/git/blobs", json={"content": base64.b64encode(content.encode()).decode(), "encoding": "base64"})
                tree.append({"path": path, "mode": "100644", "type": "blob", "sha": b.json()["sha"]})
            t = await http.post(f"https://api.github.com/repos/{login}/{slug}/git/trees", json={"base_tree": base_tree, "tree": tree})
            c = await http.post(f"https://api.github.com/repos/{login}/{slug}/git/commits", json={"message": f"Lois-Tech export · {now_iso()[:16]}", "tree": t.json()["sha"], "parents": [head_sha]})
            await http.patch(f"https://api.github.com/repos/{login}/{slug}/git/refs/heads/{branch}", json={"sha": c.json()["sha"]})
        result = {"status": "pushed", "repo": repo["html_url"], "files": len(files), "commit": c.json()["sha"][:7], "branch": branch, "pushed_at": now_iso()}
        await db.apps.update_one({"app_id": app_id}, {"$set": {"github": result}})
        await log_activity(app_id, user_id, "github.push", f"Pushed {len(files)} files to {repo['full_name']}")
        return result

    @api.post("/apps/{app_id}/github/push")
    async def github_push(app_id: str, body: GithubPushIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        return await push_to_github(app_id, user["user_id"], body.repo_name, body.private)

    @api.post("/apps/{app_id}/github/autosync")
    async def github_autosync(app_id: str, body: AutoSyncIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        await db.apps.update_one({"app_id": app_id}, {"$set": {"github_autosync": body.enabled}})
        return await db.apps.find_one({"app_id": app_id}, {"_id": 0})

    async def maybe_autosync(app_id: str, user_id: str):
        doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0, "github_autosync": 1})
        if doc and doc.get("github_autosync"):
            async def _w():
                try:
                    await push_to_github(app_id, user_id, None, True)
                except Exception:
                    logger.exception("autosync failed")
            asyncio.create_task(_w())

    return {"upsert_chat_lead": upsert_chat_lead, "maybe_autosync": maybe_autosync}
