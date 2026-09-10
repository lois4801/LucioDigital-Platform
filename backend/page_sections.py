"""Section templates per page type + page reordering for the Site Mode Page Manager.
Every set is built from the client's own niche copy, so it lands already on-brand: the palette,
accent and motion system come from the client's Site Mode settings, not from the set."""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import Depends, HTTPException
from pydantic import BaseModel

# page type -> curated sets. Each set: (id, label, best-for line, block types in order)
SETS: Dict[str, List[Dict[str, Any]]] = {
    "home": [
        {"id": "home-launch", "label": "Hero with CTA", "hint": "Best for a brand-new site that needs to convert from the first scroll.",
         "blocks": ["hero", "stats", "features", "testimonials", "cta"]},
        {"id": "home-proof", "label": "Proof-led landing", "hint": "Best when reviews and numbers are your strongest sales argument.",
         "blocks": ["hero", "testimonials", "stats", "features", "faq", "cta"]},
        {"id": "home-showcase", "label": "Visual showcase", "hint": "Best for studios and trades whose work sells itself in photos.",
         "blocks": ["hero", "gallery", "features", "testimonials", "cta"]},
        {"id": "home-service", "label": "Service-first", "hint": "Best for local service businesses that need calls today.",
         "blocks": ["hero", "features", "pricing", "stats", "contact"]},
    ],
    "about": [
        {"id": "about-team", "label": "Team intro", "hint": "Best when the people are the reason clients choose you.",
         "blocks": ["hero", "team", "text", "stats", "cta"]},
        {"id": "about-mission", "label": "Mission statement", "hint": "Best for a values-led story with a clear purpose up front.",
         "blocks": ["hero", "text", "features", "team", "cta"]},
        {"id": "about-timeline", "label": "Timeline", "hint": "Best for an established business with history worth showing.",
         "blocks": ["hero", "text", "stats", "gallery", "team", "cta"]},
        {"id": "about-gallery", "label": "Photo gallery", "hint": "Best for showing the space, the crew and the day-to-day.",
         "blocks": ["hero", "gallery", "team", "text", "contact"]},
    ],
    "services": [
        {"id": "services-cards", "label": "Service cards grid", "hint": "Best for a clear menu of what you offer at a glance.",
         "blocks": ["hero", "features", "pricing", "faq", "cta"]},
        {"id": "services-pricing", "label": "Pricing table", "hint": "Best when transparent prices win the enquiry.",
         "blocks": ["hero", "pricing", "features", "testimonials", "cta"]},
        {"id": "services-process", "label": "Process steps", "hint": "Best for explaining how the work actually runs, step by step.",
         "blocks": ["hero", "features", "stats", "gallery", "faq", "cta"]},
        {"id": "services-faq", "label": "FAQ accordion", "hint": "Best for services people research hard before buying.",
         "blocks": ["hero", "features", "faq", "testimonials", "contact"]},
    ],
    "contact": [
        {"id": "contact-form", "label": "Contact form", "hint": "Best for a single, simple way to get in touch.",
         "blocks": ["hero", "contact", "faq"]},
        {"id": "contact-locations", "label": "Office locations", "hint": "Best for multi-site businesses with visiting clients.",
         "blocks": ["hero", "contact", "features", "gallery"]},
        {"id": "contact-support", "label": "Support hours", "hint": "Best when response times and cover matter most.",
         "blocks": ["hero", "contact", "stats", "faq", "cta"]},
        {"id": "contact-book", "label": "Book a slot", "hint": "Best for appointment-led businesses taking bookings.",
         "blocks": ["hero", "contact", "pricing", "testimonials"]},
    ],
    "general": [
        {"id": "general-standard", "label": "Standard page", "hint": "Best all-round set: intro, detail and a clear next step.",
         "blocks": ["hero", "text", "features", "cta"]},
        {"id": "general-long", "label": "Long-form page", "hint": "Best for detailed explanations that need proof alongside.",
         "blocks": ["hero", "text", "features", "stats", "testimonials", "faq", "cta"]},
        {"id": "general-visual", "label": "Visual page", "hint": "Best for image-led pages such as projects or spaces.",
         "blocks": ["hero", "gallery", "text", "cta"]},
        {"id": "general-landing", "label": "Campaign landing", "hint": "Best for a single offer with one conversion goal.",
         "blocks": ["hero", "features", "testimonials", "contact"]},
    ],
}

TYPE_BY_SLUG = {"/": "home", "/about": "about", "/services": "services", "/contact": "contact"}


def page_type(slug: str, name: str = "") -> str:
    if slug in TYPE_BY_SLUG:
        return TYPE_BY_SLUG[slug]
    low = f"{slug} {name}".lower()
    for t in ("about", "services", "contact"):
        if t in low:
            return t
    return "general"


def sets_for(slug: str, name: str = "") -> Dict[str, Any]:
    t = page_type(slug, name)
    return {"page_type": t, "sets": SETS[t]}


