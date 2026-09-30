"""Nexus Runner: isolated execution service for Lucio Dev Agent.

This service must run separately from the Lucio production API. It clones one repository
per workspace, constrains file access to that workspace, and exposes a small authenticated
tool surface for the agent. It intentionally does not mount Lucio's production database or
application secrets.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Nexus Runner", version="1.0.0")

ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/tmp/lucio-workspaces")).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
RUNNER_SECRET = (os.environ.get("NEXUS_RUNNER_SECRET") or "").strip()
RUNNER_PUBLIC_URL = (os.environ.get("NEXUS_RUNNER_PUBLIC_URL") or "").rstrip("/")
ALLOW_INSECURE = (os.environ.get("NEXUS_RUNNER_ALLOW_INSECURE") or "").lower() == "true"
MAX_OUTPUT = int(os.environ.get("NEXUS_RUNNER_MAX_OUTPUT", "120000"))
MAX_FILE_BYTES = int(os.environ.get("NEXUS_RUNNER_MAX_FILE_BYTES", "750000"))
COMMAND_TIMEOUT = int(os.environ.get("NEXUS_RUNNER_COMMAND_TIMEOUT", "180"))

DENIED_PARTS = {
    ".env", ".git", ".ssh", ".aws", ".npmrc", ".pypirc", "credentials", "secrets",
    "id_rsa", "id_ed25519", "service-account.json", "firebase-adminsdk.json",
}
IGNORED_TREE = {".git", "node_modules", ".next", "dist", "build", ".venv", "venv", "__pycache__", ".cache"}
ALLOWED_BINARIES = {
    "npm", "npx", "pnpm", "yarn", "node", "python", "python3", "pytest", "pip", "pip3",
    "uvicorn", "ruff", "eslint", "tsc", "vite", "next", "go", "cargo", "make",
}

# workspace_id -> preview process metadata. Source files live on disk and are the source of truth.
PREVIEWS: Dict[str, Dict[str, Any]] = {}


class WorkspaceCreate(BaseModel):
    workspace_id: str = Field(min_length=3, max_length=96)
    repo_url: str
    branch: str = "main"


class ToolRequest(BaseModel):
    tool: str
    input: Dict[str, Any] = Field(default_factory=dict)


class PreviewRequest(BaseModel):
    argv: List[str] = Field(min_length=1, max_length=32)
    cwd: str = "."


class VerifyRequest(BaseModel):
    commands: List[List[str]] = Field(default_factory=list, max_length=12)


def _auth(authorization: Optional[str] = Header(default=None)) -> None:
    if ALLOW_INSECURE and not RUNNER_SECRET:
        return
    if not RUNNER_SECRET:
        raise HTTPException(503, "NEXUS_RUNNER_SECRET is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Runner authentication required")
    supplied = authorization[7:]
    if not secrets.compare_digest(supplied, RUNNER_SECRET):
        raise HTTPException(403, "Invalid runner credential")


def _workspace_id(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]", "-", value).strip(".-")
    if not clean or clean != value or len(clean) > 96:
        raise HTTPException(400, "Invalid workspace id")
    return clean


def _workspace(workspace_id: str) -> Path:
    wid = _workspace_id(workspace_id)
    path = (ROOT / wid).resolve()
    if path.parent != ROOT:
        raise HTTPException(400, "Invalid workspace path")
    if not path.exists():
        raise HTTPException(404, "Workspace not found")
    return path


def _safe_path(workspace: Path, relative: str, *, allow_missing: bool = True) -> Path:
    relative = (relative or ".").replace("\\", "/")
    parts = [p for p in Path(relative).parts if p not in ("", ".")]
    lowered = {p.lower() for p in parts}
    if lowered & DENIED_PARTS or any(p.startswith(".env") for p in lowered):
        raise HTTPException(403, "Secret or repository metadata paths are not accessible")
    target = (workspace / relative).resolve()
    try:
        target.relative_to(workspace)
    except ValueError:
        raise HTTPException(403, "Path escapes workspace")
    if not allow_missing and not target.exists():
        raise HTTPException(404, "Path not found")
    return target


def _validate_repo_url(repo_url: str) -> str:
    parsed = urlparse(repo_url)
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
        raise HTTPException(400, "Only https://github.com/... repositories are supported by this runner")
    if parsed.username or parsed.password or "@" in parsed.netloc:
        raise HTTPException(400, "Credentials must never be embedded in repository URLs")
    path = parsed.path.strip("/")
    if len(path.split("/")) != 2:
        raise HTTPException(400, "Repository URL must be https://github.com/owner/repo")
    return f"https://github.com/{path.removesuffix('.git')}.git"


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT:
        return text
    return text[-MAX_OUTPUT:] + "\n[output truncated]"


def _run(workspace: Path, argv: List[str], cwd: str = ".", timeout: Optional[int] = None) -> Dict[str, Any]:
    if not argv or not all(isinstance(x, str) and x for x in argv):
        raise HTTPException(400, "argv must contain command arguments")
    binary = Path(argv[0]).name
    if binary not in ALLOWED_BINARIES:
        raise HTTPException(403, f"Command '{binary}' is not allowed")
    workdir = _safe_path(workspace, cwd, allow_missing=False)
    if not workdir.is_dir():
        raise HTTPException(400, "cwd must be a directory")
    started = time.monotonic()
    try:
        result = subprocess.run(
            argv,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout or COMMAND_TIMEOUT,
            env={**os.environ, "CI": "1", "NO_COLOR": "1"},
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + "\n" + (exc.stderr or "")
        return {"ok": False, "returncode": 124, "output": _truncate(output), "duration_ms": int((time.monotonic()-started)*1000), "timed_out": True}
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "output": _truncate((result.stdout or "") + ("\n" if result.stdout and result.stderr else "") + (result.stderr or "")),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def _git(workspace: Path, args: List[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(workspace), capture_output=True, text=True, timeout=timeout)


def _tree(workspace: Path, limit: int = 600) -> List[str]:
    out: List[str] = []
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in IGNORED_TREE]
        root_path = Path(root)
        rel_root = root_path.relative_to(workspace)
        for name in sorted(files):
            if name in DENIED_PARTS or name.startswith(".env"):
                continue
            rel = (rel_root / name).as_posix()
            out.append(rel)
            if len(out) >= limit:
                return out
    return out


def _detect(workspace: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {"stack": [], "scripts": {}, "verify": [], "preview": None}
    pkg = workspace / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text("utf-8"))
            result["stack"].append("node")
            result["scripts"] = data.get("scripts") or {}
            deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
            if "next" in deps:
                result["stack"].append("nextjs")
            elif "vite" in deps:
                result["stack"].append("vite")
            elif "react" in deps:
                result["stack"].append("react")
            if "lint" in result["scripts"]:
                result["verify"].append(["npm", "run", "lint"])
            if "test" in result["scripts"] and "no test specified" not in str(result["scripts"]["test"]):
                result["verify"].append(["npm", "test", "--", "--runInBand"])
            if "build" in result["scripts"]:
                result["verify"].append(["npm", "run", "build"])
            if "dev" in result["scripts"]:
                result["preview"] = ["npm", "run", "dev"]
            elif "start" in result["scripts"]:
                result["preview"] = ["npm", "start"]
        except Exception:
            pass
    if (workspace / "requirements.txt").exists() or (workspace / "pyproject.toml").exists():
        result["stack"].append("python")
        if (workspace / "pytest.ini").exists() or (workspace / "tests").exists():
            result["verify"].append(["pytest", "-q"])
    if (workspace / "go.mod").exists():
        result["stack"].append("go")
        result["verify"].append(["go", "test", "./..."])
    if (workspace / "Cargo.toml").exists():
        result["stack"].append("rust")
        result["verify"].append(["cargo", "test"])
    return result


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "nexus-runner", "workspaces": len([p for p in ROOT.iterdir() if p.is_dir()])}


@app.post("/v1/workspaces", dependencies=[Depends(_auth)])
async def create_workspace(body: WorkspaceCreate):
    wid = _workspace_id(body.workspace_id)
    repo = _validate_repo_url(body.repo_url)
    dest = (ROOT / wid).resolve()
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    clone = subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", body.branch, "--single-branch", repo, str(dest)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if clone.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        raise HTTPException(400, f"Repository clone failed: {_truncate(clone.stderr or clone.stdout)[:1200]}")
    return {"workspace_id": wid, "branch": body.branch, "repository": body.repo_url, "inspection": {"files": _tree(dest), **_detect(dest)}}


@app.get("/v1/workspaces/{workspace_id}", dependencies=[Depends(_auth)])
async def inspect_workspace(workspace_id: str):
    workspace = _workspace(workspace_id)
    status = _git(workspace, ["status", "--short"])
    return {"workspace_id": workspace_id, "files": _tree(workspace), "git_status": _truncate(status.stdout), **_detect(workspace), "preview": _preview_info(workspace_id)}


@app.post("/v1/workspaces/{workspace_id}/tool", dependencies=[Depends(_auth)])
async def use_tool(workspace_id: str, body: ToolRequest):
    workspace = _workspace(workspace_id)
    tool, data = body.tool, body.input or {}

    if tool == "read_file":
        path = _safe_path(workspace, str(data.get("path") or ""), allow_missing=False)
        if not path.is_file():
            raise HTTPException(400, "Path is not a file")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise HTTPException(413, "File is too large for agent read")
        lines = path.read_text("utf-8", errors="replace").splitlines()
        start = max(1, int(data.get("start_line") or 1))
        end = min(len(lines), int(data.get("end_line") or min(start + 299, len(lines))))
        numbered = "\n".join(f"{i+1}: {lines[i]}" for i in range(start-1, end))
        return {"ok": True, "path": path.relative_to(workspace).as_posix(), "start_line": start, "end_line": end, "content": numbered}

    if tool == "search_code":
        query = str(data.get("query") or "")[:200]
        if not query:
            raise HTTPException(400, "query is required")
        regex = re.compile(re.escape(query), re.I)
        hits = []
        for rel in _tree(workspace, limit=1200):
            if len(hits) >= 80:
                break
            path = _safe_path(workspace, rel, allow_missing=False)
            try:
                if path.stat().st_size > 350000:
                    continue
                for n, line in enumerate(path.read_text("utf-8", errors="ignore").splitlines(), start=1):
                    if regex.search(line):
                        hits.append({"path": rel, "line": n, "text": line[:500]})
                        if len(hits) >= 80:
                            break
            except (OSError, UnicodeError):
                continue
        return {"ok": True, "query": query, "hits": hits}

    if tool == "write_file":
        rel = str(data.get("path") or "")
        content = str(data.get("content") or "")
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise HTTPException(413, "Write exceeds file size limit")
        path = _safe_path(workspace, rel, allow_missing=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, "utf-8")
        return {"ok": True, "path": path.relative_to(workspace).as_posix(), "bytes": len(content.encode("utf-8"))}

    if tool == "replace_text":
        path = _safe_path(workspace, str(data.get("path") or ""), allow_missing=False)
        old = str(data.get("old") or "")
        new = str(data.get("new") or "")
        if not old:
            raise HTTPException(400, "old text is required")
        text = path.read_text("utf-8", errors="strict")
        count = text.count(old)
        if count != 1:
            raise HTTPException(409, f"Expected exactly one replacement target, found {count}")
        updated = text.replace(old, new, 1)
        if len(updated.encode("utf-8")) > MAX_FILE_BYTES:
            raise HTTPException(413, "Updated file exceeds size limit")
        path.write_text(updated, "utf-8")
        return {"ok": True, "path": path.relative_to(workspace).as_posix(), "replacements": 1}

    if tool == "run_command":
        argv = data.get("argv") or []
        cwd = str(data.get("cwd") or ".")
        return _run(workspace, argv, cwd)

    if tool == "git_diff":
        diff = _git(workspace, ["diff", "--no-ext-diff", "--", "."], timeout=60)
        untracked = _git(workspace, ["ls-files", "--others", "--exclude-standard"], timeout=30)
        return {"ok": diff.returncode == 0, "diff": _truncate(diff.stdout), "untracked": [x for x in untracked.stdout.splitlines() if x]}

    if tool == "git_status":
        status = _git(workspace, ["status", "--short"], timeout=30)
        return {"ok": status.returncode == 0, "status": _truncate(status.stdout)}

    raise HTTPException(400, f"Unknown tool '{tool}'")


@app.post("/v1/workspaces/{workspace_id}/verify", dependencies=[Depends(_auth)])
async def verify_workspace(workspace_id: str, body: VerifyRequest):
    workspace = _workspace(workspace_id)
    detected = _detect(workspace)
    commands = body.commands or detected.get("verify") or []
    results = []
    for argv in commands[:12]:
        result = _run(workspace, argv, ".", timeout=max(COMMAND_TIMEOUT, 300))
        results.append({"argv": argv, **result})
        if not result["ok"]:
            break
    return {"ok": all(r["ok"] for r in results) if results else True, "results": results, "commands": commands}


def _preview_info(workspace_id: str) -> Optional[Dict[str, Any]]:
    meta = PREVIEWS.get(workspace_id)
    if not meta:
        return None
    process: subprocess.Popen = meta["process"]
    alive = process.poll() is None
    if not alive:
        return {"running": False, "returncode": process.returncode, "logs": _read_preview_logs(meta)}
    public = f"{RUNNER_PUBLIC_URL}/preview/{workspace_id}/?t={meta['token']}" if RUNNER_PUBLIC_URL else None
    return {"running": True, "port": meta["port"], "url": public, "started_at": meta["started_at"]}


def _read_preview_logs(meta: Dict[str, Any]) -> str:
    path: Path = meta["log_path"]
    if not path.exists():
        return ""
    try:
        data = path.read_text("utf-8", errors="replace")
        return _truncate(data)
    except OSError:
        return ""


@app.post("/v1/workspaces/{workspace_id}/preview", dependencies=[Depends(_auth)])
async def start_preview(workspace_id: str, body: PreviewRequest):
    workspace = _workspace(workspace_id)
    previous = PREVIEWS.get(workspace_id)
    if previous and previous["process"].poll() is None:
        previous["process"].terminate()
    if Path(body.argv[0]).name not in ALLOWED_BINARIES:
        raise HTTPException(403, "Preview command is not allowed")
    cwd = _safe_path(workspace, body.cwd, allow_missing=False)
    port = _find_free_port()
    token = secrets.token_urlsafe(24)
    log_path = workspace / ".lucio-preview.log"
    log_handle = open(log_path, "w", encoding="utf-8")
    env = {**os.environ, "PORT": str(port), "HOST": "0.0.0.0", "CI": "0", "BROWSER": "none"}
    process = subprocess.Popen(body.argv, cwd=str(cwd), stdout=log_handle, stderr=subprocess.STDOUT, text=True, env=env)
    PREVIEWS[workspace_id] = {"process": process, "port": port, "token": token, "log_path": log_path, "log_handle": log_handle, "started_at": time.time()}
    await asyncio.sleep(1.2)
    info = _preview_info(workspace_id)
    if info and not info.get("running"):
        raise HTTPException(500, f"Preview exited immediately: {info.get('logs', '')[-1500:]}")
    return info


@app.get("/v1/workspaces/{workspace_id}/preview", dependencies=[Depends(_auth)])
async def preview_status(workspace_id: str):
    _workspace(workspace_id)
    info = _preview_info(workspace_id)
    if info:
        meta = PREVIEWS.get(workspace_id)
        info["logs"] = _read_preview_logs(meta) if meta else ""
    return info or {"running": False}


@app.delete("/v1/workspaces/{workspace_id}/preview", dependencies=[Depends(_auth)])
async def stop_preview(workspace_id: str):
    _workspace(workspace_id)
    meta = PREVIEWS.pop(workspace_id, None)
    if meta:
        process: subprocess.Popen = meta["process"]
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        try:
            meta["log_handle"].close()
        except Exception:
            pass
    return {"ok": True}


@app.api_route("/preview/{workspace_id}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_preview(workspace_id: str, path: str, request: Request):
    meta = PREVIEWS.get(workspace_id)
    if not meta or meta["process"].poll() is not None:
        raise HTTPException(404, "Preview is not running")
    if request.query_params.get("t") != meta["token"]:
        raise HTTPException(403, "Invalid preview token")
    query = [(k, v) for k, v in request.query_params.multi_items() if k != "t"]
    target = f"http://127.0.0.1:{meta['port']}/{path}"
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() not in {"host", "content-length", "connection"}}
    async with httpx.AsyncClient(follow_redirects=False, timeout=30.0) as client:
        res = await client.request(request.method, target, params=query, content=body, headers=headers)
    excluded = {"content-encoding", "transfer-encoding", "connection", "content-length"}
    response_headers = {k: v for k, v in res.headers.items() if k.lower() not in excluded}
    return Response(content=res.content, status_code=res.status_code, headers=response_headers, media_type=res.headers.get("content-type"))


@app.delete("/v1/workspaces/{workspace_id}", dependencies=[Depends(_auth)])
async def delete_workspace(workspace_id: str):
    workspace = _workspace(workspace_id)
    meta = PREVIEWS.pop(workspace_id, None)
    if meta and meta["process"].poll() is None:
        meta["process"].terminate()
    shutil.rmtree(workspace, ignore_errors=True)
    return {"ok": True}
