"""Lucio Dev Agent Phase 10 — bounded Browser QA self-healing.

A Browser QA failure can be handed back to the existing Dev Agent coding model as structured
runtime evidence. The repair loop is deliberately bounded to avoid runaway token/tool usage.
After repairs, Lucio reruns normal project verification and Chromium QA before updating the
session. Production remains untouched.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from dev_agent import _next_action, _runner, _safe_event_value

ALLOWED_TOOLS = {"read_file", "search_code", "write_file", "replace_text", "run_command", "git_diff", "git_status"}


class BrowserHealIn(BaseModel):
    max_repair_steps: int = Field(default=5, ge=1, le=8)
    path: str = Field(default="/", max_length=500)
    expected_text: List[str] = Field(default_factory=list, max_length=20)
    viewport_width: int = Field(default=1440, ge=320, le=2560)
    viewport_height: int = Field(default=900, ge=320, le=2000)
    fail_on_console_errors: bool = True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:14]}"


async def _event(db, session_id: str, kind: str, message: str, data: Dict[str, Any] | None = None):
    event = {"event_id": _id("evt"), "at": _now(), "kind": kind, "message": message[:1200]}
    if data:
        event["data"] = _safe_event_value(data)
    await db.dev_agent_sessions.update_one(
        {"session_id": session_id},
        {"$push": {"events": {"$each": [event], "$slice": -220}}, "$set": {"updated_at": _now()}},
    )


def _evidence_packet(browser_qa: dict) -> str:
    packet = {
        "status": browser_qa.get("status"),
        "title": browser_qa.get("title"),
        "missing_text": browser_qa.get("missing_text") or [],
        "console_errors": (browser_qa.get("console_errors") or [])[:20],
        "page_errors": (browser_qa.get("page_errors") or [])[:20],
        "failed_requests": (browser_qa.get("failed_requests") or [])[:20],
        "body_text_excerpt": str(browser_qa.get("body_text") or "")[:5000],
        "viewport": browser_qa.get("viewport"),
    }
    return json.dumps(packet, ensure_ascii=False)[:14000]


async def _qa(workspace_id: str, body: BrowserHealIn) -> dict:
    return await _runner(
        "POST",
        f"/v1/workspaces/{workspace_id}/browser-qa",
        body={
            "path": body.path,
            "expected_text": body.expected_text,
            "viewport_width": body.viewport_width,
            "viewport_height": body.viewport_height,
            "screenshot": False,
            "fail_on_console_errors": body.fail_on_console_errors,
        },
        timeout=70.0,
    )


def register(api, db, get_current_user):
    async def get_session(app_id: str, session_id: str, user: dict) -> dict:
        app = await db.apps.find_one({"app_id": app_id}, {"_id": 0, "owner_id": 1})
        if not app:
            raise HTTPException(404, "App not found")
        if app.get("owner_id") != user.get("user_id"):
            membership = await db.memberships.find_one({"app_id": app_id, "user_id": user.get("user_id")}, {"_id": 0}) or {}
            if membership.get("role") not in {"owner", "admin", "editor"}:
                raise HTTPException(403, "Editor access is required for Browser QA repair")
        session = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(404, "Dev Agent session not found")
        return session

    @api.post("/apps/{app_id}/dev-agent/sessions/{session_id}/browser-self-heal")
    async def browser_self_heal(app_id: str, session_id: str, body: BrowserHealIn, user: dict = Depends(get_current_user)):
        session = await get_session(app_id, session_id, user)
        workspace_id = session.get("workspace_id")
        if not workspace_id:
            raise HTTPException(409, "This Dev Agent session has no active Nexus workspace")
        preview = session.get("preview") or {}
        if not preview.get("running"):
            raise HTTPException(409, "A running sandbox preview is required before Browser QA repair")
        if session.get("status") in {"running", "queued", "preparing", "planning"}:
            raise HTTPException(409, "Wait for the current Dev Agent execution to finish before Browser QA repair")

        initial = await _qa(workspace_id, body)
        await db.dev_agent_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"browser_qa": {**initial, "checked_at": _now(), "path": body.path}, "updated_at": _now()}},
        )
        if initial.get("ok"):
            await _event(db, session_id, "browser_qa_pass", "Chromium Browser QA passed; no repair was needed", {"status": initial.get("status")})
            return {"ok": True, "repaired": False, "browser_qa": initial, "verification": session.get("verification")}

        previous_attempts = int(session.get("browser_repair_attempts") or 0)
        if previous_attempts >= 2:
            raise HTTPException(409, "Browser self-healing limit reached for this session. Review the remaining issue manually or start a follow-up Dev Agent instruction.")

        await db.dev_agent_sessions.update_one(
            {"session_id": session_id},
            {"$inc": {"browser_repair_attempts": 1}, "$set": {"updated_at": _now()}},
        )
        await _event(db, session_id, "browser_repair", "Browser QA failed; starting bounded runtime repair", {
            "attempt": previous_attempts + 1,
            "console_errors": len(initial.get("console_errors") or []),
            "page_errors": len(initial.get("page_errors") or []),
            "failed_requests": len(initial.get("failed_requests") or []),
            "missing_text": initial.get("missing_text") or [],
        })

        goal = session.get("goal") or "Repair the application so Browser QA passes without regressing existing behavior."
        plan = session.get("plan") or {}
        inspection = session.get("inspection") or {}
        transcript: List[dict] = []
        evidence = _evidence_packet(initial)

        for step in range(1, body.max_repair_steps + 1):
            action = await _next_action(
                app_id,
                session_id,
                goal,
                plan,
                inspection,
                transcript,
                repair_context=(
                    "BROWSER QA FAILURE. Fix only the demonstrated runtime issue(s), preserve working behavior, "
                    "and do not invent success. Evidence:\n" + evidence
                ),
            )
            tool = str(action.get("tool") or "").strip()
            tool_input = action.get("input") if isinstance(action.get("input"), dict) else {}
            reason = str(action.get("reason") or "")[:1200]
            await _event(db, session_id, "browser_repair_action", f"Browser repair step {step}: {tool or 'invalid action'}", {
                "reason": reason,
                "input": tool_input,
                "model": action.get("model"),
            })
            if tool == "done":
                break
            if tool not in ALLOWED_TOOLS:
                observation = {"ok": False, "error": f"Unknown or disallowed repair tool: {tool}"}
            else:
                try:
                    observation = await _runner(
                        "POST",
                        f"/v1/workspaces/{workspace_id}/tool",
                        body={"tool": tool, "input": tool_input},
                        timeout=240.0,
                    )
                except HTTPException as exc:
                    observation = {"ok": False, "error": str(exc.detail)[:2000]}
            transcript.append({
                "repair_step": step,
                "action": {"tool": tool, "input": tool_input, "reason": reason},
                "observation": _safe_event_value(observation),
            })
            await _event(db, session_id, "browser_repair_result", f"{tool} {'succeeded' if observation.get('ok', True) else 'failed'}", observation)

        config = session.get("config") or {}
        commands = config.get("verify_commands") or []
        await _event(db, session_id, "verification", "Rerunning automated verification after Browser QA repair")
        verification = await _runner(
            "POST",
            f"/v1/workspaces/{workspace_id}/verify",
            body={"commands": commands},
            timeout=900.0,
        )
        if not verification.get("ok"):
            await db.dev_agent_sessions.update_one(
                {"session_id": session_id},
                {"$set": {"verification": verification, "updated_at": _now()}},
            )
            await _event(db, session_id, "browser_repair_failed", "Browser repair caused or revealed a normal verification failure", verification)
            return {"ok": False, "repaired": True, "verification": verification, "browser_qa": initial}

        final_qa = await _qa(workspace_id, body)
        browser_record = {**final_qa, "checked_at": _now(), "path": body.path, "self_healed": bool(final_qa.get("ok"))}
        diff = await _runner(
            "POST",
            f"/v1/workspaces/{workspace_id}/tool",
            body={"tool": "git_diff", "input": {}},
            timeout=90.0,
        )
        await db.dev_agent_sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "verification": verification,
                "browser_qa": browser_record,
                "diff": diff,
                "updated_at": _now(),
            }},
        )
        await _event(
            db,
            session_id,
            "browser_repair_pass" if final_qa.get("ok") else "browser_repair_incomplete",
            "Browser QA passed after bounded self-healing" if final_qa.get("ok") else "Browser QA still reports runtime issues after bounded self-healing",
            {
                "ok": bool(final_qa.get("ok")),
                "status": final_qa.get("status"),
                "console_errors": len(final_qa.get("console_errors") or []),
                "page_errors": len(final_qa.get("page_errors") or []),
                "failed_requests": len(final_qa.get("failed_requests") or []),
                "missing_text": final_qa.get("missing_text") or [],
            },
        )
        return {"ok": bool(final_qa.get("ok")), "repaired": True, "verification": verification, "browser_qa": browser_record, "diff": diff}

    return {"registered": True, "max_session_repair_attempts": 2}
