import hashlib
import uuid
from datetime import datetime, timezone

V = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/"
U = "https://images.unsplash.com/"


def _id(p):
    return f"{p}_{uuid.uuid4().hex[:12]}"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _pv_token(app_id):
    """Deterministic preview token so published preview links survive a DB reset."""
    return "pv_" + hashlib.sha256(f"preview:{app_id}".encode()).hexdigest()[:20]


NICHES = {
    "Nexus Commerce": {
        "kind": "website", "theme": {"mode": "light", "primary": "#F97316", "secondary": "#14B8A6", "font_heading": "Sora", "font_body": "Manrope", "radius": 20},
        "badge": "Headless commerce", "title": "Sell everywhere. Manage from one place.", "sub": "Real-time inventory, AI product tagging and multi-currency checkout for ambitious online stores.",
        "cta": "Start selling", "cta2": "See a demo store", "variant": "split",
        "hero_img": U + "photo-1556742049-0cfed4f6a45d?w=1400&q=80", "video": V + "ForBiggerBlazes.mp4",
        "gallery": ["photo-1523275335684-37898b6baf30", "photo-1542291026-7eec264c27ff", "photo-1505740420928-5e560c06d30e", "photo-1526170375885-4d8ecf77b99f", "photo-1491553895911-0055eca6402d", "photo-1560343090-f0409e92791a"],
        "features": [("Live inventory", "Sync stock across web, POS and marketplaces in real time.", "Zap"), ("AI tagging", "Auto-generate product attributes, alt text and SEO copy.", "Sparkles"), ("Global checkout", "135 currencies, local payment methods, one dashboard.", "Globe")],
        "logos": ["Shopify", "Stripe", "Klarna", "DHL", "Meta"], "plans": [("Launch", "$49", ["1,000 SKUs", "2 channels"]), ("Growth", "$149", ["25,000 SKUs", "All channels", "AI tagging"]), ("Enterprise", "$499", ["Unlimited", "Dedicated CSM"])],
        "quotes": [("Our conversion rate jumped 31% in the first quarter.", "Maya Chen", "Founder, Loom & Leaf"), ("Inventory errors went to zero. Zero.", "Diego Ruiz", "Ops Director, Kettle Co."), ("The AI copy alone saves us a full-time hire.", "Priya Nair", "CMO, Bloomwell")],
        "faq": [("Does it work with my existing store?", "Yes — connect Shopify, WooCommerce or a headless stack in minutes."), ("Is there a transaction fee?", "No. You only pay the flat monthly plan."), ("Can I migrate my catalog?", "Import via CSV or API with automatic field mapping.")],
        "email": "hello@nexuscommerce.io", "phone": "+1 (416) 555-0142", "address": "88 Queen St W, Toronto",
    },
    "Orbit SaaS Portal": {
        "kind": "app", "theme": {"mode": "dark", "primary": "#06B6D4", "secondary": "#A78BFA", "font_heading": "Space Grotesk", "font_body": "DM Sans", "radius": 12},
        "badge": "Customer success, automated", "title": "Turn churn signals into renewals.", "sub": "Workflow analytics and AI copilots that tell your CS team who to call today — and what to say.",
        "cta": "Book a walkthrough", "cta2": "Watch 2-min tour", "variant": "centered",
        "hero_img": U + "photo-1551288049-bebda4e38f71?w=1400&q=80", "video": V + "ForBiggerEscapes.mp4",
        "gallery": ["photo-1551288049-bebda4e38f71", "photo-1460925895917-afdab827c52f", "photo-1504868584819-f8e8b4b6d7e3", "photo-1553877522-43269d4ea984", "photo-1531403009284-440f080d1e12", "photo-1519389950473-47ba0277781c"],
        "features": [("Health scoring", "Blend product usage, tickets and sentiment into one score.", "Heart"), ("AI copilot", "Draft renewal emails and QBR decks from live account data.", "Sparkles"), ("Playbooks", "Trigger tasks automatically when risk changes.", "Rocket")],
        "logos": ["Salesforce", "HubSpot", "Zendesk", "Slack", "Snowflake"], "plans": [("Team", "$79", ["5 seats", "Health scores"]), ("Business", "$249", ["25 seats", "AI copilot", "Playbooks"]), ("Scale", "$799", ["Unlimited", "SSO + audit log"])],
        "quotes": [("Net revenue retention went from 96% to 112%.", "Jordan Blake", "VP CS, Relay"), ("The copilot writes better QBRs than I do.", "Sam Okafor", "CSM, Northwind"), ("Finally one source of truth for accounts.", "Lena Fischer", "COO, Grid")],
        "faq": [("Which CRMs do you integrate?", "Salesforce, HubSpot and Pipedrive natively; anything else via API."), ("Is my data used to train models?", "Never. Your workspace is isolated and encrypted."), ("How long is onboarding?", "Most teams are live in under two weeks.")],
        "email": "sales@orbitportal.ai", "phone": "+1 (415) 555-0199", "address": "500 Howard St, San Francisco",
    },
    "Fleet Command": {
        "kind": "app", "theme": {"mode": "light", "primary": "#F59E0B", "secondary": "#0F172A", "font_heading": "Outfit", "font_body": "Manrope", "radius": 8},
        "badge": "Dispatch console", "title": "Every truck, every driver, one live map.", "sub": "Real-time telemetry, SLA alerts and AI route planning for logistics operators who can't afford a late delivery.",
        "cta": "Request access", "cta2": "See the console", "variant": "left",
        "hero_img": U + "photo-1601584115197-04ecc0da31d7?w=1400&q=80", "video": V + "ForBiggerFun.mp4",
        "gallery": ["photo-1601584115197-04ecc0da31d7", "photo-1586528116311-ad8dd3c8310d", "photo-1494412574643-ff11b0a5c1c3", "photo-1519003722824-194d4455a60c", "photo-1578575437130-527eed3abbec", "photo-1566576912321-d58ddd7a6088"],
        "features": [("Live telemetry", "GPS, fuel, temperature and door sensors at 1-second resolution.", "Clock"), ("SLA alerts", "Get paged before a delivery goes late, not after.", "Shield"), ("Route AI", "Re-plan 500 stops in seconds when traffic changes.", "Zap")],
        "logos": ["Samsara", "Geotab", "Mapbox", "Twilio", "AWS"], "plans": [("Depot", "$199", ["25 vehicles", "Live map"]), ("Regional", "$599", ["150 vehicles", "SLA alerts", "Route AI"]), ("National", "Custom", ["Unlimited", "On-prem option"])],
        "quotes": [("Late deliveries dropped 42% in two months.", "Carlos Mendes", "Ops Lead, Prime Freight"), ("Dispatchers stopped juggling six tabs.", "Aisha Bello", "Dispatch Manager, Northline"), ("The route AI paid for itself in fuel.", "Tom Reilly", "CFO, QuickHaul")],
        "faq": [("Which hardware do you support?", "Any ELD or telematics gateway with an API, plus our own plug-in unit."), ("Does it work offline?", "Drivers' app queues events and syncs when back online."), ("Can we self-host?", "Yes, on the National plan.")],
        "email": "ops@fleetcommand.io", "phone": "+1 (312) 555-0177", "address": "200 W Madison St, Chicago",
    },
    "Aura Wellness": {
        "kind": "app", "theme": {"mode": "light", "primary": "#A78BFA", "secondary": "#F472B6", "font_heading": "Playfair Display", "font_body": "Nunito", "radius": 28},
        "badge": "Now on iOS & Android", "title": "Book your calm in two taps.", "sub": "Yoga, massage and mindfulness sessions from studios near you — with reminders, memberships and easy rescheduling.",
        "cta": "Download the app", "cta2": "Browse studios", "variant": "split",
        "hero_img": U + "photo-1544367567-0f2fcb009e0b?w=1400&q=80", "video": V + "ForBiggerJoylikes.mp4",
        "gallery": ["photo-1544367567-0f2fcb009e0b", "photo-1506126613408-eca07ce68773", "photo-1545205597-3d9d02c29597", "photo-1540555700478-4be46b6ad3e0", "photo-1552196563-55cd4e45efb3", "photo-1518611012118-696072aa579a"],
        "features": [("Smart scheduling", "See real availability and book instantly, no phone calls.", "Clock"), ("Memberships", "Class packs and unlimited plans with auto-renew.", "Heart"), ("Gentle reminders", "SMS and push nudges so you never miss a session.", "Check")],
        "logos": ["Mindbody", "Stripe", "Apple Health", "Google Fit", "Twilio"], "plans": [("Drop-in", "$18", ["Single class"]), ("Flow", "$79", ["8 classes / mo", "Priority booking"]), ("Unlimited", "$129", ["All classes", "Guest passes"])],
        "quotes": [("I've kept a 5-day streak for three months.", "Emma Wilson", "Member since 2025"), ("Rescheduling is finally painless.", "Noah Park", "Member"), ("Our studio's no-shows halved.", "Sofia Rossi", "Owner, Luma Yoga")],
        "faq": [("Can I cancel a booking?", "Yes, free up to 12 hours before the session."), ("Do memberships roll over?", "Unused Flow classes roll over for one month."), ("Which cities are you in?", "Toronto, Vancouver, Austin and Lisbon — more soon.")],
        "email": "hello@aurawellness.app", "phone": "+1 (647) 555-0123", "address": "1200 Bay St, Toronto",
    },
    "Ledger AI Portfolio": {
        "kind": "app", "theme": {"mode": "dark", "primary": "#F472B6", "secondary": "#34D399", "font_heading": "Plus Jakarta Sans", "font_body": "Manrope", "radius": 16},
        "badge": "Personal finance copilot", "title": "Know exactly where your money goes.", "sub": "Connect every account, get plain-English summaries and a budget that adapts to real life.",
        "cta": "Start free", "cta2": "How it works", "variant": "centered",
        "hero_img": U + "photo-1611974789855-9c2a0a7236a3?w=1400&q=80", "video": V + "ForBiggerMeltdowns.mp4",
        "gallery": ["photo-1611974789855-9c2a0a7236a3", "photo-1579621970563-ebec7560ff3e", "photo-1554224155-6726b3ff858f", "photo-1559526324-4b87b5e36e44", "photo-1642790106117-e829e14a795f", "photo-1460925895917-afdab827c52f"],
        "features": [("Plaid sync", "12,000+ banks, brokerages and cards in one view.", "Globe"), ("AI summaries", "Your month, explained in three sentences.", "Sparkles"), ("Adaptive budgets", "Targets that shift with income and seasonality.", "Star")],
        "logos": ["Plaid", "Visa", "Coinbase", "Wealthsimple", "Robinhood"], "plans": [("Free", "$0", ["2 accounts", "Weekly summary"]), ("Plus", "$9", ["Unlimited accounts", "AI insights"]), ("Family", "$19", ["5 members", "Shared goals"])],
        "quotes": [("Paid off $8k of debt in a year.", "Chris Adams", "Plus member"), ("The summaries are eerily accurate.", "Yuki Tanaka", "Designer"), ("We finally agree on a budget.", "The Garcias", "Family plan")],
        "faq": [("Is my banking data safe?", "Bank-grade encryption; we never store credentials."), ("Do you sell data?", "No. Ever."), ("Can I export?", "CSV and Excel exports on all plans.")],
        "email": "support@ledger.ai", "phone": "+1 (212) 555-0111", "address": "1 Liberty Plaza, New York",
    },
    "Studio Booking": {
        "kind": "website", "theme": {"mode": "light", "primary": "#0F172A", "secondary": "#F97316", "font_heading": "Sora", "font_body": "DM Sans", "radius": 4},
        "badge": "For creative studios", "title": "Book the room. Skip the back-and-forth.", "sub": "A booking widget for photo, music and podcast studios with tiered pricing, deposits and SMS reminders.",
        "cta": "Add to your site", "cta2": "See a live widget", "variant": "left",
        "hero_img": U + "photo-1598488035139-bdbb2231ce04?w=1400&q=80", "video": V + "ForBiggerBlazes.mp4",
        "gallery": ["photo-1598488035139-bdbb2231ce04", "photo-1519741497674-611481863552", "photo-1478737270239-2f02b77fc618", "photo-1493225457124-a3eb161ffa5f", "photo-1516280440614-37939bbacd81", "photo-1511379938547-c1f69419868d"],
        "features": [("Tiered pricing", "Hourly, half-day and full-day rates with peak multipliers.", "Star"), ("Deposits", "Collect a deposit at booking, the rest on arrival.", "Shield"), ("Reminders", "SMS reminders cut no-shows by half.", "Clock")],
        "logos": ["Squarespace", "Wix", "Stripe", "Twilio", "Google Calendar"], "plans": [("Solo", "$29", ["1 room"]), ("Studio", "$79", ["5 rooms", "Deposits", "SMS"]), ("Group", "$199", ["Unlimited rooms", "Multi-location"])],
        "quotes": [("Bookings doubled after embedding the widget.", "Marcus Lee", "Owner, Redline Studios"), ("Deposits ended our no-show problem.", "Hannah Kim", "Manager, Echo Rooms"), ("Setup took 10 minutes.", "Leo Martins", "Podcaster")],
        "faq": [("Does it work on my website builder?", "Yes — one script tag works on any site."), ("Which payment providers?", "Stripe today; more coming."), ("Can clients reschedule?", "Yes, within your cancellation window.")],
        "email": "hi@studiobooking.co", "phone": "+1 (213) 555-0150", "address": "800 Traction Ave, Los Angeles",
    },
}


