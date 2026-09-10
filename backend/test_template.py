"""Test Template — the permanent sandbox template.

Same credit-safe contract as the Test Lab tenant: template design work lands on `test_template` only,
and reaches the real templates through an explicit "Push to One Template" / "Push to All Templates"
action that goes via the diff viewer, the confirmation modal, the history log and undo.

Template looks are stored in Mongo (`template_looks`) so a push survives a restart.
"""
import logging
from copy import deepcopy
from typing import List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("agency.test_template")

TEST_TEMPLATE_KEY = "test_template"
TEST_TEMPLATE_BRAND = "Test Template"
BASE_KEY = "it_services"  # neutral base clone — no client-facing template is ever used as the sandbox

# Look fields we can diff and push, grouped the same way the Diff Viewer groups them.
LOOK_FIELDS = [
    ("mode", "Design", "Light / dark mode"),
    ("primary", "Design", "Primary colour"),
    ("secondary", "Design", "Secondary colour"),
    ("bg", "Design", "Background colour"),
    ("surface", "Design", "Surface colour"),
    ("border", "Design", "Border colour"),
    ("fg", "Design", "Text colour"),
    ("muted", "Design", "Muted text colour"),
    ("font_heading", "Design", "Heading font"),
    ("font_body", "Design", "Body font"),
    ("radius", "Design", "Corner radius"),
    ("preset", "Design", "Section style preset"),
    ("hero", "Design", "Hero layout"),
    ("glass", "Animations", "Glass-morphism surfaces"),
    ("grain", "Animations", "Grain / noise overlay"),
    ("studio", "Features", "Studio 2026 component set"),
    ("look_v", "Features", "Look version"),
    # Editorial motion design system — the new default standard, staged on the Test Template first.
    ("editorial", "Design", "Editorial motion design layer"),
    ("ed_dark_base", "Design", "Dark near-black base option"),
    ("ed_bento", "Layout", "Bento grid features section"),
    ("ed_float_gallery", "Layout", "Floating scattered gallery cards"),
    ("ed_ribbon", "Layout", "Scrolling ribbon after the hero"),
    ("ed_reveal", "Animations", "Scroll reveal (fade + translate + stagger)"),
    ("ed_counters", "Animations", "Rolling number counters on stats"),
    ("ed_glow_paths", "Animations", "Glowing hero path lines"),
    ("ed_parallax", "Animations", "Cursor parallax on hero images"),
]

# Applied to the Test Template only. The original values stay in template_looks history so the
# existing rollout undo can revert this in one click.
EDITORIAL_LAYER = {
    "editorial": True,
    "ed_dark_base": True,
    "ed_bento": True,
    "ed_float_gallery": True,
    "ed_ribbon": True,
    "ed_reveal": True,
    "ed_counters": True,
    "ed_glow_paths": True,
    "ed_parallax": True,
}


async def apply_editorial_to_test_template(db) -> bool:
    """Stages the editorial motion system on the sandbox template. Never touches a live template."""
    from site_content import LOOKS
    look = LOOKS.get(TEST_TEMPLATE_KEY)
    if look is None:
        return False
    if all(look.get(k) == v for k, v in EDITORIAL_LAYER.items()):
        return False
    look.update(EDITORIAL_LAYER)
    await db.template_looks.update_one(
        {"key": TEST_TEMPLATE_KEY},
        {"$set": {"key": TEST_TEMPLATE_KEY, "look": look, "editorial_staged": True}},
        upsert=True)
    logger.info("Editorial motion layer staged on the Test Template")
    return True


def install():
    """Register the sandbox template into the shared LOOKS / NICHES tables (idempotent)."""
    from site_content import LOOKS, NICHES, LOOK_V
    if TEST_TEMPLATE_KEY in LOOKS:
        return False
    NICHES[TEST_TEMPLATE_KEY] = deepcopy(NICHES[BASE_KEY])
    NICHES[TEST_TEMPLATE_KEY]["brand"] = TEST_TEMPLATE_BRAND
    NICHES[TEST_TEMPLATE_KEY]["industry"] = "Sandbox"
    LOOKS[TEST_TEMPLATE_KEY] = {**deepcopy(LOOKS[BASE_KEY]), "look_v": LOOK_V}
    return True


async def load_overrides(db) -> int:
    """Re-apply every look that has been pushed through the Test Template before."""
    from site_content import LOOKS, NICHES
    n = 0
    async for doc in db.template_looks.find({}, {"_id": 0}):
        key, look = doc.get("key"), doc.get("look") or {}
        if key in LOOKS and look:
            LOOKS[key].update(look)
            if "primary" in look:
                NICHES[key]["primary"] = look["primary"]
            if "secondary" in look:
                NICHES[key]["secondary"] = look["secondary"]
            n += 1
    return n


