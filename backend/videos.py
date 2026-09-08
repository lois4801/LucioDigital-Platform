"""Video engine: free stock video sourcing (Pexels/Pixabay), AI video generation (fal.ai via the
Emergent Universal Key), and auto-placement of videos onto the tenant's site."""
import os
import re
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, List
from urllib.parse import urlparse

import httpx
import requests
from fastapi import HTTPException, Depends
from pydantic import BaseModel

from storage import put_object
from files_lib import usage_for, APP_NAME

logger = logging.getLogger(__name__)
require_ai_access = None

PEXELS_SEARCH = "https://api.pexels.com/videos/search"
PIXABAY_SEARCH = "https://pixabay.com/api/videos/"
MAX_VIDEO_BYTES = int(os.environ.get("MAX_VIDEO_BYTES", str(60 * 1024 * 1024)))
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
FAL_MODELS = {
    "veo3.1": {"endpoint": "fal-ai/veo3.1", "label": "Google Veo 3.1 (cinematic, with audio)",
               "defaults": {"duration": "8s", "aspect_ratio": "16:9", "resolution": "720p", "generate_audio": True}},
    "kling-o3-pro": {"endpoint": "fal-ai/kling-video/o3/pro/text-to-video", "label": "Kling O3 Pro (realistic motion)",
                     "defaults": {"duration": "5", "aspect_ratio": "16:9", "generate_audio": False}},
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _uid(p):
    return f"{p}_{uuid.uuid4().hex[:12]}"


def _keys():
    return os.environ.get("PEXELS_API_KEY", "").strip(), os.environ.get("PIXABAY_API_KEY", "").strip()


def _pick_file(files: List[dict]) -> Optional[dict]:
    usable = [f for f in files if f.get("url")]
    if not usable:
        return None
    hd = [f for f in usable if (f.get("width") or 0) >= 1280 and (f.get("height") or 0) >= 720 and (f.get("size") or 0) <= MAX_VIDEO_BYTES]
    pool = hd or [f for f in usable if (f.get("size") or 0) <= MAX_VIDEO_BYTES] or usable
    return max(pool, key=lambda f: ((f.get("width") or 0) * (f.get("height") or 0)))


async def search_stock(query: str, per_page: int = 8) -> List[dict]:
    pexels_key, pixabay_key = _keys()
    if not pexels_key and not pixabay_key:
        raise HTTPException(400, "Add a PEXELS_API_KEY or PIXABAY_API_KEY to enable free stock video sourcing")
    out = []
    async with httpx.AsyncClient(timeout=25.0) as client:
        if pexels_key:
            try:
                r = await client.get(PEXELS_SEARCH, headers={"Authorization": pexels_key},
                                     params={"query": query, "per_page": min(per_page, 20), "orientation": "landscape"})
                if r.status_code == 200:
                    for v in r.json().get("videos", []):
                        files = [{"url": f.get("link"), "width": f.get("width"), "height": f.get("height"), "size": f.get("file_size")}
                                 for f in v.get("video_files", []) if f.get("link") and (f.get("file_type") or "").endswith("mp4")]
                        best = _pick_file(files)
                        if best:
                            out.append({"provider": "pexels", "provider_id": str(v["id"]), "title": (v.get("url") or "").rstrip("/").rsplit("/", 1)[-1].replace("-", " "),
                                        "source_url": v.get("url"), "thumb": v.get("image"), "duration": v.get("duration"),
                                        "download_url": best["url"], "contributor": (v.get("user") or {}).get("name")})
                else:
                    logger.warning("pexels search %s: %s", r.status_code, r.text[:120])
            except Exception:
                logger.exception("pexels search failed")
        if pixabay_key:
            try:
                r = await client.get(PIXABAY_SEARCH, params={"key": pixabay_key, "q": query, "per_page": min(per_page, 20), "safesearch": "true"})
                if r.status_code == 200:
                    for v in r.json().get("hits", []):
                        files = [{**(v.get("videos", {}).get(n) or {}), "quality": n} for n in ("large", "medium", "small", "tiny")]
                        best = _pick_file([f for f in files if f.get("url")])
                        if best:
                            out.append({"provider": "pixabay", "provider_id": str(v["id"]), "title": (v.get("tags") or "")[:80],
                                        "source_url": v.get("pageURL"), "thumb": f"https://i.vimeocdn.com/video/{v.get('picture_id')}_640x360.jpg" if v.get("picture_id") else None,
                                        "duration": v.get("duration"), "download_url": best["url"], "contributor": v.get("user")})
                else:
                    logger.warning("pixabay search %s: %s", r.status_code, r.text[:120])
            except Exception:
                logger.exception("pixabay search failed")
    return out


async def store_video(db, app_id: str, url: str, quota_mb: int, name: str, meta: dict) -> dict:
    usage = await usage_for(db, app_id, quota_mb)
    budget = usage["quota_bytes"] - usage["used_bytes"]
    chunks, total = [], 0
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=15.0), follow_redirects=True) as client:
        async with client.stream("GET", url) as r:
            if r.status_code >= 400:
                raise HTTPException(400, f"Video download failed (HTTP {r.status_code})")
            ctype = (r.headers.get("content-type") or "video/mp4").split(";")[0]
            if "video" not in ctype and "octet-stream" not in ctype:
                raise HTTPException(415, "That link is not a video")
            async for chunk in r.aiter_bytes(1024 * 512):
                total += len(chunk)
                if total > MAX_VIDEO_BYTES:
                    raise HTTPException(413, "Video is larger than the 60 MB limit")
                if total > budget:
                    raise HTTPException(413, "Tenant storage quota reached — free space or raise the quota")
                chunks.append(chunk)
    data = b"".join(chunks)
    path = f"{APP_NAME}/library/{app_id}/{uuid.uuid4().hex}.mp4"
    res = put_object(path, data, "video/mp4")
    doc = {"file_id": uuid.uuid4().hex, "app_id": app_id, "storage_path": res["path"],
           "original_filename": (re.sub(r"[^a-zA-Z0-9 _-]+", "", name or "video").strip()[:70] or "video") + ".mp4",
           "content_type": "video/mp4", "size": res.get("size", len(data)), "is_deleted": False,
           "in_library": True, "private": False, "kind": "video", "created_at": _now(), **meta}
    await db.files.insert_one(dict(doc))
    doc.pop("_id", None)
    return {**doc, "url": f"/api/public/files/{res['path']}"}


