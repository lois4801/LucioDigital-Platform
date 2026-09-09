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

# Diff rows: (change_id, category, human label, source, field)
#   source "theme" = tenant.theme[field] · "app" = tenant[field]
DIFF_FIELDS = [
    ("design.mode", "Design", "Light / dark mode", "theme", "mode"),
    ("design.primary", "Design", "Primary colour", "theme", "primary"),
    ("design.secondary", "Design", "Secondary colour", "theme", "secondary"),
    ("design.bg", "Design", "Background colour", "theme", "bg"),
    ("design.surface", "Design", "Surface colour", "theme", "surface"),
    ("design.border", "Design", "Border colour", "theme", "border"),
    ("design.fg", "Design", "Text colour", "theme", "fg"),
    ("design.muted", "Design", "Muted text colour", "theme", "muted"),
    ("design.font_heading", "Design", "Heading font", "theme", "font_heading"),
    ("design.font_body", "Design", "Body font", "theme", "font_body"),
    ("design.radius", "Design", "Corner radius", "theme", "radius"),
    ("design.preset", "Design", "Section style preset", "theme", "preset"),
    ("design.hero", "Design", "Hero layout", "theme", "hero"),
    ("animations.motion", "Animations", "Scroll & reveal animations", "theme", "motion"),
    ("animations.cursor", "Animations", "Custom cursor trail", "theme", "cursor"),
    ("animations.glass", "Animations", "Glass-morphism surfaces", "theme", "glass"),
    ("animations.grain", "Animations", "Grain / noise overlay", "theme", "grain"),
    ("animations.cursor_effect", "Animations", "Cursor effect", "app", "cursor_effect"),
    ("animations.cursor_density", "Animations", "Cursor density", "app", "cursor_density"),
    ("animations.cursor_speed", "Animations", "Cursor speed", "app", "cursor_speed"),
    ("features.site_skin", "Features", "Site skin (Classic / Studio 2026)", "theme", "site_skin"),
    ("features.studio", "Features", "Studio 2026 component set", "theme", "studio"),
    ("features.design_v2", "Features", "Design system v2 renderer", "theme", "design_v2"),
    ("features.premium_v", "Features", "Premium site version", "theme", "premium_v"),
    ("features.look_v", "Features", "Template look version", "theme", "look_v"),
    ("features.ui_skin", "Features", "Dashboard skin", "app", "ui_skin"),
]
# Which rollout scope each category belongs to (kept so old scope-based calls still work).
CATEGORY_SCOPE = {"Design": "theme", "Animations": "motion", "Features": "skin",
                  "Content": "labels", "Forms": "forms"}


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


STAGING_NAME = "Rollout Target Demo"


async def ensure_staging_tenant(db, owner_id: str) -> dict:
    """The permanent staging tenant: a real environment the admin can push to before going live.
    Never modified automatically — only by an explicit Push to Staging."""
    doc = await db.apps.find_one({"is_staging": True}, {"_id": 0})
    if not doc:
        doc = await db.apps.find_one({"name": STAGING_NAME}, {"_id": 0})
    if doc:
        await db.apps.update_one({"app_id": doc["app_id"]},
                                 {"$set": {"is_staging": True, "protected": True, "archived": False}})
        return await db.apps.find_one({"app_id": doc["app_id"]}, {"_id": 0})
    from site_content import LOOKS, NICHES, theme_for
    key = "hvac" if "hvac" in LOOKS else next(iter(LOOKS))
    doc = {
        "app_id": _uid("app"), "owner_id": owner_id, "name": STAGING_NAME,
        "industry": NICHES[key]["industry"], "kind": "website",
        "description": "Staging tenant — the final real-environment check before pushing to live tenants.",
        "status": "active", "tags": ["staging"], "color": "#F97316",
        "is_staging": True, "protected": True, "archived": False,
        "theme": theme_for(NICHES[key], key), "site_niche": key, "premium_site_v": 3,
        "metrics": {"uptime": 100.0, "cpu": 10, "ram": 24, "response_ms": 110, "visitors_24h": 0},
        "created_at": _now(), "updated_at": _now(),
    }
    await db.apps.insert_one(dict(doc))
    doc.pop("_id", None)
    logger.info("Staging tenant ready: %s", doc["app_id"])
    return doc


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


def _common(values: list):
    """Most common live value + whether tenants disagree."""
    from collections import Counter
    keyed = [json.dumps(v, sort_keys=True, default=str) for v in values]
    if not keyed:
        return None, False
    top, _n = Counter(keyed).most_common(1)[0]
    return json.loads(top), len(set(keyed)) > 1


