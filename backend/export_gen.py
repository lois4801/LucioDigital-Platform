import json
import re
from typing import List, Dict, Any

FONT_URL = "https://fonts.googleapis.com/css2?family={h}:wght@500;600;700;800&family={b}:wght@400;500;600&display=swap"
ICON_SVG = "<svg width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'><path d='M12 2l3 7h7l-5.5 4.5L18 21l-6-4-6 4 1.5-7.5L2 9h7z'/></svg>"


def esc(s) -> str:
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def css(theme: dict) -> str:
    dark = theme.get("mode") == "dark"
    return f"""
:root{{--p:{theme['primary']};--s:{theme['secondary']};--bg:{'#0B0F17' if dark else theme['bg']};--sf:{'#111827' if dark else theme['surface']};--fg:{'#F8FAFC' if dark else theme['fg']};--mut:{'#94A3B8' if dark else theme['muted']};--bd:{'#1F2937' if dark else theme['border']};--r:{theme['radius']}px}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font-family:'{theme['font_body']}',system-ui,sans-serif;-webkit-font-smoothing:antialiased}}
h1,h2,h3,h4{{font-family:'{theme['font_heading']}',sans-serif;letter-spacing:-0.02em;margin:0;line-height:1.1}}
a{{color:inherit;text-decoration:none}}.wrap{{max-width:1120px;margin:0 auto;padding:0 24px}}
section{{padding:72px 0}}section.sm{{padding:40px 0}}section.lg{{padding:112px 0}}section.muted{{background:var(--sf)}}section.accent{{background:var(--p);color:#fff}}section.dark{{background:#0F172A;color:#fff}}
section.accent .mut,section.dark .mut{{color:rgba(255,255,255,.8)}}.center{{text-align:center}}.mut{{color:var(--mut)}}
.btn{{display:inline-block;background:var(--p);color:#fff;padding:14px 26px;border-radius:999px;font-weight:600;transition:transform .15s}}.btn:hover{{transform:translateY(-1px)}}
.btn2{{display:inline-block;border:1px solid var(--bd);padding:13px 26px;border-radius:999px;font-weight:600;margin-left:10px}}
.grid{{display:grid;gap:24px}}.g2{{grid-template-columns:repeat(2,1fr)}}.g3{{grid-template-columns:repeat(3,1fr)}}.g4{{grid-template-columns:repeat(4,1fr)}}
@media(max-width:860px){{.g2,.g3,.g4{{grid-template-columns:1fr}}}}
.card{{background:var(--sf);border:1px solid var(--bd);border-radius:var(--r);padding:28px}}
nav{{display:flex;align-items:center;justify-content:space-between;padding:18px 0}}nav .links a{{margin:0 14px;color:var(--mut);font-weight:500}}
.brand{{font-family:'{theme['font_heading']}';font-weight:800;font-size:20px}}
.hero h1{{font-size:clamp(40px,6vw,68px);font-weight:800}}.hero p{{font-size:20px;max-width:640px;margin:20px auto 0}}.hero .center p{{margin-left:auto;margin-right:auto}}
.badge{{display:inline-block;background:color-mix(in srgb,var(--s) 15%,transparent);color:var(--s);padding:6px 14px;border-radius:999px;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}}
.ico{{width:44px;height:44px;border-radius:12px;background:color-mix(in srgb,var(--p) 12%,transparent);color:var(--p);display:flex;align-items:center;justify-content:center;margin-bottom:16px}}
.price{{font-size:44px;font-weight:800}}.hl{{border-color:var(--p);box-shadow:0 20px 60px -30px var(--p)}}
ul{{list-style:none;padding:0;margin:0}}li{{padding:6px 0;color:var(--mut)}}
.faq details{{border-bottom:1px solid var(--bd);padding:18px 0}}.faq summary{{font-weight:600;cursor:pointer;font-size:18px}}
.bar{{height:180px;display:flex;align-items:flex-end;gap:10px}}.bar span{{flex:1;background:linear-gradient(180deg,var(--p),var(--s));border-radius:8px 8px 0 0}}
img.g{{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:var(--r)}}
footer{{padding:56px 0;border-top:1px solid var(--bd)}}footer h4{{font-size:14px;margin-bottom:12px}}
.logos{{display:flex;flex-wrap:wrap;gap:36px;justify-content:center;font-weight:700;color:var(--mut);font-size:20px}}
.chat-fab{{position:fixed;right:24px;bottom:24px;background:var(--p);color:#fff;border-radius:999px;padding:14px 20px;font-weight:600;box-shadow:0 12px 40px -10px var(--p)}}
"""


