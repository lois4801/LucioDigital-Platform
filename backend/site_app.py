"""Convert to Web App — turns a static client site into a full-stack app in one pass:
tenant-scoped visitor auth (bcrypt + JWT, audience-isolated from agency auth), protected pages,
form submissions persisted to MongoDB, database-driven repeated sections, a private admin panel,
a real-time client API and role-based access. Design, copy and branding are never modified."""
import os
import re
import csv
import io
import hashlib
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import bcrypt
import jwt
from fastapi import HTTPException, Depends, Request, Response
from pydantic import BaseModel, EmailStr

logger = logging.getLogger("agency.siteapp")

JWT_ALG = "HS256"
SITE_AUD = "site-user"          # keeps client visitor tokens off agency endpoints
PUBLIC_SLUGS = ("/", "/about", "/services", "/contact")
SIGNUP_MODES = ("open", "approval", "invite")

# Repeated sections that become database-driven collections. (block type -> collection name, item key)
DYNAMIC_BLOCKS = {
    "features": ("Services", "items"),
    "services": ("Services", "items"),
    "pricing": ("Plans", "plans"),
    "products": ("Products", "items"),
    "team": ("Team", "members"),
    "testimonials": ("Testimonials", "items"),
    "gallery": ("Gallery", "images"),
}


def _now():
    return datetime.now(timezone.utc)


def _iso():
    return _now().isoformat()


def _uid(p):
    import uuid
    return f"{p}_{uuid.uuid4().hex[:12]}"


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), (hashed or "").encode())
    except Exception:
        return False


def site_token(app_id: str, site_user_id: str, role: str) -> str:
    payload = {"sub": site_user_id, "app": app_id, "role": role, "aud": SITE_AUD,
               "exp": _now() + timedelta(days=7)}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALG)


class ConvertIn(BaseModel):
    signup_mode: str = "open"
    allow_self_delete: Optional[bool] = None
    booking_mode: Optional[str] = None          # period | slots
    business_hours: Optional[Dict[str, Any]] = None   # {start: 9, end: 17, slot_min: 30}


