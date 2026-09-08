from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import io
import re
import json
import uuid
import zipfile
import logging
import bcrypt
import jwt
import httpx
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal, Any, Dict

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, status
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict, EmailStr

# LLM
from emergentintegrations.llm.chat import LlmChat, UserMessage
from studio import DEFAULT_THEME
from export_gen import render_page, render_item_page, css, starter_app_files

# ---------- Setup ----------
JWT_ALGORITHM = "HS256"
JWT_SECRET = os.environ["JWT_SECRET"]
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="Agency Multi-Tenant Platform")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("agency")


# ---------- Utilities ----------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "type": "access",
               "exp": now_utc() + timedelta(hours=12)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "type": "refresh", "exp": now_utc() + timedelta(days=7)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def set_auth_cookies(response: Response, access: str, refresh: str):
    response.set_cookie("access_token", access, httponly=True, secure=True,
                        samesite="none", max_age=43200, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True,
                        samesite="none", max_age=604800, path="/")


def clear_auth_cookies(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    response.delete_cookie("session_token", path="/")


# ---------- Models ----------
class UserOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: str
    name: str
    role: str = "owner"
    picture: Optional[str] = None
    auth_provider: str = "jwt"
    created_at: datetime


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class SessionExchangeIn(BaseModel):
    session_id: str


class AppCreateIn(BaseModel):
    name: str
    industry: str
    kind: str = "website"  # website | app
    description: str = ""
    status: str = "active"  # active | maintenance | handover
    tags: List[str] = []
    color: str = "#10B981"
    thumbnail: Optional[str] = None
    video_url: Optional[str] = None
    live_url: Optional[str] = None


class AppUpdateIn(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    color: Optional[str] = None
    thumbnail: Optional[str] = None
    video_url: Optional[str] = None
    live_url: Optional[str] = None
    transfer_mode: Optional[bool] = None


class Block(BaseModel):
    id: str = Field(default_factory=lambda: new_id("blk"))
    type: str
    props: Dict[str, Any] = {}
    style: Dict[str, Any] = {"bg": "default", "align": "left", "padding": "md"}


class BlockUpsertIn(BaseModel):
    blocks: List[Block]


class MemberInviteIn(BaseModel):
    email: EmailStr
    role: str = "editor"  # owner | admin | editor | viewer


class AIPromptIn(BaseModel):
    prompt: str
    block: Dict[str, Any]


# ---------- Auth helpers ----------
async def get_current_user(request: Request) -> dict:
    # 1) session_token (Google)
    session_token = request.cookies.get("session_token")
    if not session_token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer ") and len(auth) > 40 and not auth[7:].count(".") == 2:
            session_token = auth[7:]

    if session_token:
        sess = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        if sess:
            expires_at = sess.get("expires_at")
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at and expires_at > now_utc():
                user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0, "password_hash": 0})
                if user:
                    return user

    # 2) JWT cookie / bearer
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_user_app(app_id: str, user: dict) -> dict:
    doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="App not found")
    # membership check: owner or member
    if doc["owner_id"] == user["user_id"]:
        return doc
    membership = await db.memberships.find_one(
        {"app_id": app_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not membership:
        raise HTTPException(status_code=403, detail="No access to this app")
    return doc


async def log_activity(app_id: str, user_id: str, kind: str, message: str, severity: str = "info"):
    await db.activity_logs.insert_one({
        "log_id": new_id("log"),
        "app_id": app_id,
        "user_id": user_id,
        "kind": kind,
        "severity": severity,
        "message": message,
        "created_at": now_utc().isoformat(),
    })


# ---------- Auth Routes ----------
@api.post("/auth/register")
async def register(body: RegisterIn, response: Response):
    email = body.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = new_id("user")
    doc = {
        "user_id": user_id,
        "email": email,
        "name": body.name,
        "role": "owner",
        "password_hash": hash_password(body.password),
        "auth_provider": "jwt",
        "picture": None,
        "created_at": now_utc().isoformat(),
    }
    await db.users.insert_one(doc)
    access = create_access_token(user_id, email)
    refresh = create_refresh_token(user_id)
    set_auth_cookies(response, access, refresh)
    doc.pop("password_hash", None)
    doc.pop("_id", None)
    return doc


@api.post("/auth/login")
async def login(body: LoginIn, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access = create_access_token(user["user_id"], email)
    refresh = create_refresh_token(user["user_id"])
    set_auth_cookies(response, access, refresh)
    user.pop("password_hash", None)
    user.pop("_id", None)
    return user


@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    clear_auth_cookies(response)
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return {**user, "is_admin": (user.get("email") or "").lower().strip() == os.environ["ADMIN_EMAIL"].lower().strip()}


CURSOR_EFFECTS = {"none", "fairy", "bubbles", "smoke", "fire", "wind", "frost", "plasma", "ink", "comet", "matrix"}


@api.patch("/me/preferences")
async def update_preferences(body: dict, user: dict = Depends(get_current_user)):
    updates = {}
    if "cursor_effect" in body:
        if body["cursor_effect"] not in CURSOR_EFFECTS:
            raise HTTPException(status_code=400, detail="Unknown cursor effect")
        updates["cursor_effect"] = body["cursor_effect"]
    for k in ("cursor_density", "cursor_speed"):
        if k in body:
            try:
                v = float(body[k])
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"{k} must be a number")
            updates[k] = max(0.2, min(3.0, v))
    if not updates:
        raise HTTPException(status_code=400, detail="No preferences provided")
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
    return {**user, **updates}


# Emergent Google OAuth session exchange
@api.post("/auth/session")
async def session_exchange(body: SessionExchangeIn, response: Response):
    # REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    async with httpx.AsyncClient(timeout=20.0) as http:
        r = await http.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": body.session_id},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session id")
    data = r.json()
    email = data["email"].lower().strip()

    existing = await db.users.find_one({"email": email})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": data.get("name", existing.get("name")),
                      "picture": data.get("picture"),
                      "auth_provider": "google"}}
        )
    else:
        user_id = new_id("user")
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": data.get("name", email.split("@")[0]),
            "role": "owner",
            "picture": data.get("picture"),
            "auth_provider": "google",
            "created_at": now_utc().isoformat(),
        })

    session_token = data["session_token"]
    expires_at = now_utc() + timedelta(days=7)
    await db.user_sessions.insert_one({
        "session_id": new_id("sess"),
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": now_utc().isoformat(),
    })

    response.set_cookie("session_token", session_token, httponly=True, secure=True,
                        samesite="none", max_age=604800, path="/")

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return user