def render_block(b: dict, pages_nav: str, cols: List[dict] = None) -> str:
    t, p, s = b.get("type"), b.get("props", {}), b.get("style", {}) or {}
    cls = " ".join(filter(None, [s.get("bg") if s.get("bg") in ("muted", "accent", "dark") else "", s.get("padding") if s.get("padding") in ("sm", "lg") else "", "center" if s.get("align") == "center" else ""]))
    if t == "collection_list":
        col = next((c for c in (cols or []) if c["slug"] == p.get("collection")), None)
        items = (col or {}).get("items", [])[: int(p.get("limit") or 6)]
        cards = "".join(f"<a class='card' href='{col['slug']}/{it['slug']}.html' style='display:block'>" + (f"<img class='g' src='{esc(it['cover'])}' alt='' style='aspect-ratio:16/9;margin-bottom:14px'>" if it.get("cover") else "") +
                        f"<p class='mut' style='font-size:12px'>{esc(it.get('date'))}</p><h3 style='font-size:20px;margin-top:6px'>{esc(it['title'])}</h3><p class='mut' style='margin-top:8px'>{esc(it.get('excerpt'))}</p></a>" for it in items)
        return f"<section class='{cls}'><div class='wrap'><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2><div class='grid g3' style='margin-top:32px'>{cards or '<p class=mut>No published items yet.</p>'}</div></div></section>"
    if t == "collection_detail":
        return ""
    if t == "navbar":
        links = "".join(f"<a href='{esc(l.get('href','#'))}'>{esc(l.get('label'))}</a>" for l in p.get("links", []))
        return f"<div class='wrap'><nav><span class='brand'>{esc(p.get('brand'))}</span><span class='links'>{links}</span><a class='btn' href='#'>{esc(p.get('cta','Get started'))}</a></nav></div>"
    if t == "hero":
        centered = p.get("variant") == "centered" or s.get("align") == "center"
        split = p.get("variant") == "split" and p.get("image")
        inner = (f"<span class='badge'>{esc(p['badge'])}</span><br><br>" if p.get("badge") else "") + \
                f"<h1>{esc(p.get('title'))}</h1><p class='mut'>{esc(p.get('subtitle'))}</p><div style='margin-top:28px'><a class='btn' href='#'>{esc(p.get('cta','Get started'))}</a>" + \
                (f"<a class='btn2' href='#'>{esc(p['cta2'])}</a>" if p.get("cta2") else "") + "</div>"
        if split:
            return f"<section class='hero lg {cls}'><div class='wrap grid g2' style='align-items:center'><div>{inner}</div><img class='g' src='{esc(p['image'])}' alt=''></div></section>"
        return f"<section class='hero lg {cls} {'center' if centered else ''}'><div class='wrap'>{inner}</div></section>"
    if t == "logos":
        return f"<section class='sm {cls}'><div class='wrap center'><p class='mut' style='font-size:13px;letter-spacing:.1em;text-transform:uppercase'>{esc(p.get('heading'))}</p><div class='logos' style='margin-top:20px'>{''.join(f'<span>{esc(n)}</span>' for n in p.get('names', []))}</div></div></section>"
    if t == "features":
        items = "".join(f"<div class='card'><div class='ico'>{ICON_SVG}</div><h3 style='font-size:20px'>{esc(i.get('title'))}</h3><p class='mut' style='margin-top:8px'>{esc(i.get('desc'))}</p></div>" for i in p.get("items", []))
        return f"<section class='{cls}'><div class='wrap'><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2><p class='mut' style='font-size:18px;margin-top:10px;max-width:600px'>{esc(p.get('subheading'))}</p><div class='grid g3' style='margin-top:40px'>{items}</div></div></section>"
    if t == "gallery":
        imgs = "".join(f"<img class='g' src='{esc(u)}' alt=''>" for u in p.get("images", []))
        return f"<section class='{cls}'><div class='wrap'><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2><div class='grid g3' style='margin-top:32px'>{imgs}</div></div></section>"
    if t == "video":
        return f"<section class='{cls}'><div class='wrap center'><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2><video src='{esc(p.get('url'))}' controls style='width:100%;margin-top:28px;border-radius:var(--r)'></video><p class='mut'>{esc(p.get('caption'))}</p></div></section>"
    if t == "testimonials":
        items = "".join(f"<div class='card'><p style='font-size:18px'>“{esc(i.get('quote'))}”</p><p style='margin-top:18px;font-weight:600'>{esc(i.get('name'))}</p><p class='mut' style='font-size:14px'>{esc(i.get('role'))}</p></div>" for i in p.get("items", []))
        return f"<section class='{cls}'><div class='wrap'><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2><div class='grid g3' style='margin-top:40px'>{items}</div></div></section>"
    if t == "pricing":
        plans = "".join(f"<div class='card {'hl' if pl.get('highlight') else ''}'><p class='mut' style='font-weight:600'>{esc(pl.get('name'))}</p><div class='price'>{esc(pl.get('price'))}<span class='mut' style='font-size:16px;font-weight:500'>/{esc(pl.get('period','mo'))}</span></div><ul>{''.join(f'<li>✓ {esc(f)}</li>' for f in pl.get('features', []))}</ul><a class='btn' style='margin-top:20px' href='#'>Choose {esc(pl.get('name'))}</a></div>" for pl in p.get("plans", []))
        return f"<section class='{cls}'><div class='wrap'><h2 class='center' style='font-size:40px'>{esc(p.get('heading'))}</h2><div class='grid g3' style='margin-top:40px'>{plans}</div></div></section>"
    if t == "faq":
        items = "".join(f"<details><summary>{esc(i.get('q'))}</summary><p class='mut'>{esc(i.get('a'))}</p></details>" for i in p.get("items", []))
        return f"<section class='{cls}'><div class='wrap' style='max-width:760px'><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2><div class='faq' style='margin-top:24px'>{items}</div></div></section>"
    if t == "chart":
        mx = max([x.get("v", 1) for x in p.get("series", [])] + [1])
        bars = "".join(f"<span title='{esc(x.get('m'))}' style='height:{(x.get('v', 0) / mx) * 100}%'></span>" for x in p.get("series", []))
        return f"<section class='{cls}'><div class='wrap'><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2><div class='bar' style='margin-top:32px'>{bars}</div></div></section>"
    if t == "cta":
        return f"<section class='accent center {s.get('padding','') if s.get('padding') in ('sm','lg') else ''}'><div class='wrap'><h2 style='font-size:44px'>{esc(p.get('title'))}</h2><p class='mut' style='font-size:18px;margin-top:12px'>{esc(p.get('subtitle'))}</p><a class='btn' style='background:#fff;color:var(--p);margin-top:28px' href='#'>{esc(p.get('cta','Get started'))}</a></div></section>"
    if t == "contact":
        return f"<section class='{cls}'><div class='wrap grid g2'><div><h2 style='font-size:40px'>{esc(p.get('heading'))}</h2><p class='mut' style='margin-top:10px'>{esc(p.get('subtitle'))}</p><p style='margin-top:20px'>{esc(p.get('email'))}<br>{esc(p.get('phone'))}<br>{esc(p.get('address'))}</p></div><form class='card'><input placeholder='Name' style='width:100%;padding:12px;border:1px solid var(--bd);border-radius:10px;margin-bottom:10px'><input placeholder='Email' style='width:100%;padding:12px;border:1px solid var(--bd);border-radius:10px;margin-bottom:10px'><textarea placeholder='Message' rows='4' style='width:100%;padding:12px;border:1px solid var(--bd);border-radius:10px'></textarea><button class='btn' style='border:0;margin-top:12px;width:100%'>Send</button></form></div></section>"
    if t == "footer":
        cols = "".join(f"<div><h4>{esc(c.get('title'))}</h4><ul>{''.join(f'<li>{esc(l)}</li>' for l in c.get('links', []))}</ul></div>" for c in p.get("columns", []))
        return f"<footer><div class='wrap grid g4'><div><span class='brand'>{esc(p.get('brand'))}</span><p class='mut' style='margin-top:8px'>{esc(p.get('tagline'))}</p></div>{cols}</div></footer>"
    return ""


