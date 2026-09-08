"""Tenant content lock: saved site content is the source of truth and can never be regenerated
or overwritten by a builder prompt while the tenant is locked."""
import os
from datetime import datetime, timezone
from fastapi import HTTPException, Depends
from pydantic import BaseModel


def _now():
    return datetime.now(timezone.utc).isoformat()


async def assert_unlocked(db, app_id: str, action: str = "replace this site's pages"):
    """Raise unless the tenant is explicitly unlocked. Called by every wholesale-rewrite path."""
    doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0, "content_locked": 1, "name": 1})
    if doc and doc.get("content_locked", True):
        raise HTTPException(423, f"This tenant's site content is locked, so nothing can {action}. "
                                 "Unlock it in Overview → Content lock if you really want to overwrite the saved site.")
    return doc


async def lock_after_build(db, app_id: str):
    """Auto-lock a tenant once it actually has a site, so later prompts can't wipe it."""
    if await db.pages.count_documents({"app_id": app_id}) > 0:
        await db.apps.update_one({"app_id": app_id}, {"$set": {"content_locked": True, "locked_at": _now()}})


async def lock_all_existing(db) -> int:
    """One-time: lock every tenant that has no explicit setting yet."""
    r = await db.apps.update_many({"content_locked": {"$exists": False}}, {"$set": {"content_locked": True, "locked_at": _now()}})
    return r.modified_count


async def sync_overview(db, app_id: str):
    """Keep the Overview snapshot in step with whatever Site Mode currently holds."""
    home = await db.pages.find_one({"app_id": app_id, "slug": "/"}, {"_id": 0, "blocks": 1}) \
        or await db.pages.find_one({"app_id": app_id}, {"_id": 0, "blocks": 1})
    if not home:
        return None
    blocks = home.get("blocks") or []
    hero = next((b for b in blocks if b.get("type") == "hero"), None)
    props = (hero or {}).get("props") or {}
    img = next((v for b in blocks for k, v in ((b.get("props") or {}).items())
                if k in ("image", "bg", "background") and isinstance(v, str) and v.strip()), None)
    snap = {"headline": str(props.get("title") or "")[:160], "subtitle": str(props.get("subtitle") or "")[:240],
            "pages": await db.pages.count_documents({"app_id": app_id}),
            "sections": len(blocks), "updated_at": _now()}
    upd = {"site_snapshot": snap}
    if img:
        upd["thumbnail"] = img
    await db.apps.update_one({"app_id": app_id}, {"$set": upd})
    return snap


class LockIn(BaseModel):
    locked: bool


def register(api, db, get_current_user, get_user_app, log_activity):
    @api.get("/apps/{app_id}/content-lock")
    async def get_lock(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        return {"locked": bool(doc.get("content_locked", True)), "locked_at": doc.get("locked_at"),
                "snapshot": doc.get("site_snapshot")}

    @api.post("/apps/{app_id}/content-lock")
    async def set_lock(app_id: str, body: LockIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        await db.apps.update_one({"app_id": app_id}, {"$set": {"content_locked": body.locked, "locked_at": _now()}})
        await log_activity(app_id, user["user_id"], "content.lock", f"Site content {'locked' if body.locked else 'unlocked'}")
        return {"locked": body.locked}

    return {"assert_unlocked": assert_unlocked, "lock_after_build": lock_after_build, "sync_overview": sync_overview}
