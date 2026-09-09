"""Test Lab tenant + controlled global rollout.

Permanent platform rule: every design/behaviour change lands on the Test Lab tenant only. It reaches
live tenants exclusively when a rollout admin clicks "Push to All Tenants" and confirms.

  - ensure_test_lab()          one protected tenant, preloaded with every template layout
  - mark_template_states()     detects template design changes and parks them as "pending"
  - /api/test-lab/*            preview, rollout (scoped, background, snapshotted), job progress
  - /api/templates/*/rollout   per-template push to the tenants using that template
"""
import asyncio
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("agency.test_lab")

TEST_LAB_ID = "app_testlab"
TEST_LAB_NAME = "LucioDigital Test Lab"

# What a rollout can copy from the Test Lab. Each scope is opt-in per rollout.
SCOPES = {
    "theme": ("Design tokens", "Colours, fonts, radius, glass/grain and the look version"),
    "mode": ("Light / dark mode", "The Test Lab's current light or dark mode"),
    "skin": ("UI skin", "Classic vs Studio 2026 site skin"),
    "motion": ("Motion & cursor", "Animation and cursor-effect settings"),
    "labels": ("UI labels", "Renamed sections and buttons"),
    "forms": ("CTA form defaults", "Field layout of matching CTA forms"),
}
THEME_KEYS = ("primary", "secondary", "bg", "surface", "border", "fg", "muted", "font_heading",
              "font_body", "radius", "preset", "hero", "glass", "grain", "design_v2", "premium_v",
              "look_v", "site_skin", "studio")
MOTION_KEYS = ("motion", "cursor")
APP_MOTION_KEYS = ("cursor_effect", "cursor_density", "cursor_speed")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(p: str) -> str:
    return f"{p}_{uuid.uuid4().hex[:12]}"


def _look_hash(key: str) -> str:
    from site_content import LOOKS
    return hashlib.sha256(json.dumps(LOOKS.get(key) or {}, sort_keys=True, default=str).encode()).hexdigest()[:16]


# ---------- Test Lab tenant ----------
async def ensure_test_lab(db, owner_id: str, build_pages=None) -> dict:
    """Idempotent. Creates the protected Test Lab tenant and preloads one page per template."""
    from site_content import LOOKS, NICHES, build_premium_site, theme_for
    doc = await db.apps.find_one({"app_id": TEST_LAB_ID}, {"_id": 0})
    if not doc:
        doc = {
            "app_id": TEST_LAB_ID, "owner_id": owner_id, "name": TEST_LAB_NAME,
            "industry": "Internal Tools", "kind": "website",
            "description": "Permanent sandbox for testing designs, animations, templates and new "
                           "features before anything is pushed to live tenants.",
            "status": "active", "tags": ["test", "sandbox"], "color": "#22D3EE",
            "is_test_lab": True, "protected": True, "archived": False, "transfer_mode": False,
            "theme": theme_for(NICHES["saas"], "saas") if "saas" in LOOKS else {},
            "site_niche": "saas", "premium_site_v": 3,
            "metrics": {"uptime": 100.0, "cpu": 8, "ram": 22, "response_ms": 90, "visitors_24h": 0},
            "created_at": _now(), "updated_at": _now(),
        }
        await db.apps.insert_one(dict(doc))
        doc.pop("_id", None)
        logger.info("Test Lab tenant created")
    else:
        await db.apps.update_one({"app_id": TEST_LAB_ID},
                                 {"$set": {"name": TEST_LAB_NAME, "is_test_lab": True,
                                           "protected": True, "archived": False,
                                           "description": "Permanent sandbox for testing designs, animations, "
                                                          "templates and new features before anything is pushed "
                                                          "to live tenants."}})

    existing = {p.get("template_key") for p in
                await db.pages.find({"app_id": TEST_LAB_ID}, {"_id": 0, "template_key": 1}).to_list(200)}
    order = len(existing)
    added = 0
    for key in LOOKS:
        if key in existing:
            continue
        try:
            pages, _theme, _n = build_premium_site({"app_id": TEST_LAB_ID, "name": NICHES[key]["brand"],
                                                    "industry": NICHES[key]["industry"]}, key,
                                                   {"name": NICHES[key]["brand"]})
        except Exception:
            logger.exception("Test Lab: could not build template %s", key)
            continue
        pname, _slug, blocks = pages[0]
        await db.pages.insert_one({
            "page_id": _uid("pg"), "app_id": TEST_LAB_ID, "template_key": key,
            "name": f"{NICHES[key]['brand']} · {key}",
            "slug": "/" if order == 0 else f"/t-{key}", "order": order,
            "blocks": blocks, "theme_preview": theme_for(NICHES[key], key),
            "updated_at": _now(),
        })
        order += 1
        added += 1
    if added:
        logger.info("Test Lab: preloaded %s template layout(s)", added)
    return await db.apps.find_one({"app_id": TEST_LAB_ID}, {"_id": 0})