def _blk(t, props, style=None):
    st = dict(style or {"bg": "default", "align": "left", "padding": "md"})
    st.setdefault("effects", {"reveal": True, "hover": t in ("features", "gallery", "testimonials", "pricing", "logos")})
    return {"id": _id("blk"), "type": t, "props": props, "style": st}


def build_pages(name, n):
    nav = _blk("navbar", {"brand": name, "links": [{"label": "Home", "href": "/"}, {"label": "About", "href": "/about"}, {"label": "Pricing", "href": "/pricing"}, {"label": "Contact", "href": "/contact"}], "cta": n["cta"]})
    footer = _blk("footer", {"brand": name, "tagline": n["sub"][:70] + "…", "columns": [{"title": "Product", "links": ["Features", "Pricing", "Changelog"]}, {"title": "Company", "links": ["About", "Careers", "Contact"]}, {"title": "Legal", "links": ["Privacy", "Terms"]}]})
    imgs = [U + f"{p}?w=1200&q=80" for p in n["gallery"]]
    centered = n["variant"] == "centered"
    home = [nav,
            _blk("hero", {"variant": n["variant"], "badge": n["badge"], "title": n["title"], "subtitle": n["sub"], "cta": n["cta"], "cta2": n["cta2"], "image": n["hero_img"]}, {"bg": "default", "align": "center" if centered else "left", "padding": "lg"}),
            _blk("logos", {"heading": "Trusted by teams at", "names": n["logos"]}, {"bg": "muted", "align": "center", "padding": "sm"}),
            _blk("features", {"heading": "Built for the way you work", "subheading": "Three capabilities customers mention most.", "items": [{"title": a, "desc": b, "icon": c} for a, b, c in n["features"]]}),
            _blk("video", {"heading": "See it in action", "url": n["video"], "caption": "A 60-second product tour."}, {"bg": "muted", "align": "center", "padding": "md"}),
            _blk("gallery", {"heading": "A closer look", "images": imgs[:6]}),
            _blk("testimonials", {"heading": "Loved by customers", "items": [{"quote": q, "name": a, "role": r} for q, a, r in n["quotes"]]}, {"bg": "muted", "align": "left", "padding": "md"}),
            _blk("cta", {"title": "Ready when you are.", "subtitle": "Join hundreds of teams already using " + name + ".", "cta": n["cta"]}, {"bg": "accent", "align": "center", "padding": "lg"}),
            footer]
    about = [nav,
             _blk("hero", {"variant": "left", "badge": "Our story", "title": f"Why we built {name}", "subtitle": "We started with a simple frustration and turned it into a product thousands rely on every day.", "cta": "Meet the team", "image": imgs[1]}, {"bg": "default", "align": "left", "padding": "lg"}),
             _blk("gallery", {"heading": "Behind the scenes", "images": imgs[2:5]}),
             _blk("chart", {"heading": "Customers over time", "series": [{"m": "Jan", "v": 120}, {"m": "Mar", "v": 260}, {"m": "May", "v": 410}, {"m": "Jul", "v": 590}, {"m": "Sep", "v": 820}, {"m": "Nov", "v": 1140}]}, {"bg": "muted", "align": "left", "padding": "md"}),
             footer]
    pricing = [nav,
               _blk("pricing", {"heading": "Simple, transparent pricing", "plans": [{"name": a, "price": b, "period": "mo", "features": c, "highlight": i == 1} for i, (a, b, c) in enumerate(n["plans"])]}, {"bg": "default", "align": "center", "padding": "lg"}),
               _blk("faq", {"heading": "Frequently asked questions", "items": [{"q": q, "a": a} for q, a in n["faq"]]}, {"bg": "muted", "align": "left", "padding": "md"}),
               footer]
    contact = [nav,
               _blk("contact", {"heading": "Let's talk", "subtitle": "We reply within one business day.", "email": n["email"], "phone": n["phone"], "address": n["address"]}, {"bg": "default", "align": "left", "padding": "lg"}),
               footer]
    return [("Home", "/", home), ("About", "/about", about), ("Pricing", "/pricing", pricing), ("Contact", "/contact", contact)]