def register(api, db, get_current_user, get_user_app, log_activity, uid, now_iso):

    class OrderIn(BaseModel):
        page_ids: List[str]

    class ApplyIn(BaseModel):
        set_id: str

    def _build(set_id: str, page: dict, app: dict, saved_blocks=None) -> List[dict]:
        """Blocks come from the client's own niche copy so the set is on-brand immediately."""
        from site_content import blocks_for_types, niche_for
        types = saved_blocks
        if types is None:
            for group in SETS.values():
                for s in group:
                    if s["id"] == set_id:
                        types = s["blocks"]
        if types is None:
            raise HTTPException(400, f"Unknown section set: {set_id}")
        niche = (app.get("motion_profile") or {}).get("template_key") or niche_for(app)
        return blocks_for_types(types, niche, app.get("name") or "", page.get("name") or "", uid)

    class SaveSetIn(BaseModel):
        label: str
        page_type: str = "general"
        hint: str = ""

    @api.get("/apps/{app_id}/pages/{page_id}/section-sets")
    async def section_sets(app_id: str, page_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        pg = await db.pages.find_one({"app_id": app_id, "page_id": page_id}, {"_id": 0})
        if not pg:
            raise HTTPException(404, "Page not found")
        got = sets_for(pg.get("slug") or "", pg.get("name") or "")
        saved = [d async for d in db.section_sets.find(
            {"page_type": {"$in": [got["page_type"], "any"]}}, {"_id": 0}).sort("created_at", -1)]
        return {**got, "sets": got["sets"] + saved, "saved_count": len(saved),
                "empty": not (pg.get("blocks") or []), "page_name": pg.get("name")}

    @api.post("/apps/{app_id}/pages/{page_id}/save-as-set")
    async def save_as_set(app_id: str, page_id: str, body: SaveSetIn, user: dict = Depends(get_current_user)):
        """Saves the page's STRUCTURE, so every future client fills it with their own copy."""
        await get_user_app(app_id, user)
        pg = await db.pages.find_one({"app_id": app_id, "page_id": page_id}, {"_id": 0})
        if not pg:
            raise HTTPException(404, "Page not found")
        blocks = [b.get("type") for b in (pg.get("blocks") or []) if b.get("type")
                  and b.get("type") not in ("navbar", "footer")]
        if not blocks:
            raise HTTPException(400, "This page has no sections to save yet")
        if body.page_type not in list(SETS.keys()) + ["any"]:
            raise HTTPException(400, "Unknown page type")
        label = body.label.strip()[:60]
        if not label:
            raise HTTPException(400, "Give the section set a name")
        doc = {"id": f"saved-{re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')}",
               "label": label, "page_type": body.page_type, "saved": True,
               "hint": body.hint.strip()[:120] or f"Saved from {pg.get('name')} — {len(blocks)} sections.",
               "blocks": blocks, "created_by": user["user_id"],
               "created_at": datetime.now(timezone.utc).isoformat()}
        await db.section_sets.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        await log_activity(app_id, user["user_id"], "sections.saved", f"Saved '{label}' as a section set")
        return doc

    @api.delete("/section-sets/{set_id}")
    async def delete_set(set_id: str, user: dict = Depends(get_current_user)):
        res = await db.section_sets.delete_one({"id": set_id})
        if not res.deleted_count:
            raise HTTPException(404, "Section set not found")
        return {"ok": True}

    @api.post("/apps/{app_id}/pages/{page_id}/apply-set")
    async def apply_set(app_id: str, page_id: str, body: ApplyIn, user: dict = Depends(get_current_user)):
        app = await get_user_app(app_id, user)
        pg = await db.pages.find_one({"app_id": app_id, "page_id": page_id}, {"_id": 0})
        if not pg:
            raise HTTPException(404, "Page not found")
        if body.set_id == "blank":
            blocks = []
        else:
            saved = await db.section_sets.find_one({"id": body.set_id}, {"_id": 0})
            blocks = _build(body.set_id, pg, app, saved.get("blocks") if saved else None)
        await db.pages.update_one({"app_id": app_id, "page_id": page_id},
                                  {"$set": {"blocks": blocks, "updated_at": now_iso()}})
        await log_activity(app_id, user["user_id"], "page.sections",
                           f"Applied the '{body.set_id}' section set to {pg.get('name')}")
        return {"page_id": page_id, "blocks": blocks, "count": len(blocks)}

    @api.put("/apps/{app_id}/pages/order")
    async def reorder_pages(app_id: str, body: OrderIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        pages = {p["page_id"]: p async for p in db.pages.find({"app_id": app_id}, {"_id": 0})}
        unknown = [p for p in body.page_ids if p not in pages]
        if unknown:
            raise HTTPException(400, "Those pages do not belong to this client")
        for i, pid in enumerate(body.page_ids):
            await db.pages.update_one({"app_id": app_id, "page_id": pid}, {"$set": {"order": i}})
        # the site navigation follows the tab order exactly
        wanted = [pages[p]["slug"] for p in body.page_ids]
        async for pg in db.pages.find({"app_id": app_id}, {"_id": 0, "page_id": 1, "blocks": 1}):
            blocks, touched = pg.get("blocks") or [], False
            for b in blocks:
                if b.get("type") != "navbar":
                    continue
                links = list((b.get("props") or {}).get("links") or [])
                ordered = ([next(x for x in links if (x or {}).get("href") == s) for s in wanted
                            if any((x or {}).get("href") == s for x in links)]
                           + [x for x in links if (x or {}).get("href") not in wanted])
                if ordered != links:
                    b["props"]["links"] = ordered
                    touched = True
            if touched:
                await db.pages.update_one({"app_id": app_id, "page_id": pg["page_id"]}, {"$set": {"blocks": blocks}})
        await log_activity(app_id, user["user_id"], "pages.reorder", "Reordered the site pages")
        return {"ok": True, "order": body.page_ids}
