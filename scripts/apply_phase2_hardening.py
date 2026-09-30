from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{path}: expected one match, found {n}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "runner/server.py",
    "import subprocess\nimport time\n",
    "import subprocess\nimport sys\nimport time\n",
)

replace_once(
    "runner/server.py",
    '''def _run(workspace: Path, argv: List[str], cwd: str = ".", timeout: Optional[int] = None) -> Dict[str, Any]:
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
''',
    '''def _ensure_venv(workspace: Path) -> Path:
    venv = workspace / ".venv"
    python_bin = venv / "bin" / "python"
    if not python_bin.exists():
        created = subprocess.run([sys.executable, "-m", "venv", str(venv)], cwd=str(workspace), capture_output=True, text=True, timeout=90)
        if created.returncode != 0:
            raise HTTPException(500, f"Could not create isolated Python environment: {_truncate(created.stderr or created.stdout)[:1200]}")
    return python_bin


def _run(workspace: Path, argv: List[str], cwd: str = ".", timeout: Optional[int] = None) -> Dict[str, Any]:
    if not argv or not all(isinstance(x, str) and x for x in argv):
        raise HTTPException(400, "argv must contain command arguments")
    binary = Path(argv[0]).name
    if binary not in ALLOWED_BINARIES:
        raise HTTPException(403, f"Command '{binary}' is not allowed")
    workdir = _safe_path(workspace, cwd, allow_missing=False)
    if not workdir.is_dir():
        raise HTTPException(400, "cwd must be a directory")

    actual_argv = [binary, *argv[1:]]
    if binary in {"python", "python3", "pip", "pip3"}:
        venv_python = _ensure_venv(workspace)
        actual_argv[0] = str(venv_python if binary in {"python", "python3"} else venv_python.parent / "pip")
    elif binary in {"pytest", "uvicorn"}:
        candidate = workspace / ".venv" / "bin" / binary
        if candidate.exists():
            actual_argv[0] = str(candidate)

    started = time.monotonic()
    try:
        result = subprocess.run(
            actual_argv,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout or COMMAND_TIMEOUT,
            env={**os.environ, "CI": "1", "NO_COLOR": "1"},
        )
''',
)

replace_once(
    "runner/server.py",
    '''    subprocess.run(["git", "init"], cwd=str(dest), capture_output=True, text=True, timeout=30)
''',
    '''    if (dest / "requirements.txt").exists():
        venv_python = _ensure_venv(dest)
        install = subprocess.run([str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"], cwd=str(dest), capture_output=True, text=True, timeout=240)
        if install.returncode != 0:
            raise HTTPException(500, f"Python scaffold dependency install failed: {_truncate(install.stderr or install.stdout)[:1400]}")

    subprocess.run(["git", "init"], cwd=str(dest), capture_output=True, text=True, timeout=30)
''',
)

replace_once(
    "runner/server.py",
    '''                    result["preview"] = ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "{port}"]
''',
    '''                    result["preview"] = ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "{port}", "--base", "{base}"]
''',
)

replace_once(
    "runner/server.py",
    '''    public = f"{RUNNER_PUBLIC_URL}/preview/{workspace_id}/?t={meta['token']}" if RUNNER_PUBLIC_URL else None
''',
    '''    public = f"{RUNNER_PUBLIC_URL}/preview/{workspace_id}/{meta['token']}/" if RUNNER_PUBLIC_URL else None
''',
)

replace_once(
    "runner/server.py",
    '''    env = {**os.environ, "PORT": str(port), "HOST": "0.0.0.0", "CI": "0", "BROWSER": "none"}
    argv = [str(port) if part == "{port}" else part for part in body.argv]
    process = subprocess.Popen(argv, cwd=str(cwd), stdout=log_handle, stderr=subprocess.STDOUT, text=True, env=env)
''',
    '''    base = f"/preview/{workspace_id}/{token}/"
    env = {**os.environ, "PORT": str(port), "HOST": "0.0.0.0", "CI": "0", "BROWSER": "none", "LUCIO_PREVIEW_BASE": base}
    argv = [str(port) if part == "{port}" else base if part == "{base}" else part for part in body.argv]
    process = subprocess.Popen(argv, cwd=str(cwd), stdout=log_handle, stderr=subprocess.STDOUT, text=True, env=env)
''',
)

replace_once(
    "runner/server.py",
    '''@app.api_route("/preview/{workspace_id}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_preview(workspace_id: str, path: str, request: Request):
    meta = PREVIEWS.get(workspace_id)
    if not meta or meta["process"].poll() is not None:
        raise HTTPException(404, "Preview is not running")
    if request.query_params.get("t") != meta["token"]:
        raise HTTPException(403, "Invalid preview token")
    query = [(k, v) for k, v in request.query_params.multi_items() if k != "t"]
''',
    '''@app.api_route("/preview/{workspace_id}/{token}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_preview(workspace_id: str, token: str, path: str, request: Request):
    meta = PREVIEWS.get(workspace_id)
    if not meta or meta["process"].poll() is not None:
        raise HTTPException(404, "Preview is not running")
    if not secrets.compare_digest(token, meta["token"]):
        raise HTTPException(403, "Invalid preview token")
    query = list(request.query_params.multi_items())
''',
)

print("Phase 2 hardening applied")
