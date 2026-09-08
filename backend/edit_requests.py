"""Client edit requests: a locked page shows 'Request a change'; the request lands in the admin's
Inbox and, once approved, grants that client a single-use edit unlock for that page."""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import HTTPException, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)
GRANT_HOURS = 48

def _now():
    return datetime.now(timezone.utc)


def _iso():
    return _now().isoformat()


def _uid(p):
    return f"{p}_{uuid.uuid4().hex[:12]}"


async def active_grant(db, app_id: str, page_id: str, user_id: str) -> Optional[dict]:
    g = await db.edit_grants.find_one({"app_id": app_id, "page_id": page_id, "user_id": user_id,
                                       "used": False, "expires_at": {"$gt": _iso()}}, {"_id": 0})
    return g


async def consume_grant(db, grant_id: str):
    await db.edit_grants.update_one({"grant_id": grant_id}, {"$set": {"used": True, "used_at": _iso()}})


class RequestIn(BaseModel):
    description: str
    attachments: List[dict] = []


class ItemRequestIn(BaseModel):
    kind: str
    item_id: str
    item_name: Optional[str] = None
    description: str
    attachments: List[dict] = []


class DecisionIn(BaseModel):
    reply: Optional[str] = None


def register(api, db, get_current_user, get_user_app, log_activity, send_email=None):
    from page_guard import role_of

    @api.post("/apps/{app_id}/pages/{page_id}/edit-request")
    async def create_request(app_id: str, page_id: str, body: RequestIn, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        page = await db.pages.find_one({"app_id": app_id, "page_id": page_id}, {"_id": 0, "name": 1, "slug": 1})
        if not page:
            raise HTTPException(404, "Page not found")
        if not (body.description or "").strip():
            raise HTTPException(400, "Describe the change you'd like")
        who = user.get("name") or user["email"]
        msg = {
            "message_id": _uid("msg"), "app_id": app_id, "kind": "edit_request", "status": "unread",
            "from_name": who, "from_email": user["email"],
            "subject": f"Edit request — {page['name']}",
            "body": body.description.strip()[:3000],
            "attachments": (body.attachments or [])[:5],
            "edit_request": {"page_id": page_id, "page_name": page["name"], "page_slug": page["slug"],
                             "state": "pending", "requested_by": user["user_id"], "requested_at": _iso()},
            "score": 0, "created_at": _iso(), "updated_at": _iso(), "replies": [],
        }
        await db.messages.insert_one(dict(msg))
        msg.pop("_id", None)
        await log_activity(app_id, user["user_id"], "edit.requested", f"{who} requested a change on '{page['name']}'")
        owner = await db.users.find_one({"user_id": doc["owner_id"]}, {"_id": 0, "email": 1})
        if owner and send_email:
            try:
                await send_email(owner["email"], f"[Edit request] {page['name']} — {doc.get('name')}",
                                 f"{who} asked for a change on '{page['name']}':\n\n{msg['body']}\n\nApprove or reject it in the Inbox.")
            except Exception:
                logger.exception("edit request email failed")
        return msg

    @api.post("/apps/{app_id}/edit-request")
    async def create_item_request(app_id: str, body: ItemRequestIn, user: dict = Depends(get_current_user)):
        """Generic 'Request a change' for any locked item: section, form, CMS entry, workflow, App Mode…"""
        doc = await get_user_app(app_id, user)
        from locks import KINDS, LABELS
        if body.kind not in KINDS:
            raise HTTPException(400, f"Unknown item kind '{body.kind}'")
        if not (body.description or "").strip():
            raise HTTPException(400, "Describe the change you'd like")
        who = user.get("name") or user["email"]
        name = (body.item_name or LABELS[body.kind]).strip()
        msg = {
            "message_id": _uid("msg"), "app_id": app_id, "kind": "edit_request", "status": "unread",
            "from_name": who, "from_email": user["email"],
            "subject": f"Edit request — {name}",
            "body": body.description.strip()[:3000],
            "attachments": (body.attachments or [])[:5],
            "edit_request": {"page_id": body.item_id, "page_name": name, "page_slug": "",
                             "item_kind": body.kind, "item_label": LABELS[body.kind],
                             "state": "pending", "requested_by": user["user_id"], "requested_at": _iso()},
            "score": 0, "created_at": _iso(), "updated_at": _iso(), "replies": [],
        }
        await db.messages.insert_one(dict(msg))
        msg.pop("_id", None)
        await log_activity(app_id, user["user_id"], "edit.requested", f"{who} requested a change on {LABELS[body.kind]} '{name}'")
        owner = await db.users.find_one({"user_id": doc["owner_id"]}, {"_id": 0, "email": 1})
        if owner and send_email:
            try:
                await send_email(owner["email"], f"[Edit request] {name} — {doc.get('name')}",
                                 f"{who} asked for a change on the {LABELS[body.kind]} '{name}':\n\n{msg['body']}\n\nApprove or reject it in the Inbox.")
            except Exception:
                logger.exception("edit request email failed")
        return msg

    @api.get("/apps/{app_id}/edit-access")
    async def item_edit_access(app_id: str, kind: str, item_id: str, user: dict = Depends(get_current_user)):
        """Whether this user may change one specific locked item right now."""
        doc = await get_user_app(app_id, user)
        from locks import is_locked
        locked = await is_locked(db, app_id, kind, item_id)
        role = await role_of(db, doc, user)
        grant = await active_grant(db, app_id, item_id, user["user_id"])
        pending = await db.messages.count_documents({"app_id": app_id, "kind": "edit_request",
                                                     "edit_request.page_id": item_id, "edit_request.state": "pending"})
        return {"kind": kind, "item_id": item_id, "locked": locked, "role": role,
                "can_edit": (not locked) or role in ("owner", "admin") or bool(grant),
                "can_request": locked and role not in ("owner", "admin"),
                "grant": grant, "pending_requests": pending}

    @api.get("/apps/{app_id}/pages/{page_id}/edit-access")
    async def edit_access(app_id: str, page_id: str, user: dict = Depends(get_current_user)):
        """Tells the builder whether this user may edit a locked page right now."""
        doc = await get_user_app(app_id, user)
        page = await db.pages.find_one({"app_id": app_id, "page_id": page_id}, {"_id": 0, "locked": 1, "name": 1})
        if not page:
            raise HTTPException(404, "Page not found")
        role = await role_of(db, doc, user)
        grant = await active_grant(db, app_id, page_id, user["user_id"])
        pending = await db.messages.count_documents({"app_id": app_id, "kind": "edit_request",
                                                     "edit_request.page_id": page_id, "edit_request.state": "pending"})
        return {"locked": bool(page.get("locked")), "role": role,
                "can_edit": (not page.get("locked")) or role in ("owner", "admin") or bool(grant),
                "can_request": bool(page.get("locked")) and role not in ("owner", "admin"),
                "grant": grant, "pending_requests": pending}

    async def _decide(app_id: str, message_id: str, approve: bool, reply: Optional[str], user: dict):
        doc = await get_user_app(app_id, user)
        if await role_of(db, doc, user) not in ("owner", "admin"):
            raise HTTPException(403, "Only the agency owner or an admin can decide on edit requests")
        msg = await db.messages.find_one({"app_id": app_id, "message_id": message_id}, {"_id": 0})
        if not msg or not msg.get("edit_request"):
            raise HTTPException(404, "Edit request not found")
        if msg["edit_request"].get("state") != "pending":
            raise HTTPException(400, f"This request was already {msg['edit_request']['state']}")
        er = {**msg["edit_request"], "state": "approved" if approve else "rejected",
              "decided_at": _iso(), "decided_by": user.get("name") or user["email"]}
        grant = None
        if approve:
            grant = {"grant_id": _uid("grant"), "app_id": app_id, "page_id": er["page_id"],
                     "user_id": er["requested_by"], "message_id": message_id, "used": False,
                     "granted_at": _iso(), "expires_at": (_now() + timedelta(hours=GRANT_HOURS)).isoformat()}
            await db.edit_grants.insert_one(dict(grant))
            grant.pop("_id", None)
            er["grant_id"] = grant["grant_id"]
        upd = {"edit_request": er, "status": "read", "updated_at": _iso()}
        if reply:
            await db.messages.update_one({"message_id": message_id}, {"$push": {"replies": {
                "reply_id": _uid("rp"), "by": user.get("name") or user["email"], "body": reply[:2000],
                "created_at": _iso(), "delivery": "in_app"}}})
        await db.messages.update_one({"message_id": message_id}, {"$set": upd})
        await log_activity(app_id, user["user_id"], f"edit.{'approved' if approve else 'rejected'}",
                           f"Edit request on '{er['page_name']}' {'approved' if approve else 'rejected'}")
        if send_email and msg.get("from_email"):
            try:
                await send_email(msg["from_email"], f"Your edit request for '{er['page_name']}' was {er['state']}",
                                 (reply or "") + ("\n\nThe page is unlocked for your change — save it within 48 hours." if approve else "\n\nNo change was made."))
            except Exception:
                logger.exception("edit decision email failed")
        return {**(await db.messages.find_one({"message_id": message_id}, {"_id": 0})), "grant": grant}

    @api.post("/apps/{app_id}/inbox/{message_id}/edit-request/approve")
    async def approve(app_id: str, message_id: str, body: DecisionIn, user: dict = Depends(get_current_user)):
        return await _decide(app_id, message_id, True, body.reply, user)

    @api.post("/apps/{app_id}/inbox/{message_id}/edit-request/reject")
    async def reject(app_id: str, message_id: str, body: DecisionIn, user: dict = Depends(get_current_user)):
        return await _decide(app_id, message_id, False, body.reply, user)

    return {"active_grant": active_grant, "consume_grant": consume_grant}
