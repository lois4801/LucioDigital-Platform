import io
import json
import os
import re
import uuid
import zipfile
from datetime import datetime, timezone

from fastapi import Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from storage import MIME, get_object, put_object

APP_NAME = "omnistack"
DOC_MIME = {
    "pdf": "application/pdf", "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv", "txt": "text/plain", "zip": "application/zip", "json": "application/json",
    "mp4": "video/mp4", "webm": "video/webm", "mp3": "audio/mpeg", "wav": "audio/wav",
}
ALL_MIME = {**MIME, **DOC_MIME}
MAX_BYTES = 15 * 1024 * 1024
DEFAULT_QUOTA_MB = int(os.environ.get("TENANT_STORAGE_QUOTA_MB", "500"))
FILE_URL_RE = re.compile(r"(?:https?://[^\s\"'()]+)?/api/public/files/([A-Za-z0-9._/\-]+)")
EXPORT_COLLECTIONS = ("pages", "cms_collections", "cms_items", "messages", "memberships", "activity_logs", "workflows", "site_analytics")


class RenameIn(BaseModel):
    name: str


class PrivacyIn(BaseModel):
    private: bool


def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def usage_for(db, app_id: str, quota_mb: int) -> dict:
    agg = await db.files.aggregate([
        {"$match": {"app_id": app_id, "is_deleted": False}},
        {"$group": {"_id": None, "bytes": {"$sum": "$size"}, "count": {"$sum": 1}}},
    ]).to_list(1)
    used = int(agg[0]["bytes"]) if agg else 0
    count = int(agg[0]["count"]) if agg else 0
    quota = quota_mb * 1024 * 1024
    return {"used_bytes": used, "quota_bytes": quota, "files": count,
            "percent": round(min(100, used / quota * 100), 1) if quota else 0}


# Rewrites storage URLs in exported HTML/CSS to local asset paths and returns the binaries.
def bundle_media(files: dict) -> dict:
    assets, mapping = {}, {}
    out = {}
    for path, content in files.items():
        if not isinstance(content, str):
            out[path] = content
            continue
        def repl(m):
            key = m.group(1)
            if key not in mapping:
                ext = key.rsplit(".", 1)[-1].lower() if "." in key.rsplit("/", 1)[-1] else "bin"
                name = f"{uuid.uuid4().hex[:12]}.{ext}"
                try:
                    data, _ = get_object(key)
                except Exception:
                    return m.group(0)
                assets[f"site/assets/{name}"] = data
                mapping[key] = name
            return f"assets/{mapping[key]}"
        out[path] = FILE_URL_RE.sub(repl, content)
    out.update(assets)
    return out