async def build_diff(db, targets: list, lab: dict) -> dict:
    """Aggregate diff between the Test Lab and every live tenant. Only real differences appear."""
    lab_theme = lab.get("theme") or {}
    rows = []
    for cid, cat, label, source, field in DIFF_FIELDS:
        new = lab_theme.get(field) if source == "theme" else lab.get(field)
        lives = [(t.get("theme") or {}).get(field) if source == "theme" else t.get(field) for t in targets]
        differing = [v for v in lives if v != new]
        if not targets or not differing:
            continue
        old, variance = _common(differing)
        rows.append({"id": cid, "category": cat, "label": label, "old": old, "new": new,
                     "kind": "added" if old in (None, "") else ("removed" if new in (None, "") else "changed"),
                     "tenants": len(differing), "variance": variance})

    lab_labels = ((await db.ui_labels.find_one({"app_id": TEST_LAB_ID}, {"_id": 0})) or {}).get("labels") or {}
    live_labels = {}
    for t in targets:
        doc = await db.ui_labels.find_one({"app_id": t["app_id"]}, {"_id": 0}) or {}
        for k, v in (doc.get("labels") or {}).items():
            live_labels.setdefault(k, []).append(v)
    for k, new in lab_labels.items():
        lives = live_labels.get(k) or []
        differing = [v for v in lives if v != new] or ([None] if not lives else [])
        if not targets or not differing:
            continue
        old, variance = _common(differing)
        rows.append({"id": f"content.labels.{k}", "category": "Content", "label": f"Label “{k}”",
                     "old": old, "new": new, "kind": "added" if old is None else "changed",
                     "tenants": len(differing), "variance": variance})
    for k in live_labels:
        if k not in lab_labels:
            old, _v = _common(live_labels[k])
            rows.append({"id": f"content.labels.{k}", "category": "Content",
                         "label": f"Label “{k}” removed", "old": old, "new": None, "kind": "removed",
                         "tenants": len(live_labels[k]), "variance": False})

    lab_forms = await db.cta_forms.find({"app_id": TEST_LAB_ID}, {"_id": 0}).to_list(100)
    for f in lab_forms:
        key = f.get("key")
        new = {"fields": [x.get("label") for x in (f.get("fields") or [])],
               "success_message": f.get("success_message")}
        lives = []
        for t in targets:
            doc = await db.cta_forms.find_one({"app_id": t["app_id"], "key": key}, {"_id": 0})
            if doc:
                lives.append({"fields": [x.get("label") for x in (doc.get("fields") or [])],
                              "success_message": doc.get("success_message")})
        differing = [v for v in lives if v != new]
        if not differing:
            continue
        old, variance = _common(differing)
        rows.append({"id": f"forms.{key}", "category": "Forms", "label": f"CTA form “{f.get('title') or key}”",
                     "old": old, "new": new, "kind": "changed", "tenants": len(differing), "variance": variance})

    by_cat: dict = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    return {"changes": rows, "by_category": by_cat, "total": len(rows),
            "target_count": len(targets),
            "targets": [{"app_id": t["app_id"], "name": t.get("name")} for t in targets],
            "generated_at": _now()}