async def retheme_test_lab_only(db) -> int:
    """Startup maintenance now stops at the Test Lab — live tenants are never re-themed silently."""
    from site_content import LOOKS, NICHES, theme_for
    doc = await db.apps.find_one({"app_id": TEST_LAB_ID}, {"_id": 0, "site_niche": 1, "theme": 1})
    if not doc:
        return 0
    key = doc.get("site_niche")
    if key not in LOOKS:
        return 0
    await db.apps.update_one({"app_id": TEST_LAB_ID},
                             {"$set": {"theme": {**(doc.get("theme") or {}), **theme_for(NICHES[key], key)}}})
    return 1


async def mark_template_states(db) -> int:
    """Any template whose design changed since the last push is parked as Pending Rollout."""
    from site_content import LOOKS
    pending = 0
    for key in LOOKS:
        h = _look_hash(key)
        doc = await db.template_states.find_one({"key": key}, {"_id": 0})
        if not doc:
            await db.template_states.update_one(
                {"key": key}, {"$set": {"key": key, "look_hash": h, "status": "live", "updated_at": _now()}},
                upsert=True)
            continue
        if doc.get("look_hash") != h:
            await db.template_states.update_one(
                {"key": key}, {"$set": {"pending_hash": h, "status": "pending", "updated_at": _now()}})
            pending += 1
        elif doc.get("status") == "pending" and doc.get("pending_hash") == h:
            pending += 1
    return pending


