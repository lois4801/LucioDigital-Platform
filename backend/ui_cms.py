import os
from datetime import datetime, timezone
from typing import Dict, Optional
from fastapi import HTTPException, Depends
from pydantic import BaseModel

MAX_KEYS = 200


class LabelsPatch(BaseModel):
    labels: Dict[str, str]
    scope: Optional[str] = "tenant"  # tenant | global


def _is_platform_admin(user: dict) -> bool:
    return (user.get("email") or "").lower().strip() == os.environ["ADMIN_EMAIL"].lower().strip()


def _clean(labels: Dict[str, str]) -> Dict[str, str]:
    out = {}
    for k, v in list(labels.items())[:MAX_KEYS]:
        k = (k or "").strip().replace(".", "_").replace("$", "_")[:80]
        if k:
            out[k] = (v or "").strip()[:400]
    return out


def register(api, db, get_current_user, get_user_app):
    async def _globals() -> Dict[str, str]:
        doc = await db.site_settings.find_one({"key": "ui_labels"}, {"_id": 0}) or {}
        return doc.get("labels", {})

    async def _can_edit(app_doc: dict, user: dict) -> bool:
        return _is_platform_admin(user) or app_doc["owner_id"] == user["user_id"]

    @api.get("/apps/{app_id}/ui_labels")
    async def get_ui_labels(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        g = await _globals()
        t = doc.get("ui_overrides") or {}
        return {
            "labels": {**g, **t},
            "tenant": t,
            "global": g,
            "can_edit": await _can_edit(doc, user),
        }

    @api.put("/apps/{app_id}/ui_labels")
    async def put_ui_labels(app_id: str, body: LabelsPatch, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        if not await _can_edit(doc, user):
            raise HTTPException(403, "Only the platform admin or tenant owner can edit labels")
        patch = _clean(body.labels)
        if not patch:
            raise HTTPException(400, "No labels provided")
        ts = datetime.now(timezone.utc).isoformat()
        if body.scope == "global":
            if not _is_platform_admin(user):
                raise HTTPException(403, "Only the platform admin can set global defaults")
            g = {**(await _globals()), **patch}
            await db.site_settings.update_one(
                {"key": "ui_labels"},
                {"$set": {"key": "ui_labels", "labels": g, "updated_at": ts, "updated_by": user["email"]}},
                upsert=True,
            )
        else:
            await db.apps.update_one(
                {"app_id": app_id},
                {"$set": {**{f"ui_overrides.{k}": v for k, v in patch.items()}, "updated_at": ts}},
            )
        fresh = await db.apps.find_one({"app_id": app_id}, {"_id": 0, "ui_overrides": 1})
        g = await _globals()
        t = (fresh or {}).get("ui_overrides") or {}
        return {"labels": {**g, **t}, "tenant": t, "global": g, "can_edit": True}

    @api.delete("/apps/{app_id}/ui_labels")
    async def reset_ui_labels(app_id: str, scope: str = "tenant", user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        if not await _can_edit(doc, user):
            raise HTTPException(403, "Only the platform admin or tenant owner can edit labels")
        await db.apps.update_one({"app_id": app_id}, {"$unset": {"ui_overrides": ""}})
        if scope == "all":
            if not _is_platform_admin(user):
                raise HTTPException(403, "Only the platform admin can reset global defaults")
            await db.site_settings.update_one({"key": "ui_labels"}, {"$set": {"labels": {}}}, upsert=True)
        g = await _globals()
        return {"labels": g, "tenant": {}, "global": g, "can_edit": True}
