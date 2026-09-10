"""Reviews & testimonials: 20 AI-written, industry-specific 5-star reviews per template
(plus a LucioDigital agency set), editable per client, with a dynamic colour system."""
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

PORTRAITS = [
    "https://images.unsplash.com/photo-1764084052338-23a317e34ea1",
    "https://images.unsplash.com/photo-1763259405177-0121bf79da0d",
    "https://images.unsplash.com/photo-1758599543126-59e3154d7195",
    "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2",
    "https://images.unsplash.com/photo-1699899657680-421c2c2d5064",
    "https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e",
    "https://images.unsplash.com/photo-1494790108377-be9c29b29330",
    "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7",
    "https://images.unsplash.com/photo-1752650143077-8334ebff6393",
    "https://images.unsplash.com/photo-1781613602681-2820b74ca7bc",
    "https://images.unsplash.com/photo-1787647562292-cb5595159273",
    "https://images.unsplash.com/photo-1758691737605-69a0e78bd193",
    "https://images.unsplash.com/photo-1787647561687-fd0b69654aea",
    "https://images.unsplash.com/photo-1762793193633-c26f3d34e710",
    "https://images.unsplash.com/photo-1767396857436-0692218b0963",
    "https://images.unsplash.com/photo-1556793521-8ee923a8eef4",
    "https://images.unsplash.com/photo-1767396857504-99375ab21c1a",
    "https://images.unsplash.com/photo-1542458579-bc6f69b5ce6b",
    "https://images.unsplash.com/photo-1559638862-156d0b977e5e",
    "https://images.unsplash.com/photo-1748282664302-80a9d7e29f49",
    "https://images.unsplash.com/photo-1758336011136-343678e4fc05",
    "https://images.unsplash.com/photo-1615464670798-6e92fafa2a89",
    "https://images.unsplash.com/photo-1758599543125-0a927f1d7a3b",
    "https://images.unsplash.com/photo-1758599543114-4eaf17a9ef64",
    "https://images.unsplash.com/photo-1765648580528-8d659861d81a",
]
_Q = "?crop=faces&fit=crop&w=200&h=200&q=80&fm=jpg"
portrait = lambda i: f"{PORTRAITS[i % len(PORTRAITS)]}{_Q}"

# Worldwide reviewer locations — city, country, ISO code (drives the flag on each card).
LOCATIONS = [
    ("Toronto", "Canada", "ca"), ("Austin", "United States", "us"), ("Manchester", "United Kingdom", "gb"),
    ("Melbourne", "Australia", "au"), ("Auckland", "New Zealand", "nz"), ("Dublin", "Ireland", "ie"),
    ("Rotterdam", "Netherlands", "nl"), ("Munich", "Germany", "de"), ("Lyon", "France", "fr"),
    ("Milan", "Italy", "it"), ("Barcelona", "Spain", "es"), ("Lisbon", "Portugal", "pt"),
    ("Stockholm", "Sweden", "se"), ("Oslo", "Norway", "no"), ("Copenhagen", "Denmark", "dk"),
    ("Warsaw", "Poland", "pl"), ("Singapore", "Singapore", "sg"), ("Tokyo", "Japan", "jp"),
    ("Seoul", "South Korea", "kr"), ("Bengaluru", "India", "in"), ("Dubai", "United Arab Emirates", "ae"),
    ("Cape Town", "South Africa", "za"), ("Nairobi", "Kenya", "ke"), ("Lagos", "Nigeria", "ng"),
    ("São Paulo", "Brazil", "br"), ("Mexico City", "Mexico", "mx"), ("Santiago", "Chile", "cl"),
    ("Vancouver", "Canada", "ca"), ("Chicago", "United States", "us"), ("Edinburgh", "United Kingdom", "gb"),
]

