import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict
from fastapi import HTTPException, Depends
from pydantic import BaseModel

DEFAULTS = {
    "cards": [
        {"id": "card_ecom", "title": "E-commerce", "description": "Storefronts with featured products, offers and loyalty built in.", "image": "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=900&q=80"},
        {"id": "card_saas", "title": "SaaS dashboards", "description": "Data-dense product dashboards with billing and client portals.", "image": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=900&q=80"},
        {"id": "card_wellness", "title": "Wellness apps", "description": "Class schedules, trainers, memberships and free-trial funnels.", "image": "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=900&q=80"},
        {"id": "card_logistics", "title": "Logistics tools", "description": "Fleet, dispatch and freight quoting with live tracking.", "image": "https://images.unsplash.com/photo-1601584115197-04ecc0da31d7?w=900&q=80"},
    ],
    "marquee": ["Nexus", "Orbit", "Fleet", "Aura", "Ledger", "Studio", "Vanta", "Halo"],
    "texts": {
        "hero_caption_overline": "Live · Orbit SaaS Portal", "hero_caption_title": "B2B Success Analytics",
        "products_overline": "Products we ship", "products_heading": "Every tenant, on-brand and always live.",
        "demos_overline": "See it in action", "demos_heading": "Watch OmniStack build, brand and ship a product.",
        "platform_overline": "The platform", "platform_heading": "Everything between “kickoff” and “handoff”.",
        "cta_heading": "Launch your agency workspace today.",
    },
}


class Card(BaseModel):
    id: Optional[str] = None
    title: str
    description: Optional[str] = ""
    image: Optional[str] = ""


class LandingPatch(BaseModel):
    cards: Optional[List[Card]] = None
    marquee: Optional[List[str]] = None
    texts: Optional[Dict[str, str]] = None


def is_admin(user: dict) -> bool:
    return (user.get("email") or "").lower().strip() == os.environ["ADMIN_EMAIL"].lower().strip()


def register(api, db, get_current_user):
    async def _get():
        doc = await db.site_settings.find_one({"key": "landing"}, {"_id": 0}) or {}
        return {"cards": doc.get("cards", DEFAULTS["cards"]), "marquee": doc.get("marquee", DEFAULTS["marquee"]), "texts": {**DEFAULTS["texts"], **doc.get("texts", {})}}

    @api.get("/public/landing")
    async def public_landing():
        return await _get()

    @api.put("/admin/landing")
    async def update_landing(body: LandingPatch, user: dict = Depends(get_current_user)):
        if not is_admin(user):
            raise HTTPException(403, "Admin only")
        cur = await _get()
        if body.cards is not None:
            cur["cards"] = [{"id": c.id or f"card_{uuid.uuid4().hex[:8]}", "title": c.title.strip()[:80], "description": (c.description or "").strip()[:300], "image": (c.image or "").strip()[:500]} for c in body.cards]
        if body.marquee is not None:
            cur["marquee"] = [m.strip()[:40] for m in body.marquee if m.strip()][:24]
        if body.texts is not None:
            cur["texts"] = {**cur["texts"], **{k[:60]: v.strip()[:600] for k, v in body.texts.items() if k.strip()}}
        await db.site_settings.update_one({"key": "landing"}, {"$set": {**cur, "key": "landing", "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": user["email"]}}, upsert=True)
        return cur
