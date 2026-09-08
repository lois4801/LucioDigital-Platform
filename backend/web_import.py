"""Import any public website: scrape its content, brand and colours, then rebuild it as editable Site Mode pages."""
import os
import re
import json
import uuid
import asyncio
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Optional, List
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException, Depends
from pydantic import BaseModel

from emergentintegrations.llm.chat import LlmChat, UserMessage
from studio import _parse_json, _ensure_ids, _clean_theme, BLOCK_SCHEMA, DEFAULT_THEME

logger = logging.getLogger(__name__)
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
require_ai_access = None

UA = "Mozilla/5.0 (compatible; OmniStackImporter/1.0; +https://omnistack.ai)"
MAX_BYTES = 1_500_000
EXTRA_HINTS = ("about", "service", "product", "pricing", "price", "contact", "team", "work", "portfolio", "menu")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,2}[\s.-])?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}")
HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}\b")
SKIP_HEX = {"#fff", "#ffffff", "#000", "#000000", "#fefefe", "#f9f9f9"}


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


async def _fetch(client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        r = await client.get(url)
        if r.status_code >= 400 or "html" not in r.headers.get("content-type", "text/html"):
            return None
        return r.text[:MAX_BYTES]
    except Exception:
        return None


def _text_of(soup: BeautifulSoup, sel: str, limit: int, cap: int = 220) -> List[str]:
    out, seen = [], set()
    for el in soup.select(sel):
        t = " ".join(el.get_text(" ", strip=True).split())[:cap]
        if len(t) > 2 and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
        if len(out) >= limit:
            break
    return out


def _parse_page(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    for bad in soup(["script", "style", "noscript"]):
        bad.decompose()
    meta = lambda n, a="name": (soup.find("meta", attrs={a: n}) or {}).get("content") if soup.find("meta", attrs={a: n}) else None
    images, seen = [], set()
    for im in soup.find_all("img"):
        src = im.get("src") or im.get("data-src") or ""
        if not src or src.startswith("data:"):
            continue
        full = urljoin(url, src)
        if full in seen or full.lower().endswith(".svg"):
            continue
        seen.add(full)
        images.append({"url": full, "alt": (im.get("alt") or "")[:120]})
        if len(images) >= 24:
            break
    logo = None
    for im in soup.find_all("img")[:20]:
        hay = f"{im.get('class','')} {im.get('id','')} {im.get('alt','')} {im.get('src','')}".lower()
        if "logo" in hay and im.get("src") and not im["src"].startswith("data:"):
            logo = urljoin(url, im["src"])
            break
    links, lseen = [], set()
    host = urlparse(url).netloc
    for a in soup.find_all("a", href=True):
        full = urljoin(url, a["href"]).split("#")[0]
        if urlparse(full).netloc != host or full in lseen:
            continue
        lseen.add(full)
        label = " ".join(a.get_text(" ", strip=True).split())[:40]
        if label:
            links.append({"label": label, "url": full})
    body = " ".join(soup.get_text(" ", strip=True).split())
    hexes = [h.lower() for h in HEX_RE.findall(html) if h.lower() not in SKIP_HEX]
    return {
        "url": url,
        "title": (soup.title.string.strip() if soup.title and soup.title.string else None),
        "description": meta("description") or meta("og:description", "property"),
        "site_name": meta("og:site_name", "property"),
        "og_image": meta("og:image", "property"),
        "theme_color": meta("theme-color"),
        "logo": logo,
        "h1": _text_of(soup, "h1", 4),
        "h2": _text_of(soup, "h2", 14),
        "h3": _text_of(soup, "h3", 20),
        "paragraphs": _text_of(soup, "p", 40, 400),
        "list_items": _text_of(soup, "li", 40, 160),
        "images": images,
        "links": links[:40],
        "emails": list(dict.fromkeys(EMAIL_RE.findall(body)))[:4],
        "phones": list(dict.fromkeys(PHONE_RE.findall(body)))[:4],
        "colors": [c for c, _ in Counter(hexes).most_common(8)],
        "text": body[:6000],
    }


async def scrape_site(url: str, on: Optional[callable] = None) -> dict:
    url = _norm_url(url)

    async def say(*a):
        if on:
            await on(*a)
    async with httpx.AsyncClient(follow_redirects=True, timeout=25.0, headers={"User-Agent": UA, "Accept-Language": "en"}) as client:
        await say("scanning", f"Opening {urlparse(url).netloc}")
        html = await _fetch(client, url)
        if not html:
            raise HTTPException(400, "Could not load that website (it may block bots or be offline)")
        home = _parse_page(html, url)
        picked, subs = [], []
        for l in home["links"]:
            path = urlparse(l["url"]).path.lower().strip("/")
            if path and any(h in path or h in l["label"].lower() for h in EXTRA_HINTS) and l["url"] != url:
                if path not in [urlparse(p).path.lower().strip("/") for p in picked]:
                    picked.append(l["url"])
            if len(picked) >= 4:
                break
        for i, u in enumerate(picked):
            await say("reading", f"Reading page {i + 2} of {len(picked) + 1} — {urlparse(u).path}")
            sub_html = await _fetch(client, u)
            if sub_html:
                subs.append(_parse_page(sub_html, u))
    brand = home["site_name"] or (home["title"] or "").split("|")[0].split("–")[0].split("-")[0].strip() or urlparse(url).netloc
    return {
        "url": url, "brand": brand[:80], "home": home, "subpages": subs,
        "found": {"pages": 1 + len(subs), "images": len(home["images"]) + sum(len(s["images"]) for s in subs),
                  "emails": home["emails"], "phones": home["phones"], "colors": ([home["theme_color"]] if home["theme_color"] else []) + home["colors"][:4],
                  "logo": home["logo"] or home["og_image"], "title": home["title"], "description": home["description"]},
    }


async def _claude(system: str, prompt: str, session: str) -> str:
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=session, system_message=system).with_model("anthropic", "claude-sonnet-5")
    reply = await chat.send_message(UserMessage(text=prompt))
    return reply if isinstance(reply, str) else str(reply)


SYSTEM = (
    "You rebuild a scraped website as a premium, editable page structure for a visual site builder. Return ONLY valid JSON (no markdown): "
    "{\"business\": {\"name\", \"email\", \"phone\", \"address\", \"industry\"}, \"theme\": {mode, primary, secondary, bg, surface, border, font_heading, font_body, radius}, "
    "\"pages\": [{\"name\", \"slug\", \"blocks\": [...]}]}. " + BLOCK_SCHEMA +
    " Rules: use ONLY facts, names, services, prices, testimonials and contact details found in the scraped data — never invent a different company. "
    "Keep the original wording where it is good, tighten it where it is bloated. Reuse the scraped image URLs exactly as given (they are absolute). "
    "Build 3-5 pages: Home (slug '/', navbar first, 8-12 blocks including a hero with variant 'cover' using the best scraped image, then the site's real "
    "services/features, stats or credentials, testimonials if any, pricing if any, FAQ if any, a cta and a footer) plus About / Services / Contact when the "
    "scraped content supports them. Navbar links must point at the slugs you create. theme.primary and secondary must come from the scraped colours (pick the "
    "two strongest brand colours, not black or white); mode 'dark' unless the scraped colours are clearly light — then use 'light' with bg #FFFFFF and "
    "surface #F8FAFC. Omit block ids."
)


async def build_import(url: str, on: Optional[callable] = None) -> dict:
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "LLM key missing")

    async def say(*a):
        if on:
            await on(*a)
    src = await scrape_site(url, on)
    payload = {"url": src["url"], "brand": src["brand"], "home": src["home"], "subpages": src["subpages"]}
    await say("rebuilding", f"Rebuilding {src['brand']} as editable pages")
    try:
        data = _parse_json(await _claude(SYSTEM, json.dumps(payload, default=str)[:38000], f"import-{_uid('i')}"))
    except Exception as e:
        logger.exception("website import failed")
        raise HTTPException(500, f"Could not rebuild that site: {str(e)[:160]}")
    pages = data.get("pages") or []
    if not pages:
        raise HTTPException(500, "Nothing usable was found on that website")
    theme = {**DEFAULT_THEME, **_clean_theme(data.get("theme") or {})}
    out = []
    for i, pg in enumerate(pages):
        slug = "/" if i == 0 else "/" + re.sub(r"[^a-z0-9-]+", "-", str(pg.get("slug") or pg.get("name") or f"page-{i}").lower().strip("/ ")).strip("-")
        out.append({"name": pg.get("name") or slug.strip("/").title() or "Home", "slug": slug, "blocks": _ensure_ids(pg.get("blocks") or [])})
    return {"source": src["found"], "url": src["url"], "business": data.get("business") or {"name": src["brand"]}, "theme": theme, "pages": out}