def register(api, db, get_current_user, get_user_app, log_activity):

    class RolloutIn(BaseModel):
        scopes: List[str] = []
        changes: Optional[List[str]] = None
        target_app_ids: Optional[List[str]] = None
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

    async def _targets(only: Optional[List[str]] = None) -> List[dict]:
        # "All tenants" means live client tenants: the Test Lab and the staging tenant are only
        # ever reached through an explicit Push to Staging / Test Lab edit.
        q = {"app_id": {"$ne": TEST_LAB_ID}, "archived": {"$ne": True}, "is_staging": {"$ne": True}}
        if only:
            q = {"app_id": {"$in": [a for a in only if a != TEST_LAB_ID]}, "archived": {"$ne": True}}
        return await db.apps.find(q,
                                  {"_id": 0, "app_id": 1, "name": 1, "theme": 1, "site_niche": 1,
                                   "ui_skin": 1, "cursor_effect": 1, "cursor_density": 1,
                                   "cursor_speed": 1}).to_list(500)

    @api.get("/staging-tenant")
    async def staging_tenant(user: dict = Depends(get_current_user)):
        doc = await db.apps.find_one({"is_staging": True}, {"_id": 0, "app_id": 1, "name": 1, "theme": 1})
        if not doc:
            raise HTTPException(404, "No staging tenant configured — restart the backend to create it")
        return doc

    @api.post("/test-lab/run-test")
    async def run_test(user: dict = Depends(get_current_user)):
        """Admin-triggered smoke check. Nothing here runs automatically."""
        await _require_rollout_admin(user)
        lab = await _test_lab()
        pages = await db.pages.count_documents({"app_id": TEST_LAB_ID})
        blocks = sum(len(p.get("blocks") or []) for p in
                     await db.pages.find({"app_id": TEST_LAB_ID}, {"_id": 0, "blocks": 1}).to_list(200))
        targets = await _targets()
        diff = await build_diff(db, targets, lab)
        staging = await db.apps.find_one({"is_staging": True}, {"_id": 0, "app_id": 1, "name": 1})
        checks = [
            {"name": "Test Lab tenant", "ok": bool(lab), "detail": lab.get("name")},
            {"name": "Template pages loaded", "ok": pages > 0, "detail": f"{pages} page(s), {blocks} block(s)"},
            {"name": "Staging tenant", "ok": bool(staging), "detail": (staging or {}).get("name", "missing")},
            {"name": "Live tenants reachable", "ok": True, "detail": f"{len(targets)} live tenant(s)"},
            {"name": "Unpushed Test Lab changes", "ok": True, "detail": f"{diff['total']} change(s) waiting"},
            {"name": "Forms configured", "ok": True,
             "detail": f"{await db.cta_forms.count_documents({'app_id': TEST_LAB_ID})} CTA form(s)"},
        ]
        result = {"ran_at": _now(), "by": user.get("email"), "scope": "test_lab_only",
                  "passed": sum(1 for c in checks if c["ok"]), "total": len(checks), "checks": checks,
                  "preview_url": f"/apps/{TEST_LAB_ID}"}
        await db.apps.update_one({"app_id": TEST_LAB_ID}, {"$set": {"last_test": result}})
        await log_activity(TEST_LAB_ID, user["user_id"], "test.run",
                           f"Ran the Test Lab smoke test — {result['passed']}/{result['total']} checks passed")
        return result

    def _patch_for(scopes: List[str], lab: dict, target: dict, changes: Optional[List[str]] = None) -> dict:
        """The $set patch a single tenant receives. `changes` (from the Diff Viewer) wins when given."""
        lab_theme = lab.get("theme") or {}
        theme = dict(target.get("theme") or {})
        upd: dict = {}
        if changes is not None:
            picked = set(changes)
            for cid, _cat, _label, source, field in DIFF_FIELDS:
                if cid not in picked:
                    continue
                if source == "theme":
                    if field in lab_theme:
                        theme[field] = lab_theme[field]
                elif field in lab:
                    upd[field] = lab[field]
            if theme != (target.get("theme") or {}):
                upd["theme"] = theme
            return upd
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

    async def _snapshot(job_id: str, app_id: str):
        """Full pre-rollout snapshot: design, animations, features, labels and form structures."""
        full = await db.apps.find_one({"app_id": app_id}, {"_id": 0}) or {}
        labels = await db.ui_labels.find_one({"app_id": app_id}, {"_id": 0})
        forms = await db.cta_forms.find({"app_id": app_id}, {"_id": 0}).to_list(100)
        await db.rollout_snapshots.insert_one({
            "snapshot_id": _uid("snap"), "job_id": job_id, "app_id": app_id, "created_at": _now(),
            "before": {"theme": full.get("theme"), "ui_skin": full.get("ui_skin"),
                       **{k: full.get(k) for k in APP_MOTION_KEYS}},
            "labels": (labels or {}).get("labels"),
            "forms": [{"key": f.get("key"), "fields": f.get("fields"),
                       "success_message": f.get("success_message")} for f in forms],
        })

    async def _run_rollout(job_id: str, scopes: List[str], user: dict, changes: Optional[List[str]] = None,
                           only: Optional[List[str]] = None):
        lab = await _test_lab()
        targets = await _targets(only)
        picked = set(changes or [])
        want_labels = ("labels" in scopes) if changes is None else any(c.startswith("content.labels.") for c in picked)
        want_forms = ("forms" in scopes) if changes is None else any(c.startswith("forms.") for c in picked)
        labels_doc = await db.ui_labels.find_one({"app_id": TEST_LAB_ID}, {"_id": 0}) if want_labels else None
        lab_forms = await db.cta_forms.find({"app_id": TEST_LAB_ID}, {"_id": 0}).to_list(100) if want_forms else []
        if changes is not None and want_forms:
            lab_forms = [f for f in lab_forms if f"forms.{f.get('key')}" in picked]
        done = 0
        changed = 0
        failed = 0
        for t in targets:
            try:
                full = await db.apps.find_one({"app_id": t["app_id"]}, {"_id": 0})
                await _snapshot(job_id, t["app_id"])
                upd = _patch_for(scopes, lab, full, changes)
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
                failed += 1
            done += 1
            await db.rollout_jobs.update_one({"job_id": job_id}, {"$set": {
                "done": done, "changed": changed, "failed": failed,
                "pct": int(done / max(1, len(targets)) * 100)}})
            await asyncio.sleep(0)
        status = "failed" if failed and not changed else ("partial" if failed else "done")
        await db.rollout_jobs.update_one({"job_id": job_id}, {"$set": {
            "status": status, "pct": 100, "finished_at": _now(),
            "detail": f"Applied to {changed} of {len(targets)} tenant(s)"
                      + (f" · {failed} failed" if failed else "")}})
        await log_activity(TEST_LAB_ID, user["user_id"], "rollout.all",
                           f"Pushed {len(picked) or len(scopes)} change(s) from the Test Lab to {changed} tenant(s)")

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
        changes = body.changes
        only = body.target_app_ids or None
        if changes is not None:
            valid = {c["id"] for c in (await build_diff(db, await _targets(only), await _test_lab()))["changes"]}
            changes = [c for c in changes if c in valid]
            if not changes:
                raise HTTPException(400, "Select at least one change to push")
            scopes = sorted({CATEGORY_SCOPE.get(c.split(".")[0].capitalize(), "theme") for c in changes})
        elif not scopes:
            raise HTTPException(400, "Choose at least one thing to push")
        lab = await _test_lab()
        targets = await _targets(only)
        diff = await build_diff(db, targets, lab)
        if changes is not None:
            diff = {**diff, "changes": [c for c in diff["changes"] if c["id"] in set(changes)]}
            diff["by_category"] = {}
            for r in diff["changes"]:
                diff["by_category"].setdefault(r["category"], []).append(r)
            diff["total"] = len(diff["changes"])
        job = {"job_id": _uid("roll"), "scopes": scopes, "changes": changes,
               "kind": "single" if only else "global", "target_app_ids": only,
               "status": "running", "pct": 0, "done": 0, "changed": 0, "failed": 0,
               "total": len(targets), "by": user["user_id"], "by_email": user.get("email"),
               "by_name": user.get("name"), "diff": diff,
               "categories": sorted(diff["by_category"].keys()),
               "detail": "Starting rollout", "created_at": _now()}
        await db.rollout_jobs.insert_one(dict(job))
        asyncio.create_task(_run_rollout(job["job_id"], scopes, user, changes, only))
        job.pop("_id", None)
        return job

    @api.get("/test-lab/diff")
    async def test_lab_diff(app_id: Optional[str] = None, user: dict = Depends(get_current_user)):
        lab = await _test_lab()
        return await build_diff(db, await _targets([app_id] if app_id else None), lab)

    @api.get("/test-lab/pending")
    async def pending_map(user: dict = Depends(get_current_user)):
        """Per-tenant count of unpushed Test Lab changes — drives the orange "Pending Update" badge."""
        lab = await db.apps.find_one({"app_id": TEST_LAB_ID}, {"_id": 0})
        if not lab:
            return {"tenants": {}}
        out = {}
        for t in await _targets():
            d = await build_diff(db, [t], lab)
            if d["total"]:
                out[t["app_id"]] = d["total"]
        return {"tenants": out, "total": sum(out.values())}

    @api.get("/test-lab/rollout/history")
    async def rollout_history(user: dict = Depends(get_current_user)):
        jobs = await db.rollout_jobs.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
        undoable = next((j["job_id"] for j in jobs
                         if j.get("status") in ("done", "partial") and not j.get("undone_at")), None)
        admins = await _rollout_admins()
        return {"entries": [{**j, "can_undo": j["job_id"] == undoable} for j in jobs],
                "is_rollout_admin": (user.get("email") or "").lower().strip() in admins}

    async def _run_undo(job_id: str, user: dict):
        snaps = await db.rollout_snapshots.find({"job_id": job_id}, {"_id": 0}).to_list(1000)
        done = 0
        for s in snaps:
            try:
                if s.get("template_key"):
                    from site_content import LOOKS, NICHES
                    key, before = s["template_key"], s.get("before_look") or {}
                    if key in LOOKS:
                        LOOKS[key].update(before)
                        if "primary" in before:
                            NICHES[key]["primary"] = before["primary"]
                        if "secondary" in before:
                            NICHES[key]["secondary"] = before["secondary"]
                        await db.template_looks.update_one(
                            {"key": key}, {"$set": {"key": key, "look": LOOKS[key], "updated_at": _now()}},
                            upsert=True)
                    done += 1
                    await db.rollout_jobs.update_one({"job_id": job_id}, {"$set": {
                        "undo_done": done, "undo_pct": int(done / max(1, len(snaps)) * 100)}})
                    continue
                before = s.get("before") or {}
                setter = {k: v for k, v in before.items() if v is not None}
                unset = {k: "" for k, v in before.items() if v is None}
                ops = {}
                if setter:
                    ops["$set"] = {**setter, "updated_at": _now()}
                if unset:
                    ops["$unset"] = unset
                if ops:
                    await db.apps.update_one({"app_id": s["app_id"]}, ops)
                if s.get("labels") is not None:
                    await db.ui_labels.update_one({"app_id": s["app_id"]},
                                                  {"$set": {"labels": s["labels"], "updated_at": _now()}},
                                                  upsert=True)
                for f in s.get("forms") or []:
                    await db.cta_forms.update_one(
                        {"app_id": s["app_id"], "key": f.get("key")},
                        {"$set": {"fields": f.get("fields") or [],
                                  "success_message": f.get("success_message"), "updated_at": _now()}})
            except Exception:
                logger.exception("undo failed for %s", s.get("app_id"))
            done += 1
            await db.rollout_jobs.update_one({"job_id": job_id}, {"$set": {
                "undo_done": done, "undo_pct": int(done / max(1, len(snaps)) * 100)}})
            await asyncio.sleep(0)
        await db.rollout_jobs.update_one({"job_id": job_id}, {"$set": {
            "undone_at": _now(), "undone_by": user.get("email"), "undo_pct": 100,
            "undo_total": len(snaps), "status_before_undo": "done", "status": "undone"}})
        await log_activity(TEST_LAB_ID, user["user_id"], "rollout.undo",
                           f"Undid rollout {job_id} — restored {len(snaps)} tenant(s)")

    @api.post("/test-lab/rollout/jobs/{job_id}/undo")
    async def undo_rollout(job_id: str, body: RolloutIn, user: dict = Depends(get_current_user)):
        await _require_rollout_admin(user)
        _check_confirm(body.confirm)
        jobs = await db.rollout_jobs.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
        undoable = next((j for j in jobs
                         if j.get("status") in ("done", "partial") and not j.get("undone_at")), None)
        if not undoable or undoable["job_id"] != job_id:
            raise HTTPException(400, "Only the most recent completed rollout can be undone")
        snaps = await db.rollout_snapshots.count_documents({"job_id": job_id})
        await db.rollout_jobs.update_one({"job_id": job_id},
                                         {"$set": {"undo_pct": 0, "undo_total": snaps, "undo_done": 0}})
        asyncio.create_task(_run_undo(job_id, user))
        return {"ok": True, "job_id": job_id, "tenants": snaps}

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
        diff_rows = [{"id": f"design.{k}", "category": "Design", "label": f"Template token “{k}”",
                      "old": None, "new": v, "kind": "changed", "tenants": len(targets), "variance": False}
                     for k, v in look.items()]
        await db.rollout_jobs.insert_one({
            "job_id": job_id, "kind": "template", "template_key": key, "scopes": ["theme"],
            "status": "running", "pct": 0, "done": 0, "changed": 0, "failed": 0, "total": len(targets),
            "by": user["user_id"], "by_email": user.get("email"), "by_name": user.get("name"),
            "categories": ["Design"], "diff": {"changes": diff_rows, "by_category": {"Design": diff_rows},
                                               "total": len(diff_rows), "target_count": len(targets),
                                               "targets": [{"app_id": t["app_id"], "name": t.get("name")} for t in targets]},
            "detail": f"Pushing the {key} template design", "created_at": _now()})
        for t in targets:
            await _snapshot(job_id, t["app_id"])
            await db.apps.update_one({"app_id": t["app_id"]},
                                     {"$set": {"theme": {**(t.get("theme") or {}), **look},
                                               "updated_at": _now()}})
        await db.rollout_jobs.update_one({"job_id": job_id}, {"$set": {
            "status": "done", "pct": 100, "done": len(targets), "changed": len(targets),
            "finished_at": _now(), "detail": f"Applied to {len(targets)} tenant(s) using {key}"}})
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
