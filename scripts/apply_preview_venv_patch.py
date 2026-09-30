from pathlib import Path

p = Path('runner/server.py')
text = p.read_text(encoding='utf-8')
old = '''    argv = [str(port) if part == "{port}" else base if part == "{base}" else part for part in body.argv]\n    process = subprocess.Popen(argv, cwd=str(cwd), stdout=log_handle, stderr=subprocess.STDOUT, text=True, env=env)\n'''
new = '''    argv = [str(port) if part == "{port}" else base if part == "{base}" else part for part in body.argv]\n    binary = Path(argv[0]).name\n    if binary in {"python", "python3", "uvicorn"}:\n        candidate = workspace / ".venv" / "bin" / ("python" if binary in {"python", "python3"} else binary)\n        if candidate.exists():\n            argv[0] = str(candidate)\n    process = subprocess.Popen(argv, cwd=str(cwd), stdout=log_handle, stderr=subprocess.STDOUT, text=True, env=env)\n'''
if text.count(old) != 1:
    raise SystemExit(f'Expected exactly one preview launch block, found {text.count(old)}')
p.write_text(text.replace(old, new, 1), encoding='utf-8')
print('Preview virtualenv patch applied')
