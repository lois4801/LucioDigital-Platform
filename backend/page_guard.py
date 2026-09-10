"""Page-level locks (owner/admin gate client edits) and dated page version history with restore."""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)
MAX_VERSIONS = 30


def _now():
    return datetime.now(timezone.utc).isoformat()


def _uid(p):
    return f"{p}_{uuid.uuid4().hex[:12]}"


async def role_of(db, app_doc: dict, user: dict) -> str:
    if app_doc["owner_id"] == user["user_id"]:
        return "owner"
    m = await db.memberships.find_one({"app_id": app_doc["app_id"], "user_id": user["user_id"]}, {"_id": 0, "role": 1})
    return (m or {}).get("role", "viewer")


async def assert_can_edit_page(db, app_doc: dict, page: dict, user: dict):
    """A locked page is read-only for editors and viewers; owner/admin, or a client holding an
    approved single-use edit grant, can still save it."""
    if not page.get("locked"):
        return None
    if await role_of(db, app_doc, user) in ("owner", "admin"):
        return None
    from edit_requests import active_grant
    grant = await active_grant(db, app_doc["app_id"], page["page_id"], user["user_id"])
    if grant:
        return grant
    raise HTTPException(423, f"'{page.get('name')}' is locked by the agency. Use “Request a change” to ask them to open it.")


async def snapshot(db, app_id: str, page: dict, by: str, reason: str = "save") -> Optional[dict]:
    """Store a dated copy of a page's blocks, keeping the newest MAX_VERSIONS per page."""
    if not page:
        return None
    doc = {"version_id": _uid("ver"), "app_id": app_id, "page_id": page["page_id"], "slug": page.get("slug"),
           "name": page.get("name"), "blocks": page.get("blocks") or [], "by": by, "reason": reason,
           "sections": len(page.get("blocks") or []), "created_at": _now()}
    await db.page_versions.insert_one(dict(doc))
    old = await db.page_versions.find({"app_id": app_id, "page_id": page["page_id"]}, {"_id": 0, "version_id": 1}) \
        .sort("created_at", -1).skip(MAX_VERSIONS).to_list(200)
    if old:
        await db.page_versions.delete_many({"version_id": {"$in": [o["version_id"] for o in old]}})
    doc.pop("blocks", None)
    return doc


async def snapshot_site(db, app_id: str, by: str, reason: str):
    """Called before a wholesale rewrite (import, AI rebuild, look change) so it can be undone as a batch."""
    pages = await db.pages.find({"app_id": app_id}, {"_id": 0}).to_list(120)
    batch_id = _uid("batch")
    for pg in pages:
        v = await snapshot(db, app_id, pg, by, reason)
        if v:
            await db.page_versions.update_one({"version_id": v["version_id"]}, {"$set": {"batch_id": batch_id}})
    return {"batch_id": batch_id, "pages": len(pages)}


class LockIn(BaseModel):
    locked: bool


class BatchIn(BaseModel):
    batch_id: str


