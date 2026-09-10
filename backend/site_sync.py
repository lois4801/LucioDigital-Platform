"""Site → App AI sync: reads a client's live Site Mode content and builds/updates its App Mode blueprint."""
import os
import json
import uuid
import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException, Depends
from pydantic import BaseModel

from llm_provider import get_chat, UserMessage, llm_available
from studio import _parse_json, _blocks_text

logger = logging.getLogger(__name__)
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
require_ai_access = None


def _now():
    return datetime.now(timezone.utc).isoformat()


def _uid(p):
    return f"{p}_{uuid.uuid4().hex[:12]}"


SYSTEM = (
    "You are a principal product architect. You are given everything about a live marketing WEBSITE (brand, industry, page structure, "
    "real copy, services, pricing, contact details, theme colours) and you must design the companion SOFTWARE APP for that same business. "
    "Return ONLY valid JSON (no markdown) with shape: "
    "{\"name\", \"tagline\", \"screens\": [{\"name\", \"route\", \"description\", \"nav\": bool, "
    "\"components\": [{\"type\": \"navbar|stats|table|form|list|cards|chart|detail|kanban|calendar|chat|settings|hero|auth\", \"label\", \"fields\": [string], \"model\": string}]}], "
    "\"models\": [{\"name\", \"fields\": [{\"name\", \"type\": \"string|number|boolean|date|email|text|enum|ref\", \"required\": bool}]}], "
    "\"api\": [{\"method\", \"path\", \"description\"}], \"roles\": [string], \"integrations\": [string], \"summary\": \"one or two sentences on what you built or changed\"}. "
    "Rules: the app name and tagline must match the real business name and voice from the website. Every service, plan, location and form on the "
    "website must map to a screen, model or field (e.g. a services list → a jobs/bookings model; pricing plans → a plans/subscriptions model; a "
    "contact form → a leads model with the same fields; a team section → staff/roles). Include an auth screen and an operational dashboard whose "
    "stats mirror the metrics the website advertises. Use the website's own terminology, never generic placeholders. 5-9 screens, 4-7 models, "
    "RESTful /api paths."
)


async def _claude(system: str, prompt: str, session: str, app_id: str = None, feature: str = "site_generation") -> str:
    from ai_models import resolve_for
    provider, model = await resolve_for(app_id, feature)
    chat = get_chat(provider, model, system, session)
    reply = await chat.send_message(UserMessage(text=prompt))
    return reply if isinstance(reply, str) else str(reply)


async def site_snapshot(db, app_doc: dict) -> dict:
    """Everything the AI needs to know about the client's site."""
    app_id = app_doc["app_id"]
    pages = await db.pages.find({"app_id": app_id}, {"_id": 0}).to_list(50)
    pages.sort(key=lambda p: (p.get("slug") != "/", p.get("order", 0)))
    cols = await db.collections.find({"app_id": app_id}, {"_id": 0, "name": 1, "slug": 1}).to_list(20)
    theme = app_doc.get("theme") or {}
    prof = app_doc.get("brand_profile") or {}
    page_text = []
    for pg in pages:
        blocks = pg.get("blocks") or []
        page_text.append(f"## PAGE {pg.get('name')} ({pg.get('slug')})\nsections: {', '.join(b.get('type', '') for b in blocks)}\n{_blocks_text(blocks)}")
    return {
        "business": app_doc.get("name"),
        "industry": app_doc.get("industry"),
        "niche": app_doc.get("site_niche"),
        "description": app_doc.get("description"),
        "contact": {k: prof.get(k) for k in ("email", "phone", "address") if prof.get(k)},
        "theme": {k: theme.get(k) for k in ("primary", "secondary", "mode", "font_heading") if theme.get(k)},
        "collections": [c.get("name") for c in cols],
        "pages": [{"name": p.get("name"), "slug": p.get("slug"), "blocks": len(p.get("blocks") or [])} for p in pages],
        "content": "\n\n".join(page_text)[:16000],
    }


def _fingerprint(snap: dict) -> str:
    return hashlib.sha256(json.dumps(snap, sort_keys=True, default=str).encode()).hexdigest()[:32]