async def apply_import(db, app_id: str, imp: dict, mode: str, apply_theme: bool, log_activity, user_id: str) -> dict:
    biz = imp.get("business") or {}
    pages = imp["pages"]
    if mode == "replace":
        await db.pages.delete_many({"app_id": app_id})
        start = 0
    else:
        start = await db.pages.count_documents({"app_id": app_id})
    created = []
    existing_slugs = {p["slug"] for p in await db.pages.find({"app_id": app_id}, {"_id": 0, "slug": 1}).to_list(60)}
    for i, pg in enumerate(pages):
        slug = pg["slug"]
        if slug in existing_slugs or (mode != "replace" and slug == "/"):
            slug = f"/imported-{re.sub(r'[^a-z0-9-]+', '-', pg['name'].lower()).strip('-') or i}"
        existing_slugs.add(slug)
        doc = {"page_id": _uid("pg"), "app_id": app_id, "name": pg["name"], "slug": slug, "order": start + i,
               "blocks": pg["blocks"], "updated_at": _now()}
        await db.pages.insert_one(dict(doc))
        created.append({"name": doc["name"], "slug": slug, "blocks": len(doc["blocks"])})
    upd = {"updated_at": _now(), "imported_from": imp.get("url")}
    prof = {k: v for k, v in {"email": biz.get("email"), "phone": biz.get("phone"), "address": biz.get("address")}.items() if v}
    if prof:
        upd["brand_profile"] = prof
    if apply_theme:
        upd["theme"] = imp["theme"]
    hero_img = next((b["props"].get("image") for p in pages for b in p["blocks"] if b.get("type") == "hero" and b.get("props", {}).get("image")), None)
    if hero_img:
        upd["thumbnail"] = hero_img
    await db.apps.update_one({"app_id": app_id}, {"$set": upd})
    await log_activity(app_id, user_id, "site.imported", f"Imported {len(created)} page(s) from {imp.get('url')}")
    return {"pages": created, "theme": imp["theme"] if apply_theme else None, "business": biz, "mode": mode}