def register(api, db, get_current_user, get_user_app, log_activity):
    @api.post("/apps/{app_id}/pages/{page_id}/lock")
    async def lock_page(app_id: str, page_id: str, body: LockIn, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        if await role_of(db, doc, user) not in ("owner", "admin"):
            raise HTTPException(403, "Only the agency owner or an admin can lock or unlock pages")
        r = await db.pages.update_one({"app_id": app_id, "page_id": page_id}, {"$set": {"locked": body.locked, "locked_at": _now()}})
        if not r.matched_count:
            raise HTTPException(404, "Page not found")
        page = await db.pages.find_one({"page_id": page_id}, {"_id": 0, "name": 1, "locked": 1})
        await log_activity(app_id, user["user_id"], "page.lock", f"Page '{page['name']}' {'locked' if body.locked else 'unlocked'}")
        return {"page_id": page_id, "locked": body.locked}

    @api.post("/apps/{app_id}/pages/lock-all")
    async def lock_all_pages(app_id: str, body: LockIn, user: dict = Depends(get_current_user)):
        """Lock or unlock every page of a client at once, plus the client-wide content lock."""
        doc = await get_user_app(app_id, user)
        if await role_of(db, doc, user) not in ("owner", "admin"):
            raise HTTPException(403, "Only the agency owner or an admin can lock or unlock pages")
        r = await db.pages.update_many({"app_id": app_id}, {"$set": {"locked": body.locked, "locked_at": _now()}})
        await db.apps.update_one({"app_id": app_id}, {"$set": {"content_locked": body.locked, "locked_at": _now()}})
        await log_activity(app_id, user["user_id"], "page.lock_all",
                           f"All {r.matched_count} page(s) and the content lock {'locked' if body.locked else 'unlocked'}")
        return {"locked": body.locked, "pages": r.matched_count, "content_locked": body.locked}

    @api.get("/apps/{app_id}/pages/{page_id}/versions")
    async def list_versions(app_id: str, page_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        if not await db.pages.find_one({"app_id": app_id, "page_id": page_id}, {"_id": 0, "page_id": 1}):
            raise HTTPException(404, "Page not found")
        vs = await db.page_versions.find({"app_id": app_id, "page_id": page_id}, {"_id": 0, "blocks": 0}) \
            .sort("created_at", -1).to_list(MAX_VERSIONS)
        return {"versions": vs, "max": MAX_VERSIONS}

    @api.get("/apps/{app_id}/pages/{page_id}/versions/{version_id}")
    async def get_version(app_id: str, page_id: str, version_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        v = await db.page_versions.find_one({"app_id": app_id, "page_id": page_id, "version_id": version_id}, {"_id": 0})
        if not v:
            raise HTTPException(404, "That version is no longer available")
        return v

    @api.get("/apps/{app_id}/pages/{page_id}/versions/{version_id}/diff")
    async def diff_version(app_id: str, page_id: str, version_id: str, user: dict = Depends(get_current_user)):
        """What would change if this version were restored: added / removed / edited sections."""
        await get_user_app(app_id, user)
        page = await db.pages.find_one({"app_id": app_id, "page_id": page_id}, {"_id": 0, "blocks": 1, "name": 1})
        v = await db.page_versions.find_one({"app_id": app_id, "page_id": page_id, "version_id": version_id}, {"_id": 0})
        if not page or not v:
            raise HTTPException(404, "That version is no longer available")
        from page_diff import diff_blocks
        return {"page": page["name"], "version_at": v["created_at"], "by": v["by"], "reason": v["reason"],
                **diff_blocks(page.get("blocks") or [], v.get("blocks") or [])}

    @api.post("/apps/{app_id}/pages/{page_id}/versions/{version_id}/restore")
    async def restore_version(app_id: str, page_id: str, version_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        page = await db.pages.find_one({"app_id": app_id, "page_id": page_id}, {"_id": 0})
        if not page:
            raise HTTPException(404, "Page not found")
        await assert_can_edit_page(db, doc, page, user)
        v = await db.page_versions.find_one({"app_id": app_id, "page_id": page_id, "version_id": version_id}, {"_id": 0})
        if not v:
            raise HTTPException(404, "That version is no longer available")
        who = user.get("name") or user["email"]
        await snapshot(db, app_id, page, who, "before restore")
        await db.pages.update_one({"page_id": page_id}, {"$set": {"blocks": v["blocks"], "updated_at": _now()}})
        from content_lock import sync_overview
        await sync_overview(db, app_id)
        await log_activity(app_id, user["user_id"], "page.restored", f"Restored '{page['name']}' to the {v['created_at'][:16].replace('T', ' ')} version")
        return await db.pages.find_one({"page_id": page_id}, {"_id": 0})

    @api.get("/apps/{app_id}/site/restore-points")
    async def restore_points(app_id: str, user: dict = Depends(get_current_user)):
        """Whole-site snapshots taken before an import, rebuild or AI regeneration."""
        await get_user_app(app_id, user)
        vs = await db.page_versions.find({"app_id": app_id, "batch_id": {"$exists": True}}, {"_id": 0, "blocks": 0}) \
            .sort("created_at", -1).to_list(400)
        by_batch = {}
        for v in vs:
            b = by_batch.setdefault(v["batch_id"], {"batch_id": v["batch_id"], "reason": v["reason"], "by": v["by"],
                                                    "created_at": v["created_at"], "pages": []})
            b["pages"].append({"slug": v["slug"], "name": v["name"], "sections": v["sections"]})
            b["created_at"] = max(b["created_at"], v["created_at"])
        return {"restore_points": sorted(by_batch.values(), key=lambda b: b["created_at"], reverse=True)[:20]}

    @api.post("/apps/{app_id}/site/restore-batch")
    async def restore_batch(app_id: str, body: BatchIn, user: dict = Depends(get_current_user)):
        """Undo a whole import/rebuild by putting every page from that snapshot back."""
        doc = await get_user_app(app_id, user)
        if await role_of(db, doc, user) not in ("owner", "admin"):
            raise HTTPException(403, "Only the agency owner or an admin can undo a whole site change")
        vs = await db.page_versions.find({"app_id": app_id, "batch_id": body.batch_id}, {"_id": 0}).to_list(200)
        if not vs:
            raise HTTPException(404, "That restore point is no longer available")
        who = user.get("name") or user["email"]
        await snapshot_site(db, app_id, who, f"before undo of '{vs[0]['reason']}'")
        await db.pages.delete_many({"app_id": app_id})
        restored = []
        for i, v in enumerate(sorted(vs, key=lambda x: (x["slug"] != "/", x["slug"]))):
            await db.pages.insert_one({"page_id": _uid("pg"), "app_id": app_id, "name": v["name"], "slug": v["slug"],
                                       "order": i, "blocks": v["blocks"], "updated_at": _now()})
            restored.append({"name": v["name"], "slug": v["slug"], "blocks": len(v["blocks"])})
        from content_lock import sync_overview
        await sync_overview(db, app_id)
        await log_activity(app_id, user["user_id"], "site.restored", f"Undid '{vs[0]['reason']}' — {len(restored)} page(s) put back")
        return {"pages": restored, "reason": vs[0]["reason"], "at": vs[0]["created_at"]}

    return {"snapshot": snapshot, "snapshot_site": snapshot_site, "assert_can_edit_page": assert_can_edit_page, "role_of": role_of}
