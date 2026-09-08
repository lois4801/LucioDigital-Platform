"""Block-level diff so an admin can see exactly what a restore would change."""
import difflib
from typing import Any, Dict, List

SKIP = {"id"}


def _texts(props: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
    out = {}
    for k, v in (props or {}).items():
        if k in SKIP:
            continue
        key = f"{prefix}{k}"
        if isinstance(v, str):
            out[key] = v
        elif isinstance(v, (int, float, bool)):
            out[key] = str(v)
        elif isinstance(v, dict):
            out.update(_texts(v, f"{key}."))
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    out.update(_texts(item, f"{key}[{i}]."))
                elif isinstance(item, (str, int, float, bool)):
                    out[f"{key}[{i}]"] = str(item)
    return out


def _inline(old: str, new: str) -> List[dict]:
    """Word-level inline diff for a single field."""
    parts = []
    sm = difflib.SequenceMatcher(a=old.split(), b=new.split())
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            parts.append({"op": "same", "text": " ".join(sm.a[i1:i2])})
        elif op == "delete":
            parts.append({"op": "removed", "text": " ".join(sm.a[i1:i2])})
        elif op == "insert":
            parts.append({"op": "added", "text": " ".join(sm.b[j1:j2])})
        else:
            parts.append({"op": "removed", "text": " ".join(sm.a[i1:i2])})
            parts.append({"op": "added", "text": " ".join(sm.b[j1:j2])})
    return [p for p in parts if p["text"].strip()]


def _label(block: dict) -> str:
    p = block.get("props") or {}
    for k in ("heading", "title", "brand", "q"):
        if isinstance(p.get(k), str) and p[k].strip():
            return p[k][:60]
    return block.get("type", "section")


def diff_blocks(current: List[dict], target: List[dict]) -> dict:
    """`current` is live, `target` is the version being restored: additions are what the restore brings back."""
    cur_by_id = {b.get("id"): b for b in current if b.get("id")}
    tgt_by_id = {b.get("id"): b for b in target if b.get("id")}
    changes, added, removed, edited = [], 0, 0, 0

    for i, b in enumerate(target):
        bid = b.get("id")
        match = cur_by_id.get(bid) or (current[i] if bid not in cur_by_id and i < len(current) and current[i].get("type") == b.get("type") and current[i].get("id") not in tgt_by_id else None)
        if not match:
            added += 1
            changes.append({"op": "added", "type": b.get("type"), "label": _label(b), "position": i,
                            "fields": [{"field": k, "old": "", "new": v, "parts": [{"op": "added", "text": v}]} for k, v in list(_texts(b.get("props")).items())[:6] if v]})
            continue
        old_t, new_t = _texts(match.get("props")), _texts(b.get("props"))
        fields = []
        for k in sorted(set(old_t) | set(new_t)):
            o, n = old_t.get(k, ""), new_t.get(k, "")
            if o != n:
                fields.append({"field": k, "old": o[:400], "new": n[:400], "parts": _inline(o[:400], n[:400])})
        if fields or (match.get("style") or {}) != (b.get("style") or {}):
            edited += 1
            changes.append({"op": "edited", "type": b.get("type"), "label": _label(b), "position": i,
                            "style_changed": (match.get("style") or {}) != (b.get("style") or {}),
                            "fields": fields[:10]})

    matched_ids = {b.get("id") for b in target if b.get("id") in cur_by_id}
    for i, b in enumerate(current):
        if b.get("id") in matched_ids:
            continue
        if not any(t.get("type") == b.get("type") and t.get("id") == b.get("id") for t in target):
            removed += 1
            changes.append({"op": "removed", "type": b.get("type"), "label": _label(b), "position": i,
                            "fields": [{"field": k, "old": v, "new": "", "parts": [{"op": "removed", "text": v}]} for k, v in list(_texts(b.get("props")).items())[:6] if v]})

    return {"summary": {"added": added, "removed": removed, "edited": edited,
                        "sections_now": len(current), "sections_after": len(target),
                        "identical": not changes},
            "changes": changes[:60]}
