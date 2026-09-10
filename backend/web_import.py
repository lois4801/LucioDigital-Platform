"""Full-site importer: crawls every internal page, downloads media into the client library,
recreates forms (wired to the Inbox) and navigation, extracts the colour scheme, and reports back."""
import os
import re
import json
import uuid
import asyncio
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Optional, List, Callable
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException, Depends
from pydantic import BaseModel

from llm_provider import get_chat, UserMessage
from storage import MIME, put_object
from files_lib import usage_for, APP_NAME
from studio import _parse_json, _ensure_ids, _clean_theme, BLOCK_SCHEMA, DEFAULT_THEME

logger = logging.getLogger(__name__)
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
require_ai_access = None
place_video = None
search_stock = None
store_video = None
IMPORTANT_RE = re.compile(r"service|about|product|pricing|price|contact|team|work|portfolio|menu|solution|industr|faq|gallery|book|quote|location|schedule|career", re.I)
EMBED_RE = re.compile(r"(youtube\.com|youtu\.be|player\.vimeo\.com|vimeo\.com|wistia|loom\.com)", re.I)

UA = "Mozilla/5.0 (compatible; LoisTechImporter/1.0; +https://omnistack.ai)"
MAX_BYTES = 1_500_000
MAX_PAGES = 100
MAX_DEPTH = 3
MAX_IMAGES = 80
MAX_IMAGE_BYTES = 8 * 1024 * 1024
AI_CONCURRENCY = 4

SKIP_PATH = re.compile(r"(/wp-(json|admin|login)|/feed|/tag/|/category/|/author/|/page/\d|/\d{4}/\d{2}/|\.(pdf|zip|docx?|xlsx?|jpe?g|png|gif|webp|svg|mp4|mp3|ico|css|js)$)", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,2}[\s.-])?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}")
HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}\b")
RGB_RE = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})")
CSS_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")
NEUTRAL = {"#fff", "#ffffff", "#000", "#000000", "#fefefe", "#f9f9f9", "#fafafa", "#eee", "#eeeeee", "#ccc", "#cccccc", "#333", "#333333", "#666", "#666666", "#999", "#999999", "#f5f5f5", "#111", "#111111", "#222", "#222222"}
FIELD_TYPES = {"text", "email", "tel", "number", "url", "date", "textarea", "select", "checkbox", "radio", "password"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _uid(p):
    return f"{p}_{uuid.uuid4().hex[:12]}"


def _norm_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise HTTPException(400, "Enter a website address")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    p = urlparse(url)
    if not p.netloc or "." not in p.netloc:
        raise HTTPException(400, "That doesn't look like a valid website address")
    if p.hostname in ("localhost", "127.0.0.1", "0.0.0.0") or (p.hostname or "").endswith(".local"):
        raise HTTPException(400, "Local addresses cannot be imported")
    return url


def _slugify(path: str) -> str:
    s = re.sub(r"[^a-z0-9-]+", "-", (path or "").lower().strip("/ ")).strip("-")
    return "/" + s if s else "/"


async def _fetch(client: httpx.AsyncClient, url: str):
    try:
        r = await client.get(url)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}"
        if "html" not in r.headers.get("content-type", "text/html"):
            return None, "not an HTML page"
        return r.text[:MAX_BYTES], None
    except Exception as e:
        return None, type(e).__name__


def _text_of(soup, sel: str, limit: int, cap: int = 240) -> List[str]:
    out, seen = [], set()
    for el in soup.select(sel):
        t = " ".join(el.get_text(" ", strip=True).split())[:cap]
        if len(t) > 2 and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
        if len(out) >= limit:
            break
    return out


def _label_for(soup, el) -> str:
    fid = el.get("id")
    if fid:
        lab = soup.find("label", attrs={"for": fid})
        if lab:
            return " ".join(lab.get_text(" ", strip=True).split())[:80]
    parent_lab = el.find_parent("label")
    if parent_lab:
        return " ".join(parent_lab.get_text(" ", strip=True).split())[:80]
    return (el.get("aria-label") or el.get("placeholder") or (el.get("name") or "").replace("_", " ").replace("-", " ").title())[:80]


def _parse_forms(soup) -> List[dict]:
    forms = []
    for f in soup.find_all("form"):
        fields = []
        for el in f.find_all(["input", "textarea", "select"]):
            t = (el.get("type") or ("textarea" if el.name == "textarea" else "select" if el.name == "select" else "text")).lower()
            if t in ("hidden", "submit", "button", "image", "reset"):
                continue
            if t not in FIELD_TYPES:
                t = "text"
            fld = {"name": (el.get("name") or el.get("id") or f"field{len(fields) + 1}")[:60],
                   "label": _label_for(soup, el) or "Field", "type": t,
                   "placeholder": (el.get("placeholder") or "")[:100],
                   "required": el.has_attr("required") or "required" in (el.get("class") or [])}
            if el.name == "select":
                fld["options"] = [" ".join(o.get_text(" ", strip=True).split())[:60] for o in el.find_all("option") if o.get_text(strip=True)][:25]
            fields.append(fld)
            if len(fields) >= 20:
                break
        names = " ".join(x["name"].lower() for x in fields)
        if not fields or (len(fields) <= 1 and re.search(r"\b(q|s|search|query|keyword)\b", names)):
            continue
        btn = f.find(["button", "input"], attrs={"type": re.compile("submit", re.I)}) or f.find("button")
        heading = ""
        for prev in f.find_all_previous(["h1", "h2", "h3"], limit=1):
            heading = " ".join(prev.get_text(" ", strip=True).split())[:80]
        forms.append({"heading": heading or "Get in touch", "fields": fields,
                      "submit_label": (btn.get_text(" ", strip=True) if btn and btn.name == "button" else (btn.get("value") if btn else "") or "Send")[:40]})
        if len(forms) >= 3:
            break
    return forms


