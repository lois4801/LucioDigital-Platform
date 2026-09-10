"""Client onboarding checklist: a short guided list that ticks itself off as the client works,
with manual tick/skip for anything we cannot detect."""
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import Depends, HTTPException
from pydantic import BaseModel

STEPS: List[Dict[str, str]] = [
    {"id": "logo", "label": "Add your logo", "hint": "Upload it once and it appears across every page.", "where": "site-mode"},
    {"id": "address", "label": "Confirm your business address", "hint": "It powers your map, directions and contact details.", "where": "site-mode"},
    {"id": "figures", "label": "Replace the demo figures", "hint": "Type your own numbers or drop in a spreadsheet.", "where": "figures"},
    {"id": "reviews", "label": "Check your reviews", "hint": "Edit, add or remove any of the reviews on your site.", "where": "reviews"},
    {"id": "accent", "label": "Pick your accent colour", "hint": "Everything on the site recolours instantly.", "where": "site-mode"},
    {"id": "live", "label": "Go live", "hint": "Switch publishing from draft to live when you are happy.", "where": "publishing"},
]


def register(api, db, get_current_user, get_user_app, log_activity):

    class MarkIn(BaseModel):
        state: str = "done"        # done | skipped | reset

    async def _status(app: dict) -> Dict[str, Any]:
        sm = app.get("site_mode") or {}
        manual = app.get("onboarding") or {}
        auto = {
            "logo": bool(app.get("logo_url") or (app.get("brand_profile") or {}).get("logo")),
            "address": bool(sm.get("address") or (app.get("brand_profile") or {}).get("address")),
            "figures": (app.get("vitals") or {}).get("source") in ("imported", "custom")
            or bool((app.get("vitals") or {}).get("metrics")),
            "reviews": bool((app.get("reviews") or {}).get("reviews")),
            "accent": bool(sm.get("accent")),
            "live": sm.get("publish") == "live",
        }
        steps = []
        for s in STEPS:
            state = manual.get(s["id"])
            done = state == "done" or (state != "reset" and auto.get(s["id"], False))
            steps.append({**s, "done": bool(done), "skipped": state == "skipped",
                          "auto": auto.get(s["id"], False), "manual": state or ""})
        counted = [s for s in steps if not s["skipped"]]
        done_n = sum(1 for s in counted if s["done"])
        return {"steps": steps, "done": done_n, "total": len(counted),
                "complete": done_n >= len(counted) and len(counted) > 0}

    @api.get("/apps/{app_id}/onboarding")
    async def get_onboarding(app_id: str, user: dict = Depends(get_current_user)):
        app = await get_user_app(app_id, user)
        return await _status(app)

    @api.post("/apps/{app_id}/onboarding/{step_id}")
    async def mark_step(app_id: str, step_id: str, body: MarkIn, user: dict = Depends(get_current_user)):
        app = await get_user_app(app_id, user)
        if step_id not in [s["id"] for s in STEPS]:
            raise HTTPException(400, f"Unknown step: {step_id}")
        if body.state not in ("done", "skipped", "reset"):
            raise HTTPException(400, "State must be done, skipped or reset")
        cur = dict(app.get("onboarding") or {})
        cur[step_id] = body.state
        cur["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.apps.update_one({"app_id": app_id}, {"$set": {"onboarding": cur}})
        await log_activity(app_id, user["user_id"], "onboarding.step", f"Marked '{step_id}' as {body.state}")
        return await _status({**app, "onboarding": cur})
