from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1))


# ---- Nexus Runner: support blank-project scaffolds + stronger preview detection ----
replace_once(
    "runner/server.py",
    '''ALLOWED_BINARIES = {
    "npm", "npx", "pnpm", "yarn", "node", "python", "python3", "pytest", "pip", "pip3",
    "uvicorn", "ruff", "eslint", "tsc", "vite", "next", "go", "cargo", "make",
}
''',
    '''ALLOWED_BINARIES = {
    "npm", "npx", "pnpm", "yarn", "node", "python", "python3", "pytest", "pip", "pip3",
    "uvicorn", "ruff", "eslint", "tsc", "vite", "next", "go", "cargo", "make",
}
SUPPORTED_SCAFFOLDS = {"react-vite", "fastapi", "fullstack-fastapi"}
''',
)

replace_once(
    "runner/server.py",
    '''class WorkspaceCreate(BaseModel):
    workspace_id: str = Field(min_length=3, max_length=96)
    repo_url: str
    branch: str = "main"
''',
    '''class WorkspaceCreate(BaseModel):
    workspace_id: str = Field(min_length=3, max_length=96)
    repo_url: Optional[str] = None
    branch: str = "main"
    scaffold: str = "react-vite"
    project_name: str = "Lucio App"
''',
)

marker = '''def _detect(workspace: Path) -> Dict[str, Any]:
'''
scaffold_code = r'''def _scaffold_workspace(dest: Path, preset: str, project_name: str) -> Dict[str, Any]:
    preset = (preset or "react-vite").strip().lower()
    if preset not in SUPPORTED_SCAFFOLDS:
        raise HTTPException(400, f"Unsupported scaffold '{preset}'. Choose one of: {', '.join(sorted(SUPPORTED_SCAFFOLDS))}")
    safe_name = re.sub(r"[^A-Za-z0-9 _.-]", "", project_name or "Lucio App").strip()[:80] or "Lucio App"
    dest.mkdir(parents=True, exist_ok=False)

    if preset == "react-vite":
        (dest / "src").mkdir()
        (dest / "package.json").write_text(json.dumps({
            "name": re.sub(r"[^a-z0-9-]", "-", safe_name.lower()).strip("-") or "lucio-app",
            "private": True,
            "version": "0.1.0",
            "type": "module",
            "scripts": {"dev": "vite", "build": "vite build"},
            "dependencies": {"react": "^19.1.1", "react-dom": "^19.1.1"},
            "devDependencies": {"@vitejs/plugin-react": "^4.6.0", "vite": "^6.4.3"},
        }, indent=2) + "\n")
        (dest / "index.html").write_text('<!doctype html><html><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/><title>' + safe_name + '</title></head><body><div id="root"></div><script type="module" src="/src/main.jsx"></script></body></html>\n')
        (dest / "vite.config.js").write_text("import { defineConfig } from 'vite';\nimport react from '@vitejs/plugin-react';\nexport default defineConfig({ plugins: [react()], base: './' });\n")
        (dest / "src" / "main.jsx").write_text("import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App.jsx';\nimport './index.css';\ncreateRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);\n")
        (dest / "src" / "App.jsx").write_text("export default function App(){return <main className='shell'><p className='eyebrow'>Lucio AI</p><h1>" + safe_name.replace("'", "") + "</h1><p>Your AI development workspace is ready. Tell Lucio what to build.</p></main>}\n")
        (dest / "src" / "index.css").write_text("*{box-sizing:border-box}body{margin:0;background:#09090b;color:#f4f4f5;font-family:Inter,system-ui,sans-serif}.shell{max-width:900px;margin:0 auto;padding:12vh 24px}.eyebrow{color:#a78bfa;text-transform:uppercase;letter-spacing:.18em;font-size:12px}h1{font-size:clamp(44px,8vw,92px);line-height:.95;margin:18px 0}p{color:#a1a1aa;font-size:18px;line-height:1.7}\n")
        install = subprocess.run(["npm", "install", "--no-audit", "--no-fund"], cwd=str(dest), capture_output=True, text=True, timeout=240)
        if install.returncode != 0:
            raise HTTPException(500, f"React scaffold dependency install failed: {_truncate(install.stderr or install.stdout)[:1400]}")

    elif preset == "fastapi":
        (dest / "requirements.txt").write_text("fastapi==0.115.12\nuvicorn[standard]==0.34.2\n")
        (dest / "main.py").write_text("from fastapi import FastAPI\n\napp = FastAPI(title='" + safe_name.replace("'", "") + "')\n\n@app.get('/api/health')\ndef health():\n    return {'status': 'ok'}\n\n@app.get('/')\ndef root():\n    return {'app': '" + safe_name.replace("'", "") + "', 'message': 'Built with Lucio AI'}\n")

    else:
        (dest / "requirements.txt").write_text("fastapi==0.115.12\nuvicorn[standard]==0.34.2\n")
        (dest / "main.py").write_text("from fastapi import FastAPI\nfrom fastapi.responses import HTMLResponse\n\napp = FastAPI(title='" + safe_name.replace("'", "") + "')\n\n@app.get('/api/health')\ndef health():\n    return {'status': 'ok'}\n\n@app.get('/', response_class=HTMLResponse)\ndef home():\n    return '''<!doctype html><html><meta name=viewport content='width=device-width,initial-scale=1'><style>body{margin:0;background:#09090b;color:#fafafa;font-family:system-ui}.wrap{max-width:900px;margin:auto;padding:12vh 24px}small{color:#a78bfa;text-transform:uppercase;letter-spacing:.18em}h1{font-size:clamp(44px,8vw,88px);line-height:.95}p{color:#a1a1aa;font-size:18px;line-height:1.7}</style><div class=wrap><small>Lucio AI full-stack starter</small><h1>" + safe_name.replace("<", "").replace(">", "") + "</h1><p>FastAPI backend and a live frontend are ready for the Dev Agent to extend.</p></div></html>'''\n")

    subprocess.run(["git", "init"], cwd=str(dest), capture_output=True, text=True, timeout=30)
    subprocess.run(["git", "config", "user.email", "dev-agent@lucio.local"], cwd=str(dest), capture_output=True, text=True, timeout=15)
    subprocess.run(["git", "config", "user.name", "Lucio Dev Agent"], cwd=str(dest), capture_output=True, text=True, timeout=15)
    subprocess.run(["git", "add", "."], cwd=str(dest), capture_output=True, text=True, timeout=30)
    commit = subprocess.run(["git", "commit", "-m", "Lucio scaffold baseline"], cwd=str(dest), capture_output=True, text=True, timeout=30)
    if commit.returncode != 0:
        raise HTTPException(500, f"Could not initialize scaffold baseline: {_truncate(commit.stderr or commit.stdout)[:1200]}")
    return {"preset": preset, "project_name": safe_name}


'''
replace_once("runner/server.py", marker, scaffold_code + marker)

replace_once(
    "runner/server.py",
    '''            if "dev" in result["scripts"]:
                result["preview"] = ["npm", "run", "dev"]
            elif "start" in result["scripts"]:
                result["preview"] = ["npm", "start"]
''',
    '''            if "dev" in result["scripts"]:
                if "vite" in deps:
                    result["preview"] = ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "{port}"]
                elif "next" in deps:
                    result["preview"] = ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "{port}"]
                else:
                    result["preview"] = ["npm", "run", "dev"]
            elif "start" in result["scripts"]:
                result["preview"] = ["npm", "start"]