def _parse_nav(soup, url: str) -> List[dict]:
    root = soup.select_one("header nav") or soup.select_one("nav") or soup.select_one("header")
    if not root:
        return []
    items, seen = [], set()
    host = urlparse(url).netloc
    top = root.select("li") or root.find_all("a", href=True)
    for li in top:
        a = li if getattr(li, "name", "") == "a" else li.find("a", href=True)
        if not a or li.find_parent("li") is not None:
            continue
        label = " ".join(a.get_text(" ", strip=True).split())[:40]
        href = urljoin(url, a["href"]).split("#")[0]
        if not label or label.lower() in seen:
            continue
        seen.add(label.lower())
        kids = []
        for sub in (li.select("li a[href]") if getattr(li, "name", "") == "li" else []):
            sl = " ".join(sub.get_text(" ", strip=True).split())[:40]
            sh = urljoin(url, sub["href"]).split("#")[0]
            if sl and urlparse(sh).netloc == host:
                kids.append({"label": sl, "href": _slugify(urlparse(sh).path)})
            if len(kids) >= 8:
                break
        item = {"label": label, "href": _slugify(urlparse(href).path) if urlparse(href).netloc == host else href}
        kids = [k for k in kids if k["href"] != item["href"] and k["label"].lower() != label.lower()]
        if kids:
            item["children"] = kids
        items.append(item)
        if len(items) >= 8:
            break
    return items


def _colors_from_css(css: str) -> dict:
    """Split declared colours into background / text / button buckets."""
    bg, fg, btn = Counter(), Counter(), Counter()

    def add(counter, val):
        for h in HEX_RE.findall(val):
            h = h.lower()
            if len(h) == 4:
                h = "#" + "".join(c * 2 for c in h[1:])
            counter[h] += 1
        for m in RGB_RE.finditer(val):
            r, g, b = (min(255, int(x)) for x in m.groups())
            counter["#%02x%02x%02x" % (r, g, b)] += 1
    for sel, body in CSS_RULE_RE.findall(css or "")[:4000]:
        s = sel.lower()
        for decl in body.split(";"):
            if ":" not in decl:
                continue
            prop, val = decl.split(":", 1)
            prop = prop.strip().lower()
            if "background" in prop:
                add(btn if re.search(r"btn|button|cta|submit", s) else bg, val)
            elif prop == "color":
                add(btn if re.search(r"btn|button|cta|submit", s) else fg, val)
            elif prop in ("border-color", "fill", "stroke"):
                add(btn, val)
    pick = lambda c, n=4: [h for h, _ in c.most_common(24) if h not in NEUTRAL][:n]
    return {"background": pick(bg), "text": pick(fg), "button": pick(btn), "all": pick(bg + fg + btn, 8)}