def _fal_headers(extra: Optional[dict] = None) -> dict:
    h = {"Authorization": f"Bearer {EMERGENT_LLM_KEY}", "Content-Type": "application/json"}
    if os.environ.get("job_id"):
        h["X-App-ID"] = h["X-Job-ID"] = os.environ["job_id"]
    if os.environ.get("run_id"):
        h["X-Environment-ID"] = os.environ["run_id"]
    if extra:
        h.update(extra)
    return h


def _proxy_base() -> str:
    # Fal Universal Key supports queue inference through the Emergent proxy only, not Fal Platform APIs.
    return os.environ.get("INTEGRATION_PROXY_URL", "https://integrations.emergentagent.com").rstrip("/") + "/api/v1/fal"


def _trusted(url: str) -> str:
    base = urlparse(_proxy_base() + "/queue")
    got = urlparse(url)
    if got.scheme != base.scheme or got.netloc != base.netloc or not got.path.startswith(base.path.rstrip("/") + "/"):
        raise HTTPException(502, "Video provider returned an untrusted queue URL")
    return url


def _fal_generate(endpoint: str, payload: dict, timeout_s: int = 900) -> str:
    """Blocking fal queue flow (submit → poll → result); always run in a worker thread."""
    import time
    base = _proxy_base()
    sub = requests.post(f"{base}/proxy", headers=_fal_headers({"X-Fal-Target-Url": f"https://queue.fal.run/{endpoint}"}),
                        json=payload, timeout=60)
    if sub.status_code == 402:
        raise HTTPException(402, "Universal Key balance is too low for AI video generation — top it up in Profile → Manage plan → Universal Key")
    if sub.status_code >= 400:
        raise HTTPException(502, f"Video model rejected the request ({sub.status_code}): {sub.text[:160]}")
    body = sub.json()
    status_url, response_url = _trusted(body["status_url"]), _trusted(body["response_url"])
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        st = requests.get(status_url, headers=_fal_headers(), timeout=30)
        st.raise_for_status()
        data = st.json()
        state = (data.get("status") or "").upper()
        if state in ("COMPLETED", "OK"):
            res = requests.get(response_url, headers=_fal_headers(), timeout=60)
            res.raise_for_status()
            out = res.json()
            url = ((out.get("video") or {}) if isinstance(out.get("video"), dict) else {}).get("url")
            if not url:
                raise HTTPException(502, "The model returned no video")
            return url
        if state in ("FAILED", "CANCELLED", "CANCELED", "ERROR"):
            raise HTTPException(502, f"Video generation {state.lower()}")
        time.sleep(3)
    raise HTTPException(504, "Video generation timed out")