def register(api, db, get_current_user, log_activity):
    from test_lab import (TEST_LAB_ID, _now, _uid, _common, _look_hash)

    class TplRolloutIn(BaseModel):
        scope: str = "all"                  # all | classic | studio | selected
        keys: Optional[List[str]] = None    # used when scope == "selected"
        changes: Optional[List[str]] = None
        confirm: str = ""

    async def _rollout_admins() -> List[str]:
        import os
        doc = await db.platform_settings.find_one({"_id": "rollout_admins"}) or {}
        base = (os.environ.get("ADMIN_EMAIL") or "").lower().strip()
        return [e for e in [base, *[x.lower().strip() for x in (doc.get("emails") or [])]] if e]

    async def _require_admin(user: dict):
        if (user.get("email") or "").lower().strip() not in await _rollout_admins():
            raise HTTPException(403, "Only a rollout admin can push template changes")

    def _resolve_targets(scope: str, keys: Optional[List[str]]) -> List[str]:
        from site_content import LOOKS
        if scope == "selected":
            picked = [k for k in (keys or []) if k in LOOKS and k != TEST_TEMPLATE_KEY]
            if not picked:
                raise HTTPException(400, "Choose at least one template to push to")
            return picked
        out = [k for k in LOOKS if k != TEST_TEMPLATE_KEY]
        if scope == "classic":
            return [k for k in out if not LOOKS[k].get("studio")]
        if scope == "studio":
            return [k for k in out if LOOKS[k].get("studio")]
        return out

    def _build_look_diff(targets: List[str]) -> dict:
        from site_content import LOOKS
        lab = LOOKS[TEST_TEMPLATE_KEY]
        rows = []
        for field, cat, label in LOOK_FIELDS:
            new = lab.get(field)
            lives = [LOOKS[k].get(field) for k in targets]
            differing = [v for v in lives if v != new]
            if not targets or not differing:
                continue
            old, variance = _common(differing)
            rows.append({"id": f"{cat.lower()}.{field}", "category": cat, "label": label,
                         "old": old, "new": new,
                         "kind": "added" if old in (None, "") else ("removed" if new in (None, "") else "changed"),
                         "tenants": len(differing), "variance": variance})
        by_cat: dict = {}
        for r in rows:
            by_cat.setdefault(r["category"], []).append(r)
        return {"changes": rows, "by_category": by_cat, "total": len(rows),
                "target_count": len(targets),
                "targets": [{"app_id": k, "name": k} for k in targets],
                "generated_at": _now()}

    @api.post("/test-template/push-staging")
    async def push_test_template_staging(body: TplRolloutIn, user: dict = Depends(get_current_user)):
        """Real-environment check: apply the Test Template look to the staging tenant only."""
        from site_content import LOOKS
        await _require_admin(user)
        # Override: template pushes apply without typing CONFIRM.
        staging = await db.apps.find_one({"is_staging": True}, {"_id": 0})
        if not staging:
            raise HTTPException(404, "No staging tenant configured")
        lab = LOOKS[TEST_TEMPLATE_KEY]
        picked = set(body.changes) if body.changes is not None else None
        fields = [f for f, cat, _l in LOOK_FIELDS
                  if picked is None or f"{cat.lower()}.{f}" in picked]
        if not fields:
            raise HTTPException(400, "Select at least one change to push")
        job_id = _uid("tplstag")
        rows = [{"id": f"design.{f}", "category": "Design", "label": f"Template token “{f}”",
                 "old": (staging.get("theme") or {}).get(f), "new": lab.get(f), "kind": "changed",
                 "tenants": 1, "variance": False} for f in fields]
        await db.rollout_snapshots.insert_one({
            "snapshot_id": _uid("snap"), "job_id": job_id, "app_id": staging["app_id"],
            "before": {"theme": staging.get("theme")}, "created_at": _now()})
        await db.apps.update_one({"app_id": staging["app_id"]}, {"$set": {
            "theme": {**(staging.get("theme") or {}), **{f: lab.get(f) for f in fields}},
            "updated_at": _now()}})
        await db.rollout_jobs.insert_one({
            "job_id": job_id, "kind": "template_staging", "status": "done", "pct": 100, "done": 1,
            "changed": 1, "failed": 0, "total": 1, "by": user["user_id"],
            "by_email": user.get("email"), "by_name": user.get("name"), "categories": ["Design"],
            "diff": {"changes": rows, "by_category": {"Design": rows}, "total": len(rows),
                     "target_count": 1,
                     "targets": [{"app_id": staging["app_id"], "name": staging.get("name")}]},
            "detail": f"Applied {len(fields)} Test Template change(s) to staging",
            "created_at": _now(), "finished_at": _now()})
        await log_activity(TEST_LAB_ID, user["user_id"], "rollout.template_staging",
                           f"Pushed {len(fields)} Test Template change(s) to staging")
        return {"ok": True, "job_id": job_id, "staging": staging["app_id"], "changes": len(fields)}

    @api.get("/test-template")
    async def get_test_template(user: dict = Depends(get_current_user)):
        from site_content import LOOKS
        states = {d["key"]: d for d in await db.template_states.find({}, {"_id": 0}).to_list(100)}
        admins = await _rollout_admins()
        return {
            "key": TEST_TEMPLATE_KEY, "brand": TEST_TEMPLATE_BRAND,
            "look": LOOKS[TEST_TEMPLATE_KEY],
            "is_rollout_admin": (user.get("email") or "").lower().strip() in admins,
            "templates": [{"key": k, "studio": bool(LOOKS[k].get("studio")), "pending": False}
                          for k in LOOKS if k != TEST_TEMPLATE_KEY],
        }

    @api.get("/test-template/diff")
    async def test_template_diff(scope: str = "all", keys: Optional[str] = None,
                                 user: dict = Depends(get_current_user)):
        targets = _resolve_targets(scope, (keys or "").split(",") if keys else None)
        return {**_build_look_diff(targets), "scope": scope, "target_keys": targets}

    @api.post("/test-template/rollout")
    async def push_test_template(body: TplRolloutIn, user: dict = Depends(get_current_user)):
        from site_content import LOOKS, NICHES
        await _require_admin(user)
        # Override: template pushes apply without typing CONFIRM.
        targets = _resolve_targets(body.scope, body.keys)
        diff = _build_look_diff(targets)
        picked = set(body.changes) if body.changes is not None else {c["id"] for c in diff["changes"]}
        fields = [f for f, cat, _l in LOOK_FIELDS if f"{cat.lower()}.{f}" in picked]
        if not fields:
            raise HTTPException(400, "Select at least one change to push")
        rows = [c for c in diff["changes"] if c["id"] in picked]
        by_cat: dict = {}
        for r in rows:
            by_cat.setdefault(r["category"], []).append(r)

        job_id = _uid("tpllook")
        lab = LOOKS[TEST_TEMPLATE_KEY]
        for key in targets:
            await db.rollout_snapshots.insert_one({
                "snapshot_id": _uid("snap"), "job_id": job_id, "template_key": key,
                "before_look": {f: LOOKS[key].get(f) for f in fields}, "created_at": _now()})
            patch = {f: lab.get(f) for f in fields}
            LOOKS[key].update(patch)
            if "primary" in patch:
                NICHES[key]["primary"] = patch["primary"]
            if "secondary" in patch:
                NICHES[key]["secondary"] = patch["secondary"]
            await db.template_looks.update_one({"key": key}, {"$set": {"key": key, "look": LOOKS[key],
                                                                      "updated_at": _now()}}, upsert=True)
            # always-live: the change is applied to tenants on this template immediately
            await db.template_states.update_one({"key": key}, {"$set": {
                "key": key, "status": "live", "look_hash": _look_hash(key), "pending_hash": None,
                "updated_at": _now()}}, upsert=True)
            from auto_propagate import apply_template
            await apply_template(db, key)

        await db.rollout_jobs.insert_one({
            "job_id": job_id, "kind": "template_look", "scope": body.scope, "template_keys": targets,
            "status": "done", "pct": 100, "done": len(targets), "changed": len(targets), "failed": 0,
            "total": len(targets), "by": user["user_id"], "by_email": user.get("email"),
            "by_name": user.get("name"), "categories": sorted(by_cat.keys()),
            "diff": {"changes": rows, "by_category": by_cat, "total": len(rows),
                     "target_count": len(targets),
                     "targets": [{"app_id": k, "name": k} for k in targets]},
            "detail": f"Applied {len(fields)} change(s) to {len(targets)} template(s)",
            "created_at": _now(), "finished_at": _now()})
        await log_activity(TEST_LAB_ID, user["user_id"], "rollout.template_look",
                           f"Pushed {len(fields)} Test Template change(s) to {len(targets)} template(s)")
        return {"ok": True, "job_id": job_id, "templates_updated": len(targets), "changes": len(fields)}
