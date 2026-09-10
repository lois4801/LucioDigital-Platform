"""Rename visible 'template' copy to 'project'. Internals (paths, ids, keys) are left alone."""
import re
import subprocess
import sys

SKIP_SUBSTR = ("/", "api", "_", "data-testid", "template-", "@")
WORDS = [("Templates", "Projects"), ("Template", "Project"), ("templates", "projects"), ("template", "project")]


def swap(text: str) -> str:
    for a, b in WORDS:
        text = re.sub(rf"\b{a}\b", b, text)
    return text


def ok_literal(s: str) -> bool:
    low = s.lower()
    if any(x in low for x in SKIP_SUBSTR):
        return False
    return bool(re.search(r"\btemplates?\b", low))


def process(path: str) -> bool:
    src = open(path).read()
    out, i, changed = [], 0, False

    # 1) JSX text nodes: >…text…<
    def jsx(m):
        nonlocal changed
        body = m.group(1)
        if "{" in body or not re.search(r"\btemplates?\b", body, re.I):
            return m.group(0)
        new = swap(body)
        changed = changed or new != body
        return f">{new}<"

    src = re.sub(r">([^<>{}]*?)<", jsx, src)

    # 2) quoted string literals that look like human copy
    def lit(m):
        nonlocal changed
        q, body = m.group(1), m.group(2)
        if not ok_literal(body):
            return m.group(0)
        new = swap(body)
        changed = changed or new != body
        return f"{q}{new}{q}"

    src = re.sub(r'(["\'])([^"\'\n]*)\1', lit, src)
    open(path, "w").write(src)
    return changed


files = sys.argv[1:] or subprocess.check_output(
    ["bash", "-lc", "grep -rl 'emplate' /app/frontend/src /app/backend --include=*.tsx --include=*.ts --include=*.py | grep -v tests/"],
    text=True).split()
hit = [f for f in files if process(f)]
print(f"files touched: {len(hit)}")
for f in hit:
    print(" ", f)