def _parse_page(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    for bad in soup(["script", "style", "noscript"]):
        bad.decompose()

    def meta(n, a="name"):
        el = soup.find("meta", attrs={a: n})
        return el.get("content") if el else None
    images, seen = [], set()

    def add_img(src, alt=""):
        if not src or src.startswith("data:") or len(images) >= 40:
            return
        full = urljoin(url, src.strip()).split("?")[0]
        if full in seen or full.lower().endswith(".svg"):
            return
        seen.add(full)
        images.append({"url": full, "alt": (alt or "")[:120]})

    def from_srcset(v):
        best, best_w = None, -1
        for part in (v or "").split(","):
            bits = part.strip().split()
            if not bits:
                continue
            w = int(re.sub(r"\D", "", bits[-1]) or 0) if len(bits) > 1 else 0
            if w >= best_w:
                best, best_w = bits[0], w
        return best
    for im in soup.find_all("img"):
        add_img(im.get("src") or im.get("data-src") or im.get("data-lazy-src") or im.get("data-original") or from_srcset(im.get("srcset") or im.get("data-srcset")), im.get("alt"))
    for so in soup.find_all("source"):
        add_img(from_srcset(so.get("srcset") or so.get("data-srcset")))
    for el in soup.find_all(style=True)[:300]:
        for m in re.finditer(r"url\((['\"]?)([^'\")]+)\1\)", el.get("style", "")):
            add_img(m.group(2))
    if meta("og:image", "property"):
        add_img(meta("og:image", "property"))
    logo = None
    for im in soup.find_all("img")[:25]:
        hay = f"{im.get('class', '')} {im.get('id', '')} {im.get('alt', '')} {im.get('src', '')}".lower()
        if "logo" in hay and im.get("src") and not im["src"].startswith("data:"):
            logo = urljoin(url, im["src"])
            break
    links, lseen = [], set()
    host = urlparse(url).netloc
    for a in soup.find_all("a", href=True):
        full = urljoin(url, a["href"]).split("#")[0].rstrip("/") or url
        if urlparse(full).netloc != host or full in lseen or SKIP_PATH.search(urlparse(full).path or ""):
            continue
        lseen.add(full)
        label = " ".join(a.get_text(" ", strip=True).split())[:40]
        links.append({"label": label, "url": full})
    body = " ".join(soup.get_text(" ", strip=True).split())
    inline_css = " ".join(el.get("style", "") for el in soup.find_all(style=True)[:400])
    path = urlparse(url).path
    return {
        "url": url, "slug": _slugify(path),
        "title": (soup.title.string.strip() if soup.title and soup.title.string else None),
        "description": meta("description") or meta("og:description", "property"),
        "site_name": meta("og:site_name", "property"),
        "og_image": meta("og:image", "property"),
        "theme_color": meta("theme-color"),
        "logo": logo,
        "h1": _text_of(soup, "h1", 4), "h2": _text_of(soup, "h2", 16), "h3": _text_of(soup, "h3", 24),
        "paragraphs": _text_of(soup, "p", 45, 420),
        "list_items": _text_of(soup, "li", 45, 160),
        "buttons": _text_of(soup, "a.btn, button, .button, .cta, a[class*=button]", 14, 40),
        "images": images, "links": links[:60],
        "forms": _parse_forms(soup),
        "nav": _parse_nav(soup, url),
        "emails": list(dict.fromkeys(EMAIL_RE.findall(body)))[:5],
        "phones": list(dict.fromkeys(PHONE_RE.findall(body)))[:5],
        "addresses": _text_of(soup, "address", 3, 200),
        "inline_css": inline_css[:40000],
        "embeds": list(dict.fromkeys([urljoin(url, (f.get("src") or "")) for f in soup.find_all("iframe") if EMBED_RE.search(f.get("src") or "")]))[:6],
        "stylesheets": [urljoin(url, l["href"]) for l in soup.find_all("link", rel=lambda v: v and "stylesheet" in v, href=True)][:4],
        "text": body[:5000],
    }


def _rank_links(home: dict, base: str) -> List[str]:
    """Order internal links so the meaningful pages get crawled first."""
    hints = ("service", "about", "product", "pricing", "price", "contact", "team", "work", "portfolio", "menu", "solution", "industr", "faq", "gallery", "book", "quote", "location")
    scored = []
    for l in home["links"]:
        p = urlparse(l["url"]).path.lower()
        if not p or p == "/" or SKIP_PATH.search(p):
            continue
        depth = len([x for x in p.split("/") if x])
        score = (0 if any(h in p or h in l["label"].lower() for h in hints) else 1) + depth
        scored.append((score, l["url"]))
    out, seen = [], set()
    for _, u in sorted(scored, key=lambda x: x[0]):
        key = urlparse(u).path.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(u)
    return out


async def crawl_site(url: str, max_pages: int = MAX_PAGES, on: Optional[Callable] = None) -> dict:
    url = _norm_url(url)

    async def say(*a):
        if on:
            await on(*a)
    failures = []
    async with httpx.AsyncClient(follow_redirects=True, timeout=25.0, headers={"User-Agent": UA, "Accept-Language": "en"}) as client:
        await say("scanning", f"Opening {urlparse(url).netloc}")
        html, err = await _fetch(client, url)
        if not html:
            raise HTTPException(400, f"Could not load that website ({err or 'no response'}) — it may block bots or be offline")
        home = _parse_page(html, url)
        pages = [home]
        seen = {urlparse(url).path.rstrip("/").lower() or "/"}
        queue = [(u, 1) for u in _rank_links(home, url)]
        while queue and len(pages) < max_pages:
            u, depth = queue.pop(0)
            key = urlparse(u).path.rstrip("/").lower() or "/"
            if key in seen or depth > MAX_DEPTH:
                continue
            seen.add(key)
            await say("reading", f"Crawling page {len(pages) + 1} — {urlparse(u).path or '/'}")
            sub_html, err = await _fetch(client, u)
            if not sub_html:
                failures.append({"item": u, "reason": f"page skipped ({err})"})
                continue
            pg = _parse_page(sub_html, u)
            pages.append(pg)
            if depth < MAX_DEPTH:
                for nxt in _rank_links(pg, u)[:10]:
                    if (urlparse(nxt).path.rstrip("/").lower() or "/") not in seen:
                        queue.append((nxt, depth + 1))
        css = home["inline_css"]
        for sheet in home["stylesheets"][:3]:
            try:
                r = await client.get(sheet)
                if r.status_code < 400:
                    css += "\n" + r.text[:400_000]
            except Exception:
                failures.append({"item": sheet, "reason": "stylesheet could not be read"})
    colors = _colors_from_css(css)
    if home.get("theme_color"):
        colors["button"] = [home["theme_color"].lower()] + colors["button"]
    brand = home["site_name"] or (home["title"] or "").split("|")[0].split("–")[0].split("-")[0].strip() or urlparse(url).netloc
    return {"url": url, "brand": brand[:80], "pages": pages, "nav": home["nav"], "colors": colors, "failures": failures}


async def save_images(db, app_id: str, urls: List[str], quota_mb: int, on: Optional[Callable] = None):
    """Download every image into the client's media library so nothing is hotlinked."""
    async def say(*a):
        if on:
            await on(*a)
    mapping, failures, saved = {}, [], 0
    urls = [u for u in dict.fromkeys(urls) if u][:MAX_IMAGES]
    if not urls:
        return mapping, saved, failures
    usage = await usage_for(db, app_id, quota_mb)
    budget = max(0, usage["quota_bytes"] - usage["used_bytes"])
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0, headers={"User-Agent": UA}) as client:
        for i, u in enumerate(urls):
            if i % 8 == 0:
                await say("media", f"Saving image {i + 1} of {len(urls)} to the media library")
            try:
                r = await client.get(u)
                ctype = (r.headers.get("content-type") or "").split(";")[0].lower()
                url_ext = (urlparse(u).path.rsplit(".", 1)[-1] or "").lower()
                if ctype in ("application/octet-stream", "binary/octet-stream", "") and url_ext in ("jpg", "jpeg", "png", "webp", "gif"):
                    ctype = f"image/{'jpeg' if url_ext in ('jpg', 'jpeg') else url_ext}"
                if r.status_code >= 400 or not ctype.startswith("image/"):
                    failures.append({"item": u, "reason": f"image not downloadable ({r.status_code}, {ctype or 'unknown type'})"})
                    continue
                data = r.content
                if len(data) < 900:
                    continue
                if len(data) > MAX_IMAGE_BYTES:
                    failures.append({"item": u, "reason": "image over 8 MB — add it manually"})
                    continue
                if len(data) > budget:
                    failures.append({"item": u, "reason": "client storage quota reached"})
                    break
                ext = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif", "image/svg+xml": "svg"}.get(ctype)
                if not ext or ext not in MIME:
                    failures.append({"item": u, "reason": f"unsupported image type ({ctype})"})
                    continue
                path = f"{APP_NAME}/library/{app_id}/{uuid.uuid4().hex}.{ext}"
                res = put_object(path, data, MIME[ext])
                await db.files.insert_one({
                    "file_id": uuid.uuid4().hex, "app_id": app_id, "storage_path": res["path"],
                    "original_filename": (urlparse(u).path.rsplit("/", 1)[-1] or f"image.{ext}")[:160],
                    "content_type": MIME[ext], "size": res.get("size", len(data)), "is_deleted": False,
                    "uploaded_by": "website import", "in_library": True, "private": False,
                    "source_url": u, "created_at": _now()})
                mapping[u] = f"/api/public/files/{res['path']}"
                budget -= len(data)
                saved += 1
            except Exception as e:
                failures.append({"item": u, "reason": f"download failed ({type(e).__name__})"})
    return mapping, saved, failures


