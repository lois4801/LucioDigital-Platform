"""30-day restore window for deleted tenants.

Deleting a tenant from the dashboard moves it to the trash instead of erasing it: the site goes
offline immediately, but every page, block, lead, booking, member and file is kept and can be
restored for 30 days. After that a boot-time sweep purges it for good. The master workspace can
never be trashed.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException

logger = logging.getLogger("agency.tenant_trash")

WINDOW_DAYS = 30
PURGE_COLLECTIONS = ("apps", "pages", "memberships", "messages", "activity_logs", "submissions",
                     "item_locks", "workflows", "cms_collections", "cms_items", "site_users",
                     "media_assets", "files", "bookings", "page_versions")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.isoformat()


def days_left(app: dict) -> int:
    raw = app.get("purge_after")
    if not raw:
        return WINDOW_DAYS
    try:
        due = datetime.fromisoformat(raw)
    except ValueError:
        return WINDOW_DAYS
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    return max(0, (due - _now()).days)


async def erase(db, app_id: str) -> dict:
    removed = {}
    for coll in PURGE_COLLECTIONS:
        r = await db[coll].delete_many({"app_id": app_id})
        if r.deleted_count:
            removed[coll] = r.deleted_count
    return removed


async def sweep_expired(db) -> int:
    """Purge tenants whose 30-day window has run out. Runs on every boot."""
    n = 0
    async for app in db.apps.find({"trashed": True}, {"_id": 0, "app_id": 1, "purge_after": 1, "name": 1}):
        if days_left(app) <= 0 and app.get("purge_after"):
            await erase(db, app["app_id"])
            logger.info(f"Trash window expired — purged {app.get('name')} ({app['app_id']})")
            n += 1
    return n


def register(api, db, get_current_user, get_user_app, log_activity):

    @api.post("/apps/{app_id}/trash")
    async def trash_app(app_id: str, user: dict = Depends(get_current_user)):
        """Soft delete: offline now, fully restorable for 30 days."""
        app = await get_user_app(app_id, user)
        if app.get("is_test_lab") or app.get("protected"):
            raise HTTPException(400, "The master workspace is permanent and cannot be deleted")
        if app["owner_id"] != user["user_id"]:
            raise HTTPException(403, "Only the owner can delete a tenant")
        due = _now() + timedelta(days=WINDOW_DAYS)
        await db.apps.update_one({"app_id": app_id}, {"$set": {
            "trashed": True, "trashed_at": _iso(_now()), "purge_after": _iso(due),
            "archived": True, "archived_at": _iso(_now()),
            "preview_enabled": False, "featured": False, "updated_at": _iso(_now()),
        }})
        await log_activity(app_id, user["user_id"], "app.trashed",
                           f"Deleted {app['name']} — restorable until {due.date().isoformat()}")
        leads = await db.messages.count_documents({"app_id": app_id})
        return {"app_id": app_id, "trashed": True, "restore_until": _iso(due),
                "days_left": WINDOW_DAYS, "leads_kept": leads}

    @api.get("/apps-trash")
    async def list_trash(user: dict = Depends(get_current_user)):
        rows = await db.apps.find(
            {"trashed": True, "owner_id": user["user_id"]},
            {"_id": 0, "app_id": 1, "name": 1, "industry": 1, "description": 1, "color": 1,
             "trashed_at": 1, "purge_after": 1},
        ).sort("trashed_at", -1).to_list(200)
        out = []
        for a in rows:
            out.append({**a, "days_left": days_left(a),
                        "pages": await db.pages.count_documents({"app_id": a["app_id"]}),
                        "leads": await db.messages.count_documents({"app_id": a["app_id"]})})
        return {"tenants": out, "count": len(out), "window_days": WINDOW_DAYS}

    @api.post("/apps/{app_id}/untrash")
    async def restore_app(app_id: str, user: dict = Depends(get_current_user)):
        app = await get_user_app(app_id, user)
        if not app.get("trashed"):
            raise HTTPException(400, "That tenant is not in the trash")
        await db.apps.update_one({"app_id": app_id}, {"$set": {
            "trashed": False, "archived": False, "updated_at": _iso(_now()),
        }, "$unset": {"trashed_at": "", "purge_after": ""}})
        await log_activity(app_id, user["user_id"], "app.untrashed", f"Restored {app['name']} from the trash")
        return {"app_id": app_id, "trashed": False, "restored": True}

    @api.delete("/apps/{app_id}/trash")
    async def purge_now(app_id: str, user: dict = Depends(get_current_user)):
        """Skip the window and erase a trashed tenant immediately."""
        app = await get_user_app(app_id, user)
        if app.get("is_test_lab") or app.get("protected"):
            raise HTTPException(400, "The master workspace is permanent and cannot be deleted")
        if app["owner_id"] != user["user_id"]:
            raise HTTPException(403, "Only the owner can permanently delete a tenant")
        if not app.get("trashed") and not app.get("archived"):
            raise HTTPException(400, "Delete this tenant first, then erase it permanently")
        removed = await erase(db, app_id)
        return {"ok": True, "app_id": app_id, "removed": removed}
