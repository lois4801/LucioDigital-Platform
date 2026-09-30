"""Approval-gated GitHub publishing for Lucio Dev Agent.

This module deliberately keeps GitHub credentials in the Lucio backend only. Nexus Runner
never receives GitHub credentials. Publishing is allowed only for an approved, verified Dev
Agent session that originated from an existing GitHub repository, and always creates a new
branch instead of writing directly to the configured base branch.
"""
from __future__ import annotations

import base64
import io
import os
import re
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set, Tuple
from urllib.parse import quote

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from storage import get_object

GITHUB_API = "https://api.github.com"
TOKEN = (os.environ.get("LUCIO_GITHUB_TOKEN") or "").strip()
ALLOWED_OWNER = (os.environ.get("LUCIO_GITHUB_ALLOWED_OWNER") or "").strip().lower()
MAX_PUBLISH_FILES = max(10, min(5000, int(os.environ.get("DEV_AGENT_PUBLISH_MAX_FILES", "1200"))))
MAX_PUBLISH_BYTES = max(1_000_000, min(100_000_000, int(os.environ.get("DEV_AGENT_PUBLISH_MAX_BYTES", str(40 * 1024 * 1024)))))


class PublishIn(BaseModel):
    branch: Optional[str] = Field(default=None, max_length=180)
    commit_message: Optional[str] = Field(default=None, max_length=240)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_repo(value: str) -> Tuple[str, str]:
    match = re.fullmatch(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?", (value or "").strip())
    if not match:
        raise HTTPException(400, "Dev Agent publishing currently supports https://github.com/owner/repo repositories")
    owner, repo = match.group(1), match.group(2)
    if ALLOWED_OWNER and owner.lower() != ALLOWED_OWNER:
        raise HTTPException(403, "This GitHub repository owner is not enabled for Lucio publishing")
    return owner, repo


def _safe_branch(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._/-]+", "-", (value or "").strip()).strip("./-")
    value = re.sub(r"/{2,}", "/", value)
    if not value or value.startswith("-") or value.endswith(".") or ".." in value or "@{" in value:
        raise HTTPException(400, "Invalid GitHub branch name")
    return value[:180]


def _changed_paths(diff_doc: Dict[str, Any]) -> Tuple[Set[str], Set[str]]:
    """Return (writes, deletes) from git diff text plus untracked paths."""
    writes: Set[str] = set(str(x) for x in (diff_doc.get("untracked") or []) if x)
    deletes: Set[str] = set()
    text = str(diff_doc.get("diff") or "")
    blocks = re.split(r"(?=^diff --git )", text, flags=re.M)
    for block in blocks:
        first = block.splitlines()[0] if block.strip() else ""
        m = re.match(r"diff --git a/(.+) b/(.+)$", first)
        if not m:
            continue
        old_path, new_path = m.group(1), m.group(2)
        rename_from = re.search(r"^rename from (.+)$", block, re.M)
        rename_to = re.search(r"^rename to (.+)$", block, re.M)
        deleted = "deleted file mode" in block or re.search(r"^\+\+\+ /dev/null$", block, re.M)
        if rename_from and rename_to:
            deletes.add(rename_from.group(1))
            writes.add(rename_to.group(1))
        elif deleted:
            deletes.add(old_path)
        else:
            writes.add(new_path)
    writes -= deletes
    return writes, deletes


def _read_artifact(payload: bytes) -> Tuple[Dict[str, bytes], int]:
    files: Dict[str, bytes] = {}
    total = 0
    try:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = info.filename.replace("\\", "/").lstrip("/")
                parts = [p for p in name.split("/") if p]
                if not parts or any(p in {".", ".."} for p in parts):
                    raise HTTPException(400, "Project artifact contains an unsafe path")
                total += info.file_size
                if len(files) >= MAX_PUBLISH_FILES or total > MAX_PUBLISH_BYTES:
                    raise HTTPException(413, "Project artifact exceeds the safe GitHub publish limit")
                files[name] = zf.read(info)
    except zipfile.BadZipFile:
        raise HTTPException(400, "Approved Dev Agent artifact is not a valid ZIP archive")
    return files, total


class GitHubClient:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Lucio-Dev-Agent",
        }

    async def request(self, method: str, path: str, body: Optional[dict] = None, *, allow_404: bool = False) -> dict:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.request(method, f"{GITHUB_API}{path}", headers=self.headers, json=body)
        if allow_404 and response.status_code == 404:
            return {"_not_found": True}
        try:
            data = response.json()
        except Exception:
            data = {"message": response.text[:800]}
        if response.status_code >= 400:
            message = str(data.get("message") if isinstance(data, dict) else data)[:600]
            if response.status_code in {401, 403}:
                raise HTTPException(502, f"GitHub publishing credential was rejected: {message}")
            raise HTTPException(502, f"GitHub API error ({response.status_code}): {message}")
        return data if isinstance(data, dict) else {"data": data}


