"""Sign-in extras: email verification, magic links, Microsoft & Yahoo OAuth.

Everything funnels into the app's existing HttpOnly cookie JWT session — no second
session mechanism. Microsoft/Yahoo stay dormant until their credentials are set,
so the buttons can ship before the OAuth apps exist.
"""
import base64
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from jwt import PyJWKClient
from pydantic import BaseModel, EmailStr

logger = logging.getLogger("agency.auth_extra")

EMAIL_BASE_URL = "https://integrations.emergentagent.com"
TOKEN_TTL_MIN = 30
MS_TENANT = os.environ.get("MICROSOFT_TENANT", "common")
MS_DISCOVERY = f"https://login.microsoftonline.com/{MS_TENANT}/v2.0/.well-known/openid-configuration"
MS_ISSUER = f"https://login.microsoftonline.com/{MS_TENANT}/v2.0"
YAHOO_DISCOVERY = "https://api.login.yahoo.com/.well-known/openid-configuration"
YAHOO_ISSUER = "https://api.login.yahoo.com"


def _env(k: str) -> str:
    return (os.environ.get(k) or "").strip()


def _now():
    return datetime.now(timezone.utc)


def _frontend() -> str:
    return _env("FRONTEND_URL").rstrip("/")


def _backend() -> str:
    return _env("BACKEND_PUBLIC_URL").rstrip("/") or _frontend()


def provider_config(name: str):
    if name == "microsoft":
        return _env("MICROSOFT_CLIENT_ID"), _env("MICROSOFT_CLIENT_SECRET")
    return _env("YAHOO_CLIENT_ID"), _env("YAHOO_CLIENT_SECRET")


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def send_email(*, to: str, subject: str, html: str):
    key = _env("EMERGENT_EMAIL_KEY")
    if not key:
        raise HTTPException(500, "Email is not configured")
    payload = {"to": [to], "subject": subject, "html": html,
               "from_name": _env("EMAIL_FROM_NAME") or "Lois-Tech"}
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                headers={"X-Email-Key": key}, json=payload)
    if res.is_error:
        logger.error("email send failed: %s %s", res.status_code, res.text[:200])
        raise HTTPException(502, "Could not send the email — try again in a moment")
    return res.json().get("id")


def _shell(heading: str, body: str, cta_label: str, cta_url: str, brand: str) -> str:
    return (
        '<table role="presentation" width="100%" style="background:#0b0d12;padding:32px 0">'
        '<tr><td align="center"><table role="presentation" width="520" style="max-width:520px;'
        'background:#12151d;border:1px solid #232734;border-radius:16px;font-family:Arial,Helvetica,sans-serif">'
        f'<tr><td style="padding:28px 28px 8px;color:#e8eaf0;font-size:20px;font-weight:700">{escape(heading)}</td></tr>'
        f'<tr><td style="padding:0 28px;color:#a2a9bb;font-size:14px;line-height:22px">{body}</td></tr>'
        f'<tr><td style="padding:24px 28px"><a href="{cta_url}" style="display:inline-block;'
        'background:#10b981;color:#06110c;text-decoration:none;font-weight:700;font-size:14px;'
        f'padding:12px 22px;border-radius:999px">{escape(cta_label)}</a></td></tr>'
        f'<tr><td style="padding:4px 28px 26px;color:#6b7280;font-size:11px;line-height:18px">'
        f'This link expires in {TOKEN_TTL_MIN} minutes and can be used once. '
        f'Sent by {escape(brand)}. We never ask for your password by email.'
        '</td></tr></table></td></tr></table>'
    )


async def send_verification_email(db, email: str, name: str = "") -> str:
    """Used by the signup route so a form registration still proves the address is real."""
    email = email.lower().strip()
    token = secrets.token_urlsafe(32)
    await db.auth_tokens.insert_one({
        "token_hash": _hash(token), "kind": "verify", "email": email,
        "expires_at": (_now() + timedelta(minutes=TOKEN_TTL_MIN)).isoformat(),
        "used": False, "created_at": _now().isoformat()})
    brand = _env("EMAIL_FROM_NAME") or "Lois-Tech"
    await send_email(to=email, subject=f"Confirm your {brand} email address",
                     html=_shell("Confirm your email address",
                                 f"Hi {escape(name or 'there')}, confirm this address to finish "
                                 "setting up your workspace.",
                                 "Confirm email", f"{_backend()}/api/auth/verify?token={token}", brand))
    return token


