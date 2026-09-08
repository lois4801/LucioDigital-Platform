import os
from datetime import datetime, timezone
from typing import Dict, Optional
from fastapi import HTTPException, Depends
from pydantic import BaseModel

MAX_KEYS = 200


class LabelsPatch(BaseModel):
    labels: Optional[Dict[str, str]] = None
    styles: Optional[Dict[str, Dict[str, str]]] = None
    scope: Optional[str] = "tenant"  # tenant | global


def _is_platform_admin(user: dict) -> bool:
    return (user.get("email") or "").lower().strip() == os.environ["ADMIN_EMAIL"].lower().strip()


def _key(k: str) -> str:
    return (k or "").strip().replace(".", "_").replace("$", "_")[:80]


def _clean(labels: Dict[str, str]) -> Dict[str, str]:
    out = {}
    for k, v in list(labels.items())[:MAX_KEYS]:
        k = _key(k)
        if k:
            out[k] = (v or "").strip()[:400]
    return out


def _clean_styles(styles: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    out = {}
    for k, v in list(styles.items())[:MAX_KEYS]:
        k = _key(k)
        if not k or not isinstance(v, dict):
            continue
        out[k] = {
            "font": (v.get("font") or "").strip()[:120],
            "color": (v.get("color") or "").strip()[:40],
        }
    return out


class CursorVoteIn(BaseModel):
    effect: str


CURSOR_FX = {"none": "None", "fairy": "Fairy Dust", "bubbles": "Water Bubbles", "smoke": "Mystic Smoke",
             "fire": "Fire & Embers", "wind": "Wind & Petals", "frost": "Frost & Snowfall",
             "plasma": "Neon Plasma", "ink": "Liquid Ink", "comet": "Cosmic Comet", "matrix": "Digital Matrix"}


def register(api, db, get_current_user, get_user_app):
    async def _globals() -> dict:
        doc = await db.site_settings.find_one({"key": "ui_labels"}, {"_id": 0}) or {}
        return {"labels": doc.get("labels", {}), "styles": doc.get("styles", {})}

    async def _can_edit(app_doc: dict, user: dict) -> bool:
        return _is_platform_admin(user) or app_doc["owner_id"] == user["user_id"]

    def _shape(g: dict, t_labels: dict, t_styles: dict, can_edit: bool) -> dict:
        return {
            "labels": {**g["labels"], **t_labels},
            "styles": {**g["styles"], **t_styles},
            "tenant": t_labels,
            "tenant_styles": t_styles,
            "global": g["labels"],
            "global_styles": g["styles"],
            "can_edit": can_edit,
        }

    @api.get("/apps/{app_id}/cursor-vote")
    async def get_cursor_vote(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        return {"vote": doc.get("cursor_vote"), "current": (doc.get("theme") or {}).get("cursor_effect") or "none"}

    @api.post("/apps/{app_id}/cursor-vote")
    async def set_cursor_vote(app_id: str, body: CursorVoteIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        if body.effect not in CURSOR_FX:
            raise HTTPException(400, "Unknown cursor effect")
        vote = {
            "effect": body.effect,
            "label": CURSOR_FX[body.effect],
            "by": user.get("name") or user.get("email"),
            "at": datetime.now(timezone.utc).isoformat(),
            "applied": False,
        }
        await db.apps.update_one({"app_id": app_id}, {"$set": {"cursor_vote": vote}})
        return {"vote": vote}

    @api.post("/apps/{app_id}/cursor-vote/apply")
    async def apply_cursor_vote(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        if not (_is_platform_admin(user) or doc["owner_id"] == user["user_id"]):
            raise HTTPException(403, "Only the platform admin or tenant owner can apply a vote")
        vote = doc.get("cursor_vote")
        if not vote:
            raise HTTPException(404, "No client vote yet")
        theme = {**(doc.get("theme") or {}), "cursor_effect": vote["effect"]}
        await db.apps.update_one({"app_id": app_id}, {"$set": {"theme": theme, "cursor_vote.applied": True}})
        return {"vote": {**vote, "applied": True}, "theme": theme}

    @api.get("/apps/{app_id}/ui_labels")
    async def get_ui_labels(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        return _shape(await _globals(), doc.get("ui_overrides") or {}, doc.get("ui_label_styles") or {}, await _can_edit(doc, user))

    @api.put("/apps/{app_id}/ui_labels")
    async def put_ui_labels(app_id: str, body: LabelsPatch, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        if not await _can_edit(doc, user):
            raise HTTPException(403, "Only the platform admin or tenant owner can edit labels")
        labels = _clean(body.labels or {})
        # These three now follow Site Mode, so an override here would only become dead data.
        from content_lock import SYNCED_LABEL_KEYS
        ignored = [k for k in labels if k in SYNCED_LABEL_KEYS]
        labels = {k: v for k, v in labels.items() if k not in SYNCED_LABEL_KEYS}
        styles = _clean_styles(body.styles or {})
        if not labels and not styles:
            if ignored:
                return {"ok": True, "ignored": ignored,
                        "note": "The Overview title and summary follow Site Mode — edit the Navbar brand and hero copy instead."}
            raise HTTPException(400, "No labels or styles provided")
        ts = datetime.now(timezone.utc).isoformat()
        if body.scope == "global":
            if not _is_platform_admin(user):
                raise HTTPException(403, "Only the platform admin can set global defaults")
            g = await _globals()
            g = {"labels": {**g["labels"], **labels}, "styles": {**g["styles"], **styles}}
            await db.site_settings.update_one(
                {"key": "ui_labels"},
                {"$set": {"key": "ui_labels", **g, "updated_at": ts, "updated_by": user["email"]}},
                upsert=True,
            )
        else:
            sets = {f"ui_overrides.{k}": v for k, v in labels.items()}
            sets.update({f"ui_label_styles.{k}": v for k, v in styles.items()})
            await db.apps.update_one({"app_id": app_id}, {"$set": {**sets, "updated_at": ts}})
        fresh = await db.apps.find_one({"app_id": app_id}, {"_id": 0, "ui_overrides": 1, "ui_label_styles": 1}) or {}
        return _shape(await _globals(), fresh.get("ui_overrides") or {}, fresh.get("ui_label_styles") or {}, True)

    @api.delete("/apps/{app_id}/ui_labels")
    async def reset_ui_labels(app_id: str, scope: str = "tenant", user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        if not await _can_edit(doc, user):
            raise HTTPException(403, "Only the platform admin or tenant owner can edit labels")
        await db.apps.update_one({"app_id": app_id}, {"$unset": {"ui_overrides": "", "ui_label_styles": ""}})
        if scope == "all":
            if not _is_platform_admin(user):
                raise HTTPException(403, "Only the platform admin can reset global defaults")
            await db.site_settings.update_one({"key": "ui_labels"}, {"$set": {"labels": {}, "styles": {}}}, upsert=True)
        return _shape(await _globals(), {}, {}, True)
