import io
import re
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Depends, UploadFile, File
from pydantic import BaseModel

logger = logging.getLogger("agency.cms")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def uid(p):
    import uuid
    return f"{p}_{uuid.uuid4().hex[:12]}"


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or uid("item")[5:]


DEFAULT_COLLECTIONS = [("Blog posts", "blog"), ("Case studies", "case-studies")]

WORKFLOW_TEMPLATES = {
    "welcome_lead": {"name": "Welcome email on new lead", "trigger": "form_submitted", "conditions": [],
                     "actions": [{"type": "email", "subject": "Thanks for reaching out, {{name}}", "body": "We received your message and will get back to you within one business day."}, {"type": "notify", "message": "New lead from {{name}} ({{email}})"}]},
    "slack_ping": {"name": "Slack / webhook ping on new lead", "trigger": "form_submitted", "conditions": [],
                   "actions": [{"type": "webhook", "url": "https://hooks.slack.com/services/REPLACE/ME"}, {"type": "notify", "message": "Lead pinged to Slack: {{name}}"}]},
    "thank_payment": {"name": "Thank-you on payment", "trigger": "payment_succeeded", "conditions": [],
                      "actions": [{"type": "email", "subject": "Welcome to the {{plan}} plan", "body": "Your subscription is active. Reply to this email any time if you need help."}, {"type": "db_write", "collection": "payments"}]},
    "log_chat": {"name": "Log chat leads to database", "trigger": "chat_lead", "conditions": [], "actions": [{"type": "db_write", "collection": "chat_leads"}]},
    "pro_alert": {"name": "Alert team when a Pro lead arrives", "trigger": "form_submitted", "conditions": [{"field": "message", "op": "contains", "value": "pro"}],
                  "actions": [{"type": "notify", "message": "Hot lead: {{name}} mentioned Pro"}]},
    "change_request": {"name": "Acknowledge client change requests", "trigger": "change_requested", "conditions": [],
                       "actions": [{"type": "email", "subject": "We got your change request: {{title}}", "body": "Thanks — our team will review and reply in the portal."}, {"type": "notify", "message": "Change request from {{name}}: {{title}}"}]},
}
DEFAULT_TEMPLATES_ON_CREATE = ["welcome_lead", "log_chat", "change_request"]


class CollectionIn(BaseModel):
    name: str


class ItemIn(BaseModel):
    title: str
    slug: Optional[str] = None
    excerpt: str = ""
    body: str = ""
    cover: str = ""
    date: Optional[str] = None
    tags: List[str] = []
    published: bool = True


class RequestIn(BaseModel):
    title: str
    details: str


def extract_text(filename: str, data: bytes) -> str:
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "docx":
        import docx
        d = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in d.paragraphs if p.text.strip())
    if ext == "pdf":
        try:
            from pypdf import PdfReader
            return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages)
        except Exception:
            raise HTTPException(400, "Could not read this PDF")
    if ext in ("txt", "md", "csv", "json"):
        return data.decode("utf-8", "ignore")
    raise HTTPException(400, "Upload .docx, .pdf, .txt or .md")


