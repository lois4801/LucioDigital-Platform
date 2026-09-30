from pathlib import Path

source = Path("scripts/apply_dev_agent_phase2.py").read_text(encoding="utf-8")
source = source.replace("scaffold_code = r'''", 'scaffold_code = r"""', 1)
source = source.replace("\n'''\nreplace_once(\"runner/server.py\", marker, scaffold_code + marker)", "\n\"\"\"\nreplace_once(\"runner/server.py\", marker, scaffold_code + marker)", 1)
compile(source, "apply_dev_agent_phase2.py", "exec")
exec(compile(source, "apply_dev_agent_phase2.py", "exec"), {"__name__": "__main__"})