''',
)

replace_once(
    "runner/server.py",
    '''    if (workspace / "requirements.txt").exists() or (workspace / "pyproject.toml").exists():
        result["stack"].append("python")
        if (workspace / "pytest.ini").exists() or (workspace / "tests").exists():
            result["verify"].append(["pytest", "-q"])
''',
    '''    if (workspace / "requirements.txt").exists() or (workspace / "pyproject.toml").exists():
        result["stack"].append("python")
        if (workspace / "main.py").exists():
            result["verify"].append(["python", "-m", "py_compile", "main.py"])
            try:
                if "FastAPI(" in (workspace / "main.py").read_text("utf-8", errors="ignore"):
                    result["preview"] = ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "{port}"]
            except OSError:
                pass
        if (workspace / "pytest.ini").exists() or (workspace / "tests").exists():
            result["verify"].append(["pytest", "-q"])
''',
)

replace_once(
    "runner/server.py",
    '''@app.post("/v1/workspaces", dependencies=[Depends(_auth)])
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
''',
    '''@app.post("/v1/workspaces", dependencies=[Depends(_auth)])
async def create_workspace(body: WorkspaceCreate):
    wid = _workspace_id(body.workspace_id)
    dest = (ROOT / wid).resolve()
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)

    scaffold = None
    repository = None
    if body.repo_url:
        repo = _validate_repo_url(body.repo_url)
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", body.branch, "--single-branch", repo, str(dest)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if clone.returncode != 0:
            shutil.rmtree(dest, ignore_errors=True)
            raise HTTPException(400, f"Repository clone failed: {_truncate(clone.stderr or clone.stdout)[:1200]}")
        repository = body.repo_url
    else:
        scaffold = _scaffold_workspace(dest, body.scaffold, body.project_name)

    inspection = {"files": _tree(dest), **_detect(dest)}
    inspection["source_mode"] = "repository" if repository else "scaffold"
    if scaffold:
        inspection["scaffold"] = scaffold
    return {"workspace_id": wid, "branch": body.branch, "repository": repository, "scaffold": scaffold, "inspection": inspection}
