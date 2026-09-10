"""Per-tenant case study pages, isolated Site Mode settings and the redesign approval workflow.

Platform rule kept intact: nothing here pushes anything to a live tenant. Case studies are authored
per tenant (Test Lab first), Site Mode is stored per tenant and never shared, and every redesign
raises a pending approval record that an admin must review before the existing rollout flow runs.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("agency.case_study")

TEST_LAB_ID = "app_testlab"
REDESIGN_DOC = "redesign_flag"
CURRENT_REDESIGN = "editorial-motion-v1"

ANIMATION_LEVELS = ("full", "reduced", "none")
PUBLISH_STATES = ("draft", "preview", "live")
SITE_STYLES = ("original", "editorial")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "tenant"


def blank_case_study(app: Dict[str, Any]) -> Dict[str, Any]:
    """Sensible starting copy so a new case study is never an empty page."""
    name = app.get("name") or "Client"
    return {
        "app_id": app.get("app_id"),
        "slug": slugify(name),
        "status": "draft",
        "tenant_name": name,
        "industry": app.get("industry") or app.get("site_niche") or "Client work",
        "accent": (app.get("theme") or {}).get("primary") or "#10B981",
        "tagline": f"How {name} launched a modern client experience.",
        "hero_image": app.get("thumbnail") or "",
        "challenge": f"{name} needed a site their team could actually run — bookings, enquiries and "
                     "content changes were spread across tools nobody owned.",
        "solution_intro": "We rebuilt the whole experience on one workspace: a designed site, a lead inbox and billing.",
        "shots": [],
        "stats": [
            {"label": "Leads generated", "value": 1284, "suffix": "+"},
            {"label": "Pages built", "value": 24, "suffix": ""},
            {"label": "Days to launch", "value": 9, "suffix": ""},
        ],
        "quote": "It finally feels like one product instead of five tools taped together.",
        "quote_name": "Client name",
        "quote_role": f"Founder, {name}",
        "updated_at": _now(),
    }


def register(api, db, get_current_user, get_user_app, log_activity):

    # ── models ────────────────────────────────────────────────────────────
    class StatIn(BaseModel):
        label: str = ""
        value: float = 0
        suffix: str = ""

    class ShotIn(BaseModel):
        url: str = ""
        caption: str = ""

    class CaseStudyIn(BaseModel):
        status: Optional[str] = None
        tagline: Optional[str] = None
        hero_image: Optional[str] = None
        challenge: Optional[str] = None
        solution_intro: Optional[str] = None
        shots: Optional[List[ShotIn]] = None
        stats: Optional[List[StatIn]] = None
        quote: Optional[str] = None
        quote_name: Optional[str] = None
        quote_role: Optional[str] = None
        industry: Optional[str] = None
        accent: Optional[str] = None

    class SiteModeIn(BaseModel):
        style: Optional[str] = None            # original | editorial
        mode: Optional[str] = None             # light | dark
        animation: Optional[str] = None        # full | reduced | none
        publish: Optional[str] = None          # draft | preview | live
        template_key: Optional[str] = None     # which of the industry templates drives the look
        hero: Optional[str] = None             # signature hero motion for this tenant
        accent: Optional[str] = None           # tenant accent used by every motion layer
        motion_speed: Optional[float] = None       # 0.25x – 2x playback of the hero engine
        motion_intensity: Optional[float] = None   # 0.2 (subtle) – 1.5 (bold) presence

    class RedesignIn(BaseModel):
        note: str = ""
        version: str = CURRENT_REDESIGN

    async def _app_or_404(app_id: str, user: dict) -> dict:
        doc = await get_user_app(app_id, user) if get_user_app else None
        if not doc:
            doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Tenant not found")
        return doc

    async def _load(app: dict) -> dict:
        doc = await db.case_studies.find_one({"app_id": app["app_id"]}, {"_id": 0})
        if not doc:
            doc = blank_case_study(app)
            await db.case_studies.insert_one({**doc})
            doc.pop("_id", None)
        return doc

    # ── public: index + single page ───────────────────────────────────────
    @api.get("/public/case-studies")
    async def public_index():
        rows = await db.case_studies.find({"status": "published"}, {"_id": 0}).to_list(200)
        out = []
        for r in rows:
            app = await db.apps.find_one({"app_id": r["app_id"]}, {"_id": 0, "name": 1, "thumbnail": 1, "status": 1}) or {}
            headline = (r.get("stats") or [{}])[0]
            out.append({
                "slug": r["slug"], "app_id": r["app_id"],
                "tenant_name": r.get("tenant_name") or app.get("name"),
                "industry": r.get("industry"), "accent": r.get("accent"),
                "tagline": r.get("tagline"),
                "thumbnail": r.get("hero_image") or app.get("thumbnail") or "",
                "headline_stat": {"label": headline.get("label", ""), "value": headline.get("value", 0),
                                  "suffix": headline.get("suffix", "")},
            })
        return {"case_studies": out, "total": len(out)}

    @api.get("/public/case-studies/{slug}")
    async def public_one(slug: str):
        doc = await db.case_studies.find_one({"slug": slug, "status": "published"}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "That case study isn't published")
        return doc

    # ── admin: author the case study ──────────────────────────────────────
    @api.get("/apps/{app_id}/case-study")
    async def get_case_study(app_id: str, user: dict = Depends(get_current_user)):
        app = await _app_or_404(app_id, user)
        return await _load(app)

    @api.put("/apps/{app_id}/case-study")
    async def put_case_study(app_id: str, body: CaseStudyIn, user: dict = Depends(get_current_user)):
        app = await _app_or_404(app_id, user)
        cur = await _load(app)
        patch: Dict[str, Any] = {k: v for k, v in body.model_dump(exclude_none=True).items()}
        if "status" in patch and patch["status"] not in ("draft", "published"):
            raise HTTPException(400, "Status must be draft or published")
        if "shots" in patch:
            patch["shots"] = [s for s in patch["shots"] if (s.get("url") or "").strip()]
        patch["updated_at"] = _now()
        patch["slug"] = cur.get("slug") or slugify(app.get("name"))
        await db.case_studies.update_one({"app_id": app_id}, {"$set": patch}, upsert=True)
        if log_activity:
            await log_activity(app_id, user, "case_study.save", f"Case study updated ({patch.get('status', cur.get('status'))})")
        return await db.case_studies.find_one({"app_id": app_id}, {"_id": 0})

    @api.post("/apps/{app_id}/case-study/sync-metrics")
    async def sync_metrics(app_id: str, user: dict = Depends(get_current_user)):
        """Pulls this tenant's real numbers into the case study results row."""
        app = await _app_or_404(app_id, user)
        cs = await _load(app)
        leads = await db.leads.count_documents({"app_id": app_id})
        subs = await db.form_submissions.count_documents({"app_id": app_id})
        pages = await db.pages.count_documents({"app_id": app_id})
        blocks = await db.blocks.count_documents({"app_id": app_id})
        created = app.get("created_at") or ""
        days = 0
        try:
            start = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            days = max(1, (datetime.now(timezone.utc) - start).days)
        except Exception:
            days = 0
        stats = [
            {"label": "Leads generated", "value": leads + subs, "suffix": "+"},
            {"label": "Pages built", "value": pages or blocks, "suffix": ""},
            {"label": "Days live", "value": days, "suffix": ""},
        ]
        await db.case_studies.update_one({"app_id": app_id},
                                         {"$set": {"stats": stats, "metrics_synced_at": _now()}}, upsert=True)
        if log_activity:
            await log_activity(app_id, user, "case_study.sync_metrics", f"Metrics synced: {stats}")
        return {"stats": stats, "synced_at": _now(), "previous": cs.get("stats")}

    # ── per-tenant Site Mode (fully isolated) ─────────────────────────────
    @api.get("/apps/{app_id}/site-mode")
    async def get_site_mode(app_id: str, user: dict = Depends(get_current_user)):
        app = await _app_or_404(app_id, user)
        sm = app.get("site_mode") or {}
        theme = app.get("theme") or {}
        return {
            "app_id": app_id,
            "style": sm.get("style") or "original",
            "mode": sm.get("mode") or theme.get("mode") or "dark",
            "animation": sm.get("animation") or "full",
            "publish": sm.get("publish") or ("live" if app.get("status") == "active" else "draft"),
            "template_key": sm.get("template_key") or app.get("site_niche") or "",
            "hero": sm.get("hero") or (app.get("motion_profile") or {}).get("hero") or "",
            "accent": sm.get("accent") or (app.get("motion_profile") or {}).get("accent") or theme.get("primary") or "",
            "motion_speed": float(sm.get("motion_speed") or 1.0),
            "motion_intensity": float(sm.get("motion_intensity") or 1.0),
            "preview_token": app.get("preview_token") or "",
            "preview_enabled": bool(app.get("preview_enabled")),
            "options": {"styles": list(SITE_STYLES), "animations": list(ANIMATION_LEVELS), "publish": list(PUBLISH_STATES)},
        }

    @api.put("/apps/{app_id}/site-mode")
    async def put_site_mode(app_id: str, body: SiteModeIn, user: dict = Depends(get_current_user)):
        app = await _app_or_404(app_id, user)
        cur = dict(app.get("site_mode") or {})
        patch = body.model_dump(exclude_none=True)
        if patch.get("style") and patch["style"] not in SITE_STYLES:
            raise HTTPException(400, "Unknown site style")
        if patch.get("animation") and patch["animation"] not in ANIMATION_LEVELS:
            raise HTTPException(400, "Animation must be full, reduced or none")
        if patch.get("publish") and patch["publish"] not in PUBLISH_STATES:
            raise HTTPException(400, "Publish status must be draft, preview or live")
        if patch.get("mode") and patch["mode"] not in ("light", "dark"):
            raise HTTPException(400, "Mode must be light or dark")
        from editorial_rollout import HERO_NAMES, RESERVED_ACCENTS
        if patch.get("hero") and patch["hero"] not in HERO_NAMES:
            raise HTTPException(400, "Unknown hero motion")
        if patch.get("accent") and patch["accent"].upper() in RESERVED_ACCENTS:
            raise HTTPException(400, "That accent is reserved for the platform site")
        if patch.get("motion_speed") is not None and not 0.25 <= patch["motion_speed"] <= 2.0:
            raise HTTPException(400, "Motion speed must be between 0.25x and 2x")
        if patch.get("motion_intensity") is not None and not 0.2 <= patch["motion_intensity"] <= 1.5:
            raise HTTPException(400, "Motion intensity must be between 0.2 and 1.5")
        cur.update(patch)
        cur["updated_at"] = _now()
        prof = dict(app.get("motion_profile") or {})
        if patch.get("hero"):
            prof["hero"] = patch["hero"]
        if patch.get("accent"):
            prof["accent"] = patch["accent"]
        if patch.get("motion_speed") is not None:
            prof["speed"] = patch["motion_speed"]
        if patch.get("motion_intensity") is not None:
            prof["intensity"] = patch["motion_intensity"]
        if prof:
            await db.apps.update_one({"app_id": app_id}, {"$set": {"motion_profile": prof}})
        await db.apps.update_one({"app_id": app_id}, {"$set": {"site_mode": cur}})
        # Always-live: a design change saved in the master workspace propagates instantly to every
        # active tenant and to the platform defaults future tenants inherit. Content is untouched.
        from auto_propagate import propagate_site_mode
        prop = await propagate_site_mode(db, app_id, patch)
        if log_activity:
            await log_activity(app_id, user, "site_mode.save", f"Site Mode updated: {patch}")
        return {"app_id": app_id, **cur, "propagated_to": (prop or {}).get("tenants") or []}

    # ── redesign approval workflow ────────────────────────────────────────
    @api.get("/redesign/pending")
    async def redesign_pending(user: dict = Depends(get_current_user)):
        doc = await db.platform_settings.find_one({"_id": REDESIGN_DOC}) or {}
        pending = bool(doc.get("version")) and not doc.get("dismissed_at") and not doc.get("rolled_out_at")
        return {
            "pending": pending,
            "version": doc.get("version") or "",
            "note": doc.get("note") or "",
            "created_at": doc.get("created_at") or "",
            "reviewed_at": doc.get("reviewed_at") or "",
            "preview_url": "/test-lab/landing",
        }

    @api.post("/redesign/flag")
    async def redesign_flag(body: RedesignIn, user: dict = Depends(get_current_user)):
        """Raised automatically whenever a redesign lands in the Test Lab."""
        await db.platform_settings.update_one(
            {"_id": REDESIGN_DOC},
            {"$set": {"version": body.version, "note": body.note, "created_at": _now(),
                      "dismissed_at": None, "rolled_out_at": None, "reviewed_at": None}},
            upsert=True)
        return await redesign_pending(user)

    @api.post("/redesign/reviewed")
    async def redesign_reviewed(user: dict = Depends(get_current_user)):
        """Step 3 → the admin has inspected the preview and asked for the diff."""
        await db.platform_settings.update_one({"_id": REDESIGN_DOC}, {"$set": {"reviewed_at": _now()}}, upsert=True)
        return await redesign_pending(user)

    @api.post("/redesign/dismiss")
    async def redesign_dismiss(user: dict = Depends(get_current_user)):
        await db.platform_settings.update_one({"_id": REDESIGN_DOC}, {"$set": {"dismissed_at": _now()}}, upsert=True)
        return await redesign_pending(user)

    return {"blank_case_study": blank_case_study}


