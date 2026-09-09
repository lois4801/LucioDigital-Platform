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
    """Keep the Overview snapshot in step with whatever Site Mode currently holds.

    Captures the live hero headline/subheadline/description, the real page and section counts,
    a fresh thumbnail, and mirrors the Navbar brand name onto the tenant name.
    """
    pages = await db.pages.find({"app_id": app_id}, {"_id": 0, "slug": 1, "blocks": 1, "updated_at": 1}).to_list(80)
    if not pages:
        return None
    pages.sort(key=lambda p: p.get("slug") != "/")
    home = next((p for p in pages if p.get("slug") == "/"), pages[0])
    blocks = home.get("blocks") or []
    hero = next((b for b in blocks if b.get("type") == "hero"), None)
    props = (hero or {}).get("props") or {}
    nav = next((b for b in blocks if b.get("type") == "navbar"), None)
    brand = str(((nav or {}).get("props") or {}).get("brand") or "").strip()[:120]
    # 'description' wins over legacy 'body'/'text'/'lead'/'blurb' when a hero carries more than one.
    description = next((str(props.get(k)).strip() for k in ("description", "body", "text", "lead", "blurb")
                        if isinstance(props.get(k), str) and props.get(k).strip()), "")
    # Prefer the hero's own artwork so the thumbnail stays visually stable across builders.
    img = next((props.get(k) for k in ("image", "bg", "background")
                if isinstance(props.get(k), str) and props.get(k).strip()), None) \
        or next((v for b in blocks for k, v in ((b.get("props") or {}).items())
                 if k in ("image", "bg", "background") and isinstance(v, str) and v.strip()), None)
    snap = {"headline": str(props.get("title") or "")[:160],
            "subtitle": str(props.get("subtitle") or "")[:240],
            "description": description[:400],
            "brand": brand,
            "pages": len(pages),
            "sections": len(blocks),
            "total_sections": sum(len(p.get("blocks") or []) for p in pages),
            "thumbnail": img,
            "updated_at": _now()}
    upd = {"site_snapshot": snap, "updated_at": _now()}
    if img:
        upd["thumbnail"] = img
    if brand:
        # The Navbar brand is the tenant's public name — keep the workspace header in step with it.
        upd["name"] = brand
    blurb = (description or snap["subtitle"] or "").strip()
    if blurb:
        # The Overview summary line tracks the live hero copy.
        upd["description"] = blurb[:400]
    await db.apps.update_one({"app_id": app_id}, {"$set": upd})
    return snap


class LockIn(BaseModel):
    locked: bool


SYNCED_LABEL_KEYS = ("header_tenant_name", "overview_card_title", "overview_card_description")


async def clear_synced_label_overrides(db) -> int:
    """These three fields now follow Site Mode, so any saved label override is dead data."""
    res = await db.apps.update_many(
        {"$or": [{f"ui_overrides.{k}": {"$exists": True}} for k in SYNCED_LABEL_KEYS]},
        {"$unset": {f"ui_overrides.{k}": "" for k in SYNCED_LABEL_KEYS}})
    return res.modified_count


async def sync_all_overviews(db) -> int:
    """Bring every tenant's Overview snapshot in step with its current Site Mode content."""
    import asyncio
    ids = [a["app_id"] async for a in db.apps.find({"is_deleted": {"$ne": True}, "archived": {"$ne": True}}, {"_id": 0, "app_id": 1})]

    async def one(app_id):
        try:
            return bool(await sync_overview(db, app_id))
        except Exception:
            return False

    done = 0
    for i in range(0, len(ids), 10):
        done += sum(await asyncio.gather(*(one(a) for a in ids[i:i + 10])))
    return done


def register(api, db, get_current_user, get_user_app, log_activity):
    @api.post("/apps/{app_id}/site/sync-overview")
    async def resync_overview(app_id: str, user: dict = Depends(get_current_user)):
        """Force a re-read of Site Mode into the Overview card (normally automatic on every save)."""
        await get_user_app(app_id, user)
        snap = await sync_overview(db, app_id)
        if not snap:
            raise HTTPException(400, "This tenant has no Site Mode pages yet")
        return snap

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

    return {"assert_unlocked": assert_unlocked, "lock_after_build": lock_after_build,
            "sync_overview": sync_overview, "sync_all_overviews": sync_all_overviews}
