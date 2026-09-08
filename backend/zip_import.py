"""ZIP site import: extract an uploaded bundle, detect its pages and assets, store the media in the
tenant library and rebuild every HTML page as editable Site Mode pages."""
import io
import os
import re
import uuid
import asyncio
import logging
import zipfile
from datetime import datetime, timezone
from typing import Optional, List
from urllib.parse import urljoin, urlparse, unquote

from fastapi import HTTPException, Depends, UploadFile, File, Form
from storage import MIME, put_object
from files_lib import usage_for, APP_NAME
import web_import as WI

logger = logging.getLogger(__name__)
require_ai_access = None

MAX_ZIP_BYTES = int(os.environ.get("MAX_ZIP_BYTES", str(200 * 1024 * 1024)))
MAX_UNPACKED = 400 * 1024 * 1024
MAX_MEMBERS = 3000
MAX_HTML_PAGES = 40
IMG_EXT = {"jpg", "jpeg", "png", "webp", "gif", "svg", "ico", "avif"}
VID_EXT = {"mp4", "webm", "mov"}
BASE = "https://zip.local/"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _uid(p):
    return f"{p}_{uuid.uuid4().hex[:12]}"


def _safe(name: str) -> bool:
    n = name.replace("\\", "/")
    return not (n.startswith("/") or ".." in n.split("/") or n.startswith("__MACOSX") or "/." in f"/{n}")


def _slug_for(rel: str, index: int) -> str:
    p = re.sub(r"(index|home|default)\.html?$", "", rel, flags=re.I).strip("/")
    p = re.sub(r"\.html?$", "", p, flags=re.I)
    s = re.sub(r"[^a-z0-9-]+", "-", p.lower()).strip("-")
    return "/" + s if s else ("/" if index == 0 else f"/page-{index}")


async def _store_asset(db, app_id: str, name: str, data: bytes, ctype: str, budget: int) -> Optional[str]:
    ext = name.rsplit(".", 1)[-1].lower()
    if ext not in MIME or len(data) > budget:
        return None
    res = put_object(f"{APP_NAME}/library/{app_id}/{uuid.uuid4().hex}.{ext}", data, MIME.get(ext, ctype))
    await db.files.insert_one({"file_id": uuid.uuid4().hex, "app_id": app_id, "storage_path": res["path"],
                               "original_filename": name.rsplit("/", 1)[-1][:160], "content_type": MIME.get(ext, ctype),
                               "size": res.get("size", len(data)), "is_deleted": False, "in_library": True,
                               "private": False, "uploaded_by": "zip import", "created_at": _now()})
    return f"/api/public/files/{res['path']}"