def _doc(app_doc, theme, title, body, css_path="styles.css"):
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)} · {esc(app_doc['name'])}</title><link rel='stylesheet' href='{FONT_URL.format(h=theme['font_heading'].replace(' ', '+'), b=theme['font_body'].replace(' ', '+'))}'>"
            f"<link rel='stylesheet' href='{css_path}'></head><body>{body}</body></html>")


def render_page(app_doc: dict, theme: dict, page: dict, pages: List[dict], cols: List[dict] = None) -> str:
    body = "".join(render_block(b, "", cols) for b in page.get("blocks", []))
    body = re.sub(r"href='(/[a-z0-9-]*)'", lambda m: f"href='{'index' if m.group(1)=='/' else m.group(1).strip('/')}.html'", body)
    return _doc(app_doc, theme, page["name"], body)


def render_item_page(app_doc: dict, theme: dict, col: dict, item: dict, pages: List[dict]) -> str:
    home = next((pg for pg in pages if pg.get("slug") == "/"), None)
    nav = next((b for b in (home or {}).get("blocks", []) if b.get("type") == "navbar"), None)
    footer = next((b for b in (home or {}).get("blocks", []) if b.get("type") == "footer"), None)
    paras = "".join(f"<p style='font-size:18px;line-height:1.7;margin-top:18px'>{esc(x)}</p>" for x in (item.get("body") or "").split("\n") if x.strip())
    body = (render_block(nav, "") if nav else "") + \
        f"<section class='lg'><div class='wrap' style='max-width:800px'><p class='badge'>{esc(col['name'])}</p><h1 style='font-size:clamp(36px,5vw,56px);margin-top:16px'>{esc(item['title'])}</h1><p class='mut' style='margin-top:12px'>{esc(item.get('date'))}{(' · ' + ', '.join(item.get('tags', []))) if item.get('tags') else ''}</p>" + \
        (f"<img class='g' src='{esc(item['cover'])}' alt='' style='aspect-ratio:16/9;margin-top:28px'>" if item.get("cover") else "") + \
        f"<p class='mut' style='font-size:20px;margin-top:28px'>{esc(item.get('excerpt'))}</p>{paras}<p style='margin-top:40px'><a class='btn2' href='../index.html'>← Back</a></p></div></section>" + \
        (render_block(footer, "") if footer else "")
    body = re.sub(r"href='(/[a-z0-9-]*)'", lambda m: f"href='../{'index' if m.group(1)=='/' else m.group(1).strip('/')}.html'", body)
    return _doc(app_doc, theme, item["title"], body, "../styles.css")


