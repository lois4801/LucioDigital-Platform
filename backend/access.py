"""Owner-only access: public sign in and sign up are closed. Owners get in by email link.

The owner allowlist lives in `settings.owners` (seeded from OWNER_EMAILS / ADMIN_EMAIL). Anyone not on
that list cannot register or log in at all — they only ever see the public landing page.
"""
import os
from datetime import datetime, timezone
from typing import List

from fastapi import Depends, HTTPException
from pydantic import BaseModel, EmailStr

SEED_OWNERS = ["jaybernabe@luciodigital.com", "jlbusiness2020@gmail.com"]


def _env_owners() -> List[str]:
    raw = os.environ.get("OWNER_EMAILS") or ""
    out = [e.strip().lower() for e in raw.split(",") if e.strip()]
    admin = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    if admin:
        out.append(admin)
    return out or SEED_OWNERS


async def owner_emails(db) -> List[str]:
    doc = await db.settings.find_one({"key": "owners"}, {"_id": 0})
    stored = [e.lower().strip() for e in ((doc or {}).get("emails") or [])]
    return sorted(set(stored) | set(_env_owners()) | set(SEED_OWNERS))


async def is_owner(db, email: str) -> bool:
    return (email or "").lower().strip() in await owner_emails(db)


def register(api, db, get_current_user, log_activity):

    class OwnerIn(BaseModel):
        email: EmailStr

    async def _require_owner(user: dict) -> dict:
        if not await is_owner(db, user.get("email")):
            raise HTTPException(403, "Owners only")
        return user

    @api.get("/public/access")
    async def public_access():
        """Tells the frontend that public auth is closed, so it hides every sign-in affordance."""
        return {"public_signup": False, "public_login": False, "owner_login_path": "/lucio-admin"}

    @api.get("/admin/owners")
    async def list_owners(user: dict = Depends(get_current_user)):
        await _require_owner(user)
        emails = await owner_emails(db)
        rows = []
        for e in emails:
            u = await db.users.find_one({"email": e}, {"_id": 0, "user_id": 1, "name": 1, "last_login_at": 1})
            rows.append({"email": e, "has_account": bool(u), "name": (u or {}).get("name") or "",
                         "last_login_at": (u or {}).get("last_login_at"),
                         "locked": e in set(SEED_OWNERS) | set(_env_owners())})
        return {"owners": rows, "you": (user.get("email") or "").lower()}

    @api.post("/admin/owners")
    async def add_owner(body: OwnerIn, user: dict = Depends(get_current_user)):
        await _require_owner(user)
        email = str(body.email).lower().strip()
        doc = await db.settings.find_one({"key": "owners"}, {"_id": 0}) or {}
        emails = sorted(set([e.lower() for e in (doc.get("emails") or [])] + [email]))
        await db.settings.update_one({"key": "owners"},
                                     {"$set": {"emails": emails, "updated_at": datetime.now(timezone.utc).isoformat()}},
                                     upsert=True)
        # Give them full platform access immediately — no signup, no payment.
        await db.users.update_one({"email": email}, {"$set": {"membership": {
            "status": "active", "grandfathered": True, "manual": True, "suspended": False, "welcomed": True}}})
        await log_activity(None, user["user_id"], "owner.add", f"Granted admin access to {email}")
        return await list_owners(user)

    @api.delete("/admin/owners/{email}")
    async def remove_owner(email: str, user: dict = Depends(get_current_user)):
        await _require_owner(user)
        email = email.lower().strip()
        if email in set(SEED_OWNERS) | set(_env_owners()):
            raise HTTPException(400, "That owner is permanent and cannot be removed")
        doc = await db.settings.find_one({"key": "owners"}, {"_id": 0}) or {}
        emails = [e for e in (doc.get("emails") or []) if e.lower() != email]
        await db.settings.update_one({"key": "owners"}, {"$set": {"emails": emails}}, upsert=True)
        await log_activity(None, user["user_id"], "owner.remove", f"Removed admin access for {email}")
        return await list_owners(user)