def register(api, db, get_current_user, get_user_app, log_activity):
    async def _quota(app_doc: dict) -> int:
        return int(app_doc.get("storage_quota_mb") or DEFAULT_QUOTA_MB)

    @api.post("/apps/{app_id}/files")
    async def upload_file(app_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
        app_doc = await get_user_app(app_id, user)
        ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
        if ext not in ALL_MIME:
            raise HTTPException(400, "Unsupported file type")
        data = await file.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(400, "File must be under 15 MB")
        quota_mb = await _quota(app_doc)
        u = await usage_for(db, app_id, quota_mb)
        if u["used_bytes"] + len(data) > u["quota_bytes"]:
            raise HTTPException(413, f"Storage quota reached ({quota_mb} MB). Delete files or ask for more space.")
        path = f"{APP_NAME}/library/{app_id}/{uuid.uuid4().hex}.{ext}"
        try:
            res = put_object(path, data, ALL_MIME[ext])
        except Exception as e:
            raise HTTPException(502, f"Storage upload failed: {str(e)[:120]}")
        doc = {
            "file_id": uuid.uuid4().hex, "app_id": app_id, "storage_path": res["path"],
            "original_filename": file.filename or f"file.{ext}", "content_type": ALL_MIME[ext],
            "size": res.get("size", len(data)), "is_deleted": False,
            "uploaded_by": user.get("name") or user.get("email"), "in_library": True, "private": True,
            "created_at": now_iso(),
        }
        await db.files.insert_one(doc)
        await log_activity(app_id, user["user_id"], "file.uploaded", f"Uploaded {doc['original_filename']}")
        doc.pop("_id", None)
        return {**doc, "url": f"/api/public/files/{res['path']}"}

    @api.get("/apps/{app_id}/files")
    async def list_files(app_id: str, user: dict = Depends(get_current_user)):
        app_doc = await get_user_app(app_id, user)
        docs = await db.files.find({"app_id": app_id, "is_deleted": False, "in_library": True}, {"_id": 0}).sort("created_at", -1).to_list(500)
        for d in docs:
            d["url"] = f"/api/public/files/{d['storage_path']}"
        return {"files": docs, "usage": await usage_for(db, app_id, await _quota(app_doc))}

    @api.get("/apps/{app_id}/files/usage")
    async def file_usage(app_id: str, user: dict = Depends(get_current_user)):
        app_doc = await get_user_app(app_id, user)
        return await usage_for(db, app_id, await _quota(app_doc))

    @api.patch("/apps/{app_id}/files/{file_id}")
    async def rename_file(app_id: str, file_id: str, body: RenameIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        name = body.name.strip()[:160]
        if not name:
            raise HTTPException(400, "Name required")
        res = await db.files.update_one({"app_id": app_id, "file_id": file_id, "is_deleted": False}, {"$set": {"original_filename": name}})
        if not res.matched_count:
            raise HTTPException(404, "File not found")
        doc = await db.files.find_one({"file_id": file_id}, {"_id": 0})
        return {**doc, "url": f"/api/public/files/{doc['storage_path']}"}

    @api.get("/apps/{app_id}/files/{file_id}/download")
    async def download_file(app_id: str, file_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        doc = await db.files.find_one({"app_id": app_id, "file_id": file_id, "is_deleted": False}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "File not found")
        try:
            data, ct = get_object(doc["storage_path"])
        except Exception as e:
            raise HTTPException(502, f"Storage read failed: {str(e)[:120]}")
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", doc.get("original_filename") or "file")
        return StreamingResponse(iter([data]), media_type=doc.get("content_type") or ct,
                                 headers={"Content-Disposition": f"inline; filename={name}"})

    @api.patch("/apps/{app_id}/files/{file_id}/privacy")
    async def set_privacy(app_id: str, file_id: str, body: PrivacyIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        res = await db.files.update_one({"app_id": app_id, "file_id": file_id, "is_deleted": False}, {"$set": {"private": body.private}})
        if not res.matched_count:
            raise HTTPException(404, "File not found")
        doc = await db.files.find_one({"file_id": file_id}, {"_id": 0})
        return {**doc, "url": f"/api/public/files/{doc['storage_path']}"}

    @api.delete("/apps/{app_id}/files/{file_id}")
    async def delete_file(app_id: str, file_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        res = await db.files.update_one({"app_id": app_id, "file_id": file_id, "is_deleted": False}, {"$set": {"is_deleted": True, "deleted_at": now_iso()}})
        if not res.matched_count:
            raise HTTPException(404, "File not found")
        await log_activity(app_id, user["user_id"], "file.deleted", "Deleted a file from the media library")
        return {"ok": True}

    @api.get("/apps/{app_id}/data-export")
    async def data_export(app_id: str, user: dict = Depends(get_current_user)):
        app_doc = await get_user_app(app_id, user)
        if app_doc["owner_id"] != user["user_id"] and not user.get("is_admin"):
            member = await db.memberships.find_one({"app_id": app_id, "user_id": user["user_id"]})
            if not member:
                raise HTTPException(403, "No access to this app")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("data/app.json", json.dumps(app_doc, indent=2, default=str))
            for name in EXPORT_COLLECTIONS:
                rows = await db[name].find({"app_id": app_id}, {"_id": 0}).to_list(5000)
                z.writestr(f"data/{name}.json", json.dumps(rows, indent=2, default=str))
            owner = await db.users.find_one({"user_id": app_doc["owner_id"]}, {"_id": 0, "password_hash": 0})
            member_ids = [m["user_id"] async for m in db.memberships.find({"app_id": app_id}, {"_id": 0, "user_id": 1})]
            people = await db.users.find({"user_id": {"$in": member_ids}}, {"_id": 0, "password_hash": 0}).to_list(500)
            z.writestr("data/people.json", json.dumps({"owner": owner, "members": people}, indent=2, default=str))
            docs = await db.files.find({"app_id": app_id, "is_deleted": False}, {"_id": 0}).to_list(500)
            manifest = []
            for d in docs:
                try:
                    data, _ = get_object(d["storage_path"])
                except Exception:
                    continue
                safe = re.sub(r"[^A-Za-z0-9._-]+", "_", d.get("original_filename") or "file")
                z.writestr(f"files/{d['file_id']}-{safe}", data)
                manifest.append({"file": f"files/{d['file_id']}-{safe}", "name": d.get("original_filename"), "size": d.get("size"), "uploaded_at": d.get("created_at")})
            z.writestr("files/manifest.json", json.dumps(manifest, indent=2))
            z.writestr("README.md", f"# {app_doc['name']} — data & media export\n\nGenerated {now_iso()}\n\n"
                                    "`data/` holds every record for this client as JSON (site pages, CMS, leads, team, activity).\n"
                                    "`files/` holds every uploaded file, with `files/manifest.json` mapping them to their original names.\n"
                                    "This archive is yours to keep, migrate or import into another system at any time.\n")
        buf.seek(0)
        await log_activity(app_id, user["user_id"], "data.exported", "Downloaded full client data & media archive")
        fname = f"{app_doc['name'].lower().replace(' ', '-')}-data-export.zip"
        return StreamingResponse(iter([buf.getvalue()]), media_type="application/zip",
                                 headers={"Content-Disposition": f"attachment; filename={fname}"})