# ---------- Apps CRUD ----------
def _serialize_app(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != "_id"}


@api.get("/apps")
async def list_apps(industry: Optional[str] = None, status_f: Optional[str] = None,
                    user: dict = Depends(get_current_user)):
    # owner OR member
    memberships = await db.memberships.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(500)
    member_app_ids = [m["app_id"] for m in memberships]
    q = {"$or": [{"owner_id": user["user_id"]}, {"app_id": {"$in": member_app_ids}}]}
    if industry:
        q["industry"] = industry
    if status_f:
        q["status"] = status_f
    docs = await db.apps.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return docs


@api.post("/apps")
async def create_app(body: AppCreateIn, user: dict = Depends(get_current_user)):
    app_id = new_id("app")
    doc = {
        "app_id": app_id,
        "owner_id": user["user_id"],
        "name": body.name,
        "industry": body.industry,
        "kind": body.kind if body.kind in ("website", "app") else "website",
        "description": body.description,
        "status": body.status,
        "tags": body.tags,
        "color": body.color,
        "thumbnail": body.thumbnail,
        "video_url": body.video_url,
        "live_url": body.live_url,
        "transfer_mode": False,
        "metrics": {
            "uptime": 99.9,
            "cpu": 24,
            "ram": 48,
            "response_ms": 120,
            "visitors_24h": 0,
        },
        "created_at": now_utc().isoformat(),
        "updated_at": now_utc().isoformat(),
    }
    await db.apps.insert_one(doc)
    await CMS_HOOKS["install_defaults"](app_id)
    # seed a starter page
    await db.pages.insert_one({
        "page_id": new_id("pg"),
        "app_id": app_id,
        "name": "Home",
        "slug": "/",
        "blocks": _default_blocks(body.name),
        "updated_at": now_utc().isoformat(),
    })
    await log_activity(app_id, user["user_id"], "app.created", f"App '{body.name}' created")
    return _serialize_app(doc)


@api.get("/apps/{app_id}")
async def get_app(app_id: str, user: dict = Depends(get_current_user)):
    doc = await get_user_app(app_id, user)
    return doc


@api.patch("/apps/{app_id}")
async def update_app(app_id: str, body: AppUpdateIn, user: dict = Depends(get_current_user)):
    doc = await get_user_app(app_id, user)
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return doc
    updates["updated_at"] = now_utc().isoformat()
    await db.apps.update_one({"app_id": app_id}, {"$set": updates})
    if "status" in updates:
        await log_activity(app_id, user["user_id"], "status.changed",
                           f"Status changed to {updates['status']}")
    if "transfer_mode" in updates:
        await log_activity(app_id, user["user_id"], "transfer.toggle",
                           f"Client Transfer Mode {'enabled' if updates['transfer_mode'] else 'disabled'}",
                           "warning")
    return await db.apps.find_one({"app_id": app_id}, {"_id": 0})