async def _claude(system: str, prompt: str, session: str) -> str:
    chat = get_chat("anthropic", "claude-sonnet-5", system, session)
    reply = await chat.send_message(UserMessage(text=prompt))
    return reply if isinstance(reply, str) else str(reply)

GLOBAL_SYSTEM = (
    "You analyse a crawled website and define its global identity for a visual site builder. Return ONLY valid JSON (no markdown): "
    "{\"business\": {\"name\", \"email\", \"phone\", \"address\", \"industry\", \"tagline\"}, "
    "\"theme\": {mode, primary, secondary, bg, surface, fg, muted, border, font_heading, font_body, radius}, "
    "\"navbar\": {\"brand\", \"cta\", \"links\": [{\"label\", \"href\", \"children\": [{\"label\", \"href\"}]}]}, "
    "\"footer\": {\"brand\", \"tagline\", \"columns\": [{\"title\", \"links\": [string]}]}}. "
    "Use ONLY real scraped facts — never invent a different company. theme.primary/secondary must come from the scraped button and background colours "
    "(never pure black or white); bg/surface/fg/muted/border must be consistent with the site's real light or dark scheme (mode 'light' → bg #FFFFFF, "
    "surface #F8FAFC, fg #0F172A; mode 'dark' → dark bg and light fg). Keep the site's own navigation labels, order and dropdown children, and rewrite "
    "hrefs to the given client slugs. All hex values must be 6-digit."
)

PAGE_SYSTEM = (
    "You rebuild ONE crawled web page as premium editable blocks for a visual site builder. Return ONLY valid JSON (no markdown): "
    "{\"name\": \"<short page name>\", \"blocks\": [...]}. " + BLOCK_SCHEMA +
    " Rules: use ONLY the scraped text, services, prices, testimonials, FAQs, contact details and IMAGE URLS given (the image URLs are already local — "
    "reuse them verbatim, never invent or hotlink other images). Keep the page's real wording and button labels; tighten only what is bloated. "
    "Do NOT emit navbar or footer blocks — they are added globally. 5-11 blocks, ordered like the original page: lead with a hero (use variant 'cover' with "
    "the best image when one exists), then the real sections. If the page has FORMS, recreate each one as a 'form' block preserving every field label, type, "
    "placeholder, options and required flag exactly as scraped. If the page lists contact details, include a 'contact' block with the real email/phone/address. "
    "Omit block ids."
)


STRING_PROPS = ("cta", "cta2", "title", "subtitle", "heading", "subheading", "brand", "badge", "caption", "tagline",
                "submit_label", "success_message", "email", "phone", "address", "value", "label", "name", "role",
                "quote", "desc", "price", "period", "q", "a")