def register(api, db, get_current_user, create_access_token, create_refresh_token, set_auth_cookies):
    class EmailIn(BaseModel):
        email: EmailStr

    async def _issue(kind: str, email: str) -> str:
        token = secrets.token_urlsafe(32)
        await db.auth_tokens.insert_one({
            "token_hash": _hash(token), "kind": kind, "email": email.lower().strip(),
            "expires_at": (_now() + timedelta(minutes=TOKEN_TTL_MIN)).isoformat(),
            "used": False, "created_at": _now().isoformat()})
        return token

    async def _consume(kind: str, token: str) -> dict:
        doc = await db.auth_tokens.find_one({"token_hash": _hash(token), "kind": kind})
        if not doc or doc.get("used"):
            raise HTTPException(400, "This link has already been used or is invalid")
        if datetime.fromisoformat(doc["expires_at"]) < _now():
            raise HTTPException(400, "This link has expired — request a new one")
        await db.auth_tokens.update_one({"_id": doc["_id"]}, {"$set": {"used": True, "used_at": _now().isoformat()}})
        return doc

    async def _throttle(kind: str, email: str):
        since = (_now() - timedelta(minutes=2)).isoformat()
        recent = await db.auth_tokens.count_documents(
            {"kind": kind, "email": email.lower().strip(), "created_at": {"$gt": since}})
        if recent >= 3:
            raise HTTPException(429, "Too many emails requested — wait a couple of minutes")

    async def _login_response(user: dict, response: Response):
        access = create_access_token(user["user_id"], user["email"])
        refresh = create_refresh_token(user["user_id"])
        set_auth_cookies(response, access, refresh)

    async def _upsert_user(email: str, name: str, provider: str) -> dict:
        email = email.lower().strip()
        user = await db.users.find_one({"email": email})
        if user:
            await db.users.update_one({"email": email}, {"$set": {
                "email_verified": True, "last_login_at": _now().isoformat()},
                "$addToSet": {"auth_providers": provider}})
            return await db.users.find_one({"email": email}, {"_id": 0, "password_hash": 0})
        doc = {"user_id": f"user_{secrets.token_hex(6)}", "email": email,
               "name": name or email.split("@")[0], "role": "owner",
               "auth_provider": provider, "auth_providers": [provider],
               "email_verified": True, "picture": None,
               "created_at": _now().isoformat()}
        await db.users.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    # ---------- which sign-in options exist ----------
    @api.get("/auth/providers")
    async def providers():
        out = {"google": True, "magic_link": bool(_env("EMERGENT_EMAIL_KEY"))}
        for name in ("microsoft", "yahoo"):
            cid, secret = provider_config(name)
            out[name] = bool(cid and secret)
        return out

    # ---------- email verification ----------
    @api.post("/auth/verify/request")
    async def request_verification(body: EmailIn):
        email = body.email.lower().strip()
        user = await db.users.find_one({"email": email}, {"_id": 0, "name": 1, "email_verified": 1})
        if not user:
            return {"ok": True}  # never reveal whether an address is registered
        if user.get("email_verified"):
            return {"ok": True, "already_verified": True}
        await _throttle("verify", email)
        token = await _issue("verify", email)
        brand = _env("EMAIL_FROM_NAME") or "Lois-Tech"
        await send_email(to=email, subject=f"Confirm your {brand} email address",
                         html=_shell("Confirm your email address",
                                     f"Hi {escape(user.get('name') or 'there')}, confirm this address to "
                                     "finish setting up your workspace.",
                                     "Confirm email", f"{_backend()}/api/auth/verify?token={token}", brand))
        return {"ok": True}

    @api.get("/auth/verify")
    async def verify_email(token: str):
        doc = await _consume("verify", token)
        await db.users.update_one({"email": doc["email"]},
                                  {"$set": {"email_verified": True, "verified_at": _now().isoformat()}})
        return RedirectResponse(f"{_frontend()}/login?verified=1")

    # ---------- magic link (sign in AND sign up, no form) ----------
    @api.post("/auth/magic-link")
    async def magic_link(body: EmailIn):
        email = body.email.lower().strip()
        await _throttle("magic", email)
        token = await _issue("magic", email)
        brand = _env("EMAIL_FROM_NAME") or "Lois-Tech"
        exists = await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
        await send_email(to=email, subject=f"Your {brand} sign-in link",
                         html=_shell("Your sign-in link",
                                     "Use the button below to sign in. No password needed."
                                     if exists else
                                     "Use the button below to create your workspace — no form to fill in.",
                                     "Sign in", f"{_backend()}/api/auth/magic?token={token}", brand))
        return {"ok": True, "new_account": not exists}

    @api.get("/auth/magic")
    async def magic_consume(token: str):
        doc = await _consume("magic", token)
        user = await _upsert_user(doc["email"], "", "magic_link")
        response = RedirectResponse(f"{_frontend()}/dashboard")
        await _login_response(user, response)
        return response

    # ---------- Microsoft / Yahoo OAuth ----------
    def _state_cookie(provider: str, state: str, verifier: str, nonce: str) -> str:
        return jwt.encode({"provider": provider, "state": state, "verifier": verifier, "nonce": nonce,
                           "exp": _now() + timedelta(minutes=10)},
                          os.environ["JWT_SECRET"], algorithm="HS256")

    def _read_state(raw, provider: str, returned_state: str) -> dict:
        if not raw:
            raise HTTPException(400, "Missing OAuth state")
        try:
            value = jwt.decode(raw, os.environ["JWT_SECRET"], algorithms=["HS256"])
        except jwt.PyJWTError:
            raise HTTPException(400, "Invalid OAuth state")
        if value.get("provider") != provider or not secrets.compare_digest(value.get("state", ""), returned_state):
            raise HTTPException(400, "OAuth state mismatch")
        return value

    async def _discovery(url: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url)
            res.raise_for_status()
            return res.json()

    async def _start(provider: str):
        cid, secret = provider_config(provider)
        if not (cid and secret):
            return RedirectResponse(f"{_frontend()}/login?provider_unavailable={provider}")
        meta = await _discovery(MS_DISCOVERY if provider == "microsoft" else YAHOO_DISCOVERY)
        state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        verifier = _b64url(secrets.token_bytes(32))
        challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
        params = {"client_id": cid, "response_type": "code",
                  "redirect_uri": f"{_backend()}/api/auth/{provider}/callback",
                  "scope": "openid profile email", "state": state, "nonce": nonce,
                  "code_challenge": challenge, "code_challenge_method": "S256"}
        res = RedirectResponse(f"{meta['authorization_endpoint']}?{urlencode(params)}")
        res.set_cookie("oauth_state", _state_cookie(provider, state, verifier, nonce),
                       max_age=600, httponly=True, secure=True, samesite="lax", path="/api/auth")
        return res

    async def _identity(provider: str, code: str, verifier: str, nonce: str) -> dict:
        cid, secret = provider_config(provider)
        discovery_url = MS_DISCOVERY if provider == "microsoft" else YAHOO_DISCOVERY
        issuer = MS_ISSUER if provider == "microsoft" else YAHOO_ISSUER
        meta = await _discovery(discovery_url)
        data = {"client_id": cid, "client_secret": secret, "grant_type": "authorization_code",
                "code": code, "redirect_uri": f"{_backend()}/api/auth/{provider}/callback",
                "code_verifier": verifier}
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(meta["token_endpoint"], data=data)
            if res.is_error:
                logger.info("%s token exchange failed: %s", provider, res.text[:200])
                raise HTTPException(401, "Provider token exchange failed")
            tokens = res.json()
            jwks = PyJWKClient(meta["jwks_uri"])
            try:
                key = jwks.get_signing_key_from_jwt(tokens["id_token"]).key
                claims = jwt.decode(tokens["id_token"], key, algorithms=["RS256", "RS384", "RS512"],
                                    audience=cid, issuer=issuer,
                                    options={"require": ["exp", "iat", "iss", "aud", "sub"]})
            except jwt.PyJWTError as exc:
                raise HTTPException(401, f"Invalid ID token: {exc}")
            if not secrets.compare_digest(claims.get("nonce", ""), nonce):
                raise HTTPException(401, "Invalid ID-token nonce")
            info = {}
            if meta.get("userinfo_endpoint"):
                ui = await client.get(meta["userinfo_endpoint"],
                                      headers={"Authorization": f"Bearer {tokens['access_token']}"})
                if ui.is_success:
                    info = ui.json()
        merged = {**claims, **info}
        email = (merged.get("email") or merged.get("preferred_username") or "").strip().lower()
        if not email or merged.get("email_verified") is False:
            raise HTTPException(403, "Your provider did not return a verified email address")
        return {"subject": merged["sub"], "email": email, "name": merged.get("name") or ""}

    async def _callback(provider: str, code: str, state: str, raw_state):
        saved = _read_state(raw_state, provider, state)
        ident = await _identity(provider, code, saved["verifier"], saved["nonce"])
        owner = await db.users.find_one(
            {"auth_identities": {"$elemMatch": {"provider": provider, "subject": ident["subject"]}}},
            {"_id": 0, "email": 1})
        if owner and owner["email"] != ident["email"]:
            raise HTTPException(409, "That provider account is already linked to another user")
        user = await _upsert_user(ident["email"], ident["name"], provider)
        await db.users.update_one({"email": ident["email"]}, {"$addToSet": {
            "auth_identities": {"provider": provider, "subject": ident["subject"]}}})
        res = RedirectResponse(f"{_frontend()}/dashboard")
        res.delete_cookie("oauth_state", path="/api/auth")
        await _login_response(user, res)
        return res

    @api.get("/auth/microsoft/start")
    async def microsoft_start():
        return await _start("microsoft")

    @api.get("/auth/yahoo/start")
    async def yahoo_start():
        return await _start("yahoo")

    @api.get("/auth/microsoft/callback")
    async def microsoft_callback(code: str, state: str, oauth_state: str = Cookie(None)):
        return await _callback("microsoft", code, state, oauth_state)

    @api.get("/auth/yahoo/callback")
    async def yahoo_callback(code: str, state: str, oauth_state: str = Cookie(None)):
        return await _callback("yahoo", code, state, oauth_state)
