"""Shared lock vocabulary + edit-grant helpers.

`locks.py` and `edit_requests.py` both need these, so they live here to keep the import graph
one-directional (both modules import this one; neither imports the other).
"""
from datetime import datetime, timezone
from typing import Optional

KINDS = ("page", "block", "form", "cms_collection", "cms_item", "workflow",
         "data_destination", "app_mode", "overview")

LABELS = {"page": "page", "block": "section", "form": "form", "cms_collection": "collection",
          "cms_item": "content item", "workflow": "workflow", "data_destination": "data destination",
          "app_mode": "App Mode blueprint", "overview": "Overview"}


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def active_grant(db, app_id: str, page_id: str, user_id: str) -> Optional[dict]:
    return await db.edit_grants.find_one(
        {"app_id": app_id, "page_id": page_id, "user_id": user_id, "used": False,
         "expires_at": {"$gt": _iso()}}, {"_id": 0})


async def consume_grant(db, grant_id: str):
    await db.edit_grants.update_one({"grant_id": grant_id}, {"$set": {"used": True, "used_at": _iso()}})