def _sanitize(node):
    """LLMs sometimes return {label, href} where a plain string belongs — flatten those."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k in STRING_PROPS and isinstance(v, dict):
                out[k] = str(v.get("label") or v.get("text") or v.get("title") or "")
            elif k in ("names", "images", "features") and isinstance(v, list):
                out[k] = [x if isinstance(x, str) else str((x or {}).get("label") or (x or {}).get("url") or (x or {}).get("title") or "") for x in v]
            else:
                out[k] = _sanitize(v)
        return out
    if isinstance(node, list):
        return [_sanitize(x) for x in node]
    return node


def _localize(imgs: List[dict], mapping: dict) -> List[dict]:
    return [{"url": mapping[i["url"]], "alt": i["alt"]} for i in imgs if i["url"] in mapping]


FORM_PAGE_RE = re.compile(r"contact|schedule|quote|book|appointment|estimate|enquir|inquir|request|get-started|signup|sign-up", re.I)
DEFAULT_FORM = {"heading": "Request a callback", "submit_label": "Send request", "fields": [
    {"name": "name", "label": "Full name", "type": "text", "placeholder": "Jane Doe", "required": True},
    {"name": "email", "label": "Email", "type": "email", "placeholder": "jane@company.com", "required": True},
    {"name": "phone", "label": "Phone", "type": "tel", "placeholder": "(555) 010-2030", "required": False},
    {"name": "message", "label": "How can we help?", "type": "textarea", "placeholder": "A few details…", "required": True}]}


async def _build_page(pg: dict, mapping: dict, brand: str, industry: str, sem: asyncio.Semaphore, on) -> dict:
    imgs = _localize(pg["images"], mapping)
    payload = {k: pg[k] for k in ("url", "slug", "title", "description", "h1", "h2", "h3", "paragraphs", "list_items", "buttons", "forms", "emails", "phones", "addresses")}
    payload["images"] = imgs[:14]
    payload["business"] = {"name": brand, "industry": industry}
    synth = False
    if not pg["forms"] and FORM_PAGE_RE.search(f"{pg['slug']} {pg.get('title') or ''}"):
        payload["forms"] = [DEFAULT_FORM]
        payload["form_note"] = "The original form on this page is JavaScript-rendered and could not be read; rebuild this standard form instead."
        synth = True
    async with sem:
        raw = await _claude(PAGE_SYSTEM, json.dumps(payload, default=str)[:24000], f"impg-{_uid('p')}")
    data = _parse_json(raw)
    blocks = _sanitize(data.get("blocks") or [])
    if not blocks:
        raise ValueError("no blocks returned")
    name = (data.get("name") or pg["slug"].strip("/").replace("-", " ").title() or "Home")[:40]
    return {"slug": pg["slug"], "name": name, "blocks": blocks, "forms": len(pg["forms"]), "synth_form": synth}


async def build_import(url: str, on: Optional[Callable] = None, db=None, app_id: Optional[str] = None,
                       quota_mb: int = 500, max_pages: int = MAX_PAGES, crawl: Optional[dict] = None,
                       keep_slugs: Optional[List[str]] = None, pre_mapping: Optional[dict] = None) -> dict:
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "LLM key missing")

    async def say(*a):
        if on:
            await on(*a)
    crawl = crawl or await crawl_site(url, max_pages, on)
    failures = list(crawl["failures"])
    all_pages = crawl["pages"]
    if keep_slugs:
        wanted = set(keep_slugs)
        chosen = [p for p in all_pages if p["slug"] in wanted] or all_pages[:1]
    else:
        chosen = all_pages
    home = all_pages[0]

    mapping, saved_imgs = dict(pre_mapping or {}), 0
    if db is not None and app_id:
        all_imgs = [i["url"] for pg in chosen for i in pg["images"] if i["url"] not in mapping]
        for pg in chosen + [home]:
            if pg.get("logo") and pg["logo"] not in mapping:
                all_imgs.insert(0, pg["logo"])
        fetched, saved_imgs, img_fail = await save_images(db, app_id, all_imgs, quota_mb, on)
        mapping.update(fetched)
        failures += img_fail

    await say("rebuilding", f"Rebuilding {crawl['brand']} — global brand, colours and navigation")
    g_payload = {"url": crawl["url"], "brand": crawl["brand"], "colors": crawl["colors"], "nav": crawl["nav"],
                 "slugs": [p["slug"] for p in chosen],
                 "home": {k: home[k] for k in ("title", "description", "h1", "h2", "paragraphs", "emails", "phones", "addresses", "text")}}
    try:
        gdata = _parse_json(await _claude(GLOBAL_SYSTEM, json.dumps(g_payload, default=str)[:24000], f"imgl-{_uid('g')}"))
    except Exception as e:
        logger.exception("global import step failed")
        raise HTTPException(500, f"Could not analyse that website: {str(e)[:150]}")
    biz = gdata.get("business") or {"name": crawl["brand"]}
    theme = {**DEFAULT_THEME, **_clean_theme(gdata.get("theme") or {})}
    nav = gdata.get("navbar") or {"brand": crawl["brand"], "links": crawl["nav"]}
    footer = gdata.get("footer") or {"brand": crawl["brand"], "tagline": biz.get("tagline", ""), "columns": []}
    footer["columns"] = [{"title": str(c.get("title", ""))[:40],
                          "links": [l if isinstance(l, str) else str((l or {}).get("label", "")) for l in (c.get("links") or [])][:8]}
                         for c in (footer.get("columns") or []) if isinstance(c, dict)][:4]
    logo_src = next((p["logo"] for p in chosen + [home] if p.get("logo")), None)
    logo = mapping.get(logo_src)

    sem = asyncio.Semaphore(AI_CONCURRENCY)
    total = len(chosen)
    done = [0]

    async def one(pg):
        try:
            res = await _build_page(pg, mapping, biz.get("name") or crawl["brand"], biz.get("industry", ""), sem, on)
        except Exception as e:
            logger.warning("page rebuild failed %s: %s", pg["slug"], e)
            return {"slug": pg["slug"], "error": f"page could not be rebuilt ({type(e).__name__}) — add it manually"}
        done[0] += 1
        await say("rebuilding", f"Rebuilt {done[0]} of {total} pages — {res['name']}")
        return res
    results = await asyncio.gather(*[one(pg) for pg in chosen])

    embeds = list(dict.fromkeys([e for pg in chosen for e in (pg.get("embeds") or [])]))
    pages, forms_total, seen_slugs = [], 0, set()
    for pg, res in zip(chosen, results):
        if res.get("error"):
            failures.append({"item": pg["url"], "reason": res["error"]})
            continue
        if res.get("synth_form"):
            failures.append({"item": pg["url"], "reason": "form was JavaScript-rendered — a standard contact form was rebuilt; check the fields"})
        slug = res["slug"] if res["slug"] not in seen_slugs else f"{res['slug'].rstrip('/')}-{len(seen_slugs)}"
        seen_slugs.add(slug)
        nb = {"type": "navbar", "props": _sanitize({"brand": nav.get("brand") or crawl["brand"], "cta": nav.get("cta") or "Contact us",
                                                    "links": nav.get("links") or crawl["nav"], **({"logo": logo} if logo else {})}), "style": {}}
        ft = {"type": "footer", "props": _sanitize({**footer, **({"logo": logo} if logo else {})}), "style": {}}
        body_blocks = [b for b in res["blocks"] if b.get("type") not in ("navbar", "footer")]
        body_blocks = [b for b in body_blocks if b.get("type") != "video" or str((b.get("props") or {}).get("url") or "").strip()]
        page_embeds = pg.get("embeds") or []
        if page_embeds and not any(b.get("type") == "video" for b in body_blocks):
            body_blocks.insert(min(2, len(body_blocks)), {"type": "video", "props": {"heading": "Watch", "url": page_embeds[0], "caption": ""},
                                                          "style": {"bg": "muted", "align": "center", "padding": "md"}})
        blocks = _ensure_ids([nb] + body_blocks + [ft])
        forms_total += sum(1 for b in blocks if b.get("type") == "form")
        pages.append({"name": res["name"], "slug": slug, "blocks": blocks})
    if not pages:
        raise HTTPException(500, "Nothing usable could be rebuilt from that website")
    pages.sort(key=lambda p: (p["slug"] != "/", p["slug"]))

    report = {
        "crawled": len(all_pages), "pages_imported": len(pages), "images_saved": saved_imgs,
        "images_found": len({i["url"] for pg in chosen for i in pg["images"]}),
        "forms_detected": forms_total, "nav_items": len(nav.get("links") or []),
        "videos_embedded": sum(1 for p in pages for b in p["blocks"] if b.get("type") == "video"),
        "videos_found": len(embeds),
        "dropdowns": sum(1 for l in (nav.get("links") or []) if l.get("children")),
        "colors": crawl["colors"], "failures": failures[:40], "failed_count": len(failures),
    }
    return {"source": {"pages": len(all_pages), "images": report["images_found"], "emails": home["emails"],
                       "phones": home["phones"], "colors": crawl["colors"]["all"][:5],
                       "logo": logo, "title": home["title"], "description": home["description"]},
            "url": crawl["url"], "business": biz, "theme": theme, "logo": logo, "pages": pages, "report": report}


async def apply_import(db, app_id: str, imp: dict, mode: str, apply_theme: bool, log_activity, user_id: str) -> dict:
    biz = imp.get("business") or {}
    pages = imp["pages"]
    from content_lock import assert_unlocked, lock_after_build, sync_overview
    if mode == "replace":
        await assert_unlocked(db, app_id, "replace the saved pages")
        from page_guard import snapshot_site
        await snapshot_site(db, app_id, "website import", f"before import from {imp.get('url')}")
        await db.pages.delete_many({"app_id": app_id})
        start = 0
    else:
        start = await db.pages.count_documents({"app_id": app_id})
    created = []
    existing_slugs = {p["slug"] for p in await db.pages.find({"app_id": app_id}, {"_id": 0, "slug": 1}).to_list(80)}
    for i, pg in enumerate(pages):
        slug = pg["slug"]
        if slug in existing_slugs:
            slug = f"/imported-{re.sub(r'[^a-z0-9-]+', '-', pg['name'].lower()).strip('-') or f'page-{i + 1}'}"
        existing_slugs.add(slug)
        await db.pages.insert_one({"page_id": _uid("pg"), "app_id": app_id, "name": pg["name"], "slug": slug,
                                   "order": start + i, "blocks": pg["blocks"], "updated_at": _now()})
        created.append({"name": pg["name"], "slug": slug, "blocks": len(pg["blocks"]),
                        "forms": sum(1 for b in pg["blocks"] if b.get("type") == "form")})
    upd = {"updated_at": _now(), "imported_from": imp.get("url"), "premium_site_v": 3}
    prof = {k: v for k, v in {"email": biz.get("email"), "phone": biz.get("phone"), "address": biz.get("address")}.items() if v}
    if prof:
        upd["brand_profile"] = prof
    if apply_theme:
        upd["theme"] = imp["theme"]
    if imp.get("logo"):
        upd["logo"] = imp["logo"]
    hero_img = next((b["props"].get("image") for p in pages for b in p["blocks"] if b.get("type") == "hero" and b.get("props", {}).get("image")), None)
    if hero_img:
        upd["thumbnail"] = hero_img
    await db.apps.update_one({"app_id": app_id}, {"$set": upd})
    if not (await db.apps.find_one({"app_id": app_id}, {"_id": 0, "preview_token": 1}) or {}).get("preview_token"):
        await db.apps.update_one({"app_id": app_id}, {"$set": {"preview_token": _uid("pv"), "preview_enabled": True}})
    await log_activity(app_id, user_id, "site.imported", f"Imported {len(created)} page(s) from {imp.get('url')}")
    await lock_after_build(db, app_id)
    await sync_overview(db, app_id)
    return {"pages": created, "theme": imp["theme"] if apply_theme else None, "business": biz, "mode": mode,
            "report": imp.get("report")}


class DiscoverIn(BaseModel):
    url: str
    max_pages: int = MAX_PAGES


class SelectedIn(BaseModel):
    discovery_id: str
    slugs: List[str] = []
    mode: str = "replace"
    apply_theme: bool = True
    source_videos: bool = True


class UrlIn(BaseModel):
    url: str
    max_pages: int = 25


class ApplyIn(BaseModel):
    import_id: str
    mode: str = "replace"
    apply_theme: bool = True


class OneShotIn(BaseModel):
    url: str
    mode: str = "replace"
    apply_theme: bool = True
    max_pages: int = 25
    source_videos: bool = True


def _summary(import_id: str, imp: dict) -> dict:
    return {"import_id": import_id, "source": imp["source"], "business": imp["business"], "theme": imp["theme"],
            "report": imp["report"], "logo": imp.get("logo"),
            "pages": [{"name": p["name"], "slug": p["slug"], "blocks": len(p["blocks"]),
                       "forms": sum(1 for b in p["blocks"] if b.get("type") == "form"),
                       "images": sum(1 for b in p["blocks"] for v in (b.get("props") or {}).values() if isinstance(v, str) and "/api/public/files/" in v),
                       "types": [b.get("type") for b in p["blocks"]]} for p in imp["pages"]]}


def register(api, db, get_current_user, get_user_app, log_activity):
    async def _quota(app_doc: dict) -> int:
        return int(app_doc.get("storage_quota_mb") or os.environ.get("TENANT_STORAGE_QUOTA_MB", "500"))

    async def _run_job(job_id: str, app_id: str, url: str, user_id: str, auto: Optional[dict], max_pages: int, quota_mb: int,
                       crawl: Optional[dict] = None, keep_slugs: Optional[List[str]] = None):
        """Crawl + media + rebuild in the background — ingress caps requests at 60s, so the client polls."""
        async def say(stage: str, detail: str = ""):
            await db.import_jobs.update_one({"job_id": job_id}, {"$set": {"stage": stage, "stage_detail": detail, "stage_at": _now()}})
        try:
            imp = await build_import(url, say, db, app_id, quota_mb, max_pages, crawl, keep_slugs)
            import_id = _uid("imp")
            await db.site_imports.insert_one({"import_id": import_id, "app_id": app_id, "created_at": _now(), **imp})
            result = _summary(import_id, imp)
            if auto:
                await say("applying", f"Adding {len(imp['pages'])} page(s) to the project")
                result["applied"] = await apply_import(db, app_id, imp, auto["mode"], auto["apply_theme"], log_activity, user_id)
                if auto.get("source_videos") and search_stock and store_video and place_video:
                    await say("videos", "Sourcing free videos that match this business")
                    try:
                        result["videos"] = await _auto_videos(app_id, imp, quota_mb)
                    except Exception as e:
                        logger.warning("auto video sourcing skipped: %s", e)
                        result["videos"] = {"saved": 0, "reason": str(e)[:140]}
            await db.import_jobs.update_one({"job_id": job_id}, {"$set": {"status": "done", "stage": "done", "stage_detail": "", "result": result, "finished_at": _now()}})
        except HTTPException as e:
            await db.import_jobs.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e.detail), "finished_at": _now()}})
        except Exception as e:
            logger.exception("import job failed")
            await db.import_jobs.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e)[:180], "finished_at": _now()}})

    async def _auto_videos(app_id: str, imp: dict, quota_mb: int) -> dict:
        """After an import, pull 1-2 free niche-matched videos into the library and place one on the home page."""
        biz = imp.get("business") or {}
        query = " ".join(filter(None, [biz.get("industry"), (biz.get("name") or "").split()[0]]))[:60] or "business team"
        found = await search_stock(query, 6)
        saved = []
        for item in found[:2]:
            try:
                v = await store_video(db, app_id, item["download_url"], quota_mb, item.get("title") or query,
                                      {"kind": "video", "uploaded_by": f"{item['provider']} stock", "source_url": item.get("source_url"),
                                       "provider": item["provider"], "contributor": item.get("contributor"),
                                       "license_review_required": True, "search_query": query})
                saved.append(v)
            except Exception as e:
                logger.info("video skipped: %s", e)
        placed = None
        if saved:
            placed = await place_video(app_id, saved[0]["url"], f"{biz.get('name') or 'We'} in action",
                                       f"Video by {saved[0].get('contributor') or saved[0].get('provider')}")
        return {"saved": len(saved), "query": query, "placed": placed, "videos": saved}

    async def _start(app_id: str, url: str, user: dict, auto: Optional[dict], max_pages: int,
                     crawl: Optional[dict] = None, keep_slugs: Optional[List[str]] = None):
        app_doc = await require_ai_access(app_id, user)
        if auto and auto.get("mode") == "replace":
            from content_lock import assert_unlocked as _au
            await _au(db, app_id, "replace the saved pages")
        _norm_url(url)
        job_id = _uid("job")
        await db.import_jobs.insert_one({"job_id": job_id, "app_id": app_id, "url": url, "status": "running",
                                         "stage": "queued", "stage_detail": "Starting full-site crawl", "created_at": _now()})
        asyncio.create_task(_run_job(job_id, app_id, url, user["user_id"], auto, max(1, min(MAX_PAGES, max_pages)),
                                     await _quota(app_doc), crawl, keep_slugs))
        return {"job_id": job_id, "status": "running"}

    async def _run_discover(job_id: str, app_id: str, url: str, max_pages: int):
        async def say(stage: str, detail: str = ""):
            await db.import_jobs.update_one({"job_id": job_id}, {"$set": {"stage": stage, "stage_detail": detail, "stage_at": _now()}})
        try:
            crawl = await crawl_site(url, max_pages, say)
            discovery_id = _uid("disc")
            await db.site_discoveries.insert_one({"discovery_id": discovery_id, "app_id": app_id, "url": url,
                                                  "created_at": _now(), "crawl": crawl})
            pages = [{"slug": p["slug"], "url": p["url"], "title": (p.get("title") or p["slug"]).strip()[:90],
                      "words": len((p.get("text") or "").split()), "images": len(p["images"]), "forms": len(p["forms"]),
                      "videos": len(p.get("embeds") or []),
                      "important": p["slug"] == "/" or bool(IMPORTANT_RE.search(p["slug"]))} for p in crawl["pages"]]
            result = {"discovery_id": discovery_id, "brand": crawl["brand"], "url": crawl["url"], "pages": pages,
                      "colors": crawl["colors"]["all"][:6], "failures": crawl["failures"][:20],
                      "totals": {"pages": len(pages), "images": sum(p["images"] for p in pages),
                                 "forms": sum(p["forms"] for p in pages), "videos": sum(p["videos"] for p in pages),
                                 "important": sum(1 for p in pages if p["important"])}}
            await db.import_jobs.update_one({"job_id": job_id}, {"$set": {"status": "done", "stage": "done", "result": result, "finished_at": _now()}})
        except HTTPException as e:
            await db.import_jobs.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e.detail), "finished_at": _now()}})
        except Exception as e:
            logger.exception("discover failed")
            await db.import_jobs.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e)[:180], "finished_at": _now()}})

    @api.post("/apps/{app_id}/site/discover")
    async def discover(app_id: str, body: DiscoverIn, user: dict = Depends(get_current_user)):
        """Fast crawl with no AI and no downloads — lists every page found so the admin can pick."""
        await require_ai_access(app_id, user)
        _norm_url(body.url)
        job_id = _uid("job")
        await db.import_jobs.insert_one({"job_id": job_id, "app_id": app_id, "url": body.url, "status": "running",
                                         "kind": "discover", "stage": "queued", "stage_detail": "Discovering pages", "created_at": _now()})
        asyncio.create_task(_run_discover(job_id, app_id, body.url, max(1, min(MAX_PAGES, body.max_pages))))
        return {"job_id": job_id, "status": "running"}

    @api.post("/apps/{app_id}/site/import-selected")
    async def import_selected(app_id: str, body: SelectedIn, user: dict = Depends(get_current_user)):
        if body.mode != "append":
            from content_lock import assert_unlocked as _au
            await _au(db, app_id, "replace the saved pages")
        disc = await db.site_discoveries.find_one({"discovery_id": body.discovery_id, "app_id": app_id}, {"_id": 0})
        if not disc:
            raise HTTPException(404, "Discovery expired — scan the website again")
        if not body.slugs:
            raise HTTPException(400, "Pick at least one page to import")
        mode = body.mode if body.mode in ("replace", "append") else "replace"
        return await _start(app_id, disc["url"], user, {"mode": mode, "apply_theme": body.apply_theme, "source_videos": body.source_videos},
                            MAX_PAGES, disc["crawl"], body.slugs)

    @api.post("/apps/{app_id}/site/import-preview")
    async def import_preview(app_id: str, body: UrlIn, user: dict = Depends(get_current_user)):
        return await _start(app_id, body.url, user, None, body.max_pages)

    @api.get("/apps/{app_id}/site/import-job/{job_id}")
    async def import_job(app_id: str, job_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        job = await db.import_jobs.find_one({"job_id": job_id, "app_id": app_id}, {"_id": 0})
        if not job:
            raise HTTPException(404, "Import job not found")
        return job

    @api.post("/apps/{app_id}/site/import-apply")
    async def import_apply(app_id: str, body: ApplyIn, user: dict = Depends(get_current_user)):
        await require_ai_access(app_id, user)
        mode = body.mode if body.mode in ("replace", "append") else "replace"
        if mode == "replace":
            from content_lock import assert_unlocked as _au
            await _au(db, app_id, "replace the saved pages")
        imp = await db.site_imports.find_one({"import_id": body.import_id, "app_id": app_id}, {"_id": 0})
        if not imp:
            raise HTTPException(404, "Import not found — scan the website again")
        return await apply_import(db, app_id, imp, mode, body.apply_theme, log_activity, user["user_id"])

    @api.post("/apps/{app_id}/site/import")
    async def import_now(app_id: str, body: OneShotIn, user: dict = Depends(get_current_user)):
        mode = body.mode if body.mode in ("replace", "append") else "replace"
        return await _start(app_id, body.url, user, {"mode": mode, "apply_theme": body.apply_theme, "source_videos": body.source_videos}, body.max_pages)
