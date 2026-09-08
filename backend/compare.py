"""Before/after share links: the prospect's current site next to their Lois-Tech rebuild.
The "before" is an automatic screenshot of the old URL; the "after" is the live rebuilt site."""
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

from fastapi import HTTPException, Depends
from pydantic import BaseModel, EmailStr

logger = logging.getLogger("agency.compare")

SHOT = "https://s.wordpress.com/mshots/v1/{url}?w=1280&h=1600"


def _iso():
    return datetime.now(timezone.utc).isoformat()


def _uid(p):
    import uuid
    return f"{p}_{uuid.uuid4().hex[:12]}"


def shot_url(url: str) -> str:
    return SHOT.format(url=quote(url, safe=""))


class CompareIn(BaseModel):
    before_url: Optional[str] = None
    headline: Optional[str] = None
    before_image: Optional[str] = None


class CompareLeadIn(BaseModel):
    name: str
    email: EmailStr
    message: str = ""


def register(api, db, get_current_user, get_user_app, log_activity, new_message=None, send_email=None):

    @api.post("/apps/{app_id}/compare-link")
    async def create_compare(app_id: str, body: CompareIn, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        from page_guard import role_of
        if await role_of(db, doc, user) not in ("owner", "admin"):
            raise HTTPException(403, "Only the agency owner or an admin can create a share link")
        before = (body.before_url or doc.get("imported_from") or doc.get("source_url") or "").strip()
        if before and not before.startswith("http"):
            before = f"https://{before}"
        if not before and not body.before_image:
            raise HTTPException(400, "Add the prospect's current website address so we can capture the 'before' shot")
        if not doc.get("preview_token"):
            raise HTTPException(409, "Turn on the live preview link for this tenant first")
        existing = await db.compare_links.find_one({"app_id": app_id}, {"_id": 0})
        code = existing["code"] if existing else secrets.token_urlsafe(9)
        row = {"code": code, "app_id": app_id, "before_url": before,
               "before_image": body.before_image or (shot_url(before) if before else ""),
               "headline": (body.headline or f"{doc.get('name')} — before and after")[:160],
               "preview_token": doc["preview_token"], "created_at": existing.get("created_at") if existing else _iso(),
               "updated_at": _iso(), "views": existing.get("views", 0) if existing else 0}
        await db.compare_links.update_one({"app_id": app_id}, {"$set": row}, upsert=True)
        await log_activity(app_id, user["user_id"], "compare.link", f"Before/after link ready for {before or 'uploaded screenshot'}")
        return {**row, "url": f"/compare/{code}"}

    @api.get("/apps/{app_id}/compare-link")
    async def get_compare(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        row = await db.compare_links.find_one({"app_id": app_id}, {"_id": 0})
        return {"link": ({**row, "url": f"/compare/{row['code']}"} if row else None),
                "suggested_before_url": doc.get("imported_from") or doc.get("source_url") or ""}

    @api.delete("/apps/{app_id}/compare-link")
    async def delete_compare(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        from page_guard import role_of
        if await role_of(db, doc, user) not in ("owner", "admin"):
            raise HTTPException(403, "Only the agency owner or an admin can remove a share link")
        await db.compare_links.delete_one({"app_id": app_id})
        return {"deleted": True}

    @api.get("/public/compare/{code}")
    async def public_compare(code: str):
        row = await db.compare_links.find_one({"code": code}, {"_id": 0})
        if not row:
            raise HTTPException(404, "This comparison link is no longer available")
        app_doc = await db.apps.find_one({"app_id": row["app_id"]}, {"_id": 0, "name": 1, "industry": 1, "color": 1, "theme": 1})
        await db.compare_links.update_one({"code": code}, {"$inc": {"views": 1}})
        return {"headline": row["headline"], "before_url": row["before_url"], "before_image": row["before_image"],
                "preview_token": row["preview_token"], "app": {"name": (app_doc or {}).get("name"),
                                                               "industry": (app_doc or {}).get("industry"),
                                                               "color": (app_doc or {}).get("color")}}

    @api.post("/public/compare/{code}/lead")
    async def compare_lead(code: str, body: CompareLeadIn):
        row = await db.compare_links.find_one({"code": code}, {"_id": 0})
        if not row:
            raise HTTPException(404, "This comparison link is no longer available")
        app_doc = await db.apps.find_one({"app_id": row["app_id"]}, {"_id": 0, "name": 1, "owner_id": 1})
        msg = {"message_id": _uid("msg"), "app_id": row["app_id"], "kind": "lead", "source": "compare",
               "status": "unread", "from_name": body.name.strip()[:120], "from_email": body.email.lower(),
               "subject": f"Before/after page — {body.name.strip()[:60]} wants the rebuild",
               "body": (body.message or "Interested in the rebuild shown on the before/after page.")[:3000],
               "score": None, "created_at": _iso(), "updated_at": _iso(), "replies": [], "attachments": []}
        await db.messages.insert_one(dict(msg))
        owner = await db.users.find_one({"user_id": (app_doc or {}).get("owner_id")}, {"_id": 0, "email": 1})
        if owner and send_email:
            try:
                await send_email(owner["email"], f"[Before/after] {body.name} wants the {(app_doc or {}).get('name')} rebuild",
                                 f"{body.name} <{body.email}> asked about the rebuild.\n\n{msg['body']}")
            except Exception:
                logger.exception("compare lead email failed")
        msg.pop("_id", None)
        return {"ok": True, "message_id": msg["message_id"]}
