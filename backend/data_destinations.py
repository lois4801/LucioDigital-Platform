import asyncio
import base64
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Literal, Optional
from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("agency.data_destinations")

Provider = Literal[
    "platform",
    "postgres",
    "supabase",
    "rest_api",
    "google_drive",
    "dropbox",
    "onedrive",
]

TESTABLE_PROVIDERS = {"platform", "postgres", "supabase", "rest_api"}


class DestinationIn(BaseModel):
    provider: Provider = "platform"
    label: str = ""
    configuration: Dict[str, str] = Field(default_factory=dict)
    secrets: Dict[str, str] = Field(default_factory=dict)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fernet() -> Fernet:
    secret = os.environ["JWT_SECRET"].encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def _encrypt(value: Dict[str, str]) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode()
    return _fernet().encrypt(raw).decode()


def _decrypt(value: str) -> Dict[str, str]:
    if not value:
        return {}
    try:
        decoded = _fernet().decrypt(value.encode()).decode()
        parsed = json.loads(decoded)
        return parsed if isinstance(parsed, dict) else {}
    except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _clean(values: Dict[str, str], max_value: int = 32000) -> Dict[str, str]:
    cleaned = {}
    for key, value in values.items():
        safe_key = "".join(c for c in str(key) if c.isalnum() or c in "_-")[:80]
        if safe_key and isinstance(value, str) and value.strip():
            cleaned[safe_key] = value.strip()[:max_value]
    return cleaned


def _missing(provider: str, config: Dict[str, str], secrets: Dict[str, str]) -> list[str]:
    if provider == "platform":
        return []
    if provider in {"postgres", "supabase"}:
        return [] if secrets.get("connection_uri") else ["connection_uri"]
    if provider == "rest_api":
        needed = [] if config.get("base_url") else ["base_url"]
        mode = config.get("auth_mode", "bearer")
        if mode == "bearer" and not secrets.get("token"):
            needed.append("token")
        if mode == "headers" and not secrets.get("headers_json"):
            needed.append("headers_json")
        return needed
    if provider == "google_drive":
        if config.get("connection_mode") == "oauth":
            return [key for key, value in {
                "client_id": config.get("client_id"),
                "client_secret": secrets.get("client_secret"),
            }.items() if not value]
        return [] if secrets.get("service_account_json") else ["service_account_json"]
    if provider == "dropbox":
        return [key for key, value in {
            "app_key": config.get("app_key"),
            "app_secret": secrets.get("app_secret"),
        }.items() if not value]
    if provider == "onedrive":
        return [key for key, value in {
            "entra_tenant_id": config.get("entra_tenant_id"),
            "client_id": config.get("client_id"),
            "client_secret": secrets.get("client_secret"),
            "drive_id": config.get("drive_id"),
            "root_item_id": config.get("root_item_id"),
        }.items() if not value]
    return ["provider"]


def _is_valid_database_uri(uri: str, provider: str) -> bool:
    parsed = urlparse(uri)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        return False
    if provider == "supabase":
        return parsed.hostname.endswith("pooler.supabase.com") and parsed.port == 6543
    return True


def _public(doc: Optional[dict]) -> dict:
    if not doc:
        return {
            "provider": "platform",
            "label": "LucioDigital workspace",
            "status": "active",
            "configuration": {},
            "secret_fields": [],
            "missing_fields": [],
            "can_test": True,
        }
    secrets = _decrypt(doc.get("secrets_encrypted", ""))
    provider = doc.get("provider", "platform")
    config = doc.get("configuration") or {}
    return {
        "provider": provider,
        "label": doc.get("label") or provider.replace("_", " ").title(),
        "status": doc.get("status", "needs_credentials"),
        "configuration": config,
        "secret_fields": sorted(secrets.keys()),
        "missing_fields": _missing(provider, config, secrets),
        "can_test": provider in TESTABLE_PROVIDERS and not _missing(provider, config, secrets),
        "last_tested_at": doc.get("last_tested_at"),
        "last_test_message": doc.get("last_test_message"),
    }