async def build_from_zip(db, app_id: str, raw: bytes, quota_mb: int, on=None) -> dict:
    async def say(stage, detail=""):
        if on:
            await on(stage, detail)
    if len(raw) > MAX_ZIP_BYTES:
        raise HTTPException(413, "That ZIP is larger than the 200 MB limit")
    await say("scanning", "Opening the ZIP package")
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise HTTPException(400, "That file is not a valid ZIP archive")
    infos = [i for i in zf.infolist() if not i.is_dir() and _safe(i.filename)]
    failures = [{"item": i.filename, "reason": "unsafe path skipped"} for i in zf.infolist()
                if not i.is_dir() and not _safe(i.filename)][:20]
    if len(infos) > MAX_MEMBERS:
        raise HTTPException(413, f"That ZIP has {len(infos)} files — trim it to under {MAX_MEMBERS}")
    if sum(i.file_size for i in infos) > MAX_UNPACKED:
        raise HTTPException(413, "That ZIP expands to more than 400 MB")

    html = sorted([i for i in infos if i.filename.lower().endswith((".html", ".htm"))],
                  key=lambda i: (0 if re.search(r"(^|/)(index|home)\.html?$", i.filename, re.I) else 1, i.filename.count("/"), i.filename))
    if not html:
        raise HTTPException(400, "No .html pages were found in that ZIP")
    if len(html) > MAX_HTML_PAGES:
        failures += [{"item": i.filename, "reason": f"beyond the {MAX_HTML_PAGES}-page limit"} for i in html[MAX_HTML_PAGES:]][:20]
        html = html[:MAX_HTML_PAGES]

    usage = await usage_for(db, app_id, quota_mb)
    budget = max(0, usage["quota_bytes"] - usage["used_bytes"])
    mapping, assets_saved, videos = {}, 0, 0
    media = [i for i in infos if i.filename.rsplit(".", 1)[-1].lower() in IMG_EXT | VID_EXT]
    for n, i in enumerate(media):
        if n % 10 == 0:
            await say("media", f"Saving asset {n + 1} of {len(media)} to the media library")
        try:
            data = zf.read(i)
            if len(data) < 200:
                continue
            url = await _store_asset(db, app_id, i.filename, data, "application/octet-stream", budget)
            if not url:
                failures.append({"item": i.filename, "reason": "unsupported type or storage quota reached"})
                continue
            mapping[urljoin(BASE, i.filename)] = url
            budget -= len(data)
            assets_saved += 1
            if i.filename.rsplit(".", 1)[-1].lower() in VID_EXT:
                videos += 1
        except Exception as e:
            failures.append({"item": i.filename, "reason": f"could not be read ({type(e).__name__})"})

    skipped = [i.filename for i in infos if i.filename.rsplit(".", 1)[-1].lower() in ("php", "asp", "jsp", "exe", "dll", "sh")][:20]
    failures += [{"item": s, "reason": "server-side/executable file left out"} for s in skipped]

    pages, brand = [], None
    for idx, i in enumerate(html):
        await say("reading", f"Reading page {idx + 1} of {len(html)} — {i.filename}")
        try:
            text = zf.read(i).decode("utf-8", "ignore")
        except Exception as e:
            failures.append({"item": i.filename, "reason": f"page could not be decoded ({type(e).__name__})"})
            continue
        parsed = WI._parse_page(text, urljoin(BASE, i.filename))
        parsed["slug"] = _slug_for(i.filename, idx)
        parsed["images"] = [{**im, "url": unquote(im["url"])} for im in parsed["images"]]
        pages.append(parsed)
        brand = brand or parsed.get("site_name") or (parsed.get("title") or "").split("|")[0].strip()
    if not pages:
        raise HTTPException(400, "None of the HTML pages in that ZIP could be read")

    css = " ".join(zf.read(i).decode("utf-8", "ignore")[:300_000] for i in infos if i.filename.lower().endswith(".css"))[:900_000]
    crawl = {"url": "zip://package", "brand": (brand or "Imported site")[:80], "pages": pages,
             "nav": pages[0].get("nav") or [], "colors": WI._colors_from_css(css + pages[0]["inline_css"]),
             "failures": failures}
    imp = await WI.build_import("zip://package", on, db, app_id, quota_mb, len(pages), crawl, None, mapping)
    imp["report"].update({"assets_saved": assets_saved, "videos_saved": videos, "zip_files": len(infos),
                          "html_pages": len(html)})
    imp["source"] = {**imp["source"], "pages": len(pages), "images": assets_saved}
    return imp


def register(api, db, get_current_user, get_user_app, log_activity):
    async def _quota(app_doc: dict) -> int:
        return int(app_doc.get("storage_quota_mb") or os.environ.get("TENANT_STORAGE_QUOTA_MB", "500"))

    @api.post("/apps/{app_id}/site/import-zip")
    async def import_zip(app_id: str, file: UploadFile = File(...), mode: str = Form("replace"),
                         apply_theme: str = Form("true"), user: dict = Depends(get_current_user)):
        app_doc = await require_ai_access(app_id, user)
        mode = mode if mode in ("replace", "append") else "replace"
        if mode == "replace":
            from content_lock import assert_unlocked
            await assert_unlocked(db, app_id, "replace the saved pages")
        if not (file.filename or "").lower().endswith(".zip"):
            raise HTTPException(400, "Upload a .zip package")
        raw = await file.read()
        quota = await _quota(app_doc)
        job_id = _uid("job")
        await db.import_jobs.insert_one({"job_id": job_id, "app_id": app_id, "url": file.filename, "kind": "zip",
                                         "status": "running", "stage": "queued", "stage_detail": "Unpacking the ZIP",
                                         "created_at": _now()})

        async def run():
            async def say(stage, detail=""):
                await db.import_jobs.update_one({"job_id": job_id}, {"$set": {"stage": stage, "stage_detail": detail, "stage_at": _now()}})
            try:
                imp = await build_from_zip(db, app_id, raw, quota, say)
                import_id = _uid("imp")
                await db.site_imports.insert_one({"import_id": import_id, "app_id": app_id, "created_at": _now(), **imp})
                result = WI._summary(import_id, imp)
                await say("applying", f"Adding {len(imp['pages'])} page(s) to the project")
                result["applied"] = await WI.apply_import(db, app_id, imp, mode, apply_theme.lower() == "true",
                                                          log_activity, user["user_id"])
                await db.import_jobs.update_one({"job_id": job_id}, {"$set": {"status": "done", "stage": "done", "result": result, "finished_at": _now()}})
            except HTTPException as e:
                await db.import_jobs.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e.detail), "finished_at": _now()}})
            except Exception as e:
                logger.exception("zip import failed")
                await db.import_jobs.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e)[:180], "finished_at": _now()}})
        asyncio.create_task(run())
        return {"job_id": job_id, "status": "running", "filename": file.filename}
