"""Lucio Dev Agent — Goal -> Working App orchestration layer.

The production API never executes generated code itself. All filesystem and process tools are
delegated to the separately deployed Nexus Runner service. Sessions are durable in MongoDB so
the UI can poll, resume, review diffs and approve/reject a run.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("agency.dev_agent")

RUNNER_URL = (os.environ.get("NEXUS_RUNNER_URL") or "").rstrip("/")
RUNNER_SECRET = (os.environ.get("NEXUS_RUNNER_SECRET") or "").strip()
MAX_STEPS = max(3, min(40, int(os.environ.get("DEV_AGENT_MAX_STEPS", "16"))))
MAX_EVENT_CHARS = max(1000, min(24000, int(os.environ.get("DEV_AGENT_EVENT_CHARS", "9000"))))


class DevConfigIn(BaseModel):
    repo_url: Optional[str] = None
    branch: str = "main"
    preview_argv: Optional[List[str]] = None
    verify_commands: Optional[List[List[str]]] = None


class SessionCreateIn(BaseModel):
    goal: str = Field(min_length=5, max_length=12000)
    repo_url: Optional[str] = None
    branch: Optional[str] = None
    auto_execute: bool = False


class ExecuteIn(BaseModel):
    max_steps: int = Field(default=16, ge=3, le=40)
    start_preview: bool = True


class ContinueIn(BaseModel):
    instruction: str = Field(min_length=3, max_length=8000)
    max_steps: int = Field(default=12, ge=3, le=40)
    start_preview: bool = True


class DecisionIn(BaseModel):
    note: str = Field(default="", max_length=2000)
    cleanup_workspace: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:14]}"


def _clean_repo_url(value: str) -> str:
    value = (value or "").strip()
    if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?", value):
        raise HTTPException(400, "Repository must be a GitHub https URL such as https://github.com/owner/repo")
    if "@" in value.split("github.com", 1)[0]:
        raise HTTPException(400, "Do not put credentials in the repository URL")
    return value.rstrip("/").removesuffix(".git")


def _runner_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {RUNNER_SECRET}"} if RUNNER_SECRET else {}


async def _runner(method: str, path: str, *, body: Optional[dict] = None, timeout: float = 180.0) -> dict:
    if not RUNNER_URL:
        raise HTTPException(503, "NEXUS_RUNNER_URL is not configured. Deploy the runner service before executing code.")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.request(method, f"{RUNNER_URL}{path}", json=body, headers=_runner_headers())
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Nexus Runner is unreachable: {str(exc)[:220]}")
    try:
        payload = res.json()
    except Exception:
        payload = {"detail": res.text[:1200]}
    if res.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else str(payload)
        raise HTTPException(res.status_code, f"Runner: {str(detail)[:1200]}")
    return payload if isinstance(payload, dict) else {"result": payload}


async def _runner_health() -> dict:
    if not RUNNER_URL:
        return {"configured": False, "reachable": False}
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            res = await client.get(f"{RUNNER_URL}/health")
        return {"configured": True, "reachable": res.status_code == 200, "detail": res.json() if res.status_code == 200 else None}
    except Exception:
        return {"configured": True, "reachable": False}


def _json_object(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start:end+1])
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    raise ValueError("Model did not return a valid JSON object")


def _safe_event_value(value: Any) -> Any:
    if isinstance(value, str):
        return value[:MAX_EVENT_CHARS]
    if isinstance(value, list):
        return [_safe_event_value(v) for v in value[:80]]
    if isinstance(value, dict):
        return {str(k)[:120]: _safe_event_value(v) for k, v in list(value.items())[:80]}
    return value


async def _push_event(db, session_id: str, kind: str, message: str, data: Optional[dict] = None):
    event = {"event_id": _id("evt"), "at": _now(), "kind": kind, "message": message[:1200]}
    if data:
        event["data"] = _safe_event_value(data)
    await db.dev_agent_sessions.update_one(
        {"session_id": session_id},
        {"$push": {"events": {"$each": [event], "$slice": -220}}, "$set": {"updated_at": _now()}},
    )


async def _set_session(db, session_id: str, **updates):
    updates["updated_at"] = _now()
    await db.dev_agent_sessions.update_one({"session_id": session_id}, {"$set": updates})


async def _plan(app_id: str, goal: str, inspection: dict, session_id: str) -> Dict[str, Any]:
    from ai_models import run_text
    system = """You are the planning lead for Lucio Dev Agent, an autonomous software-development system.