# ---------- Lovable-style starter code from app_spec ----------
PY_TYPES = {"string": "str", "text": "str", "email": "EmailStr", "number": "float", "boolean": "bool", "date": "str", "enum": "str", "ref": "str"}


def _pascal(s: str) -> str:
    return "".join(w.capitalize() for w in re.sub(r"[^a-zA-Z0-9]+", " ", s or "Item").split()) or "Item"


def _snake(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "item").lower()).strip("_") or "item"


def starter_backend(spec: dict) -> str:
    models = spec.get("models") or []
    lines = ["from fastapi import FastAPI, APIRouter, HTTPException", "from fastapi.middleware.cors import CORSMiddleware",
             "from motor.motor_asyncio import AsyncIOMotorClient", "from pydantic import BaseModel, EmailStr", "from typing import Optional, List",
             "import os, uuid", "from dotenv import load_dotenv", "", "load_dotenv()",
             "client = AsyncIOMotorClient(os.environ['MONGO_URL'])", "db = client[os.environ['DB_NAME']]",
             f"app = FastAPI(title={json.dumps(spec.get('name', 'App'))})", "api = APIRouter(prefix='/api')", ""]
    for m in models:
        cls = _pascal(m.get("name"))
        lines.append(f"class {cls}In(BaseModel):")
        fields = m.get("fields") or [{"name": "title", "type": "string", "required": True}]
        for f in fields:
            t = PY_TYPES.get(f.get("type", "string"), "str")
            lines.append(f"    {_snake(f.get('name'))}: {t if f.get('required') else f'Optional[{t}] = None'}")
        lines.append("")
        coll = _snake(m.get("name"))
        lines += [
            f"@api.get('/{coll}')", f"async def list_{coll}():", f"    return await db.{coll}.find({{}}, {{'_id': 0}}).to_list(500)", "",
            f"@api.post('/{coll}')", f"async def create_{coll}(body: {cls}In):",
            f"    doc = {{'id': uuid.uuid4().hex, **body.model_dump()}}", f"    await db.{coll}.insert_one(dict(doc))", "    return doc", "",
            f"@api.get('/{coll}/{{item_id}}')", f"async def get_{coll}(item_id: str):",
            f"    doc = await db.{coll}.find_one({{'id': item_id}}, {{'_id': 0}})", "    if not doc: raise HTTPException(404)", "    return doc", "",
            f"@api.put('/{coll}/{{item_id}}')", f"async def update_{coll}(item_id: str, body: {cls}In):",
            f"    await db.{coll}.update_one({{'id': item_id}}, {{'$set': body.model_dump(exclude_unset=True)}})",
            f"    return await db.{coll}.find_one({{'id': item_id}}, {{'_id': 0}})", "",
            f"@api.delete('/{coll}/{{item_id}}')", f"async def delete_{coll}(item_id: str):",
            f"    await db.{coll}.delete_one({{'id': item_id}})", "    return {'ok': True}", "",
        ]
    lines += ["app.include_router(api)", "app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])", ""]
    return "\n".join(lines)