class StockIn(BaseModel):
    query: Optional[str] = None
    count: int = 3
    place: bool = True


class ImportOneIn(BaseModel):
    provider: str
    download_url: str
    title: Optional[str] = None
    source_url: Optional[str] = None
    contributor: Optional[str] = None
    place: bool = False


class AiVideoIn(BaseModel):
    prompt: Optional[str] = None
    model: str = "veo3.1"
    aspect_ratio: str = "16:9"
    duration: Optional[str] = None
    place: bool = True


class PlaceIn(BaseModel):
    url: str
    heading: Optional[str] = None
    caption: Optional[str] = None
    page_slug: str = "/"


def register(api, db, get_current_user, get_user_app, log_activity):
    async def _quota(app_doc: dict) -> int:
        return int(app_doc.get("storage_quota_mb") or os.environ.get("TENANT_STORAGE_QUOTA_MB", "500"))

    def _terms(app_doc: dict) -> str:
        return " ".join(filter(None, [app_doc.get("site_niche") or app_doc.get("industry"), (app_doc.get("name") or "").split()[0] if app_doc.get("industry") else None]))[:60] or "business team office"

    async def place_video(app_id: str, url: str, heading: str, caption: str, page_slug: str = "/") -> dict:
        page = await db.pages.find_one({"app_id": app_id, "slug": page_slug}, {"_id": 0}) or await db.pages.find_one({"app_id": app_id}, {"_id": 0})
        if not page:
            raise HTTPException(404, "This tenant has no pages yet — build or import the site first")
        blocks = page.get("blocks") or []
        block = {"id": _uid("b"), "type": "video", "props": {"heading": heading or "See it in action", "url": url, "caption": caption or ""},
                 "style": {"bg": "muted", "align": "center", "padding": "md"}}
        existing = next((i for i, b in enumerate(blocks) if b.get("type") == "video" and b.get("props", {}).get("url") == url), None)
        if existing is None:
            idx = next((i for i, b in enumerate(blocks) if b.get("type") == "hero"), 0) + 1
            blocks.insert(idx, block)
            await db.pages.update_one({"page_id": page["page_id"]}, {"$set": {"blocks": blocks, "updated_at": _now()}})
        return {"page_slug": page["slug"], "block_id": block["id"]}

    @api.get("/apps/{app_id}/videos")
    async def list_videos(app_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        docs = await db.files.find({"app_id": app_id, "is_deleted": {"$ne": True}, "content_type": {"$regex": "^video/"}}, {"_id": 0}).sort("created_at", -1).to_list(100)
        pexels_key, pixabay_key = _keys()
        return {"videos": [{**d, "url": f"/api/public/files/{d['storage_path']}"} for d in docs],
                "stock_enabled": bool(pexels_key or pixabay_key), "providers": {"pexels": bool(pexels_key), "pixabay": bool(pixabay_key)},
                "ai_models": [{"id": k, "label": v["label"]} for k, v in FAL_MODELS.items()], "ai_enabled": bool(EMERGENT_LLM_KEY)}

    @api.get("/apps/{app_id}/videos/stock-search")
    async def stock_search(app_id: str, q: Optional[str] = None, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        return {"results": await search_stock(q or _terms(doc), 12), "query": q or _terms(doc)}

    @api.post("/apps/{app_id}/videos/auto-source")
    async def auto_source(app_id: str, body: StockIn, user: dict = Depends(get_current_user)):
        """Find niche-matched free videos, download them into the library and drop one onto the site."""
        doc = await require_ai_access(app_id, user)
        query = (body.query or _terms(doc)).strip()
        found = await search_stock(query, max(6, body.count * 3))
        if not found:
            raise HTTPException(404, f"No free videos found for '{query}'")
        quota = await _quota(doc)
        saved, failures = [], []
        for item in found[:max(1, min(6, body.count))]:
            try:
                v = await store_video(db, app_id, item["download_url"], quota, item.get("title") or query,
                                      {"kind": "video", "uploaded_by": f"{item['provider']} stock", "source_url": item.get("source_url"),
                                       "provider": item["provider"], "contributor": item.get("contributor"), "license_review_required": True,
                                       "search_query": query})
                saved.append(v)
            except HTTPException as e:
                failures.append({"item": item.get("source_url") or item["download_url"], "reason": str(e.detail)})
            except Exception as e:
                failures.append({"item": item.get("download_url"), "reason": type(e).__name__})
        placed = None
        if saved and body.place:
            placed = await place_video(app_id, saved[0]["url"], f"{doc.get('name')} in action", f"Video by {saved[0].get('contributor') or saved[0].get('provider')}")
        await log_activity(app_id, user["user_id"], "video.sourced", f"{len(saved)} free video(s) added for '{query}'")
        return {"query": query, "saved": saved, "placed": placed, "failures": failures}

    @api.post("/apps/{app_id}/videos/import-one")
    async def import_one(app_id: str, body: ImportOneIn, user: dict = Depends(get_current_user)):
        doc = await require_ai_access(app_id, user)
        if urlparse(body.download_url).hostname not in ("player.vimeo.com", "cdn.pixabay.com", "vod-progressive.akamaized.net", "videos.pexels.com") and not urlparse(body.download_url).hostname.endswith((".pexels.com", ".pixabay.com", ".vimeocdn.com", ".akamaized.net")):
            raise HTTPException(400, "Only Pexels and Pixabay video files can be imported")
        v = await store_video(db, app_id, body.download_url, await _quota(doc), body.title or "stock video",
                              {"kind": "video", "uploaded_by": f"{body.provider} stock", "source_url": body.source_url,
                               "provider": body.provider, "contributor": body.contributor, "license_review_required": True})
        placed = await place_video(app_id, v["url"], f"{doc.get('name')} in action", f"Video by {body.contributor or body.provider}") if body.place else None
        return {"video": v, "placed": placed}

    @api.post("/apps/{app_id}/videos/ai-generate")
    async def ai_generate(app_id: str, body: AiVideoIn, user: dict = Depends(get_current_user)):
        doc = await require_ai_access(app_id, user)
        model = FAL_MODELS.get(body.model)
        if not model:
            raise HTTPException(400, "Unknown video model")
        if not EMERGENT_LLM_KEY:
            raise HTTPException(500, "LLM key missing")
        prompt = (body.prompt or f"A premium 8-second brand film for {doc.get('name')}, a {doc.get('site_niche') or doc.get('industry')} business: cinematic camera movement, real people at work, natural light, no on-screen text.").strip()
        job_id = _uid("vjob")
        await db.video_jobs.insert_one({"job_id": job_id, "app_id": app_id, "status": "running", "model": body.model,
                                        "prompt": prompt, "created_at": _now()})
        payload = {**model["defaults"], "prompt": prompt, "aspect_ratio": body.aspect_ratio}
        if body.duration:
            payload["duration"] = body.duration

        async def run():
            try:
                url = await asyncio.to_thread(_fal_generate, model["endpoint"], payload)
                v = await store_video(db, app_id, url, await _quota(doc), f"ai {doc.get('name')}",
                                      {"kind": "video", "uploaded_by": f"AI ({model['label']})", "ai_prompt": prompt, "ai_model": model["endpoint"]})
                placed = await place_video(app_id, v["url"], f"{doc.get('name')} — AI brand film", "") if body.place else None
                await db.video_jobs.update_one({"job_id": job_id}, {"$set": {"status": "done", "result": {"video": v, "placed": placed}, "finished_at": _now()}})
                await log_activity(app_id, user["user_id"], "video.generated", f"AI video generated with {model['label']}")
            except HTTPException as e:
                await db.video_jobs.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e.detail), "finished_at": _now()}})
            except Exception as e:
                logger.exception("ai video failed")
                await db.video_jobs.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e)[:180], "finished_at": _now()}})
        asyncio.create_task(run())
        return {"job_id": job_id, "status": "running", "prompt": prompt, "model": model["label"]}

    @api.get("/apps/{app_id}/videos/job/{job_id}")
    async def video_job(app_id: str, job_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        job = await db.video_jobs.find_one({"job_id": job_id, "app_id": app_id}, {"_id": 0})
        if not job:
            raise HTTPException(404, "Video job not found")
        return job

    @api.post("/apps/{app_id}/videos/place")
    async def place(app_id: str, body: PlaceIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        res = await place_video(app_id, body.url, body.heading or "See it in action", body.caption or "", body.page_slug)
        await log_activity(app_id, user["user_id"], "video.placed", f"Video placed on {res['page_slug']}")
        return res

    return {"place_video": place_video, "auto_source": auto_source, "search_stock": search_stock, "store_video": store_video}
