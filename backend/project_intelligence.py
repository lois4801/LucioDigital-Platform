"""LucioDigital Phase 12 — persistent project intelligence for Dev Agent.

This module keeps a bounded, app-scoped memory of architecture, prior agent runs,
verified capabilities, known failures, and explicit human decisions. It intentionally
stores no credentials and only feeds compact project context back into the Dev Agent.
"""
from __future__ import annotations

import copy
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

MAX_MEMORY_CHARS = 18000
MAX_FILES = 140
MAX_RUNS = 24
MAX_DECISIONS = 80


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:14]}"


def _clip(value: Any, limit: int = 1600) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _safe_repo_config(config: dict) -> dict:
    return {
        "repo_url": _clip(config.get("repo_url"), 500),
        "branch": _clip(config.get("branch") or "main", 160),
        "scaffold": _clip(config.get("scaffold"), 80),
        "preview_argv": list(config.get("preview_argv") or [])[:20],
        "verify_commands": list(config.get("verify_commands") or [])[:20],
    }


def _safe_inspection(inspection: dict) -> dict:
    if not isinstance(inspection, dict):
        return {}
    files = []
    for item in (inspection.get("files") or [])[:MAX_FILES]:
        if isinstance(item, str):
            files.append(item[:300])
        elif isinstance(item, dict):
            path = item.get("path") or item.get("name")
            if path:
                files.append(str(path)[:300])
    return {
        "stack": inspection.get("stack"),
        "scaffold": inspection.get("scaffold"),
        "package_manager": inspection.get("package_manager"),
        "preview": inspection.get("preview"),
        "verification": inspection.get("verification"),
        "files": files,
    }


def _session_summary(session: dict) -> dict:
    plan = session.get("plan") or {}
    review = session.get("review") or {}
    verification = session.get("verification") or {}
    browser_qa = session.get("browser_qa") or {}
    publication = session.get("publication") or {}
    decision = session.get("decision") or {}
    return {
        "session_id": session.get("session_id"),
        "goal": _clip(session.get("goal"), 1000),
        "status": session.get("status"),
        "source_mode": session.get("source_mode"),
        "repo_url": _clip(session.get("repo_url"), 500),
        "branch": _clip(session.get("branch"), 160),
        "plan_summary": _clip(plan.get("summary"), 900),
        "architecture": _clip(plan.get("architecture"), 1400),
        "verification_ok": verification.get("ok"),
        "browser_qa_ok": browser_qa.get("ok") if browser_qa else None,
        "review_ready": review.get("ready_for_human_approval"),
        "decision": decision.get("state"),
        "published_branch": publication.get("branch"),
        "published_commit": publication.get("commit_sha"),
        "updated_at": session.get("updated_at") or session.get("created_at"),
        "error": _clip(session.get("error"), 900) if session.get("error") else None,
    }