@api.delete("/apps/{app_id}")
async def delete_app(app_id: str, user: dict = Depends(get_current_user)):
    doc = await get_user_app(app_id, user)
    if doc["owner_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Only owner can delete")
    await db.apps.delete_one({"app_id": app_id})
    await db.pages.delete_many({"app_id": app_id})
    await db.memberships.delete_many({"app_id": app_id})
    await db.activity_logs.delete_many({"app_id": app_id})
    return {"ok": True}


# ---------- Pages / Builder ----------
def _default_blocks(name: str) -> List[dict]:
    return [
        {"id": new_id("blk"), "type": "hero", "props": {
            "title": f"{name}", "subtitle": "Beautifully engineered for growth.",
            "cta": "Get Started", "align": "left", "accent": "#10B981"
        }},
        {"id": new_id("blk"), "type": "features", "props": {
            "heading": "Core Capabilities",
            "items": [
                {"title": "Fast", "desc": "Sub-100ms responses across the stack."},
                {"title": "Secure", "desc": "SOC2 aligned, isolated tenants."},
                {"title": "Scalable", "desc": "From MVP to millions of users."},
            ]
        }},
        {"id": new_id("blk"), "type": "pricing", "props": {
            "heading": "Simple Pricing",
            "plans": [
                {"name": "Starter", "price": "$29", "features": ["1 project", "Basic support"]},
                {"name": "Pro", "price": "$99", "features": ["10 projects", "Priority support"]},
                {"name": "Scale", "price": "$299", "features": ["Unlimited", "Dedicated SLA"]},
            ]
        }},
        {"id": new_id("blk"), "type": "chart", "props": {
            "heading": "Growth Metrics",
            "series": [
                {"m": "Jan", "v": 32}, {"m": "Feb", "v": 48}, {"m": "Mar", "v": 61},
                {"m": "Apr", "v": 74}, {"m": "May", "v": 92}, {"m": "Jun", "v": 118},
            ]
        }},
        {"id": new_id("blk"), "type": "contact", "props": {
            "heading": "Contact Us",
            "subtitle": "Talk to our team.",
            "email": "hello@example.com"
        }},
    ]


@api.get("/apps/{app_id}/page")
async def get_page(app_id: str, user: dict = Depends(get_current_user)):
    await get_user_app(app_id, user)
    page = await db.pages.find_one({"app_id": app_id, "slug": "/"}, {"_id": 0}) or await db.pages.find_one({"app_id": app_id}, {"_id": 0})
    if not page:
        page_doc = {
            "page_id": new_id("pg"), "app_id": app_id, "name": "Home", "slug": "/",
            "blocks": _default_blocks("Untitled"),
            "updated_at": now_utc().isoformat(),
        }
        await db.pages.insert_one(page_doc)
        page_doc.pop("_id", None)
        return page_doc
    return page


@api.put("/apps/{app_id}/page")
async def save_page(app_id: str, body: BlockUpsertIn, user: dict = Depends(get_current_user)):
    await get_user_app(app_id, user)
    blocks = [b.model_dump() for b in body.blocks]
    await db.pages.update_one(
        {"app_id": app_id, "slug": "/"},
        {"$set": {"blocks": blocks, "updated_at": now_utc().isoformat()}},
        upsert=True,
    )
    await log_activity(app_id, user["user_id"], "page.saved", f"Saved {len(blocks)} blocks")
    return {"ok": True, "count": len(blocks)}


