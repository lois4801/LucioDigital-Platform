import os
import uuid
import logging
import requests
from fastapi import HTTPException, Depends, UploadFile, File, Response

logger = logging.getLogger("storage")
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "omnistack"
MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "svg": "image/svg+xml", "webp": "image/webp", "gif": "image/gif"}
storage_key = None


def init_storage(force=False):
    global storage_key
    if storage_key and not force:
        return storage_key
    r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    r.raise_for_status()
    storage_key = r.json()["storage_key"]
    return storage_key


def put_object(path, data, content_type):
    r = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": init_storage(), "Content-Type": content_type}, data=data, timeout=120)
    if r.status_code == 404:
        r = requests.put(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": init_storage(force=True), "Content-Type": content_type}, data=data, timeout=120)
    r.raise_for_status()
    return r.json()


def get_object(path):
    r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": init_storage()}, timeout=60)
    if r.status_code == 404:
        r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": init_storage(force=True)}, timeout=60)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")


def register(api, db, get_current_user, get_user_app, log_activity, now_iso):
    @api.post("/apps/{app_id}/brand/logo")
    async def upload_logo(app_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
        app = await get_user_app(app_id, user)
        ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
        if ext not in MIME:
            raise HTTPException(400, "Logo must be PNG, JPG, SVG, WEBP or GIF")
        data = await file.read()
        if len(data) > 2 * 1024 * 1024:
            raise HTTPException(400, "Logo must be under 2 MB")
        path = f"{APP_NAME}/logos/{app_id}/{uuid.uuid4().hex}.{ext}"
        try:
            res = put_object(path, data, MIME[ext])
        except Exception as e:
            raise HTTPException(502, f"Storage upload failed: {str(e)[:120]}")
        await db.files.insert_one({"file_id": uuid.uuid4().hex, "app_id": app_id, "storage_path": res["path"], "original_filename": file.filename, "content_type": MIME[ext], "size": res.get("size", len(data)), "is_deleted": False, "created_at": now_iso()})
        url = f"/api/public/files/{res['path']}"
        await db.apps.update_one({"app_id": app_id}, {"$set": {"logo": url, "brand_profile.logo": url, "updated_at": now_iso()}})
        # Flow into every navbar/footer block across the site
        touched = 0
        async for pg in db.pages.find({"app_id": app_id}, {"_id": 0, "page_id": 1, "blocks": 1}):
            changed = False
            for b in pg.get("blocks", []):
                if b.get("type") in ("navbar", "footer"):
                    b.setdefault("props", {})["logo"] = url
                    changed = True
            if changed:
                await db.pages.update_one({"page_id": pg["page_id"]}, {"$set": {"blocks": pg["blocks"], "updated_at": now_iso()}})
                touched += 1
        await log_activity(app_id, user["user_id"], "brand.logo", f"Logo uploaded ({file.filename}) and applied to {touched} pages")
        return {"logo": url, "pages_updated": touched, "app": app["name"]}

    @api.post("/apps/{app_id}/media/upload")
    async def upload_image(app_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
        if ext not in MIME:
            raise HTTPException(400, "Image must be PNG, JPG, SVG, WEBP or GIF")
        data = await file.read()
        if len(data) > 8 * 1024 * 1024:
            raise HTTPException(400, "Image must be under 8 MB")
        path = f"{APP_NAME}/images/{app_id}/{uuid.uuid4().hex}.{ext}"
        try:
            res = put_object(path, data, MIME[ext])
        except Exception as e:
            raise HTTPException(502, f"Storage upload failed: {str(e)[:120]}")
        await db.files.insert_one({"file_id": uuid.uuid4().hex, "app_id": app_id, "storage_path": res["path"], "original_filename": file.filename, "content_type": MIME[ext], "size": res.get("size", len(data)), "is_deleted": False, "created_at": now_iso()})
        return {"url": f"/api/public/files/{res['path']}", "size": res.get("size", len(data))}

    @api.delete("/apps/{app_id}/brand/logo")
    async def remove_logo(app_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        await db.apps.update_one({"app_id": app_id}, {"$set": {"logo": None, "brand_profile.logo": None}})
        async for pg in db.pages.find({"app_id": app_id}, {"_id": 0, "page_id": 1, "blocks": 1}):
            for b in pg.get("blocks", []):
                if b.get("type") in ("navbar", "footer"):
                    b.get("props", {}).pop("logo", None)
            await db.pages.update_one({"page_id": pg["page_id"]}, {"$set": {"blocks": pg["blocks"]}})
        return {"logo": None}

    @api.get("/public/files/{path:path}")
    async def public_file(path: str):
        rec = await db.files.find_one({"storage_path": path, "is_deleted": False}, {"_id": 0})
        if not rec:
            raise HTTPException(404, "File not found")
        try:
            data, ct = get_object(path)
        except Exception as e:
            raise HTTPException(502, f"Storage read failed: {str(e)[:120]}")
        return Response(content=data, media_type=rec.get("content_type") or ct, headers={"Cache-Control": "public, max-age=31536000, immutable"})