''',
)

replace_once(
    "runner/server.py",
    '''    env = {**os.environ, "PORT": str(port), "HOST": "0.0.0.0", "CI": "0", "BROWSER": "none"}
    process = subprocess.Popen(body.argv, cwd=str(cwd), stdout=log_handle, stderr=subprocess.STDOUT, text=True, env=env)
''',
    '''    env = {**os.environ, "PORT": str(port), "HOST": "0.0.0.0", "CI": "0", "BROWSER": "none"}
    argv = [str(port) if part == "{port}" else part for part in body.argv]
    process = subprocess.Popen(argv, cwd=str(cwd), stdout=log_handle, stderr=subprocess.STDOUT, text=True, env=env)
''',
)

# ---- Production API: repository OR new-app scaffold mode ----
replace_once(
    "backend/dev_agent.py",
    '''class DevConfigIn(BaseModel):
    repo_url: Optional[str] = None
    branch: str = "main"
    preview_argv: Optional[List[str]] = None
    verify_commands: Optional[List[List[str]]] = None
''',
    '''SUPPORTED_SCAFFOLDS = {"react-vite", "fastapi", "fullstack-fastapi"}


class DevConfigIn(BaseModel):
    repo_url: Optional[str] = None
    branch: str = "main"
    scaffold: Optional[str] = "react-vite"
    preview_argv: Optional[List[str]] = None
    verify_commands: Optional[List[List[str]]] = None
''',
)

replace_once(
    "backend/dev_agent.py",
    '''class SessionCreateIn(BaseModel):
    goal: str = Field(min_length=5, max_length=12000)
    repo_url: Optional[str] = None
    branch: Optional[str] = None
    auto_execute: bool = False
''',
    '''class SessionCreateIn(BaseModel):
    goal: str = Field(min_length=5, max_length=12000)
    repo_url: Optional[str] = None
    branch: Optional[str] = None
    scaffold: Optional[str] = None
    project_name: Optional[str] = Field(default=None, max_length=120)
    auto_execute: bool = False
''',
)

replace_once(
    "backend/dev_agent.py",
    '''            "phases": {
                "phase_1_dev_agent": True,
                "phase_2_isolated_runtime": bool(runner.get("configured")),
                "phase_3_agentic_loop": True,
                "phase_4_goal_to_working_app": True,
            },
            "capabilities": ["repository_inspection", "planning", "read_search", "code_editing", "commands", "tests", "self_healing", "git_diff", "review", "live_preview", "approval_gate"],