# What each template's reviews must talk about, so no two industries read alike.
BRIEFS: Dict[str, str] = {
    "hvac": "residential and commercial heating, cooling and air quality — same-day callouts, first-visit fixes, energy bill savings, maintenance plans",
    "healthcare": "a medical clinic — patient outcomes, appointment booking, wait times, clinic efficiency, follow-up care",
    "construction": "a commercial construction firm — on-time delivery, budget accuracy, safety record, site communication, snag lists",
    "fitness": "a gym and training studio — training results, class bookings, member retention, coaching quality, habit change",
    "retail": "a retail and e-commerce brand — product quality, shipping speed, returns, repeat purchase, customer service",
    "hospitality": "a boutique hotel — guest experience, booking flow, housekeeping, dining, repeat stays",
    "finance": "a wealth management practice — portfolio returns, tax efficiency, planning clarity, reporting, adviser responsiveness",
    "it_services": "a managed IT and security provider — uptime, ticket response, onboarding, cyber-security posture, IT budgeting",
    "creative_studio": "a creative and brand studio — brand launches, design quality, campaign results, collaboration, delivery speed",
    "logistics": "a freight and logistics carrier — on-time delivery, damage rates, tracking visibility, cross-border clearance, cost per load",
    "saas": "a customer-success SaaS platform — net revenue retention, onboarding time, reporting, integrations, support quality",
    "legal": "a law firm — case outcomes, client communication, document handling, settlement speed, cost transparency",
    "education": "a private school — student outcomes, teaching quality, class sizes, university placement, parent communication",
    "real_estate": "a real estate brokerage — property listings, lead generation, days on market, negotiation, client closings",
    "restaurant": "a restaurant — food quality, service, reservations, private events, consistency",
    "events": "an events production company — event delivery, attendee experience, production quality, logistics, sponsor value",
    "veterinary": "a veterinary clinic — animal recovery, same-day appointments, surgery outcomes, compassionate staff, pet owner guidance",
    "dental": "a dental practice — treatment comfort, chair time, recall rates, cosmetic results, nervous-patient care",
    "accounting": "an accounting practice — filing accuracy, tax savings found, bookkeeping cleanliness, deadline reliability, advisory value",
    "landscaping": "a landscaping and grounds company — garden transformation, maintenance reliability, planting survival, crew tidiness, seasonal planning",
    "photography": "a photography studio — image quality, turnaround, direction on shoot day, print quality, event coverage",
    "automotive": "an auto service centre — first-time fix rate, turnaround, honest quoting, diagnostics, warranty work",
    "beauty": "a hair and beauty salon — colour results, rebooking, consultation quality, product advice, treatment comfort",
    "insurance": "an insurance brokerage — claim approvals, claim speed, cover advice, premium savings, renewal handling",
    "pet_grooming": "a pet grooming salon — grooming results, nervous-pet handling, coat health, appointment availability, pick-up experience",
    "hvac_plumbing": "a plumbing and heating callout service — same-day response, leak fixes, boiler installs, tidy work, emergency availability",
    "coworking": "a coworking space — desk availability, meeting rooms, community, internet reliability, flexible terms",
    "wellness": "a wellness and therapy studio — client wellbeing, treatment plans, therapist skill, booking ease, long-term results",
    "cleaning": "a commercial cleaning company — quality scores, reliability, staff vetting, contract flexibility, after-hours work",
    "music_school": "a music school — exam results, teaching quality, student confidence, recital experience, practice habits",
    "nonprofit": "a nonprofit — people supported, funds to programmes, volunteer experience, donor reporting, community impact",
    "architecture": "an architecture practice — planning approvals, design quality, budget control, contractor coordination, finished buildings",
    "test_template": "an internal design and QA sandbox — release confidence, regression catching, motion quality, build speed, handoff clarity",
    "luciodigital": "LucioDigital, a platform agencies and freelancers use to build and ship client websites — client management, template speed, motion design quality, client handoff, and business growth. Reviewers are agency owners, digital studio founders and freelance designers/developers",
}

SYSTEM = (
    "You write short, believable, specific 5-star customer reviews for business websites. "
    "Never use the words 'amazing', 'game-changer', 'seamless' or exclamation marks. "
    "Every quote names a concrete detail or number. Return STRICT JSON only, no prose, no code fences."
)

