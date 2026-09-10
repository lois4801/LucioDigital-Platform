"""Always-live auto-propagation.

There is no pending state, no queue and no push button anywhere on the platform. Any design or
motion change is applied to its source template immediately, pushed to every active client using
that template, and inherited by every future client created from it.

Propagation order (enforced here):
  1. change lands on the source template / master workspace
  2. it is written to every active client using that template
  3. platform defaults are updated so future clients inherit it at creation time

CONTENT IS NEVER TOUCHED: only theme tokens, site_mode design flags and motion_profile move.
Pages, blocks, copy, imagery, CTA forms, stats, leads and client data are never read or written.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Depends

logger = logging.getLogger("agency.auto_propagate")

MASTER_ID = "app_testlab"          # LucioDigital Test Lab — the live master workspace
DESIGN_KEYS = ("style", "mode", "animation")   # never publish/content/template_key


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _tenants_on(db, key: str):
    return await db.apps.find(
        {"site_niche": key, "archived": {"$ne": True}, "app_id": {"$ne": MASTER_ID}},
        {"_id": 0, "app_id": 1, "name": 1, "theme": 1, "site_mode": 1, "motion_profile": 1},
    ).to_list(500)


async def apply_template(db, key: str) -> Dict[str, Any]:
    """Applies a template's current design + motion to every active client using it."""
    from site_content import LOOKS, NICHES, theme_for
    from editorial_rollout import profile_for
    if key not in LOOKS:
        return {"key": key, "tenants": []}
    look = theme_for(NICHES[key], key)
    updated = []
    for t in await _tenants_on(db, key):
        sm = t.get("site_mode") or {}
        prof = dict(t.get("motion_profile") or {})
        # per-client overrides always win; otherwise inherit the template's motion
        inherited = profile_for(key, sm.get("accent") or prof.get("accent"))
        if not sm.get("hero"):
            prof["hero"] = inherited["hero"]
        if not sm.get("accent"):
            prof["accent"] = inherited["accent"]
        prof.update({k: inherited[k] for k in ("layout", "reveal", "counter", "template_key", "version")})
        prof["speed"] = float(sm.get("motion_speed") or prof.get("speed") or 1.0)
        prof["intensity"] = float(sm.get("motion_intensity") or prof.get("intensity") or 1.0)
        await db.apps.update_one({"app_id": t["app_id"]}, {"$set": {
            "theme": {**(t.get("theme") or {}), **look},
            "motion_profile": prof,
            "updated_at": _now(),
        }})
        updated.append(t.get("name") or t["app_id"])
    await db.template_states.update_one({"key": key}, {"$set": {
        "key": key, "status": "live", "pending_hash": None,
        "auto_applied_at": _now(), "updated_at": _now()}}, upsert=True)
    return {"key": key, "tenants": updated}


async def run(db) -> Dict[str, int]:
    """Full sweep — every template applied to every client using it. Runs on every boot."""
    from site_content import LOOKS
    from test_lab import _look_hash
    templates = 0
    clients = 0
    for key in LOOKS:
        res = await apply_template(db, key)
        templates += 1
        clients += len(res["tenants"])
        await db.template_states.update_one({"key": key}, {"$set": {"look_hash": _look_hash(key)}}, upsert=True)
    return {"templates": templates, "tenants": clients}


async def propagate_site_mode(db, app_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    """A change saved in the master workspace becomes the platform's live state everywhere."""
    if app_id != MASTER_ID:
        return {"propagated": False}
    design = {k: patch[k] for k in DESIGN_KEYS if patch.get(k) is not None}
    if not design:
        return {"propagated": False}
    touched = []
    async for app in db.apps.find({"archived": {"$ne": True}, "app_id": {"$ne": MASTER_ID}},
                                  {"_id": 0, "app_id": 1, "name": 1, "site_mode": 1}):
        sm = dict(app.get("site_mode") or {})
        sm.update(design)
        sm["updated_at"] = _now()
        await db.apps.update_one({"app_id": app["app_id"]}, {"$set": {"site_mode": sm}})
        touched.append(app.get("name") or app["app_id"])
    # future clients inherit at creation
    defaults = (await db.platform_settings.find_one({"_id": "site_mode_defaults"}) or {})
    await db.platform_settings.update_one(
        {"_id": "site_mode_defaults"},
        {"$set": {**{k: v for k, v in defaults.items() if k != "_id"}, **design, "updated_at": _now()}},
        upsert=True)
    return {"propagated": True, "tenants": touched}


def register(api, db, get_current_user):

    @api.get("/auto-propagate/status")
    async def status(user: dict = Depends(get_current_user)):
        return {"auto": True, "pending": 0, "queue": [], "master": MASTER_ID,
                "note": "Every change is applied instantly — there is no pending state."}

    @api.post("/auto-propagate/run")
    async def run_now(user: dict = Depends(get_current_user)):
        res = await run(db)
        return {"ok": True, **res}

    @api.post("/auto-propagate/templates/{key}")
    async def run_one(key: str, user: dict = Depends(get_current_user)):
        return {"ok": True, **(await apply_template(db, key))}