Return JSON only. Study the repository manifest before planning. Preserve working behavior unless the goal requires a change.
Create the smallest production-quality plan that satisfies the goal. Never request or expose secrets.
Schema: {"summary":"...","architecture":"...","risks":["..."],"tasks":[{"id":"T1","title":"...","description":"...","agent":"frontend|backend|database|qa|devops|reviewer","acceptance":["..."],"files_hint":["..."]}],"verification":["..."]}.
Use 1-12 ordered tasks. Include tests/verification in the plan."""
    prompt = f"GOAL:\n{goal}\n\nREPOSITORY INSPECTION:\n{json.dumps(inspection, ensure_ascii=False)[:30000]}"
    text, model = await run_text(app_id, "site_generation", system, prompt, f"dev-plan-{session_id}")
    plan = _json_object(text)
    plan["model"] = model
    return plan


ACTION_SYSTEM = """You are the coding executor inside Lucio Dev Agent. You work one safe tool action at a time.
Return exactly one JSON object and no markdown. Read relevant code before changing it. Keep changes tightly scoped to the user's goal.
Never inspect .env, credentials, tokens, .git metadata, SSH keys, cloud credentials, or production secrets.
Available actions:
- {"tool":"read_file","input":{"path":"...","start_line":1,"end_line":300},"reason":"..."}
- {"tool":"search_code","input":{"query":"..."},"reason":"..."}
- {"tool":"write_file","input":{"path":"...","content":"complete file contents"},"reason":"..."}
- {"tool":"replace_text","input":{"path":"...","old":"exact existing text","new":"replacement text"},"reason":"..."}
- {"tool":"run_command","input":{"argv":["npm","run","build"],"cwd":"."},"reason":"..."}
- {"tool":"git_diff","input":{},"reason":"..."}
- {"tool":"git_status","input":{},"reason":"..."}
- {"tool":"done","input":{},"reason":"why implementation is ready for verification"}
Do not use shell operators, redirections, curl/wget, or arbitrary system commands. Prefer replace_text for small edits and write_file for new/small files.
When enough evidence exists that the requested implementation is complete, return tool=done."""


async def _next_action(app_id: str, session_id: str, goal: str, plan: dict, inspection: dict,
                       transcript: List[dict], repair_context: str = "") -> Dict[str, Any]:
    from ai_models import run_text
    compact = transcript[-12:]
    prompt = (
        f"GOAL:\n{goal}\n\nPLAN:\n{json.dumps(plan, ensure_ascii=False)[:18000]}\n\n"
        f"REPOSITORY:\n{json.dumps(inspection, ensure_ascii=False)[:16000]}\n\n"
        f"RECENT TOOL TRANSCRIPT:\n{json.dumps(compact, ensure_ascii=False)[:26000]}\n\n"
        f"REPAIR CONTEXT:\n{repair_context[:10000]}\n\nChoose the single best next action."
    )
    text, model = await run_text(app_id, "site_generation", ACTION_SYSTEM, prompt, f"dev-code-{session_id}")
    action = _json_object(text)
    action["model"] = model
    return action


async def _review(app_id: str, session_id: str, goal: str, diff: dict, verification: dict) -> Dict[str, Any]:
    from ai_models import run_text
    system = """You are the final software reviewer for Lucio Dev Agent. Return JSON only.
