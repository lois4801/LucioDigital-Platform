"""AI model routing: a platform default that each tenant can override, across every LLM call.
Text models: Claude, OpenAI and Gemini (3 Flash / 3.1 Pro). Images: Gemini Nano Banana."""
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Tuple

from fastapi import HTTPException, Depends
from pydantic import BaseModel

logger = logging.getLogger("agency.ai_models")

TEXT_MODELS = {
    "claude-sonnet-5": ("anthropic", "Claude Sonnet 5 — balanced default"),
    "claude-haiku-4-5-20251001": ("anthropic", "Claude Haiku — fastest, cheapest"),
    "gemini-3-flash-preview": ("gemini", "Gemini 3 Flash — fast and cheap"),
    "gemini-3.1-pro-preview": ("gemini", "Gemini 3.1 Pro — strongest reasoning"),
    "gpt-5.4": ("openai", "GPT-5.4 — OpenAI flagship"),
    "gpt-5.4-mini": ("openai", "GPT-5.4 mini — fast"),
}
FEATURES = ("site_generation", "chat_widget", "lead_scoring", "copy_rewrite", "seo")
DEFAULT_MODEL = "claude-sonnet-5"
FEATURE_DEFAULTS = {"site_generation": "gemini-3.1-pro-preview", "chat_widget": "gemini-3-flash-preview",
                    "lead_scoring": "gemini-3-flash-preview", "copy_rewrite": "claude-sonnet-5",
                    "seo": "gemini-3-flash-preview"}

_db = None


class ModelIn(BaseModel):
    model: Optional[str] = None
    features: Optional[dict] = None


def _now():
    return datetime.now(timezone.utc).isoformat()


async def resolve_model(db, app_id: Optional[str], feature: str = "") -> Tuple[str, str]:
    """Tenant override → platform default → built-in default. Returns (provider, model)."""
    try:
        plat = await db.platform_settings.find_one({"_id": "ai"}) or {}
        chosen = None
        if app_id:
            app_doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0, "ai_model": 1}) or {}
            ai = app_doc.get("ai_model") or {}
            chosen = (ai.get("features") or {}).get(feature) or ai.get("model")
        if not chosen:
            chosen = (plat.get("features") or {}).get(feature) or plat.get("model")
        if not chosen:
            chosen = FEATURE_DEFAULTS.get(feature, DEFAULT_MODEL)
        if chosen not in TEXT_MODELS:
            chosen = DEFAULT_MODEL
        return TEXT_MODELS[chosen][0], chosen
    except Exception:
        logger.exception("model resolve failed, using default")
        return TEXT_MODELS[DEFAULT_MODEL][0], DEFAULT_MODEL


async def resolve_for(app_id: Optional[str], feature: str = "") -> Tuple[str, str]:
    """Same as resolve_model but uses the db handle captured at registration."""
    if _db is None:
        return TEXT_MODELS[FEATURE_DEFAULTS.get(feature, DEFAULT_MODEL)][0], FEATURE_DEFAULTS.get(feature, DEFAULT_MODEL)
    return await resolve_model(_db, app_id, feature)


def resolve_sync(app_id: Optional[str] = None, feature: str = "") -> Tuple[str, str]:
    """Sync helper for call sites that cannot await (falls back to the built-in default)."""
    return TEXT_MODELS[FEATURE_DEFAULTS.get(feature, DEFAULT_MODEL)][0], FEATURE_DEFAULTS.get(feature, DEFAULT_MODEL)


