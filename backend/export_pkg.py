"""Three-way export system for every tenant.

  website   — static multi-page site, every asset + font embedded locally, a tiny form server
              and WordPress/Webflow import files
  fullstack — React frontend + FastAPI backend + seeded database + auth + admin dashboard
  plugin    — structured JSON + assets bundle that restores as a new tenant on this platform

Exports run as background jobs with progress; the finished .zip lives in object storage and is
streamed back through an authenticated download route.
"""
import asyncio
import csv
import io
import json
import logging
import os
import re
import uuid
import zipfile
from html import unescape as html_unescape
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from export_gen import FONT_URL, css, render_item_page, render_page
from storage import APP_NAME, get_object, put_object

logger = logging.getLogger("agency.export")

KINDS = {"website": "Website", "fullstack": "Full-Stack App", "plugin": "Plugin Package"}
FILE_RE = re.compile(r"/api/public/files/([A-Za-z0-9._/\-]+)")
EXT_RE = re.compile(r"https?://[^\s'\"<>()]+?\.(?:png|jpe?g|webp|gif|svg|avif|mp4|webm|mov|woff2?|ttf)(?:\?[^\s'\"<>()]*)?", re.I)
ATTR_RE = re.compile(r"(?:src|poster|data-src)=['\"](https?://[^'\"]+)['\"]", re.I)
CSSURL_RE = re.compile(r"url\((['\"]?)(https?://[^)'\"]+)\1\)", re.I)
JSONURL_RE = re.compile(r"\"(https?://[^\"\\\s]+)\"")
MEDIA_HOSTS = ("unsplash.com", "pexels.com", "pixabay.com", "fal.media", "fal.ai", "cloudinary.com",
               "imgix.net", "googleusercontent.com", "cloudfront.net", "cdn.", "media.", "images.")
SKIP_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com", "youtube.com", "youtu.be", "vimeo.com",
              "player.vimeo.com", "google-analytics.com", "gtag", "schema.org", "w3.org")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
CT = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif",
      "svg": "image/svg+xml", "avif": "image/avif", "mp4": "video/mp4", "webm": "video/webm", "mov": "video/quicktime",
      "woff2": "font/woff2", "woff": "font/woff", "ttf": "font/ttf"}
EXT_FOR_CT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif",
              "image/svg+xml": "svg", "image/avif": "avif", "video/mp4": "mp4", "video/webm": "webm",
              "video/quicktime": "mov"}


def _iso():
    return datetime.now(timezone.utc).isoformat()


def _uid(p):
    return f"{p}_{uuid.uuid4().hex[:12]}"


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "site").lower()).strip("-") or "site"


def _body_only(html: str) -> str:
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S)
    body = m.group(1) if m else html
    return re.sub(r"<script\b.*?</script>", "", body, flags=re.S)