def starter_screen(screen: dict, spec: dict) -> str:
    name = _pascal(screen.get("name"))
    comps = screen.get("components") or []
    body = []
    for c in comps:
        t, label = c.get("type", "cards"), c.get("label") or c.get("type", "").title()
        model = _snake(c.get("model") or (spec.get("models") or [{}])[0].get("name", "items"))
        if t in ("table", "list", "cards", "kanban"):
            body.append(f"""      <section className="card">
        <h2>{label}</h2>
        <DataList collection="{model}" fields={{{json.dumps(c.get('fields') or [])}}} />
      </section>""")
        elif t == "form":
            body.append(f"""      <section className="card">
        <h2>{label}</h2>
        <DataForm collection="{model}" fields={{{json.dumps(c.get('fields') or [])}}} />
      </section>""")
        elif t == "stats":
            body.append(f"""      <section className="stats">{''.join(f'<div className="stat"><span>{esc(f)}</span><strong>—</strong></div>' for f in (c.get('fields') or ['Total', 'Active', 'Revenue']))}</section>""")
        else:
            body.append(f"""      <section className="card"><h2>{label}</h2><p className="muted">{esc(screen.get('description'))}</p></section>""")
    return f"""import {{ DataList, DataForm }} from "../components/Data";

export default function {name}() {{
  return (
    <main className="page">
      <h1>{esc(screen.get('name'))}</h1>
      <p className="muted">{esc(screen.get('description'))}</p>
{chr(10).join(body)}
    </main>
  );
}}
"""