''',
    '''            "phases": {
                "phase_1_dev_agent": True,
                "phase_2_isolated_runtime": bool(runner.get("configured")),
                "phase_3_agentic_loop": True,
                "phase_4_goal_to_working_app": True,
            },
            "scaffolds": sorted(SUPPORTED_SCAFFOLDS),
            "capabilities": ["repository_inspection", "new_app_scaffolding", "planning", "read_search", "code_editing", "commands", "tests", "self_healing", "git_diff", "review", "live_preview", "approval_gate"],
''',
)

replace_once(
    "backend/dev_agent.py",
    '''        return doc.get("dev_agent") or {"repo_url": "", "branch": "main", "preview_argv": None, "verify_commands": None}
''',
    '''        return doc.get("dev_agent") or {"repo_url": "", "branch": "main", "scaffold": "react-vite", "preview_argv": None, "verify_commands": None}
''',
)

replace_once(
    "backend/dev_agent.py",
    '''        if data.get("repo_url"):
            data["repo_url"] = _clean_repo_url(data["repo_url"])
        merged = {**current, **data, "updated_at": _now()}
''',
    '''        if data.get("repo_url"):
            data["repo_url"] = _clean_repo_url(data["repo_url"])
        if data.get("scaffold"):
            scaffold = str(data["scaffold"]).strip().lower()
            if scaffold not in SUPPORTED_SCAFFOLDS:
                raise HTTPException(400, f"Unsupported scaffold: {scaffold}")
            data["scaffold"] = scaffold
        merged = {**current, **data, "updated_at": _now()}
''',
)

replace_once(
    "backend/dev_agent.py",
    '''        app_doc = await require_editor(app_id, user)
        config = app_doc.get("dev_agent") or {}
        repo_url = _clean_repo_url(body.repo_url or config.get("repo_url") or "")
        branch = (body.branch or config.get("branch") or "main").strip()[:160]
        session_id = _id("dev")
''',
    '''        app_doc = await require_editor(app_id, user)
        config = app_doc.get("dev_agent") or {}
        repo_candidate = (body.repo_url or config.get("repo_url") or "").strip()
        repo_url = _clean_repo_url(repo_candidate) if repo_candidate else ""
        scaffold = (body.scaffold or config.get("scaffold") or "react-vite").strip().lower()
        if scaffold not in SUPPORTED_SCAFFOLDS:
            raise HTTPException(400, f"Unsupported scaffold: {scaffold}")
        source_mode = "repository" if repo_url else "scaffold"
        branch = (body.branch or config.get("branch") or "main").strip()[:160]
        session_id = _id("dev")
''',
)

replace_once(
    "backend/dev_agent.py",
    '''            "repo_url": repo_url,
            "branch": branch,
            "status": "preparing",
            "config": {**config, "repo_url": repo_url, "branch": branch},
''',
    '''            "repo_url": repo_url,
            "branch": branch,
            "source_mode": source_mode,
            "scaffold": scaffold if source_mode == "scaffold" else None,
            "status": "preparing",
            "config": {**config, "repo_url": repo_url, "branch": branch, "scaffold": scaffold},
''',
)

replace_once(
    "backend/dev_agent.py",
    '''            runner = await _runner("POST", "/v1/workspaces", body={"workspace_id": workspace_id, "repo_url": repo_url, "branch": branch}, timeout=180.0)
            inspection = runner.get("inspection") or runner
            await _set_session(db, session_id, status="planning", inspection=inspection)
            await _push_event(db, session_id, "workspace", "Repository cloned and inspected", {"stack": inspection.get("stack"), "file_count": len(inspection.get("files") or [])})
''',
    '''            runner = await _runner("POST", "/v1/workspaces", body={
                "workspace_id": workspace_id,
                "repo_url": repo_url or None,
                "branch": branch,
                "scaffold": scaffold,
                "project_name": body.project_name or app_doc.get("name") or "Lucio App",
            }, timeout=300.0)
            inspection = runner.get("inspection") or runner
            await _set_session(db, session_id, status="planning", inspection=inspection)
            await _push_event(db, session_id, "workspace", "Development workspace prepared and inspected", {"source_mode": source_mode, "scaffold": inspection.get("scaffold"), "stack": inspection.get("stack"), "file_count": len(inspection.get("files") or [])})