class ProfileIn(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


class PasswordIn(BaseModel):
    current_password: str
    password: str


class AcceptIn(BaseModel):
    password: str


class BookingAction(BaseModel):
    action: str                      # confirm | reschedule | decline
    date: Optional[str] = None
    slot: Optional[str] = None
    note: Optional[str] = None


class ClientInviteIn(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class AccessIn(BaseModel):
    protected: bool


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: str = ""


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str


class SubmitIn(BaseModel):
    form_id: Optional[str] = None
    form_name: Optional[str] = None
    name: str = ""
    email: Optional[EmailStr] = None
    fields: Dict[str, Any] = {}
    booking_date: Optional[str] = None
    booking_slot: Optional[str] = None


class UserPatch(BaseModel):
    role: Optional[str] = None
    status: Optional[str] = None


class InviteIn(BaseModel):
    email: EmailStr
    role: str = "user"


class ItemIn(BaseModel):
    title: str = ""
    excerpt: str = ""
    body: str = ""
    cover: str = ""
    published: bool = True
    fields: Dict[str, Any] = {}


def register(api, db, get_current_user, get_user_app, log_activity, send_email=None):

    # ---------- helpers ----------

    async def app_by_token(token: str) -> dict:
        doc = await db.apps.find_one({"preview_token": token}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Site not found")
        return doc

    def webapp_of(doc: dict) -> dict:
        return doc.get("webapp") or {}

    async def require_webapp(token: str) -> dict:
        doc = await app_by_token(token)
        if not webapp_of(doc).get("converted"):
            raise HTTPException(409, "This site has not been converted to a web app yet")
        return doc

    async def current_site_user(request: Request, doc: dict) -> Optional[dict]:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        try:
            payload = jwt.decode(auth[7:], os.environ["JWT_SECRET"], algorithms=[JWT_ALG], audience=SITE_AUD)
        except jwt.PyJWTError:
            return None
        if payload.get("app") != doc["app_id"]:
            return None
        u = await db.site_users.find_one({"site_user_id": payload["sub"], "app_id": doc["app_id"]}, {"_id": 0, "password_hash": 0})
        if not u or u.get("status") != "active":
            return None
        return u

    async def require_site_user(request: Request, token: str) -> tuple:
        doc = await require_webapp(token)
        u = await current_site_user(request, doc)
        if not u:
            raise HTTPException(401, "Please sign in to continue")
        return doc, u

    async def require_panel(request: Request, token: str) -> tuple:
        """Panel access: a site admin, or the agency owner/admin via their platform session."""
        doc = await require_webapp(token)
        u = await current_site_user(request, doc)
        if u and u.get("role") == "admin":
            return doc, u
        try:
            agency = await get_current_user(request)
            app_doc = await get_user_app(doc["app_id"], agency)
            from page_guard import role_of
            if await role_of(db, app_doc, agency) in ("owner", "admin"):
                return doc, {"site_user_id": agency["user_id"], "email": agency["email"],
                             "name": agency.get("name"), "role": "admin", "agency": True}
        except HTTPException:
            pass
        raise HTTPException(403, "Admin access only")

    def public_user(u: dict) -> dict:
        return {k: u.get(k) for k in ("site_user_id", "email", "name", "role", "status", "created_at", "last_login")}

    async def notify(to: str, subject: str, body: str):
        if send_email and to:
            try:
                await send_email(to, subject, body)
            except Exception:
                logger.exception("site app email failed")

    # ---------- conversion ----------

    async def _make_dynamic(app_id: str) -> dict:
        """Copy repeated section content into CMS collections and bind the section to them.
        Block props are kept intact so the rendered design and copy never change."""
        made, bound = [], 0
        pages = await db.pages.find({"app_id": app_id}, {"_id": 0}).to_list(200)
        for pg in pages:
            blocks = pg.get("blocks") or []
            dirty = False
            for b in blocks:
                spec = DYNAMIC_BLOCKS.get(b.get("type"))
                if not spec:
                    continue
                name, key = spec
                items = (b.get("props") or {}).get(key) or []
                if not items or (b.get("props") or {}).get("dynamic"):
                    continue
                slug = _slug(name)
                col = await db.cms_collections.find_one({"app_id": app_id, "slug": slug}, {"_id": 0})
                if col and await db.cms_items.count_documents({"collection_id": col["collection_id"]}):
                    # A second section of the same kind keeps its own content in its own collection.
                    n = 2
                    while await db.cms_collections.find_one({"app_id": app_id, "slug": f"{slug}-{n}"}):
                        n += 1
                    slug, name, col = f"{slug}-{n}", f"{name} {n}", None
                if not col:
                    col = {"collection_id": _uid("col"), "app_id": app_id, "name": name, "slug": slug,
                           "kind": "section", "created_at": _iso()}
                    await db.cms_collections.insert_one(dict(col))
                    made.append(name)
                for i, it in enumerate(items):
                    if isinstance(it, str):
                        it = {"image": it}
                    title = str(it.get("title") or it.get("name") or it.get("author") or f"{name} {i + 1}")[:160]
                    await db.cms_items.insert_one({
                        "item_id": _uid("item"), "app_id": app_id, "collection_id": col["collection_id"],
                        "title": title, "slug": f"{_slug(title)}-{i}", "excerpt": str(it.get("desc") or it.get("quote") or it.get("role") or "")[:400],
                        "body": str(it.get("body") or ""), "cover": it.get("photo") or it.get("image") or "",
                        "date": _iso(), "tags": [], "published": True, "order": i,
                        "fields": {k: v for k, v in it.items()}, "source_block": b.get("id"),
                    })
                b.setdefault("props", {})["collection"] = slug
                b["props"]["dynamic"] = True
                bound += 1
                dirty = True
            if dirty:
                await db.pages.update_one({"app_id": app_id, "page_id": pg["page_id"]},
                                          {"$set": {"blocks": blocks, "updated_at": _iso()}})
        return {"collections": sorted(set(made)), "sections_bound": bound}

    async def _protect_pages(app_id: str) -> List[str]:
        protected = []
        for pg in await db.pages.find({"app_id": app_id}, {"_id": 0, "page_id": 1, "slug": 1, "name": 1}).to_list(200):
            if pg.get("slug") in PUBLIC_SLUGS:
                await db.pages.update_one({"app_id": app_id, "page_id": pg["page_id"]}, {"$set": {"protected": False}})
                continue
            await db.pages.update_one({"app_id": app_id, "page_id": pg["page_id"]}, {"$set": {"protected": True}})
            protected.append(pg.get("name") or pg.get("slug"))
        return protected

    async def _form_registry(app_id: str) -> List[dict]:
        forms = []
        for pg in await db.pages.find({"app_id": app_id}, {"_id": 0, "slug": 1, "blocks": 1}).to_list(200):
            for b in pg.get("blocks") or []:
                if b.get("type") in ("form", "contact"):
                    forms.append({"form_id": b.get("id"), "name": str((b.get("props") or {}).get("heading") or ("Contact form" if b.get("type") == "contact" else "Form"))[:80],
                                  "page": pg.get("slug")})
        return forms

    @api.post("/apps/{app_id}/convert-to-webapp")
    async def convert(app_id: str, body: ConvertIn, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        from page_guard import role_of
        if await role_of(db, doc, user) not in ("owner", "admin"):
            raise HTTPException(403, "Only the agency owner or an admin can convert a site")
        if body.signup_mode not in SIGNUP_MODES:
            raise HTTPException(400, f"signup_mode must be one of {', '.join(SIGNUP_MODES)}")
        existing = webapp_of(doc)
        token = doc.get("preview_token") or _uid("pv").replace("pv_", "pv_")
        if existing.get("converted"):
            return {"already": True, **existing, "admin_panel_url": f"/site-admin/{token}",
                    "summary": existing.get("summary", {})}

        dyn = await _make_dynamic(app_id)
        protected = await _protect_pages(app_id)
        forms = await _form_registry(app_id)

        owner = await db.users.find_one({"user_id": doc["owner_id"]}, {"_id": 0, "email": 1, "name": 1})
        admin_row = None
        if owner:
            admin_row = await db.site_users.find_one({"app_id": app_id, "email": owner["email"].lower()}, {"_id": 0})
            if not admin_row:
                admin_row = {"site_user_id": _uid("su"), "app_id": app_id, "email": owner["email"].lower(),
                             "name": owner.get("name") or "Site admin", "role": "admin", "status": "active",
                             "password_hash": "", "created_at": _iso(), "last_login": None}
                await db.site_users.insert_one(dict(admin_row))

        webapp = {
            "converted": True, "converted_at": _iso(), "signup_mode": body.signup_mode,
            "version": 1,
            "summary": {
                "auth": "Email + password sign-in, registration and password reset for site visitors",
                "signup_mode": body.signup_mode,
                "protected_pages": protected,
                "public_pages": [p for p in PUBLIC_SLUGS],
                "collections": dyn["collections"],
                "sections_bound": dyn["sections_bound"],
                "forms_connected": forms,
                "roles": ["admin", "user"],
                "api_base": f"/api/site/{token}",
                "emails": "Confirmation email to every form submitter + owner notification",
            },
        }
        await db.apps.update_one({"app_id": app_id}, {"$set": {"webapp": webapp, "preview_token": token,
                                                              "preview_enabled": True, "updated_at": _iso()}})
        await log_activity(app_id, user["user_id"], "webapp.converted",
                           f"Converted to a web app — {len(protected)} page(s) protected, {dyn['sections_bound']} section(s) now database-driven")
        if owner:
            await notify(owner["email"], f"{doc.get('name')} is now a web app",
                         f"Your site is now a full web app.\n\nAdmin panel: /site-admin/{token}\n"
                         f"Protected pages: {len(protected)}\nDatabase-driven sections: {dyn['sections_bound']}\n"
                         f"Forms connected: {len(forms)}\n\nUse “Forgot password” on the panel sign-in to set your panel password.")
        return {"already": False, **webapp, "admin_panel_url": f"/site-admin/{token}", "token": token}

    @api.get("/apps/{app_id}/webapp")
    async def webapp_status(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        w = webapp_of(doc)
        pages = await db.pages.find({"app_id": app_id}, {"_id": 0, "page_id": 1, "name": 1, "slug": 1, "protected": 1}).to_list(200)
        counts = {}
        if w.get("converted"):
            counts = {"users": await db.site_users.count_documents({"app_id": app_id}),
                      "submissions": await db.submissions.count_documents({"app_id": app_id})}
        return {**w, "pages": pages, "counts": counts, "token": doc.get("preview_token"),
                "admin_panel_url": f"/site-admin/{doc.get('preview_token')}" if w.get("converted") else None}

    @api.post("/apps/{app_id}/webapp/pages/{page_id}/access")
    async def page_access(app_id: str, page_id: str, body: AccessIn, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        from page_guard import role_of
        if await role_of(db, doc, user) not in ("owner", "admin"):
            raise HTTPException(403, "Only the agency owner or an admin can change page access")
        r = await db.pages.update_one({"app_id": app_id, "page_id": page_id}, {"$set": {"protected": body.protected}})
        if not r.matched_count:
            raise HTTPException(404, "Page not found")
        return {"page_id": page_id, "protected": body.protected}

    @api.patch("/apps/{app_id}/webapp/settings")
    async def webapp_settings(app_id: str, body: ConvertIn, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        from page_guard import role_of
        if await role_of(db, doc, user) not in ("owner", "admin"):
            raise HTTPException(403, "Only the agency owner or an admin can change these settings")
        if body.signup_mode not in SIGNUP_MODES:
            raise HTTPException(400, "Unknown signup mode")
        upd = {"webapp.signup_mode": body.signup_mode, "webapp.summary.signup_mode": body.signup_mode}
        if body.allow_self_delete is not None:
            upd["webapp.allow_self_delete"] = bool(body.allow_self_delete)
        if body.booking_mode:
            if body.booking_mode not in ("period", "slots"):
                raise HTTPException(400, "booking_mode must be 'period' or 'slots'")
            upd["webapp.booking_mode"] = body.booking_mode
        if body.business_hours is not None:
            bh = body.business_hours or {}
            upd["webapp.business_hours"] = {"start": int(bh.get("start", 9)), "end": int(bh.get("end", 17)),
                                            "slot_min": 60 if int(bh.get("slot_min", 30)) >= 60 else 30}
        await db.apps.update_one({"app_id": app_id}, {"$set": upd})
        doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0, "webapp": 1})
        return doc.get("webapp") or {}

    @api.get("/apps/{app_id}/submissions")
    async def list_submissions(app_id: str, q: str = "", export: bool = False, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        query: Dict[str, Any] = {"app_id": app_id}
        if q:
            rx = {"$regex": re.escape(q), "$options": "i"}
            query["$or"] = [{"name": rx}, {"email": rx}, {"form_name": rx}]
        rows = await db.submissions.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
        if not export:
            return {"submissions": rows, "total": await db.submissions.count_documents({"app_id": app_id})}
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["created_at", "form", "page", "name", "email", "status", "fields"])
        for r in rows:
            w.writerow([r.get("created_at"), r.get("form_name"), r.get("page"), r.get("name"), r.get("email"),
                        r.get("status"), "; ".join(f"{k}={v}" for k, v in (r.get("fields") or {}).items())])
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="submissions.csv"'})

    # ---------- client visitor auth ----------

    @api.get("/site/{token}/config")
    async def site_config(token: str):
        doc = await app_by_token(token)
        w = webapp_of(doc)
        return {"name": doc.get("name"), "converted": bool(w.get("converted")),
                "signup_mode": w.get("signup_mode", "open"),
                "booking_mode": w.get("booking_mode", "period"),
                "paid": {"enabled": bool((w.get("paid") or {}).get("enabled")), "mode": (w.get("paid") or {}).get("mode", "one_time"),
                         "price": (w.get("paid") or {}).get("price"), "currency": (w.get("paid") or {}).get("currency", "usd"),
                         "interval": (w.get("paid") or {}).get("interval", "month")},
                "allow_self_delete": bool(w.get("allow_self_delete")),
                "protected_slugs": [p["slug"] for p in await db.pages.find({"app_id": doc["app_id"], "protected": True}, {"_id": 0, "slug": 1}).to_list(200)]}

    @api.post("/site/{token}/auth/register")
    async def site_register(token: str, body: RegisterIn):
        doc = await require_webapp(token)
        mode = webapp_of(doc).get("signup_mode", "open")
        if mode == "invite":
            raise HTTPException(403, "This site is invite-only — ask the site admin for an invitation")
        if len(body.password) < 8:
            raise HTTPException(400, "Use at least 8 characters for your password")
        email = body.email.lower()
        existing = await db.site_users.find_one({"app_id": doc["app_id"], "email": email}, {"_id": 0})
        if existing and existing.get("password_hash"):
            raise HTTPException(409, "An account with that email already exists — try signing in")
        status = "pending" if mode == "approval" else "active"
        row = {"site_user_id": existing.get("site_user_id") if existing else _uid("su"),
               "app_id": doc["app_id"], "email": email, "name": (body.name or email.split("@")[0])[:80],
               "role": existing.get("role") if existing else "user",
               "status": existing.get("status") if existing else status,
               "password_hash": hash_pw(body.password), "created_at": _iso(), "last_login": None}
        await db.site_users.update_one({"app_id": doc["app_id"], "email": email}, {"$set": row}, upsert=True)
        await notify(email, f"Welcome to {doc.get('name')}",
                     "Your account is ready." if row["status"] == "active" else "Your account was created and is waiting for admin approval.")
        if row["status"] != "active":
            return {"pending": True, "message": "Your account needs admin approval before you can sign in"}
        return {"token": site_token(doc["app_id"], row["site_user_id"], row["role"]), "user": public_user(row)}

    @api.post("/site/{token}/auth/login")
    async def site_login(token: str, body: LoginIn, request: Request):
        doc = await require_webapp(token)
        email = body.email.lower()
        fwd = (request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip") or "")
        ip = fwd.split(",")[0].strip() or (request.client.host if request.client else "-")
        ident = f"{ip}:{doc['app_id']}:{email}"
        att = await db.site_login_attempts.find_one({"identifier": ident}, {"_id": 0})
        if att and att.get("count", 0) >= 5 and att.get("until", "") > _iso():
            raise HTTPException(429, "Too many attempts — try again in a few minutes")
        u = await db.site_users.find_one({"app_id": doc["app_id"], "email": email})
        if not u or not u.get("password_hash") or not verify_pw(body.password, u["password_hash"]):
            r = await db.site_login_attempts.find_one_and_update(
                {"identifier": ident},
                {"$inc": {"count": 1}, "$set": {"until": (_now() + timedelta(minutes=15)).isoformat()}},
                upsert=True, return_document=True)
            if (r or {}).get("count", 0) >= 5:
                raise HTTPException(429, "Too many attempts — try again in a few minutes")
            raise HTTPException(401, "Email or password is incorrect")
        if u.get("status") == "pending":
            raise HTTPException(403, "Your account is waiting for admin approval")
        if u.get("status") == "suspended":
            raise HTTPException(403, "This account has been suspended")
        await db.site_login_attempts.delete_one({"identifier": ident})
        await db.site_users.update_one({"site_user_id": u["site_user_id"]}, {"$set": {"last_login": _iso()}})
        return {"token": site_token(doc["app_id"], u["site_user_id"], u.get("role", "user")), "user": public_user(u)}

    @api.get("/site/{token}/auth/me")
    async def site_me(token: str, request: Request):
        doc, u = await require_site_user(request, token)
        return {"user": public_user(u)}

    @api.post("/site/{token}/auth/forgot")
    async def site_forgot(token: str, body: ForgotIn):
        doc = await require_webapp(token)
        u = await db.site_users.find_one({"app_id": doc["app_id"], "email": body.email.lower()}, {"_id": 0})
        if u:
            raw = secrets.token_urlsafe(32)
            await db.site_resets.insert_one({"app_id": doc["app_id"], "site_user_id": u["site_user_id"],
                                             "token_hash": hashlib.sha256(raw.encode()).hexdigest(),
                                             "expires_at": (_now() + timedelta(hours=1)).isoformat(), "used": False})
            await notify(u["email"], f"Reset your {doc.get('name')} password",
                         f"Open this link within the hour to choose a new password:\n\n/site-admin/{token}?reset={raw}\n\nIf you did not ask for this, ignore this email.")
        return {"sent": True}

    @api.post("/site/{token}/auth/reset")
    async def site_reset(token: str, body: ResetIn):
        doc = await require_webapp(token)
        if len(body.password) < 8:
            raise HTTPException(400, "Use at least 8 characters for your password")
        row = await db.site_resets.find_one({"app_id": doc["app_id"], "used": False,
                                             "token_hash": hashlib.sha256(body.token.encode()).hexdigest()}, {"_id": 0})
        if not row or row["expires_at"] < _iso():
            raise HTTPException(400, "This reset link has expired — request a new one")
        await db.site_users.update_one({"site_user_id": row["site_user_id"]}, {"$set": {"password_hash": hash_pw(body.password), "status": "active"}})
        await db.site_resets.update_one({"token_hash": row["token_hash"]}, {"$set": {"used": True}})
        u = await db.site_users.find_one({"site_user_id": row["site_user_id"]}, {"_id": 0, "password_hash": 0})
        return {"token": site_token(doc["app_id"], u["site_user_id"], u.get("role", "user")), "user": public_user(u)}

    # ---------- live client API ----------

    @api.get("/site/{token}/page/{slug:path}")
    async def site_page(token: str, slug: str, request: Request):
        """Page payload with the auth gate applied, so members-only pages never leak content."""
        doc = await app_by_token(token)
        path = "/" + slug.strip("/") if slug not in ("", "/") else "/"
        pg = await db.pages.find_one({"app_id": doc["app_id"], "slug": path}, {"_id": 0})
        if not pg:
            raise HTTPException(404, "Page not found")
        if pg.get("protected") and webapp_of(doc).get("converted"):
            if not await current_site_user(request, doc):
                return {"protected": True, "requires_login": True, "name": pg.get("name"), "slug": path}
        if pg.get("paid") and ((doc.get("webapp") or {}).get("paid") or {}).get("enabled"):
            u = await current_site_user(request, doc)
            from pro_features import register as _p  # noqa: F401
            access = await db.member_access.find_one({"app_id": doc["app_id"], "site_user_id": (u or {}).get("site_user_id"),
                                                      "status": "active"}, {"_id": 0}) if u else None
            if not access:
                return {"paid": True, "requires_payment": True, "requires_login": not bool(u),
                        "name": pg.get("name"), "slug": path}
        return {"protected": bool(pg.get("protected")), "requires_login": False, **pg}

    @api.get("/site/{token}/content/{col_slug}")
    async def site_content(token: str, col_slug: str):
        doc = await app_by_token(token)
        col = await db.cms_collections.find_one({"app_id": doc["app_id"], "slug": col_slug}, {"_id": 0})
        if not col:
            raise HTTPException(404, "Collection not found")
        items = await db.cms_items.find({"collection_id": col["collection_id"], "published": True}, {"_id": 0}).sort("order", 1).to_list(300)
        return {"collection": col, "items": items}

    @api.post("/site/{token}/submit")
    async def site_submit(token: str, body: SubmitIn, request: Request):
        doc = await require_webapp(token)
        u = await current_site_user(request, doc)
        page_slug, form_name = None, body.form_name or "Form"
        if body.form_id:
            pg = await db.pages.find_one({"app_id": doc["app_id"], "blocks.id": body.form_id}, {"_id": 0, "slug": 1, "blocks": 1})
            if pg:
                block = next((b for b in pg.get("blocks", []) if b.get("id") == body.form_id), None)
                page_slug = pg.get("slug")
                form_name = str(((block or {}).get("props") or {}).get("heading") or form_name)[:80]
        row = {"submission_id": _uid("sub"), "app_id": doc["app_id"], "form_id": body.form_id,
               "form_name": form_name, "page": page_slug, "name": (body.name or (u or {}).get("name") or "")[:120],
               "email": (str(body.email) if body.email else (u or {}).get("email") or "").lower(),
               "site_user_id": (u or {}).get("site_user_id"),
               "fields": {k: str(v)[:2000] for k, v in (body.fields or {}).items()},
               "status": "new", "created_at": _iso()}
        if body.booking_date:
            row["booking"] = {"date": body.booking_date[:10], "slot": (body.booking_slot or "")[:20] or None,
                              "status": "requested", "requested_at": _iso(), "confirmed_at": None}
        await db.submissions.insert_one(dict(row))
        summary = "\n".join(f"{k}: {v}" for k, v in row["fields"].items())
        if row.get("booking"):
            summary = f"Requested date: {row['booking']['date']} {row['booking'].get('slot') or ''}\n{summary}"
        if row["email"]:
            await notify(row["email"], f"We received your message — {doc.get('name')}",
                         f"Thanks{' ' + row['name'] if row['name'] else ''}, we have your submission and will reply soon.\n\n{summary}")
        owner = await db.users.find_one({"user_id": doc["owner_id"]}, {"_id": 0, "email": 1})
        if owner:
            await notify(owner["email"], f"[{form_name}] new submission on {doc.get('name')}",
                         f"From {row['name']} <{row['email']}>\nPage: {page_slug or '-'}\n\n{summary}")
        row.pop("_id", None)
        return {"ok": True, "submission": row}

    @api.get("/site/{token}/me/submissions")
    async def my_submissions(token: str, request: Request):
        doc, u = await require_site_user(request, token)
        rows = await db.submissions.find({"app_id": doc["app_id"], "site_user_id": u["site_user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return {"submissions": rows}

    # ---------- member profile ----------

    @api.get("/site/{token}/me")
    async def me_profile(token: str, request: Request):
        doc, u = await require_site_user(request, token)
        return {"user": {**public_user(u), "phone": u.get("phone", ""), "notes": u.get("notes", "")},
                "allow_self_delete": bool(webapp_of(doc).get("allow_self_delete"))}

    @api.patch("/site/{token}/me")
    async def me_update(token: str, body: ProfileIn, request: Request):
        doc, u = await require_site_user(request, token)
        upd = {k: str(v)[:400] for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
        if not upd:
            raise HTTPException(400, "Nothing to update")
        await db.site_users.update_one({"site_user_id": u["site_user_id"]}, {"$set": upd})
        row = await db.site_users.find_one({"site_user_id": u["site_user_id"]}, {"_id": 0, "password_hash": 0})
        return {"user": {**public_user(row), "phone": row.get("phone", ""), "notes": row.get("notes", "")}}

    @api.post("/site/{token}/me/password")
    async def me_password(token: str, body: PasswordIn, request: Request):
        doc, u = await require_site_user(request, token)
        row = await db.site_users.find_one({"site_user_id": u["site_user_id"]})
        if not verify_pw(body.current_password, row.get("password_hash", "")):
            raise HTTPException(401, "Your current password is incorrect")
        if len(body.password) < 8:
            raise HTTPException(400, "Use at least 8 characters for your new password")
        await db.site_users.update_one({"site_user_id": u["site_user_id"]}, {"$set": {"password_hash": hash_pw(body.password)}})
        return {"changed": True}

    @api.delete("/site/{token}/me")
    async def me_delete(token: str, request: Request):
        doc, u = await require_site_user(request, token)
        if not webapp_of(doc).get("allow_self_delete"):
            raise HTTPException(403, "Account deletion is turned off for this site — contact the site admin")
        await db.site_users.delete_one({"site_user_id": u["site_user_id"]})
        await db.submissions.update_many({"site_user_id": u["site_user_id"]}, {"$set": {"site_user_id": None}})
        return {"deleted": True}

    # ---------- bookings ----------

    def _slots_for(w: dict) -> List[str]:
        bh = w.get("business_hours") or {"start": 9, "end": 17, "slot_min": 30}
        step = 60 if int(bh.get("slot_min", 30)) >= 60 else 30
        out, mins = [], int(bh.get("start", 9)) * 60
        end = int(bh.get("end", 17)) * 60
        while mins + step <= end:
            out.append(f"{mins // 60:02d}:{mins % 60:02d}")
            mins += step
        return out

    @api.get("/site/{token}/slots")
    async def open_slots(token: str, date: str):
        """Available slots for a date — period buckets, or fixed times minus the ones already taken."""
        doc = await require_webapp(token)
        w = webapp_of(doc)
        if w.get("booking_mode", "period") == "period":
            return {"mode": "period", "slots": ["Morning", "Afternoon", "Evening"]}
        taken = await db.submissions.distinct("booking.slot", {"app_id": doc["app_id"], "booking.date": date,
                                                               "booking.status": {"$in": ["requested", "confirmed"]}})
        return {"mode": "slots", "slots": [s for s in _slots_for(w) if s not in taken]}

    @api.get("/site/{token}/admin/bookings")
    async def admin_bookings(token: str, request: Request):
        doc, _me = await require_panel(request, token)
        rows = await db.submissions.find({"app_id": doc["app_id"], "booking": {"$ne": None}}, {"_id": 0}).sort("booking.date", 1).to_list(500)
        return {"bookings": rows, "mode": webapp_of(doc).get("booking_mode", "period"),
                "business_hours": webapp_of(doc).get("business_hours") or {"start": 9, "end": 17, "slot_min": 30}}

    @api.patch("/site/{token}/admin/bookings/{submission_id}")
    async def admin_booking_action(token: str, submission_id: str, body: BookingAction, request: Request):
        doc, _me = await require_panel(request, token)
        row = await db.submissions.find_one({"app_id": doc["app_id"], "submission_id": submission_id}, {"_id": 0})
        if not row or not row.get("booking"):
            raise HTTPException(404, "Booking not found")
        bk = dict(row["booking"])
        if body.action == "confirm":
            bk.update({"status": "confirmed", "confirmed_at": _iso()})
            subject, msg = "Your booking is confirmed", f"Your booking on {bk['date']} ({bk.get('slot') or 'any time'}) is confirmed."
        elif body.action == "reschedule":
            if not body.date:
                raise HTTPException(400, "Pick a new date to reschedule to")
            bk.update({"status": "confirmed", "date": body.date, "slot": body.slot or bk.get("slot"), "confirmed_at": _iso(), "rescheduled": True})
            subject, msg = "Your booking has moved", f"Your booking is now on {bk['date']} ({bk.get('slot') or 'any time'})."
        elif body.action == "decline":
            bk.update({"status": "declined", "confirmed_at": None})
            subject, msg = "About your booking request", "Unfortunately we cannot make that time. Reply to this email and we'll find another slot."
        else:
            raise HTTPException(400, "action must be confirm, reschedule or decline")
        if body.note:
            bk["note"] = body.note[:500]
        await db.submissions.update_one({"submission_id": submission_id},
                                        {"$set": {"booking": bk, "status": "handled" if body.action != "decline" else "archived"}})
        if row.get("email"):
            await notify(row["email"], f"{subject} — {doc.get('name')}", f"{msg}\n\n{body.note or ''}".strip())
        return {"submission_id": submission_id, "booking": bk}

    # ---------- client panel invite ----------

    @api.post("/apps/{app_id}/webapp/invite-client")
    async def invite_client(app_id: str, body: ClientInviteIn, user: dict = Depends(get_current_user)):
        """One-click invite: the client gets a single-use link that lets them set a password and manage their own site."""
        doc = await get_user_app(app_id, user)
        from page_guard import role_of
        if await role_of(db, doc, user) not in ("owner", "admin"):
            raise HTTPException(403, "Only the agency owner or an admin can invite a client")
        if not webapp_of(doc).get("converted"):
            raise HTTPException(409, "Convert this site to a web app first")
        token = doc["preview_token"]
        email = body.email.lower()
        row = await db.site_users.find_one({"app_id": app_id, "email": email}, {"_id": 0})
        if not row:
            row = {"site_user_id": _uid("su"), "app_id": app_id, "email": email,
                   "name": (body.name or email.split("@")[0])[:80], "role": "admin", "status": "active",
                   "password_hash": "", "created_at": _iso(), "last_login": None}
            await db.site_users.insert_one(dict(row))
        else:
            await db.site_users.update_one({"site_user_id": row["site_user_id"]}, {"$set": {"role": "admin", "status": "active"}})
        code = secrets.token_urlsafe(24)
        await db.client_invites.update_many({"app_id": app_id, "email": email, "state": "sent"}, {"$set": {"state": "revoked"}})
        inv = {"invite_id": _uid("inv"), "app_id": app_id, "email": email, "site_user_id": row["site_user_id"],
               "code_hash": hashlib.sha256(code.encode()).hexdigest(), "role": "admin", "state": "sent",
               "created_at": _iso(), "expires_at": (_now() + timedelta(days=7)).isoformat(),
               "invited_by": user.get("name") or user["email"]}
        await db.client_invites.insert_one(dict(inv))
        link = f"/site-admin/{token}?invite={code}"
        await notify(email, f"Your {doc.get('name')} admin access is ready",
                     f"{user.get('name') or 'Your agency'} set up an admin panel for {doc.get('name')}.\n\n"
                     f"Open this link to choose a password and sign in (valid for 7 days):\n{link}\n\n"
                     "From the panel you can review form submissions, manage accounts and edit your site content.")
        await log_activity(app_id, user["user_id"], "webapp.client_invited", f"Panel invite sent to {email}")
        inv.pop("code_hash", None)
        return {"invite": inv, "link": link}

    @api.get("/apps/{app_id}/webapp/invites")
    async def list_invites(app_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        rows = await db.client_invites.find({"app_id": app_id}, {"_id": 0, "code_hash": 0}).sort("created_at", -1).to_list(50)
        for r in rows:
            if r["state"] == "sent" and r["expires_at"] < _iso():
                r["state"] = "expired"
        return {"invites": rows}

    @api.delete("/apps/{app_id}/webapp/invites/{invite_id}")
    async def revoke_invite(app_id: str, invite_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        from page_guard import role_of
        if await role_of(db, doc, user) not in ("owner", "admin"):
            raise HTTPException(403, "Only the agency owner or an admin can revoke an invite")
        r = await db.client_invites.update_one({"app_id": app_id, "invite_id": invite_id}, {"$set": {"state": "revoked"}})
        if not r.matched_count:
            raise HTTPException(404, "Invite not found")
        return {"invite_id": invite_id, "state": "revoked"}

    @api.get("/site/{token}/invite/{code}")
    async def check_invite(token: str, code: str):
        doc = await require_webapp(token)
        inv = await db.client_invites.find_one({"app_id": doc["app_id"], "state": "sent",
                                                "code_hash": hashlib.sha256(code.encode()).hexdigest()}, {"_id": 0})
        if not inv or inv["expires_at"] < _iso():
            raise HTTPException(400, "This invitation has expired or was already used")
        return {"email": inv["email"], "site": doc.get("name"), "role": inv["role"]}

    @api.post("/site/{token}/invite/{code}/accept")
    async def accept_invite(token: str, code: str, body: AcceptIn):
        doc = await require_webapp(token)
        inv = await db.client_invites.find_one({"app_id": doc["app_id"], "state": "sent",
                                                "code_hash": hashlib.sha256(code.encode()).hexdigest()}, {"_id": 0})
        if not inv or inv["expires_at"] < _iso():
            raise HTTPException(400, "This invitation has expired or was already used")
        if len(body.password) < 8:
            raise HTTPException(400, "Use at least 8 characters for your password")
        await db.site_users.update_one({"site_user_id": inv["site_user_id"]},
                                       {"$set": {"password_hash": hash_pw(body.password), "status": "active",
                                                 "role": inv["role"], "last_login": _iso()}})
        await db.client_invites.update_one({"invite_id": inv["invite_id"]}, {"$set": {"state": "accepted", "accepted_at": _iso()}})
        u = await db.site_users.find_one({"site_user_id": inv["site_user_id"]}, {"_id": 0, "password_hash": 0})
        return {"token": site_token(doc["app_id"], u["site_user_id"], u.get("role", "admin")), "user": public_user(u)}

    # ---------- admin panel API ----------

    @api.get("/site/{token}/admin/summary")
    async def admin_summary(token: str, request: Request):
        doc, me = await require_panel(request, token)
        app_id = doc["app_id"]
        since = (_now() - timedelta(days=30)).isoformat()
        daily = await db.submissions.aggregate([
            {"$match": {"app_id": app_id, "created_at": {"$gte": since}}},
            {"$group": {"_id": {"$substr": ["$created_at", 0, 10]}, "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}]).to_list(40)
        signups = await db.site_users.aggregate([
            {"$match": {"app_id": app_id, "created_at": {"$gte": since}}},
            {"$group": {"_id": {"$substr": ["$created_at", 0, 10]}, "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}]).to_list(40)
        views = await db.analytics_events.count_documents({"app_id": app_id, "event": "view", "ts": {"$gte": since}})
        return {
            "site": {"name": doc.get("name"), "token": token, "signup_mode": webapp_of(doc).get("signup_mode", "open")},
            "me": me,
            "totals": {
                "submissions": await db.submissions.count_documents({"app_id": app_id}),
                "new_submissions": await db.submissions.count_documents({"app_id": app_id, "status": "new"}),
                "users": await db.site_users.count_documents({"app_id": app_id}),
                "pending_users": await db.site_users.count_documents({"app_id": app_id, "status": "pending"}),
                "visits_30d": views,
            },
            "submissions_daily": [{"day": d["_id"], "count": d["n"]} for d in daily],
            "signups_daily": [{"day": d["_id"], "count": d["n"]} for d in signups],
        }

    @api.get("/site/{token}/admin/submissions")
    async def admin_submissions(token: str, request: Request, q: str = ""):
        doc, _me = await require_panel(request, token)
        query: Dict[str, Any] = {"app_id": doc["app_id"]}
        if q:
            rx = {"$regex": re.escape(q), "$options": "i"}
            query["$or"] = [{"name": rx}, {"email": rx}, {"form_name": rx}]
        return {"submissions": await db.submissions.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)}

    @api.patch("/site/{token}/admin/submissions/{submission_id}")
    async def admin_submission_status(token: str, submission_id: str, body: dict, request: Request):
        doc, _me = await require_panel(request, token)
        status = str(body.get("status", "read"))
        if status not in ("new", "read", "handled", "archived"):
            raise HTTPException(400, "Unknown status")
        r = await db.submissions.update_one({"app_id": doc["app_id"], "submission_id": submission_id}, {"$set": {"status": status}})
        if not r.matched_count:
            raise HTTPException(404, "Submission not found")
        return {"submission_id": submission_id, "status": status}

    @api.get("/site/{token}/admin/users")
    async def admin_users(token: str, request: Request):
        doc, _me = await require_panel(request, token)
        rows = await db.site_users.find({"app_id": doc["app_id"]}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(500)
        return {"users": rows}

    @api.patch("/site/{token}/admin/users/{site_user_id}")
    async def admin_user_patch(token: str, site_user_id: str, body: UserPatch, request: Request):
        doc, me = await require_panel(request, token)
        upd = {}
        if body.role:
            if body.role not in ("admin", "user"):
                raise HTTPException(400, "Role must be admin or user")
            upd["role"] = body.role
        if body.status:
            if body.status not in ("active", "pending", "suspended"):
                raise HTTPException(400, "Unknown status")
            upd["status"] = body.status
        if not upd:
            raise HTTPException(400, "Nothing to update")
        if site_user_id == me.get("site_user_id") and upd.get("role") == "user":
            raise HTTPException(400, "You cannot remove your own admin access")
        r = await db.site_users.update_one({"app_id": doc["app_id"], "site_user_id": site_user_id}, {"$set": upd})
        if not r.matched_count:
            raise HTTPException(404, "User not found")
        return await db.site_users.find_one({"site_user_id": site_user_id}, {"_id": 0, "password_hash": 0})

    @api.post("/site/{token}/admin/users/invite")
    async def admin_invite(token: str, body: InviteIn, request: Request):
        doc, _me = await require_panel(request, token)
        email = body.email.lower()
        if body.role not in ("admin", "user"):
            raise HTTPException(400, "Role must be admin or user")
        if await db.site_users.find_one({"app_id": doc["app_id"], "email": email}):
            raise HTTPException(409, "That email already has an account here")
        row = {"site_user_id": _uid("su"), "app_id": doc["app_id"], "email": email, "name": email.split("@")[0],
               "role": body.role, "status": "active", "password_hash": "", "created_at": _iso(), "last_login": None}
        await db.site_users.insert_one(dict(row))
        raw = secrets.token_urlsafe(32)
        await db.site_resets.insert_one({"app_id": doc["app_id"], "site_user_id": row["site_user_id"],
                                         "token_hash": hashlib.sha256(raw.encode()).hexdigest(),
                                         "expires_at": (_now() + timedelta(days=3)).isoformat(), "used": False})
        await notify(email, f"You have been invited to {doc.get('name')}",
                     f"Choose your password with this link (valid for 3 days):\n\n/site-admin/{token}?reset={raw}")
        return {"invited": public_user(row)}

    @api.get("/site/{token}/admin/collections")
    async def admin_collections(token: str, request: Request):
        doc, _me = await require_panel(request, token)
        cols = await db.cms_collections.find({"app_id": doc["app_id"]}, {"_id": 0}).to_list(80)
        for c in cols:
            c["items"] = await db.cms_items.find({"collection_id": c["collection_id"]}, {"_id": 0}).sort("order", 1).to_list(300)
        return {"collections": cols}

    @api.post("/site/{token}/admin/collections/{col_slug}/items")
    async def admin_item_create(token: str, col_slug: str, body: ItemIn, request: Request):
        doc, _me = await require_panel(request, token)
        col = await db.cms_collections.find_one({"app_id": doc["app_id"], "slug": col_slug}, {"_id": 0})
        if not col:
            raise HTTPException(404, "Collection not found")
        n = await db.cms_items.count_documents({"collection_id": col["collection_id"]})
        row = {"item_id": _uid("item"), "app_id": doc["app_id"], "collection_id": col["collection_id"],
               "title": body.title[:160] or "Untitled", "slug": f"{_slug(body.title) or 'item'}-{n}",
               "excerpt": body.excerpt[:400], "body": body.body, "cover": body.cover, "date": _iso(),
               "tags": [], "published": body.published, "order": n, "fields": body.fields}
        await db.cms_items.insert_one(dict(row))
        return row

    @api.put("/site/{token}/admin/items/{item_id}")
    async def admin_item_update(token: str, item_id: str, body: ItemIn, request: Request):
        doc, _me = await require_panel(request, token)
        upd = {"title": body.title[:160], "excerpt": body.excerpt[:400], "body": body.body,
               "cover": body.cover, "published": body.published, "fields": body.fields, "updated_at": _iso()}
        r = await db.cms_items.update_one({"app_id": doc["app_id"], "item_id": item_id}, {"$set": upd})
        if not r.matched_count:
            raise HTTPException(404, "Item not found")
        return await db.cms_items.find_one({"item_id": item_id}, {"_id": 0})

    @api.delete("/site/{token}/admin/items/{item_id}")
    async def admin_item_delete(token: str, item_id: str, request: Request):
        doc, _me = await require_panel(request, token)
        r = await db.cms_items.delete_one({"app_id": doc["app_id"], "item_id": item_id})
        if not r.deleted_count:
            raise HTTPException(404, "Item not found")
        return {"deleted": item_id}

    return {"require_panel": require_panel, "current_site_user": current_site_user}
