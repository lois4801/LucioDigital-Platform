"""Replace the word tenant with client in USER-VISIBLE copy only.
Identifiers stay: API/DB fields (tenant_id), collection and route names, CSS class names.
data-testid values are renamed (they are not persisted anywhere)."""
import re
import sys
from pathlib import Path

ROOTS = [Path("/app/frontend/src"), Path("/app/backend")]
EXTS = {".tsx", ".jsx", ".ts", ".js", ".py", ".css"}
SKIP_DIRS = {"node_modules", ".git", "tests", "__pycache__", "test_reports"}

# Things that must never change — they are contracts, not copy.
PROTECT = [
    r"tenant_id", r"tenant_ids", r"tenantId", r"tenant_key", r"tenant_trash",
    r"tenant-scroll", r"tenant-v2", r"tenantV2",
    r"/tenants", r"/tenant\b", r"landing/tenants",
    r"db\.tenants", r"\.tenants\b",
    r"\"tenants\"\s*:", r"'tenants'\s*:",
]

WORD = re.compile(r"\b(Tenants|tenants|TENANTS|Tenant|tenant|TENANT)\b")
MAP = {"Tenants": "Clients", "tenants": "clients", "TENANTS": "CLIENTS",
       "Tenant": "Client", "tenant": "client", "TENANT": "CLIENT"}

STRING = re.compile(r"(\"[^\"\n]*\"|'[^'\n]*'|`[^`\n]*`)")
JSX_TEXT = re.compile(r">([^<>{}\n]*[A-Za-z][^<>{}\n]*)<")


def protected(seg: str) -> bool:
    if any(re.search(p, seg) for p in PROTECT):
        return True
    inner = seg.strip("\"'`")
    if inner.startswith("/") or inner in ("tenants", "tenant"):
        return True
    return False


def swap(text: str) -> str:
    return WORD.sub(lambda m: MAP[m.group(1)], text)


def process(path: Path) -> int:
    src = path.read_text()
    out, changed = [], 0
    for line in src.split("\n"):
        if not WORD.search(line):
            out.append(line)
            continue
        new = line
        # 1) string literals that are copy, not contracts
        def fix_string(m):
            seg = m.group(1)
            if protected(seg):
                return seg
            # a dict/object key like "tenants": … is a contract
            return swap(seg)
        pos, rebuilt, last = 0, [], 0
        for m in STRING.finditer(new):
            seg, after = m.group(1), new[m.end():m.end() + 2]
            rebuilt.append(new[last:m.start()])
            rebuilt.append(seg if protected(seg) or after.lstrip().startswith(":") else swap(seg))
            last = m.end()
        rebuilt.append(new[last:])
        new = "".join(rebuilt)
        # 2) JSX text nodes
        new = JSX_TEXT.sub(lambda m: ">" + swap(m.group(1)) + "<", new)
        # 3) comments (python + js), so future readers see the product wording
        if "#" in new or "//" in new or "*" in new:
            idx = min([i for i in (new.find("# "), new.find("// "), new.find("* ")) if i >= 0] or [-1])
            if idx >= 0:
                head, tail = new[:idx], new[idx:]
                if not protected(tail):
                    new = head + swap(tail)
        if new != line:
            changed += 1
        out.append(new)
    if changed:
        path.write_text("\n".join(out))
    return changed


total_files = total_lines = 0
for root in ROOTS:
    for p in sorted(root.rglob("*")):
        if p.is_dir() or p.suffix not in EXTS or any(d in p.parts for d in SKIP_DIRS):
            continue
        n = process(p)
        if n:
            total_files += 1
            total_lines += n
            print(f"{p}: {n} lines", flush=True)
print(f"\n{total_lines} lines changed in {total_files} files")