async def reseed_demo_sites(db, owner_id):
    """Give each seeded demo app a unique themed multi-page site (runs once per app)."""
    for name, n in NICHES.items():
        app = await db.apps.find_one({"owner_id": owner_id, "name": name}, {"_id": 0})
        if not app or app.get("demo_site_v") == 2:
            continue
        if await db.pages.count_documents({"app_id": app["app_id"]}) > 0:
            continue  # never overwrite a tenant that already has saved pages
        for i, (pname, slug, blocks) in enumerate(build_pages(name, n)):
            await db.pages.insert_one({"page_id": _id("pg"), "app_id": app["app_id"], "name": pname, "slug": slug, "order": i, "blocks": blocks, "updated_at": _now()})
        await db.apps.update_one({"app_id": app["app_id"]}, {"$set": {"theme": n["theme"], "kind": n["kind"], "demo_site_v": 2, "thumbnail": n["hero_img"], "video_url": n["video"],
                                                                  "preview_enabled": True, "preview_token": app.get("preview_token") or _id("pv") + uuid.uuid4().hex[:8]}})



# Canonical tenant the client-editor account is a member of. Recreated idempotently by app_id so a
# wiped database never leaves the editor account with zero tenants.
EDITOR_TENANT_ID = "app_6663b5de0007"
EDITOR_EMAIL = "client.editor@example.com"
EDITOR_PASSWORD = "ClientEdit2026!"