class UrlIn(BaseModel):
    url: str


class ApplyIn(BaseModel):
    import_id: str
    mode: str = "replace"
    apply_theme: bool = True


class OneShotIn(BaseModel):
    url: str
    mode: str = "replace"
    apply_theme: bool = True


def _summary(import_id: str, imp: dict) -> dict:
    return {"import_id": import_id, "source": imp["source"], "business": imp["business"], "theme": imp["theme"],
            "pages": [{"name": p["name"], "slug": p["slug"], "blocks": len(p["blocks"]), "types": [b.get("type") for b in p["blocks"]]} for p in imp["pages"]]}


def register(api, db, get_current_user, get_user_app, log_activity):
    async def _run_job(job_id: str, app_id: str, url: str, user_id: str, auto: Optional[dict]):
        """Scrape + rebuild in the background — ingress caps requests at 60s, so the client polls."""
        async def say(stage: str, detail: str = ""):
            await db.import_jobs.update_one({"job_id": job_id}, {"$set": {"stage": stage, "stage_detail": detail, "stage_at": _now()}})
        try:
            imp = await build_import(url, say)
            import_id = _uid("imp")
            await db.site_imports.insert_one({"import_id": import_id, "app_id": app_id, "created_at": _now(), **imp})
            result = _summary(import_id, imp)
            if auto:
                await say("applying", f"Adding {len(imp['pages'])} page(s) to the project")
                result["applied"] = await apply_import(db, app_id, imp, auto["mode"], auto["apply_theme"], log_activity, user_id)
            await db.import_jobs.update_one({"job_id": job_id}, {"$set": {"status": "done", "stage": "done", "stage_detail": "", "result": result, "finished_at": _now()}})
        except HTTPException as e:
            await db.import_jobs.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e.detail), "finished_at": _now()}})
        except Exception as e:
            logger.exception("import job failed")
            await db.import_jobs.update_one({"job_id": job_id}, {"$set": {"status": "error", "error": str(e)[:180], "finished_at": _now()}})

    async def _start(app_id: str, url: str, user: dict, auto: Optional[dict]):
        await require_ai_access(app_id, user)
        _norm_url(url)
        job_id = _uid("job")
        await db.import_jobs.insert_one({"job_id": job_id, "app_id": app_id, "url": url, "status": "running",
                                         "stage": "queued", "stage_detail": "Starting import", "created_at": _now()})
        asyncio.create_task(_run_job(job_id, app_id, url, user["user_id"], auto))
        return {"job_id": job_id, "status": "running"}

    @api.post("/apps/{app_id}/site/import-preview")
    async def import_preview(app_id: str, body: UrlIn, user: dict = Depends(get_current_user)):
        return await _start(app_id, body.url, user, None)

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
        imp = await db.site_imports.find_one({"import_id": body.import_id, "app_id": app_id}, {"_id": 0})
        if not imp:
            raise HTTPException(404, "Import not found — scan the website again")
        mode = body.mode if body.mode in ("replace", "append") else "replace"
        return await apply_import(db, app_id, imp, mode, body.apply_theme, log_activity, user["user_id"])

    @api.post("/apps/{app_id}/site/import")
    async def import_now(app_id: str, body: OneShotIn, user: dict = Depends(get_current_user)):
        mode = body.mode if body.mode in ("replace", "append") else "replace"
        return await _start(app_id, body.url, user, {"mode": mode, "apply_theme": body.apply_theme})