def starter_frontend_files(spec: dict) -> Dict[str, str]:
    screens = spec.get("screens") or []
    files = {}
    imports, routes, nav = [], [], []
    for s in screens:
        n = _pascal(s.get("name"))
        route = s.get("route") or f"/{_snake(s.get('name'))}"
        files[f"frontend/src/pages/{n}.jsx"] = starter_screen(s, spec)
        imports.append(f'import {n} from "./pages/{n}";')
        routes.append(f'        <Route path="{route}" element={{<{n} />}} />')
        if s.get("nav", True):
            nav.append(f'<Link to="{route}">{esc(s.get("name"))}</Link>')
    files["frontend/src/App.jsx"] = f"""import {{ BrowserRouter, Routes, Route, Link }} from "react-router-dom";
{chr(10).join(imports)}
import "./styles.css";

export default function App() {{
  return (
    <BrowserRouter>
      <nav className="nav"><strong>{esc(spec.get('name', 'App'))}</strong>{''.join(nav)}</nav>
      <Routes>
{chr(10).join(routes)}
      </Routes>
    </BrowserRouter>
  );
}}
"""
    files["frontend/src/components/Data.jsx"] = """import { useEffect, useState } from "react";
const API = process.env.REACT_APP_BACKEND_URL + "/api";

export function DataList({ collection, fields }) {
  const [rows, setRows] = useState([]);
  useEffect(() => { fetch(`${API}/${collection}`).then(r => r.json()).then(setRows).catch(() => {}); }, [collection]);
  return (
    <table className="table"><thead><tr>{fields.map(f => <th key={f}>{f}</th>)}</tr></thead>
      <tbody>{rows.map(r => <tr key={r.id}>{fields.map(f => <td key={f}>{String(r[f.toLowerCase().replace(/\\s+/g, "_")] ?? "")}</td>)}</tr>)}</tbody></table>
  );
}

export function DataForm({ collection, fields }) {
  const [form, setForm] = useState({});
  async function submit(e) {
    e.preventDefault();
    await fetch(`${API}/${collection}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
    setForm({});
  }
  return (
    <form onSubmit={submit} className="form">
      {fields.map(f => <input key={f} placeholder={f} value={form[f.toLowerCase().replace(/\\s+/g, "_")] || ""} onChange={e => setForm({ ...form, [f.toLowerCase().replace(/\\s+/g, "_")]: e.target.value })} />)}
      <button>Save</button>
    </form>
  );
}
"""
    files["frontend/src/styles.css"] = ":root{--p:#F97316;--s:#14B8A6;--bd:#E2E8F0;--mut:#64748B}body{margin:0;font-family:Manrope,system-ui,sans-serif;color:#0F172A}.nav{display:flex;gap:18px;padding:16px 24px;border-bottom:1px solid var(--bd)}.nav a{color:var(--mut);text-decoration:none}.page{max-width:1080px;margin:0 auto;padding:40px 24px}.muted{color:var(--mut)}.card{border:1px solid var(--bd);border-radius:16px;padding:24px;margin-top:20px}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:20px}.stat{border:1px solid var(--bd);border-radius:16px;padding:20px}.stat strong{display:block;font-size:28px}.table{width:100%;border-collapse:collapse}.table th,.table td{text-align:left;padding:10px;border-bottom:1px solid var(--bd)}.form{display:grid;gap:10px}.form input{padding:12px;border:1px solid var(--bd);border-radius:10px}.form button{background:var(--p);color:#fff;border:0;padding:12px;border-radius:999px;font-weight:600}"
    files["frontend/package.json"] = json.dumps({"name": _snake(spec.get("name", "app")), "private": True, "dependencies": {"react": "^19.0.0", "react-dom": "^19.0.0", "react-router-dom": "^7.0.0", "react-scripts": "5.0.1"}, "scripts": {"start": "react-scripts start", "build": "react-scripts build"}}, indent=2)
    files["frontend/src/index.js"] = 'import React from "react";\nimport ReactDOM from "react-dom/client";\nimport App from "./App";\nReactDOM.createRoot(document.getElementById("root")).render(<App />);\n'
    files["frontend/public/index.html"] = "<!doctype html><html><head><meta charset='utf-8'><title>App</title></head><body><div id='root'></div></body></html>"
    files["frontend/.env.example"] = "REACT_APP_BACKEND_URL=http://localhost:8001\n"
    return files


SQL_TYPES = {"string": "text", "text": "text", "email": "text", "number": "numeric", "boolean": "boolean", "date": "timestamptz", "enum": "text", "ref": "uuid"}


def supabase_schema(spec: dict) -> str:
    out = ["-- Postgres / Supabase schema generated by OmniStack AI", "create extension if not exists \"pgcrypto\";", ""]
    for m in spec.get("models") or []:
        t = _snake(m.get("name"))
        cols = ["  id uuid primary key default gen_random_uuid()", "  created_at timestamptz not null default now()"]
        for f in m.get("fields") or []:
            cols.append(f"  {_snake(f.get('name'))} {SQL_TYPES.get(f.get('type', 'string'), 'text')}{' not null' if f.get('required') else ''}")
        out.append(f"create table if not exists {t} (\n" + ",\n".join(cols) + "\n);")
        out.append(f"alter table {t} enable row level security;")
        out.append(f"create policy \"{t}_owner\" on {t} for all using (auth.uid() is not null);\n")
    return "\n".join(out)


def starter_app_files(spec: dict) -> Dict[str, str]:
    files = starter_frontend_files(spec)
    files["backend/server.py"] = starter_backend(spec)
    files["backend/schema.sql"] = supabase_schema(spec)
    files["backend/requirements.txt"] = "fastapi\nuvicorn\nmotor\npydantic[email]\npython-dotenv\n"
    files["backend/.env.example"] = "MONGO_URL=mongodb://localhost:27017\nDB_NAME=app\n"
    files["blueprint.json"] = json.dumps(spec, indent=2)
    files["README.md"] = (f"# {spec.get('name', 'App')}\n\n{spec.get('tagline', '')}\n\n## Run\n- backend: `cd backend && pip install -r requirements.txt && uvicorn server:app --reload --port 8001`\n"
                          f"- frontend: `cd frontend && npm i && npm start`\n\n## Screens\n" + "\n".join(f"- {s.get('name')} `{s.get('route')}` — {s.get('description', '')}" for s in spec.get("screens", []))
                          + "\n\n## API\n" + "\n".join(f"- {a.get('method')} `{a.get('path')}` — {a.get('description', '')}" for a in spec.get("api", [])) + "\n")
    return files