async def ensure_editor_tenant(db, owner_id, hash_password):
    app = await db.apps.find_one({"app_id": EDITOR_TENANT_ID}, {"_id": 0})
    if not app:
        app = {
            "app_id": EDITOR_TENANT_ID, "owner_id": owner_id, "name": "Northwind Roofing",
            "industry": "Construction", "status": "active",
            "description": "Residential and commercial roofing with 24/7 storm response and financing.",
            "tags": ["Roofing", "Bookings", "Leads"], "color": "#F97316",
            "thumbnail": U + "photo-1632759145355-8c1d0a1bff2a?w=1400&q=80",
            "transfer_mode": False, "preview_enabled": True, "preview_token": _pv_token(EDITOR_TENANT_ID),
            "metrics": {"uptime": 99.95, "cpu": 28, "ram": 54, "response_ms": 92, "visitors_24h": 1840},
            "created_at": _now(), "updated_at": _now(),
        }
        await db.apps.insert_one(dict(app))
    if await db.pages.count_documents({"app_id": EDITOR_TENANT_ID}) == 0:
        from site_content import build_premium_site
        pages, theme, n = build_premium_site(app, "construction", {"name": app["name"]})
        for i, (pname, slug, blocks) in enumerate(pages):
            await db.pages.insert_one({"page_id": _id("pg"), "app_id": EDITOR_TENANT_ID, "name": pname, "slug": slug, "order": i, "blocks": blocks, "updated_at": _now()})
        await db.apps.update_one({"app_id": EDITOR_TENANT_ID}, {"$set": {"theme": theme, "premium_site_v": 3, "site_niche": "construction", "video_url": n["video"], "preview_enabled": True, "updated_at": _now()}})

    user = await db.users.find_one({"email": EDITOR_EMAIL}, {"_id": 0})
    if not user:
        await db.users.insert_one({
            "user_id": _id("user"), "email": EDITOR_EMAIL, "name": "Client Editor", "role": "user",
            "password_hash": hash_password(EDITOR_PASSWORD), "auth_provider": "jwt",
            "picture": None, "created_at": _now(),
        })
        user = await db.users.find_one({"email": EDITOR_EMAIL}, {"_id": 0})

    await db.memberships.update_one(
        {"app_id": EDITOR_TENANT_ID, "user_id": user["user_id"]},
        {"$set": {"role": "editor"}, "$setOnInsert": {"created_at": _now()}},
        upsert=True,
    )