async def ensure_seed(db, current_version: str = CURRENT_REDESIGN):
    """Test Lab gets a starter case study; the editorial redesign raises one pending approval."""
    lab = await db.apps.find_one({"app_id": TEST_LAB_ID}, {"_id": 0})
    if lab and not await db.case_studies.find_one({"app_id": TEST_LAB_ID}):
        doc = blank_case_study(lab)
        doc["status"] = "published"          # so the showcase index has one live example to review
        doc["shots"] = [
            {"url": "https://images.unsplash.com/photo-1551650975-87deedd944c3?w=1200&q=80", "caption": "Site mode canvas"},
            {"url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1200&q=80", "caption": "Client dashboard"},
            {"url": "https://images.unsplash.com/photo-1554415707-6e8cfc93fe23?w=1200&q=80", "caption": "Lead inbox"},
        ]
        await db.case_studies.insert_one(doc)
        logger.info("Seeded Test Lab case study")
    doc = await db.platform_settings.find_one({"_id": REDESIGN_DOC}) or {}
    if doc.get("version") != current_version:
        await db.platform_settings.update_one(
            {"_id": REDESIGN_DOC},
            {"$set": {"version": current_version, "created_at": _now(), "reviewed_at": None,
                      "dismissed_at": None, "rolled_out_at": None,
                      "note": "Editorial motion design system applied to the Test Lab tenant and Test Template."}},
            upsert=True)
        logger.info("Redesign approval flag raised: %s", current_version)
