"""Pass 2: catch the visible copy pass 1 missed — JSX text mixed with {interpolation},
ternary strings, docstrings and comments. Identifiers and contracts stay protected."""
import re
from pathlib import Path

ROOTS = [Path("/app/frontend/src"), Path("/app/backend")]
EXTS = {".tsx", ".jsx", ".ts", ".js", ".py"}
SKIP_DIRS = {"node_modules", ".git", "tests", "__pycache__", "test_reports"}

MAP = {"Tenants": "Clients", "tenants": "clients", "TENANTS": "CLIENTS",
       "Tenant": "Client", "tenant": "client", "TENANT": "CLIENT"}

# A match is skipped when any of these sit right around it — these are contracts, not copy.
BEFORE_SKIP = re.compile(r"[.\w_\-/]$")          # data.tenants, tenant_id, tenant-scroll, /tenants
AFTER_SKIP = re.compile(r"^[\w_\-]")             # tenant_id, tenants_count, tenant-v2
WORD = re.compile(r"\b(Tenants|tenants|TENANTS|Tenant|tenant|TENANT)\b")

# lines that are pure plumbing: imports, route strings, mongo collections, testids we keep stable
LINE_SKIP = re.compile(r"^\s*(import|from)\s|db\.tenants|api\.(get|put|post|delete)\(\"/[^\"]*tenants")


def fix(line: str) -> str:
    if LINE_SKIP.search(line):
        return line
    out, last = [], 0
    for m in WORD.finditer(line):
        before, after = line[:m.start()], line[m.end():]
        key = m.group(1)
        skip = bool(before and BEFORE_SKIP.search(before)) or bool(after and AFTER_SKIP.match(after))
        # an object/dict key such as "tenants": … or tenants: … stays as the contract it is
        if not skip and after.lstrip().startswith(":") and re.search(r"[\{,\(]\s*[\"']?$", before):
            skip = True
        # a quoted string that is exactly the field name stays
        if not skip and re.search(r"[\"']$", before) and re.match(r"^[\"']", after):
            skip = True
        out.append(line[last:m.start()])
        out.append(key if skip else MAP[key])
        last = m.end()
    out.append(line[last:])
    return "".join(out)


changed_files = changed_lines = 0
for root in ROOTS:
    for p in sorted(root.rglob("*")):
        if p.is_dir() or p.suffix not in EXTS or any(d in p.parts for d in SKIP_DIRS):
            continue
        src = p.read_text()
        lines = src.split("\n")
        new = [fix(ln) for ln in lines]
        n = sum(1 for a, b in zip(lines, new) if a != b)
        if n:
            p.write_text("\n".join(new))
            changed_files += 1
            changed_lines += n
            print(f"{p}: {n}", flush=True)
print(f"\npass 2: {changed_lines} lines in {changed_files} files")
