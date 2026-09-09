"""Template Gallery + client-facing template preview links.

Nothing here creates a tenant. `/public/templates` and `/public/templates/{key}` build the site
in memory from the template definition so the gallery can render a real, scrollable preview of
every design without touching the database.
"""
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

SHARE_DAYS = 7

# Browsable industry categories for the gallery filter tabs.
CATEGORY = {
    "hvac": "Home Services", "healthcare": "Medical", "construction": "Construction",
    "fitness": "Fitness", "retail": "Retail", "hospitality": "Hospitality",
    "finance": "Finance", "it_services": "Tech", "creative_studio": "Creative",
    "logistics": "Logistics", "saas": "Tech", "legal": "Legal", "education": "Education",
    "real_estate": "Real Estate", "restaurant": "Hospitality", "events": "Events",
}


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


class ShareIn(BaseModel):
    client_name: str
    note: str = ""


class SelectIn(BaseModel):
    key: str
    client_note: str = ""


def build_template_site(key: str):
    """Render a template to pages + theme in memory. No DB writes, no tenant created."""
    from site_content import NICHES, LOOKS, build_premium_site
    if key not in LOOKS:
        raise HTTPException(404, "Unknown template")
    n = NICHES[key]
    fake = {"app_id": f"tpl_{key}", "name": n["brand"], "industry": n["industry"],
            "description": n["sub"], "thumbnail": n["hero"], "video_url": n["video"]}
    pages, theme, _n = build_premium_site(fake, key, {"name": n["brand"]})
    return {
        "key": key, "brand": n["brand"], "industry": n["industry"], "category": CATEGORY[key],
        "tagline": n["title"], "summary": n["sub"], "thumbnail": n["hero"], "video": n["video"],
        "theme": theme,
        "pages": [{"name": p[0], "slug": p[1], "blocks": p[2]} for p in pages],
    }


def register(api, db, get_current_user):
    from site_content import NICHES, LOOKS

    @api.get("/public/templates")
    async def list_templates():
        out = []
        for key, look in LOOKS.items():
            n = NICHES[key]
            out.append({
                "key": key, "brand": n["brand"], "industry": n["industry"], "category": CATEGORY[key],
                "tagline": n["title"], "summary": n["sub"], "thumbnail": n["hero"], "video": n["video"],
                "mode": look["mode"], "primary": look["primary"], "secondary": look["secondary"],
                "bg": look["bg"], "surface": look["surface"], "border": look["border"],
                "font_heading": look["font_heading"], "font_body": look["font_body"],
                "radius": look["radius"], "preset": look["preset"], "hero": look["hero"],
            })
        cats = sorted({c["category"] for c in out})
        return {"templates": out, "categories": cats, "count": len(out)}

    @api.get("/public/templates/{key}")
    async def template_detail(key: str):
        return build_template_site(key)

    # ---------- Client preview links (no login, expire after 7 days) ----------
    @api.post("/template-shares")
    async def create_share(body: ShareIn, user: dict = Depends(get_current_user)):
        doc = {
            "token": secrets.token_urlsafe(12), "client_name": body.client_name.strip() or "Client",
            "note": body.note.strip(), "created_by": user["user_id"], "created_at": _iso(_now()),
            "expires_at": _iso(_now() + timedelta(days=SHARE_DAYS)),
            "selected_key": None, "selected_at": None, "client_note": "", "views": 0, "acknowledged": False,
        }
        await db.template_shares.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @api.get("/template-shares")
    async def list_shares(user: dict = Depends(get_current_user)):
        docs = await db.template_shares.find({"created_by": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
        now = _iso(_now())
        for d in docs:
            d["expired"] = d["expires_at"] < now
            if d.get("selected_key"):
                d["selected_brand"] = NICHES.get(d["selected_key"], {}).get("brand")
        return {"shares": docs, "pending": [d for d in docs if d.get("selected_key") and not d.get("acknowledged")]}

    @api.post("/template-shares/{token}/ack")
    async def ack_share(token: str, user: dict = Depends(get_current_user)):
        r = await db.template_shares.update_one({"token": token, "created_by": user["user_id"]}, {"$set": {"acknowledged": True}})
        if not r.matched_count:
            raise HTTPException(404, "Preview link not found")
        return {"ok": True}

    @api.delete("/template-shares/{token}")
    async def revoke_share(token: str, user: dict = Depends(get_current_user)):
        r = await db.template_shares.delete_one({"token": token, "created_by": user["user_id"]})
        if not r.deleted_count:
            raise HTTPException(404, "Preview link not found")
        return {"ok": True}

    async def _live_share(token: str):
        doc = await db.template_shares.find_one({"token": token}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "This preview link is not valid")
        if doc["expires_at"] < _iso(_now()):
            raise HTTPException(410, "This preview link has expired. Ask your agency for a fresh one.")
        return doc

    @api.get("/public/template-shares/{token}")
    async def open_share(token: str):
        doc = await _live_share(token)
        await db.template_shares.update_one({"token": token}, {"$inc": {"views": 1}, "$set": {"viewed_at": _iso(_now())}})
        return {"client_name": doc["client_name"], "note": doc["note"], "expires_at": doc["expires_at"],
                "selected_key": doc.get("selected_key"), "client_note": doc.get("client_note", "")}

    @api.post("/public/template-shares/{token}/select")
    async def select_template(token: str, body: SelectIn):
        await _live_share(token)
        if body.key not in LOOKS:
            raise HTTPException(400, "Unknown template")
        await db.template_shares.update_one({"token": token}, {"$set": {
            "selected_key": body.key, "selected_at": _iso(_now()),
            "client_note": body.client_note.strip()[:600], "acknowledged": False,
        }})
        return {"ok": True, "selected_key": body.key, "brand": NICHES[body.key]["brand"]}

    return {"build_template_site": build_template_site}
