"""Per-tenant lock registry: a master switch plus granular locks on every page, block, form,
CMS collection/item, workflow, data destination, App Mode blueprint and the Overview snapshot.
Locked items are read-only for editors/viewers (423 + "Request a change"); owner/admin always pass."""
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from lock_shared import KINDS, LABELS, active_grant, consume_grant  # noqa: F401


def _now():
    return datetime.now(timezone.utc).isoformat()


async def is_locked(db, app_id: str, kind: str, item_id: str) -> bool:
    if kind == "page":
        pg = await db.pages.find_one({"app_id": app_id, "page_id": item_id}, {"_id": 0, "locked": 1})
        return bool((pg or {}).get("locked"))
    d = await db.item_locks.find_one({"app_id": app_id, "kind": kind, "item_id": item_id}, {"_id": 0, "locked": 1})
    return bool((d or {}).get("locked"))


async def set_lock(db, app_id: str, kind: str, item_id: str, locked: bool, by: str):
    if kind == "page":
        await db.pages.update_one({"app_id": app_id, "page_id": item_id}, {"$set": {"locked": locked, "locked_at": _now()}})
    await db.item_locks.update_one({"app_id": app_id, "kind": kind, "item_id": item_id},
                                   {"$set": {"locked": locked, "at": _now(), "by": by}}, upsert=True)


async def assert_item_editable(db, app_doc: dict, kind: str, item_id: str, user: dict, name: str = "") -> Optional[dict]:
    """Raise 423 when a client tries to change a locked item. Returns a consumed-later grant, if any."""
    if not await is_locked(db, app_doc["app_id"], kind, item_id):
        return None
    from page_guard import role_of
    if await role_of(db, app_doc, user) in ("owner", "admin"):
        return None

    grant = await active_grant(db, app_doc["app_id"], item_id, user["user_id"])
    if grant:
        return grant
    label = LABELS.get(kind, "item")
    raise HTTPException(423, f"This {label}{f' ({name})' if name else ''} is locked by the agency. "
                             "Use “Request a change” to ask them to open it.")


async def _inventory(db, app_id: str):
    """Every lockable item in a client, as (kind, item_id, name) tuples."""
    items = []
    pages = await db.pages.find({"app_id": app_id}, {"_id": 0, "page_id": 1, "name": 1, "blocks": 1, "locked": 1}).to_list(200)
    for pg in pages:
        items.append(("page", pg["page_id"], pg.get("name") or "Page"))
        for b in pg.get("blocks") or []:
            if b.get("id"):
                kind = "form" if b.get("type") == "form" else "block"
                items.append((kind, b["id"], f"{pg.get('name')} · {b.get('type')}"))
    for c in await db.cms_collections.find({"app_id": app_id}, {"_id": 0, "collection_id": 1, "name": 1}).to_list(80):
        items.append(("cms_collection", c["collection_id"], c.get("name") or "Collection"))
    for it in await db.cms_items.find({"app_id": app_id}, {"_id": 0, "item_id": 1, "title": 1}).to_list(500):
        items.append(("cms_item", it["item_id"], it.get("title") or "Item"))
    for w in await db.workflows.find({"app_id": app_id}, {"_id": 0, "workflow_id": 1, "name": 1}).to_list(200):
        items.append(("workflow", w["workflow_id"], w.get("name") or "Workflow"))
    if await db.data_destinations.count_documents({"app_id": app_id}):
        items.append(("data_destination", "default", "Client database / drive"))
    items.append(("app_mode", "default", "App Mode blueprint"))
    items.append(("overview", "default", "Overview & site snapshot"))
    return items


async def lock_map(db, app_id: str) -> dict:
    """{kind: {item_id: True}} of everything currently locked."""
    out = {}
    for pg in await db.pages.find({"app_id": app_id, "locked": True}, {"_id": 0, "page_id": 1}).to_list(200):
        out.setdefault("page", {})[pg["page_id"]] = True
    for d in await db.item_locks.find({"app_id": app_id, "locked": True}, {"_id": 0, "kind": 1, "item_id": 1}).to_list(2000):
        out.setdefault(d["kind"], {})[d["item_id"]] = True
    return out


async def summary(db, app_id: str) -> dict:
    inv = await _inventory(db, app_id)
    lm = await lock_map(db, app_id)
    locked = sum(1 for k, i, _ in inv if lm.get(k, {}).get(i))
    total = len(inv)
    app = await db.apps.find_one({"app_id": app_id}, {"_id": 0, "content_locked": 1})
    state = "unlocked" if locked == 0 else ("locked" if locked >= total else "partial")
    return {"app_id": app_id, "state": state, "locked": locked, "total": total,
            "master": bool((app or {}).get("content_locked"))}