# ---------- Activity / Notifications ----------
@api.get("/apps/{app_id}/activity")
async def get_activity(app_id: str, user: dict = Depends(get_current_user)):
    await get_user_app(app_id, user)
    logs = await db.activity_logs.find({"app_id": app_id}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    return logs


@api.get("/notifications")
async def notifications(user: dict = Depends(get_current_user)):
    memberships = await db.memberships.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(500)
    app_ids = [m["app_id"] for m in memberships]
    q = {"$or": [{"user_id": user["user_id"]}, {"app_id": {"$in": app_ids}}]}
    logs = await db.activity_logs.find(q, {"_id": 0}).sort("created_at", -1).limit(15).to_list(15)
    return logs


# ---------- Members (RBAC) ----------
@api.get("/apps/{app_id}/members")
async def list_members(app_id: str, user: dict = Depends(get_current_user)):
    app_doc = await get_user_app(app_id, user)
    owner = await db.users.find_one({"user_id": app_doc["owner_id"]}, {"_id": 0, "password_hash": 0})
    memberships = await db.memberships.find({"app_id": app_id}, {"_id": 0}).to_list(200)
    members = []
    if owner:
        members.append({**owner, "role": "owner", "membership_id": "owner"})
    for m in memberships:
        u = await db.users.find_one({"user_id": m["user_id"]}, {"_id": 0, "password_hash": 0})
        if u:
            members.append({**u, "role": m["role"], "membership_id": m["membership_id"]})
    return members


@api.post("/apps/{app_id}/members")
async def invite_member(app_id: str, body: MemberInviteIn, user: dict = Depends(get_current_user)):
    app_doc = await get_user_app(app_id, user)
    email = body.email.lower().strip()
    invitee = await db.users.find_one({"email": email})
    if not invitee:
        # create shell user
        invitee_id = new_id("user")
        await db.users.insert_one({
            "user_id": invitee_id, "email": email, "name": email.split("@")[0],
            "role": "member", "auth_provider": "invited",
            "created_at": now_utc().isoformat(),
        })
    else:
        invitee_id = invitee["user_id"]

    if invitee_id == app_doc["owner_id"]:
        raise HTTPException(400, "User is the owner")

    existing = await db.memberships.find_one({"app_id": app_id, "user_id": invitee_id})
    if existing:
        await db.memberships.update_one({"membership_id": existing["membership_id"]},
                                        {"$set": {"role": body.role}})
    else:
        await db.memberships.insert_one({
            "membership_id": new_id("mem"),
            "app_id": app_id,
            "user_id": invitee_id,
            "role": body.role,
            "created_at": now_utc().isoformat(),
        })
    await log_activity(app_id, user["user_id"], "member.invited",
                       f"Invited {email} as {body.role}")
    return {"ok": True}


@api.delete("/apps/{app_id}/members/{membership_id}")
async def remove_member(app_id: str, membership_id: str, user: dict = Depends(get_current_user)):
    await get_user_app(app_id, user)
    await db.memberships.delete_one({"membership_id": membership_id, "app_id": app_id})
    await log_activity(app_id, user["user_id"], "member.removed", "Removed a member")
    return {"ok": True}


# ---------- Export ----------
def _generate_html(app_doc: dict, blocks: List[dict]) -> str:
    parts = [f"""<!doctype html><html><head><meta charset='utf-8'>
<title>{app_doc['name']}</title>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<link rel='preconnect' href='https://fonts.googleapis.com'>
<link href='https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono&display=swap' rel='stylesheet'>
<style>
  :root {{ --bg:#0b0c11; --card:#161924; --line:#282D3F; --fg:#F1F5F9; --mut:#94A3B8; --acc:{app_doc.get('color','#10B981')}; }}
  * {{ box-sizing:border-box }} body {{ margin:0; background:var(--bg); color:var(--fg); font-family:'JetBrains Mono',ui-monospace,monospace }}
  h1,h2,h3 {{ font-family:'Space Grotesk',sans-serif; letter-spacing:-0.02em }}
  .wrap {{ max-width:1120px; margin:0 auto; padding:80px 24px }}
  .hero h1 {{ font-size:64px; margin:0 0 16px }} .hero p {{ color:var(--mut); font-size:18px }}
  .btn {{ display:inline-block; margin-top:24px; background:var(--acc); color:#000; padding:14px 22px; border-radius:999px; text-decoration:none; font-weight:700 }}
  .grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:24px; margin-top:40px }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:16px; padding:24px }}
  .price {{ font-size:36px; font-weight:800 }}
  ul {{ list-style:none; padding:0 }} li {{ padding:6px 0; color:var(--mut) }}
  .bar {{ height:120px; background:linear-gradient(180deg,transparent,rgba(16,185,129,0.15)); border-radius:8px; display:flex; align-items:flex-end; padding:8px; gap:6px }}
  .bar span {{ background:var(--acc); flex:1; border-radius:4px 4px 0 0 }}
</style></head><body><div class='wrap'>"""]
    for b in blocks:
        p = b.get("props", {})
        t = b.get("type")
        if t == "hero":
            parts.append(f"<section class='hero'><h1>{p.get('title','')}</h1><p>{p.get('subtitle','')}</p><a class='btn' href='#'>{p.get('cta','Get Started')}</a></section>")
        elif t == "features":
            items = "".join([f"<div class='card'><h3>{i.get('title','')}</h3><p style='color:var(--mut)'>{i.get('desc','')}</p></div>" for i in p.get("items", [])])
            parts.append(f"<section><h2>{p.get('heading','')}</h2><div class='grid'>{items}</div></section>")
        elif t == "pricing":
            plans = "".join([f"<div class='card'><h3>{pl.get('name','')}</h3><div class='price'>{pl.get('price','')}</div><ul>{''.join([f'<li>• {f}</li>' for f in pl.get('features',[])])}</ul></div>" for pl in p.get("plans", [])])
            parts.append(f"<section><h2>{p.get('heading','')}</h2><div class='grid'>{plans}</div></section>")
        elif t == "chart":
            mx = max([s.get("v", 1) for s in p.get("series", [])] + [1])
            bars = "".join([f"<span style='height:{(s.get('v',0)/mx)*100}%'></span>" for s in p.get("series", [])])
            parts.append(f"<section><h2>{p.get('heading','')}</h2><div class='bar'>{bars}</div></section>")
        elif t == "contact":
            parts.append(f"<section><h2>{p.get('heading','')}</h2><p style='color:var(--mut)'>{p.get('subtitle','')}</p><p>{p.get('email','')}</p></section>")
    parts.append("</div></body></html>")
    return "".join(parts)


async def build_export_files(app_doc: dict) -> dict:
    app_id = app_doc["app_id"]
    pages = await db.pages.find({"app_id": app_id}, {"_id": 0}).to_list(50)
    pages.sort(key=lambda p: (p.get("slug") != "/", p.get("order", 0)))
    theme = {**DEFAULT_THEME, **(app_doc.get("theme") or {})}
    cols = await CMS_HOOKS["public_collections"](app_id)
    embed = f"<script src='{FRONTEND_URL}/api/public/embed.js' data-token='{app_doc.get('preview_token')}' data-origin='{FRONTEND_URL}'></script>" if app_doc.get("preview_token") else ""
    files = {}
    logo = app_doc.get("logo") or ""
    logo_asset = None
    if logo.startswith("/api/public/files/"):
        try:
            from storage import get_object
            data, ct = get_object(logo[len("/api/public/files/"):])
            ext = logo.rsplit(".", 1)[-1] if "." in logo else "png"
            logo_asset = f"assets/logo.{ext}"
            files[f"site/{logo_asset}"] = data
        except Exception as e:
            logger.warning(f"Logo bundle skipped: {e}")
    def _rewrite(html):
        return html.replace(logo, f"/{logo_asset}") if logo_asset else (html.replace(logo, f"{FRONTEND_URL}{logo}") if logo else html)
    for pg in pages:
        fname = "index.html" if pg.get("slug") == "/" else f"{pg['slug'].strip('/')}.html"
        files[f"site/{fname}"] = _rewrite(render_page(app_doc, theme, pg, pages, cols)).replace("</body>", f"{embed}</body>")
    for c in cols:
        for it in c["items"]:
            files[f"site/{c['slug']}/{it['slug']}.html"] = _rewrite(render_item_page(app_doc, theme, c, it, pages)).replace("</body>", f"{embed}</body>")
    files["site/styles.css"] = css(theme)
    files["site/pages.json"] = json.dumps(pages, indent=2)
    files["site/theme.json"] = json.dumps(theme, indent=2)
    files["site/vercel.json"] = json.dumps({"cleanUrls": True}, indent=2)
    readme = f"# {app_doc['name']}\n\nExported from OmniStack AI.\n\n## site/\nStatic multi-page website ({len(pages)} pages). Deploy to Vercel / Netlify / any static host. Includes the AI chat widget embed.\n"
    if app_doc.get("app_spec"):
        for path, content in starter_app_files(app_doc["app_spec"], {**theme, "logo": (f"/{logo_asset}" if logo_asset else (f"{FRONTEND_URL}{logo}" if logo else None))}).items():
            files[f"app/{path}"] = content
        readme += "\n## app/\nLovable-style React + FastAPI starter generated from the App Blueprint (see app/README.md, app/schema.sql for Postgres/Supabase).\n"
    slug = re.sub(r"[^a-z0-9]+", "", app_doc["name"].lower()) or "app"
    files["mobile/capacitor.config.json"] = json.dumps({"appId": f"com.omnistack.{slug}", "appName": app_doc["name"], "webDir": "../site", "server": {"androidScheme": "https"}}, indent=2)
    files["mobile/package.json"] = json.dumps({"name": f"{slug}-mobile", "private": True, "scripts": {"add:ios": "npx cap add ios", "add:android": "npx cap add android", "sync": "npx cap sync", "open:ios": "npx cap open ios", "open:android": "npx cap open android"}, "devDependencies": {"@capacitor/cli": "^6.0.0"}, "dependencies": {"@capacitor/core": "^6.0.0", "@capacitor/ios": "^6.0.0", "@capacitor/android": "^6.0.0"}}, indent=2)
    files["mobile/README.md"] = (f"# {app_doc['name']} — App Store & Google Play\n\nThis folder wraps the exported site as a native app with Capacitor.\n\n"
                                "1. `cd mobile && npm i`\n2. `npm run add:ios` / `npm run add:android`\n3. `npm run sync`\n4. `npm run open:ios` → Xcode → Archive → App Store Connect\n"
                                "5. `npm run open:android` → Android Studio → Build → Generate Signed Bundle (.aab) → Google Play Console\n\n"
                                "Icons/splash: `npx @capacitor/assets generate`. Store listing images: use the AI Media Studio in OmniStack.\n")
    files["README.md"] = readme + "\n## mobile/\nCapacitor wrapper for publishing to the Apple App Store and Google Play (see mobile/README.md).\n"
    return files


@api.get("/apps/{app_id}/export/source")
async def export_source(app_id: str, user: dict = Depends(get_current_user)):
    app_doc = await get_user_app(app_id, user)
    files = await build_export_files(app_doc)
    files = bundle_media(files)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path, content in files.items():
            z.writestr(path, content)
    buf.seek(0)

    await log_activity(app_id, user["user_id"], "export.source", "Exported source bundle (.zip)")
    filename = f"{app_doc['name'].lower().replace(' ', '-')}-source.zip"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@api.post("/apps/{app_id}/export/mobile")
async def export_mobile(app_id: str, platform: str = "ios", user: dict = Depends(get_current_user)):
    """MOCKED native build. Returns a fake job id + steps for UI simulation."""
    await get_user_app(app_id, user)
    ext = "ipa" if platform == "ios" else "aab"
    job = {
        "job_id": new_id("build"),
        "platform": platform,
        "artifact": f"{platform}-build-{new_id('v')}.{ext}",
        "status": "queued",
        "steps": [
            "Fetching source",
            "Bundling assets",
            "Compiling native shell",
            f"Signing {platform.upper()} package",
            "Uploading artifact",
        ],
        "estimated_seconds": 22,
        "created_at": now_utc().isoformat(),
    }
    await log_activity(app_id, user["user_id"], "export.mobile",
                       f"Started MOCKED {platform.upper()} build")
    return job


# ---------- AI Prompt Editor ----------
@api.post("/apps/{app_id}/ai/edit")
async def ai_edit_block(app_id: str, body: AIPromptIn, user: dict = Depends(get_current_user)):
    await GROWTH["require_ai_access"](app_id, user)
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "LLM key missing")

    system_message = (
        "You are a UI block editor. You receive a JSON block config and a user instruction. "
        "Return ONLY the updated block JSON (no markdown fences, no commentary). "
        "Preserve the 'id' and 'type' fields exactly. Modify only the 'props' object per the user's intent. "
        "Keep values concise and production-ready."
    )
    prompt_text = (
        f"USER INSTRUCTION:\n{body.prompt}\n\n"
        f"CURRENT BLOCK JSON:\n{json.dumps(body.block, indent=2)}\n\n"
        "Return updated JSON only."
    )
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"editor-{app_id}-{user['user_id']}",
        system_message=system_message,
    ).with_model("anthropic", "claude-sonnet-5")

    try:
        reply = await chat.send_message(UserMessage(text=prompt_text))
        text = reply.strip() if isinstance(reply, str) else str(reply)
        # strip code fences if present
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        updated = json.loads(text)
        # enforce id/type
        updated["id"] = body.block.get("id", updated.get("id"))
        updated["type"] = body.block.get("type", updated.get("type"))
        await log_activity(app_id, user["user_id"], "ai.edit",
                           f"AI edit: {body.prompt[:80]}")
        return updated
    except json.JSONDecodeError:
        raise HTTPException(500, "AI returned invalid JSON. Try rephrasing your prompt.")
    except Exception as e:
        logger.exception("AI edit failed")
        raise HTTPException(500, f"AI edit failed: {str(e)[:200]}")


