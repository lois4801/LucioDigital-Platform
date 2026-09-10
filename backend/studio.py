import os
import re
import json
import base64
import hashlib
import logging
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Depends, Response
from pydantic import BaseModel
from llm_provider import get_chat, UserMessage, llm_available, generate_speech

logger = logging.getLogger("agency.studio")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def uid(prefix):
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


DEFAULT_THEME = {
    "mode": "dark", "primary": "#F97316", "secondary": "#14B8A6", "bg": "#0A0A0F", "surface": "#141420",
    "fg": "#F8FAFC", "muted": "#A1A7B8", "border": "#262637",
    "font_heading": "Plus Jakarta Sans", "font_body": "Manrope", "radius": 20, "motion": True, "cursor": True, "cursor_effect": "none", "cursor_density": 1, "cursor_speed": 1, "glass": True, "grain": True,
    "design_v2": False,
}

# The Framer-grade standard applied to every new tenant site and every AI-generated site.
V2_THEME = {**DEFAULT_THEME, "font_heading": "Sora", "font_body": "Inter", "radius": 20, "design_v2": True}

BLOCK_SCHEMA = """
Block types and props (every block: {"id": string, "type": string, "props": {...}, "style": {"bg": "default|muted|accent|dark", "align": "left|center", "padding": "sm|md|lg"}}):
- navbar: {brand, links:[{label, href}], cta}
- hero: {variant: "cover|centered|split|left", badge, title, subtitle, cta, cta2, image (unsplash url; "cover" renders it full-width behind a cinematic gradient)}
- logos: {heading, names:[string]}  (also used for certifications, insurers, service areas, technologies)
- features: {heading, subheading, items:[{title, desc, icon (lucide name: Zap|Shield|Rocket|Heart|Star|Globe|Sparkles|Clock|Users|Check)}]}
- stats: {heading, items:[{value, label}]}
- team: {heading, members:[{name, role, photo (unsplash portrait url)}]}
- gallery: {heading, images:[unsplash urls]}
- video: {heading, url (mp4 url or YouTube embed url), caption}
- testimonials: {heading, items:[{quote, name, role}]}
- pricing: {heading, plans:[{name, price, period, features:[string], highlight: bool}]}
- faq: {heading, items:[{q, a}]}
- chart: {heading, caption, series:[{m, v}]}
- cta: {title, subtitle, cta}
- contact: {heading, subtitle, email, phone, address}
- form: {heading, subtitle, fields:[{name, label, type: "text|email|tel|number|url|date|textarea|select|checkbox|radio", placeholder, required: bool, options:[string] (select/radio only)}], submit_label, success_message}  (submissions land in the tenant's Lead Inbox)
- footer: {brand, tagline, columns:[{title, links:[string]}]}
- collection_list: {heading, collection: "blog|case-studies", limit: 6}  (auto-fills from the CMS)
Hrefs for links must be page slugs like "/", "/about", "/pricing" or "#section".
"""

INDUSTRY_SECTIONS = ("Industry section structure (use the matching one, adapt for other niches): HVAC → Services, Emergency Call, Maintenance Plans, Service Areas, Certifications. "
                     "Healthcare → Specialties, Meet the Doctors, Insurance Accepted, Patient Portal, Appointment Booking. Construction → Projects Portfolio, Services, Safety Record, Certifications, Request a Quote. "
                     "Fitness → Class Schedule, Trainers, Membership Plans, Transformation Stories, Free Trial. Retail → Featured Products, Categories, Offers, Loyalty Program, Store Locator. "
                     "Hospitality → Rooms, Amenities, Dining, Local Attractions, Booking. Finance → Services, Why Us, Client Results, Compliance & Security, Get Started. IT services → Solutions, Technologies, Case Studies, SLA Guarantee, Free Audit.")


