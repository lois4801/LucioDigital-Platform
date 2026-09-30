from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{path}: expected one match, found {n}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---------- Nexus Runner: safe source ZIP export ----------
replace_once(
    "runner/server.py",
    "import asyncio\nimport json\n",
    "import asyncio\nimport io\nimport json\n",
)
replace_once(
    "runner/server.py",
    "import time\nfrom pathlib import Path\n",
    "import time\nimport zipfile\nfrom pathlib import Path\n",
)
replace_once(
    "runner/server.py",
    '''COMMAND_TIMEOUT = int(os.environ.get("NEXUS_RUNNER_COMMAND_TIMEOUT", "180"))\n''',
    '''COMMAND_TIMEOUT = int(os.environ.get("NEXUS_RUNNER_COMMAND_TIMEOUT", "180"))\nMAX_ARCHIVE_SOURCE_BYTES = int(os.environ.get("NEXUS_RUNNER_MAX_ARCHIVE_SOURCE_BYTES", str(50 * 1024 * 1024)))\nMAX_ARCHIVE_FILES = int(os.environ.get("NEXUS_RUNNER_MAX_ARCHIVE_FILES", "5000"))\n''',
)

archive_code = r'''
def _workspace_archive(workspace: Path) -> tuple[bytes, int]:
    """Create a source-only ZIP. Dependencies, build output, VCS data and secret-like paths are excluded."""
    buffer = io.BytesIO()
    total_source = 0
    included = 0
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(workspace.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(workspace)
            parts = set(rel.parts)
            if parts & IGNORED_TREE or parts & DENIED_PARTS:
                continue
            if any(part.lower() in DENIED_PARTS for part in rel.parts):
                continue
            if rel.name == ".lucio-preview.log":
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            total_source += size
            included += 1
            if included > MAX_ARCHIVE_FILES:
                raise HTTPException(413, f"Workspace contains more than {MAX_ARCHIVE_FILES} exportable files")
            if total_source > MAX_ARCHIVE_SOURCE_BYTES:
                raise HTTPException(413, f"Workspace source exceeds {MAX_ARCHIVE_SOURCE_BYTES // (1024 * 1024)} MB export limit")
            zf.write(path, arcname=rel.as_posix())
    return buffer.getvalue(), included


@app.get("/v1/workspaces/{workspace_id}/archive", dependencies=[Depends(_auth)])
async def archive_workspace(workspace_id: str):
    workspace = _workspace(workspace_id)
    payload, files = _workspace_archive(workspace)
    return Response(
        content=payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{workspace_id}.zip"',
            "X-Lucio-Archive-Files": str(files),
            "Cache-Control": "no-store",
        },
    )


'''
replace_once(
    "runner/server.py",
    '''@app.get("/v1/workspaces/{workspace_id}", dependencies=[Depends(_auth)])\nasync def inspect_workspace(workspace_id: str):\n''',
    archive_code + '''@app.get("/v1/workspaces/{workspace_id}", dependencies=[Depends(_auth)])\nasync def inspect_workspace(workspace_id: str):\n''',
)

# ---------- Backend: persist approved workspace ZIP to configured storage ----------
replace_once(
    "backend/dev_agent.py",
    '''from fastapi import BackgroundTasks, Depends, HTTPException\n''',
    '''from fastapi import BackgroundTasks, Depends, HTTPException, Response\n''',
)
replace_once(
    "backend/dev_agent.py",
    '''import httpx\nfrom fastapi import BackgroundTasks, Depends, HTTPException, Response\n''',
    '''import httpx\nfrom fastapi import BackgroundTasks, Depends, HTTPException, Response\nfrom storage import get_object, put_object\n''',
)

runner_bytes_code = r'''

async def _runner_bytes(path: str, *, timeout: float = 180.0) -> tuple[bytes, str]:
    if not RUNNER_URL:
        raise HTTPException(503, "NEXUS_RUNNER_URL is not configured")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.get(f"{RUNNER_URL}{path}", headers=_runner_headers())
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Nexus Runner is unreachable: {str(exc)[:220]}")
    if res.status_code >= 400:
        try:
            detail = res.json().get("detail")
        except Exception:
            detail = res.text[:1200]
        raise HTTPException(res.status_code, f"Runner: {str(detail)[:1200]}")
    return res.content, res.headers.get("content-type", "application/octet-stream")
'''
replace_once(
    "backend/dev_agent.py",
    '''async def _runner_health() -> dict:\n''',
    runner_bytes_code + '''\n\nasync def _runner_health() -> dict:\n''',
)