# ---------- Health ----------
@api.get("/")
async def root():
    return {"service": "agency-platform", "ok": True}


# ---------- Seed Data ----------
SEED_APPS = [
    {
        "name": "Nexus Commerce",
        "industry": "E-commerce",
        "description": "Headless commerce dashboard with real-time inventory, AI product tagging and multi-currency checkout.",
        "status": "active",
        "tags": ["Stripe", "Next.js", "Postgres"],
        "color": "#10B981",
        "thumbnail": "https://images.unsplash.com/photo-1625838144804-300f3907c110?crop=entropy&cs=srgb&fm=jpg&q=85",
        "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
        "live_url": "https://nexus.example.com",
        "metrics": {"uptime": 99.98, "cpu": 32, "ram": 61, "response_ms": 84, "visitors_24h": 12480},
    },
    {
        "name": "Orbit SaaS Portal",
        "industry": "SaaS Portals",
        "description": "Workflow analytics + AI copilots for B2B customer success teams.",
        "status": "active",
        "tags": ["React", "FastAPI", "Redis"],
        "color": "#06B6D4",
        "thumbnail": "https://images.unsplash.com/photo-1675410202405-5ef270c857d3?crop=entropy&cs=srgb&fm=jpg&q=85",
        "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4",
        "live_url": "https://orbit.example.com",
        "metrics": {"uptime": 99.92, "cpu": 41, "ram": 58, "response_ms": 112, "visitors_24h": 6284},
    },
    {
        "name": "Fleet Command",
        "industry": "Internal Tools",
        "description": "Dispatch console for logistics operators with live map, driver telemetry and SLA alerts.",
        "status": "maintenance",
        "tags": ["Mapbox", "Websockets", "Mongo"],
        "color": "#F59E0B",
        "thumbnail": "https://images.unsplash.com/photo-1758626099012-2904337e9c60?crop=entropy&cs=srgb&fm=jpg&q=85",
        "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4",
        "live_url": "https://fleet.internal.example.com",
        "metrics": {"uptime": 98.4, "cpu": 74, "ram": 82, "response_ms": 208, "visitors_24h": 812},
    },
    {
        "name": "Aura Wellness",
        "industry": "Service Booking",
        "description": "Native iOS + Android booking flow for wellness studios with Stripe payments and Google Calendar sync.",
        "status": "handover",
        "tags": ["React Native", "Stripe", "Twilio"],
        "color": "#A78BFA",
        "thumbnail": "https://images.unsplash.com/photo-1558655146-6c222b05fce4?crop=entropy&cs=srgb&fm=jpg&q=85",
        "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoylikes.mp4",
        "live_url": "https://aura.app",
        "metrics": {"uptime": 99.7, "cpu": 22, "ram": 44, "response_ms": 96, "visitors_24h": 3120},
    },
    {
        "name": "Ledger AI Portfolio",
        "industry": "SaaS Portals",
        "description": "Personal-finance copilot with LLM summaries, Plaid sync and multi-account budgeting.",
        "status": "active",
        "tags": ["Claude", "Plaid", "Recharts"],
        "color": "#F472B6",
        "thumbnail": "https://images.unsplash.com/photo-1625838144804-300f3907c110?crop=entropy&cs=srgb&fm=jpg&q=85",
        "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4",
        "live_url": "https://ledger.ai",
        "metrics": {"uptime": 99.99, "cpu": 18, "ram": 36, "response_ms": 68, "visitors_24h": 9200},
    },
    {
        "name": "Studio Booking",
        "industry": "Service Booking",
        "description": "Multi-tenant booking widget for creative studios with tiered pricing and SMS reminders.",
        "status": "active",
        "tags": ["Twilio", "Vercel", "Stripe"],
        "color": "#34D399",
        "thumbnail": "https://images.unsplash.com/photo-1558655146-6c222b05fce4?crop=entropy&cs=srgb&fm=jpg&q=85",
        "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
        "live_url": "https://studio.example.com",
        "metrics": {"uptime": 99.6, "cpu": 27, "ram": 51, "response_ms": 132, "visitors_24h": 1740},
    },
]