def register(api, db, get_current_user, get_user_app, log_activity):
    async def _editable(app_id: str, user: dict) -> dict:
        app_doc = await get_user_app(app_id, user)
        is_platform_admin = (
            (user.get("email") or "").lower().strip()
            == (os.environ.get("ADMIN_EMAIL") or "").lower().strip()
        )
        if app_doc["owner_id"] == user["user_id"] or is_platform_admin:
            return app_doc
        membership = await db.memberships.find_one(
            {"app_id": app_id, "user_id": user["user_id"]},
            {"_id": 0, "role": 1},
        )
        if membership and membership.get("role") == "admin":
            return app_doc
        raise HTTPException(403, "Only this client's owner or admin can manage data storage")

    @api.get("/apps/{app_id}/data-destination")
    async def get_destination(app_id: str, user: dict = Depends(get_current_user)):
        await _editable(app_id, user)
        doc = await db.data_destinations.find_one({"app_id": app_id}, {"_id": 0})
        return _public(doc)

    @api.put("/apps/{app_id}/data-destination")
    async def save_destination(
        app_id: str,
        body: DestinationIn,
        user: dict = Depends(get_current_user),
    ):
        await _editable(app_id, user)
        existing = await db.data_destinations.find_one({"app_id": app_id}, {"_id": 0})
        config = _clean(body.configuration, max_value=1000)
        incoming_secrets = _clean(body.secrets)
        existing_secrets = _decrypt(existing.get("secrets_encrypted", "")) if existing else {}
        if existing and existing.get("provider") == body.provider:
            secrets = {**existing_secrets, **incoming_secrets}
        else:
            secrets = incoming_secrets

        if body.provider in {"postgres", "supabase"} and secrets.get("connection_uri"):
            if not _is_valid_database_uri(secrets["connection_uri"], body.provider):
                if body.provider == "supabase":
                    raise HTTPException(
                        400,
                        "Use the Supabase Transaction Pooler URI on port 6543, not a direct URI.",
                    )
                raise HTTPException(400, "Use a valid postgresql:// or postgres:// connection URI.")

        if body.provider == "rest_api" and config.get("base_url"):
            parsed = urlparse(config["base_url"])
            if parsed.scheme != "https" or not parsed.netloc:
                raise HTTPException(400, "Custom API URLs must use HTTPS.")

        missing = _missing(body.provider, config, secrets)
        status = "active" if body.provider == "platform" else (
            "needs_credentials" if missing else "ready_to_verify"
        )
        doc = {
            "app_id": app_id,
            "provider": body.provider,
            "label": (body.label or body.provider.replace("_", " ").title()).strip()[:100],
            "configuration": config,
            "secrets_encrypted": _encrypt(secrets),
            "status": status,
            "updated_at": now_iso(),
            "updated_by": user["user_id"],
        }
        await db.data_destinations.update_one({"app_id": app_id}, {"$set": doc}, upsert=True)
        await log_activity(
            app_id,
            user["user_id"],
            "data.destination.saved",
            f"Set data destination to {doc['label']}",
        )
        return _public(doc)

    @api.delete("/apps/{app_id}/data-destination")
    async def reset_destination(app_id: str, user: dict = Depends(get_current_user)):
        await _editable(app_id, user)
        await db.data_destinations.delete_one({"app_id": app_id})
        await log_activity(
            app_id,
            user["user_id"],
            "data.destination.reset",
            "Returned data storage to the LucioDigital workspace",
        )
        return _public(None)

    @api.post("/apps/{app_id}/data-destination/test")
    async def test_destination(app_id: str, user: dict = Depends(get_current_user)):
        await _editable(app_id, user)
        doc = await db.data_destinations.find_one({"app_id": app_id}, {"_id": 0})
        public = _public(doc)
        provider = public["provider"]
        if provider == "platform":
            return {"ok": True, "message": "LucioDigital workspace is active"}
        if not public["can_test"]:
            raise HTTPException(409, "Add the required secure connection details before testing.")

        secrets = _decrypt((doc or {}).get("secrets_encrypted", ""))
        config = (doc or {}).get("configuration") or {}
        try:
            if provider in {"postgres", "supabase"}:
                def check_postgres():
                    import psycopg2

                    with psycopg2.connect(secrets["connection_uri"], connect_timeout=7) as conn:
                        with conn.cursor() as cursor:
                            cursor.execute("SELECT 1")
                            cursor.fetchone()

                await asyncio.to_thread(check_postgres)
                message = "Database connection verified"
            else:
                headers = {}
                if config.get("auth_mode", "bearer") == "bearer":
                    headers["Authorization"] = f"Bearer {secrets['token']}"
                elif config.get("auth_mode") == "headers":
                    headers = json.loads(secrets["headers_json"])
                    if not isinstance(headers, dict):
                        raise ValueError("Custom headers must be a JSON object")
                async with httpx.AsyncClient(timeout=12, follow_redirects=False) as client:
                    response = await client.get(config["base_url"], headers=headers)
                if response.status_code >= 400:
                    raise RuntimeError(f"Endpoint returned {response.status_code}")
                message = "Custom workspace API is reachable"
        except Exception as exc:
            logger.info("Data destination test failed for %s: %s", app_id, type(exc).__name__)
            await db.data_destinations.update_one(
                {"app_id": app_id},
                {"$set": {"status": "connection_failed", "last_tested_at": now_iso()}},
            )
            raise HTTPException(502, "Connection failed. Check the credentials, host and network access.")

        tested_at = now_iso()
        await db.data_destinations.update_one(
            {"app_id": app_id},
            {"$set": {
                "status": "connected",
                "last_tested_at": tested_at,
                "last_test_message": message,
            }},
        )
        return {"ok": True, "message": message, "tested_at": tested_at}