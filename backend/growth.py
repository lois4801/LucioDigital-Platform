import os
import re
import json
import base64
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

logger = logging.getLogger("agency.growth")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
from llm_provider import image_available  # noqa: E402


def now():
    return datetime.now(timezone.utc)


def uid(p):
    import uuid
    return f"{p}_{uuid.uuid4().hex[:12]}"


class TrackIn(BaseModel):
    path: str = "/"
    event: str = "view"
    session: str
    referrer: Optional[str] = None


class BlogIn(BaseModel):
    topic: str
    tone: str = "expert, friendly"
    with_cover: bool = True


class InviteIn(BaseModel):
    email: str
    role: str = "viewer"


def register(api, db, get_current_user, get_user_app, log_activity, create_access_token, create_refresh_token, set_auth_cookies, send_email, hooks):
    ai_roles = ("owner", "admin")

    async def require_ai_access(app_id: str, user: dict) -> dict:
        """Clients (viewer/editor) cannot spend the agency's AI credits."""
        doc = await get_user_app(app_id, user)
        if doc["owner_id"] == user["user_id"]:
            return doc
        m = await db.memberships.find_one({"app_id": app_id, "user_id": user["user_id"]}, {"_id": 0})
        if not m or m.get("role") not in ai_roles:
            raise HTTPException(403, "AI generation is reserved for the agency team. Ask your agency to make this change.")
        return doc

    # ===== ANALYTICS =====
    @api.post("/public/track/{token}")
    async def track(token: str, body: TrackIn):
        doc = await db.apps.find_one({"preview_token": token, "preview_enabled": True}, {"_id": 0, "app_id": 1})
        if not doc:
            return {"ok": False}
        await db.analytics_events.insert_one({"app_id": doc["app_id"], "path": body.path[:200], "event": body.event[:40], "session": body.session[:60],
                                              "referrer": (body.referrer or "")[:200], "ts": now().isoformat(), "day": now().strftime("%Y-%m-%d")})
        return {"ok": True}

    @api.get("/apps/{app_id}/analytics")
    async def analytics(app_id: str, days: int = 30, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        since = (now() - timedelta(days=days)).isoformat()
        q = {"app_id": app_id, "ts": {"$gte": since}}
        views = await db.analytics_events.count_documents({**q, "event": "view"})
        sessions = len(await db.analytics_events.distinct("session", q))
        top = await db.analytics_events.aggregate([{"$match": {**q, "event": "view"}}, {"$group": {"_id": "$path", "views": {"$sum": 1}}}, {"$sort": {"views": -1}}, {"$limit": 6}]).to_list(6)
        daily = await db.analytics_events.aggregate([{"$match": {**q, "event": "view"}}, {"$group": {"_id": "$day", "v": {"$sum": 1}}}, {"$sort": {"_id": 1}}]).to_list(60)
        chats = await db.chat_messages.count_documents({"token": {"$in": [a["preview_token"] for a in await db.apps.find({"app_id": app_id}, {"_id": 0, "preview_token": 1}).to_list(1) if a.get("preview_token")]}, "role": "user", "created_at": {"$gte": since}})
        chat_sessions = len(await db.messages.distinct("session_id", {"app_id": app_id, "source": "chat", "created_at": {"$gte": since}}))
        leads = await db.messages.count_documents({"app_id": app_id, "source": {"$in": ["contact", "chat"]}, "created_at": {"$gte": since}})
        refs = await db.analytics_events.aggregate([{"$match": {**q, "referrer": {"$nin": ["", None]}}}, {"$group": {"_id": "$referrer", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 5}]).to_list(5)
        return {"days": days, "views": views, "visitors": sessions, "top_pages": [{"path": t["_id"], "views": t["views"]} for t in top],
                "daily": [{"day": d["_id"], "views": d["v"]} for d in daily], "chat_messages": chats, "chat_conversations": chat_sessions, "leads": leads,
                "referrers": [{"ref": r["_id"], "n": r["n"]} for r in refs], "conversion": round((leads / sessions) * 100, 1) if sessions else 0}

    # ===== AI BLOG WRITER =====
    @api.post("/apps/{app_id}/cms/{collection_id}/ai-write")
    async def ai_write(app_id: str, collection_id: str, body: BlogIn, user: dict = Depends(get_current_user)):
        doc = await require_ai_access(app_id, user)
        col = await db.cms_collections.find_one({"app_id": app_id, "collection_id": collection_id}, {"_id": 0})
        if not col:
            raise HTTPException(404, "Collection not found")
        from studio import _claude, _parse_json
        system = ("You are a senior content marketer. Return ONLY JSON: {\"title\", \"slug\", \"excerpt\" (1-2 sentences), \"body\" (600-900 words, paragraphs separated by \\n, no markdown headings), "
                  "\"tags\": [3-5 strings], \"cover_prompt\": \"a vivid photographic image description for the cover, no text\"}.")
        prompt = f"Business: {doc['name']} ({doc.get('industry', '')}). {doc.get('description', '')}\nCollection: {col['name']}\nTopic: {body.topic}\nTone: {body.tone}"
        try:
            post = _parse_json(await _claude(system, prompt, f"blog-{app_id}-{uid('b')}"))
        except Exception as e:
            raise HTTPException(500, f"Writing failed: {str(e)[:140]}")
        cover = ""
        if body.with_cover and image_available():
            try:
                from llm_provider import generate_image
                imgs = await generate_image(f"{post.get('cover_prompt') or body.topic}. Editorial blog cover, premium, natural light, no text.")
                if imgs:
                    cover = "data:image/png;base64," + base64.b64encode(imgs[0]).decode()
            except Exception:
                logger.exception("cover failed")
        slug = re.sub(r"[^a-z0-9]+", "-", str(post.get("slug") or post.get("title", body.topic)).lower()).strip("-")
        if await db.cms_items.find_one({"collection_id": collection_id, "slug": slug}):
            slug = f"{slug}-{uid('')[1:5]}"
        item = {"item_id": uid("itm"), "collection_id": collection_id, "app_id": app_id, "title": post.get("title", body.topic), "slug": slug, "excerpt": post.get("excerpt", ""),
                "body": post.get("body", ""), "cover": cover, "date": now().strftime("%Y-%m-%d"), "tags": post.get("tags", [])[:6], "published": False, "ai_generated": True,
                "created_at": now().isoformat(), "updated_at": now().isoformat()}
        await db.cms_items.insert_one(dict(item))
        await log_activity(app_id, user["user_id"], "cms.ai", f"AI drafted post: {item['title'][:60]}")
        return item

    # ===== PORTAL INVITES (magic link) =====
    @api.post("/apps/{app_id}/portal/invite")
    async def portal_invite(app_id: str, body: InviteIn, user: dict = Depends(get_current_user)):
        app_doc = await get_user_app(app_id, user)
        email = body.email.lower().strip()
        if "@" not in email:
            raise HTTPException(400, "Invalid email")
        role = body.role if body.role in ("viewer", "editor", "admin") else "viewer"
        invitee = await db.users.find_one({"email": email})
        if not invitee:
            invitee = {"user_id": uid("user"), "email": email, "name": email.split("@")[0], "role": "member", "auth_provider": "invited", "created_at": now().isoformat()}
            await db.users.insert_one(dict(invitee))
        if invitee["user_id"] != app_doc["owner_id"]:
            await db.memberships.update_one({"app_id": app_id, "user_id": invitee["user_id"]},
                                            {"$set": {"role": role}, "$setOnInsert": {"membership_id": uid("mem"), "app_id": app_id, "user_id": invitee["user_id"], "created_at": now().isoformat()}}, upsert=True)
        token = uid("ml") + uid("")[1:]
        await db.magic_links.insert_one({"token": token, "user_id": invitee["user_id"], "app_id": app_id, "expires_at": (now() + timedelta(days=7)).isoformat(), "used": False, "created_at": now().isoformat()})
        link = f"{FRONTEND_URL}/api/auth/magic/{token}"
        res = await send_email(email, f"You're invited to the {app_doc['name']} client portal",
                               f"{user.get('name') or 'Your agency'} invited you to view {app_doc['name']} — live site, invoices, leads and change requests.\n\nOpen your portal (link valid 7 days, single use):\n{link}")
        await log_activity(app_id, user["user_id"], "portal.invite", f"Portal invite sent to {email} ({res['status']})")
        if hooks.get("fire_event"):
            await hooks["fire_event"](app_id, "member_invited", {"email": email, "role": role})
        return {"ok": True, "email": email, "delivery": res["status"], "delivery_detail": res.get("detail") or res.get("reason"), "magic_link": link if res["status"] != "sent" else None}

    @api.get("/auth/magic/{token}")
    async def magic_login(token: str):
        ml = await db.magic_links.find_one({"token": token})
        if not ml or ml.get("used") or ml["expires_at"] < now().isoformat():
            return RedirectResponse(f"{FRONTEND_URL}/login?error=magic_link_invalid")
        u = await db.users.find_one({"user_id": ml["user_id"]}, {"_id": 0})
        if not u:
            return RedirectResponse(f"{FRONTEND_URL}/login?error=magic_link_invalid")
        await db.magic_links.update_one({"token": token}, {"$set": {"used": True, "used_at": now().isoformat()}})
        resp = RedirectResponse(f"{FRONTEND_URL}/portal", status_code=302)
        set_auth_cookies(resp, create_access_token(u["user_id"], u["email"]), create_refresh_token(u["user_id"]))
        return resp

    return {"require_ai_access": require_ai_access}