SEED_ACTIVITY = [
    ("deploy.success", "info", "Deployed build 2.14.0 to production"),
    ("error.report", "error", "Payment webhook retried 3× (transient)"),
    ("member.invited", "info", "Invited an editor to the workspace"),
    ("maintenance.window", "warning", "Scheduled maintenance window opened"),
    ("ai.edit", "info", "AI rewrote hero copy with brand voice"),
]


@app.on_event("startup")
async def startup():
    # indexes
    try:
        await db.users.create_index("email", unique=True)
        await db.users.create_index("user_id", unique=True)
        await db.apps.create_index("app_id", unique=True)
        await db.apps.create_index("owner_id")
        await db.pages.create_index("app_id")
        await db.memberships.create_index("app_id")
        await db.activity_logs.create_index("app_id")
        await db.media_assets.create_index("app_id")
        await db.data_destinations.create_index("app_id", unique=True)
        await db.payment_transactions.create_index("session_id", unique=True)
        await db.apps.create_index("preview_token")
    except Exception as e:
        logger.warning(f"index create warning: {e}")

    # seed admin user
    admin_email = os.environ["ADMIN_EMAIL"].lower().strip()
    admin_password = os.environ["ADMIN_PASSWORD"]
    admin = await db.users.find_one({"email": admin_email})
    if not admin:
        admin_id = new_id("user")
        await db.users.insert_one({
            "user_id": admin_id,
            "email": admin_email,
            "name": "Jay Bernabe",
            "role": "owner",
            "password_hash": hash_password(admin_password),
            "auth_provider": "jwt",
            "picture": None,
            "created_at": now_utc().isoformat(),
        })
        admin = await db.users.find_one({"email": admin_email})
    else:
        # ensure password matches env
        if not verify_password(admin_password, admin.get("password_hash", "")):
            await db.users.update_one(
                {"email": admin_email},
                {"$set": {"password_hash": hash_password(admin_password)}}
            )

    admin_id = admin["user_id"]
    existing_count = await db.apps.count_documents({"owner_id": admin_id})
    if existing_count == 0:
        for seed in SEED_APPS:
            app_id = new_id("app")
            doc = {
                "app_id": app_id,
                "owner_id": admin_id,
                "transfer_mode": False,
                "created_at": now_utc().isoformat(),
                "updated_at": now_utc().isoformat(),
                **seed,
            }
            await db.apps.insert_one(doc)
            await db.pages.insert_one({
                "page_id": new_id("pg"),
                "app_id": app_id,
                "name": "Home",
                "slug": "/",
                "blocks": _default_blocks(seed["name"]),
                "updated_at": now_utc().isoformat(),
            })
            for i, (k, sev, msg) in enumerate(SEED_ACTIVITY):
                await db.activity_logs.insert_one({
                    "log_id": new_id("log"),
                    "app_id": app_id,
                    "user_id": admin_id,
                    "kind": k,
                    "severity": sev,
                    "message": msg,
                    "created_at": (now_utc() - timedelta(hours=i * 3 + 1)).isoformat(),
                })
        logger.info(f"Seeded {len(SEED_APPS)} demo apps for {admin_email}")
    await reseed_demo_sites(db, admin_id)
    # Tenant site content is locked to its saved DB state: no retroactive redesign migration ever runs.
    from content_lock import lock_all_existing
    logger.info(f"Content lock applied to {await lock_all_existing(db)} tenant(s)")
    try:
        init_storage()
        logger.info("Object storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")


