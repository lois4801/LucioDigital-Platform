"""Marquee text ribbon: an outline-text ribbon per template, editable per client."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

# key -> (top ribbon phrase, bottom ribbon phrase). Brand names come from the niche copy.
PHRASES: Dict[str, tuple] = {
    "hvac": ("SUMMIT AIR & HEAT · COMFORT ON CALL", "SAME-DAY SERVICE · HONEST QUOTES"),
    "healthcare": ("NORTHGATE FAMILY MEDICINE · CARE YOU CAN COUNT ON", "SHORTER WAITS · BETTER OUTCOMES"),
    "construction": ("WE BUILD THE STRUCTURES CITIES RUN ON", "ON TIME · ON BUDGET · ON SITE"),
    "fitness": ("FORGE ATHLETIC CLUB · TRAIN LIKE IT MATTERS", "STRONGER EVERY SESSION"),
    "retail": ("MADE TO BE USED, NOT STORED", "FAST SHIPPING · EASY RETURNS"),
    "hospitality": ("STAY LONGER · SLEEP BETTER", "QUIET LUXURY · WARM WELCOME"),
    "finance": ("PATIENT CAPITAL · CLEAR ADVICE", "PLAN · PROTECT · GROW"),
    "it_services": ("UPTIME IS THE WHOLE JOB", "MONITORED · PATCHED · SECURED"),
    "creative_studio": ("BRANDS THAT REFUSE TO BLEND IN", "STRATEGY · DESIGN · MOTION"),
    "logistics": ("FREIGHT THAT ARRIVES WHEN WE SAY", "TRACKED · SEALED · ON TIME"),
    "saas": ("ORBIT CUSTOMER SUCCESS · RETENTION BY DESIGN", "ONBOARD · ADOPT · RENEW"),
    "legal": ("PRECISION · INTEGRITY · RESULTS", "COUNSEL YOU CAN ACT ON"),
    "education": ("SMALL CLASSES · BIG FUTURES", "TAUGHT WELL · KNOWN BY NAME"),
    "real_estate": ("HARBOUR & VALE REALTY · PREMIUM PROPERTIES", "LISTED · SHOWN · SOLD"),
    "restaurant": ("EMBER & OAK · COOKED OVER FIRE", "SEASONAL · LOCAL · GENEROUS"),
    "events": ("LUMEN EVENTS CO · MOMENTS ENGINEERED", "PLANNED · PRODUCED · REMEMBERED"),
    "veterinary": ("GENTLE HANDS · STEADY CARE", "SAME-DAY APPOINTMENTS · CALM CLINIC"),
    "dental": ("SMILES BUILT TO LAST", "COMFORTABLE · UNHURRIED · PRECISE"),
    "accounting": ("BOOKS CLEAN · DEADLINES MET", "FILED EARLY · ADVISED PROPERLY"),
    "landscaping": ("GARDENS THAT GROW INTO THEMSELVES", "PLANTED · PRUNED · MAINTAINED"),
    "photography": ("LIGHT, CAUGHT PROPERLY", "SHOT WELL · DELIVERED FAST"),
    "automotive": ("FIXED RIGHT THE FIRST TIME", "DIAGNOSED · REPAIRED · GUARANTEED"),
    "beauty": ("COLOUR WITH INTENT", "CONSULTED · CUT · CARED FOR"),
    "insurance": ("COVER THAT ACTUALLY PAYS OUT", "REVIEWED · CLAIMED · SETTLED"),
    "pet_grooming": ("HAPPY PETS, HONEST GROOMING", "GENTLE · PATIENT · SPOTLESS"),
    "hvac_plumbing": ("LEAKS, BOILERS, EMERGENCIES · SAME DAY", "TIDY WORK · FAIR PRICES"),
    "coworking": ("DESKS FOR PEOPLE WHO SHIP", "FLEXIBLE TERMS · REAL COMMUNITY"),
    "wellness": ("MAISON VERDE · REST IS PRODUCTIVE", "BREATHE · MOVE · RECOVER"),
    "cleaning": ("SPOTLESS, EVERY SINGLE VISIT", "VETTED TEAMS · AFTER HOURS"),
    "music_school": ("PRACTICE MADE PLEASURABLE", "TAUGHT · PERFORMED · PASSED"),
    "nonprofit": ("EVERY POUND DOES THE WORK", "FUNDED · DELIVERED · REPORTED"),
    "architecture": ("BUILDINGS THAT EARN THEIR PLACE", "DESIGNED · APPROVED · BUILT"),
    "test_template": ("LUCIODIGITAL TEST LAB · MASTER WORKSPACE", "BUILD · PROPAGATE · SHIP"),
    "luciodigital": ("LUCIODIGITAL · SHIP · SHOWCASE · HAND OFF",
                     "EVERY CLIENT APP · FROM ONE MASTER WORKSPACE"),
}
FALLBACK = ("BUILT PROPERLY · DELIVERED ON TIME", "TRUSTED BY THE PEOPLE WE WORK FOR")

DEFAULTS = {"speed": 1.0, "stroke_opacity": 0.3, "font_size": 1.0, "enabled": True,
            "top_source": "static", "bottom_source": "static",
            "top_figure": 0, "bottom_figure": 1,
            "offer_text": "", "offer_from": "", "offer_to": ""}

SOURCES = ("static", "review", "offer", "figure")


def _offer_live(mq: Dict[str, Any]) -> str:
    """The offer line, only while it is inside its optional date window."""
    text = (mq.get("offer_text") or "").strip()
    if not text:
        return ""
    today = datetime.now(timezone.utc).date().isoformat()
    if (mq.get("offer_from") or "") > today or ((mq.get("offer_to") or "") and mq["offer_to"] < today):
        return ""
    return text


def live_ctx(reviews: Any = None, vitals: Any = None) -> Dict[str, Any]:
    """The live values a ribbon can pull from: newest review and the client's own figures."""
    rows = (reviews or {}).get("reviews") or []
    first = rows[0] if rows else {}
    return {"review_quote": (first.get("quote") or "").strip(), "review_name": (first.get("name") or "").strip(),
            "metrics": (vitals or {}).get("metrics") or []}


