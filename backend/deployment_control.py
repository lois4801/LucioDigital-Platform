"""Lucio Dev Agent Phase 7 — approval-gated preview deployments.

A published GitHub branch can be deployed to an isolated Railway preview service only after
human approval and successful verification. Publishing code and deploying production remain
separate operations. Production promotion is intentionally NOT implemented here.

Preferred auth is a Railway project token because it is scoped to one environment. Account /
workspace / OAuth bearer tokens are also supported for future integrations. Credentials stay
in the Lucio backend and are never sent to Nexus Runner or generated applications.
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

RAILWAY_API = "https://backboard.railway.com/graphql/v2"
PROJECT_TOKEN = (os.environ.get("LUCIO_RAILWAY_PROJECT_TOKEN") or "").strip()
BEARER_TOKEN = (os.environ.get("LUCIO_RAILWAY_TOKEN") or "").strip()
RAILWAY_PROJECT_ID = (os.environ.get("LUCIO_RAILWAY_PROJECT_ID") or "").strip()
RAILWAY_ENVIRONMENT_ID = (os.environ.get("LUCIO_RAILWAY_ENVIRONMENT_ID") or "").strip()
PREVIEW_ENABLED = (os.environ.get("LUCIO_RAILWAY_PREVIEW_ENABLED") or "false").strip().lower() in {"1", "true", "yes", "on"}


class PreviewDeployIn(BaseModel):
    service_name: Optional[str] = Field(default=None, max_length=80)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str, fallback: str = "lucio-preview") -> str:
    cleaned = re.sub(r"[^a-z0-9-]+", "-", (value or "").lower()).strip("-")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    return (cleaned or fallback)[:60].strip("-")


def _repo_slug(url: str) -> str:
    match = re.fullmatch(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?", (url or "").strip())
    if not match:
        raise HTTPException(409, "Published repository is not a supported GitHub repository URL")
    return f"{match.group(1)}/{match.group(2)}"


def _configured() -> bool:
    return bool((PROJECT_TOKEN or BEARER_TOKEN) and RAILWAY_PROJECT_ID and RAILWAY_ENVIRONMENT_ID and PREVIEW_ENABLED)


class RailwayClient:
    def __init__(self):
        headers = {"Content-Type": "application/json", "User-Agent": "Lucio-Dev-Agent/Phase7"}
        if PROJECT_TOKEN:
            headers["Project-Access-Token"] = PROJECT_TOKEN
        elif BEARER_TOKEN:
            headers["Authorization"] = f"Bearer {BEARER_TOKEN}"
        else:
            raise HTTPException(503, "Railway preview deployment credential is not configured")
        self.headers = headers

    async def gql(self, query: str, variables: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(RAILWAY_API, headers=self.headers, json={"query": query, "variables": variables})
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"Railway API network error: {str(exc)[:300]}")
        try:
            payload = response.json()
        except Exception:
            raise HTTPException(502, f"Railway API returned an unreadable response ({response.status_code})")
        if response.status_code == 429:
            raise HTTPException(429, "Railway API rate limit reached; retry after the Railway reset window")
        if response.status_code >= 400:
            raise HTTPException(502, f"Railway API HTTP {response.status_code}: {str(payload)[:500]}")
        errors = payload.get("errors") or []
        if errors:
            msg = "; ".join(str(e.get("message") or e) for e in errors[:3])
            raise HTTPException(502, f"Railway API error: {msg[:600]}")
        return payload.get("data") or {}

    async def create_preview(self, *, repo: str, branch: str, name: str) -> Dict[str, Any]:
        query = """
        mutation serviceCreate($input: ServiceCreateInput!) {
          serviceCreate(input: $input) { id name }
        }
        """
        data = await self.gql(query, {"input": {
            "projectId": RAILWAY_PROJECT_ID,
            "name": name,
            "source": {"repo": repo},
            "branch": branch,
        }})
        service = data.get("serviceCreate") or {}
        service_id = service.get("id")
        if not service_id:
            raise HTTPException(502, "Railway did not return a preview service ID")

        deploy_query = """
        mutation serviceInstanceDeployV2($serviceId: String!, $environmentId: String!) {
          serviceInstanceDeployV2(serviceId: $serviceId, environmentId: $environmentId)
        }
        """
        deploy_data = await self.gql(deploy_query, {"serviceId": service_id, "environmentId": RAILWAY_ENVIRONMENT_ID})
        deployment_id = deploy_data.get("serviceInstanceDeployV2")

        domain_query = """
        mutation serviceDomainCreate($input: ServiceDomainCreateInput!) {
          serviceDomainCreate(input: $input) { id domain }
        }
        """
        domain = {}
        try:
            domain_data = await self.gql(domain_query, {"input": {
                "serviceId": service_id,
                "environmentId": RAILWAY_ENVIRONMENT_ID,
            }})
            domain = domain_data.get("serviceDomainCreate") or {}
        except HTTPException:
            # A preview can still be useful while domain creation is retried/refreshed later.
            domain = {}

        return {
            "service_id": service_id,
            "service_name": service.get("name") or name,
            "deployment_id": deployment_id,
            "domain_id": domain.get("id"),
            "domain": domain.get("domain"),
        }

    async def status(self, service_id: str) -> Dict[str, Any]:
        query = """
        query previewStatus($serviceId: String!, $environmentId: String!, $projectId: String!) {
          serviceInstance(serviceId: $serviceId, environmentId: $environmentId) {
            serviceName
            latestDeployment { id status createdAt }
          }
          domains(projectId: $projectId, environmentId: $environmentId, serviceId: $serviceId) {
            serviceDomains { id domain suffix targetPort }
          }
        }
        """
        data = await self.gql(query, {
            "serviceId": service_id,
            "environmentId": RAILWAY_ENVIRONMENT_ID,
            "projectId": RAILWAY_PROJECT_ID,
        })
        instance = data.get("serviceInstance") or {}
        deployment = instance.get("latestDeployment") or {}
        domains = ((data.get("domains") or {}).get("serviceDomains") or [])
        domain = domains[0] if domains else {}
        status = str(deployment.get("status") or "UNKNOWN").upper()
        return {
            "service_name": instance.get("serviceName"),
            "deployment_id": deployment.get("id"),
            "status": status,
            "created_at": deployment.get("createdAt"),
            "domain_id": domain.get("id"),
            "domain": domain.get("domain"),
            "url": f"https://{domain.get('domain')}" if domain.get("domain") else None,
            "ready": status == "SUCCESS" and bool(domain.get("domain")),
        }


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
    async def get_app(app_id: str, user: dict) -> Tuple[dict, str]:
        doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "App not found")
        if doc.get("owner_id") == user.get("user_id"):
            return doc, "owner"
        membership = await db.memberships.find_one({"app_id": app_id, "user_id": user.get("user_id")}, {"_id": 0}) or {}
        role = membership.get("role")
        if not role:
            raise HTTPException(403, "No access to this app")
        return doc, role

    async def require_editor(app_id: str, user: dict) -> dict:
        doc, role = await get_app(app_id, user)
        if role not in {"owner", "admin", "editor"}:
            raise HTTPException(403, "Editor access is required to deploy a preview")
        return doc

    @api.get("/dev-agent/deployment-control")
    async def deployment_control_status(user: dict = Depends(get_current_user)):
        return {
            "provider": "railway",
            "configured": _configured(),
            "preview_enabled": PREVIEW_ENABLED,
            "credential_type": "project_token" if PROJECT_TOKEN else "bearer" if BEARER_TOKEN else None,
            "project_configured": bool(RAILWAY_PROJECT_ID),
            "environment_configured": bool(RAILWAY_ENVIRONMENT_ID),
            "requires_published_branch": True,
            "requires_verified_approved_run": True,
            "production_promotion_enabled": False,
            "production_rule": "Preview deployment and production promotion are separate approvals.",
        }

    @api.get("/apps/{app_id}/dev-agent/sessions/{session_id}/preview-readiness")
    async def preview_readiness(app_id: str, session_id: str, user: dict = Depends(get_current_user)):
        await get_app(app_id, user)
        session = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(404, "Dev Agent session not found")
        reasons = []
        if not _configured():
            reasons.append("Railway preview deployment is not connected/enabled on the Lucio backend")
        if session.get("status") != "approved":
            reasons.append("The Dev Agent change set must be approved")
        if not (session.get("verification") or {}).get("ok"):
            reasons.append("Automated verification must pass")
        publication = session.get("publication") or {}
        if not publication.get("branch") or not publication.get("repository"):
            reasons.append("Publish the approved change set to a reviewable GitHub branch first")
        return {
            "ready": not reasons,
            "reasons": reasons,
            "publication": publication or None,
            "preview": session.get("preview_deployment"),
            "production_promotion_enabled": False,
        }

    @api.post("/apps/{app_id}/dev-agent/sessions/{session_id}/preview-deploy")
    async def preview_deploy(app_id: str, session_id: str, body: PreviewDeployIn, user: dict = Depends(get_current_user)):
        app_doc = await require_editor(app_id, user)
        session = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(404, "Dev Agent session not found")
        existing = session.get("preview_deployment") or {}
        if existing.get("service_id"):
            return existing
        if not _configured():
            raise HTTPException(503, "Railway preview deployment is not connected/enabled on the Lucio backend")
        if session.get("status") != "approved":
            raise HTTPException(409, "Approve this change set before deploying a preview")
        if not (session.get("verification") or {}).get("ok"):
            raise HTTPException(409, "A preview deployment requires passing automated verification")
        publication = session.get("publication") or {}
        if not publication.get("repository") or not publication.get("branch"):
            raise HTTPException(409, "Publish the approved change set to a GitHub branch before deploying a preview")

        repo = _repo_slug(publication["repository"])
        branch = str(publication["branch"])
        default_name = f"preview-{_slug(app_doc.get('name') or app_id, 'lucio')}-{session_id[-6:].lower()}"
        name = _slug(body.service_name or default_name, default_name)
        client = RailwayClient()
        created = await client.create_preview(repo=repo, branch=branch, name=name)
        preview = {
            **created,
            "provider": "railway",
            "repository": publication["repository"],
            "branch": branch,
            "commit_sha": publication.get("commit_sha"),
            "requested_at": _now(),
            "requested_by": user.get("user_id"),
            "status": "DEPLOYING",
            "ready": False,
            "url": f"https://{created['domain']}" if created.get("domain") else None,
            "production": False,
        }
        await db.dev_agent_sessions.update_one({"session_id": session_id}, {"$set": {"preview_deployment": preview, "updated_at": _now()}})
        await _append_event(db, session_id, "preview_deploy", "Railway preview deployment requested", preview)
        return preview

    @api.post("/apps/{app_id}/dev-agent/sessions/{session_id}/preview-refresh")
    async def preview_refresh(app_id: str, session_id: str, user: dict = Depends(get_current_user)):
        await get_app(app_id, user)
        session = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(404, "Dev Agent session not found")
        preview = session.get("preview_deployment") or {}
        service_id = preview.get("service_id")
        if not service_id:
            raise HTTPException(409, "This run does not have a Railway preview deployment")
        if not (PROJECT_TOKEN or BEARER_TOKEN):
            raise HTTPException(503, "Railway API credential is not configured")
        latest = await RailwayClient().status(service_id)
        merged = {**preview, **latest, "refreshed_at": _now(), "production": False}
        await db.dev_agent_sessions.update_one({"session_id": session_id}, {"$set": {"preview_deployment": merged, "updated_at": _now()}})
        if latest.get("ready") and not preview.get("ready"):
            await _append_event(db, session_id, "preview_ready", "Railway preview is live", {"url": latest.get("url"), "service_id": service_id})
        return merged

    @api.post("/apps/{app_id}/dev-agent/sessions/{session_id}/production-request")
    async def production_request(app_id: str, session_id: str, user: dict = Depends(get_current_user)):
        await require_editor(app_id, user)
        session = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(404, "Dev Agent session not found")
        preview = session.get("preview_deployment") or {}
        if not preview.get("ready"):
            raise HTTPException(409, "A successful preview deployment is required before production can be requested")
        request = session.get("production_request") or {
            "status": "awaiting_explicit_production_approval",
            "requested_at": _now(),
            "requested_by": user.get("user_id"),
            "preview_url": preview.get("url"),
            "commit_sha": preview.get("commit_sha"),
            "branch": preview.get("branch"),
            "note": "No production deployment has been performed. A separate production promotion phase is required.",
        }
        await db.dev_agent_sessions.update_one({"session_id": session_id}, {"$set": {"production_request": request, "updated_at": _now()}})
        await _append_event(db, session_id, "production_gate", "Production promotion requested; no production change performed", request)
        return request

    return {
        "configured": _configured(),
        "provider": "railway",
        "project_id_set": bool(RAILWAY_PROJECT_ID),
        "environment_id_set": bool(RAILWAY_ENVIRONMENT_ID),
    }