async def run_text(app_id: Optional[str], feature: str, system: str, prompt: str, session_id: str) -> Tuple[str, str]:
    """One-shot text generation on whichever model this tenant/feature resolves to."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
    provider, model = await resolve_for(app_id, feature)
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=session_id,
                   system_message=system).with_model(provider, model)
    reply = ""
    async for ev in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(ev, TextDelta):
            reply += ev.content
        elif isinstance(ev, StreamDone):
            break
    return reply.strip(), model


async def build_lead_summary(db, app_id: str, days: int = 7) -> dict:
    """AI paragraph over the last N days of leads: volume, sources, hottest leads, suggested actions."""
    from datetime import timedelta
    app_doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0, "name": 1, "industry": 1}) or {}
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    msgs = await db.messages.find({"app_id": app_id, "created_at": {"$gte": since},
                                   "kind": {"$ne": "edit_request"}, "lane": {"$ne": "test"}}, {"_id": 0}).sort("created_at", -1).to_list(80)
    sources: dict = {}
    for m in msgs:
        key = m.get("source") or m.get("channel") or ("chat" if m.get("session_id") else "form")
        sources[key] = sources.get(key, 0) + 1
    hot = [m for m in msgs if m.get("hot")]
    counts = {"leads": len(msgs), "hot": len(hot), "days": days,
              "sources": sources, "unread": sum(1 for m in msgs if m.get("status") == "unread")}
    if not msgs:
        return {"summary": f"No new leads in the last {days} days. Nothing to chase — consider a campaign or a fresh offer on the site.",
                "counts": counts, "model": "", "generated_at": _now()}
    lines = []
    for m in msgs[:30]:
        lines.append(f"- {m.get('from_name') or 'Anonymous'} <{m.get('from_email') or '-'}> "
                     f"score={m.get('score')} hot={bool(m.get('hot'))} status={m.get('status')} "
                     f"replied={bool(m.get('replies'))}: {(m.get('body') or '')[:220]}")
    system = ("You are a sales assistant summarising a week of inbound leads for a business owner. "
              "Reply in plain text, no markdown, no headings: one short paragraph (max 90 words) covering volume, "
              "where the leads came from and the overall picture, then a blank line, then 2-4 lines starting with "
              "'- ' naming the hottest leads and the single next action for each. Be concrete and use their names.")
    prompt = (f"Business: {app_doc.get('name')} ({app_doc.get('industry') or 'general'}). "
              f"Window: last {days} days. Total {len(msgs)} leads, {len(hot)} marked hot. "
              f"Sources: {sources}.\n\nLeads:\n" + "\n".join(lines))
    try:
        text, model = await run_text(app_id, "lead_scoring", system, prompt, f"leadsum-{app_id}")
    except Exception:
        logger.exception("lead summary generation failed for %s", app_id)
        raise
    return {"summary": text[:2500], "counts": counts, "model": model, "generated_at": _now()}


def register(api, db, get_current_user, get_user_app, log_activity):
    global _db
    _db = db

    def _clean(body: ModelIn) -> dict:
        out = {}
        if body.model:
            if body.model not in TEXT_MODELS:
                raise HTTPException(400, f"Unknown model '{body.model}'")
            out["model"] = body.model
        if body.features is not None:
            feats = {}
            for k, v in body.features.items():
                if k not in FEATURES:
                    raise HTTPException(400, f"Unknown feature '{k}'")
                if v and v not in TEXT_MODELS:
                    raise HTTPException(400, f"Unknown model '{v}'")
                if v:
                    feats[k] = v
            out["features"] = feats
        return out

    @api.get("/ai/models")
    async def list_models(user: dict = Depends(get_current_user)):
        plat = await db.platform_settings.find_one({"_id": "ai"}) or {}
        return {"models": [{"id": k, "provider": v[0], "label": v[1]} for k, v in TEXT_MODELS.items()],
                "features": list(FEATURES), "feature_defaults": FEATURE_DEFAULTS,
                "platform": {"model": plat.get("model") or DEFAULT_MODEL, "features": plat.get("features") or {}},
                "image_model": "gemini-2.5-flash-image-preview"}

    @api.patch("/ai/models")
    async def set_platform_model(body: ModelIn, user: dict = Depends(get_current_user)):
        admin_email = (os.environ.get("ADMIN_EMAIL") or "").lower().strip()
        if not user.get("is_admin") and (user.get("email") or "").lower().strip() != admin_email:
            raise HTTPException(403, "Only a platform admin can change the default model")
        upd = _clean(body)
        ops = {"$set": {**upd, "updated_at": _now()}}
        if not upd:
            ops["$unset"] = {"model": "", "features": ""}
        await db.platform_settings.update_one({"_id": "ai"}, ops, upsert=True)
        plat = await db.platform_settings.find_one({"_id": "ai"}, {"_id": 0})
        return plat or {}

    @api.get("/apps/{app_id}/ai-model")
    async def get_tenant_model(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        eff = {}
        for f in FEATURES:
            provider, model = await resolve_model(db, app_id, f)
            eff[f] = {"provider": provider, "model": model}
        return {"override": doc.get("ai_model") or {}, "effective": eff}

    @api.patch("/apps/{app_id}/ai-model")
    async def set_tenant_model(app_id: str, body: ModelIn, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        from page_guard import role_of
        if await role_of(db, doc, user) not in ("owner", "admin"):
            raise HTTPException(403, "Only the agency owner or an admin can change the AI model")
        upd = _clean(body)
        await db.apps.update_one({"app_id": app_id}, {"$set": {"ai_model": upd}})
        await log_activity(app_id, user["user_id"], "ai.model", f"AI model set to {upd.get('model') or 'platform default'}")
        return upd

    @api.get("/apps/{app_id}/ai/lead-summary")
    async def get_lead_summary(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        return doc.get("ai_lead_summary") or {}

    @api.post("/apps/{app_id}/ai/lead-summary")
    async def make_lead_summary(app_id: str, days: int = 7, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        days = max(1, min(90, days))
        try:
            res = await build_lead_summary(db, app_id, days)
        except Exception as e:
            raise HTTPException(500, f"Summary failed: {str(e)[:140]}")
        await db.apps.update_one({"app_id": app_id}, {"$set": {"ai_lead_summary": res}})
        await log_activity(app_id, user["user_id"], "ai.lead_summary",
                           f"Weekly lead summary written for {res['counts']['leads']} lead(s)")
        return res

    @api.post("/apps/{app_id}/ai/seo")
    async def write_seo(app_id: str, user: dict = Depends(get_current_user)):
        """Gemini writes SEO title + meta description for every page, from its real content."""
        doc = await get_user_app(app_id, user)
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        provider, model = await resolve_model(db, app_id, "seo")
        pages = await db.pages.find({"app_id": app_id}, {"_id": 0, "page_id": 1, "name": 1, "slug": 1, "blocks": 1}).to_list(60)
        out = []
        for pg in pages:
            text = " ".join(str(v)[:160] for b in (pg.get("blocks") or [])[:6]
                            for v in (b.get("props") or {}).values() if isinstance(v, str))[:1500]
            chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"seo-{app_id}-{pg['page_id']}",
                           system_message=("You write SEO metadata. Reply with exactly two lines: "
                                           "TITLE: <max 60 chars>\nDESCRIPTION: <max 155 chars>. No other text.")
                           ).with_model(provider, model)
            try:
                reply = ""
                async for ev in chat.stream_message(UserMessage(
                        text=f"Business: {doc.get('name')} ({doc.get('industry')}). Page: {pg.get('name')} {pg.get('slug')}.\n\n{text}")):
                    from emergentintegrations.llm.chat import TextDelta, StreamDone
                    if isinstance(ev, TextDelta):
                        reply += ev.content
                    elif isinstance(ev, StreamDone):
                        break
            except Exception:
                logger.exception("seo generation failed for %s", pg["page_id"])
                continue
            title = next((l.split(":", 1)[1].strip() for l in reply.splitlines() if l.upper().startswith("TITLE")), "")[:70]
            desc = next((l.split(":", 1)[1].strip() for l in reply.splitlines() if l.upper().startswith("DESCRIPTION")), "")[:170]
            if title or desc:
                await db.pages.update_one({"app_id": app_id, "page_id": pg["page_id"]},
                                          {"$set": {"seo": {"title": title, "description": desc, "model": model, "at": _now()}}})
                out.append({"page_id": pg["page_id"], "name": pg.get("name"), "title": title, "description": desc})
        await log_activity(app_id, user["user_id"], "ai.seo", f"SEO metadata written for {len(out)} page(s) with {model}")
        return {"model": model, "provider": provider, "pages": out}
