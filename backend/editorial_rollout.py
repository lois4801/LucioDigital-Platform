"""Editorial motion rollout: 42 unique template motion profiles + platform-wide defaults.

Flow enforced here:
  1. sandbox pre-check (only LucioDigital Test Lab may exist)
  2. full snapshot of every client + template into rollout_snapshots under one job_id
     (so the existing "Undo Last Rollout" restores everything)
  3. push the editorial system to every active client, and to every industry template
  4. store platform Site Mode defaults so FUTURE clients inherit everything automatically

Colour rule: each client/template keeps its OWN accent. Lime (#B6FF3B) is reserved for
luciodigital.ca and is never written to a client or template.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("agency.editorial_rollout")

LIME = "#84FF00"                 # platform-only accent (luciodigital.ca)
RESERVED_ACCENTS = {"#84FF00", "#B6FF3B"}   # never applied to a client or template
TEST_LAB_ID = "app_testlab"
DEFAULTS_DOC = "site_mode_defaults"

# ── 42 signature motion profiles. hero / layout / reveal / counter are unique per template. ──
# accent = that template's own path-line colour (never lime).
P = lambda hero, layout, reveal, counter, accent: {           # noqa: E731
    "hero": hero, "layout": layout, "reveal": reveal, "counter": counter, "accent": accent}

MOTION_PROFILES: Dict[str, Dict[str, str]] = {
    # ── the 16 core industry templates ──
    "real_estate":    P("curved-ribbon-scroll", "asymmetric-bento", "horizontal-wipe-left", "gold-rollup", "#F59E0B"),
    "education":      P("orbital-constellation", "masonry", "radial-bloom", "stagger-up", "#3B82F6"),
    "healthcare":     P("calm-pulse-wave", "two-column-split", "vertical-fade-up", "slow-smooth", "#14B8A6"),
    "fitness":        P("kinetic-energy-burst", "stacked-oversized", "hard-snap-up", "slam-bounce", "#F97316"),
    "legal":          P("precision-grid-reveal", "numbered-steps", "scan-line", "fixed-steps", "#E5E7EB"),
    "hospitality":    P("slow-luxury-parallax", "three-col-bleed", "cross-dissolve", "luxury-ease-2s", "#D4AF37"),
    "construction":   P("blueprint-draft-on", "timeline-row", "stroke-draw-border", "measure-draw", "#FACC15"),
    "saas":           P("particle-network", "tabbed-panel", "node-expand", "digital-ticker", "#22D3EE"),
    "creative_studio": P("scattered-gravity-drop", "overlap-stack-drag", "gravity-drop", "tumble-in", "#A855F7"),
    "events":         P("spotlight-sweep", "spotlight-card", "spotlight-wipe", "scoreboard-flash", "#FFFFFF"),
    "finance":        P("data-dashboard-morph", "asymmetric-bento-metrics", "clip-wipe-lr", "trading-ticker", "#22C55E"),
    "retail":         P("product-orbit-carousel", "filmstrip", "filmstrip-slide", "slot-machine", "#EC4899"),
    "restaurant":     P("steam-aroma-drift", "floating-food-cluster", "soft-upward-drift", "steam-rise", "#F59E0B"),
    "logistics":      P("route-path-animation", "horizontal-strip-routes", "path-trace", "travel-along-line", "#3B82F6"),
    "it_services":    P("circuit-trace-draw", "tabbed-circuit", "circuit-trace-border", "packet-pulse", "#38BDF8"),
    "hvac":           P("thermal-current-drift", "three-col-thermal", "warm-air-rise", "thermostat-dial", "#0EA5E9"),
    # ── the Studio 2026 pack ──
    "veterinary":     P("paw-print-trail", "three-col-rounded", "paw-trail-diagonal", "pad-in-digits", "#FDBA74"),
    "dental":         P("precision-slide-in", "two-column-clean", "slide-left-overshoot-8", "precise-steps", "#F8FAFC"),
    "accounting":     P("ledger-line-reveal", "stacked-ruled-rows", "ruled-line-draw", "adding-machine", "#94A3B8"),
    "landscaping":    P("organic-leaf-unfurl", "organic-masonry-borders", "corner-unfurl", "grow-upward", "#4ADE80"),
    "photography":    P("shutter-aperture-open", "filmstrip-bleed", "iris-wipe", "aperture-click", "#475569"),
    "automotive":     P("gear-shift-acceleration", "horizontal-strip-speed", "gear-accelerate", "accelerate-brake", "#DC2626"),
    "beauty":         P("float-and-bloom", "floating-bloom-cluster", "bloom-outward", "petal-rise", "#F9A8D4"),
    "insurance":      P("shield-assemble", "spotlight-trust-tiles", "assemble-pieces", "build-piecewise", "#1D4ED8"),
    "pet_grooming":   P("playful-bounce-trail", "overlap-playful-stack", "elastic-bounce-3", "elastic-bounce", "#FB923C"),
    "hvac_plumbing":  P("pipe-flow-trace", "timeline-pipes", "pipe-trace", "flow-along-path", "#0284C7"),
    "coworking":      P("desk-network-pulse", "asymmetric-bento-community", "node-pulse", "pulse-outward", "#D6D3D1"),
    "wellness":       P("breathing-canvas", "organic-masonry", "organic-bloom", "breathe-slow", "#86EFAC"),
    "cleaning":       P("sweep-and-reveal", "stacked-before-after", "brush-sweep", "sweep-from-left", "#F1F5F9"),
    "music_school":   P("sound-wave-rhythm", "filmstrip-waveform", "waveform-spike", "oscillate-settle", "#818CF8"),
    "nonprofit":      P("community-ripple", "three-col-community", "ripple-outward", "expand-from-centre", "#FCD34D"),
    "architecture":   P("structural-line-reveal", "diagonal-render-split", "wireframe-trace", "build-upward", "#7DD3FC"),
    # ── permanent sandbox template ──
    "test_template":  P("modular-grid-build", "modular-grid", "broken-to-assembled", "assemble-digits", "#A3A3A3"),
}

# Reserved profiles: applied automatically if a template with one of these keys is ever added.
RESERVED_PROFILES: Dict[str, Dict[str, str]] = {
    "tech_code":      P("matrix-code-rain", "three-col-code", "central-node-expand", "binary-countup", "#2563EB"),
    "medical":        P("dna-helix-rotation", "two-column-clinical", "fade-up-no-lateral", "linear-steps", "#5EEAD4"),
    "sports":         P("stadium-wave-ripple", "stacked-athlete-rows", "stadium-wave", "crowd-slam", "#F43F5E"),
    "fashion":        P("editorial-magazine-flip", "overlap-editorial-stack", "runway-slide-up", "luxury-rollup", "#FB7185"),
    "internal_tools": P("command-line-type-on", "numbered-terminal", "type-on", "terminal-type", "#4ADE80"),
    "saas_portals":   P("metric-counter-cascade", "asymmetric-bento-cards", "card-flip-cascade", "flip-3d", "#6366F1"),
    "art_culture":    P("museum-spotlight-pan", "gallery-masonry", "spotlight-unveil", "placard-fade", "#FDE68A"),
    "mental_health":  P("aurora-wave", "soft-masonry", "slow-cross-dissolve", "breathe-3s", "#C4B5FD"),
    "food_beverage":  P("ingredient-scatter", "floating-cluster", "toss-and-land", "bounce-place", "#EF4444"),
    "property_mgmt":  P("architectural-fly-through", "diagonal-split", "depth-push-in", "depth-stagger", "#64748B"),
}

PLATFORM_PROFILE = {   # luciodigital.ca only — shares nothing with the 42 templates
    "hero": "platform-drift-cards", "layout": "platform-bento",
    "reveal": "platform-fade-rise", "counter": "platform-odometer", "accent": LIME,
}

HERO_NAMES = sorted({v["hero"] for v in list(MOTION_PROFILES.values()) + list(RESERVED_PROFILES.values())}
                    | {PLATFORM_PROFILE["hero"]})

DEFAULT_SITE_MODE = {"style": "editorial", "mode": "dark", "animation": "full"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(p: str) -> str:
    return f"{p}_{uuid.uuid4().hex[:12]}"


def profile_for(template_key: Optional[str], accent: Optional[str] = None) -> Dict[str, Any]:
    """Resolves a client's motion profile from its template, keeping the client's own accent."""
    prof = dict(MOTION_PROFILES.get((template_key or "").lower()) or RESERVED_PROFILES.get((template_key or "").lower()) or MOTION_PROFILES["test_template"])
    if accent and accent.upper() != LIME:
        prof["accent"] = accent
    prof["template_key"] = template_key or "test_template"
    prof["glow_opacity"] = 0.4
    prof["version"] = "editorial-motion-v1"
    return prof


def register(api, db, get_current_user):

    async def _snapshot(job_id: str) -> int:
        """Step 0 — snapshot every client and every template under one undoable job."""
        from site_content import LOOKS
        n = 0
        async for app in db.apps.find({}, {"_id": 0}):
            await db.rollout_snapshots.insert_one({
                "snapshot_id": _uid("snap"), "job_id": job_id, "app_id": app["app_id"],
                "created_at": _now(),
                "before": {"theme": app.get("theme"), "ui_skin": app.get("ui_skin"),
                           "site_mode": app.get("site_mode"), "motion_profile": app.get("motion_profile")},
            })
            n += 1
        for key, look in LOOKS.items():
            await db.rollout_snapshots.insert_one({
                "snapshot_id": _uid("snap"), "job_id": job_id, "template_key": key,
                "created_at": _now(), "before_look": dict(look),
            })
            n += 1
        return n

    async def _run(job_id: str, user: dict):
        from sandbox_guard import purge_other_sandboxes
        from site_content import LOOKS, NICHES

        async def step(pct: int, label: str):
            await db.rollout_jobs.update_one({"job_id": job_id},
                                             {"$set": {"progress": pct, "step": label, "updated_at": _now()}})

        try:
            await step(2, "Verifying single test site")
            purged = await purge_other_sandboxes(db)

            await step(8, "Snapshotting every client and template")
            snaps = await _snapshot(job_id)

            await step(25, "Pushing editorial system to active clients")
            clients = 0
            async for app in db.apps.find({}, {"_id": 0}):
                theme = app.get("theme") or {}
                accent = theme.get("primary") or "#10B981"
                if str(accent).upper() in RESERVED_ACCENTS:              # lime never leaves the platform site
                    accent = "#10B981"
                sm = dict(app.get("site_mode") or {})
                sm.update({"style": "editorial", "animation": "full"})
                sm.setdefault("mode", theme.get("mode") or "dark")
                sm.setdefault("publish", "live" if app.get("status") == "active" else "draft")
                sm["updated_at"] = _now()
                prof = profile_for(sm.get("template_key") or app.get("site_niche"), accent)
                await db.apps.update_one({"app_id": app["app_id"]}, {"$set": {
                    "site_mode": sm, "motion_profile": prof,
                    "theme.bg": "#080808", "theme.editorial": True,
                }})
                clients += 1

            await step(65, "Applying unique motion profile to all industry templates")
            tpl = 0
            for key, prof in MOTION_PROFILES.items():
                look = LOOKS.get(key)
                if look is None:
                    continue
                accent = (NICHES.get(key) or {}).get("primary") or prof["accent"]
                if str(accent).upper() in RESERVED_ACCENTS:
                    accent = prof["accent"]
                look.update({
                    "editorial": True, "ed_dark_base": True, "ed_bento": True,
                    "ed_float_gallery": True, "ed_ribbon": True, "ed_reveal": True,
                    "ed_counters": True, "ed_glow_paths": True, "ed_parallax": True,
                    "ed_hero": prof["hero"], "ed_layout": prof["layout"],
                    "ed_reveal_style": prof["reveal"], "ed_counter_style": prof["counter"],
                    "ed_accent": accent, "ed_glow_opacity": 0.4,
                })
                await db.template_looks.update_one({"key": key},
                                                   {"$set": {"key": key, "look": look, "editorial": True}},
                                                   upsert=True)
                tpl += 1

            await step(90, "Storing defaults for future clients")
            await db.platform_settings.update_one(
                {"_id": DEFAULTS_DOC},
                {"$set": {**DEFAULT_SITE_MODE, "inherit_motion": True, "updated_at": _now(),
                          "platform_profile": PLATFORM_PROFILE}},
                upsert=True)
            await db.platform_settings.update_one({"_id": "redesign_flag"},
                                                  {"$set": {"rolled_out_at": _now()}}, upsert=True)

            await db.rollout_jobs.update_one({"job_id": job_id}, {"$set": {
                "status": "done", "progress": 100, "step": "Rollout complete",
                "finished_at": _now(), "tenants": clients, "templates": tpl,
                "snapshots": snaps, "purged": purged,
            }})
            logger.info("Editorial rollout %s complete: %s clients, %s templates, %s snapshots",
                        job_id, clients, tpl, snaps)
        except Exception as e:                                   # noqa: BLE001
            logger.exception("Editorial rollout failed")
            await db.rollout_jobs.update_one({"job_id": job_id}, {"$set": {
                "status": "failed", "error": str(e), "finished_at": _now()}})

    @api.post("/editorial/rollout")
    async def start_rollout(user: dict = Depends(get_current_user)):
        job_id = _uid("edjob")
        await db.rollout_jobs.insert_one({
            "job_id": job_id, "kind": "editorial-motion-v1", "status": "running", "progress": 0,
            "step": "Queued", "created_at": _now(), "by": user.get("email"), "undoable": True})
        asyncio.create_task(_run(job_id, user))
        return {"ok": True, "job_id": job_id}

    @api.get("/editorial/rollout/{job_id}")
    async def rollout_status(job_id: str, user: dict = Depends(get_current_user)):
        job = await db.rollout_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(404, "Rollout job not found")
        return job

    @api.get("/editorial/profiles")
    async def profiles(user: dict = Depends(get_current_user)):
        return {"templates": MOTION_PROFILES, "reserved": RESERVED_PROFILES, "platform": PLATFORM_PROFILE,
                "defaults": DEFAULT_SITE_MODE, "total": len(MOTION_PROFILES) + len(RESERVED_PROFILES)}

    @api.get("/editorial/heroes")
    async def heroes(user: dict = Depends(get_current_user)):
        by_template = {v["hero"]: k for k, v in MOTION_PROFILES.items()}
        by_template.update({v["hero"]: f"reserved · {k}" for k, v in RESERVED_PROFILES.items()})
        by_template[PLATFORM_PROFILE["hero"]] = "luciodigital.ca (platform only)"
        return {"heroes": [{"hero": h, "used_by": by_template.get(h, "")} for h in HERO_NAMES],
                "total": len(HERO_NAMES)}

    def _lum(hex_c: str) -> float:
        h = (hex_c or "").lstrip("#")
        if len(h) != 6:
            return 0.0
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4   # noqa: E731
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

    def _brighten(hex_c: str, factor: float = 1.55) -> str:
        h = (hex_c or "").lstrip("#")
        if len(h) != 6:
            return "#10B981"
        rgb = [min(255, int(int(h[i:i + 2], 16) * factor) + 18) for i in (0, 2, 4)]
        return "#" + "".join(f"{c:02X}" for c in rgb)

    @api.get("/editorial/accent-audit")
    async def accent_audit(user: dict = Depends(get_current_user)):
        base = _lum("#080808")
        rows = []
        async for app in db.apps.find({}, {"_id": 0}):
            prof = app.get("motion_profile") or {}
            sm = app.get("site_mode") or {}
            accent = sm.get("accent") or prof.get("accent") or (app.get("theme") or {}).get("primary") or "#10B981"
            l = _lum(accent)
            contrast = round((max(l, base) + 0.05) / (min(l, base) + 0.05), 2)
            rows.append({
                "app_id": app["app_id"], "name": app.get("name"), "accent": accent.upper(),
                "hero": prof.get("hero") or "", "template_key": prof.get("template_key") or "",
                "contrast_on_080808": contrast,
                "verdict": "dull" if contrast < 3.0 else ("ok" if contrast < 4.5 else "vivid"),
                "suggested": _brighten(accent) if contrast < 3.0 else accent.upper(),
                "is_platform_lime": accent.upper() in RESERVED_ACCENTS,
            })
        rows.sort(key=lambda r: r["contrast_on_080808"])
        return {"base": "#080808", "tenants": rows, "dull": sum(1 for r in rows if r["verdict"] == "dull")}

    class HeroSwapIn(BaseModel):
        hero: str
        apply_to_tenants: bool = True

    @api.put("/editorial/templates/{key}/hero")
    async def swap_template_hero(key: str, body: HeroSwapIn, user: dict = Depends(get_current_user)):
        """Swaps a template's signature hero. Future clients inherit it; existing clients on that
        template are updated too unless they picked their own hero."""
        from site_content import LOOKS
        prof = MOTION_PROFILES.get(key)
        if not prof:
            raise HTTPException(404, "Unknown project")
        if body.hero not in HERO_NAMES:
            raise HTTPException(400, "Unknown hero motion")
        previous = prof["hero"]
        prof["hero"] = body.hero
        look = LOOKS.get(key)
        if look is not None:
            look["ed_hero"] = body.hero
            await db.template_looks.update_one({"key": key}, {"$set": {"key": key, "look": look}}, upsert=True)
        updated = []
        if body.apply_to_tenants:
            async for app in db.apps.find({}, {"_id": 0}):
                mp = app.get("motion_profile") or {}
                sm = app.get("site_mode") or {}
                if mp.get("template_key") != key or sm.get("hero"):     # respect per-client overrides
                    continue
                mp["hero"] = body.hero
                await db.apps.update_one({"app_id": app["app_id"]}, {"$set": {"motion_profile": mp}})
                updated.append(app.get("name"))
        return {"template_key": key, "hero": body.hero, "previous": previous, "tenants_updated": updated}

    @api.post("/editorial/accent-autotune")
    async def accent_autotune(user: dict = Depends(get_current_user)):
        """Brightens every dull accent in one pass."""
        audit = await accent_audit(user)
        changed = []
        for r in audit["tenants"]:
            if r["verdict"] != "dull" or r["is_platform_lime"]:
                continue
            sm = dict((await db.apps.find_one({"app_id": r["app_id"]}, {"_id": 0, "site_mode": 1}) or {}).get("site_mode") or {})
            mp = dict((await db.apps.find_one({"app_id": r["app_id"]}, {"_id": 0, "motion_profile": 1}) or {}).get("motion_profile") or {})
            sm["accent"] = r["suggested"]; sm["updated_at"] = _now(); mp["accent"] = r["suggested"]
            await db.apps.update_one({"app_id": r["app_id"]}, {"$set": {"site_mode": sm, "motion_profile": mp}})
            changed.append({"app_id": r["app_id"], "name": r["name"], "from": r["accent"], "to": r["suggested"]})
        return {"tuned": changed, "count": len(changed)}

    class FavIn(BaseModel):
        hero: str

    @api.get("/editorial/hero-favourites")
    async def get_favs(user: dict = Depends(get_current_user)):
        doc = await db.platform_settings.find_one({"_id": "hero_favourites"}) or {}
        return {"favourites": doc.get("heroes") or []}

    @api.post("/editorial/hero-favourites")
    async def toggle_fav(body: FavIn, user: dict = Depends(get_current_user)):
        if body.hero not in HERO_NAMES:
            raise HTTPException(400, "Unknown hero motion")
        doc = await db.platform_settings.find_one({"_id": "hero_favourites"}) or {}
        favs = list(doc.get("heroes") or [])
        favs.remove(body.hero) if body.hero in favs else favs.append(body.hero)
        await db.platform_settings.update_one({"_id": "hero_favourites"}, {"$set": {"heroes": favs}}, upsert=True)
        return {"favourites": favs}

    @api.get("/public/motion-profile/{app_id}")
    async def public_profile(app_id: str):
        """Preview, Live and Demo all read this — identical motion in every environment."""
        app = await db.apps.find_one({"app_id": app_id}, {"_id": 0, "motion_profile": 1, "site_mode": 1, "theme": 1})
        if not app:
            raise HTTPException(404, "Client not found")
        defaults = await db.platform_settings.find_one({"_id": DEFAULTS_DOC}) or {}
        sm = app.get("site_mode") or {}
        return {
            "motion_profile": app.get("motion_profile") or profile_for(sm.get("template_key"),
                                                                       (app.get("theme") or {}).get("primary")),
            "style": sm.get("style") or defaults.get("style") or "editorial",
            "animation": sm.get("animation") or defaults.get("animation") or "full",
            "mode": sm.get("mode") or defaults.get("mode") or "dark",
        }

    return {"profile_for": profile_for}


async def ensure_defaults(db) -> dict:
    """Future clients inherit these automatically — no per-client setup."""
    doc = await db.platform_settings.find_one({"_id": DEFAULTS_DOC})
    if not doc:
        await db.platform_settings.update_one(
            {"_id": DEFAULTS_DOC},
            {"$set": {**DEFAULT_SITE_MODE, "inherit_motion": True, "updated_at": _now(),
                      "platform_profile": PLATFORM_PROFILE}}, upsert=True)
    return DEFAULT_SITE_MODE


async def backfill_new_tenants(db) -> int:
    """Any client without a motion profile (i.e. created after the rollout) inherits it now."""
    n = 0
    async for app in db.apps.find({"motion_profile": {"$exists": False}}, {"_id": 0}):
        theme = app.get("theme") or {}
        accent = theme.get("primary") or "#10B981"
        if str(accent).upper() in RESERVED_ACCENTS:
            accent = "#10B981"
        sm = dict(app.get("site_mode") or {})
        sm.setdefault("style", DEFAULT_SITE_MODE["style"])
        sm.setdefault("animation", DEFAULT_SITE_MODE["animation"])
        sm.setdefault("mode", DEFAULT_SITE_MODE["mode"])
        await db.apps.update_one({"app_id": app["app_id"]}, {"$set": {
            "site_mode": sm,
            "motion_profile": profile_for(sm.get("template_key") or app.get("site_niche"), accent),
        }})
        n += 1
    return n