# Canonical demo tenants, one per showcase industry. Fixed app_ids so a wiped or rolled-back
# database always self-heals to the same set instead of generating new tenants.
DEMO_TENANTS = [
    ("app_009e5e117f77", "retail"),
    ("app_04366e4b6d97", "saas"),
    ("app_cca4d5dd736d", "logistics"),
    ("app_b86054a26f34", "fitness"),
    ("app_77d30fefb622", "finance"),
    ("app_b96a63e4b700", "creative_studio"),
]


async def ensure_demo_tenants(db, owner_id):
    from site_content import NICHES, build_premium_site, theme_for
    made = 0
    for app_id, key in DEMO_TENANTS:
        if await db.apps.find_one({"app_id": app_id}, {"_id": 0, "app_id": 1}):
            continue
        n = NICHES[key]
        doc = {
            "app_id": app_id, "owner_id": owner_id, "name": n["brand"], "industry": n["industry"],
            "description": n["sub"], "status": "active", "tags": [n["industry"]], "color": n["primary"],
            "thumbnail": n["hero"], "video_url": n["video"], "transfer_mode": False,
            "preview_enabled": True, "preview_token": _pv_token(app_id),
            "site_niche": key, "premium_site_v": 3, "theme": theme_for(n, key),
            "metrics": {"uptime": 99.9, "cpu": 24, "ram": 48, "response_ms": 96, "visitors_24h": 1200},
            "created_at": _now(), "updated_at": _now(),
        }
        await db.apps.insert_one(dict(doc))
        pages, _theme, _n = build_premium_site(doc, key, {"name": n["brand"]})
        for i, (pname, slug, blocks) in enumerate(pages):
            await db.pages.insert_one({"page_id": _id("pg"), "app_id": app_id, "name": pname, "slug": slug, "order": i, "blocks": blocks, "updated_at": _now()})
        made += 1
    return made