Judge only whether the change set appears consistent with the requested goal and verification evidence. Do not claim tests passed unless evidence says so.
Schema: {"summary":"...","goal_coverage":["..."],"risks":["..."],"recommended_manual_checks":["..."],"ready_for_human_approval":true|false}."""
    prompt = f"GOAL:\n{goal}\n\nDIFF:\n{json.dumps(diff, ensure_ascii=False)[:30000]}\n\nVERIFICATION:\n{json.dumps(verification, ensure_ascii=False)[:18000]}"
    text, model = await run_text(app_id, "site_generation", system, prompt, f"dev-review-{session_id}")
    review = _json_object(text)
    review["model"] = model
    return review


async def _execute_session(db, app_id: str, session_id: str, max_steps: int, start_preview: bool):
    session = await db.dev_agent_sessions.find_one({"session_id": session_id, "app_id": app_id}, {"_id": 0})
    if not session:
        return
    workspace_id = session["workspace_id"]
    goal = session["goal"]
    plan = session.get("plan") or {}
    inspection = session.get("inspection") or {}
    config = session.get("config") or {}
    transcript: List[dict] = []
    try:
        await _set_session(db, session_id, status="running", error=None)
        await _push_event(db, session_id, "execution", "Coding agent started")
        done = False
        for step in range(1, min(max_steps, MAX_STEPS) + 1):
            action = await _next_action(app_id, session_id, goal, plan, inspection, transcript)
            tool = str(action.get("tool") or "").strip()
            tool_input = action.get("input") if isinstance(action.get("input"), dict) else {}
            reason = str(action.get("reason") or "")[:1200]
            await _push_event(db, session_id, "agent_action", f"Step {step}: {tool or 'invalid action'}", {"reason": reason, "input": tool_input, "model": action.get("model")})
            if tool == "done":
                done = True
                transcript.append({"step": step, "action": action, "observation": {"done": True}})
                break
            if tool not in {"read_file", "search_code", "write_file", "replace_text", "run_command", "git_diff", "git_status"}:
                observation = {"ok": False, "error": f"Unknown or disallowed tool: {tool}"}
            else:
                try:
                    observation = await _runner("POST", f"/v1/workspaces/{workspace_id}/tool", body={"tool": tool, "input": tool_input}, timeout=240.0)
                except HTTPException as exc:
                    observation = {"ok": False, "error": str(exc.detail)[:2000]}
            transcript.append({"step": step, "action": {"tool": tool, "input": tool_input, "reason": reason}, "observation": _safe_event_value(observation)})
            await _push_event(db, session_id, "tool_result", f"{tool} {'succeeded' if observation.get('ok', True) else 'failed'}", observation)

        await _push_event(db, session_id, "verification", "Running automated verification")
        commands = config.get("verify_commands") or []
        verification = await _runner("POST", f"/v1/workspaces/{workspace_id}/verify", body={"commands": commands}, timeout=900.0)

        # One bounded self-healing pass if the first verification fails.
        if not verification.get("ok"):
            failure_text = json.dumps(verification, ensure_ascii=False)[:14000]
            await _push_event(db, session_id, "repair", "Verification failed; starting self-healing repair pass", verification)
            for repair_step in range(1, 6):
                action = await _next_action(app_id, session_id, goal, plan, inspection, transcript, repair_context=failure_text)
                tool = str(action.get("tool") or "")
                if tool == "done":
                    break
                if tool not in {"read_file", "search_code", "write_file", "replace_text", "run_command", "git_diff", "git_status"}:
                    continue
                try:
                    observation = await _runner("POST", f"/v1/workspaces/{workspace_id}/tool", body={"tool": tool, "input": action.get("input") or {}}, timeout=240.0)
                except HTTPException as exc:
                    observation = {"ok": False, "error": str(exc.detail)[:2000]}
                transcript.append({"repair_step": repair_step, "action": action, "observation": _safe_event_value(observation)})
                await _push_event(db, session_id, "repair_action", f"Repair {repair_step}: {tool}", observation)
            verification = await _runner("POST", f"/v1/workspaces/{workspace_id}/verify", body={"commands": commands}, timeout=900.0)

        diff = await _runner("POST", f"/v1/workspaces/{workspace_id}/tool", body={"tool": "git_diff", "input": {}}, timeout=90.0)
        review = await _review(app_id, session_id, goal, diff, verification)
        preview = None
        preview_argv = config.get("preview_argv") or inspection.get("preview")
        if start_preview and preview_argv and verification.get("ok"):
            try:
                preview = await _runner("POST", f"/v1/workspaces/{workspace_id}/preview", body={"argv": preview_argv, "cwd": "."}, timeout=45.0)
                await _push_event(db, session_id, "preview", "Live preview started", preview)
            except Exception as exc:
                await _push_event(db, session_id, "preview_warning", "Preview could not be started", {"detail": str(getattr(exc, "detail", exc))[:1800]})

        changed = bool((diff.get("diff") or "").strip() or diff.get("untracked"))
        final_status = "awaiting_approval" if changed else "completed"
        await _set_session(
            db,
            session_id,
            status=final_status,
            completed_execution=done,
            verification=verification,
            diff=diff,
            review=review,
            preview=preview,
            transcript_tail=_safe_event_value(transcript[-12:]),
        )
        await _push_event(db, session_id, "complete", "Agent run finished and is ready for review" if changed else "Agent run finished with no repository changes")
    except Exception as exc:
        logger.exception("Dev Agent execution failed for %s", session_id)
        detail = str(getattr(exc, "detail", exc))[:2400]
        await _set_session(db, session_id, status="failed", error=detail)
        await _push_event(db, session_id, "error", "Agent execution failed", {"detail": detail})


async def _continue_session(db, app_id: str, session_id: str, instruction: str, max_steps: int, start_preview: bool):
    session = await db.dev_agent_sessions.find_one({"session_id": session_id, "app_id": app_id}, {"_id": 0})
    if not session:
        return
    combined = f"{session.get('goal', '')}\n\nFOLLOW-UP INSTRUCTION:\n{instruction}"
    await _set_session(db, session_id, goal=combined, status="running", decision=None)
    await _push_event(db, session_id, "user_instruction", instruction)
    await _execute_session(db, app_id, session_id, max_steps, start_preview)


def register(api, db, get_current_user):
    async def get_app(app_id: str, user: dict) -> dict:
        doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "App not found")
        if doc.get("owner_id") == user.get("user_id"):
            return doc
        membership = await db.memberships.find_one({"app_id": app_id, "user_id": user.get("user_id")}, {"_id": 0})
        if not membership:
            raise HTTPException(403, "No access to this app")
        return doc

    async def require_editor(app_id: str, user: dict) -> dict:
        doc = await get_app(app_id, user)
        if doc.get("owner_id") == user.get("user_id"):
            return doc
        membership = await db.memberships.find_one({"app_id": app_id, "user_id": user.get("user_id")}, {"_id": 0}) or {}
        if membership.get("role") not in {"owner", "admin", "editor"}:
            raise HTTPException(403, "Editor access is required for Dev Agent")
        return doc

    @api.get("/dev-agent/status")
    async def status(user: dict = Depends(get_current_user)):
        from llm_provider import llm_available, llm_mode
        runner = await _runner_health()
        return {
            "enabled": True,
            "llm_available": llm_available(),
            "llm_mode": llm_mode(),
            "runner": runner,
            "phases": {
                "phase_1_dev_agent": True,
                "phase_2_isolated_runtime": bool(runner.get("configured")),
                "phase_3_agentic_loop": True,
                "phase_4_goal_to_working_app": True,
            },
            "capabilities": ["repository_inspection", "planning", "read_search", "code_editing", "commands", "tests", "self_healing", "git_diff", "review", "live_preview", "approval_gate"],
        }

    @api.get("/apps/{app_id}/dev-agent/config")
    async def get_config(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_app(app_id, user)
        return doc.get("dev_agent") or {"repo_url": "", "branch": "main", "preview_argv": None, "verify_commands": None}

    @api.patch("/apps/{app_id}/dev-agent/config")
    async def set_config(app_id: str, body: DevConfigIn, user: dict = Depends(get_current_user)):
        await require_editor(app_id, user)
        current = (await db.apps.find_one({"app_id": app_id}, {"_id": 0, "dev_agent": 1}) or {}).get("dev_agent") or {}
        data = body.model_dump(exclude_unset=True)
        if data.get("repo_url"):
            data["repo_url"] = _clean_repo_url(data["repo_url"])
        merged = {**current, **data, "updated_at": _now()}
        await db.apps.update_one({"app_id": app_id}, {"$set": {"dev_agent": merged}})
        return merged

    @api.get("/apps/{app_id}/dev-agent/sessions")
    async def list_sessions(app_id: str, user: dict = Depends(get_current_user)):
        await get_app(app_id, user)
        docs = await db.dev_agent_sessions.find({"app_id": app_id}, {"_id": 0, "transcript_tail": 0}).sort("created_at", -1).to_list(30)
        return docs

    @api.post("/apps/{app_id}/dev-agent/sessions")
    async def create_session(app_id: str, body: SessionCreateIn, background: BackgroundTasks, user: dict = Depends(get_current_user)):
        app_doc = await require_editor(app_id, user)
        config = app_doc.get("dev_agent") or {}
        repo_url = _clean_repo_url(body.repo_url or config.get("repo_url") or "")
        branch = (body.branch or config.get("branch") or "main").strip()[:160]
        session_id = _id("dev")
        workspace_id = session_id
        doc = {
            "session_id": session_id,
            "workspace_id": workspace_id,
            "app_id": app_id,
            "user_id": user["user_id"],
            "goal": body.goal.strip(),
            "repo_url": repo_url,
            "branch": branch,
            "status": "preparing",
            "config": {**config, "repo_url": repo_url, "branch": branch},
            "events": [],
            "created_at": _now(),
            "updated_at": _now(),
        }
        await db.dev_agent_sessions.insert_one(doc)
        try:
            await _push_event(db, session_id, "workspace", "Creating isolated development workspace")
            runner = await _runner("POST", "/v1/workspaces", body={"workspace_id": workspace_id, "repo_url": repo_url, "branch": branch}, timeout=180.0)
            inspection = runner.get("inspection") or runner
            await _set_session(db, session_id, status="planning", inspection=inspection)
            await _push_event(db, session_id, "workspace", "Repository cloned and inspected", {"stack": inspection.get("stack"), "file_count": len(inspection.get("files") or [])})
            plan = await _plan(app_id, body.goal.strip(), inspection, session_id)
            await _set_session(db, session_id, status="planned", plan=plan)
            await _push_event(db, session_id, "plan", "Development plan generated", plan)
        except Exception as exc:
            detail = str(getattr(exc, "detail", exc))[:2400]
            await _set_session(db, session_id, status="failed", error=detail)
            await _push_event(db, session_id, "error", "Could not prepare Dev Agent session", {"detail": detail})
            return await db.dev_agent_sessions.find_one({"session_id": session_id}, {"_id": 0})
        if body.auto_execute:
            background.add_task(_execute_session, db, app_id, session_id, MAX_STEPS, True)
            await _set_session(db, session_id, status="queued")
        return await db.dev_agent_sessions.find_one({"session_id": session_id}, {"_id": 0})

    @api.get("/apps/{app_id}/dev-agent/sessions/{session_id}")
    async def get_session(app_id: str, session_id: str, user: dict = Depends(get_current_user)):
        await get_app(app_id, user)
        doc = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Dev Agent session not found")
        return doc

    @api.post("/apps/{app_id}/dev-agent/sessions/{session_id}/execute")
    async def execute(app_id: str, session_id: str, body: ExecuteIn, background: BackgroundTasks, user: dict = Depends(get_current_user)):
        await require_editor(app_id, user)
        doc = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Dev Agent session not found")
        if doc.get("status") in {"running", "queued", "preparing", "planning"}:
            raise HTTPException(409, f"Session is already {doc.get('status')}")
        await _set_session(db, session_id, status="queued", error=None)
        background.add_task(_execute_session, db, app_id, session_id, body.max_steps, body.start_preview)
        return {"session_id": session_id, "status": "queued"}

    @api.post("/apps/{app_id}/dev-agent/sessions/{session_id}/continue")
    async def continue_run(app_id: str, session_id: str, body: ContinueIn, background: BackgroundTasks, user: dict = Depends(get_current_user)):
        await require_editor(app_id, user)
        doc = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Dev Agent session not found")
        if doc.get("status") in {"running", "queued"}:
            raise HTTPException(409, "Wait for the current run to finish")
        await _set_session(db, session_id, status="queued")
        background.add_task(_continue_session, db, app_id, session_id, body.instruction, body.max_steps, body.start_preview)
        return {"session_id": session_id, "status": "queued"}

    @api.post("/apps/{app_id}/dev-agent/sessions/{session_id}/approve")
    async def approve(app_id: str, session_id: str, body: DecisionIn, user: dict = Depends(get_current_user)):
        await require_editor(app_id, user)
        doc = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Dev Agent session not found")
        decision = {"state": "approved", "by": user["user_id"], "at": _now(), "note": body.note}
        await _set_session(db, session_id, status="approved", decision=decision)
        await _push_event(db, session_id, "approval", "Change set approved by human reviewer", decision)
        if body.cleanup_workspace:
            try:
                await _runner("DELETE", f"/v1/workspaces/{doc['workspace_id']}", timeout=30.0)
            except Exception:
                pass
        return {"session_id": session_id, "status": "approved", "decision": decision, "diff": doc.get("diff")}

    @api.post("/apps/{app_id}/dev-agent/sessions/{session_id}/reject")
    async def reject(app_id: str, session_id: str, body: DecisionIn, user: dict = Depends(get_current_user)):
        await require_editor(app_id, user)
        doc = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Dev Agent session not found")
        decision = {"state": "rejected", "by": user["user_id"], "at": _now(), "note": body.note}
        await _set_session(db, session_id, status="rejected", decision=decision)
        await _push_event(db, session_id, "approval", "Change set rejected", decision)
        if body.cleanup_workspace:
            try:
                await _runner("DELETE", f"/v1/workspaces/{doc['workspace_id']}", timeout=30.0)
            except Exception:
                pass
        return {"session_id": session_id, "status": "rejected", "decision": decision}

    @api.get("/apps/{app_id}/dev-agent/sessions/{session_id}/preview")
    async def preview(app_id: str, session_id: str, user: dict = Depends(get_current_user)):
        await get_app(app_id, user)
        doc = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Dev Agent session not found")
        return await _runner("GET", f"/v1/workspaces/{doc['workspace_id']}/preview", timeout=20.0)

    @api.delete("/apps/{app_id}/dev-agent/sessions/{session_id}/workspace")
    async def cleanup(app_id: str, session_id: str, user: dict = Depends(get_current_user)):
        await require_editor(app_id, user)
        doc = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Dev Agent session not found")
        try:
            await _runner("DELETE", f"/v1/workspaces/{doc['workspace_id']}", timeout=30.0)
        finally:
            await _set_session(db, session_id, workspace_cleaned_at=_now(), preview=None)
        return {"ok": True}

    return {"runner_url": RUNNER_URL, "max_steps": MAX_STEPS}