def register(api, db, get_current_user, get_user_app, log_activity):

    class RolloutIn(BaseModel):
        scopes: List[str] = []
        confirm: str = ""

    class AdminIn(BaseModel):
        email: str

    async def _rollout_admins() -> List[str]:
        doc = await db.platform_settings.find_one({"_id": "rollout_admins"}) or {}
        base = (os.environ.get("ADMIN_EMAIL") or "").lower().strip()
        extra = [e.lower().strip() for e in (doc.get("emails") or [])]
        return [e for e in [base, *extra] if e]

    async def _require_rollout_admin(user: dict) -> dict:
        email = (user.get("email") or "").lower().strip()
        if email not in await _rollout_admins():
            raise HTTPException(403, "Only a rollout admin can push changes to all tenants")
        return user

    def _check_confirm(word: str):
        if (word or "").strip().upper() != "CONFIRM":
            raise HTTPException(400, "Type CONFIRM to apply this rollout")

    async def _test_lab() -> dict:
        doc = await db.apps.find_one({"app_id": TEST_LAB_ID}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Test Lab tenant is missing — restart the backend to recreate it")
        return doc

    async def _targets() -> List[dict]:
        return await db.apps.find({"app_id": {"$ne": TEST_LAB_ID}, "archived": {"$ne": True}},
                                  {"_id": 0, "app_id": 1, "name": 1, "theme": 1, "site_niche": 1}).to_list(500)

    def _patch_for(scopes: List[str], lab: dict, target: dict) -> dict:
        """The $set patch a single tenant receives for the chosen scopes."""
        lab_theme = lab.get("theme") or {}
        theme = dict(target.get("theme") or {})
        upd: dict = {}
        if "theme" in scopes:
            theme.update({k: lab_theme[k] for k in THEME_KEYS if k in lab_theme})
        if "mode" in scopes and "mode" in lab_theme:
            theme["mode"] = lab_theme["mode"]
        if "motion" in scopes:
            theme.update({k: lab_theme[k] for k in MOTION_KEYS if k in lab_theme})
            upd.update({k: lab[k] for k in APP_MOTION_KEYS if k in lab})
        if "skin" in scopes:
            if "site_skin" in lab_theme:
                theme["site_skin"] = lab_theme["site_skin"]
            if "ui_skin" in lab:
                upd["ui_skin"] = lab["ui_skin"]
        if theme != (target.get("theme") or {}):
            upd["theme"] = theme
        return upd

    async def _snapshot_keys(scopes: List[str]) -> List[str]:
        keys = ["theme"]
        if "motion" in scopes:
            keys += list(APP_MOTION_KEYS)
        if "skin" in scopes:
            keys.append("ui_skin")
        return keys

    async def _run_rollout(job_id: str, scopes: List[str], user: dict):
        lab = await _test_lab()
        targets = await _targets()
        snap_keys = await _snapshot_keys(scopes)
        labels_doc = await db.ui_labels.find_one({"app_id": TEST_LAB_ID}, {"_id": 0}) if "labels" in scopes else None
        lab_forms = await db.cta_forms.find({"app_id": TEST_LAB_ID}, {"_id": 0}).to_list(100) if "forms" in scopes else []
        done = 0
        changed = 0
        for t in targets:
            try:
                full = await db.apps.find_one({"app_id": t["app_id"]}, {"_id": 0})
                await db.rollout_snapshots.insert_one({
                    "snapshot_id": _uid("snap"), "job_id": job_id, "app_id": t["app_id"],
                    "before": {k: full.get(k) for k in snap_keys}, "created_at": _now()})
                upd = _patch_for(scopes, lab, full)
                if upd:
                    upd["updated_at"] = _now()
                    await db.apps.update_one({"app_id": t["app_id"]}, {"$set": upd})
                    changed += 1
                if labels_doc:
                    await db.ui_labels.update_one(
                        {"app_id": t["app_id"]},
                        {"$set": {"labels": labels_doc.get("labels") or {}, "updated_at": _now()}}, upsert=True)
                for f in lab_forms:
                    await db.cta_forms.update_one(
                        {"app_id": t["app_id"], "key": f.get("key")},
                        {"$set": {"fields": f.get("fields") or [], "success_message": f.get("success_message"),
                                  "updated_at": _now()}})
            except Exception:
                logger.exception("rollout failed for %s", t["app_id"])
            done += 1
            await db.rollout_jobs.update_one({"job_id": job_id}, {"$set": {
                "done": done, "changed": changed, "pct": int(done / max(1, len(targets)) * 100)}})
            await asyncio.sleep(0)
        await db.rollout_jobs.update_one({"job_id": job_id}, {"$set": {
            "status": "done", "pct": 100, "finished_at": _now(),
            "detail": f"Applied to {changed} of {len(targets)} tenant(s)"}})
        await log_activity(TEST_LAB_ID, user["user_id"], "rollout.all",
                           f"Pushed {', '.join(scopes)} from the Test Lab to {changed} tenant(s)")

    # ---------- Test Lab ----------
    @api.get("/test-lab")
    async def get_test_lab(user: dict = Depends(get_current_user)):
        lab = await _test_lab()
        pages = await db.pages.count_documents({"app_id": TEST_LAB_ID})
        admins = await _rollout_admins()
        return {"app": lab, "template_pages": pages,
                "is_rollout_admin": (user.get("email") or "").lower().strip() in admins,
                "scopes": [{"key": k, "label": v[0], "description": v[1]} for k, v in SCOPES.items()]}

    @api.get("/test-lab/rollout/preview")
    async def rollout_preview(user: dict = Depends(get_current_user)):
        lab = await _test_lab()
        targets = await _targets()
        theme = lab.get("theme") or {}
        return {
            "target_count": len(targets),
            "targets": [{"app_id": t["app_id"], "name": t["name"]} for t in targets],
            "scopes": [{"key": k, "label": v[0], "description": v[1]} for k, v in SCOPES.items()],
            "current": {
                "theme": {k: theme.get(k) for k in ("primary", "secondary", "font_heading", "font_body", "radius", "look_v")},
                "mode": theme.get("mode"),
                "skin": theme.get("site_skin") or lab.get("ui_skin") or "classic",
                "motion": {"motion": theme.get("motion"), "cursor": theme.get("cursor"),
                           "cursor_effect": lab.get("cursor_effect")},
                "labels": bool(await db.ui_labels.find_one({"app_id": TEST_LAB_ID})),
                "forms": await db.cta_forms.count_documents({"app_id": TEST_LAB_ID}),
            },
        }

    @api.post("/test-lab/rollout")
    async def start_rollout(body: RolloutIn, user: dict = Depends(get_current_user)):
        await _require_rollout_admin(user)
        _check_confirm(body.confirm)
        scopes = [s for s in body.scopes if s in SCOPES]
        if not scopes:
            raise HTTPException(400, "Choose at least one thing to push")
        await _test_lab()
        targets = await _targets()
        job = {"job_id": _uid("roll"), "scopes": scopes, "status": "running", "pct": 0, "done": 0,
               "changed": 0, "total": len(targets), "by": user["user_id"], "by_email": user.get("email"),
               "detail": "Starting rollout", "created_at": _now()}
        await db.rollout_jobs.insert_one(dict(job))
        asyncio.create_task(_run_rollout(job["job_id"], scopes, user))
        job.pop("_id", None)
        return job

    @api.get("/test-lab/rollout/jobs")
    async def rollout_jobs(user: dict = Depends(get_current_user)):
        return {"jobs": await db.rollout_jobs.find({}, {"_id": 0}).sort("created_at", -1).to_list(10)}

    @api.get("/test-lab/rollout/jobs/{job_id}")
    async def rollout_job(job_id: str, user: dict = Depends(get_current_user)):
        job = await db.rollout_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(404, "Rollout job not found")
        return job

    # ---------- rollout admins ----------
    @api.get("/rollout-admins")
    async def list_rollout_admins(user: dict = Depends(get_current_user)):
        doc = await db.platform_settings.find_one({"_id": "rollout_admins"}) or {}
        return {"owner": (os.environ.get("ADMIN_EMAIL") or "").lower().strip(),
                "extra": doc.get("emails") or [],
                "is_rollout_admin": (user.get("email") or "").lower().strip() in await _rollout_admins()}

    @api.post("/rollout-admins")
    async def add_rollout_admin(body: AdminIn, user: dict = Depends(get_current_user)):
        await _require_rollout_admin(user)
        email = body.email.lower().strip()
        if "@" not in email:
            raise HTTPException(400, "Enter a valid email address")
        await db.platform_settings.update_one({"_id": "rollout_admins"},
                                              {"$addToSet": {"emails": email}}, upsert=True)
        return await list_rollout_admins(user)

    @api.delete("/rollout-admins/{email}")
    async def remove_rollout_admin(email: str, user: dict = Depends(get_current_user)):
        await _require_rollout_admin(user)
        await db.platform_settings.update_one({"_id": "rollout_admins"},
                                              {"$pull": {"emails": email.lower().strip()}})
        return await list_rollout_admins(user)

    # ---------- template rollout ----------
    @api.get("/templates/rollout-status")
    async def template_rollout_status(user: dict = Depends(get_current_user)):
        from site_content import LOOKS
        states = {d["key"]: d for d in await db.template_states.find({}, {"_id": 0}).to_list(100)}
        out = []
        for key in LOOKS:
            st = states.get(key) or {}
            using = await db.apps.count_documents({"site_niche": key, "archived": {"$ne": True},
                                                   "app_id": {"$ne": TEST_LAB_ID}})
            out.append({"key": key, "status": st.get("status", "live"), "tenants_using": using,
                        "updated_at": st.get("updated_at"), "last_pushed_at": st.get("last_pushed_at")})
        return {"templates": out, "pending": sum(1 for t in out if t["status"] == "pending")}

    @api.post("/templates/{key}/rollout")
    async def push_template(key: str, body: RolloutIn, user: dict = Depends(get_current_user)):
        from site_content import LOOKS, NICHES, theme_for
        await _require_rollout_admin(user)
        _check_confirm(body.confirm)
        if key not in LOOKS:
            raise HTTPException(404, "Unknown template")
        job_id = _uid("tplroll")
        look = theme_for(NICHES[key], key)
        targets = await db.apps.find({"site_niche": key, "archived": {"$ne": True},
                                      "app_id": {"$ne": TEST_LAB_ID}}, {"_id": 0}).to_list(500)
        for t in targets:
            await db.rollout_snapshots.insert_one({
                "snapshot_id": _uid("snap"), "job_id": job_id, "app_id": t["app_id"],
                "before": {"theme": t.get("theme")}, "created_at": _now()})
            await db.apps.update_one({"app_id": t["app_id"]},
                                     {"$set": {"theme": {**(t.get("theme") or {}), **look},
                                               "updated_at": _now()}})
        await db.template_states.update_one({"key": key}, {"$set": {
            "key": key, "look_hash": _look_hash(key), "status": "live", "pending_hash": None,
            "last_pushed_at": _now(), "updated_at": _now()}}, upsert=True)
        await log_activity(TEST_LAB_ID, user["user_id"], "rollout.template",
                           f"Pushed the {key} template design to {len(targets)} tenant(s)")
        return {"ok": True, "key": key, "tenants_updated": len(targets), "job_id": job_id}

    @api.post("/templates/{key}/discard")
    async def discard_template(key: str, user: dict = Depends(get_current_user)):
        from site_content import LOOKS
        await _require_rollout_admin(user)
        if key not in LOOKS:
            raise HTTPException(404, "Unknown template")
        await db.template_states.update_one({"key": key}, {"$set": {
            "key": key, "look_hash": _look_hash(key), "status": "live", "pending_hash": None,
            "discarded_at": _now(), "updated_at": _now()}}, upsert=True)
        return {"ok": True, "key": key, "status": "live"}