PROMPT = """Write exactly 20 five-star reviews for {brief}.

Return JSON: {{"reviews": [{{"name","title","company","company_desc","quote","tags","city","country","flag"}}]}}
- name: a real-sounding full name; vary gender and nationality across the 20.
- title: their job title.
- company: their company or, for consumer businesses, a short label like "Homeowner" or "Parent of two".
- company_desc: ONE short line (max 8 words) describing that company or person.
- city / country: where they are based — spread the 20 across different countries and continents.
- flag: the ISO 3166-1 alpha-2 country code in lowercase, matching `country` exactly (e.g. "ca", "ng", "jp").
- quote: 20-38 words, first person, specific, mentioning a concrete outcome or number. No two quotes may share a sentence structure.
- tags: exactly 2 short measurable outcome tags, each max 22 characters, like "38% faster turnaround" or "0 safety incidents".
All 20 must be distinct in name, company, quote and tags. JSON only."""


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def decorate(reviews: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    """Adds the stable parts every card needs: id, 5 stars, portrait, city and flag."""
    out = []
    for i, r in enumerate(reviews):
        city, country, iso = LOCATIONS[(i * 7 + len(key)) % len(LOCATIONS)]
        tags = [str(t)[:26] for t in (r.get("tags") or [])][:2]
        out.append({
            "id": r.get("id") or f"rv_{_slug(key)}_{i}",
            "name": r.get("name") or "Client",
            "title": r.get("title") or "",
            "company": r.get("company") or "",
            "company_desc": r.get("company_desc") or "",
            "quote": r.get("quote") or "",
            "tags": tags,
            "rating": 5,
            "photo": r.get("photo") or portrait(i * 3 + len(key)),
            "city": r.get("city") or city,
            "country": r.get("country") or country,
            "flag": r.get("flag") or iso,
        })
    return out


def fallback_set(key: str) -> List[Dict[str, Any]]:
    """Used until the AI set is generated, so a template is never empty."""
    brief = BRIEFS.get(key, "a professional service business")
    topic = brief.split("—")[-1].split(",")
    base = [
        ("Elena Marsh", "Operations Director", "Harbourline Group", "Multi-site operator",
         "They rebuilt our {a} inside a month and the difference showed in the first invoice. We have not had to chase anything since.",
         ["Set up in 4 weeks", "Zero chasing"]),
        ("Tomas Reiner", "Founder", "Reiner & Co.", "Independent practice",
         "What sold me was the detail on {b}. Every promise made in the first meeting was still true six months later.",
         ["6 months, no slips", "Fully as quoted"]),
        ("Priya Raman", "General Manager", "Northfield Partners", "Regional service group",
         "We compared three providers. Their handling of {a} was the only one that stood up under a busy week.",
         ["Best of 3 quotes", "Held under load"]),
    ]
    rows = []
    for i in range(20):
        n, t, c, d, q, tg = base[i % len(base)]
        a = (topic[i % len(topic)] or "the work").strip()
        b = (topic[(i + 1) % len(topic)] or "the detail").strip()
        rows.append({"name": f"{n.split()[0]} {chr(65 + i)}. {n.split()[-1]}", "title": t,
                     "company": f"{c} {i + 1}" if i >= len(base) else c, "company_desc": d,
                     "quote": q.format(a=a, b=b), "tags": tg})
    return decorate(rows, key)


DEFAULT_STYLE = {"accent": "", "card_bg": "", "title_color": "",
                 "title": "Reviews & testimonials",
                 "subtitle": "Real results, in our clients' own words."}


def register(api, db, get_current_user, get_user_app, log_activity):

    async def _ai_set(key: str) -> List[Dict[str, Any]]:
        from dotenv import load_dotenv
        load_dotenv()
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"reviews-{key}",
                       system_message=SYSTEM).with_model("anthropic", "claude-sonnet-4-6")
        raw = await chat.send_message(UserMessage(text=PROMPT.format(brief=BRIEFS.get(key, key))))
        txt = re.sub(r"^```(?:json)?|```$", "", str(raw).strip(), flags=re.M).strip()
        start, end = txt.find("{"), txt.rfind("}")
        data = json.loads(txt[start:end + 1])
        rows = data.get("reviews") or []
        if len(rows) < 10:
            raise ValueError(f"model returned {len(rows)} reviews")
        return decorate(rows[:20], key)

    async def stored_set(key: str) -> Dict[str, Any]:
        doc = await db.template_reviews.find_one({"key": key}, {"_id": 0})
        if doc and doc.get("reviews"):
            return {"reviews": doc["reviews"], "source": doc.get("source") or "ai"}
        return {"reviews": fallback_set(key), "source": "fallback"}

    async def generate_and_store(key: str) -> Dict[str, Any]:
        reviews = await _ai_set(key)
        await db.template_reviews.update_one(
            {"key": key},
            {"$set": {"key": key, "reviews": reviews, "source": "ai",
                      "generated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"key": key, "count": len(reviews)}

    api.state_reviews_stored = stored_set          # reused by studio + template gallery
    api.state_reviews_generate = generate_and_store

    class ReviewsIn(BaseModel):
        reviews: Optional[List[Dict[str, Any]]] = None
        style: Optional[Dict[str, str]] = None

    @api.get("/public/reviews/{key}")
    async def public_reviews(key: str):
        got = await stored_set(key)
        return {**got, "style": DEFAULT_STYLE}

    @api.get("/apps/{app_id}/reviews")
    async def get_reviews(app_id: str, user: dict = Depends(get_current_user)):
        app = await get_user_app(app_id, user)
        key = (app.get("motion_profile") or {}).get("template_key") or app.get("site_niche") or ""
        base = await stored_set(key)
        own = app.get("reviews") or {}
        return {"reviews": own.get("reviews") or base["reviews"],
                "style": {**DEFAULT_STYLE, **(own.get("style") or {})},
                "source": "custom" if own.get("reviews") else base["source"],
                "template_key": key}

    @api.put("/apps/{app_id}/reviews")
    async def put_reviews(app_id: str, body: ReviewsIn, user: dict = Depends(get_current_user)):
        app = await get_user_app(app_id, user)
        cur = dict(app.get("reviews") or {})
        if body.reviews is not None:
            if len(body.reviews) > 60:
                raise HTTPException(400, "A reviews section can hold up to 60 reviews")
            key = (app.get("motion_profile") or {}).get("template_key") or ""
            cur["reviews"] = decorate(body.reviews, key or app_id)
        if body.style is not None:
            allowed = ("accent", "card_bg", "title_color", "title", "subtitle")
            colours = ("accent", "card_bg", "title_color")
            clean = {}
            for k, v in body.style.items():
                if k not in allowed:
                    continue
                val = str(v)[:120].strip()
                if k in colours and val and not re.fullmatch(r"#[0-9a-fA-F]{3,8}|rgba?\([\d.,%\s]+\)", val):
                    raise HTTPException(400, f"{k} must be a hex or rgb colour")
                clean[k] = val
            cur["style"] = clean
        cur["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.apps.update_one({"app_id": app_id}, {"$set": {"reviews": cur}})
        await log_activity(app_id, user["user_id"], "reviews.save", "Updated the reviews section")
        return await get_reviews(app_id, user)

    @api.post("/apps/{app_id}/reviews/reset")
    async def reset_reviews(app_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        await db.apps.update_one({"app_id": app_id}, {"$unset": {"reviews": ""}})
        await log_activity(app_id, user["user_id"], "reviews.reset", "Restored the project reviews")
        return await get_reviews(app_id, user)

    @api.post("/admin/reviews/generate/{key}")
    async def admin_generate(key: str, user: dict = Depends(get_current_user)):
        if key not in BRIEFS:
            raise HTTPException(400, f"Unknown template: {key}")
        try:
            return await generate_and_store(key)
        except Exception as e:
            raise HTTPException(502, f"Could not write reviews: {e}")

    @api.get("/admin/reviews/status")
    async def admin_status(user: dict = Depends(get_current_user)):
        done = {d["key"]: d.get("count", 0) async for d in db.template_reviews.aggregate(
            [{"$project": {"_id": 0, "key": 1, "count": {"$size": {"$ifNull": ["$reviews", []]}}}}])}
        return {"generated": done, "missing": [k for k in BRIEFS if k not in done], "total": len(BRIEFS)}