class Bundler:
    """Downloads every referenced image, video and font once and rewrites URLs to local paths."""

    def __init__(self, budget_bytes: int):
        self.files: dict = {}          # "assets/xxx.png" -> bytes
        self.map: dict = {}            # original url -> "assets/xxx.png"
        self.skipped: list = []
        self.budget = budget_bytes

    def add(self, data: bytes, ext: str, sub: str = "") -> Optional[str]:
        if len(data) > self.budget:
            return None
        self.budget -= len(data)
        rel = f"assets/{sub + '/' if sub else ''}{uuid.uuid4().hex[:12]}.{ext.lower()}"
        self.files[rel] = data
        return rel

    async def _remote(self, client: httpx.AsyncClient, url: str):
        for attempt in range(3):
            try:
                r = await client.get(html_unescape(url), headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
                r.raise_for_status()
                return r.content, (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            except Exception:
                if attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
        return None, ""

    async def resolve(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        if url in self.map:
            return self.map[url]
        data, ext = None, "bin"
        m = FILE_RE.search(url)
        if m and url.startswith("/api/public/files/"):
            key = m.group(1)
            ext = key.rsplit(".", 1)[-1].lower() if "." in key.rsplit("/", 1)[-1] else "png"
            try:
                data, _ct = await asyncio.to_thread(get_object, key)
            except Exception:
                data = None
        elif url.startswith("http"):
            clean = html_unescape(url).split("?")[0]
            tail = clean.rsplit("/", 1)[-1]
            data, ctype = await self._remote(client, url)
            ext = tail.rsplit(".", 1)[-1].lower() if "." in tail else EXT_FOR_CT.get(ctype, "")
            if not ext or ext not in CT:
                ext = EXT_FOR_CT.get(ctype, "")
        if not data or len(data) < 64 or not ext:
            self.skipped.append(url[:160])
            return None
        rel = self.add(data, ext if ext in CT else "png")
        if not rel:
            self.skipped.append(f"{url[:140]} (storage budget reached)")
            return None
        self.map[url] = rel
        return rel

    def candidates(self, text: str) -> set:
        out = set(ATTR_RE.findall(text))
        out |= {m[1] for m in CSSURL_RE.findall(text)}
        out |= set(EXT_RE.findall(text))
        for u in JSONURL_RE.findall(text):
            low = html_unescape(u).lower()
            if any(h in low for h in MEDIA_HOSTS) or EXT_RE.fullmatch(u):
                out.add(u)
        return {u for u in out if not any(h in html_unescape(u).lower() for h in SKIP_HOSTS)}

    async def localise(self, client: httpx.AsyncClient, text: str, prefix: str = "") -> str:
        if not isinstance(text, str):
            return text
        out = text
        for key in set(FILE_RE.findall(text)):
            rel = await self.resolve(client, f"/api/public/files/{key}")
            if rel:
                out = out.replace(f"/api/public/files/{key}", f"{prefix}{rel}")
        for url in sorted(self.candidates(out), key=len, reverse=True):
            rel = await self.resolve(client, url)
            if rel:
                out = out.replace(url, f"{prefix}{rel}")
                plain = html_unescape(url)
                if plain != url:
                    out = out.replace(plain, f"{prefix}{rel}")
        return out


async def bundle_fonts(bundler: Bundler, client: httpx.AsyncClient, heading: str, body: str, prefix: str = "") -> str:
    """Google Fonts CSS + woff2 files copied into the package so nothing hotlinks."""
    url = FONT_URL.format(h=(heading or "Sora").replace(" ", "+"), b=(body or "Inter").replace(" ", "+"))
    try:
        r = await client.get(url, headers={"User-Agent": UA}, timeout=25, follow_redirects=True)
        r.raise_for_status()
        sheet = r.text
    except Exception:
        logger.warning("font sheet download failed")
        return f"/* Google Fonts unavailable at export time; falls back to system fonts. */\n"
    for font_url in set(re.findall(r"url\((https://[^)]+)\)", sheet)):
        data, _ct = await bundler._remote(client, font_url)
        if not data:
            continue
        ext = "woff2" if ".woff2" in font_url else ("woff" if ".woff" in font_url else "ttf")
        rel = bundler.add(data, ext, "fonts")
        if rel:
            sheet = sheet.replace(font_url, f"{prefix}{rel}")
    return sheet


FORM_JS = """<script>
(function(){var EP=(window.OMNI_FORM_ENDPOINT||'').replace(/\\/$/,'');
document.querySelectorAll('form').forEach(function(f){f.addEventListener('submit',async function(e){
e.preventDefault();var fd={};new FormData(f).forEach(function(v,k){fd[k]=v});
f.querySelectorAll('input,textarea,select').forEach(function(el,i){var k=el.name||el.placeholder||('field_'+i);if(!fd[k])fd[k]=el.value});
var btn=f.querySelector('button');var old=btn?btn.textContent:'';if(btn){btn.disabled=true;btn.textContent='Sending…'}
try{if(!EP)throw new Error('no endpoint');
var r=await fetch(EP+'/api/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({form:f.dataset.form||'Contact',fields:fd})});
if(!r.ok)throw new Error('bad status');f.innerHTML='<p style="padding:18px 0">Thanks — we\\'ll be in touch shortly.</p>'}
catch(err){if(btn){btn.disabled=false;btn.textContent=old}alert('Could not send. Start the included form server (see README) or point window.OMNI_FORM_ENDPOINT at your own endpoint.')}
})})})();
</script>"""

FORM_SERVER = '''"""Tiny form-submission server for the exported static site.

    pip install fastapi uvicorn
    uvicorn server:app --port 8002

Submissions land in submissions.db (SQLite). Open http://localhost:8002/admin?token=YOUR_TOKEN
(ADMIN_TOKEN env var, default "changeme") to read them or download a CSV.
"""
import csv, io, json, os, sqlite3
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

DB = os.environ.get("SUBMISSIONS_DB", "submissions.db")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "changeme")
app = FastAPI(title="Form server")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def conn():
    c = sqlite3.connect(DB)
    c.execute("create table if not exists submissions (id integer primary key autoincrement, form text, fields text, created_at text)")
    return c


@app.post("/api/submit")
async def submit(request: Request):
    body = await request.json()
    c = conn()
    c.execute("insert into submissions (form, fields, created_at) values (?,?,?)",
              (str(body.get("form") or "Contact")[:120], json.dumps(body.get("fields") or {})[:8000],
               datetime.now(timezone.utc).isoformat()))
    c.commit(); c.close()
    return {"ok": True}


def _rows():
    c = conn()
    rows = c.execute("select id, form, fields, created_at from submissions order by id desc").fetchall()
    c.close()
    return rows


@app.get("/admin", response_class=HTMLResponse)
async def admin(token: str = ""):
    if token != ADMIN_TOKEN:
        raise HTTPException(401, "Add ?token=YOUR_ADMIN_TOKEN")
    body = "".join(
        f"<tr><td>{r[0]}</td><td>{r[1]}</td><td><pre>{json.dumps(json.loads(r[2]), indent=1)}</pre></td><td>{r[3]}</td></tr>"
        for r in _rows())
    return (f"<!doctype html><meta charset=utf-8><title>Submissions</title>"
            "<style>body{font-family:system-ui;margin:32px}table{border-collapse:collapse;width:100%}"
            "td,th{border-bottom:1px solid #ddd;padding:8px;text-align:left;vertical-align:top;font-size:13px}"
            "pre{margin:0;white-space:pre-wrap}</style>"
            f"<h1>Submissions</h1><p><a href='/admin/export.csv?token={token}'>Download CSV</a></p>"
            f"<table><tr><th>#</th><th>Form</th><th>Fields</th><th>When</th></tr>{body}</table>")


@app.get("/admin/export.csv")
async def export_csv(token: str = ""):
    if token != ADMIN_TOKEN:
        raise HTTPException(401, "Add ?token=YOUR_ADMIN_TOKEN")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "form", "fields", "created_at"])
    for r in _rows():
        w.writerow(r)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=submissions.csv"})
'''


def _wxr(app_doc: dict, pages: list) -> str:
    """WordPress WXR file — import via Tools → Import → WordPress."""
    items = []
    for i, pg in enumerate(pages, 1):
        slug = (pg.get("slug") or "/").strip("/") or "home"
        items.append(
            f"<item><title>{_x(pg.get('name'))}</title><link>/{slug}</link>"
            f"<dc:creator><![CDATA[admin]]></dc:creator>"
            f"<content:encoded><![CDATA[{pg.get('html') or ''}]]></content:encoded>"
            f"<excerpt:encoded><![CDATA[{_x((pg.get('seo') or {}).get('description') or '')}]]></excerpt:encoded>"
            f"<wp:post_id>{100 + i}</wp:post_id><wp:post_name>{_x(slug)}</wp:post_name>"
            "<wp:status>publish</wp:status><wp:post_type>page</wp:post_type></item>")
    return ("<?xml version='1.0' encoding='UTF-8'?>\n"
            "<rss version='2.0' xmlns:content='http://purl.org/rss/1.0/modules/content/' "
            "xmlns:dc='http://purl.org/dc/elements/1.1/' xmlns:wp='http://wordpress.org/export/1.2/' "
            "xmlns:excerpt='http://wordpress.org/export/1.2/excerpt/'>\n<channel>"
            f"<title>{_x(app_doc.get('name'))}</title><wp:wxr_version>1.2</wp:wxr_version>"
            + "".join(items) + "</channel></rss>")


def _x(s) -> str:
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _csv(rows: list, header: list) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def register(api, db, get_current_user, get_user_app, log_activity, send_email=None, cms_public=None,
             default_theme=None, default_blocks=None):
    THEME = default_theme or {}

    async def notify(to, subject, body):
        if send_email and to:
            try:
                await send_email(to, subject, body)
            except Exception:
                logger.exception("export email failed")

    async def _quota_bytes(app_doc: dict) -> int:
        mb = int(app_doc.get("storage_quota_mb") or os.environ.get("TENANT_STORAGE_QUOTA_MB", "500"))
        return mb * 1024 * 1024

    async def _collections(app_id: str) -> list:
        if cms_public:
            try:
                return await cms_public(app_id)
            except Exception:
                logger.exception("collection fetch failed")
        return []

    # ---------------- package builders ----------------

    async def build_website(app_doc, pages, cols, bundler, client, say):
        theme = {**THEME, **(app_doc.get("theme") or {})}
        files: dict = {}
        await say("pages", "Rendering every page", 25)
        rendered = []
        for pg in pages:
            html = render_page(app_doc, theme, pg, pages, cols)
            rendered.append((pg, html))
        await say("assets", "Downloading images, video and media", 45)
        for pg, html in rendered:
            name = "index.html" if pg.get("slug") == "/" else f"{(pg.get('slug') or '').strip('/') or 'page'}.html"
            out = await bundler.localise(client, html)
            out = out.replace(FONT_URL.format(h=theme.get("font_heading", "Sora").replace(" ", "+"),
                                              b=theme.get("font_body", "Inter").replace(" ", "+")), "fonts.css")
            out = out.replace("</body>", f"{FORM_JS}</body>")
            out = out.replace("<head>", "<head><script src='config.js'></script>")
            files[f"site/{name}"] = out
            pg["html"] = _body_only(out)
        for c in cols:
            for it in c.get("items", []):
                html = await bundler.localise(client, render_item_page(app_doc, theme, c, it, pages), "../")
                html = re.sub(r"href='https://fonts\.googleapis[^']*'", "href='../fonts.css'", html)
                files[f"site/{c['slug']}/{it['slug']}.html"] = html.replace("</body>", f"{FORM_JS}</body>")
        await say("fonts", "Embedding fonts", 62)
        files["site/fonts.css"] = await bundle_fonts(bundler, client, theme.get("font_heading"), theme.get("font_body"))
        files["site/styles.css"] = await bundler.localise(client, css(theme))
        files["site/config.js"] = ("// Point this at the included form server (server/) or your own endpoint.\n"
                                   "window.OMNI_FORM_ENDPOINT = 'http://localhost:8002';\n")
        files["site/robots.txt"] = "User-agent: *\nAllow: /\n"
        files["site/sitemap.xml"] = ("<?xml version='1.0' encoding='UTF-8'?><urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
                                     + "".join(f"<url><loc>/{(p.get('slug') or '/').strip('/')}</loc></url>" for p in pages)
                                     + "</urlset>")
        files["site/vercel.json"] = json.dumps({"cleanUrls": True}, indent=2)
        files["site/_redirects"] = "/*    /index.html   200\n"
        files["server/server.py"] = FORM_SERVER
        files["server/requirements.txt"] = "fastapi\nuvicorn\n"
        files["server/.env.example"] = "ADMIN_TOKEN=change-this-token\nSUBMISSIONS_DB=submissions.db\n"
        await say("cms", "Writing WordPress and Webflow import files", 74)
        files["cms/wordpress-import.xml"] = _wxr(app_doc, pages)
        files["cms/webflow-pages.csv"] = _csv(
            [[(p.get("slug") or "/"), p.get("name"), (p.get("seo") or {}).get("title") or p.get("name"),
              (p.get("seo") or {}).get("description") or "", p.get("html") or ""] for p in pages],
            ["Slug", "Name", "SEO Title", "Meta Description", "Body HTML"])
        for c in cols:
            files[f"cms/collections/{c['slug']}.csv"] = _csv(
                [[it.get("slug"), it.get("title"), it.get("excerpt"), it.get("body"), it.get("cover"), it.get("date")]
                 for it in c.get("items", [])],
                ["Slug", "Name", "Excerpt", "Body", "Cover Image", "Date"])
        files["content/pages.json"] = json.dumps([{k: p.get(k) for k in ("name", "slug", "seo", "blocks")} for p in pages], indent=2)
        files["README.md"] = _website_readme(app_doc, pages, cols, bundler)
        return files

    async def build_fullstack(app_doc, pages, cols, bundler, client, say):
        theme = {**THEME, **(app_doc.get("theme") or {})}
        app_id = app_doc["app_id"]
        files: dict = {}
        await say("pages", "Rendering pages for the app shell", 22)
        page_data = []
        for pg in pages:
            html = await bundler.localise(client, render_page(app_doc, theme, pg, pages, cols), "/")
            body = _body_only(html)
            body = re.sub(r"href='([a-z0-9\-]+)\.html'", lambda m: f"href='/{'' if m.group(1) == 'index' else m.group(1)}'", body)
            page_data.append({"page_id": pg.get("page_id"), "name": pg.get("name"), "slug": pg.get("slug"),
                              "protected": bool(pg.get("protected")), "paid": bool(pg.get("paid")),
                              "seo": pg.get("seo") or {}, "blocks": pg.get("blocks") or [], "html": body})
        await say("data", "Exporting your live data", 45)
        subs = await db.submissions.find({"app_id": app_id}, {"_id": 0}).to_list(2000)
        members = await db.site_users.find({"app_id": app_id}, {"_id": 0}).to_list(2000)
        grants = await db.member_access.find({"app_id": app_id}, {"_id": 0}).to_list(2000)
        workflows = await db.workflows.find({"app_id": app_id}, {"_id": 0}).to_list(200)
        site_settings = await db.site_settings.find_one({"app_id": app_id}, {"_id": 0}) or {}
        data = {
            "site": {"name": app_doc.get("name"), "industry": app_doc.get("industry"),
                     "description": app_doc.get("description"), "logo": None,
                     "webapp": app_doc.get("webapp") or {}, "theme": theme},
            "pages": page_data,
            "collections": [{"slug": c["slug"], "name": c["name"], "items": c.get("items", [])} for c in cols],
            "submissions": subs, "members": members, "member_access": grants,
            "workflows": workflows, "settings": site_settings,
        }
        if app_doc.get("logo"):
            rel = await bundler.resolve(client, app_doc["logo"])
            data["site"]["logo"] = f"/{rel}" if rel else None
        raw = await bundler.localise(client, json.dumps(data), "/")
        files["backend/data/data.json"] = raw
        await say("fonts", "Embedding fonts and media", 62)
        files["frontend/public/fonts.css"] = await bundle_fonts(bundler, client, theme.get("font_heading"), theme.get("font_body"), "/")
        files["frontend/public/styles.css"] = await bundler.localise(client, css(theme), "/")
        await say("code", "Writing the frontend, backend and admin dashboard", 76)
        files.update(_fullstack_code(app_doc, theme, page_data, cols))
        files["README.md"] = _fullstack_readme(app_doc, page_data, cols, data, bundler)
        return files

    async def build_plugin(app_doc, pages, cols, bundler, client, say):
        app_id = app_doc["app_id"]
        await say("data", "Collecting pages, CMS, forms and settings", 30)
        doc = {k: v for k, v in app_doc.items() if k not in ("_id", "owner_id", "app_id", "preview_token", "github", "metrics")}
        manifest = {
            "format": "omnistack.plugin", "version": 1, "exported_at": _iso(),
            "source_app_id": app_id, "platform": "Lois-Tech",
            "app": doc,
            "theme": app_doc.get("theme") or {},
            "pages": pages,
            "cms_collections": await db.cms_collections.find({"app_id": app_id}, {"_id": 0}).to_list(200),
            "cms_items": await db.cms_items.find({"app_id": app_id}, {"_id": 0}).to_list(5000),
            "workflows": await db.workflows.find({"app_id": app_id}, {"_id": 0}).to_list(200),
            "item_locks": await db.item_locks.find({"app_id": app_id}, {"_id": 0}).to_list(2000),
            "site_settings": await db.site_settings.find_one({"app_id": app_id}, {"_id": 0}) or {},
            "submissions": await db.submissions.find({"app_id": app_id}, {"_id": 0}).to_list(2000),
            "site_users": await db.site_users.find({"app_id": app_id}, {"_id": 0}).to_list(2000),
            "member_access": await db.member_access.find({"app_id": app_id}, {"_id": 0}).to_list(2000),
            "data_destinations": await db.data_destinations.find({"app_id": app_id}, {"_id": 0}).to_list(50),
        }
        manifest["forms"] = [{"page": p.get("slug"), "block_id": b.get("id"), "props": b.get("props") or {}}
                             for p in pages for b in (p.get("blocks") or []) if b.get("type") in ("contact", "form")]
        await say("assets", "Bundling every image, video and file", 60)
        raw = await bundler.localise(client, json.dumps(manifest, default=str), "")
        files = {"plugin.json": raw,
                 "assets/README.txt": "Every image, video and font referenced by plugin.json lives here.\n"}
        counts = {"pages": len(pages), "cms_items": len(manifest["cms_items"]), "assets": len(bundler.files),
                  "submissions": len(manifest["submissions"]), "members": len(manifest["site_users"])}
        files["manifest-summary.json"] = json.dumps(counts, indent=2)
        files["README.md"] = (
            f"# {app_doc.get('name')} — Lois-Tech plugin package\n\n"
            "Plug-and-play backup / clone bundle for this platform.\n\n"
            "## Restore it\n"
            "1. Open Lois-Tech → **Dashboard**\n"
            "2. Either open any tenant → **Site Mode → Import → Import a .zip** and drop this file in, "
            "or use **Import plugin package** on the dashboard to restore it as a brand-new tenant.\n"
            "3. The importer detects `plugin.json` and restores pages, blocks, design, CMS, forms, workflows, "
            "settings, bookings and members with every asset re-uploaded — no rebuild needed.\n\n"
            "## What's inside\n"
            f"- `plugin.json` — {counts['pages']} page(s), {counts['cms_items']} CMS item(s), "
            f"{counts['submissions']} submission(s), {counts['members']} member account(s), theme, locks and settings\n"
            f"- `assets/` — {counts['assets']} embedded file(s)\n")
        return files

    BUILDERS = {"website": build_website, "fullstack": build_fullstack, "plugin": build_plugin}

    # ---------------- job runner ----------------

    async def _run(job_id: str, app_doc: dict, kind: str, user: dict):
        app_id = app_doc["app_id"]

        async def say(stage, detail, pct):
            await db.export_jobs.update_one({"job_id": job_id}, {"$set": {
                "stage": stage, "detail": detail, "pct": int(pct), "stage_at": _iso()}})
        try:
            await say("collecting", "Collecting pages and content", 10)
            pages = await db.pages.find({"app_id": app_id}, {"_id": 0}).sort("order", 1).to_list(200)
            pages.sort(key=lambda p: (p.get("slug") != "/", p.get("order", 0)))
            cols = await _collections(app_id)
            bundler = Bundler(await _quota_bytes(app_doc))
            async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
                files = await BUILDERS[kind](app_doc, pages, cols, bundler, client, say)
            await say("zipping", "Compressing the package", 88)
            root = f"{_slugify(app_doc.get('name'))}-{kind}"
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for path, content in files.items():
                    z.writestr(f"{root}/{path}", content)
                asset_root = "frontend/public/" if kind == "fullstack" else ("site/" if kind == "website" else "")
                for rel, data in bundler.files.items():
                    z.writestr(f"{root}/{asset_root}{rel}", data)
            raw = buf.getvalue()
            path = f"{APP_NAME}/exports/{app_id}/{job_id}.zip"
            await asyncio.to_thread(put_object, path, raw, "application/zip")
            filename = f"{root}.zip"
            await db.export_jobs.update_one({"job_id": job_id}, {"$set": {
                "status": "done", "stage": "done", "detail": "Your download is ready", "pct": 100,
                "storage_path": path, "filename": filename, "size": len(raw),
                "file_count": len(files) + len(bundler.files), "skipped": bundler.skipped[:100],
                "finished_at": _iso()}})
            await log_activity(app_id, user["user_id"], f"export.{kind}",
                              f"{KINDS[kind]} export ready ({len(raw) // 1024} KB, {len(files) + len(bundler.files)} files)")
            await notify(user.get("email"), f"[{app_doc.get('name')}] {KINDS[kind]} export is ready",
                         f"Your {KINDS[kind]} export for {app_doc.get('name')} finished.\n\n"
                         f"File: {filename}\nSize: {len(raw) // 1024} KB\n"
                         f"Files bundled: {len(files) + len(bundler.files)}\n\n"
                         "Open the tenant's Handoff & Export tab to download it.")
        except Exception as e:
            logger.exception("export failed")
            await db.export_jobs.update_one({"job_id": job_id}, {"$set": {
                "status": "error", "error": str(e)[:220], "detail": "Export failed", "finished_at": _iso()}})

    @api.post("/apps/{app_id}/export/start")
    async def start_export(app_id: str, kind: str = "website", user: dict = Depends(get_current_user)):
        app_doc = await get_user_app(app_id, user)
        if kind not in BUILDERS:
            raise HTTPException(400, "kind must be website, fullstack or plugin")
        job_id = _uid("exp")
        job = {"job_id": job_id, "app_id": app_id, "kind": kind, "status": "running", "stage": "queued",
               "detail": "Starting the export", "pct": 3, "by": user["user_id"], "created_at": _iso()}
        await db.export_jobs.insert_one(dict(job))
        asyncio.create_task(_run(job_id, app_doc, kind, user))
        job.pop("_id", None)
        return job

    @api.get("/apps/{app_id}/export/jobs")
    async def list_jobs(app_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        return {"jobs": await db.export_jobs.find({"app_id": app_id}, {"_id": 0}).sort("created_at", -1).to_list(12)}

    @api.get("/apps/{app_id}/export/jobs/{job_id}")
    async def get_job(app_id: str, job_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        job = await db.export_jobs.find_one({"app_id": app_id, "job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(404, "Export job not found")
        return job

    @api.get("/apps/{app_id}/export/jobs/{job_id}/download")
    async def download_job(app_id: str, job_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        job = await db.export_jobs.find_one({"app_id": app_id, "job_id": job_id}, {"_id": 0})
        if not job or job.get("status") != "done":
            raise HTTPException(404, "That export is not ready")
        try:
            data, _ct = await asyncio.to_thread(get_object, job["storage_path"])
        except Exception as e:
            raise HTTPException(502, f"Could not read the package: {str(e)[:120]}")
        return StreamingResponse(iter([data]), media_type="application/zip",
                                 headers={"Content-Disposition": f"attachment; filename={job['filename']}"})

    # ---------------- plugin import (restore as a new tenant) ----------------

    async def restore_plugin(manifest: dict, zf: zipfile.ZipFile, app_id: str, user_id: str, name: Optional[str] = None):
        """Rewrites every bundled asset into this platform's storage, then restores all collections."""
        raw = json.dumps(manifest)
        for info in zf.infolist():
            if info.is_dir() or not info.filename.split("/", 1)[-1].startswith("assets/"):
                continue
            rel = info.filename.split("/", 1)[-1] if "/" in info.filename and not info.filename.startswith("assets/") else info.filename
            if not rel.startswith("assets/") or rel.endswith(".txt"):
                continue
            ext = rel.rsplit(".", 1)[-1].lower()
            if ext not in CT:
                continue
            data = zf.read(info)
            res = await asyncio.to_thread(put_object, f"{APP_NAME}/library/{app_id}/{uuid.uuid4().hex}.{ext}", data, CT[ext])
            await db.files.insert_one({"file_id": uuid.uuid4().hex, "app_id": app_id, "storage_path": res["path"],
                                       "original_filename": rel.rsplit("/", 1)[-1], "content_type": CT[ext],
                                       "size": res.get("size", len(data)), "is_deleted": False, "in_library": True,
                                       "private": False, "uploaded_by": "plugin import", "created_at": _iso()})
            raw = raw.replace(rel, f"/api/public/files/{res['path']}")
        m = json.loads(raw)
        app_upd = {k: v for k, v in (m.get("app") or {}).items()
                   if k not in ("_id", "app_id", "owner_id", "created_at", "preview_token")}
        if name:
            app_upd["name"] = name
        app_upd["theme"] = m.get("theme") or app_upd.get("theme") or {}
        app_upd["updated_at"] = _iso()
        await db.apps.update_one({"app_id": app_id}, {"$set": app_upd})
        await db.pages.delete_many({"app_id": app_id})
        await db.cms_collections.delete_many({"app_id": app_id})
        await db.cms_items.delete_many({"app_id": app_id})
        for coll in (db.workflows, db.submissions, db.site_users, db.member_access, db.item_locks):
            await coll.delete_many({"app_id": app_id})
        counts = {}

        async def _load(coll, rows, id_field=None):
            rows = [{**r, "app_id": app_id} for r in (rows or [])]
            for r in rows:
                r.pop("_id", None)
                if id_field:
                    r[id_field] = r.get(id_field) or _uid(id_field[:2])
            if rows:
                await coll.insert_many(rows)
            return len(rows)

        counts["pages"] = await _load(db.pages, m.get("pages"), "page_id")
        counts["collections"] = await _load(db.cms_collections, m.get("cms_collections"), "collection_id")
        counts["items"] = await _load(db.cms_items, m.get("cms_items"), "item_id")
        counts["workflows"] = await _load(db.workflows, m.get("workflows"), "workflow_id")
        counts["submissions"] = await _load(db.submissions, m.get("submissions"), "submission_id")
        counts["members"] = await _load(db.site_users, m.get("site_users"), "site_user_id")
        counts["member_access"] = await _load(db.member_access, m.get("member_access"))
        counts["locks"] = await _load(db.item_locks, m.get("item_locks"))
        if m.get("site_settings"):
            s = {**m["site_settings"], "app_id": app_id}
            s.pop("_id", None)
            await db.site_settings.update_one({"app_id": app_id}, {"$set": s}, upsert=True)
        return counts

    def read_manifest(raw: bytes):
        """Returns (manifest, zipfile) when the ZIP is a Lois-Tech plugin package, else (None, None)."""
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile:
            return None, None
        cand = [i for i in zf.infolist() if i.filename.rsplit("/", 1)[-1] == "plugin.json" and not i.is_dir()]
        if not cand:
            return None, None
        try:
            m = json.loads(zf.read(cand[0]).decode("utf-8", "ignore"))
        except Exception:
            return None, None
        if m.get("format") != "omnistack.plugin":
            return None, None
        return m, zf

    @api.post("/site/import-plugin")
    async def import_plugin(file: UploadFile = File(...), name: str = Form(""), user: dict = Depends(get_current_user)):
        """Restores a plugin package as a brand-new tenant owned by the caller."""
        if not (file.filename or "").lower().endswith(".zip"):
            raise HTTPException(400, "Upload the plugin .zip package")
        raw = await file.read()
        if len(raw) > 200 * 1024 * 1024:
            raise HTTPException(413, "That ZIP is larger than the 200 MB limit")
        manifest, zf = read_manifest(raw)
        if not manifest:
            raise HTTPException(400, "That ZIP is not a Lois-Tech plugin package (no plugin.json found)")
        src = manifest.get("app") or {}
        app_id = _uid("app")
        title = (name or src.get("name") or "Restored project")[:120]
        await db.apps.insert_one({
            "app_id": app_id, "owner_id": user["user_id"], "name": title,
            "industry": src.get("industry") or "General", "kind": src.get("kind") or "website",
            "description": src.get("description") or "", "status": src.get("status") or "in-progress",
            "tags": src.get("tags") or [], "color": src.get("color") or "#F97316",
            "transfer_mode": False, "theme": manifest.get("theme") or {},
            "preview_token": f"pv_{uuid.uuid4().hex[:20]}",
            "metrics": {"uptime": 99.9, "cpu": 24, "ram": 48, "response_ms": 120, "visitors_24h": 0},
            "created_at": _iso(), "updated_at": _iso()})
        counts = await restore_plugin(manifest, zf, app_id, user["user_id"], title)
        await log_activity(app_id, user["user_id"], "import.plugin",
                           f"Restored from a plugin package ({counts.get('pages', 0)} pages)")
        app_doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0})
        return {"app": app_doc, "restored": counts}

    return {"read_manifest": read_manifest, "restore_plugin": restore_plugin}


# ---------------- generated project code / docs ----------------

def _website_readme(app_doc, pages, cols, bundler) -> str:
    skipped = "\n".join(f"- {s}" for s in bundler.skipped[:20]) or "- none, everything was bundled"
    return f"""# {app_doc.get('name')} — website package

Exported from Lois-Tech. Everything is local: images, video, fonts and CSS. No hotlinks, no CDN
dependency, nothing to fetch at runtime.

```
site/       the website — open site/index.html to check it, or upload the folder to any host
server/     optional FastAPI form server (receives the site's form posts into SQLite)
cms/        WordPress + Webflow import files
content/    pages.json (structured content, if you want to feed another CMS)
```

## 1. Deploy the site
- **Any static host** — drag `site/` into Netlify, Vercel, Cloudflare Pages, GitHub Pages, S3, or upload
  it to `public_html` over FTP/cPanel. `vercel.json` and `_redirects` are already included.
- **Local check** — `cd site && python3 -m http.server 3000` → http://localhost:3000

## 2. Turn the forms on
1. `cd server && pip install -r requirements.txt`
2. `ADMIN_TOKEN=pick-a-token uvicorn server:app --port 8002`
3. Edit `site/config.js` and set `window.OMNI_FORM_ENDPOINT` to the server's public URL.
4. Read submissions at `http://localhost:8002/admin?token=pick-a-token` (CSV export included).

Prefer your own stack? Point `OMNI_FORM_ENDPOINT` at anything that accepts
`POST /api/submit {{ "form": "...", "fields": {{...}} }}` — Formspree, Basin, a Zapier hook, your CRM.

## 3. Move it into WordPress or Webflow
- **WordPress** — Tools → Import → WordPress → upload `cms/wordpress-import.xml`. Every page arrives
  with its full HTML. Then upload `site/assets/` into `wp-content/uploads/` (or use the Media Library)
  and re-point the image paths, or install any "import external images" plugin to do it automatically.
- **Webflow** — create your pages, then use CMS → Import for `cms/webflow-pages.csv`
  (and `cms/collections/*.csv` for each collection). Paste the Body HTML into an Embed block, or use
  it as the reference build. Fonts: upload `site/assets/fonts/*.woff2` in Site Settings → Fonts.
- **Squarespace / Shopify / any other CMS** — `content/pages.json` has the structured content
  (headings, copy, lists, image paths) so you can map fields without re-typing anything.

## Pages ({len(pages)})
""" + "\n".join(f"- {p.get('name')} → `{p.get('slug')}`" for p in pages) + f"""

## Collections ({len(cols)})
""" + ("\n".join(f"- {c['name']} — {len(c.get('items', []))} item(s) → `site/{c['slug']}/`" for c in cols) or "- none") + f"""

## Assets
{len(bundler.files)} file(s) bundled under `site/assets/` (including fonts).

Anything skipped (unreachable or over the storage budget):
{skipped}
"""


def _fullstack_readme(app_doc, page_data, cols, data, bundler) -> str:
    return f"""# {app_doc.get('name')} — full-stack app

React frontend + FastAPI backend + seeded database + email/password auth (admin & user roles) +
admin dashboard. All of your real content is already in `backend/data/data.json`, so the app is
usable the moment it boots — no extra development required.

```
frontend/   React app (all pages, exact design, member area, admin dashboard)
backend/    FastAPI API, auth, seed script, MongoDB + Postgres schema
docker-compose.yml   one command to run everything
```

## Quick start (Docker)
```bash
cp backend/.env.example backend/.env      # fill in the values, see below
docker compose up --build
```
Frontend → http://localhost:3000 · API → http://localhost:8001/api · Admin → http://localhost:3000/admin

## Quick start (manual)
```bash
# 1. database
#    MongoDB locally, or a free Atlas cluster — copy its connection string
# 2. backend
cd backend && pip install -r requirements.txt
cp .env.example .env      # set MONGO_URL, DB_NAME, JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD
python seed.py            # loads every page, collection, submission, booking and member
uvicorn server:app --reload --port 8001
# 3. frontend
cd ../frontend && npm install
cp .env.example .env      # REACT_APP_BACKEND_URL=http://localhost:8001
npm start
```

## Environment variables
| Variable | Where | What it is |
| --- | --- | --- |
| `MONGO_URL` | backend | MongoDB connection string (`mongodb://localhost:27017` or an Atlas URI) |
| `DB_NAME` | backend | Database name, e.g. `{_slugify(app_doc.get('name'))}` |
| `JWT_SECRET` | backend | Any long random string — signs login tokens |
| `ADMIN_EMAIL` | backend | First admin account, created by `seed.py` |
| `ADMIN_PASSWORD` | backend | That admin's password — change it after first login |
| `CORS_ORIGINS` | backend | Comma-separated frontend origins |
| `SMTP_*` | backend | Optional: outgoing email for form notifications |
| `REACT_APP_BACKEND_URL` | frontend | Public URL of the backend |

## Deploy anywhere
- **Render / Railway / Fly.io** — backend: `pip install -r requirements.txt` then
  `uvicorn server:app --host 0.0.0.0 --port $PORT`. Frontend: `npm run build`, publish `build/`.
- **Vercel / Netlify (frontend) + any Python host (backend)** — set `REACT_APP_BACKEND_URL` to the API URL.
- **Your own VPS** — `docker compose up -d` behind nginx/Caddy for TLS.
- **Postgres instead of Mongo** — `backend/schema.sql` has the equivalent tables; swap the small
  data layer in `server.py` (every query is in one place).

## What's wired and working
- {len(page_data)} page(s) with the exact exported design, {sum(1 for p in page_data if p['protected'])} of them members-only
- {len(cols)} CMS collection(s), {sum(len(c.get('items', [])) for c in cols)} item(s) — editable in the admin dashboard
- Forms + bookings → `POST /api/submit`, visible in the dashboard with CSV export
- {len(data['members'])} member account(s) imported (existing passwords keep working), roles: `admin`, `user`
- {len(data['submissions'])} submission(s)/booking(s) preloaded
- Members area gate on protected pages; paid-page flags carried over (add your Stripe keys to charge)

## Admin dashboard
`/admin` — sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`. Tabs: Submissions, Bookings, Members,
Content (pages + collections CRUD), Settings.

## Assets
{len(bundler.files)} file(s) under `frontend/public/assets/` (images, video, fonts) — all local.
"""


def _fullstack_code(app_doc, theme, page_data, cols) -> dict:
    name = app_doc.get("name") or "App"
    f = {}
    f["backend/requirements.txt"] = "fastapi\nuvicorn[standard]\nmotor\npydantic[email]\npython-dotenv\nbcrypt\npyjwt\npython-multipart\n"
    f["backend/.env.example"] = ("MONGO_URL=mongodb://localhost:27017\n"
                                 f"DB_NAME={_slugify(name)}\n"
                                 "JWT_SECRET=replace-with-a-long-random-string\n"
                                 "ADMIN_EMAIL=admin@example.com\n"
                                 "ADMIN_PASSWORD=change-me-now\n"
                                 "CORS_ORIGINS=http://localhost:3000\n")
    f["backend/server.py"] = SERVER_PY
    f["backend/seed.py"] = SEED_PY
    f["backend/schema.sql"] = SCHEMA_SQL
    f["frontend/package.json"] = json.dumps({
        "name": _slugify(name), "private": True, "version": "1.0.0",
        "dependencies": {"react": "^18.3.1", "react-dom": "^18.3.1", "react-router-dom": "^6.26.0",
                         "react-scripts": "5.0.1"},
        "scripts": {"start": "react-scripts start", "build": "react-scripts build"},
        "browserslist": [">0.2%", "not dead"]}, indent=2)
    f["frontend/.env.example"] = "REACT_APP_BACKEND_URL=http://localhost:8001\n"
    f["frontend/public/index.html"] = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{_x(name)}</title><link rel='stylesheet' href='/fonts.css'>"
        "<link rel='stylesheet' href='/styles.css'><link rel='stylesheet' href='/app.css'>"
        "</head><body><div id='root'></div></body></html>")
    f["frontend/public/app.css"] = APP_CSS
    f["frontend/src/index.js"] = ('import React from "react";\nimport ReactDOM from "react-dom/client";\n'
                                  'import App from "./App";\nReactDOM.createRoot(document.getElementById("root")).render(<App />);\n')
    f["frontend/src/api.js"] = API_JS
    f["frontend/src/App.jsx"] = APP_JSX
    f["frontend/src/Site.jsx"] = SITE_JSX
    f["frontend/src/Auth.jsx"] = AUTH_JSX
    f["frontend/src/Admin.jsx"] = ADMIN_JSX
    f["docker-compose.yml"] = DOCKER_COMPOSE
    f["backend/Dockerfile"] = ("FROM python:3.11-slim\nWORKDIR /app\nCOPY requirements.txt .\n"
                               "RUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\n"
                               "CMD [\"uvicorn\",\"server:app\",\"--host\",\"0.0.0.0\",\"--port\",\"8001\"]\n")
    f["frontend/Dockerfile"] = ("FROM node:20-alpine\nWORKDIR /app\nCOPY package.json .\nRUN npm install\n"
                                "COPY . .\nEXPOSE 3000\nCMD [\"npm\",\"start\"]\n")
    return f


SERVER_PY = '''"""API for the exported site: pages, CMS, forms, bookings, members and admin."""
import os, uuid, json
from datetime import datetime, timezone, timedelta
from typing import Optional, List

import bcrypt, jwt
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr

load_dotenv()
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
JWT_SECRET = os.environ["JWT_SECRET"]
app = FastAPI(title="Site API")
api = APIRouter(prefix="/api")
bearer = HTTPBearer(auto_error=False)
PUBLIC_SLUGS = {"/", "/about", "/services", "/contact"}


def now():
    return datetime.now(timezone.utc).isoformat()


def token_for(user):
    return jwt.encode({"sub": user["user_id"], "role": user.get("role", "user"),
                       "exp": datetime.now(timezone.utc) + timedelta(days=14)}, JWT_SECRET, algorithm="HS256")


async def current_user(cred: Optional[HTTPAuthorizationCredentials] = Depends(bearer)):
    if not cred:
        return None
    try:
        p = jwt.decode(cred.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return await db.users.find_one({"user_id": p["sub"]}, {"_id": 0, "password_hash": 0})


async def require_user(user=Depends(current_user)):
    if not user:
        raise HTTPException(401, "Sign in first")
    return user


async def require_admin(user=Depends(require_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admins only")
    return user


class Credentials(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = ""


class SubmitIn(BaseModel):
    form: str = "Contact"
    fields: dict = {}
    name: Optional[str] = ""
    email: Optional[str] = ""
    booking: Optional[dict] = None


class ItemIn(BaseModel):
    title: str
    slug: Optional[str] = None
    excerpt: Optional[str] = ""
    body: Optional[str] = ""
    cover: Optional[str] = ""
    date: Optional[str] = ""


class PageIn(BaseModel):
    name: Optional[str] = None
    html: Optional[str] = None
    protected: Optional[bool] = None
    seo: Optional[dict] = None


# ---------- auth ----------
@api.post("/auth/register")
async def register(body: Credentials):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "That email is already registered")
    doc = {"user_id": uuid.uuid4().hex, "email": email, "name": body.name or email.split("@")[0],
           "role": "user", "status": "active", "created_at": now(),
           "password_hash": bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()}
    await db.users.insert_one(dict(doc))
    doc.pop("password_hash"); doc.pop("_id", None)
    return {"token": token_for(doc), "user": doc}


@api.post("/auth/login")
async def login(body: Credentials):
    user = await db.users.find_one({"email": body.email.lower().strip()})
    if not user or not user.get("password_hash") or not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(401, "Wrong email or password")
    user.pop("password_hash"); user.pop("_id", None)
    return {"token": token_for(user), "user": user}


@api.get("/auth/me")
async def me(user=Depends(require_user)):
    return user


# ---------- public site ----------
@api.get("/site")
async def site():
    s = await db.site.find_one({"_id": "site"}, {"_id": 0}) or {}
    pages = await db.pages.find({}, {"_id": 0, "html": 0, "blocks": 0}).to_list(300)
    return {"site": s, "pages": pages}


@api.get("/pages/{slug:path}")
async def page(slug: str, user=Depends(current_user)):
    key = "/" + slug.strip("/") if slug.strip("/") else "/"
    pg = await db.pages.find_one({"slug": key}, {"_id": 0})
    if not pg:
        raise HTTPException(404, "Page not found")
    if pg.get("protected") and not user:
        return {"slug": key, "name": pg.get("name"), "protected": True, "html": None,
                "message": "Members only — sign in to read this page."}
    return pg


@api.get("/collections")
async def collections():
    cols = await db.collections_meta.find({}, {"_id": 0}).to_list(100)
    for c in cols:
        c["items"] = await db.items.find({"collection": c["slug"]}, {"_id": 0}).to_list(500)
    return cols


@api.post("/submit")
async def submit(body: SubmitIn):
    doc = {"submission_id": uuid.uuid4().hex, "form_name": body.form[:120],
           "name": (body.name or body.fields.get("Name") or body.fields.get("name") or "")[:120],
           "email": (body.email or body.fields.get("Email") or body.fields.get("email") or "").lower()[:160],
           "fields": body.fields, "status": "new", "created_at": now()}
    if body.booking:
        doc["booking"] = {**body.booking, "status": "requested", "requested_at": now()}
    await db.submissions.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


# ---------- member area ----------
@api.get("/me/submissions")
async def my_submissions(user=Depends(require_user)):
    return await db.submissions.find({"email": user["email"]}, {"_id": 0}).sort("created_at", -1).to_list(200)


# ---------- admin ----------
@api.get("/admin/submissions")
async def admin_submissions(user=Depends(require_admin)):
    return await db.submissions.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


@api.patch("/admin/submissions/{submission_id}")
async def admin_submission_status(submission_id: str, body: dict, user=Depends(require_admin)):
    await db.submissions.update_one({"submission_id": submission_id}, {"$set": {"status": str(body.get("status") or "new")[:40]}})
    return await db.submissions.find_one({"submission_id": submission_id}, {"_id": 0})


@api.get("/admin/bookings")
async def admin_bookings(user=Depends(require_admin)):
    return await db.submissions.find({"booking": {"$exists": True}}, {"_id": 0}).sort("booking.date", 1).to_list(1000)


@api.patch("/admin/bookings/{submission_id}")
async def admin_booking(submission_id: str, body: dict, user=Depends(require_admin)):
    upd = {f"booking.{k}": v for k, v in body.items() if k in ("date", "slot", "status", "duration_min", "notes")}
    await db.submissions.update_one({"submission_id": submission_id}, {"$set": upd})
    return await db.submissions.find_one({"submission_id": submission_id}, {"_id": 0})


@api.get("/admin/members")
async def admin_members(user=Depends(require_admin)):
    return await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)


@api.patch("/admin/members/{user_id}")
async def admin_member(user_id: str, body: dict, user=Depends(require_admin)):
    upd = {k: v for k, v in body.items() if k in ("role", "status", "name")}
    await db.users.update_one({"user_id": user_id}, {"$set": upd})
    return await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})


@api.patch("/admin/pages/{page_id}")
async def admin_page(page_id: str, body: PageIn, user=Depends(require_admin)):
    upd = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    await db.pages.update_one({"page_id": page_id}, {"$set": {**upd, "updated_at": now()}})
    return await db.pages.find_one({"page_id": page_id}, {"_id": 0})


@api.post("/admin/collections/{slug}/items")
async def admin_item_create(slug: str, body: ItemIn, user=Depends(require_admin)):
    doc = {"item_id": uuid.uuid4().hex, "collection": slug, "status": "published",
           **body.model_dump(), "created_at": now()}
    doc["slug"] = doc.get("slug") or body.title.lower().replace(" ", "-")[:80]
    await db.items.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


@api.put("/admin/items/{item_id}")
async def admin_item_update(item_id: str, body: ItemIn, user=Depends(require_admin)):
    await db.items.update_one({"item_id": item_id}, {"$set": body.model_dump(exclude_none=True)})
    return await db.items.find_one({"item_id": item_id}, {"_id": 0})


@api.delete("/admin/items/{item_id}")
async def admin_item_delete(item_id: str, user=Depends(require_admin)):
    await db.items.delete_one({"item_id": item_id})
    return {"ok": True}


@api.get("/admin/settings")
async def admin_settings(user=Depends(require_admin)):
    return await db.site.find_one({"_id": "site"}, {"_id": 0}) or {}


@api.put("/admin/settings")
async def admin_settings_save(body: dict, user=Depends(require_admin)):
    await db.site.update_one({"_id": "site"}, {"$set": {k: v for k, v in body.items() if k != "_id"}}, upsert=True)
    return await db.site.find_one({"_id": "site"}, {"_id": 0})


@api.get("/health")
async def health():
    return {"ok": True, "pages": await db.pages.count_documents({})}


app.include_router(api)
app.add_middleware(CORSMiddleware,
                   allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",")],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
'''

SEED_PY = '''"""Loads data/data.json into the database and creates the first admin account.

    python seed.py            # idempotent, safe to re-run
"""
import asyncio, json, os, uuid
from datetime import datetime, timezone

import bcrypt
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()
DATA = json.load(open(os.path.join(os.path.dirname(__file__), "data", "data.json")))


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc).isoformat()

    await db.site.update_one({"_id": "site"}, {"$set": DATA["site"]}, upsert=True)

    for pg in DATA["pages"]:
        pg["page_id"] = pg.get("page_id") or uuid.uuid4().hex
        await db.pages.update_one({"slug": pg["slug"]}, {"$set": pg}, upsert=True)

    for col in DATA["collections"]:
        await db.collections_meta.update_one({"slug": col["slug"]},
                                             {"$set": {"slug": col["slug"], "name": col["name"]}}, upsert=True)
        for it in col.get("items", []):
            it = {**it, "collection": col["slug"]}
            it["item_id"] = it.get("item_id") or uuid.uuid4().hex
            await db.items.update_one({"collection": col["slug"], "slug": it.get("slug")}, {"$set": it}, upsert=True)

    for s in DATA.get("submissions", []):
        s.pop("app_id", None)
        s["submission_id"] = s.get("submission_id") or uuid.uuid4().hex
        await db.submissions.update_one({"submission_id": s["submission_id"]}, {"$set": s}, upsert=True)

    for m in DATA.get("members", []):
        m.pop("app_id", None)
        doc = {"user_id": m.get("site_user_id") or uuid.uuid4().hex, "email": (m.get("email") or "").lower(),
               "name": m.get("name") or "", "role": m.get("role") or "user",
               "status": m.get("status") or "active", "created_at": m.get("created_at") or now}
        if m.get("password_hash"):
            doc["password_hash"] = m["password_hash"]   # existing member passwords keep working
        if doc["email"]:
            await db.users.update_one({"email": doc["email"]}, {"$set": doc}, upsert=True)

    admin_email = (os.environ.get("ADMIN_EMAIL") or "").lower().strip()
    if admin_email:
        await db.users.update_one({"email": admin_email}, {"$set": {
            "user_id": uuid.uuid4().hex, "email": admin_email, "name": "Administrator", "role": "admin",
            "status": "active", "created_at": now,
            "password_hash": bcrypt.hashpw(os.environ.get("ADMIN_PASSWORD", "change-me-now").encode(),
                                           bcrypt.gensalt()).decode()}}, upsert=True)

    print("Seeded:", await db.pages.count_documents({}), "pages,",
          await db.items.count_documents({}), "items,",
          await db.submissions.count_documents({}), "submissions,",
          await db.users.count_documents({}), "users")

asyncio.run(main())
'''

SCHEMA_SQL = """-- Postgres / Supabase equivalent of the app's collections.
create extension if not exists "pgcrypto";

create table if not exists site (
  id text primary key default 'site',
  name text, industry text, description text, logo text,
  theme jsonb default '{}'::jsonb, webapp jsonb default '{}'::jsonb
);

create table if not exists pages (
  page_id uuid primary key default gen_random_uuid(),
  slug text unique not null, name text, html text,
  blocks jsonb default '[]'::jsonb, seo jsonb default '{}'::jsonb,
  protected boolean default false, paid boolean default false,
  updated_at timestamptz default now()
);

create table if not exists collections_meta (slug text primary key, name text);

create table if not exists items (
  item_id uuid primary key default gen_random_uuid(),
  collection text references collections_meta(slug) on delete cascade,
  slug text, title text, excerpt text, body text, cover text, date text,
  status text default 'published', created_at timestamptz default now(),
  unique (collection, slug)
);

create table if not exists users (
  user_id uuid primary key default gen_random_uuid(),
  email text unique not null, name text, password_hash text,
  role text not null default 'user', status text not null default 'active',
  created_at timestamptz default now()
);

create table if not exists submissions (
  submission_id uuid primary key default gen_random_uuid(),
  form_name text, name text, email text,
  fields jsonb default '{}'::jsonb, booking jsonb,
  status text default 'new', created_at timestamptz default now()
);

create index if not exists submissions_created_idx on submissions (created_at desc);
create index if not exists submissions_booking_idx on submissions ((booking->>'date'));
"""

DOCKER_COMPOSE = """services:
  mongo:
    image: mongo:7
    volumes: ["mongo:/data/db"]
    ports: ["27017:27017"]
  backend:
    build: ./backend
    env_file: ./backend/.env
    environment:
      MONGO_URL: mongodb://mongo:27017
    depends_on: [mongo]
    ports: ["8001:8001"]
    command: sh -c "python seed.py && uvicorn server:app --host 0.0.0.0 --port 8001"
  frontend:
    build: ./frontend
    environment:
      REACT_APP_BACKEND_URL: http://localhost:8001
    depends_on: [backend]
    ports: ["3000:3000"]
volumes:
  mongo:
"""

API_JS = """const BASE = (process.env.REACT_APP_BACKEND_URL || "http://localhost:8001") + "/api";

export function token() { return localStorage.getItem("token") || ""; }
export function setToken(t) { t ? localStorage.setItem("token", t) : localStorage.removeItem("token"); }

export async function req(path, { method = "GET", body } = {}) {
  const res = await fetch(BASE + path, {
    method,
    headers: { "Content-Type": "application/json", ...(token() ? { Authorization: `Bearer ${token()}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}
"""

APP_JSX = """import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { req, token, setToken } from "./api";
import SitePage from "./Site";
import { Login, Register, Account } from "./Auth";
import Admin from "./Admin";

export default function App() {
  const [site, setSite] = useState(null);
  const [user, setUser] = useState(null);

  useEffect(() => { req("/site").then(setSite).catch(() => setSite({ site: {}, pages: [] })); }, []);
  useEffect(() => { if (token()) req("/auth/me").then(setUser).catch(() => setToken("")); }, []);

  if (!site) return <div className="boot">Loading…</div>;
  const pages = site.pages || [];

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login onDone={setUser} />} />
        <Route path="/register" element={<Register onDone={setUser} />} />
        <Route path="/account" element={user ? <Account user={user} onOut={() => { setToken(""); setUser(null); }} /> : <Navigate to="/login" />} />
        <Route path="/admin/*" element={<Admin user={user} setUser={setUser} pages={pages} />} />
        {pages.map((p) => (
          <Route key={p.slug} path={p.slug} element={<SitePage slug={p.slug} user={user} />} />
        ))}
        <Route path="*" element={<SitePage slug="/" user={user} />} />
      </Routes>
    </BrowserRouter>
  );
}
"""

SITE_JSX = """import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { req } from "./api";

/** Renders a page exactly as designed, wires its forms to the API and gates members-only pages. */
export default function SitePage({ slug, user }) {
  const [page, setPage] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => { setPage(null); req(`/pages${slug === "/" ? "/" : slug}`).then(setPage).catch((e) => setErr(e.message)); }, [slug, user]);

  useEffect(() => {
    if (!page?.html) return;
    const forms = Array.from(document.querySelectorAll("#page form"));
    const handler = async (e) => {
      e.preventDefault();
      const form = e.target;
      const fields = {};
      form.querySelectorAll("input,textarea,select").forEach((el, i) => {
        fields[el.name || el.placeholder || `field_${i}`] = el.value;
      });
      try {
        await req("/submit", { method: "POST", body: { form: form.dataset.form || page.name, fields } });
        form.innerHTML = "<p style='padding:18px 0'>Thanks — we'll be in touch shortly.</p>";
      } catch { alert("Could not send that just now. Please try again."); }
    };
    forms.forEach((f) => f.addEventListener("submit", handler));
    return () => forms.forEach((f) => f.removeEventListener("submit", handler));
  }, [page]);

  if (err) return <div className="boot">{err}</div>;
  if (!page) return <div className="boot">Loading…</div>;
  if (page.protected && !page.html) {
    return (
      <div className="gate">
        <h1>Members only</h1>
        <p>{page.message}</p>
        <p><Link className="btn" to="/login">Sign in</Link> <Link className="btn2" to="/register">Create an account</Link></p>
      </div>
    );
  }
  return (
    <>
      <div className="account-bar">
        {user ? <Link to="/account">{user.name || user.email}</Link> : <Link to="/login">Sign in</Link>}
        {user?.role === "admin" && <Link to="/admin">Admin</Link>}
      </div>
      <div id="page" dangerouslySetInnerHTML={{ __html: page.html }} />
    </>
  );
}
"""

AUTH_JSX = """import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { req, setToken } from "./api";

function Form({ title, path, onDone, extra }) {
  const [f, setF] = useState({ email: "", password: "", name: "" });
  const [err, setErr] = useState("");
  const nav = useNavigate();
  async function submit(e) {
    e.preventDefault();
    try {
      const { token, user } = await req(path, { method: "POST", body: f });
      setToken(token); onDone?.(user); nav(user.role === "admin" ? "/admin" : "/account");
    } catch (e) { setErr(e.message); }
  }
  return (
    <form className="auth" onSubmit={submit}>
      <h1>{title}</h1>
      {extra && <input placeholder="Your name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />}
      <input placeholder="Email" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
      <input placeholder="Password" type="password" required value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
      {err && <p className="err">{err}</p>}
      <button className="btn">{title}</button>
      <p className="muted">{extra ? <Link to="/login">I already have an account</Link> : <Link to="/register">Create an account</Link>}</p>
      <p className="muted"><Link to="/">← Back to the site</Link></p>
    </form>
  );
}

export const Login = ({ onDone }) => <Form title="Sign in" path="/auth/login" onDone={onDone} />;
export const Register = ({ onDone }) => <Form title="Create account" path="/auth/register" onDone={onDone} extra />;

export function Account({ user, onOut }) {
  const [rows, setRows] = useState([]);
  useEffect(() => { req("/me/submissions").then(setRows).catch(() => {}); }, []);
  return (
    <div className="panel">
      <h1>My account</h1>
      <p className="muted">{user.email} · {user.role}</p>
      <h2>My messages & bookings</h2>
      <table className="table"><thead><tr><th>Form</th><th>When</th><th>Booking</th><th>Status</th></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.submission_id}><td>{r.form_name}</td><td>{(r.created_at || "").slice(0, 10)}</td>
            <td>{r.booking ? `${r.booking.date} ${r.booking.slot || ""}` : "—"}</td><td>{r.status}</td></tr>))}
        </tbody></table>
      <p><button className="btn2" onClick={onOut}>Sign out</button> <Link className="btn2" to="/">Back to the site</Link></p>
    </div>
  );
}
"""

ADMIN_JSX = """import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { req, setToken } from "./api";
import { Login } from "./Auth";

const TABS = ["Submissions", "Bookings", "Members", "Content", "Settings"];

export default function Admin({ user, setUser, pages }) {
  const [tab, setTab] = useState("Submissions");
  if (!user) return <Login onDone={setUser} />;
  if (user.role !== "admin") return <div className="boot">This account is not an administrator.</div>;
  return (
    <div className="admin">
      <aside>
        <div className="brand">Admin</div>
        {TABS.map((t) => <button key={t} className={t === tab ? "on" : ""} onClick={() => setTab(t)}>{t}</button>)}
        <Link to="/">← View site</Link>
        <button onClick={() => { setToken(""); setUser(null); }}>Sign out</button>
      </aside>
      <main>
        {tab === "Submissions" && <Submissions />}
        {tab === "Bookings" && <Bookings />}
        {tab === "Members" && <Members />}
        {tab === "Content" && <Content pages={pages} />}
        {tab === "Settings" && <Settings />}
      </main>
    </div>
  );
}

function useRows(path) {
  const [rows, setRows] = useState([]);
  const load = () => req(path).then(setRows).catch(() => {});
  useEffect(() => { load(); }, [path]);
  return [rows, load];
}

function Submissions() {
  const [rows, load] = useRows("/admin/submissions");
  const csv = () => {
    const body = ["form,name,email,status,created_at", ...rows.map((r) => [r.form_name, r.name, r.email, r.status, r.created_at].join(","))].join("\\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([body], { type: "text/csv" }));
    a.download = "submissions.csv"; a.click();
  };
  return (
    <>
      <h1>Submissions <button className="btn2" onClick={csv}>Export CSV</button></h1>
      <table className="table"><thead><tr><th>Form</th><th>Name</th><th>Email</th><th>Fields</th><th>Status</th></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.submission_id}><td>{r.form_name}</td><td>{r.name}</td><td>{r.email}</td>
            <td><pre>{JSON.stringify(r.fields, null, 1)}</pre></td>
            <td><select value={r.status} onChange={async (e) => { await req(`/admin/submissions/${r.submission_id}`, { method: "PATCH", body: { status: e.target.value } }); load(); }}>
              {["new", "read", "handled", "archived"].map((s) => <option key={s}>{s}</option>)}</select></td></tr>))}
        </tbody></table>
    </>
  );
}

function Bookings() {
  const [rows, load] = useRows("/admin/bookings");
  return (
    <>
      <h1>Bookings</h1>
      <table className="table"><thead><tr><th>Date</th><th>Time</th><th>Client</th><th>Service</th><th>Status</th></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.submission_id}><td>{r.booking?.date}</td><td>{r.booking?.slot}</td><td>{r.name}<br /><span className="muted">{r.email}</span></td>
            <td>{r.form_name}</td>
            <td><select value={r.booking?.status || "requested"} onChange={async (e) => { await req(`/admin/bookings/${r.submission_id}`, { method: "PATCH", body: { status: e.target.value } }); load(); }}>
              {["requested", "confirmed", "cancelled", "completed"].map((s) => <option key={s}>{s}</option>)}</select></td></tr>))}
        </tbody></table>
    </>
  );
}

function Members() {
  const [rows, load] = useRows("/admin/members");
  return (
    <>
      <h1>Members</h1>
      <table className="table"><thead><tr><th>Email</th><th>Name</th><th>Role</th><th>Status</th></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.user_id}><td>{r.email}</td><td>{r.name}</td>
            <td><select value={r.role} onChange={async (e) => { await req(`/admin/members/${r.user_id}`, { method: "PATCH", body: { role: e.target.value } }); load(); }}>
              <option>user</option><option>admin</option></select></td>
            <td><select value={r.status} onChange={async (e) => { await req(`/admin/members/${r.user_id}`, { method: "PATCH", body: { status: e.target.value } }); load(); }}>
              <option>active</option><option>suspended</option></select></td></tr>))}
        </tbody></table>
    </>
  );
}

function Content({ pages }) {
  const [cols, setCols] = useState([]);
  const [edit, setEdit] = useState(null);
  const load = () => req("/collections").then(setCols).catch(() => {});
  useEffect(() => { load(); }, []);
  return (
    <>
      <h1>Content</h1>
      <h2>Pages</h2>
      <ul className="list">{pages.map((p) => <li key={p.slug}><strong>{p.name}</strong> <span className="muted">{p.slug}{p.protected ? " · members only" : ""}</span></li>)}</ul>
      {cols.map((c) => (
        <section key={c.slug}>
          <h2>{c.name} <button className="btn2" onClick={() => setEdit({ collection: c.slug, title: "" })}>Add item</button></h2>
          <ul className="list">{(c.items || []).map((it) => (
            <li key={it.item_id || it.slug}><strong>{it.title}</strong> <span className="muted">{it.slug}</span>
              <button className="btn2" onClick={() => setEdit({ ...it, collection: c.slug })}>Edit</button>
              {it.item_id && <button className="btn2" onClick={async () => { await req(`/admin/items/${it.item_id}`, { method: "DELETE" }); load(); }}>Delete</button>}
            </li>))}</ul>
        </section>
      ))}
      {edit && (
        <div className="modal">
          <h2>{edit.item_id ? "Edit item" : "New item"}</h2>
          {["title", "slug", "excerpt", "cover", "date"].map((k) => (
            <input key={k} placeholder={k} value={edit[k] || ""} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })} />
          ))}
          <textarea rows={6} placeholder="body" value={edit.body || ""} onChange={(e) => setEdit({ ...edit, body: e.target.value })} />
          <button className="btn" onClick={async () => {
            const body = { title: edit.title, slug: edit.slug, excerpt: edit.excerpt, body: edit.body, cover: edit.cover, date: edit.date };
            if (edit.item_id) await req(`/admin/items/${edit.item_id}`, { method: "PUT", body });
            else await req(`/admin/collections/${edit.collection}/items`, { method: "POST", body });
            setEdit(null); load();
          }}>Save</button>
          <button className="btn2" onClick={() => setEdit(null)}>Cancel</button>
        </div>
      )}
    </>
  );
}

function Settings() {
  const [s, setS] = useState({});
  useEffect(() => { req("/admin/settings").then(setS).catch(() => {}); }, []);
  return (
    <>
      <h1>Settings</h1>
      {["name", "industry", "description"].map((k) => (
        <label key={k}>{k}<input value={s[k] || ""} onChange={(e) => setS({ ...s, [k]: e.target.value })} /></label>
      ))}
      <button className="btn" onClick={async () => { await req("/admin/settings", { method: "PUT", body: s }); alert("Saved"); }}>Save</button>
    </>
  );
}
"""

APP_CSS = """.boot,.gate{min-height:60vh;display:grid;place-items:center;text-align:center;padding:40px;gap:12px}
.account-bar{position:fixed;top:10px;right:14px;z-index:60;display:flex;gap:10px;font-size:13px}
.account-bar a{background:rgba(0,0,0,.55);color:#fff;padding:7px 14px;border-radius:999px;backdrop-filter:blur(10px)}
.auth,.panel{max-width:520px;margin:8vh auto;display:grid;gap:12px;padding:0 24px}
.panel{max-width:900px}
.auth input,.panel input,.modal input,.modal textarea{padding:12px;border:1px solid var(--bd,#ddd);border-radius:10px;font:inherit;background:transparent;color:inherit}
.btn,.btn2{cursor:pointer;border:0;font:inherit}
.err{color:#e11d48}.muted{opacity:.7;font-size:13px}
.admin{display:flex;min-height:100vh}
.admin aside{width:210px;padding:20px 14px;display:flex;flex-direction:column;gap:6px;border-right:1px solid var(--bd,#e5e7eb)}
.admin aside .brand{font-weight:800;margin-bottom:10px}
.admin aside button,.admin aside a{text-align:left;background:transparent;border:0;padding:10px 12px;border-radius:10px;cursor:pointer;font:inherit;color:inherit;opacity:.75}
.admin aside button.on{background:var(--p,#f97316);color:#fff;opacity:1}
.admin main{flex:1;padding:28px 32px;max-width:1100px}
.admin h1{display:flex;align-items:center;gap:12px;font-size:26px}
.table{width:100%;border-collapse:collapse;margin-top:14px;font-size:13px}
.table th,.table td{border-bottom:1px solid var(--bd,#e5e7eb);padding:9px;text-align:left;vertical-align:top}
.table pre{margin:0;white-space:pre-wrap;font-size:11px;max-width:280px}
.list{list-style:none;padding:0;display:grid;gap:6px}.list li{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--bd,#eee)}
.modal{position:fixed;inset:auto 24px 24px auto;width:380px;background:var(--sf,#fff);border:1px solid var(--bd,#ddd);border-radius:16px;padding:18px;display:grid;gap:8px;box-shadow:0 30px 80px -30px rgba(0,0,0,.5);z-index:80}
@media(max-width:860px){.admin{flex-direction:column}.admin aside{width:auto;flex-direction:row;flex-wrap:wrap;border-right:0;border-bottom:1px solid var(--bd,#eee)}}
"""