async def apply_all(db, app_id: str, locked: bool, by: str) -> dict:
    inv = await _inventory(db, app_id)
    await db.pages.update_many({"app_id": app_id}, {"$set": {"locked": locked, "locked_at": _now()}})
    ops = []
    from pymongo import UpdateOne
    for kind, item_id, _n in inv:
        ops.append(UpdateOne({"app_id": app_id, "kind": kind, "item_id": item_id},
                             {"$set": {"locked": locked, "at": _now(), "by": by}}, upsert=True))
    if ops:
        await db.item_locks.bulk_write(ops, ordered=False)
    await db.apps.update_one({"app_id": app_id}, {"$set": {"content_locked": locked, "locked_at": _now()}})
    return {"locked": locked, "items": len(inv)}


async def consume_if_grant(db, grant: Optional[dict], app_id: str, user: dict, log_activity=None):
    """A single-use grant is spent the moment the client's change lands."""
    if not grant:
        return
    await consume_grant(db, grant["grant_id"])
    await db.messages.update_one({"message_id": grant.get("message_id")},
                                 {"$set": {"edit_request.state": "completed", "edit_request.completed_at": _now()}})
    if log_activity:
        await log_activity(app_id, user["user_id"], "edit.completed", "Approved change saved on a locked item")


async def blocked_block_edits(db, app_id: str, prev_blocks: list, next_blocks: list) -> list:
    """Ids of locked sections/forms the incoming save would change, remove or reorder."""
    lm = await lock_map(db, app_id)
    locked = {**lm.get("block", {}), **lm.get("form", {})}
    if not locked:
        return []
    import json
    nxt = {b.get("id"): b for b in next_blocks or []}
    order_prev = [b.get("id") for b in prev_blocks or []]
    order_next = [b.get("id") for b in next_blocks or []]
    hit = []
    for i, b in enumerate(prev_blocks or []):
        bid = b.get("id")
        if not locked.get(bid):
            continue
        after = nxt.get(bid)
        moved = bid in order_next and order_next.index(bid) != order_prev.index(bid)
        if after is None or moved or json.dumps(after, sort_keys=True) != json.dumps(b, sort_keys=True):
            hit.append(bid)
    return hit


class AllIn(BaseModel):    locked: bool


class ItemIn(BaseModel):
    kind: str
    item_id: str
    locked: bool


def register(api, db, get_current_user, get_user_app, log_activity):
    from page_guard import role_of

    async def _require_admin(app_id: str, user: dict):
        doc = await get_user_app(app_id, user)
        if await role_of(db, doc, user) not in ("owner", "admin"):
            raise HTTPException(403, "Only the agency owner or an admin can change locks")
        return doc

    @api.get("/apps/{app_id}/locks")
    async def get_locks(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        role = await role_of(db, doc, user)
        return {**await summary(db, app_id), "locks": await lock_map(db, app_id),
                "role": role, "can_manage": role in ("owner", "admin")}

    @api.post("/apps/{app_id}/locks/all")
    async def lock_all(app_id: str, body: AllIn, user: dict = Depends(get_current_user)):
        await _require_admin(app_id, user)
        res = await apply_all(db, app_id, body.locked, user.get("name") or user["email"])
        await log_activity(app_id, user["user_id"], "locks.all",
                           f"{'Locked' if body.locked else 'Unlocked'} all {res['items']} item(s) across this client")
        return {**await summary(db, app_id), "locks": await lock_map(db, app_id), **res}

    @api.post("/apps/{app_id}/locks/item")
    async def lock_item(app_id: str, body: ItemIn, user: dict = Depends(get_current_user)):
        await _require_admin(app_id, user)
        if body.kind not in KINDS:
            raise HTTPException(400, f"Unknown lock kind '{body.kind}'")
        await set_lock(db, app_id, body.kind, body.item_id, body.locked, user.get("name") or user["email"])
        await log_activity(app_id, user["user_id"], "locks.item",
                           f"{LABELS[body.kind].title()} {'locked' if body.locked else 'unlocked'}")
        return {**await summary(db, app_id), "kind": body.kind, "item_id": body.item_id, "locked": body.locked}

    @api.get("/locks/summary")
    async def locks_summary(user: dict = Depends(get_current_user)):
        """Lock rollup for every client the user can see — powers the dashboard card badges."""
        ms = await db.memberships.find({"user_id": user["user_id"]}, {"_id": 0, "app_id": 1}).to_list(500)
        apps = await db.apps.find({"$or": [{"owner_id": user["user_id"]}, {"app_id": {"$in": [m["app_id"] for m in ms]}}]},
                                  {"_id": 0, "app_id": 1}).to_list(500)
        return {"tenants": {a["app_id"]: await summary(db, a["app_id"]) for a in apps}}

    return {"assert_item_editable": assert_item_editable, "is_locked": is_locked, "summary": summary}