replace_once(
    "backend/dev_agent.py",
    '''                "phase_4_goal_to_working_app": True,\n            },\n            "scaffolds": sorted(SUPPORTED_SCAFFOLDS),\n            "capabilities": ["repository_inspection", "new_app_scaffolding", "planning", "read_search", "code_editing", "commands", "tests", "self_healing", "git_diff", "review", "live_preview", "approval_gate"],\n''',
    '''                "phase_4_goal_to_working_app": True,\n                "phase_5_durable_artifacts": True,\n            },\n            "scaffolds": sorted(SUPPORTED_SCAFFOLDS),\n            "capabilities": ["repository_inspection", "new_app_scaffolding", "planning", "read_search", "code_editing", "commands", "tests", "self_healing", "git_diff", "review", "live_preview", "approval_gate", "durable_artifacts", "project_zip_export"],\n''',
)

old_approve = '''    @api.post("/apps/{app_id}/dev-agent/sessions/{session_id}/approve")\n    async def approve(app_id: str, session_id: str, body: DecisionIn, user: dict = Depends(get_current_user)):\n        await require_editor(app_id, user)\n        doc = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})\n        if not doc:\n            raise HTTPException(404, "Dev Agent session not found")\n        decision = {"state": "approved", "by": user["user_id"], "at": _now(), "note": body.note}\n        await _set_session(db, session_id, status="approved", decision=decision)\n        await _push_event(db, session_id, "approval", "Change set approved by human reviewer", decision)\n        if body.cleanup_workspace:\n            try:\n                await _runner("DELETE", f"/v1/workspaces/{doc['workspace_id']}", timeout=30.0)\n            except Exception:\n                pass\n        return {"session_id": session_id, "status": "approved", "decision": decision, "diff": doc.get("diff")}\n'''
new_approve = '''    @api.post("/apps/{app_id}/dev-agent/sessions/{session_id}/approve")\n    async def approve(app_id: str, session_id: str, body: DecisionIn, user: dict = Depends(get_current_user)):\n        await require_editor(app_id, user)\n        doc = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0})\n        if not doc:\n            raise HTTPException(404, "Dev Agent session not found")\n\n        # Approval first creates a durable source artifact. If persistence fails, keep the\n        # session reviewable and do not delete its workspace.\n        artifact = doc.get("artifact")\n        if not artifact:\n            try:\n                payload, content_type = await _runner_bytes(f"/v1/workspaces/{doc['workspace_id']}/archive", timeout=180.0)\n                if not payload:\n                    raise RuntimeError("Runner returned an empty project archive")\n                filename = f"lucio-{app_id}-{session_id}.zip"\n                storage_path = f"omnistack/dev-agent/{app_id}/{session_id}.zip"\n                stored = put_object(storage_path, payload, "application/zip")\n                artifact = {\n                    "file_id": f"devagent-{session_id}",\n                    "storage_path": stored.get("path", storage_path),\n                    "filename": filename,\n                    "content_type": "application/zip",\n                    "size": stored.get("size", len(payload)),\n                    "saved_at": _now(),\n                    "download_url": f"/api/apps/{app_id}/dev-agent/sessions/{session_id}/artifact",\n                }\n                await db.files.update_one(\n                    {"file_id": artifact["file_id"]},\n                    {"$set": {\n                        "file_id": artifact["file_id"], "app_id": app_id, "storage_path": artifact["storage_path"],\n                        "original_filename": filename, "content_type": "application/zip", "size": artifact["size"],\n                        "private": True, "is_deleted": False, "source": "dev_agent", "session_id": session_id,\n                        "created_at": artifact["saved_at"],\n                    }},\n                    upsert=True,\n                )\n                await _set_session(db, session_id, artifact=artifact)\n                await _push_event(db, session_id, "artifact", "Approved project source saved as a durable ZIP artifact", {"filename": filename, "size": artifact["size"]})\n            except HTTPException:\n                raise\n            except Exception as exc:\n                logger.exception("Could not persist Dev Agent artifact for %s", session_id)\n                raise HTTPException(502, f"Could not persist project artifact: {str(exc)[:300]}")\n\n        decision = {"state": "approved", "by": user["user_id"], "at": _now(), "note": body.note}\n        await _set_session(db, session_id, status="approved", decision=decision, artifact=artifact)\n        await _push_event(db, session_id, "approval", "Change set approved by human reviewer", decision)\n        if body.cleanup_workspace:\n            try:\n                await _runner("DELETE", f"/v1/workspaces/{doc['workspace_id']}", timeout=30.0)\n                await _set_session(db, session_id, workspace_cleaned_at=_now(), preview=None)\n            except Exception:\n                pass\n        return {"session_id": session_id, "status": "approved", "decision": decision, "diff": doc.get("diff"), "artifact": artifact}\n\n    @api.get("/apps/{app_id}/dev-agent/sessions/{session_id}/artifact")\n    async def download_artifact(app_id: str, session_id: str, user: dict = Depends(get_current_user)):\n        await get_app(app_id, user)\n        doc = await db.dev_agent_sessions.find_one({"app_id": app_id, "session_id": session_id}, {"_id": 0, "artifact": 1})\n        if not doc or not doc.get("artifact"):\n            raise HTTPException(404, "No durable project artifact is available for this run")\n        artifact = doc["artifact"]\n        try:\n            payload, content_type = get_object(artifact["storage_path"])\n        except HTTPException:\n            raise\n        except Exception as exc:\n            raise HTTPException(502, f"Could not read project artifact: {str(exc)[:240]}")\n        filename = re.sub(r"[^A-Za-z0-9_.-]", "-", artifact.get("filename") or f"lucio-{session_id}.zip")\n        return Response(\n            content=payload,\n            media_type=artifact.get("content_type") or content_type or "application/zip",\n            headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},\n        )\n'''
replace_once("backend/dev_agent.py", old_approve, new_approve)