def register(api, db, get_current_user, get_user_app, log_activity, wf=None):
    wf = wf or {}

    async def ensure_collections(app_id):
        if not await db.cms_collections.find_one({"app_id": app_id}):
            for name, slug in DEFAULT_COLLECTIONS:
                await db.cms_collections.insert_one({"collection_id": uid("col"), "app_id": app_id, "name": name, "slug": slug, "created_at": now_iso()})

    async def public_collections(app_id) -> List[dict]:
        cols = await db.cms_collections.find({"app_id": app_id}, {"_id": 0}).to_list(50)
        for c in cols:
            c["items"] = await db.cms_items.find({"collection_id": c["collection_id"], "published": True}, {"_id": 0}).sort("date", -1).to_list(200)
        return cols

    # ===== CMS =====
    @api.get("/apps/{app_id}/cms")
    async def list_cms(app_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        await ensure_collections(app_id)
        cols = await db.cms_collections.find({"app_id": app_id}, {"_id": 0}).to_list(50)
        for c in cols:
            c["items"] = await db.cms_items.find({"collection_id": c["collection_id"]}, {"_id": 0}).sort("date", -1).to_list(200)
        return cols

    @api.post("/apps/{app_id}/cms")
    async def create_collection(app_id: str, body: CollectionIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        slug = slugify(body.name)
        if await db.cms_collections.find_one({"app_id": app_id, "$or": [{"slug": slug}, {"name": {"$regex": f"^{re.escape(body.name.strip())}$", "$options": "i"}}]}):
            raise HTTPException(400, "Collection exists")
        doc = {"collection_id": uid("col"), "app_id": app_id, "name": body.name.strip(), "slug": slug, "created_at": now_iso()}
        await db.cms_collections.insert_one(dict(doc))
        doc["items"] = []
        return doc

    @api.delete("/apps/{app_id}/cms/{collection_id}")
    async def delete_collection(app_id: str, collection_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        await db.cms_collections.delete_one({"app_id": app_id, "collection_id": collection_id})
        await db.cms_items.delete_many({"collection_id": collection_id})
        return {"ok": True}

    @api.post("/apps/{app_id}/cms/{collection_id}/items")
    async def create_item(app_id: str, collection_id: str, body: ItemIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        if not await db.cms_collections.find_one({"app_id": app_id, "collection_id": collection_id}):
            raise HTTPException(404, "Collection not found")
        slug = slugify(body.slug or body.title)
        if await db.cms_items.find_one({"collection_id": collection_id, "slug": slug}):
            slug = f"{slug}-{uid('')[1:5]}"
        doc = {"item_id": uid("itm"), "collection_id": collection_id, "app_id": app_id, **body.model_dump(), "slug": slug, "date": body.date or now_iso()[:10], "created_at": now_iso(), "updated_at": now_iso()}
        await db.cms_items.insert_one(dict(doc))
        await log_activity(app_id, user["user_id"], "cms.item", f"CMS item created: {body.title[:50]}")
        return doc

    @api.put("/apps/{app_id}/cms/{collection_id}/items/{item_id}")
    async def update_item(app_id: str, collection_id: str, item_id: str, body: ItemIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        upd = body.model_dump()
        upd["slug"] = slugify(body.slug or body.title)
        upd["date"] = body.date or now_iso()[:10]
        upd["updated_at"] = now_iso()
        r = await db.cms_items.update_one({"app_id": app_id, "collection_id": collection_id, "item_id": item_id}, {"$set": upd})
        if not r.matched_count:
            raise HTTPException(404, "Item not found")
        return await db.cms_items.find_one({"item_id": item_id}, {"_id": 0})

    @api.delete("/apps/{app_id}/cms/{collection_id}/items/{item_id}")
    async def delete_item(app_id: str, collection_id: str, item_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        await db.cms_items.delete_one({"app_id": app_id, "item_id": item_id})
        return {"ok": True}

    # ===== WORKFLOW TEMPLATES =====
    @api.get("/workflows/templates")
    async def list_templates(user: dict = Depends(get_current_user)):
        return [{"key": k, **v} for k, v in WORKFLOW_TEMPLATES.items()]

    async def install_template(app_id: str, key: str) -> dict:
        t = WORKFLOW_TEMPLATES.get(key)
        if not t:
            raise HTTPException(404, "Template not found")
        doc = {"workflow_id": uid("wf"), "app_id": app_id, **t, "template": key, "enabled": True, "runs": 0, "last_run": None, "created_at": now_iso()}
        await db.workflows.insert_one(dict(doc))
        return doc

    @api.post("/apps/{app_id}/workflows/templates/{key}")
    async def add_template(app_id: str, key: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        doc = await install_template(app_id, key)
        await log_activity(app_id, user["user_id"], "workflow.template", f"Installed workflow template: {doc['name']}")
        return doc

    async def install_defaults(app_id: str):
        for k in DEFAULT_TEMPLATES_ON_CREATE:
            await install_template(app_id, k)

    # ===== CLIENT PORTAL =====
    @api.get("/portal")
    async def portal(user: dict = Depends(get_current_user)):
        memberships = await db.memberships.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(200)
        by_app = {m["app_id"]: m for m in memberships}
        apps = await db.apps.find({"$or": [{"owner_id": user["user_id"]}, {"app_id": {"$in": list(by_app)}}]}, {"_id": 0}).to_list(200)
        out = []
        for a in apps:
            aid = a["app_id"]
            out.append({"app_id": aid, "name": a["name"], "kind": a.get("kind", "website"), "color": a.get("color"), "status": a.get("status"), "industry": a.get("industry"),
                        "role": "owner" if a["owner_id"] == user["user_id"] else by_app.get(aid, {}).get("role", "viewer"),
                        "preview_token": a.get("preview_token") if a.get("preview_enabled") else None, "custom_domain": a.get("custom_domain"), "domain_status": a.get("domain_status"),
                        "plan": a.get("plan"), "thumbnail": a.get("thumbnail"),
                        "invoices": await db.payment_transactions.find({"app_id": aid}, {"_id": 0, "session_id": 1, "plan_name": 1, "amount": 1, "currency": 1, "payment_status": 1, "created_at": 1}).sort("created_at", -1).limit(20).to_list(20),
                        "leads": await db.messages.count_documents({"app_id": aid, "source": {"$in": ["contact", "chat"]}}),
                        "leads_unread": await db.messages.count_documents({"app_id": aid, "status": "unread", "source": {"$in": ["contact", "chat"]}}),
                        "requests": await db.messages.find({"app_id": aid, "source": "request"}, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20),
                        "activity": await db.activity_logs.find({"app_id": aid}, {"_id": 0}).sort("created_at", -1).limit(8).to_list(8)})
        return {"user": {"name": user.get("name"), "email": user["email"]}, "apps": out}

    @api.post("/portal/{app_id}/request")
    async def change_request(app_id: str, body: RequestIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        doc = {"message_id": uid("msg"), "app_id": app_id, "source": "request", "from_name": user.get("name") or user["email"], "from_email": user["email"],
               "subject": f"Change request: {body.title.strip()[:120]}", "body": body.details.strip()[:4000], "status": "unread", "starred": False, "replies": [],
               "created_at": now_iso(), "updated_at": now_iso()}
        await db.messages.insert_one(dict(doc))
        await log_activity(app_id, user["user_id"], "request.new", f"Change request: {body.title[:60]}")
        if wf.get("fire_event"):
            await wf["fire_event"](app_id, "change_requested", {"name": doc["from_name"], "email": user["email"], "title": body.title.strip(), "details": body.details.strip()[:500]})
        return doc

    # ===== LONG BRIEF UPLOAD =====
    @api.post("/apps/{app_id}/ai/brief-upload")
    async def brief_upload(app_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        text = extract_text(file.filename or "brief.txt", await file.read()).strip()
        if len(text) < 20:
            raise HTTPException(400, "No readable text found in the document")
        return {"filename": file.filename, "chars": len(text), "text": text[:20000]}

    return {"public_collections": public_collections, "install_defaults": install_defaults}