def _clean_theme(t: dict) -> dict:
    out = {k: v for k, v in (t or {}).items() if k in DEFAULT_THEME}
    r = out.get("radius")
    if isinstance(r, str):
        out["radius"] = {"none": 0, "sm": 6, "md": 12, "lg": 16, "xl": 24, "full": 32}.get(r.lower(), 16)
    elif not isinstance(r, (int, float)):
        out.pop("radius", None)
    for k in ("primary", "secondary", "bg", "surface", "fg", "muted", "border"):
        if k in out and not re.match(r"^#[0-9a-fA-F]{6}$", str(out[k])):
            out.pop(k)
    for k in ("font_heading", "font_body"):
        if k in out and str(out[k]).strip().lower() in ("roboto", "arial", "times new roman"):
            out[k] = V2_THEME[k]
    if out.get("mode") not in ("light", "dark"):
        out.pop("mode", None)
    return out


class ThemeIn(BaseModel):
    theme: Dict[str, Any]


class PageCreateIn(BaseModel):
    name: str
    slug: str


class PageUpdateIn(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    blocks: Optional[List[Dict[str, Any]]] = None


class BriefIn(BaseModel):
    brief: str
    pages: Optional[List[str]] = None


class ChatIn(BaseModel):
    session_id: str
    message: str


class TtsIn(BaseModel):
    text: str
    voice: str = "coral"


def _parse_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s >= 0 and e > s:
            return json.loads(text[s:e + 1], strict=False)
        raise


async def _claude(system: str, prompt: str, session: str, app_id: str = None, feature: str = "site_generation") -> str:
    from ai_models import resolve_for
    provider, model = await resolve_for(app_id, feature)
    chat = get_chat(provider, model, system, session)
    reply = await chat.send_message(UserMessage(text=prompt))
    return reply if isinstance(reply, str) else str(reply)


def _ensure_ids(blocks: List[dict]) -> List[dict]:
    out = []
    for b in blocks or []:
        if not isinstance(b, dict) or "type" not in b:
            continue
        b.setdefault("id", uid("blk"))
        b.setdefault("props", {})
        b.setdefault("style", {"bg": "default", "align": "left", "padding": "md"})
        b["style"].setdefault("effects", {"reveal": True, "hover": b["type"] in ("features", "gallery", "testimonials", "pricing", "collection_list", "logos", "team", "stats")})
        b["style"].setdefault("glass", True)
        out.append(b)
    return out


def _blocks_text(blocks: List[dict]) -> str:
    lines = []
    for b in blocks:
        p = b.get("props", {})
        for k in ("title", "heading", "subtitle", "subheading", "tagline"):
            if p.get(k):
                lines.append(str(p[k]))
        for it in p.get("items", []) or []:
            if isinstance(it, dict):
                lines.append(" — ".join(str(v) for k, v in it.items() if k in ("title", "desc", "q", "a", "quote")))
        for pl in p.get("plans", []) or []:
            if isinstance(pl, dict):
                lines.append(f"Plan {pl.get('name')}: {pl.get('price')} {pl.get('period','')} — {', '.join(pl.get('features', []))}")
        if b.get("type") == "contact":
            lines.append(f"Contact: {p.get('email','')} {p.get('phone','')} {p.get('address','')}")
    return "\n".join(lines)[:6000]


require_ai_access = None


def register(api, db, get_current_user, get_user_app, log_activity, hooks=None):
    hooks = hooks or {}

    # ===== THEME =====
    @api.get("/apps/{app_id}/theme")
    async def get_theme(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        return {**DEFAULT_THEME, **(doc.get("theme") or {})}

    @api.put("/apps/{app_id}/theme")
    async def put_theme(app_id: str, body: ThemeIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        theme = {**DEFAULT_THEME, **_clean_theme(body.theme)}
        await db.apps.update_one({"app_id": app_id}, {"$set": {"theme": theme, "updated_at": now_iso()}})
        await log_activity(app_id, user["user_id"], "theme.saved", "Design theme updated")
        from content_lock import sync_overview
        await sync_overview(db, app_id)
        return theme

    @api.post("/apps/{app_id}/site/upgrade-design")
    async def upgrade_design(app_id: str, user: dict = Depends(get_current_user)):
        """Switch a legacy tenant to the current design standard. Copy, images and layout are
        untouched — only the theme flag (and the old default font pair) change."""
        doc = await get_user_app(app_id, user)
        from page_guard import role_of, snapshot_site
        if await role_of(db, doc, user) not in ("owner", "admin"):
            raise HTTPException(403, "Only the agency owner or an admin can upgrade a site's design")
        old = {**DEFAULT_THEME, **_clean_theme(doc.get("theme"))}
        if old.get("design_v2"):
            return {"already": True, "theme": old}
        snap = await snapshot_site(db, app_id, user.get("name") or user["email"], "before design upgrade")
        theme = {**old, "design_v2": True}
        if old.get("font_heading") == DEFAULT_THEME["font_heading"] and old.get("font_body") == DEFAULT_THEME["font_body"]:
            theme["font_heading"], theme["font_body"] = V2_THEME["font_heading"], V2_THEME["font_body"]
        await db.apps.update_one({"app_id": app_id}, {"$set": {"theme": theme, "updated_at": now_iso()}})
        await log_activity(app_id, user["user_id"], "design.upgraded",
                           "Upgraded to the current design standard — content unchanged")
        from content_lock import sync_overview
        await sync_overview(db, app_id)
        return {"already": False, "theme": theme, "restore_point": snap}

    @api.post("/site/upgrade-design-all")
    async def upgrade_design_all(user: dict = Depends(get_current_user)):
        """Bulk upgrade every tenant the user owns or administers that is still on the legacy look."""
        ms = await db.memberships.find({"user_id": user["user_id"], "role": "admin"}, {"_id": 0, "app_id": 1}).to_list(500)
        apps = await db.apps.find({"$or": [{"owner_id": user["user_id"]}, {"app_id": {"$in": [m["app_id"] for m in ms]}}]},
                                  {"_id": 0, "app_id": 1, "name": 1, "theme": 1}).to_list(500)
        from page_guard import snapshot_site
        who = user.get("name") or user["email"]
        upgraded = []
        for a in apps:
            old = {**DEFAULT_THEME, **_clean_theme(a.get("theme"))}
            if old.get("design_v2"):
                continue
            await snapshot_site(db, a["app_id"], who, "before design upgrade")
            theme = {**old, "design_v2": True}
            if old.get("font_heading") == DEFAULT_THEME["font_heading"] and old.get("font_body") == DEFAULT_THEME["font_body"]:
                theme["font_heading"], theme["font_body"] = V2_THEME["font_heading"], V2_THEME["font_body"]
            await db.apps.update_one({"app_id": a["app_id"]}, {"$set": {"theme": theme, "updated_at": now_iso()}})
            await log_activity(a["app_id"], user["user_id"], "design.upgraded", "Upgraded to the current design standard (bulk)")
            upgraded.append({"app_id": a["app_id"], "name": a.get("name")})
        return {"upgraded": upgraded, "count": len(upgraded)}

    # ===== PAGES (multi) =====
    @api.get("/apps/{app_id}/pages")
    async def list_pages(app_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        pages = await db.pages.find({"app_id": app_id}, {"_id": 0}).to_list(50)
        pages.sort(key=lambda p: (p.get("slug") != "/", p.get("order", 0), p.get("name", "")))
        return pages

    @api.post("/apps/{app_id}/pages")
    async def create_page(app_id: str, body: PageCreateIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        slug = "/" + re.sub(r"[^a-z0-9-]+", "-", body.slug.lower().strip("/ ")).strip("-")
        if await db.pages.find_one({"app_id": app_id, "slug": slug}):
            raise HTTPException(400, "Slug already exists")
        count = await db.pages.count_documents({"app_id": app_id})
        doc = {"page_id": uid("pg"), "app_id": app_id, "name": body.name, "slug": slug, "order": count,
               "blocks": [{"id": uid("blk"), "type": "hero", "props": {"variant": "centered", "title": body.name, "subtitle": "Start editing this page.", "cta": "Learn more"},
                           "style": {"bg": "default", "align": "center", "padding": "lg"}}],
               "updated_at": now_iso()}
        await db.pages.insert_one(dict(doc))
        await log_activity(app_id, user["user_id"], "page.created", f"Page '{body.name}' created")
        from content_lock import sync_overview
        await sync_overview(db, app_id)
        return doc

    @api.patch("/apps/{app_id}/pages/{page_id}")
    async def update_page(app_id: str, page_id: str, body: PageUpdateIn, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        from page_guard import assert_can_edit_page, snapshot
        prev = await db.pages.find_one({"app_id": app_id, "page_id": page_id}, {"_id": 0})
        if not prev:
            raise HTTPException(404, "Page not found")
        grant = await assert_can_edit_page(db, doc, prev, user)
        upd = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
        if "blocks" in upd:
            from locks import blocked_block_edits
            hit = await blocked_block_edits(db, app_id, prev.get("blocks") or [], upd["blocks"])
            if hit and not grant:
                from page_guard import role_of
                if await role_of(db, doc, user) not in ("owner", "admin"):
                    raise HTTPException(423, f"{len(hit)} section(s) on this page are locked by the agency. "
                                              "Use “Request a change” on a locked section to ask them to open it.")
        if "blocks" in upd:
            upd["blocks"] = _ensure_ids(upd["blocks"])
        if "slug" in upd:
            upd["slug"] = "/" + re.sub(r"[^a-z0-9-]+", "-", upd["slug"].lower().strip("/ ")).strip("-")
        upd["updated_at"] = now_iso()
        r = await db.pages.update_one({"app_id": app_id, "page_id": page_id}, {"$set": upd})
        if not r.matched_count:
            raise HTTPException(404, "Page not found")
        if "blocks" in upd:
            await snapshot(db, app_id, prev, user.get("name") or user["email"], "save")
            if grant:
                from edit_requests import consume_grant
                await consume_grant(db, grant["grant_id"])
                await db.messages.update_one({"message_id": grant["message_id"]},
                                             {"$set": {"edit_request.state": "completed", "edit_request.completed_at": now_iso()}})
                await log_activity(app_id, user["user_id"], "edit.completed", f"Approved change saved on '{prev.get('name')}'")
            await log_activity(app_id, user["user_id"], "page.saved", f"Saved {len(upd['blocks'])} blocks")
            from content_lock import sync_overview
            await sync_overview(db, app_id)
            if hooks.get("maybe_autosync"):
                await hooks["maybe_autosync"](app_id, user["user_id"])
            if hooks.get("maybe_site_sync"):
                await hooks["maybe_site_sync"](app_id, user["user_id"])
        return await db.pages.find_one({"page_id": page_id}, {"_id": 0})

    @api.delete("/apps/{app_id}/pages/{page_id}")
    async def delete_page(app_id: str, page_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        pg = await db.pages.find_one({"app_id": app_id, "page_id": page_id})
        if not pg:
            raise HTTPException(404, "Page not found")
        if pg.get("slug") == "/":
            raise HTTPException(400, "Home page cannot be deleted")
        await db.pages.delete_one({"page_id": page_id})
        from content_lock import sync_overview
        await sync_overview(db, app_id)
        return {"ok": True}

    # ===== AI: PROMPT-TO-SITE =====
    @api.post("/apps/{app_id}/ai/generate-site")
    async def generate_site(app_id: str, body: BriefIn, user: dict = Depends(get_current_user)):
        doc = await require_ai_access(app_id, user)
        from content_lock import assert_unlocked as _au
        await _au(db, app_id, "replace the saved pages")
        from page_guard import snapshot_site
        await snapshot_site(db, app_id, user.get("name") or user["email"], "before AI site generation")
        if not EMERGENT_LLM_KEY:
            raise HTTPException(500, "LLM key missing")
        wanted = body.pages or ["Home", "About", "Pricing", "Contact"]
        system = ("You are the creative director of a premium digital agency producing dark, cinematic, high-end marketing websites. "
                  "Return ONLY valid JSON, no markdown. Shape: {\"theme\": {mode, primary, secondary, bg, surface, border, font_heading, font_body, radius}, "
                  "\"pages\": [{\"name\", \"slug\", \"blocks\": [...]}]}. " + BLOCK_SCHEMA + INDUSTRY_SECTIONS +
                  " Design rules: theme.mode is ALWAYS 'dark' with a rich dark bg (#0a0a0f or a deep navy like #070B16), surface slightly lighter, white typography, ONE accent colour chosen for the niche (dark & moody for creative studios, clean teal/blue for healthcare, bold safety-orange/amber for construction & trades, gold for hospitality, lime/pink for fitness, indigo for tech). "
                  "Home starts with navbar then a hero with variant 'cover' and a full-width niche-relevant Unsplash image; alternate style.bg between 'default' and 'muted' on every following section; include stats, team, testimonials, a video block (YouTube embed url like https://www.youtube.com/embed?listType=search&list=<niche+keywords>) and a cta block; padding lg on hero/cta, md elsewhere. "
                  "Content rules (Layer 1–3): invent a realistic business name, tagline, address, phone and email; team members with names and roles; niche-specific metrics; hero headlines that sound like a real business in that industry wrote them; services in real industry terminology; testimonials with full names, company and a specific measurable result; realistic pricing tiers; a convincing About story. Every word must be handcrafted for this niche — never generic. "
                  "Home has 9-12 blocks (navbar first, footer last); other pages 4-7 blocks. Navbar links must reference the generated page slugs. "
                  "Images: real Unsplash URLs like https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=1600&q=80 matching the industry. Omit ids.")
        prompt = f"Business brief: {body.brief}\nTenant name: {doc['name']} ({doc.get('industry','')}).\nPages to create: {', '.join(wanted)}."
        try:
            data = _parse_json(await _claude(system, prompt, f"site-{app_id}-{uid('s')}"))
        except Exception as e:
            logger.exception("generate-site failed")
            raise HTTPException(500, f"Generation failed: {str(e)[:160]}")
        pages = data.get("pages") or []
        if not pages:
            raise HTTPException(500, "AI returned no pages. Try a more specific brief.")
        theme = {**DEFAULT_THEME, **_clean_theme(doc.get("theme")), **_clean_theme(data.get("theme")), "mode": "dark", "glass": True, "grain": True, "motion": True, "cursor": True, "design_v2": True}
        from content_lock import assert_unlocked, lock_after_build, sync_overview
        await assert_unlocked(db, app_id, "replace the saved pages")
        await db.pages.delete_many({"app_id": app_id})
        out = []
        for i, pg in enumerate(pages):
            slug = "/" if i == 0 else "/" + re.sub(r"[^a-z0-9-]+", "-", str(pg.get("slug") or pg.get("name", f"page-{i}")).lower().strip("/ ")).strip("-")
            d = {"page_id": uid("pg"), "app_id": app_id, "name": pg.get("name") or slug.strip("/").title() or "Home", "slug": slug,
                 "order": i, "blocks": _ensure_ids(pg.get("blocks", [])), "updated_at": now_iso()}
            await db.pages.insert_one(dict(d))
            out.append(d)
        await db.apps.update_one({"app_id": app_id}, {"$set": {"theme": theme, "site_brief": body.brief, "updated_at": now_iso()}})
        await lock_after_build(db, app_id)
        await sync_overview(db, app_id)
        await log_activity(app_id, user["user_id"], "ai.site", f"Generated {len(out)}-page site from brief")
        return {"theme": theme, "pages": out}

    # ===== AI: PROMPT-TO-APP BLUEPRINT =====
    @api.get("/apps/{app_id}/blueprint")
    async def get_blueprint(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        return doc.get("app_spec") or None

    @api.post("/apps/{app_id}/ai/generate-app")
    async def generate_app(app_id: str, body: BriefIn, user: dict = Depends(get_current_user)):
        doc = await require_ai_access(app_id, user)
        if not EMERGENT_LLM_KEY:
            raise HTTPException(500, "LLM key missing")
        system = ("You are a principal product architect (Lovable-style). Given an app idea, return ONLY valid JSON (no markdown) with shape: "
                  "{\"name\", \"tagline\", \"screens\": [{\"name\", \"route\", \"description\", \"nav\": bool, "
                  "\"components\": [{\"type\": \"navbar|stats|table|form|list|cards|chart|detail|kanban|calendar|chat|settings|hero|auth\", \"label\", \"fields\": [string], \"model\": string}]}], "
                  "\"models\": [{\"name\", \"fields\": [{\"name\", \"type\": \"string|number|boolean|date|email|text|enum|ref\", \"required\": bool}]}], "
                  "\"api\": [{\"method\", \"path\", \"description\"}], \"roles\": [string], \"integrations\": [string]}. "
                  "Design 5-8 screens including an auth screen and a dashboard, 3-6 data models, RESTful api paths prefixed with /api. Be specific and production-minded.")
        prompt = f"App idea: {body.brief}\nTenant: {doc['name']} ({doc.get('industry','')})."
        try:
            spec = _parse_json(await _claude(system, prompt, f"app-{app_id}-{uid('a')}"))
        except Exception as e:
            logger.exception("generate-app failed")
            raise HTTPException(500, f"Generation failed: {str(e)[:160]}")
        spec["generated_at"] = now_iso()
        spec["brief"] = body.brief
        await db.apps.update_one({"app_id": app_id}, {"$set": {"app_spec": spec, "updated_at": now_iso()}})
        await log_activity(app_id, user["user_id"], "ai.app", f"Generated app blueprint: {spec.get('name', '')}")
        return spec

    # ===== AI: APP MODE CHAT (refine blueprint conversationally) =====
    class RefineIn(BaseModel):
        message: str
        target: Optional[Dict[str, Any]] = None  # {screen, component}

    @api.get("/apps/{app_id}/ai/app-chat")
    async def app_chat_history(app_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        return await db.app_chats.find({"app_id": app_id}, {"_id": 0}).sort("created_at", 1).limit(60).to_list(60)

    @api.post("/apps/{app_id}/ai/refine-app")
    async def refine_app(app_id: str, body: RefineIn, user: dict = Depends(get_current_user)):
        doc = await require_ai_access(app_id, user)
        spec = doc.get("app_spec")
        if not spec:
            raise HTTPException(400, "Generate a blueprint first")
        target = f"\nTARGET ELEMENT: screen '{body.target.get('screen')}', component '{body.target.get('component')}'. Apply the change primarily there." if body.target else ""
        system = ("You are a Lovable-style app architect. You receive the current app blueprint JSON and a change request. Return ONLY JSON: "
                  "{\"spec\": <full updated blueprint with the same shape (name, tagline, screens[], models[], api[], roles[], integrations[])>, \"summary\": \"one or two sentences describing what changed\"}. "
                  "Keep everything not mentioned unchanged. Components use types navbar|stats|table|form|list|cards|chart|detail|kanban|calendar|chat|settings|hero|auth with fields[] and model.")
        prompt = f"CURRENT BLUEPRINT:\n{json.dumps({k: v for k, v in spec.items() if k not in ('generated_at', 'brief')})[:14000]}\n\nCHANGE REQUEST: {body.message}{target}"
        await db.app_chats.insert_one({"app_id": app_id, "role": "user", "content": body.message, "target": body.target, "created_at": now_iso()})
        try:
            data = _parse_json(await _claude(system, prompt, f"refine-{app_id}-{uid('r')}"))
            new_spec = data.get("spec") or data
            if not isinstance(new_spec, dict) or "screens" not in new_spec:
                raise ValueError("bad spec")
        except Exception as e:
            raise HTTPException(500, f"Refinement failed: {str(e)[:140]}")
        new_spec.update({"generated_at": now_iso(), "brief": spec.get("brief")})
        summary = data.get("summary") if isinstance(data, dict) else "Updated the blueprint."
        await db.apps.update_one({"app_id": app_id}, {"$set": {"app_spec": new_spec}})
        await db.app_chats.insert_one({"app_id": app_id, "role": "assistant", "content": summary, "created_at": now_iso()})
        await log_activity(app_id, user["user_id"], "ai.app.refine", f"App refined: {body.message[:70]}")
        return {"spec": new_spec, "summary": summary}

    # ===== PUBLIC SITE (multi-page) =====
    @api.get("/public/site/{token}")
    async def public_site(token: str):
        if token == "studio":
            return {"app": {"name": "Lois-Tech", "industry": "Agency platform", "color": "#10B981"}, "theme": DEFAULT_THEME, "pages": []}
        doc = await db.apps.find_one({"preview_token": token, "preview_enabled": True}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Preview link is invalid or has been revoked")
        pages = await db.pages.find({"app_id": doc["app_id"]}, {"_id": 0}).to_list(50)
        pages.sort(key=lambda p: (p.get("slug") != "/", p.get("order", 0)))
        cols = await hooks["public_collections"](doc["app_id"]) if hooks.get("public_collections") else []
        # Per-tenant Site Mode always wins over the template-derived motion profile, so an
        # applied hero / accent / speed / intensity shows up in Preview, Live and Demo alike.
        sm = doc.get("site_mode") or {}
        prof = dict(doc.get("motion_profile") or {})
        if sm.get("hero"):
            prof["hero"] = sm["hero"]
        if sm.get("accent"):
            prof["accent"] = sm["accent"]
        prof["speed"] = float(sm.get("motion_speed") or prof.get("speed") or 1.0)
        prof["intensity"] = float(sm.get("motion_intensity") or prof.get("intensity") or 1.0)
        from industry_vitals import spec_for
        _vk = prof.get("template_key") or doc.get("site_niche") or ""
        vitals = {**spec_for(_vk, doc.get("industry") or ""), **(doc.get("vitals") or {})}
        # Address: the tenant's own field wins, then its contact/footer copy, then the template sample.
        _addr = (sm.get("address") or (doc.get("brand_profile") or {}).get("address") or "").strip()
        if not _addr:
            for _p in pages:
                for _b in _p.get("blocks") or []:
                    _a = (_b.get("props") or {}).get("address")
                    if isinstance(_a, str) and _a.strip() and len(_a) < 90:
                        _addr = _a.strip()
                        break
                if _addr:
                    break
        if not _addr:
            from site_content import NICHES as _NICHES
            _addr = (_NICHES.get(_vk) or {}).get("address") or ""
        from urllib.parse import quote_plus
        return {"app": {**{k: doc.get(k) for k in ("name", "industry", "description", "color", "status", "custom_domain")},
                        "app_id": doc["app_id"],
                        "site_mode": sm,
                        "vitals": vitals,
                        "address": _addr,
                        "map_url": (sm.get("map_url") or "").strip() or (
                            f"https://www.google.com/maps/search/?api=1&query={quote_plus(_addr)}" if _addr else ""),
                        "motion_profile": prof},
                "theme": {**DEFAULT_THEME, **(doc.get("theme") or {})}, "pages": pages, "collections": cols, "chat_enabled": True,
                "webapp": {"converted": bool((doc.get("webapp") or {}).get("converted")),
                           "signup_mode": (doc.get("webapp") or {}).get("signup_mode", "open")}}

    # ===== PUBLIC AI CHATBOT (text + voice) =====
    STUDIO_CONTEXT = ("Lois-Tech is an agency platform to build client websites (Framer-style drag-and-drop + AI prompt-to-site), "
                      "generate app blueprints and starter code (Lovable-style), create AI images/video/voice, bill clients via Stripe "
                      "(Starter $29, Pro $99, Scale $299 per month), connect custom domains and share live preview links.")

    @api.post("/public/chat/{token}")
    async def public_chat(token: str, body: ChatIn):
        if not EMERGENT_LLM_KEY:
            raise HTTPException(500, "LLM key missing")
        if token == "studio":
            name, context = "Lois-Tech", STUDIO_CONTEXT
        else:
            doc = await db.apps.find_one({"preview_token": token, "preview_enabled": True}, {"_id": 0})
            if not doc:
                raise HTTPException(404, "Chat unavailable")
            pages = await db.pages.find({"app_id": doc["app_id"]}, {"_id": 0}).to_list(20)
            name = doc["name"]
            context = f"{doc.get('description','')}\n" + "\n".join(_blocks_text(p.get("blocks", [])) for p in pages)
        history = await db.chat_messages.find({"session_id": body.session_id}, {"_id": 0}).sort("created_at", 1).limit(20).to_list(20)
        system = (f"You are the friendly live assistant for {name}. Answer customer questions using ONLY this website content:\n{context[:7000]}\n"
                  "Be concise (max 3 sentences), warm and helpful. If unsure, offer to connect them with the team via the contact details. Reply in the user's language.")
        transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
        prompt = (f"Conversation so far:\n{transcript}\n" if transcript else "") + f"USER: {body.message.strip()[:1500]}"
        try:
            reply = (await _claude(system, prompt, f"chat-{body.session_id}")).strip()
        except Exception as e:
            raise HTTPException(500, f"Assistant unavailable: {str(e)[:120]}")
        ts = now_iso()
        if token != "studio" and hooks.get("upsert_chat_lead"):
            await hooks["upsert_chat_lead"](doc["app_id"], body.session_id, body.message.strip()[:1500], reply)
        await db.chat_messages.insert_many([
            {"session_id": body.session_id, "token": token, "role": "user", "content": body.message.strip()[:1500], "created_at": ts},
            {"session_id": body.session_id, "token": token, "role": "assistant", "content": reply, "created_at": now_iso()},
        ])
        return {"reply": reply, "session_id": body.session_id}

    @api.get("/public/chat/{token}/history/{session_id}")
    async def chat_history(token: str, session_id: str):
        return await db.chat_messages.find({"session_id": session_id, "token": token}, {"_id": 0}).sort("created_at", 1).limit(40).to_list(40)

    def _clean_tts(text: str) -> str:
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"[*_#>~|`]", "", text)
        return re.sub(r"\s+", " ", text).strip()[:4000]

    @api.post("/public/tts")
    async def public_tts(body: TtsIn):
        if not EMERGENT_LLM_KEY:
            raise HTTPException(500, "LLM key missing")
        text = _clean_tts(body.text)
        if not text:
            raise HTTPException(400, "Empty text")
        voice = body.voice if body.voice in ("alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer") else "coral"
        key = hashlib.sha256(f"{text}|{voice}|1.0|tts-1|mp3".encode()).hexdigest()[:40]
        eleven = await db.settings.find_one({"key": "elevenlabs_api_key"}, {"_id": 0})
        eleven_key = (eleven or {}).get("value") or os.environ.get("ELEVENLABS_API_KEY", "")
        if eleven_key:
            key = "el" + key[2:]
        if not await db.tts_cache.find_one({"key": key}):
            try:
                if eleven_key:
                    from elevenlabs.client import ElevenLabs
                    def _el():
                        return b"".join(ElevenLabs(api_key=eleven_key).text_to_speech.convert(text=text, voice_id="21m00Tcm4TlvDq8ikWAM", model_id="eleven_multilingual_v2"))
                    audio = await asyncio.to_thread(_el)
                else:
                    audio = await generate_speech(text, voice=voice)
            except Exception as e:
                raise HTTPException(500, f"TTS failed: {str(e)[:120]}")
            await db.tts_cache.insert_one({"key": key, "audio_b64": base64.b64encode(audio).decode(), "created_at": now_iso()})
        return {"audio_url": f"/api/public/tts/{key}.mp3"}

    @api.get("/public/tts/{key}.mp3")
    async def get_tts(key: str):
        doc = await db.tts_cache.find_one({"key": key}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Not found")
        return Response(content=base64.b64decode(doc["audio_b64"]), media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=31536000"})