''',
)

# ---- Frontend: make repo optional and expose scaffold choices ----
replace_once(
    "frontend/src/components/DevAgentPanel.tsx",
    '''  const [config, setConfig] = useState<AnyDoc>({ repo_url: "", branch: "main" });
''',
    '''  const [config, setConfig] = useState<AnyDoc>({ repo_url: "", branch: "main", scaffold: "react-vite" });
''',
)
replace_once(
    "frontend/src/components/DevAgentPanel.tsx",
    '''      setConfig(c.data || { repo_url: "", branch: "main" });
''',
    '''      setConfig(c.data || { repo_url: "", branch: "main", scaffold: "react-vite" });
''',
)
replace_once(
    "frontend/src/components/DevAgentPanel.tsx",
    '''      const body: AnyDoc = { repo_url: config.repo_url?.trim() || null, branch: config.branch?.trim() || "main" };
''',
    '''      const body: AnyDoc = { repo_url: config.repo_url?.trim() || null, branch: config.branch?.trim() || "main", scaffold: config.scaffold || "react-vite" };
''',
)
replace_once(
    "frontend/src/components/DevAgentPanel.tsx",
    '''    if (!config.repo_url?.trim()) return toast.error("Connect this app to its GitHub repository first");
''',
    '''    // A GitHub repository is optional. When blank, Lucio starts from the selected production scaffold.
''',
)
replace_once(
    "frontend/src/components/DevAgentPanel.tsx",
    '''        goal: goal.trim(), repo_url: config.repo_url.trim(), branch: config.branch || "main", auto_execute: auto,
''',
    '''        goal: goal.trim(), repo_url: config.repo_url?.trim() || null, branch: config.branch || "main", scaffold: config.scaffold || "react-vite", project_name: appDoc?.name || "Lucio App", auto_execute: auto,
''',
)
replace_once(
    "frontend/src/components/DevAgentPanel.tsx",
    '''            <label className="mb-2 block text-xs font-medium uppercase tracking-wider text-[var(--mut)]">GitHub repository</label>
            <div className="grid gap-3 md:grid-cols-[1fr_180px]">
''',
    '''            <label className="mb-2 block text-xs font-medium uppercase tracking-wider text-[var(--mut)]">GitHub repository <span className="normal-case tracking-normal text-[var(--mut)]/70">(optional — leave blank to start a new app)</span></label>
            <div className="grid gap-3 md:grid-cols-[1fr_160px_190px]">
''',
)
replace_once(
    "frontend/src/components/DevAgentPanel.tsx",
    '''              <div className="relative">
                <GitBranch size={14} className="absolute left-3 top-3.5 text-[var(--mut)]" />
                <input value={config.branch || "main"} onChange={(e) => setConfig((c: AnyDoc) => ({ ...c, branch: e.target.value }))}
                  placeholder="main" className="input w-full pl-9" />
              </div>
            </div>
''',
    '''              <div className="relative">
                <GitBranch size={14} className="absolute left-3 top-3.5 text-[var(--mut)]" />
                <input value={config.branch || "main"} onChange={(e) => setConfig((c: AnyDoc) => ({ ...c, branch: e.target.value }))}
                  placeholder="main" className="input w-full pl-9" />
              </div>
              <select value={config.scaffold || "react-vite"} onChange={(e) => setConfig((c: AnyDoc) => ({ ...c, scaffold: e.target.value }))} className="input w-full text-sm" title="Starter used when no repository is supplied">
                <option value="react-vite">React + Vite starter</option>
                <option value="fastapi">FastAPI starter</option>
                <option value="fullstack-fastapi">Full-stack FastAPI starter</option>
              </select>
            </div>
            <p className="mt-2 text-xs text-[var(--mut)]">Connect an existing repository to improve it, or leave the repository blank and Lucio will create an isolated starter project before planning and coding.</p>
''',
)

print("Dev Agent phase 2 patch applied")
