"""Lucio Dev Agent Phase 9 — persist Browser QA evidence in Dev Agent sessions.

The Lucio backend requests Chromium QA from Nexus Runner using the existing service-to-service
credential, stores bounded QA evidence on the session, and optionally persists screenshot bytes
through Lucio's configured object storage. No runner credential is returned to the browser.
"""
from __future__ import annotations

import base64
import os
import uuid
from datetime import datetime, timezone
from typing import List

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from storage import put_object

RUNNER_URL = (os.environ.get("NEXUS_RUNNER_URL") or "").rstrip("/")
RUNNER_SECRET = (os.environ.get("NEXUS_RUNNER_SECRET") or "").strip()


class BrowserQAIn(BaseModel):
    path: str = Field(default="/", max_length=500)
    expected_text: List[str] = Field(default_factory=list, max_length=20)
    viewport_width: int = Field(default=1440, ge=320, le=2560)
    viewport_height: int = Field(default=900, ge=320, le=2000)
    screenshot: bool = True
    fail_on_console_errors: bool = True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _headers() -> dict:
    if not RUNNER_SECRET:
        raise HTTPException(503, "Nexus Runner credential is not configured")
    return {"Authorization": f"Bearer {RUNNER_SECRET}"}


async def _runner(method: str, path: str, body: dict | None = None, timeout: float = 65.0) -> dict:
    if not RUNNER_URL:
        raise HTTPException(503, "Nexus Runner is not configured")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method, f"{RUNNER_URL}{path}", headers=_headers(), json=body)
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Nexus Runner browser QA request failed: {str(exc)[:300]}")
    try:
        payload = response.json()
    except Exception:
        payload = {"detail": response.text[:1200]}
    if response.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else payload
        raise HTTPException(response.status_code if response.status_code < 500 else 502, str(detail)[:1200])
    return payload if isinstance(payload, dict) else {"data": payload}


async def _append_event(db, session_id: str, kind: str, message: str, data: dict):
    event = {
        "event_id": f"evt_{uuid.uuid4().hex[:14]}",
        "at": _now(),
        "kind": kind,
        "message": message[:1200],
        "data": data,
    }
    await db.dev_agent_sessions.update_one(
        {"session_id": session_id},
        {"$push": {"events": {"$each": [event], "$slice": -220}}, "$set": {"updated_at": _now()}},
    )


def register(api, db, get_current_user):
    async def get_session(app_id: str, session_id: str, user: dict) -> dict:
        app = await db.apps.find_one({"app_id": app_id}, {"_id": 0, "owner_id": 1})
        if not app:
            raise HTTPException(404, "App not found")
        if app.get("owner_id") != user.get("user_id"):
            membership = await db.memberships.find_one({"app_id": app_id, "user_id": user.get("user_id")}, {"_id": 0})
            if not membership:
                raise HTTPException(403, "No access to this app")
        session = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(404, "Dev Agent session not found")
        return session

    @api.get("/dev-agent/browser-qa")
    async def browser_qa_status(user: dict = Depends(get_current_user)):
        configured = bool(RUNNER_URL and RUNNER_SECRET)
        if not configured:
            return {"configured": False, "available": False, "engine": None}
        try:
            status = await _runner("GET", "/v1/browser-qa/status", timeout=12.0)
            return {"configured": True, **status}
        except HTTPException as exc:
            return {"configured": True, "available": False, "engine": "chromium", "detail": str(exc.detail)[:500]}

    @api.post("/apps/{app_id}/dev-agent/sessions/{session_id}/browser-qa")
    async def run_browser_qa(app_id: str, session_id: str, body: BrowserQAIn, user: dict = Depends(get_current_user)):
        session = await get_session(app_id, session_id, user)
        workspace_id = session.get("workspace_id")
        if not workspace_id:
            raise HTTPException(409, "This Dev Agent session has no active Nexus workspace")
        preview = session.get("preview") or {}
        if not preview.get("running"):
            raise HTTPException(409, "Start a live sandbox preview before running Browser QA")

        result = await _runner("POST", f"/v1/workspaces/{workspace_id}/browser-qa", {
            "path": body.path,
            "expected_text": body.expected_text,
            "viewport_width": body.viewport_width,
            "viewport_height": body.viewport_height,
            "screenshot": body.screenshot,
            "fail_on_console_errors": body.fail_on_console_errors,
        }, timeout=70.0)

        screenshot_b64 = result.pop("screenshot_base64", None)
        screenshot = None
        if screenshot_b64:
            try:
                raw = base64.b64decode(screenshot_b64, validate=True)
                if len(raw) <= 2_000_000:
                    path = f"omnistack/dev-agent/browser-qa/{app_id}/{session_id}/{uuid.uuid4().hex}.png"
                    stored = put_object(path, raw, "image/png")
                    screenshot = {
                        "storage_path": stored.get("path") or path,
                        "size": stored.get("size", len(raw)),
                        "url": f"/api/public/files/{stored.get('path') or path}",
                    }
            except Exception:
                screenshot = None

        evidence = {
            **result,
            "checked_at": _now(),
            "checked_by": user.get("user_id"),
            "path": body.path,
            "screenshot": screenshot,
        }
        await db.dev_agent_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"browser_qa": evidence, "updated_at": _now()}},
        )
        await _append_event(
            db,
            session_id,
            "browser_qa_pass" if evidence.get("ok") else "browser_qa_fail",
            "Chromium Browser QA passed" if evidence.get("ok") else "Chromium Browser QA found runtime issues",
            {
                "ok": bool(evidence.get("ok")),
                "status": evidence.get("status"),
                "page_errors": len(evidence.get("page_errors") or []),
                "console_errors": len(evidence.get("console_errors") or []),
                "failed_requests": len(evidence.get("failed_requests") or []),
                "missing_text": evidence.get("missing_text") or [],
                "screenshot_url": (screenshot or {}).get("url"),
            },
        )
        return evidence

    @api.get("/apps/{app_id}/dev-agent/sessions/{session_id}/browser-qa")
    async def get_browser_qa(app_id: str, session_id: str, user: dict = Depends(get_current_user)):
        session = await get_session(app_id, session_id, user)
        return session.get("browser_qa") or {}

    return {"configured": bool(RUNNER_URL and RUNNER_SECRET), "runner_url_set": bool(RUNNER_URL)}