def apply_live(mq: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Replace each ribbon's text with its live source, falling back to the static wording."""
    out = dict(mq)
    for pos in ("top", "bottom"):
        src = out.get(f"{pos}_source") or "static"
        line = ""
        if src == "review" and ctx.get("review_quote"):
            quote = ctx["review_quote"].rstrip(" .")
            line = f"“{quote}”" + (f" — {ctx['review_name']}" if ctx.get("review_name") else "")
        elif src == "offer":
            line = _offer_live(out)
        elif src == "figure":
            m = (ctx.get("metrics") or [])
            i = int(out.get(f"{pos}_figure") or 0)
            if 0 <= i < len(m):
                row = m[i]
                line = f"{row.get('prefix') or ''}{row.get('value')}{row.get('suffix') or ''} {row.get('label') or ''}".strip()
        out[f"{pos}_live"] = src if line else "static"
        if line:
            out[f"{pos}_text"] = line.upper() if src == "figure" else line
    return out



def spec_for(key: str, brand: str = "") -> Dict[str, Any]:
    top, bottom = PHRASES.get(key, FALLBACK)
    if key not in PHRASES and brand:
        top = f"{brand.upper()} · {FALLBACK[0]}"
    return {**DEFAULTS, "top_text": top, "bottom_text": bottom}


def resolve_for_page(marquee: Dict[str, Any], slug: str) -> Dict[str, Any]:
    """Site-wide ribbon with that page's own overrides on top. Blank fields inherit."""
    over = ((marquee or {}).get("pages") or {}).get(slug or "/") or {}
    out = {k: v for k, v in (marquee or {}).items() if k != "pages"}
    for k, v in over.items():
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        out[k] = v
    return out


def register(api, db, get_current_user, get_user_app, log_activity):

    class MarqueeIn(BaseModel):
        top_text: Optional[str] = None
        bottom_text: Optional[str] = None
        speed: Optional[float] = None
        stroke_opacity: Optional[float] = None
        font_size: Optional[float] = None
        enabled: Optional[bool] = None
        top_source: Optional[str] = None
        bottom_source: Optional[str] = None
        top_figure: Optional[int] = None
        bottom_figure: Optional[int] = None
        offer_text: Optional[str] = None
        offer_from: Optional[str] = None
        offer_to: Optional[str] = None

    class PageMarqueeIn(BaseModel):
        top_text: Optional[str] = None
        bottom_text: Optional[str] = None
        speed: Optional[float] = None
        stroke_opacity: Optional[float] = None
        font_size: Optional[float] = None
        enabled: Optional[bool] = None
        top_source: Optional[str] = None
        bottom_source: Optional[str] = None
        top_figure: Optional[int] = None
        bottom_figure: Optional[int] = None

    def _resolved(app: dict) -> Dict[str, Any]:
        key = (app.get("motion_profile") or {}).get("template_key") or app.get("site_niche") or ""
        own = dict(app.get("marquee") or {})
        pages = own.pop("pages", {}) or {}
        return {**spec_for(key, app.get("name") or ""), **own, "pages": pages}

    def _check_ranges(patch: dict):
        if patch.get("speed") is not None and not 0.2 <= patch["speed"] <= 3.0:
            raise HTTPException(400, "Scroll speed must be between 0.2x and 3x")
        if patch.get("stroke_opacity") is not None and not 0.05 <= patch["stroke_opacity"] <= 1.0:
            raise HTTPException(400, "Stroke opacity must be between 0.05 and 1")
        if patch.get("font_size") is not None and not 0.5 <= patch["font_size"] <= 2.5:
            raise HTTPException(400, "Font size must be between 0.5x and 2.5x")
        for pos in ("top_source", "bottom_source"):
            if patch.get(pos) is not None and patch[pos] not in SOURCES:
                raise HTTPException(400, f"Unknown ribbon source. Use one of: {', '.join(SOURCES)}")

    @api.get("/public/marquee/{key}")
    async def public_marquee(key: str):
        return spec_for(key)

    @api.get("/apps/{app_id}/marquee")
    async def get_marquee(app_id: str, user: dict = Depends(get_current_user)):
        app = await get_user_app(app_id, user)
        rows = await db.pages.find({"app_id": app_id}, {"_id": 0, "slug": 1, "name": 1, "order": 1}).to_list(200)
        rows.sort(key=lambda p: (p.get("slug") != "/", p.get("order", 0)))
        key = (app.get("motion_profile") or {}).get("template_key") or app.get("site_niche") or ""
        from industry_vitals import spec_for as _vspec
        vitals = {**_vspec(key, app.get("industry") or ""), **(app.get("vitals") or {})}
        from reviews import DEFAULT_STYLE  # noqa: F401  (kept for parity with the reviews payload)
        rev = app.get("reviews") or {}
        if not rev.get("reviews"):
            doc = await db.template_reviews.find_one({"key": key}, {"_id": 0})
            rev = {"reviews": (doc or {}).get("reviews") or []}
        base = _resolved(app)
        ctx = live_ctx(rev, vitals)
        return {**base,
                "live": {k: v for k, v in apply_live({k: v for k, v in base.items() if k != "pages"}, ctx).items()
                         if k in ("top_text", "bottom_text", "top_live", "bottom_live")},
                "figures": [{"index": i, "label": m.get("label") or f"Figure {i + 1}",
                             "value": f"{m.get('prefix') or ''}{m.get('value')}{m.get('suffix') or ''}"}
                            for i, m in enumerate(vitals.get("metrics") or [])],
                "pages_list": [{"slug": p.get("slug") or "/", "name": p.get("name") or p.get("slug")} for p in rows]}

    @api.put("/apps/{app_id}/marquee")
    async def put_marquee(app_id: str, body: MarqueeIn, user: dict = Depends(get_current_user)):
        app = await get_user_app(app_id, user)
        patch = {k: v for k, v in body.dict().items() if v is not None}
        _check_ranges(patch)
        for f in ("top_text", "bottom_text"):
            if f in patch:
                patch[f] = str(patch[f])[:160]
        cur = {**(app.get("marquee") or {}), **patch,
               "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.apps.update_one({"app_id": app_id}, {"$set": {"marquee": cur}})
        await log_activity(app_id, user["user_id"], "marquee.save", "Updated the text ribbon")
        return _resolved({**app, "marquee": cur})

    @api.put("/apps/{app_id}/marquee/pages/{slug:path}")
    async def put_page_marquee(app_id: str, slug: str, body: PageMarqueeIn, user: dict = Depends(get_current_user)):
        app = await get_user_app(app_id, user)
        slug = "/" + slug.strip("/") if slug.strip("/") else "/"
        patch = body.dict(exclude_unset=True)
        _check_ranges({k: v for k, v in patch.items() if v is not None})
        cur = dict(app.get("marquee") or {})
        pages = dict(cur.get("pages") or {})
        row = dict(pages.get(slug) or {})
        for k, v in patch.items():
            if v is None or (isinstance(v, str) and not v.strip()):
                row.pop(k, None)                      # blank means "inherit the site-wide ribbon"
            else:
                row[k] = str(v)[:160] if isinstance(v, str) else v
        if row:
            pages[slug] = row
        else:
            pages.pop(slug, None)
        cur["pages"] = pages
        cur["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.apps.update_one({"app_id": app_id}, {"$set": {"marquee": cur}})
        await log_activity(app_id, user["user_id"], "marquee.page", f"Updated the {slug} page ribbon")
        return _resolved({**app, "marquee": cur})

    @api.delete("/apps/{app_id}/marquee/pages/{slug:path}")
    async def clear_page_marquee(app_id: str, slug: str, user: dict = Depends(get_current_user)):
        app = await get_user_app(app_id, user)
        slug = "/" + slug.strip("/") if slug.strip("/") else "/"
        cur = dict(app.get("marquee") or {})
        pages = dict(cur.get("pages") or {})
        pages.pop(slug, None)
        cur["pages"] = pages
        await db.apps.update_one({"app_id": app_id}, {"$set": {"marquee": cur}})
        await log_activity(app_id, user["user_id"], "marquee.page", f"Reset the {slug} page ribbon")
        return _resolved({**app, "marquee": cur})


    @api.post("/apps/{app_id}/marquee/reset")
    async def reset_marquee(app_id: str, user: dict = Depends(get_current_user)):
        app = await get_user_app(app_id, user)
        await db.apps.update_one({"app_id": app_id}, {"$unset": {"marquee": ""}})
        await log_activity(app_id, user["user_id"], "marquee.reset", "Restored the project ribbon")
        return _resolved({**app, "marquee": None})