async def _append_event(db, session_id: str, message: str, data: dict):
    event = {
        "event_id": f"evt_{uuid.uuid4().hex[:14]}",
        "at": _now(),
        "kind": "github_publish",
        "message": message[:1200],
        "data": data,
    }
    await db.dev_agent_sessions.update_one(
        {"session_id": session_id},
        {"$push": {"events": {"$each": [event], "$slice": -220}}, "$set": {"updated_at": _now()}},
    )


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
            raise HTTPException(403, "Editor access is required to publish Dev Agent changes")
        return doc

    @api.get("/dev-agent/publishing")
    async def publishing_status(user: dict = Depends(get_current_user)):
        return {
            "configured": bool(TOKEN),
            "mode": "server_github_credential" if TOKEN else "artifact_only",
            "requires_approved_run": True,
            "publishes_to_new_branch_only": True,
            "auto_merge": False,
            "multi_tenant_note": "Use a per-user GitHub App/OAuth connection before enabling this for unrelated tenants.",
        }

    @api.get("/apps/{app_id}/dev-agent/sessions/{session_id}/publish-readiness")
    async def publish_readiness(app_id: str, session_id: str, user: dict = Depends(get_current_user)):
        await get_app(app_id, user)
        session = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(404, "Dev Agent session not found")
        reasons = []
        if not TOKEN:
            reasons.append("GitHub publishing is not connected on the Lucio backend")
        if session.get("status") != "approved":
            reasons.append("The Dev Agent change set must be approved first")
        if not (session.get("verification") or {}).get("ok"):
            reasons.append("Automated verification has not passed")
        if session.get("source_mode") != "repository" or not session.get("repo_url"):
            reasons.append("This run was scaffolded from scratch; download its ZIP until create-repository publishing is connected")
        if not session.get("artifact"):
            reasons.append("No durable approved source artifact is available")
        return {
            "ready": not reasons,
            "reasons": reasons,
            "repository": session.get("repo_url"),
            "base_branch": session.get("branch") or "main",
            "already_published": session.get("publication"),
        }

    @api.post("/apps/{app_id}/dev-agent/sessions/{session_id}/publish")
    async def publish(app_id: str, session_id: str, body: PublishIn, user: dict = Depends(get_current_user)):
        await require_editor(app_id, user)
        session = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})
        if not session:
            raise HTTPException(404, "Dev Agent session not found")
        if session.get("publication"):
            return session["publication"]
        if not TOKEN:
            raise HTTPException(503, "GitHub publishing is not connected. The approved source ZIP remains available for download.")
        if session.get("status") != "approved":
            raise HTTPException(409, "Approve this Dev Agent change set before publishing")
        if not (session.get("verification") or {}).get("ok"):
            raise HTTPException(409, "GitHub publishing requires a passing verification run")
        if session.get("source_mode") != "repository" or not session.get("repo_url"):
            raise HTTPException(409, "Create-repository publishing is not enabled yet for scaffolded projects; use the approved ZIP artifact")
        artifact = session.get("artifact") or {}
        storage_path = artifact.get("storage_path")
        if not storage_path:
            raise HTTPException(409, "Approve and persist the Dev Agent project artifact before publishing")

        owner, repo = _parse_repo(session["repo_url"])
        base_branch = _safe_branch(session.get("branch") or "main")
        default_branch = f"lucio/{re.sub(r'[^A-Za-z0-9._-]+', '-', app_id)[:36]}/{session_id[-14:]}"
        publish_branch = _safe_branch(body.branch or default_branch)
        if publish_branch == base_branch:
            raise HTTPException(400, "Lucio will not publish Dev Agent changes directly to the base branch")

        payload, _content_type = get_object(storage_path)
        if not isinstance(payload, (bytes, bytearray)):
            raise HTTPException(502, "Stored Dev Agent artifact could not be read")
        archive_files, archive_bytes = _read_artifact(bytes(payload))
        writes, deletes = _changed_paths(session.get("diff") or {})
        if not writes and not deletes:
            raise HTTPException(409, "There are no repository changes to publish")
        missing = sorted(path for path in writes if path not in archive_files)
        if missing:
            raise HTTPException(409, f"Approved artifact is missing changed file(s): {', '.join(missing[:8])}")

        gh = GitHubClient(TOKEN)
        base_ref = await gh.request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{quote(base_branch, safe='')}")
        base_sha = ((base_ref.get("object") or {}).get("sha") or "").strip()
        if not base_sha:
            raise HTTPException(502, "Could not resolve the repository base branch")
        exists = await gh.request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{quote(publish_branch, safe='')}", allow_404=True)
        if not exists.get("_not_found"):
            raise HTTPException(409, f"GitHub branch '{publish_branch}' already exists; choose a different publish branch")
        base_commit = await gh.request("GET", f"/repos/{owner}/{repo}/git/commits/{base_sha}")
        base_tree = ((base_commit.get("tree") or {}).get("sha") or "").strip()
        if not base_tree:
            raise HTTPException(502, "Could not resolve the repository base tree")

        entries = []
        for path in sorted(writes):
            blob = await gh.request("POST", f"/repos/{owner}/{repo}/git/blobs", {
                "content": base64.b64encode(archive_files[path]).decode("ascii"),
                "encoding": "base64",
            })
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob.get("sha")})
        for path in sorted(deletes):
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})

        tree = await gh.request("POST", f"/repos/{owner}/{repo}/git/trees", {"base_tree": base_tree, "tree": entries})
        commit_message = (body.commit_message or f"Lucio Dev Agent: {str(session.get('goal') or 'approved changes').splitlines()[0]}").strip()[:240]
        commit = await gh.request("POST", f"/repos/{owner}/{repo}/git/commits", {
            "message": commit_message,
            "tree": tree.get("sha"),
            "parents": [base_sha],
        })
        commit_sha = (commit.get("sha") or "").strip()
        if not commit_sha:
            raise HTTPException(502, "GitHub did not return a commit SHA")
        await gh.request("POST", f"/repos/{owner}/{repo}/git/refs", {"ref": f"refs/heads/{publish_branch}", "sha": commit_sha})

        branch_url = f"https://github.com/{owner}/{repo}/tree/{quote(publish_branch, safe='/')}"
        compare_url = f"https://github.com/{owner}/{repo}/compare/{quote(base_branch, safe='')}...{quote(publish_branch, safe='/')}?expand=1"
        publication = {
            "repository": f"https://github.com/{owner}/{repo}",
            "base_branch": base_branch,
            "branch": publish_branch,
            "commit_sha": commit_sha,
            "commit_url": f"https://github.com/{owner}/{repo}/commit/{commit_sha}",
            "branch_url": branch_url,
            "compare_url": compare_url,
            "published_at": _now(),
            "published_by": user.get("user_id"),
            "files_written": len(writes),
            "files_deleted": len(deletes),
            "artifact_bytes": archive_bytes,
            "auto_merged": False,
        }
        await db.dev_agent_sessions.update_one({"session_id": session_id}, {"$set": {"publication": publication, "updated_at": _now()}})
        await _append_event(db, session_id, "Approved change set published to a new GitHub branch", publication)
        return publication

    return {"configured": bool(TOKEN), "allowed_owner": ALLOWED_OWNER or None}