# ---------- Frontend: download durable approved project ----------
replace_once(
    "frontend/src/components/DevAgentPanel.tsx",
    '''  async function decide(state: "approve" | "reject") {\n''',
    '''  async function downloadArtifact() {\n    if (!activeId) return;\n    setBusy("download");\n    try {\n      const url = active?.artifact?.download_url || `/apps/${appId}/dev-agent/sessions/${activeId}/artifact`;\n      const res = await api.get(url, { responseType: "blob" });\n      const blob = new Blob([res.data], { type: res.headers?.["content-type"] || "application/zip" });\n      const href = URL.createObjectURL(blob);\n      const a = document.createElement("a");\n      a.href = href;\n      a.download = active?.artifact?.filename || `lucio-${activeId}.zip`;\n      document.body.appendChild(a);\n      a.click();\n      a.remove();\n      URL.revokeObjectURL(href);\n      toast.success("Project source ZIP downloaded");\n    } catch (e: any) { toast.error(e.response?.data?.detail || "Could not download project artifact"); }\n    finally { setBusy(""); }\n  }\n\n  async function decide(state: "approve" | "reject") {\n''',
)

replace_once(
    "frontend/src/components/DevAgentPanel.tsx",
    '''      toast.success(state === "approve" ? "Change set approved" : "Change set rejected");\n''',
    '''      toast.success(state === "approve" ? "Change set approved and project source saved" : "Change set rejected");\n''',
)

replace_once(
    "frontend/src/components/DevAgentPanel.tsx",
    '''                  {active.status === "awaiting_approval" && <div className="mt-5 flex flex-wrap gap-3"><button onClick={() => decide("approve")} disabled={!!busy} className="btn-primary flex items-center gap-2"><Check size={14} /> Approve change set</button><button onClick={() => decide("reject")} disabled={!!busy} className="btn-ghost flex items-center gap-2 text-red-300"><X size={14} /> Reject</button></div>}\n''',
    '''                  {active.status === "awaiting_approval" && <div className="mt-5 flex flex-wrap gap-3"><button onClick={() => decide("approve")} disabled={!!busy} className="btn-primary flex items-center gap-2"><Check size={14} /> {busy === "approve" ? "Saving project…" : "Approve & save project"}</button><button onClick={() => decide("reject")} disabled={!!busy} className="btn-ghost flex items-center gap-2 text-red-300"><X size={14} /> Reject</button></div>}\n                  {active.artifact?.download_url && <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/[.05] p-4"><div className="min-w-0 flex-1"><div className="text-xs font-semibold text-emerald-300">Durable project source saved</div><div className="mt-1 truncate text-xs text-[var(--mut)]">{active.artifact.filename} · {Math.max(1, Math.round((active.artifact.size || 0) / 1024))} KB</div></div><button onClick={downloadArtifact} disabled={!!busy} className="btn-ghost flex items-center gap-2 text-xs"><FileCode2 size={13} /> {busy === "download" ? "Preparing…" : "Download ZIP"}</button></div>}\n''',
)

print("Dev Agent durable artifact phase applied")
