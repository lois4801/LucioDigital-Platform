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
        "demos_overline": "See it in action", "demos_heading": "Watch Lois-Tech build, brand and ship a product.",
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
    return (user.get("email") or "").lower().strip() == (os.environ.get("ADMIN_EMAIL") or "").lower().strip()


def register(api, db, get_current_user, get_user_app=None, log_activity=None):
    async def _noop_log(*_a, **_k):
        return None

    _log = log_activity or _noop_log

    async def _own(app_id, user):
        if get_user_app:
            return await get_user_app(app_id, user)
        doc = await db.apps.find_one({"app_id": app_id, "owner_id": user["user_id"]}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Tenant not found")
        return doc

    def _now():
        return datetime.now(timezone.utc).isoformat()

    async def _get():
        doc = await db.site_settings.find_one({"key": "landing"}, {"_id": 0}) or {}
        return {"cards": doc.get("cards", DEFAULTS["cards"]), "marquee": doc.get("marquee", DEFAULTS["marquee"]), "texts": {**DEFAULTS["texts"], **doc.get("texts", {})}}

    @api.get("/public/landing")
    async def public_landing():
        return await _get()

    @api.patch("/apps/{app_id}/showcase")
    async def toggle_featured(app_id: str, body: dict, user: dict = Depends(get_current_user)):
        """Star/unstar a tenant for the public landing showcase."""
        await _own(app_id, user)
        featured = bool(body.get("featured"))
        upd = {"featured": featured, "updated_at": _now()}
        if featured:
            last = await db.apps.find({"owner_id": user["user_id"], "featured": True},
                                      {"_id": 0, "showcase_order": 1}).sort("showcase_order", -1).limit(1).to_list(1)
            upd["showcase_order"] = int((last[0].get("showcase_order") if last else -1) or 0) + 1
        ops = {"$set": upd} if featured else {"$set": upd, "$unset": {"showcase_order": ""}}
        await db.apps.update_one({"app_id": app_id}, ops)
        await _log(app_id, user["user_id"], "showcase.featured",
                   f"{'Featured on' if featured else 'Removed from'} the landing showcase")
        return await db.apps.find_one({"app_id": app_id}, {"_id": 0})

    @api.put("/apps/showcase/order")
    async def reorder_showcase(body: dict, user: dict = Depends(get_current_user)):
        """Persists the drag-to-reorder sequence of the landing showcase cards."""
        ids = [str(i) for i in (body.get("app_ids") or [])][:60]
        if not ids:
            raise HTTPException(400, "Send app_ids in the order you want them shown")
        owned = set(await db.apps.distinct("app_id", {"owner_id": user["user_id"], "app_id": {"$in": ids}}))
        missing = [i for i in ids if i not in owned]
        if missing:
            raise HTTPException(404, f"Not your tenant: {missing[0]}")
        from pymongo import UpdateOne
        # Authoritative resequence: the given ids take 0..n-1 and any other starred tenant keeps its
        # relative position after them, so two cards can never share an order.
        rest = await db.apps.find({"owner_id": user["user_id"], "featured": True,
                                   "app_id": {"$nin": ids}},
                                  {"_id": 0, "app_id": 1, "showcase_order": 1}).to_list(60)
        rest.sort(key=lambda a: a.get("showcase_order", 0))
        seq = ids + [a["app_id"] for a in rest]
        # Ordering only ever applies to featured cards, so keep the star on while resequencing.
        await db.apps.bulk_write([UpdateOne({"app_id": a}, {"$set": {"showcase_order": i, "featured": True}})
                                  for i, a in enumerate(seq)], ordered=False)
        return {"ordered": len(ids), "sequence": seq}

    @api.get("/public/landing/templates")
    async def public_templates():
        """Every niche site template the platform can build — derived live from the template library."""
        from site_content import NICHES
        out = []
        for key, n in NICHES.items():
            out.append({"key": key, "title": n["industry"], "brand": n["brand"], "description": n["sub"][:160],
                        "image": n["hero"], "primary": n["primary"], "sections": len(n["sections"])})
        return {"templates": sorted(out, key=lambda t: t["title"]), "count": len(out)}

    @api.get("/public/landing/tenants")
    async def public_tenants():
        """Real tenants in the platform admin's workspace, with their live deployment state."""
        from site_content import NICHES, niche_for
        admin = await db.users.find_one({"email": (os.environ.get("ADMIN_EMAIL") or "").lower().strip()}, {"_id": 0, "user_id": 1})
        if not admin:
            return {"tenants": [], "count": 0, "live": 0}
        apps = await db.apps.find({"owner_id": admin["user_id"], "is_deleted": {"$ne": True}, "archived": {"$ne": True}},
                                  {"_id": 0}).to_list(60)
        starred = [a for a in apps if a.get("featured")]
        if starred:
            # Once the admin stars any tenant, the showcase shows exactly those, in their chosen order.
            apps = sorted(starred, key=lambda a: (a.get("showcase_order", 0), a.get("created_at") or ""))
        else:
            apps = sorted(apps, key=lambda a: a.get("created_at") or "", reverse=True)
        out = []
        for a in apps:
            key = a.get("site_niche") or niche_for(a)
            n = NICHES.get(key) or {}
            live = a.get("domain_status") == "verified" or (a.get("status") == "active" and bool(a.get("preview_enabled")))
            out.append({
                "app_id": a["app_id"], "name": a.get("name"), "tag": a.get("industry") or n.get("industry") or "General",
                "cover": a.get("thumbnail") or a.get("logo") or n.get("hero"),
                "video": a.get("video_url") or n.get("video"),
                "token": a.get("preview_token") if a.get("preview_enabled") else None,
                "status": "LIVE" if live else "TEMPLATE",
                "domain": a.get("custom_domain") if a.get("domain_status") == "verified" else None,
                "niche": key, "kind": a.get("kind") or "website", "color": a.get("color"),
                "featured": bool(a.get("featured")), "order": a.get("showcase_order", 0),
                "summary": a.get("description") or n.get("sub") or "",
                "tagline": n.get("title") or "", "sections": n.get("sections") or [],
                "primary": n.get("primary") or a.get("color"),
            })
        return {"tenants": out, "count": len(out), "live": sum(1 for t in out if t["status"] == "LIVE")}

    @api.put("/admin/landing")
    async def update_landing(body: LandingPatch, user: dict = Depends(get_current_user)):
        if not is_admin(user):
            raise HTTPException(403, "Admin only")
        cur = await _get()
        if body.cards is not None:
            # Legacy landing cards; the live landing page now renders niche templates from the template library.
            cur["cards"] = [{"id": c.id or f"card_{uuid.uuid4().hex[:8]}", "title": c.title.strip()[:80], "description": (c.description or "").strip()[:300], "image": (c.image or "").strip()[:500]} for c in body.cards]
        if body.marquee is not None:
            cur["marquee"] = [m.strip()[:40] for m in body.marquee if m.strip()][:24]
        if body.texts is not None:
            cur["texts"] = {**cur["texts"], **{k[:60]: v.strip()[:600] for k, v in body.texts.items() if k.strip()}}
        await db.site_settings.update_one({"key": "landing"}, {"$set": {**cur, "key": "landing", "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": user["email"]}}, upsert=True)
        return cur