async def _load_decisions(db, app_id: str) -> List[dict]:
    return await db.dev_agent_project_decisions.find(
        {"app_id": app_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(MAX_DECISIONS)


async def build_snapshot(db, app_id: str) -> dict:
    app = await db.apps.find_one({"app_id": app_id}, {"_id": 0})
    if not app:
        raise HTTPException(404, "App not found")

    sessions = await db.dev_agent_sessions.find(
        {"app_id": app_id}, {"_id": 0, "events": 0, "transcript_tail": 0}
    ).sort("updated_at", -1).to_list(MAX_RUNS)
    decisions = await _load_decisions(db, app_id)

    latest_inspection = {}
    for session in sessions:
        if session.get("inspection"):
            latest_inspection = _safe_inspection(session.get("inspection") or {})
            break

    successful = [s for s in sessions if (s.get("verification") or {}).get("ok")]
    browser_verified = [s for s in sessions if (s.get("browser_qa") or {}).get("ok")]
    approved = [s for s in sessions if (s.get("decision") or {}).get("state") == "approved"]
    published = [s for s in sessions if s.get("publication")]
    failures = [
        {
            "session_id": s.get("session_id"),
            "goal": _clip(s.get("goal"), 500),
            "error": _clip(s.get("error"), 900),
            "updated_at": s.get("updated_at"),
        }
        for s in sessions if s.get("error")
    ][:10]

    capabilities = []
    if sessions:
        capabilities.append("repository_or_scaffold_inspection")
    if successful:
        capabilities.extend(["automated_build_verification", "bounded_self_healing"])
    if browser_verified:
        capabilities.append("chromium_browser_qa")
    if approved:
        capabilities.append("human_approval_gate")
    if published:
        capabilities.append("github_branch_handoff")

    snapshot = {
        "app_id": app_id,
        "project": {
            "name": app.get("name"),
            "kind": app.get("kind"),
            "industry": app.get("industry"),
            "description": _clip(app.get("description"), 1600),
            "status": app.get("status"),
            "dev_agent": _safe_repo_config(app.get("dev_agent") or {}),
        },
        "architecture": latest_inspection,
        "decisions": decisions,
        "recent_runs": [_session_summary(s) for s in sessions],
        "known_failures": failures,
        "verified_capabilities": sorted(set(capabilities)),
        "stats": {
            "runs": len(sessions),
            "verified_runs": len(successful),
            "browser_verified_runs": len(browser_verified),
            "approved_runs": len(approved),
            "published_runs": len(published),
            "decision_count": len(decisions),
        },
        "generated_at": _now(),
        "schema_version": 1,
    }
    return snapshot


async def persist_snapshot(db, app_id: str) -> dict:
    snapshot = await build_snapshot(db, app_id)
    await db.dev_agent_project_intelligence.update_one(
        {"app_id": app_id},
        {"$set": snapshot},
        upsert=True,
    )
    return snapshot


async def memory_context(db, app_id: str, goal: str = "") -> dict:
    """Return compact live memory for LLM planning/execution; never includes secrets/transcripts."""
    snapshot = await build_snapshot(db, app_id)
    runs = snapshot.get("recent_runs") or []
    decisions = snapshot.get("decisions") or []
    context = {
        "project": snapshot.get("project"),
        "architecture": snapshot.get("architecture"),
        "verified_capabilities": snapshot.get("verified_capabilities"),
        "human_decisions": decisions[:20],
        "recent_successful_runs": [r for r in runs if r.get("verification_ok")][:8],
        "recent_failures": snapshot.get("known_failures", [])[:6],
        "current_goal": _clip(goal, 1200),
    }
    # Hard bound before inserting into an LLM prompt.
    encoded = json.dumps(context, ensure_ascii=False)
    if len(encoded) <= MAX_MEMORY_CHARS:
        return context
    context["recent_successful_runs"] = context["recent_successful_runs"][:4]
    context["human_decisions"] = context["human_decisions"][:10]
    context["architecture"] = {
        **(context.get("architecture") or {}),
        "files": ((context.get("architecture") or {}).get("files") or [])[:60],
    }
    return context


def install_dev_agent_hooks(db) -> None:
    """Inject persistent project memory into existing Dev Agent planning/coding functions."""
    import dev_agent

    if getattr(dev_agent, "_phase12_memory_hooks_installed", False):
        return

    original_plan = dev_agent._plan
    original_next_action = dev_agent._next_action
    original_review = dev_agent._review

    async def plan_with_memory(app_id: str, goal: str, inspection: dict, session_id: str):
        enriched = copy.deepcopy(inspection or {})
        enriched["project_memory"] = await memory_context(db, app_id, goal)
        return await original_plan(app_id, goal, enriched, session_id)

    async def next_with_memory(app_id: str, session_id: str, goal: str, plan: dict,
                               inspection: dict, transcript: List[dict], repair_context: str = ""):
        enriched = copy.deepcopy(inspection or {})
        enriched["project_memory"] = await memory_context(db, app_id, goal)
        return await original_next_action(
            app_id, session_id, goal, plan, enriched, transcript, repair_context=repair_context
        )

    async def review_with_memory(app_id: str, session_id: str, goal: str, diff: dict, verification: dict):
        review = await original_review(app_id, session_id, goal, diff, verification)
        try:
            review["project_memory"] = {
                "used": True,
                "stats": (await build_snapshot(db, app_id)).get("stats", {}),
            }
        except Exception:
            review["project_memory"] = {"used": True}
        return review

    dev_agent._plan = plan_with_memory
    dev_agent._next_action = next_with_memory
    dev_agent._review = review_with_memory
    dev_agent._phase12_memory_hooks_installed = True


class DecisionIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    detail: str = Field(min_length=2, max_length=5000)
    category: str = Field(default="architecture", max_length=80)


def register(api, db, get_current_user):
    install_dev_agent_hooks(db)

    async def get_app(app_id: str, user: dict) -> dict:
        doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "App not found")
        if doc.get("owner_id") == user.get("user_id"):
            return doc
        membership = await db.memberships.find_one(
            {"app_id": app_id, "user_id": user.get("user_id")}, {"_id": 0}
        )
        if not membership:
            raise HTTPException(403, "No access to this app")
        return doc

    async def require_editor(app_id: str, user: dict) -> dict:
        doc = await get_app(app_id, user)
        if doc.get("owner_id") == user.get("user_id"):
            return doc
        membership = await db.memberships.find_one(
            {"app_id": app_id, "user_id": user.get("user_id")}, {"_id": 0}
        ) or {}
        if membership.get("role") not in {"owner", "admin", "editor"}:
            raise HTTPException(403, "Editor access is required to update project intelligence")
        return doc

    @api.get("/apps/{app_id}/dev-agent/intelligence")
    async def get_intelligence(app_id: str, user: dict = Depends(get_current_user)):
        await get_app(app_id, user)
        return await persist_snapshot(db, app_id)

    @api.post("/apps/{app_id}/dev-agent/intelligence/refresh")
    async def refresh_intelligence(app_id: str, user: dict = Depends(get_current_user)):
        await require_editor(app_id, user)
        return await persist_snapshot(db, app_id)

    @api.post("/apps/{app_id}/dev-agent/intelligence/decisions")
    async def add_decision(app_id: str, body: DecisionIn, user: dict = Depends(get_current_user)):
        await require_editor(app_id, user)
        category = re.sub(r"[^a-z0-9_-]+", "-", body.category.lower()).strip("-") or "architecture"
        doc = {
            "decision_id": _id("decision"),
            "app_id": app_id,
            "title": body.title.strip(),
            "detail": body.detail.strip(),
            "category": category[:80],
            "created_by": user.get("user_id"),
            "created_at": _now(),
        }
        await db.dev_agent_project_decisions.insert_one(doc)
        doc.pop("_id", None)
        await persist_snapshot(db, app_id)
        return doc

    @api.delete("/apps/{app_id}/dev-agent/intelligence/decisions/{decision_id}")
    async def delete_decision(app_id: str, decision_id: str, user: dict = Depends(get_current_user)):
        await require_editor(app_id, user)
        result = await db.dev_agent_project_decisions.delete_one({"app_id": app_id, "decision_id": decision_id})
        if not result.deleted_count:
            raise HTTPException(404, "Project decision not found")
        await persist_snapshot(db, app_id)
        return {"ok": True}

    @api.get("/dev-agent/intelligence/status")
    async def intelligence_status(user: dict = Depends(get_current_user)):
        return {
            "enabled": True,
            "schema_version": 1,
            "features": [
                "persistent_project_memory",
                "architecture_snapshot",
                "human_decisions",
                "verified_capabilities",
                "known_failure_memory",
                "planner_memory_context",
                "coding_memory_context",
            ],
        }

    return {"enabled": True, "schema_version": 1}
