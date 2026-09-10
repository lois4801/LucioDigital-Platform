"""Public Motion Systems index + Template Isolation Preview.

`/motion` and `/hero-gallery` render the same permanently public index: every motion system,
its assigned industry template and whether it is ACTIVE (a live tenant runs it) or RESERVED
(built and assigned, waiting for a tenant). Nothing here mutates a tenant or a template.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("agency.motion_showcase")

PICKS = "hero_picks"

# Client-facing industry labels for every template key.
LABELS = {
    "real_estate": "Real Estate", "education": "Education", "healthcare": "Healthcare",
    "fitness": "Fitness", "legal": "Legal", "hospitality": "Hospitality",
    "construction": "Construction", "saas": "Tech / SaaS", "creative_studio": "Creative Studio",
    "events": "Events", "finance": "Finance", "retail": "Retail", "restaurant": "Restaurant",
    "logistics": "Logistics", "it_services": "IT Services", "hvac": "HVAC",
    "veterinary": "Veterinary", "dental": "Dental", "accounting": "Accounting",
    "landscaping": "Landscaping", "photography": "Photography", "automotive": "Automotive",
    "beauty": "Beauty", "insurance": "Insurance", "pet_grooming": "Pet Grooming",
    "hvac_plumbing": "HVAC & Plumbing", "coworking": "Coworking", "wellness": "Wellness",
    "cleaning": "Cleaning", "music_school": "Music School", "nonprofit": "Nonprofit",
    "architecture": "Architecture", "test_template": "Sandbox Template",
    "tech_code": "Tech / Code", "medical": "Medical", "sports": "Sports", "fashion": "Fashion",
    "internal_tools": "Internal Tools", "saas_portals": "SaaS Portals",
    "art_culture": "Art & Culture", "mental_health": "Mental Health",
    "food_beverage": "Food & Beverage", "property_mgmt": "Property Management",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def label_for(key: str) -> str:
    return LABELS.get(key) or (key or "").replace("_", " ").title()


def register(api, db, get_current_user):
    from editorial_rollout import (HERO_NAMES, MOTION_PROFILES, PLATFORM_PROFILE,
                                   RESERVED_PROFILES, LIME)

    async def _live_by_template() -> dict:
        """template_key → [tenant names] for every non-archived tenant."""
        out: dict = {}
        async for app in db.apps.find({"archived": {"$ne": True}},
                                      {"_id": 0, "name": 1, "site_niche": 1, "motion_profile": 1, "site_mode": 1}):
            keys = {(app.get("motion_profile") or {}).get("template_key"),
                    (app.get("site_mode") or {}).get("template_key"),
                    app.get("site_niche")}
            for k in keys:
                if k:
                    out.setdefault(k, []).append(app.get("name") or k)
        return out

    async def _catalogue():
        live = await _live_by_template()
        rows = []
        for key, prof in list(MOTION_PROFILES.items()) + list(RESERVED_PROFILES.items()):
            tenants = live.get(key) or []
            rows.append({
                "hero": prof["hero"], "template_key": key,
                "industry": label_for(key), "industry_slug": key,
                "accent": prof["accent"], "reserved": key in RESERVED_PROFILES,
                "layout": prof["layout"], "reveal": prof["reveal"], "counter": prof["counter"],
                "status": "active" if tenants else "reserved",
                "tenants": tenants, "tenant_count": len(tenants),
            })
        used = {r["hero"] for r in rows}
        for h in HERO_NAMES:
            if h in used:
                continue
            platform = h == PLATFORM_PROFILE["hero"]
            rows.append({
                "hero": h, "template_key": "" if not platform else "platform",
                "industry": "lois-tech.ca (platform)" if platform else "Unassigned",
                "industry_slug": "platform" if platform else "unassigned",
                "accent": LIME if platform else "#10B981", "reserved": not platform,
                "layout": PLATFORM_PROFILE["layout"] if platform else "",
                "reveal": PLATFORM_PROFILE["reveal"] if platform else "",
                "counter": PLATFORM_PROFILE["counter"] if platform else "",
                "status": "active" if platform else "reserved",
                "tenants": ["lois-tech.ca"] if platform else [], "tenant_count": 1 if platform else 0,
            })
        rows.sort(key=lambda r: (r["status"] != "active", r["hero"]))
        return rows

    @api.get("/public/motion-reel")
    async def motion_reel():
        """Everything the public index needs — no auth, no tenant data beyond template usage."""
        rows = await _catalogue()
        return {
            "heroes": rows,
            "total": len(rows),
            "active": sum(1 for r in rows if r["status"] == "active"),
            "reserved": sum(1 for r in rows if r["status"] == "reserved"),
            "industries": sorted({r["industry"] for r in rows}),
            "platform_hero": PLATFORM_PROFILE["hero"],
            "reserved_accent": LIME,
        }

    @api.get("/public/motion-preview/{key}")
    async def motion_preview(key: str):
        """Full motion context for ONE template, rendered in isolation — public, no auth."""
        prof = MOTION_PROFILES.get(key) or RESERVED_PROFILES.get(key)
        if key == "platform":
            prof = PLATFORM_PROFILE
        if not prof:
            raise HTTPException(404, "Unknown template")
        live = await _live_by_template()
        tenants = live.get(key) or (["lois-tech.ca"] if key == "platform" else [])
        return {
            "template_key": key, "industry": label_for(key) if key != "platform" else "lois-tech.ca (platform)",
            "profile": {**prof, "template_key": key, "speed": 1.0, "intensity": 1.0},
            "status": "active" if tenants else "reserved", "tenants": tenants,
        }

    class PickIn(BaseModel):
        hero: str
        name: str = ""
        email: str = ""
        company: Optional[str] = ""
        note: Optional[str] = ""
        speed: Optional[float] = 1.0
        intensity: Optional[float] = 1.0

    @api.post("/public/motion-picks")
    async def create_pick(body: PickIn):
        if body.hero not in HERO_NAMES:
            raise HTTPException(400, "Unknown hero motion")
        if not body.email.strip() or "@" not in body.email:
            raise HTTPException(400, "A valid email is required")
        doc = {
            "pick_id": f"pick_{uuid.uuid4().hex[:12]}",
            "hero": body.hero, "name": body.name.strip(), "email": body.email.strip().lower(),
            "company": (body.company or "").strip(), "note": (body.note or "").strip(),
            "speed": round(max(0.25, min(2.0, body.speed or 1.0)), 2),
            "intensity": round(max(0.2, min(1.5, body.intensity or 1.0)), 2),
            "status": "new", "created_at": _now(),
        }
        await db[PICKS].insert_one(dict(doc))
        return {"ok": True, "pick_id": doc["pick_id"], "hero": doc["hero"]}

    @api.get("/motion-picks")
    async def list_picks(user: dict = Depends(get_current_user)):
        rows = await db[PICKS].find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return {"picks": rows, "total": len(rows),
                "new": sum(1 for r in rows if r.get("status") == "new")}

    @api.post("/motion-picks/{pick_id}/seen")
    async def mark_seen(pick_id: str, user: dict = Depends(get_current_user)):
        r = await db[PICKS].update_one({"pick_id": pick_id}, {"$set": {"status": "seen", "seen_at": _now()}})
        if not r.matched_count:
            raise HTTPException(404, "Pick not found")
        return {"ok": True}