async def sync_app_from_site(db, app_doc: dict, user_id: str, log_activity, mode: str = "merge") -> dict:
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "LLM key missing")
    app_id = app_doc["app_id"]
    snap = await site_snapshot(db, app_doc)
    if not (snap.get("content") or "").strip():
        raise HTTPException(400, "This site has no content yet — build or import the website first.")
    existing = app_doc.get("app_spec")
    prompt = f"WEBSITE DATA:\n{json.dumps(snap, default=str)[:17000]}"
    if mode == "merge" and existing:
        prompt += (f"\n\nEXISTING APP BLUEPRINT (preserve every screen, model and field the owner added by hand unless the website clearly contradicts it; "
                   f"add and update what the website now needs):\n{json.dumps({k: v for k, v in existing.items() if k not in ('generated_at', 'brief', 'summary')})[:10000]}")
    else:
        prompt += "\n\nThere is no existing blueprint — design the app from scratch off this website."
    try:
        data = _parse_json(await _claude(SYSTEM, prompt, f"sitesync-{app_id}-{_uid('s')}"))
    except Exception as e:
        logger.exception("site->app sync failed")
        raise HTTPException(500, f"Sync failed: {str(e)[:160]}")
    spec = data.get("spec") if isinstance(data, dict) and "screens" not in data else data
    if not isinstance(spec, dict) or not spec.get("screens"):
        raise HTTPException(500, "AI returned an unusable blueprint. Try again.")
    summary = spec.pop("summary", None) or "Rebuilt the app blueprint from the website content."
    spec.update({"generated_at": _now(), "brief": (existing or {}).get("brief") or f"Auto-built from the {snap['business']} website"})
    sync = {"enabled": bool((app_doc.get("app_sync") or {}).get("enabled")), "last_sync": _now(), "last_summary": summary,
            "fingerprint": _fingerprint(snap), "mode": mode}
    await db.apps.update_one({"app_id": app_id}, {"$set": {"app_spec": spec, "app_sync": sync, "updated_at": _now()}})
    await db.app_chats.insert_one({"app_id": app_id, "role": "assistant", "content": f"Synced from Site Mode — {summary}", "created_at": _now()})
    await log_activity(app_id, user_id, "app.sync", f"App blueprint synced from site ({len(spec.get('screens', []))} screens)")
    return {"spec": spec, "summary": summary, "sync": sync}


class SyncToggleIn(BaseModel):
    enabled: bool


class SyncRunIn(BaseModel):
    mode: str = "merge"


_running: set = set()


def register(api, db, get_current_user, get_user_app, log_activity):
    @api.get("/apps/{app_id}/site-sync")
    async def get_sync(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        s = doc.get("app_sync") or {}
        return {"enabled": bool(s.get("enabled")), "last_sync": s.get("last_sync"), "last_summary": s.get("last_summary"), "has_spec": bool(doc.get("app_spec"))}

    @api.post("/apps/{app_id}/site-sync")
    async def set_sync(app_id: str, body: SyncToggleIn, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        s = {**(doc.get("app_sync") or {}), "enabled": body.enabled}
        await db.apps.update_one({"app_id": app_id}, {"$set": {"app_sync": s}})
        await log_activity(app_id, user["user_id"], "app.sync.toggle", f"Auto app-sync {'enabled' if body.enabled else 'disabled'}")
        return {"enabled": body.enabled}

    @api.post("/apps/{app_id}/ai/app-from-site")
    async def app_from_site(app_id: str, body: SyncRunIn, user: dict = Depends(get_current_user)):
        """Starts a background sync — scrape+LLM can exceed the 60s ingress cap, so the client polls."""
        doc = await require_ai_access(app_id, user)
        mode = body.mode if body.mode in ("merge", "overwrite") else "merge"
        job_id = _uid("sjob")
        await db.sync_jobs.insert_one({"job_id": job_id, "app_id": app_id, "status": "running", "mode": mode, "created_at": _now()})

        async def run():
            try:
                res = await sync_app_from_site(db, doc, user["user_id"], log_activity, mode)
                await db.sync_jobs.update_one({"job_id": job_id}, {"$set": {"status": "done", "result": res, "finished_at": _now()}})
            except HTTPException as e:
                await db.sync_jobs.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e.detail), "finished_at": _now()}})
            except Exception as e:
                logger.exception("site->app sync failed")
                await db.sync_jobs.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e)[:180], "finished_at": _now()}})
        asyncio.create_task(run())
        return {"job_id": job_id, "status": "running"}

    @api.get("/apps/{app_id}/ai/app-sync-job/{job_id}")
    async def app_sync_job(app_id: str, job_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        job = await db.sync_jobs.find_one({"job_id": job_id, "app_id": app_id}, {"_id": 0})
        if not job:
            raise HTTPException(404, "Sync job not found")
        return job

    async def maybe_site_sync(app_id: str, user_id: str):
        """Called after a Site Mode page save — rebuilds the app in the background when auto-sync is on."""
        doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0})
        if not doc or not (doc.get("app_sync") or {}).get("enabled") or app_id in _running:
            return
        snap = await site_snapshot(db, doc)
        if _fingerprint(snap) == (doc.get("app_sync") or {}).get("fingerprint"):
            return
        _running.add(app_id)

        async def run():
            try:
                await sync_app_from_site(db, doc, user_id, log_activity, "merge")
            except Exception:
                logger.exception("auto site->app sync failed")
            finally:
                _running.discard(app_id)
        asyncio.create_task(run())

    return {"maybe_site_sync": maybe_site_sync, "sync_app_from_site": sync_app_from_site}