@app.on_event("shutdown")
async def shutdown():
    client.close()


from extras import register as register_extras
from studio import register as register_studio
from inbox import register as register_inbox
from workflows import register as register_workflows
from cms import register as register_cms
from seed_sites import reseed_demo_sites
register_extras(api, db, get_current_user, get_user_app, log_activity)
WF_HOOKS = register_workflows(api, db, get_current_user, get_user_app, log_activity)
CMS_HOOKS = register_cms(api, db, get_current_user, get_user_app, log_activity, WF_HOOKS)
INBOX_HOOKS = register_inbox(api, db, get_current_user, get_user_app, log_activity, build_export_files, WF_HOOKS)
STUDIO_HOOKS = {**INBOX_HOOKS, **WF_HOOKS, **CMS_HOOKS}
register_studio(api, db, get_current_user, get_user_app, log_activity, STUDIO_HOOKS)
from growth import register as register_growth
GROWTH = register_growth(api, db, get_current_user, get_user_app, log_activity, create_access_token, create_refresh_token, set_auth_cookies, WF_HOOKS["send_email"], WF_HOOKS)
import studio as _studio, extras as _extras
_studio.require_ai_access = GROWTH["require_ai_access"]
_extras.require_ai_access = GROWTH["require_ai_access"]
from templates import register as register_templates
register_templates(api, db, get_current_user, get_user_app, log_activity)
from site_content import register as register_site_content
from content_lock import register as register_content_lock
register_site_content(api, db, get_current_user, get_user_app, log_activity)
register_content_lock(api, db, get_current_user, get_user_app, log_activity)
from page_guard import register as register_page_guard
register_page_guard(api, db, get_current_user, get_user_app, log_activity)
from storage import register as register_storage, init_storage
register_storage(api, db, get_current_user, get_user_app, log_activity, lambda: now_utc().isoformat())
from landing_cms import register as register_landing, is_admin as _is_admin
register_landing(api, db, get_current_user)
from ui_cms import register as register_ui_cms
register_ui_cms(api, db, get_current_user, get_user_app)
from files_lib import register as register_files, bundle_media
register_files(api, db, get_current_user, get_user_app, log_activity)
from data_destinations import register as register_data_destinations
register_data_destinations(api, db, get_current_user, get_user_app, log_activity)
from site_sync import register as register_site_sync
import site_sync as _site_sync
_site_sync.require_ai_access = GROWTH["require_ai_access"]
STUDIO_HOOKS["maybe_site_sync"] = register_site_sync(api, db, get_current_user, get_user_app, log_activity)["maybe_site_sync"]
from web_import import register as register_web_import
import web_import as _web_import
_web_import.require_ai_access = GROWTH["require_ai_access"]
register_web_import(api, db, get_current_user, get_user_app, log_activity)
from followups import register as register_followups
register_followups(api, db, get_current_user, get_user_app, log_activity, WF_HOOKS["send_email"])
from videos import register as register_videos
import videos as _videos
_videos.require_ai_access = GROWTH["require_ai_access"]
VIDEO_HOOKS = register_videos(api, db, get_current_user, get_user_app, log_activity)
_web_import.place_video = VIDEO_HOOKS["place_video"]
_web_import.search_stock = VIDEO_HOOKS["search_stock"]
_web_import.store_video = VIDEO_HOOKS["store_video"]

app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[o.strip() for o in os.environ.get('CORS_ORIGINS', FRONTEND_URL).split(',')],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)
