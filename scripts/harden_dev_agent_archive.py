from pathlib import Path

p = Path('runner/server.py')
text = p.read_text(encoding='utf-8')
old = '''            if any(part.lower() in DENIED_PARTS for part in rel.parts):\n                continue\n            if rel.name == ".lucio-preview.log":\n'''
new = '''            lowered_parts = {part.lower() for part in rel.parts}\n            if lowered_parts & DENIED_PARTS or any(part.startswith(".env") for part in lowered_parts):\n                continue\n            if rel.name == ".lucio-preview.log":\n'''
if text.count(old) != 1:
    raise SystemExit(f'Expected one archive filter block, found {text.count(old)}')
p.write_text(text.replace(old, new, 1), encoding='utf-8')
print('Archive secret filtering hardened')
