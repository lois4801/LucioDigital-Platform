import re
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

U = "https://images.unsplash.com/"
PX = "https://www.pexels.com/download/video/{}/"
YT = "https://www.youtube.com/embed?listType=search&list={}"


def _id(p):
    return f"{p}_{uuid.uuid4().hex[:12]}"


def _now():
    return datetime.now(timezone.utc).isoformat()


def img(pid, w=1600):
    return f"{U}{pid}?w={w}&q=80&auto=format&fit=crop"


FACES = ["photo-1560250097-0b93528c311a", "photo-1573496359142-b8d87734a5a2", "photo-1507003211169-0a1dd7228f2d", "photo-1580489944761-15a19d654956", "photo-1472099645785-5658abf4ff4e", "photo-1438761681033-6461ffad8d80"]

# Premium dark design system per mood. bg / surface / border tuned so glass cards glow against the accent.
MOODS = {
    "industrial": {"bg": "#0B0B0F", "surface": "#15151C", "border": "#2A2A35", "font_heading": "Sora", "font_body": "Manrope", "radius": 10},
    "clinical": {"bg": "#070D14", "surface": "#0F1A24", "border": "#1F2F3D", "font_heading": "Plus Jakarta Sans", "font_body": "DM Sans", "radius": 18},
    "moody": {"bg": "#0A0A0F", "surface": "#141420", "border": "#262637", "font_heading": "Space Grotesk", "font_body": "Manrope", "radius": 6},
    "luxury": {"bg": "#0B0A0A", "surface": "#171312", "border": "#2E2622", "font_heading": "Playfair Display", "font_body": "Nunito", "radius": 4},
    "energetic": {"bg": "#0A0A0F", "surface": "#13131C", "border": "#25253A", "font_heading": "Outfit", "font_body": "DM Sans", "radius": 22},
    "corporate": {"bg": "#070B16", "surface": "#0E1526", "border": "#1D2740", "font_heading": "Plus Jakarta Sans", "font_body": "Manrope", "radius": 12},
}


def theme_for(n):
    m = MOODS[n["mood"]]
    return {"mode": "dark", "primary": n["primary"], "secondary": n["secondary"], "bg": m["bg"], "surface": m["surface"], "fg": "#F8FAFC", "muted": "#A1A7B8", "border": m["border"],
            "font_heading": m["font_heading"], "font_body": m["font_body"], "radius": m["radius"], "motion": True, "cursor": True, "glass": True, "grain": True, "premium_v": 3}


# Each niche: brand, mood, colors, hero, media, sections (ordered), copy. Every word is written for that industry.
NICHES = {
 "hvac": dict(brand="Summit Air & Heat", industry="HVAC", mood="industrial", primary="#F97316", secondary="#38BDF8",
  badge="24/7 emergency service · NATE-certified", title="Comfort you can count on, in every season.", sub="Residential and light-commercial heating, cooling and indoor air quality — installed right the first time and maintained for life.",
  cta="Book a service call", cta2="Call (416) 555-0188", hero=img("photo-1581094794329-c8112a89af12"), video=PX.format(28886877),
  gallery=["photo-1621905251189-08b45d6a269e", "photo-1504328345606-18bbc8c9d7d1", "photo-1585129777188-94600bc7b4b3", "photo-1607400201889-565b1ee75f8e", "photo-1581092160562-40aa08e78837", "photo-1558618666-fcd25c85cd64"],
  sections=["services", "emergency", "plans", "areas", "certs", "stats", "video", "testimonials", "faq", "cta"],
  services=("Services", "From a single furnace repair to a full ductless retrofit.", [("Furnace & boiler repair", "Same-day diagnostics on all gas, oil and electric systems. Most repairs completed on the first visit.", "Zap"), ("AC installation", "Right-sized 16–20 SEER systems with Manual J load calculations, not guesswork.", "Star"), ("Heat pumps & ductless", "Cold-climate heat pumps that hold 100% capacity to −15°C. Rebate paperwork handled for you.", "Globe"), ("Indoor air quality", "HRVs, HEPA filtration, humidifiers and duct cleaning for healthier air.", "Heart"), ("Commercial rooftop units", "Preventive maintenance and replacement for 3–25 ton RTUs.", "Shield"), ("Smart thermostats", "Ecobee and Nest installs with zoning and remote monitoring.", "Sparkles")]),
  emergency=("No heat? No cool? We're on call 24/7.", "A live dispatcher answers every call. Average emergency response time: 92 minutes.", "Call now: (416) 555-0188"),
  plans=("Maintenance Plans", [("Comfort", "$14", ["1 tune-up / year", "10% off repairs", "Priority scheduling"]), ("Comfort+", "$24", ["2 tune-ups / year", "15% off repairs", "No overtime charges", "Filter delivery"]), ("Total Care", "$39", ["2 tune-ups / year", "20% off repairs", "Free diagnostics", "10-year labour warranty"])]),
  areas=("Service Areas", ["Toronto", "Mississauga", "Brampton", "Vaughan", "Markham", "Oakville", "Richmond Hill", "Pickering"]),
  certs=("Licensed, insured & certified", ["TSSA Licensed", "NATE Certified", "HRAI Member", "Carrier Factory Authorized", "Energy Star Partner", "WSIB Covered"]),
  stats=[("18,400+", "Systems serviced"), ("92 min", "Avg. emergency response"), ("4.9★", "Google rating, 2,100 reviews"), ("27 yrs", "In business")],
  quotes=[("Our furnace died on the coldest night of January. Summit had a tech here in under two hours and heat back on before midnight.", "Karen Whitfield", "Homeowner, Etobicoke"), ("They replaced four rooftop units across our plaza with zero tenant downtime. Bills dropped 31% the first summer.", "Raj Patel", "Property Manager, Dixie Plaza"), ("The Total Care plan has paid for itself twice. The pre-season tune-ups caught a cracked heat exchanger before it became dangerous.", "Mike Delorme", "Homeowner, Vaughan")],
  faq=[("Do you offer financing?", "Yes — 0% for 24 months on new systems, with approvals in minutes."), ("How often should my system be serviced?", "Twice a year: cooling in spring, heating in fall. Plan members are scheduled automatically."), ("Are your technicians background-checked?", "Every technician is TSSA-licensed, drug-tested and background-checked, and arrives in uniform with ID.")],
  about=("Started in a garage in 1998 with one van and a promise.", "Summit was founded by Dan Kowalski after 12 years working for a national chain where speed mattered more than doing the job right. He started Summit with one van, a Manual J calculator and a rule: never sell a homeowner more than they need. Today 42 technicians carry that rule into 18,000 homes a year, and Dan still rides along on installs every Friday."),
  team=[("Dan Kowalski", "Founder & Master Technician"), ("Priya Anand", "Service Manager"), ("Luis Ortega", "Lead Installer"), ("Sarah Cheng", "Comfort Advisor")],
  email="service@summitairheat.ca", phone="+1 (416) 555-0188", address="215 Industrial Pkwy N, Toronto, ON"),

 "healthcare": dict(brand="Northgate Family Medicine", industry="Healthcare", mood="clinical", primary="#14B8A6", secondary="#60A5FA",
  badge="Accepting new patients · Same-week appointments", title="Modern primary care that still knows your name.", sub="Board-certified physicians, on-site lab and imaging, and a patient portal that puts your results in your pocket — usually within 24 hours.",
  cta="Book an appointment", cta2="Patient portal", hero=img("photo-1519494026892-80bbd2d6fd0d"), video=PX.format(7579840),
  gallery=["photo-1579684385127-1ef15d508118", "photo-1576091160399-112ba8d25d1d", "photo-1551601651-2a8555f1a136", "photo-1584982751601-97dcc096659c", "photo-1631217868264-e5b90bb7e133", "photo-1666214280557-f1b5022eb634"],
  sections=["services", "team", "insurance", "portal", "stats", "video", "testimonials", "booking", "faq"],
  services=("Specialties", "Comprehensive care for every stage of life, under one roof.", [("Family medicine", "Preventive care, chronic disease management and annual physicals for patients from newborn to 100.", "Heart"), ("Pediatrics", "Well-child visits, immunizations and same-day sick visits with dedicated kids' exam rooms.", "Star"), ("Women's health", "Annual exams, prenatal care coordination, contraception counselling and menopause management.", "Sparkles"), ("Cardiometabolic clinic", "Hypertension, diabetes and cholesterol programs with in-house A1c and lipid testing.", "Zap"), ("Mental health", "Integrated behavioural health with licensed therapists and psychiatric consults.", "Shield"), ("On-site lab & imaging", "Bloodwork, ECG, X-ray and ultrasound — no second trip across town.", "Globe")]),
  team_heading="Meet the Doctors",
  team=[("Dr. Amara Osei, MD", "Family Medicine · Medical Director"), ("Dr. James Whitaker, MD", "Internal Medicine"), ("Dr. Lena Berg, MD", "Pediatrics"), ("Dr. Sofia Marquez, DO", "Women's Health")],
  insurance=("Insurance Accepted", ["Blue Cross Blue Shield", "Aetna", "UnitedHealthcare", "Cigna", "Medicare", "Humana", "Kaiser (out-of-network)", "Sun Life"]),
  portal=("Your health, in your pocket.", "Message your care team, view lab results within 24 hours, request refills and check in from your phone before you arrive.", "Open the Patient Portal"),
  stats=[("24 hrs", "Avg. time to lab results"), ("98%", "Patient satisfaction"), ("12,600", "Active patients"), ("< 9 min", "Avg. wait past appointment time")],
  quotes=[("Dr. Osei caught my thyroid issue during a routine physical that two previous doctors missed. Results were in the portal the next morning.", "Melissa Tran", "Patient since 2021"), ("Same-day appointment for my son's ear infection, prescription sent before we reached the pharmacy. This is how healthcare should work.", "David Okonkwo", "Parent of two"), ("The cardiometabolic program brought my A1c from 8.4 to 6.1 in seven months without adding medication.", "Robert Kaminski", "Patient")],
  booking=("Book in under two minutes.", "Choose your provider, pick a time, and we'll text a confirmation. New patients welcome.", "Book an appointment"),
  faq=[("Are you accepting new patients?", "Yes — new patient visits are typically available within one week."), ("Do you offer telehealth?", "Video visits are available for follow-ups, medication reviews and many acute concerns."), ("What should I bring to my first visit?", "Photo ID, insurance card, current medication list and any recent records — or let us request them for you.")],
  about=("Founded by three physicians who were tired of seven-minute visits.", "Northgate opened in 2014 when Drs. Osei, Whitaker and Berg left a large hospital network to build the practice they wanted for their own families: 30-minute appointments, results in a day, and a front desk that answers the phone. We've grown to 14 providers, but every appointment is still 30 minutes."),
  email="care@northgatefamilymed.com", phone="+1 (503) 555-0142", address="4410 Northgate Blvd, Suite 200, Portland, OR"),

 "construction": dict(brand="Ironbridge Construction Group", industry="Construction", mood="industrial", primary="#F59E0B", secondary="#94A3B8",
  badge="ISO 45001 · COR™ Certified · Bonded", title="We build the structures cities run on.", sub="Commercial, institutional and industrial general contracting — delivered on schedule, on budget and with an industry-leading safety record since 1987.",
  cta="Request a quote", cta2="View our projects", hero=img("photo-1541888946425-d81bb19240f5"), video=PX.format(8598737),
  gallery=["photo-1503387762-592deb58ef4e", "photo-1541976590-713941681591", "photo-1429497419816-9ca5cfb4571a", "photo-1517581177682-a085bb7ffb15", "photo-1590644365607-1c5a5e03a0a5", "photo-1487958449943-2429e8be8625"],
  sections=["portfolio", "services", "safety", "certs", "stats", "video", "team", "testimonials", "quote"],
  portfolio=("Projects Portfolio", "A selection of recent work across sectors."),
  services=("Services", "One accountable partner from pre-construction to turnover.", [("General contracting", "Lump-sum and CM-at-risk delivery with self-performed concrete and carpentry.", "Shield"), ("Design-build", "Integrated architecture and engineering that cuts schedule by an average of 22%.", "Sparkles"), ("Pre-construction", "Constructability reviews, 4D scheduling and budgets accurate to ±3% at 60% design.", "Star"), ("Industrial & tilt-up", "Warehouses, distribution centres and plants up to 800,000 sq ft.", "Globe"), ("Institutional", "Schools, hospitals and civic buildings with occupied-site phasing.", "Heart"), ("Renovation & tenant fit-out", "Fast-track interior work with after-hours crews and dust control.", "Zap")]),
  safety=("Safety Record", [("m", "2021", "v", 1.9), ("m", "2022", "v", 1.4), ("m", "2023", "v", 0.9), ("m", "2024", "v", 0.6), ("m", "2025", "v", 0.4)], "Total Recordable Incident Rate (TRIR) per 200,000 hours — industry average is 2.5."),
  certs=("Certifications", ["ISO 45001", "COR™ Certified", "LEED AP on staff", "Gold Seal Certified", "CCA Member", "Bonded to $50M"]),
  stats=[("$1.2B", "Completed since 1987"), ("0.4", "TRIR (industry avg 2.5)"), ("94%", "Projects delivered early or on time"), ("312", "Craft & staff employees")],
  team=[("Frank Moretti", "President & CEO"), ("Denise Alvarez, P.Eng", "VP Operations"), ("Tom Nakamura", "Director of Safety"), ("Aisha Rahman", "Pre-construction Lead")],
  quotes=[("Ironbridge delivered our 240,000 sq ft distribution centre three weeks early and $410K under GMP. Their safety culture is the real thing — 190,000 hours without a recordable.", "Gary Lindqvist", "VP Real Estate, Northstar Logistics"), ("Renovating an operating hospital wing is surgery on a living patient. They phased it so well our nursing staff barely noticed.", "Dr. Helen Park", "COO, Lakeside Regional Hospital"), ("Third school we've built with them. Bid accuracy, transparent change orders, no surprises.", "Marcus Bell", "Facilities Director, District 41")],
  quote=("Request a Quote", "Send us your drawings or a project brief. A pre-construction manager will respond within one business day with a scope review and budget range.", "Request a quote"),
  faq=[("What project sizes do you take on?", "$2M to $150M, from tenant fit-outs to full campus builds."), ("Do you self-perform any trades?", "Yes — concrete, formwork, rough carpentry and site services, which lets us control the critical path."), ("Are you bonded?", "Bonded to $50M single / $150M aggregate through Travelers.")],
  about=("Three generations. One standard.", "Salvatore Moretti poured his first foundation in 1987 with a crew of six. His son Frank runs the company today with 312 employees and the same rule painted on every job trailer: nobody gets hurt building this. That standard has produced a TRIR six times better than the industry average and clients who have stayed with us for decades."),
  email="bids@ironbridgecg.com", phone="+1 (312) 555-0170", address="1800 W Fulton St, Chicago, IL"),

 "fitness": dict(brand="Forge Athletic Club", industry="Fitness", mood="energetic", primary="#84CC16", secondary="#F472B6",
  badge="First week free · No contracts", title="Train like it matters. Because it does.", sub="Small-group strength, conditioning and mobility coached by certified trainers in a 14,000 sq ft facility built for people who want results, not selfies.",
  cta="Start your free week", cta2="See class schedule", hero=img("photo-1534438327276-14e5300c3a48"), video=YT.format("small+group+strength+training+gym+tour"),
  gallery=["photo-1571019613454-1cb2f99b2d8b", "photo-1517836357463-d25dfeac3438", "photo-1583454110551-21f2fa2afe61", "photo-1574680096145-d05b474e2155", "photo-1540497077202-7c8a3999166f", "photo-1541534741688-6078c6bfb5c5"],
  sections=["schedule", "team", "plans", "stories", "stats", "video", "trial", "faq"],
  schedule=("Class Schedule", "Every class is capped at 12 athletes so coaches can actually coach.", [("Forge Strength", "Barbell fundamentals, progressive overload, tracked in our app.", "Zap"), ("Engine", "45 minutes of rowers, bikes and sleds that build a conditioning base without wrecking your joints.", "Heart"), ("Mobility & Recovery", "Guided flexibility, breath work and soft-tissue sessions on Sundays.", "Star"), ("6 AM Iron Club", "Our most loyal class: strength before sunrise, coffee after.", "Clock"), ("Youth Athletics (13–17)", "Movement quality and safe strength foundations for young athletes.", "Users"), ("Open Gym", "Coached open floor from 5 AM to 10 PM for members on a plan.", "Globe")]),
  team_heading="Trainers",
  team=[("Coach Marcus Hill", "Head Coach · CSCS, USAW L2"), ("Coach Dana Reyes", "Strength & Nutrition · PN L2"), ("Coach Tyler Brooks", "Conditioning · CF-L3"), ("Coach Priya Shah", "Mobility · FRCms")],
  plans=("Membership Plans", [("Open Gym", "$69", ["Coached open floor", "App programming", "Locker access"]), ("Unlimited Classes", "$149", ["All classes", "Open gym", "Monthly InBody scan", "Nutrition group"]), ("Coaching+", "$299", ["Everything in Unlimited", "2 personal sessions / mo", "Custom programming", "Quarterly movement screen"])]),
  stories=("Transformation Stories", [("Down 41 lbs and deadlifting 315 for the first time at 47. The coaches never let me hide in the back of the room.", "Angela Moore", "Member, 14 months"), ("I came in after two knee surgeries terrified of squatting. Eight months later I ran my first 10K pain-free.", "Kevin Nash", "Member, 8 months"), ("Forge is the first gym I've stuck with for more than three months. It's the people — and the 6 AM Iron Club.", "Simone Laurent", "Member, 2 years")]),
  stats=[("1,240", "Active members"), ("12", "Max athletes per class"), ("91%", "Members still training after 12 months"), ("6", "Certified coaches on every shift")],
  trial=("Your first week is on us.", "Seven days, unlimited classes, a movement screen and a coach who learns your name. No card required.", "Start your free week"),
  faq=[("I'm a complete beginner. Is this for me?", "Absolutely — every new member starts with a free movement screen and two Foundations sessions before joining classes."), ("Is there a contract?", "No. Month-to-month, cancel anytime with 30 days' notice."), ("Do you have showers and childcare?", "Full locker rooms with showers and towel service; Kids Club runs weekday mornings and Saturdays.")],
  about=("Built by athletes who hated commercial gyms.", "Marcus Hill spent a decade coaching Division I athletes and watched friends bounce between big-box gyms without ever getting stronger. Forge opened in 2017 as the answer: small classes, real coaching, and a community that shows up. We've since added a second floor, a recovery lounge and a waitlist for the 6 AM Iron Club."),
  email="hello@forgeathletic.club", phone="+1 (512) 555-0133", address="2200 E 6th St, Austin, TX"),

 "retail": dict(brand="Maison Verde", industry="E-commerce", mood="luxury", primary="#D4A574", secondary="#6EE7B7",
  badge="Free shipping over $75 · Free returns", title="Home goods made by people, not factories.", sub="Ceramics, linens and kitchenware from 60 independent makers across 14 countries — curated in our Brooklyn flagship and shipped to your door.",
  cta="Shop new arrivals", cta2="Find a store", hero=img("photo-1441986300917-64674bd600d8"), video=YT.format("artisan+ceramics+home+goods+store"),
  gallery=["photo-1556228453-efd6c1ff04f6", "photo-1584589167171-541ce45f1eea", "photo-1616486338812-3dadae4b4ace", "photo-1493663284031-b7e3aefcae8e", "photo-1513694203232-719a280e022f", "photo-1567016432779-094069958ea5"],
  sections=["featured", "categories", "offers", "loyalty", "stats", "video", "testimonials", "locator", "faq"],
  featured=("Featured Products", "This week's most-loved pieces."),
  categories=("Categories", "Shop by room.", [("Kitchen & dining", "Hand-thrown stoneware, carbon-steel pans and olive-wood boards built to be used daily.", "Star"), ("Bed & bath", "GOTS-certified linen sheets and Turkish cotton towels in 14 earth tones.", "Heart"), ("Living", "Wool throws, ceramic lamps and hand-woven baskets.", "Sparkles"), ("Candles & scent", "Small-batch soy candles poured in Portland and Lisbon.", "Zap"), ("Gifts under $50", "Curated for every occasion, wrapped free.", "Globe"), ("The Refill Bar", "Bring your bottle — soaps, oils and detergents by the ounce.", "Shield")]),
  offers=("Offers", [("Welcome", "10% off", ["Your first order", "Free gift wrap", "Early access to drops"]), ("Bundle & Save", "15% off", ["Any 3 kitchen pieces", "Free shipping", "Care kit included"]), ("Verde Circle", "20% off", ["Members-only pricing", "Free returns for a year", "Maker meet-ups"])]),
  loyalty=("The Verde Circle", "Earn a leaf for every dollar. 500 leaves unlocks a $25 credit, birthday gifts and first access to limited maker collaborations.", "Join for free"),
  stats=[("60", "Independent makers"), ("14", "Countries represented"), ("48K", "Circle members"), ("4.8★", "Avg. product rating")],
  quotes=[("The linen sheets are the first ones that actually got softer after washing. Two years in and they look new.", "Hannah Feldman", "Verified buyer, Brooklyn"), ("Ordered Tuesday, wrapped beautifully and on my mom's doorstep Thursday. She thinks I have taste now.", "Jordan Mills", "Verified buyer, Denver"), ("As a maker, Maison Verde pays fairly, pays on time and tells my story on the shelf. That's rare.", "Inés Calderón", "Ceramicist, Oaxaca")],
  locator=("Store Locator", "Visit us in Brooklyn, Austin or Montréal — or shop online 24/7.", "hello@maisonverde.co", "+1 (718) 555-0161", "142 Wythe Ave, Brooklyn, NY · 1011 S Congress Ave, Austin, TX · 4062 Boul. Saint-Laurent, Montréal, QC"),
  faq=[("What is your return policy?", "Free returns within 60 days for any reason. Circle members get a full year."), ("Do you ship internationally?", "Yes — to 32 countries with duties calculated at checkout."), ("Are your products ethically sourced?", "Every maker signs our fair-pay charter and we publish the origin of each product on its page.")],
  about=("It started with one ceramicist and a folding table.", "In 2016, Clara Verde sold bowls from a friend's studio in Oaxaca at a Brooklyn flea market. Customers kept asking who made them. That question became the store: every product carries the maker's name and story, and every maker earns a fair wage, paid within 14 days."),
  team=[("Clara Verde", "Founder & Curator"), ("Tomás Ruiz", "Head of Maker Partnerships"), ("Emily Watanabe", "Store Director, Brooklyn"), ("Noor Haddad", "E-commerce Lead")],
  email="hello@maisonverde.co", phone="+1 (718) 555-0161", address="142 Wythe Ave, Brooklyn, NY"),

 "hospitality": dict(brand="The Harbourline Hotel", industry="Hospitality", mood="luxury", primary="#C9A24E", secondary="#7DD3FC",
  badge="Boutique · 48 rooms · Waterfront", title="Where the city slows to the pace of the tide.", sub="A 48-room boutique hotel on the old harbour — hand-finished suites, a chef-led restaurant and a rooftop bar with the best sunset in the city.",
  cta="Check availability", cta2="Explore the rooms", hero=img("photo-1566073771259-6a8506099945"), video=YT.format("luxury+boutique+hotel+waterfront+tour"),
  gallery=["photo-1582719478250-c89cae4dc85b", "photo-1618773928121-c32242e63f39", "photo-1571003123894-1f0594d2b5d9", "photo-1584132967334-10e028bd69f7", "photo-1590490360182-c33d57733427", "photo-1520250497591-112f2f40a3f4"],
  sections=["rooms", "amenities", "dining", "attractions", "stats", "video", "testimonials", "booking", "faq"],
  rooms=("Rooms & Suites", [("Harbour King", "$289", ["Harbour view", "King bed, linen sheets", "Rain shower", "Breakfast included"]), ("Corner Suite", "$449", ["Wraparound water views", "Separate living room", "Soaking tub", "Evening turndown"]), ("The Lighthouse Penthouse", "$890", ["Private rooftop terrace", "Two bedrooms", "Butler service", "Chef's table for 6"])]),
  amenities=("Amenities", "Everything you need, nothing you don't.", [("Rooftop bar", "Cocktails and small plates from 4 PM, sunsets nightly.", "Star"), ("Spa & sauna", "Cedar sauna, cold plunge and treatment rooms overlooking the water.", "Heart"), ("Complimentary bikes", "Explore the waterfront trail on our fleet of Dutch city bikes.", "Globe"), ("Library lounge", "Fireplace, 2,000 books and a record player. Coffee all day.", "Sparkles"), ("Pet friendly", "Beds, bowls and a welcome treat — no fee.", "Shield"), ("Concierge", "Reservations, boat charters and things we're not allowed to print.", "Zap")]),
  dining=("Dining", [("Brine — the chef-led kitchen", "Daily-changing menu built around the morning's catch and produce from farms within 80 km.", "Star"), ("The Rooftop", "Natural wines, oysters and the best sunset seat in the city.", "Sparkles"), ("Breakfast", "House-baked pastries, local eggs and a proper espresso, included in every stay.", "Heart")]),
  attractions=("Local Attractions", ["Old Harbour Market · 3 min walk", "Maritime Museum · 6 min", "Coastal Trail · at the door", "Ferry to the Islands · 8 min", "Gallery District · 10 min", "Saturday Farmers Market · 5 min"]),
  stats=[("48", "Rooms & suites"), ("9.4", "Guest rating, 3,800 reviews"), ("1911", "Original warehouse built"), ("80 km", "Max distance for our produce")],
  quotes=[("We've stayed at hotels three times the price that don't come close. The corner suite at sunset is something I'll remember for a long time.", "Catherine & Paul Ellis", "Anniversary stay, London"), ("Brine alone is worth the trip. The halibut was caught that morning by a boat we watched come in from our window.", "Marco Bianchi", "Food writer, Milan"), ("Brought our dog, our toddler and our stress. Left with none of the last one.", "Jess Tran", "Family stay, Toronto")],
  booking=("Book direct and save 12%.", "Best-rate guarantee, free cancellation up to 48 hours before arrival, and a welcome drink on the rooftop.", "Check availability"),
  faq=[("What time is check-in and check-out?", "Check-in from 3 PM, check-out by 11 AM. Early and late options on request."), ("Is parking available?", "Valet parking is $35/night; the Harbour Garage next door is $22."), ("Do you host events?", "Yes — weddings up to 90 and private dinners up to 24 in the Chart Room.")],
  about=("A 1911 shipping warehouse, brought back to life.", "The Harbourline was a rope-and-sail warehouse for a century before sitting empty for twenty years. In 2019 we spent 18 months restoring the Douglas-fir beams, original brick and cast-iron columns, then added 48 rooms designed by local craftspeople. Every piece of furniture was made within 200 km."),
  team=[("Elena Marchetti", "General Manager"), ("Chef Owen Blake", "Executive Chef, Brine"), ("Samuel Adeyemi", "Head Concierge"), ("Yuki Mori", "Spa Director")],
  email="stay@harbourlinehotel.com", phone="+1 (902) 555-0119", address="1 Marginal Rd, Halifax, NS"),

 "finance": dict(brand="Meridian Wealth Partners", industry="Finance", mood="corporate", primary="#3B82F6", secondary="#F59E0B",
  badge="Fiduciary · Fee-only · SEC registered", title="Wealth management that answers to you — and no one else.", sub="Independent, fee-only financial planning and investment management for families, founders and professionals with $500K+ in investable assets.",
  cta="Book a discovery call", cta2="How we're paid", hero=img("photo-1611974789855-9c2a0a7236a3"), video=YT.format("fiduciary+financial+planning+explained"),
  gallery=["photo-1554224155-6726b3ff858f", "photo-1579621970563-ebec7560ff3e", "photo-1560472354-b33ff0c44a43", "photo-1450101499163-c8848c66ca85", "photo-1553729459-efe14ef6055d", "photo-1507679799987-c73779587ccf"],
  sections=["services", "whyus", "results", "compliance", "stats", "video", "team", "testimonials", "start", "faq"],
  services=("Services", "Integrated planning, not products.", [("Financial planning", "A living plan covering cash flow, tax, insurance, estate and retirement — updated every quarter.", "Star"), ("Investment management", "Low-cost, globally diversified portfolios with disciplined rebalancing and tax-loss harvesting.", "Zap"), ("Tax strategy", "Roth conversions, asset location and charitable giving coordinated with your CPA.", "Shield"), ("Equity compensation", "RSU, ISO and 10b5-1 planning for founders and executives.", "Sparkles"), ("Retirement income", "Withdrawal sequencing and Social Security optimization that stretches every dollar.", "Heart"), ("Estate & legacy", "Trust coordination, beneficiary reviews and family governance meetings.", "Globe")]),
  whyus=("Why Us", "What independence actually means for you.", [("Fee-only, always", "We never earn commissions. Our only revenue is the transparent fee you pay us.", "Shield"), ("Fiduciary in writing", "We sign a fiduciary oath for every client. Your interests come first — legally.", "Star"), ("CFP® on every account", "Every relationship is led by a CERTIFIED FINANCIAL PLANNER™ with 10+ years' experience.", "Sparkles")]),
  results=("Client Results", [("m", "2020", "v", 62), ("m", "2021", "v", 71), ("m", "2022", "v", 68), ("m", "2023", "v", 79), ("m", "2024", "v", 88), ("m", "2025", "v", 94)], "Median client 'confidence in retirement readiness' score (0–100) from our annual survey."),
  compliance=("Compliance & Security", ["SEC Registered Investment Adviser", "Fidelity & Schwab custody", "SOC 2 Type II vault", "256-bit encryption", "$5M E&O coverage", "Annual independent audit"]),
  stats=[("$1.4B", "Assets under management"), ("0.65%", "Avg. all-in fee (industry 1.2%)"), ("97%", "Client retention, 5-yr"), ("11", "CFP® professionals")],
  team=[("Elizabeth Meridian, CFP®, CFA", "Founder & Chief Investment Officer"), ("Daniel Ross, CFP®, CPA", "Partner, Tax Strategy"), ("Anita Kapoor, CFP®", "Partner, Founder & Equity Comp"), ("Marcus Ellison, JD", "Estate Planning Counsel")],
  quotes=[("They found $38,000 a year in tax savings through Roth conversions and asset location that my previous advisor never mentioned.", "Tom & Rachel Garner", "Clients since 2019"), ("When my company was acquired, Anita walked me through every RSU and ISO decision. I kept an extra six figures because of it.", "Wei Zhang", "Founder, exited 2023"), ("First advisor who showed me exactly what I pay, in dollars, on one page.", "Gloria Hernandez", "Retired educator")],
  start=("Get Started", "A 30-minute discovery call. No pitch, no pressure — just a conversation about where you are and whether we're the right fit.", "Book a discovery call"),
  faq=[("What are your fees?", "0.85% on the first $1M, declining to 0.40% above $5M. Planning-only engagements start at $6,000/year."), ("What is your minimum?", "$500,000 in investable assets, or $250K for clients under 40 on our Ascend program."), ("Where is my money held?", "At Fidelity or Schwab in your name. We never take custody of client assets.")],
  about=("Founded on a simple question: who does your advisor actually work for?", "Elizabeth Meridian spent 14 years at a wirehouse before leaving in 2011 to build a firm without commissions, quotas or proprietary products. Meridian has grown to $1.4B under management on one principle: advice you'd give your own family."),
  email="hello@meridianwealth.com", phone="+1 (617) 555-0128", address="200 Clarendon St, 30th Floor, Boston, MA"),

 "it_services": dict(brand="Vantage Point IT", industry="IT Services", mood="moody", primary="#6366F1", secondary="#22D3EE",
  badge="Managed IT & cybersecurity · 15-minute response SLA", title="Your IT department, without the overhead.", sub="Fully managed IT, 24/7 security operations and cloud migration for businesses with 20–500 employees. Flat monthly pricing. A human answers in 15 minutes or less.",
  cta="Get a free IT audit", cta2="See our SLA", hero=img("photo-1558494949-ef010cbdcc31"), video=YT.format("managed+service+provider+security+operations+center"),
  gallery=["photo-1551288049-bebda4e38f71", "photo-1573164713714-d95e436ab8d6", "photo-1518770660439-4636190af475", "photo-1544197150-b99a580bb7a8", "photo-1531482615713-2afd69097998", "photo-1563986768609-322da13575f2"],
  sections=["solutions", "technologies", "cases", "sla", "stats", "video", "testimonials", "audit", "faq"],
  solutions=("Solutions", "Everything a modern business needs to run securely.", [("Managed IT", "Unlimited helpdesk, patching, backups and on-site support for one flat monthly fee per user.", "Shield"), ("Cybersecurity (MDR)", "24/7 SOC with EDR, SIEM and human threat hunting. Mean time to contain: 11 minutes.", "Zap"), ("Cloud & Microsoft 365", "Migration, tenant hardening and licence optimization — most clients save 18% on M365.", "Globe"), ("Compliance", "SOC 2, HIPAA, PCI and CMMC readiness with evidence collection automated.", "Star"), ("Backup & DR", "Immutable backups tested monthly; 4-hour recovery time objective, guaranteed.", "Heart"), ("vCIO strategy", "Quarterly roadmap and budget planning with a fractional CIO.", "Sparkles")]),
  technologies=("Technologies", ["Microsoft 365", "Azure", "AWS", "CrowdStrike", "SentinelOne", "Fortinet", "Cisco Meraki", "Datto", "KnowBe4", "Okta"]),
  cases=("Case Studies", [("A 180-person law firm was hit by ransomware at 2:14 AM. Our SOC isolated the endpoint in 9 minutes; zero data loss, zero downtime by morning.", "Lindsay Carter", "Managing Partner, Carter & Associates LLP"), ("Migrated 340 users from on-prem Exchange to M365 over one weekend. Monday morning ticket volume: three.", "Ahmed Siddiqui", "COO, Prairie Logistics"), ("Passed our first SOC 2 Type II audit with zero exceptions, eleven weeks after engaging Vantage Point.", "Nina Rossi", "CTO, Ledgerly")]),
  sla=("SLA Guarantee", "15-minute response, 4-hour resolution on priority-1 issues, 99.9% uptime on managed infrastructure — or we credit 10% of that month's invoice. Automatically.", "Read the full SLA"),
  stats=[("15 min", "Guaranteed response time"), ("11 min", "Mean time to contain threats"), ("99.96%", "Uptime, trailing 12 months"), ("4.9 / 5", "Ticket satisfaction, 31K tickets")],
  quotes=[("We went from a 'guy who does IT' to a full security operation for less than his salary.", "Lindsay Carter", "Managing Partner, Carter & Associates LLP"), ("The vCIO reviews changed how we budget. Technology stopped being a surprise line item.", "Ahmed Siddiqui", "COO, Prairie Logistics"), ("Tickets actually get answered by someone who already knows our environment.", "Nina Rossi", "CTO, Ledgerly")],
  audit=("Free Audit", "A 60-minute security and infrastructure audit with a written risk report you keep — whether you hire us or not.", "Get a free IT audit"),
  faq=[("How is pricing structured?", "Flat per-user, per-month pricing that includes unlimited support. No hourly billing, ever."), ("Do you replace our internal IT person?", "Often we work alongside them — we take on security, infrastructure and after-hours so they can focus on the business."), ("What happens during onboarding?", "A 30-day discovery, documentation and hardening phase. Most clients see their security score double in the first month.")],
  about=("Founded by two engineers who were tired of break-fix IT.", "Marcus Vance and Elena Petrov met running infrastructure for a hospital network. They saw small businesses paying hourly for problems that should never have happened. Vantage Point launched in 2013 on a flat-fee model that makes prevention the profit centre. Today 48 engineers protect 9,200 endpoints across 140 clients."),
  team=[("Marcus Vance", "Co-founder & CEO"), ("Elena Petrov", "Co-founder & CISO"), ("Jordan Kim", "Director, Security Operations"), ("Fatima Al-Sayed", "vCIO Practice Lead")],
  email="hello@vantagepointit.com", phone="+1 (206) 555-0177", address="1201 3rd Ave, Suite 2200, Seattle, WA"),

 "creative_studio": dict(brand="Nocturne Studios", industry="Creative Studio", mood="moody", primary="#F43F5E", secondary="#A78BFA",
  badge="Photo · Film · Sound · Bookable by the hour", title="Three studios. Blackout-ready. Yours by the hour.", sub="A 9,000 sq ft creative complex with a cyclorama photo stage, a soundproofed recording suite and a colour-graded edit room — bookable online with instant confirmation.",
  cta="Book a studio", cta2="Take the virtual tour", hero=img("photo-1598488035139-bdbb2231ce04"), video=YT.format("photography+studio+cyclorama+tour"),
  gallery=["photo-1519741497674-611481863552", "photo-1478737270239-2f02b77fc618", "photo-1493225457124-a3eb161ffa5f", "photo-1516280440614-37939bbacd81", "photo-1511379938547-c1f69419868d", "photo-1554048612-b6a482bc67e5"],
  sections=["services", "gallery", "plans", "stats", "video", "team", "testimonials", "booking", "faq"],
  services=("The Studios", "Purpose-built spaces with the gear already in the room.", [("Studio A — Cyclorama", "40×30 ft white cyc, 16 ft ceilings, Profoto D2 kit, drive-in access for vehicles.", "Star"), ("Studio B — Daylight loft", "North-facing windows, exposed brick, styling room and a kitchen set.", "Sparkles"), ("The Booth — Recording", "Neumann U87, Apollo x8, treated live room for podcasts, VO and vocals.", "Zap"), ("Edit & Colour Suite", "DaVinci Resolve, calibrated Eizo reference, 5.1 monitoring.", "Globe"), ("Equipment rental", "Cameras, lenses, lighting and grip — reserve with your booking.", "Shield"), ("Producers & crew", "Photographers, engineers and assistants on call.", "Heart")]),
  gallery_heading="Shot at Nocturne",
  plans=("Rates", [("Hourly", "$95", ["Any studio, 2-hr minimum", "Basic lighting kit", "Wi-Fi & coffee"]), ("Half day", "$420", ["5 hours", "Full lighting & grip", "Styling room", "Assistant on request"]), ("Full day", "$740", ["10 hours", "Two studios", "Edit suite access", "Free parking for 4"])]),
  stats=[("9,000", "Square feet"), ("2,300+", "Shoots hosted"), ("< 1 min", "Online booking confirmation"), ("$0", "Overtime penalties for members")],
  team=[("Iris Nakamura", "Founder & Studio Director"), ("Devon Clarke", "Head Audio Engineer"), ("Maya Osei", "Studio Manager"), ("Felix Brandt", "Colourist")],
  quotes=[("Shot a 40-look e-commerce catalogue in Studio A in one day. The cyc was spotless and the D2s were already set up when we walked in.", "Lena Sørensen", "Photographer, Sørensen Studio"), ("The Booth is the quietest room I've recorded in outside of LA. Our podcast went from 'fine' to 'wow, what mic is that'.", "Chris Okafor", "Host, The Long Game"), ("Booked at 11 PM for a 7 AM shoot. Instant confirmation, code on the door. That's how it should work.", "Priya Menon", "Producer, Bloom Agency")],
  booking=("Book in seconds.", "Live calendar, instant confirmation, a keypad code sent to your phone. Deposits refundable up to 48 hours before.", "Book a studio"),
  faq=[("Can I bring my own gear?", "Of course. Load in via the drive-in door for Studio A or the freight lift for B."), ("Is there parking?", "Four spots included on full-day bookings; street and lot parking nearby."), ("Do you offer memberships?", "Yes — 20 hours a month from $1,200 with no overtime charges and priority booking.")],
  about=("Built by a photographer who was tired of renting other people's problems.", "Iris Nakamura spent a decade shooting in studios with broken lights, surprise fees and no one answering the phone. Nocturne opened in 2018 in a former textile warehouse with one rule: the room is ready when you arrive. Now three studios, one booking system, 2,300 shoots and counting."),
  email="book@nocturnestudios.co", phone="+1 (213) 555-0150", address="800 Traction Ave, Los Angeles, CA"),

 "logistics": dict(brand="Northline Freight Systems", industry="Internal Tools", mood="industrial", primary="#F59E0B", secondary="#38BDF8",
  badge="Asset-based · 340 trucks · 99.2% on-time", title="Freight that arrives when we said it would.", sub="Regional LTL, dedicated fleet and cross-border trucking across the Midwest and Ontario — tracked live, delivered on time 99.2% of the time.",
  cta="Get a freight quote", cta2="Track a shipment", hero=img("photo-1601584115197-04ecc0da31d7"), video=YT.format("trucking+logistics+fleet+operations"),
  gallery=["photo-1586528116311-ad8dd3c8310d", "photo-1494412574643-ff11b0a5c1c3", "photo-1519003722824-194d4455a60c", "photo-1578575437130-527eed3abbec", "photo-1566576912321-d58ddd7a6088", "photo-1553413077-25b1c8fbb0dd"],
  sections=["services", "areas", "stats", "safety", "video", "testimonials", "certs", "quote", "faq"],
  services=("Services", "Every mode we run, we own the equipment for.", [("Regional LTL", "Next-day service across 11 states and Ontario with 34 terminals.", "Zap"), ("Dedicated fleet", "Drivers, tractors and trailers branded and scheduled exclusively for you.", "Shield"), ("Cross-border", "Bonded carrier with C-TPAT and PIP; customs paperwork handled in-house.", "Globe"), ("Temperature-controlled", "Reefer fleet with live temp telemetry and 2-hour excursion alerts.", "Star"), ("Warehousing", "420,000 sq ft across three facilities with cross-dock and pick-pack.", "Heart"), ("Final mile", "Liftgate, inside delivery and appointment scheduling for B2B and retail.", "Sparkles")]),
  areas=("Service Areas", ["Chicago", "Detroit", "Toronto", "Milwaukee", "Indianapolis", "Columbus", "Minneapolis", "Buffalo"]),
  stats=[("99.2%", "On-time delivery, trailing 12 mo"), ("340", "Company-owned tractors"), ("0.31", "DOT crash rate per M miles"), ("1.8M", "Shipments last year")],
  safety=("Safety Record", [("m", "2021", "v", 0.62), ("m", "2022", "v", 0.51), ("m", "2023", "v", 0.44), ("m", "2024", "v", 0.36), ("m", "2025", "v", 0.31)], "DOT-recordable crashes per million miles — national average is 0.58."),
  certs=("Certifications", ["C-TPAT", "PIP Certified", "SmartWay Partner", "ISO 9001", "FMCSA Satisfactory", "HazMat Certified"]),
  quotes=[("Northline took our on-time rate from 91% to 99% in one quarter. Our retail chargebacks basically disappeared.", "Susan Park", "VP Supply Chain, Great Lakes Foods"), ("The reefer telemetry alerted us to a door left open at a dock — before the load was compromised. That's a $40K save.", "Derek Holmes", "Logistics Manager, FreshPoint"), ("Cross-border with them is boring, which is exactly what we want.", "Marie Dubois", "Operations Director, Lavalle Industries")],
  quote=("Request a Quote", "Send us your lanes and volumes. A pricing analyst will respond within four business hours.", "Get a freight quote"),
  faq=[("Do you use brokers or third-party carriers?", "No. Every load moves on Northline equipment with Northline drivers."), ("How do I track a shipment?", "Live GPS tracking and ETA updates in the customer portal, plus EDI 214 status messages."), ("What is your claims ratio?", "0.04% of shipments — one of the lowest in regional LTL.")],
  about=("Started with two trucks and a Chicago dock in 1994.", "Bill Halloran drove his own truck for 15 years before buying a second one and hiring his brother. Northline now runs 340 tractors from 34 terminals, but Bill's rule hasn't changed: the driver is the most important person in the company. That's why our turnover is a third of the industry average — and why your freight arrives."),
  team=[("Bill Halloran", "Founder & Chairman"), ("Karen Halloran-Reyes", "CEO"), ("Luis Fernández", "VP Safety & Compliance"), ("Grace Liu", "Director of Customer Operations")],
  email="quotes@northlinefreight.com", phone="+1 (312) 555-0177", address="4500 S Kilbourn Ave, Chicago, IL"),

 "saas": dict(brand="Orbit Customer Success", industry="SaaS Portals", mood="moody", primary="#06B6D4", secondary="#A78BFA",
  badge="SOC 2 Type II · Trusted by 1,200 CS teams", title="Turn churn signals into renewals.", sub="Orbit unifies product usage, support tickets and sentiment into one health score, then tells your customer success team who to call today — and what to say.",
  cta="Book a walkthrough", cta2="Watch 2-min tour", hero=img("photo-1551288049-bebda4e38f71"), video=YT.format("customer+success+platform+demo"),
  gallery=["photo-1460925895917-afdab827c52f", "photo-1504868584819-f8e8b4b6d7e3", "photo-1553877522-43269d4ea984", "photo-1531403009284-440f080d1e12", "photo-1519389950473-47ba0277781c", "photo-1522071820081-009f0129c71c"],
  sections=["services", "logos", "stats", "video", "plans", "testimonials", "faq", "cta"],
  services=("Platform", "Everything your CS team needs in one workspace.", [("Health scoring", "Blend product usage, tickets and NPS into a score that predicts churn 60 days out with 87% accuracy.", "Heart"), ("AI copilot", "Draft renewal emails, QBR decks and risk summaries from live account data.", "Sparkles"), ("Playbooks", "Trigger tasks, emails and Slack alerts automatically when risk changes.", "Zap"), ("Revenue forecasting", "Renewal and expansion forecasts your CFO will actually trust.", "Star"), ("Customer portal", "Shared success plans and roadmaps your customers can see.", "Globe"), ("Integrations", "Salesforce, HubSpot, Zendesk, Intercom, Snowflake and 40 more.", "Shield")]),
  logos=("Trusted by teams at", ["Relay", "Northwind", "Grid", "Lattice", "Vercel", "Loom"]),
  stats=[("+16 pts", "Avg. NRR lift in year one"), ("87%", "Churn prediction accuracy"), ("1,200", "CS teams on Orbit"), ("< 2 wks", "Median time to go live")],
  plans=("Pricing", [("Team", "$79", ["5 seats", "Health scores", "Email support"]), ("Business", "$249", ["25 seats", "AI copilot", "Playbooks", "Salesforce sync"]), ("Scale", "$799", ["Unlimited seats", "SSO + audit log", "Dedicated CSM", "Custom models"])]),
  quotes=[("Net revenue retention went from 96% to 112% in twelve months. Orbit told us which accounts to save and we saved them.", "Jordan Blake", "VP Customer Success, Relay"), ("The copilot writes better QBRs than I do, in about four seconds.", "Sam Okafor", "Senior CSM, Northwind"), ("Finally one source of truth for accounts. Our board deck comes straight from Orbit.", "Lena Fischer", "COO, Grid")],
  faq=[("Which CRMs do you integrate with?", "Salesforce, HubSpot and Pipedrive natively; anything else via our API or Zapier."), ("Is my data used to train models?", "Never. Your workspace is isolated, encrypted and never used for training."), ("How long is onboarding?", "Most teams are live in under two weeks with a dedicated implementation lead.")],
  about=("Built by CS leaders who were tired of spreadsheets.", "Orbit's founders ran customer success at two high-growth SaaS companies and spent Sunday nights in spreadsheets guessing who might churn. In 2020 they built the tool they wished they'd had. Today 1,200 CS teams use Orbit to protect $4B in recurring revenue."),
  team=[("Maya Lindqvist", "Co-founder & CEO"), ("Arjun Mehta", "Co-founder & CTO"), ("Sofia Reyes", "VP Customer Success"), ("Tom Becker", "Head of Product")],
  email="sales@orbitportal.ai", phone="+1 (415) 555-0199", address="500 Howard St, San Francisco, CA"),

 "legal": dict(brand="Whitfield & Grant LLP", industry="Legal", mood="corporate", primary="#B45309", secondary="#94A3B8",
  badge="Est. 1992 · 40+ attorneys · Free case evaluation", title="Serious counsel for the moments that decide everything.", sub="A litigation and corporate law firm representing businesses, executives and families across commercial disputes, employment, real estate and estate planning.",
  cta="Request a consultation", cta2="Our practice areas", hero=img("photo-1589829545856-d10d557cf95f"), video=YT.format("law+firm+overview+attorneys"),
  gallery=["photo-1505664194779-8beaceb93744", "photo-1450101499163-c8848c66ca85", "photo-1521791136064-7986c2920216", "photo-1507679799987-c73779587ccf", "photo-1479142506502-19b3a3b7ff33", "photo-1556761175-4b46a572b786"],
  sections=["services", "team", "results", "certs", "stats", "video", "testimonials", "consult", "faq"],
  services=("Practice Areas", "Focused expertise, coordinated under one roof.", [("Commercial litigation", "Contract disputes, shareholder actions and injunctions in state and federal court, with a 78% pre-trial resolution rate.", "Shield"), ("Employment law", "Executive agreements, wrongful dismissal, non-competes and workplace investigations for employers and senior employees.", "Users"), ("Corporate & M&A", "Formation, financing rounds, acquisitions and governance for companies from seed to $500M exit.", "Star"), ("Real estate", "Commercial leasing, acquisitions, zoning and construction disputes.", "Globe"), ("Estate planning", "Wills, trusts, powers of attorney and probate administration for families and business owners.", "Heart"), ("Intellectual property", "Trademark registration, licensing and enforcement.", "Sparkles")]),
  team_heading="Our Attorneys",
  team=[("Margaret Whitfield, QC", "Managing Partner · Litigation"), ("David Grant", "Partner · Corporate & M&A"), ("Olivia Chen", "Partner · Employment"), ("Samuel Adeyemi", "Senior Associate · Real Estate")],
  results=("Case Results", [("m", "2021", "v", 38), ("m", "2022", "v", 51), ("m", "2023", "v", 64), ("m", "2024", "v", 82), ("m", "2025", "v", 97)], "Client recoveries and savings secured, in $ millions, per year."),
  certs=("Recognition", ["Chambers & Partners", "Best Lawyers 2025", "Super Lawyers", "Lexpert Ranked", "Martindale AV Preeminent", "Law Society Certified Specialists"]),
  stats=[("$340M", "Recovered for clients"), ("78%", "Disputes resolved before trial"), ("33 yrs", "Serving the region"), ("4.9★", "Client rating, 410 reviews")],
  quotes=[("Whitfield & Grant took over a shareholder dispute two firms had stalled for 18 months and settled it in four, on terms better than we'd hoped for.", "Andrew Kessler", "CEO, Kessler Manufacturing"), ("Olivia rewrote our executive agreements and handled a difficult termination without a single claim being filed.", "Priya Raman", "VP People, Halcyon Software"), ("David closed our $42M acquisition on schedule despite a hostile seller. Calm, precise, relentless.", "Michael Torres", "Founder, Torres Logistics Group")],
  consult=("Free Case Evaluation", "Tell us what happened. An attorney — not an intake clerk — will review your matter and respond within one business day.", "Request a consultation"),
  faq=[("How do you bill?", "Hourly, flat-fee and contingency arrangements depending on the matter. Every engagement starts with a written estimate."), ("Do you handle matters outside the region?", "Yes — we're admitted in three jurisdictions and work with a national network of co-counsel."), ("Is my consultation confidential?", "Absolutely. Everything you share is protected by attorney-client privilege from the first call.")],
  about=("Founded on the belief that clients deserve partners, not associates.", "Margaret Whitfield and David Grant left a national firm in 1992 because their clients rarely saw the lawyer they'd hired. At Whitfield & Grant, every matter is led by a partner, every phone call is returned the same day, and every invoice is explained line by line. Thirty-three years and $340M in client recoveries later, that hasn't changed."),
  email="intake@whitfieldgrant.law", phone="+1 (416) 555-0190", address="181 Bay St, Suite 4400, Toronto, ON"),

 "education": dict(brand="Brightwater Academy", industry="Education", mood="clinical", primary="#0EA5E9", secondary="#FBBF24",
  badge="JK–Grade 12 · Now enrolling for September", title="Small classes. Big futures.", sub="An independent day school where 14-student classes, a project-based curriculum and dedicated learning specialists prepare every student for university and for life.",
  cta="Book a campus tour", cta2="Apply now", hero=img("photo-1523050854058-8df90110c9f1"), video=YT.format("independent+school+campus+tour"),
  gallery=["photo-1509062522246-3755977927d7", "photo-1427504494785-3a9ca7044f45", "photo-1503676260728-1c00da094a0b", "photo-1524178232363-1fb2b075b655", "photo-1571260899304-425eee4c7efc", "photo-1580582932707-520aed937b7b"],
  sections=["services", "team", "stats", "plans", "video", "testimonials", "certs", "tour", "faq"],
  services=("Programs", "A curriculum built around how children actually learn.", [("Lower School (JK–5)", "Literacy and numeracy foundations, daily outdoor learning and French from JK.", "Heart"), ("Middle School (6–8)", "Advisory groups, interdisciplinary projects and a 1:1 laptop program.", "Star"), ("Upper School (9–12)", "AP courses, university counselling from Grade 9 and a capstone research project.", "Sparkles"), ("Learning support", "Certified learning specialists and individualized education plans at no extra cost.", "Shield"), ("Arts & athletics", "Orchestra, theatre, robotics and 22 competitive teams.", "Zap"), ("Before & after care", "7:15 AM to 6:00 PM with homework club and enrichment clubs.", "Clock")]),
  team_heading="Faculty & Leadership",
  team=[("Dr. Helen Marsh", "Head of School"), ("Jonathan Reyes", "Head of Upper School"), ("Amina Yusuf", "Director of Learning Support"), ("Claire Dubois", "Director of Admissions")],
  stats=[("14", "Average class size"), ("100%", "University acceptance, 5 yrs running"), ("$2.1M", "Scholarships awarded last year"), ("9:1", "Student-to-teacher ratio")],
  plans=("Tuition & Fees", [("Lower School", "$21,400", ["JK–Grade 5", "Includes lunch & materials", "Before/after care available"]), ("Middle School", "$24,900", ["Grades 6–8", "1:1 laptop included", "Outdoor education trip"]), ("Upper School", "$27,800", ["Grades 9–12", "AP courses", "University counselling"])]),
  quotes=[("Our daughter went from dreading school to leading the robotics team. The learning specialists identified her dyslexia in Grade 3 and built a plan that actually worked.", "Karen & Tom Mitchell", "Parents, Grade 7 student"), ("Brightwater's university counselling started in Grade 9. My son had offers from four of his five choices, two with scholarships.", "Deepa Nair", "Parent, Class of 2025"), ("I've taught in three schools. This is the first where the class size lets me know every student's strengths by October.", "Ms. Laura Benson", "Grade 4 teacher, 8 years")],
  certs=("Accreditation", ["CAIS Accredited", "Ontario Ministry Inspected", "AP Authorized School", "IB Candidate School", "Round Square Member", "Green School Certified"]),
  tour=("Book a Campus Tour", "Spend a morning with us: meet teachers, sit in on a class and talk to current students. Tours run Tuesdays and Thursdays.", "Book a campus tour"),
  faq=[("What is the admissions process?", "Application, a classroom visit day for the student, a family interview and a report card review. Decisions within three weeks."), ("Is financial aid available?", "Yes — 22% of families receive need-based assistance ranging from 10% to 80% of tuition."), ("Do you offer bus transportation?", "Six routes across the city with door-to-door service for Lower School students.")],
  about=("Founded by teachers who wanted to teach children, not manage crowds.", "Brightwater opened in 1998 with 46 students in a converted church hall and a promise to parents: your child will be known. Today 620 students learn on a 12-acre campus, but the class cap of 14 has never moved — because knowing every student is still the whole point."),
  email="admissions@brightwateracademy.ca", phone="+1 (905) 555-0136", address="880 Lakeshore Rd E, Oakville, ON"),

 "real_estate": dict(brand="Harbour & Vale Realty", industry="Real Estate", mood="luxury", primary="#10B981", secondary="#D4A574",
  badge="$480M sold in 2025 · Top 1% brokerage", title="Homes worth coming home to.", sub="A boutique brokerage of 24 agents selling luxury residential and investment property across the city and the lake district — with data-driven pricing and white-glove marketing.",
  cta="Get a free home valuation", cta2="Browse listings", hero=img("photo-1600596542815-ffad4c1539a9"), video=YT.format("luxury+real+estate+home+tour"),
  gallery=["photo-1600585154340-be6161a56a0c", "photo-1600607687939-ce8a6c25118c", "photo-1613490493576-7fde63acd811", "photo-1512917774080-9991f1c4c750", "photo-1568605114967-8130f3a36994", "photo-1600047509807-ba8f99d2cdde"],
  sections=["featured", "services", "team", "stats", "video", "testimonials", "areas", "valuation", "faq"],
  featured=("Featured Listings", "A selection of homes currently represented by Harbour & Vale."),
  services=("Services", "Whether you're selling, buying or investing, one dedicated agent leads your file end to end.", [("Selling", "Pre-listing staging, professional photography, 3D tours and a 21-day launch plan. Our listings sell 9 days faster than market.", "Star"), ("Buying", "Off-market access, comparative pricing analysis and negotiation that saved buyers an average of 3.2% last year.", "Heart"), ("Investment", "Cap-rate analysis, multi-unit sourcing and property management referrals.", "Zap"), ("Relocation", "Neighbourhood tours, school guidance and move coordination for families arriving from out of town.", "Globe"), ("Luxury & waterfront", "Discreet marketing and private showings for properties above $2M.", "Sparkles"), ("Commercial", "Retail, office and mixed-use leasing and sales.", "Shield")]),
  team_heading="Our Agents",
  team=[("Victoria Hale", "Broker of Record"), ("Marcus Obi", "Luxury & Waterfront Specialist"), ("Sienna Park", "Buyer Representation Lead"), ("Ravi Menon", "Investment Advisor")],
  stats=[("$480M", "Sold in 2025"), ("9 days", "Faster than market average"), ("102%", "Avg. sale-to-list price"), ("640", "Families moved last year")],
  quotes=[("Victoria priced our home $60K above what two other agents suggested — and it sold in six days with three offers, over asking.", "The Okafor Family", "Sellers, Lakeview"), ("Marcus found us a waterfront property that never hit the market. Closed in 30 days, no bidding war.", "James & Elise Hartmann", "Buyers, Harbour District"), ("Ravi's cap-rate analysis steered us away from a bad triplex and into a fourplex that cash-flows from day one.", "Daniel Wu", "Investor")],
  areas=("Neighbourhoods We Serve", ["Harbour District", "Lakeview", "Old Town", "The Annex", "Riverside", "Vale Heights", "Forest Hill", "The Beaches"]),
  valuation=("Free Home Valuation", "Get a data-backed estimate of your home's value within 24 hours, based on 90 days of comparable sales — no obligation.", "Get my valuation"),
  faq=[("What are your commission rates?", "Competitive and negotiable based on the property and services required. Every agreement is transparent and in writing."), ("How long does it take to sell?", "Our listings average 17 days on market versus 26 for the wider market."), ("Do you work with first-time buyers?", "Absolutely — about a third of our buyers are purchasing their first home.")],
  about=("Twenty-four agents. One standard of care.", "Victoria Hale founded Harbour & Vale in 2011 after a decade at a national franchise where volume mattered more than clients. She capped the brokerage at 24 agents so every file gets a senior, full-time professional. The result: 102% average sale-to-list and a referral rate above 70%."),
  email="hello@harbourvale.com", phone="+1 (647) 555-0182", address="1 Yorkville Ave, Toronto, ON"),

 "restaurant": dict(brand="Ember & Oak", industry="Restaurants", mood="moody", primary="#EF4444", secondary="#F59E0B",
  badge="Wood-fired · Farm-to-table · Reservations recommended", title="Fire, smoke and the season's best ingredients.", sub="A neighbourhood restaurant built around a live-fire hearth, a daily-changing menu from farms within 100 km and a wine list of 140 natural and old-world bottles.",
  cta="Reserve a table", cta2="View tonight's menu", hero=img("photo-1517248135467-4c7edcad34c4"), video=YT.format("wood+fired+restaurant+kitchen+chef"),
  gallery=["photo-1414235077428-338989a2e8c0", "photo-1555396273-367ea4eb4db5", "photo-1559339352-11d035aa65de", "photo-1550966871-3ed3cdb51f8b", "photo-1544025162-d76694265947", "photo-1424847651672-bf20a4b0982b"],
  sections=["services", "gallery", "team", "stats", "video", "testimonials", "plans", "reserve", "faq"],
  services=("The Menu", "Everything touches the fire.", [("From the hearth", "Dry-aged ribeye, whole branzino and heritage pork chops over oak and applewood.", "Zap"), ("Garden", "Ember-roasted vegetables, house ferments and salads picked that morning.", "Heart"), ("Handmade pasta", "Rolled daily: tagliatelle with wild mushroom, agnolotti with brown butter.", "Star"), ("Wood-fired pizza", "72-hour dough, San Marzano tomatoes, 90 seconds at 900°F.", "Sparkles"), ("Dessert", "Burnt honey panna cotta, hearth-baked apple tart, house gelato.", "Globe"), ("Wine & cocktails", "140 natural and old-world wines, smoked cocktails and zero-proof pairings.", "Shield")]),
  gallery_heading="From the kitchen",
  team_heading="The Kitchen",
  team=[("Chef Mateo Rinaldi", "Executive Chef & Owner"), ("Ana Lucía Ferrer", "Chef de Cuisine"), ("Owen Blake", "Sommelier"), ("Jess Morgan", "General Manager")],
  stats=[("100 km", "Max distance for our produce"), ("140", "Wines on the list"), ("4.8★", "Google rating, 2,900 reviews"), ("11", "Partner farms")],
  quotes=[("The ribeye off the hearth is the best steak I've had in the city, and I've had most of them.", "Laura Chen", "Food critic, City Eats"), ("We held our rehearsal dinner in the private room. Mateo built a menu around my grandmother's recipes. People cried.", "Sofia & Marcus Bell", "Private dining guests"), ("A wine list this thoughtful at these prices shouldn't exist. Owen steered us to a $58 bottle that outperformed the $140 one.", "David Park", "Regular since 2020")],
  plans=("Private Dining & Events", [("The Hearth Table", "$95", ["Up to 10 guests", "5-course tasting", "Wine pairing optional"]), ("The Cellar Room", "$120", ["Up to 24 guests", "Family-style menu", "Dedicated server", "AV available"]), ("Full Buyout", "Custom", ["Up to 90 guests", "Custom menu", "Sommelier-led pairing", "Live-fire station"])]),
  reserve=("Reserve a Table", "Book online for parties up to 8. Larger groups and private dining — call us or email events@emberandoak.ca.", "Reserve a table"),
  faq=[("Do you accommodate dietary restrictions?", "Yes — vegan, gluten-free and allergy-aware menus available; tell us when you book."), ("Is there a dress code?", "Smart casual. Come as you are, but maybe not straight from the gym."), ("Do you take walk-ins?", "The bar and hearth counter are always walk-in; the dining room fills 2–3 weeks ahead on weekends.")],
  about=("One hearth, eleven farms, no freezers.", "Mateo Rinaldi grew up cooking over his grandfather's wood fire in Umbria. Ember & Oak opened in 2019 with a single 4-ton oak-fired hearth and a rule: if it can't be sourced within 100 km this week, it isn't on the menu. The kitchen has no freezer. The menu changes every day."),
  email="hello@emberandoak.ca", phone="+1 (416) 555-0147", address="622 Queen St W, Toronto, ON"),

 "events": dict(brand="Lumen Events Co.", industry="Events", mood="moody", primary="#A855F7", secondary="#F472B6",
  badge="Weddings · Corporate · Galas · 400+ events produced", title="Events people talk about for years.", sub="Full-service event design and production — from 40-guest dinners to 2,000-person conferences — with one producer, one budget and zero surprises.",
  cta="Start planning", cta2="See our work", hero=img("photo-1511578314322-379afb476865"), video=YT.format("event+production+gala+wedding+highlights"),
  gallery=["photo-1519167758481-83f550bb49b3", "photo-1464366400600-7168b8af9bc3", "photo-1505236858219-8359eb29e329", "photo-1540575467063-178a50c2df87", "photo-1478147427282-58a87a120781", "photo-1492684223066-81342ee5ff30"],
  sections=["services", "portfolio", "team", "stats", "video", "testimonials", "plans", "certs", "planning", "faq"],
  services=("Services", "Every detail, one accountable team.", [("Weddings", "Design, vendor curation, day-of production and a planner who answers texts at 11 PM.", "Heart"), ("Corporate events", "Product launches, summits and off-sites with AV, staging and registration handled in-house.", "Star"), ("Galas & fundraising", "Auction tech, sponsor activations and run-of-show that keeps 800 guests on schedule.", "Sparkles"), ("Design & décor", "Floral, lighting, furniture and custom builds from our own warehouse.", "Zap"), ("AV & production", "Sound, lighting, LED walls and livestream with our in-house crew.", "Globe"), ("Venue sourcing", "Access to 120 venues, including 14 private estates not listed anywhere.", "Shield")]),
  portfolio=("Recent Work", "A few of the 400+ events we've produced."),
  team=[("Camille Laurent", "Founder & Creative Director"), ("Theo Nakamura", "Head of Production"), ("Bianca Rossi", "Senior Wedding Planner"), ("Andre Mitchell", "Technical Director")],
  stats=[("400+", "Events produced"), ("2,000", "Largest guest count"), ("98%", "Delivered on budget"), ("120", "Venue partners")],
  quotes=[("Our 600-person product launch had a 40-minute run-of-show with zero dead air. Theo's crew made it look effortless.", "Rachel Kim", "VP Marketing, Nimbus Tech"), ("Camille designed a wedding that felt like us, not like Pinterest. Guests are still talking about the lighting a year later.", "Emma & Julian Reyes", "Married June 2025"), ("Our gala raised 38% more than the previous year. The auction tech and sponsor activations paid for the whole production.", "Dr. Nadia Hussain", "Executive Director, Hope Foundation")],
  plans=("Planning Packages", [("Day-of Coordination", "$3,200", ["Timeline & vendor confirmation", "12 hours on site", "Lead + assistant"]), ("Partial Planning", "$8,500", ["From 4 months out", "Design direction", "Vendor sourcing", "Day-of production"]), ("Full Production", "From $18,000", ["Concept to teardown", "Custom design & builds", "In-house AV", "Dedicated producer"])]),
  certs=("Trusted By", ["Nimbus Tech", "Hope Foundation", "Four Seasons", "Shopify", "Royal Ontario Museum", "TIFF"]),
  planning=("Start Planning", "Tell us the date, the guest count and the feeling you want in the room. A producer will reply within one business day with ideas and a budget range.", "Start planning"),
  faq=[("How far in advance should we book?", "Weddings 10–14 months; corporate events 3–6 months. We hold two rush slots per month."), ("Do you work with our own vendors?", "Yes — we're happy to coordinate vendors you already love, and we vet anyone new."), ("What does full production cost?", "Most full-production events run 12–18% of total event budget. We publish every line item.")],
  about=("Started with a wedding for 40 in a friend's backyard.", "Camille Laurent produced her first event in 2014 with string lights, borrowed tables and a run-of-show on a napkin. The couple's guests booked three more events. Lumen now has a 14-person team, a 6,000 sq ft décor warehouse and in-house AV — and still writes the run-of-show first."),
  email="hello@lumenevents.co", phone="+1 (416) 555-0171", address="99 Sudbury St, Toronto, ON"),
}

# Map every known industry label / template key / demo app to a niche
INDUSTRY_MAP = {"hvac": "hvac", "healthcare": "healthcare", "construction": "construction", "fitness": "fitness", "e-commerce": "retail", "retail": "retail", "hospitality": "hospitality", "finance": "finance", "it services": "it_services", "creative studio": "creative_studio", "service booking": "creative_studio",
                "internal tools": "logistics", "logistics": "logistics", "saas portals": "saas", "saas": "saas", "plumbing": "hvac", "electrical": "hvac", "carpentry": "construction", "health & safety": "construction", "real estate": "real_estate", "education": "education", "legal": "legal", "restaurants": "restaurant", "restaurant": "restaurant", "events": "events", "agency": "saas"}
APP_MAP = {"Nexus Commerce": "retail", "Orbit SaaS Portal": "saas", "Fleet Command": "logistics", "Aura Wellness": "fitness", "Ledger AI Portfolio": "finance", "Studio Booking": "creative_studio"}


def niche_for(app):
    return APP_MAP.get(app.get("name")) or INDUSTRY_MAP.get(str(app.get("industry", "")).lower().strip()) or "saas"


def _blk(t, props, bg="default", align="left", pad="md", hover=None):
    return {"id": _id("blk"), "type": t, "props": props, "style": {"bg": bg, "align": align, "padding": pad, "glass": True,
            "effects": {"reveal": True, "hover": hover if hover is not None else t in ("features", "gallery", "testimonials", "pricing", "logos", "team", "stats", "collection_list")}}}


def _sec(n, key, i, brand):
    """Render one named industry section into a block; i drives alternating backgrounds."""
    bg = "muted" if i % 2 else "default"
    g = lambda k: n.get(k)
    if key in ("services", "categories", "amenities", "schedule", "solutions", "whyus", "dining"):
        h, sub, items = (g(key) + (None,))[:3] if len(g(key)) == 2 else g(key)
        return _blk("features", {"heading": h, "subheading": sub, "items": [{"title": a, "desc": b, "icon": c} for a, b, c in items]}, bg)
    if key in ("plans", "offers", "rooms"):
        h, plans = g(key)
        return _blk("pricing", {"heading": h, "plans": [{"name": a, "price": b, "period": "night" if key == "rooms" else "mo" if key == "plans" and n["industry"] not in ("Creative Studio",) else "", "features": c, "highlight": k == 1} for k, (a, b, c) in enumerate(plans)]}, bg, "center", "lg")
    if key in ("areas", "certs", "insurance", "technologies", "attractions", "compliance", "logos"):
        h, names = g(key)
        return _blk("logos", {"heading": h, "names": names}, bg, "center", "sm")
    if key in ("emergency", "portal", "trial", "sla", "audit", "booking", "quote", "start", "loyalty", "cta", "consult", "tour", "valuation", "reserve", "planning"):
        if key == "cta":
            return _blk("cta", {"title": f"Ready to work with {brand}?", "subtitle": "Talk to a real person today.", "cta": n["cta"]}, "accent", "center", "lg")
        h, sub, cta = g(key)
        return _blk("cta", {"title": h, "subtitle": sub, "cta": cta}, "accent", "center", "lg")
    if key == "stats":
        return _blk("stats", {"heading": "By the numbers", "items": [{"value": v, "label": l} for v, l in n["stats"]]}, bg, "center")
    if key == "team":
        return _blk("team", {"heading": n.get("team_heading", "Meet the team"), "members": [{"name": a, "role": b, "photo": img(FACES[k % len(FACES)], 600)} for k, (a, b) in enumerate(n["team"])]}, bg)
    if key in ("testimonials", "stories", "cases"):
        h = {"testimonials": "What our clients say", "stories": g("stories")[0] if key == "stories" else "", "cases": g("cases")[0] if key == "cases" else ""}[key] or "What our clients say"
        items = n["quotes"] if key == "testimonials" else g(key)[1]
        return _blk("testimonials", {"heading": h, "items": [{"quote": q, "name": a, "role": r} for q, a, r in items]}, bg)
    if key in ("safety", "results"):
        h, series, cap = g(key)
        return _blk("chart", {"heading": h, "caption": cap, "series": [{"m": s[1], "v": s[3]} for s in series]}, bg)
    if key in ("portfolio", "featured", "gallery"):
        h = g(key)[0] if isinstance(g(key), tuple) else n.get("gallery_heading", "Our work")
        return _blk("gallery", {"heading": h, "images": [img(p, 1200) for p in n["gallery"]]}, bg)
    if key == "video":
        return _blk("video", {"heading": "See us in action", "url": n["video"], "caption": f"Inside {brand}."}, bg, "center")
    if key == "faq":
        return _blk("faq", {"heading": "Frequently asked questions", "items": [{"q": q, "a": a} for q, a in n["faq"]]}, bg)
    if key == "locator":
        h, sub, e, p, a = g(key)
        return _blk("contact", {"heading": h, "subtitle": sub, "email": e, "phone": p, "address": a}, bg)
    return None


def extract_brand(app, pages):
    """Real tenant brand data to preserve over sample pack values (pack samples are never treated as real)."""
    samples = {v[k] for v in NICHES.values() for k in ("email", "phone", "address", "brand")}
    placeholder = lambda v: not v or v in samples or "example.com" in str(v).lower() or str(v).lower().startswith("hello@yourbrand")
    prof = app.get("brand_profile") or {}
    b = {"name": app.get("name"), "email": prof.get("email"), "phone": prof.get("phone"), "address": prof.get("address"), "logo": app.get("logo") or prof.get("logo")}
    for pg in pages or []:
        for blk in pg.get("blocks", []):
            p = blk.get("props", {})
            if blk.get("type") == "contact":
                for k in ("email", "phone", "address"):
                    if p.get(k) and not placeholder(p[k]) and not b[k]:
                        b[k] = p[k]
            if blk.get("type") in ("navbar", "footer") and p.get("logo") and not b["logo"]:
                b["logo"] = p["logo"]
    return {k: (None if placeholder(v) and k != "name" else v) for k, v in b.items()}


def build_premium_site(app, niche_key=None, brand=None):
    key = niche_key or niche_for(app)
    n = dict(NICHES[key])
    brand = brand or {}
    if brand.get("name") and app.get("name") not in APP_MAP:
        n["brand"] = brand["name"]
    for k in ("email", "phone", "address"):
        if brand.get(k):
            n[k] = brand[k]
    brand_name = n["brand"] if app.get("name") in APP_MAP or not app.get("name") else app["name"]
    brand_logo = (brand or {}).get("logo") if isinstance(brand, dict) else None
    brand = brand_name
    pages_nav = [("Home", "/"), ("About", "/about"), ("Services", "/services"), ("Contact", "/contact")]
    nav = _blk("navbar", {"brand": brand, **({"logo": brand_logo} if brand_logo else {}), "links": [{"label": a, "href": b} for a, b in pages_nav], "cta": n["cta"]}, hover=False)
    footer = _blk("footer", {"brand": brand, **({"logo": brand_logo} if brand_logo else {}), "tagline": n["sub"][:90].rsplit(" ", 1)[0] + "…", "columns": [{"title": "Company", "links": ["About", "Services", "Careers", "Press"]}, {"title": "Contact", "links": [n["email"], n["phone"], n["address"]]}, {"title": "Legal", "links": ["Privacy", "Terms", "Accessibility"]}]}, hover=False)
    hero = _blk("hero", {"variant": "cover", "badge": n["badge"], "title": n["title"], "subtitle": n["sub"], "cta": n["cta"], "cta2": n["cta2"], "image": n["hero"]}, "default", "left", "lg", hover=False)
    home = [nav, hero] + [b for b in (_sec(n, k, i, brand) for i, k in enumerate(n["sections"])) if b] + [footer]
    at, story = n["about"]
    about = [nav, _blk("hero", {"variant": "cover", "badge": "Our story", "title": at, "subtitle": story, "cta": "Get in touch", "image": img(n["gallery"][1])}, "default", "left", "lg", hover=False),
             _sec(n, "stats", 1, brand), _sec(n, "team", 0, brand), _blk("gallery", {"heading": "Behind the scenes", "images": [img(p, 1200) for p in n["gallery"][2:5]]}, "muted"), footer]
    svc_key = next(k for k in n["sections"] if k in ("services", "schedule", "solutions", "rooms", "categories"))
    services = [nav, _blk("hero", {"variant": "left", "badge": n["industry"], "title": n[svc_key][0] if isinstance(n[svc_key][0], str) else "Services", "subtitle": n["sub"], "cta": n["cta"]}, "default", "left", "md", hover=False),
                _sec(n, svc_key, 1, brand)] + [b for b in (_sec(n, k, i, brand) for i, k in enumerate([k for k in n["sections"] if k in ("plans", "offers", "rooms", "testimonials", "stories", "cases", "faq")], start=2)) if b] + [_sec(n, "cta", 0, brand), footer]
    contact = [nav, _blk("contact", {"heading": "Let's talk", "subtitle": "A real person replies within one business day.", "email": n["email"], "phone": n["phone"], "address": n["address"]}, "default", "left", "lg"), _sec(n, "faq", 1, brand), footer]
    return [("Home", "/", home), ("About", "/about", about), ("Services", "/services", services), ("Contact", "/contact", contact)], theme_for(n), n


async def apply_premium(db, app, niche_key=None):
    existing = await db.pages.find({"app_id": app["app_id"]}, {"_id": 0, "blocks": 1}).to_list(50)
    brand = extract_brand(app, existing)
    pages, theme, n = build_premium_site(app, niche_key, brand)
    await db.pages.delete_many({"app_id": app["app_id"]})
    for i, (pname, slug, blocks) in enumerate(pages):
        await db.pages.insert_one({"page_id": _id("pg"), "app_id": app["app_id"], "name": pname, "slug": slug, "order": i, "blocks": blocks, "updated_at": _now()})
    upd = {"theme": theme, "premium_site_v": 3, "site_niche": niche_key or niche_for(app), "thumbnail": n["hero"], "video_url": n["video"], "preview_enabled": True, "updated_at": _now(), "brand_profile": brand}
    if not app.get("preview_token"):
        upd["preview_token"] = _id("pv") + uuid.uuid4().hex[:8]
    await db.apps.update_one({"app_id": app["app_id"]}, {"$set": upd})
    return {"pages": len(pages), "theme": theme, "niche": upd["site_niche"], "preserved": {k: v for k, v in brand.items() if v}}


async def migrate_all(db):
    """Retroactively redesign every tenant site once (premium_site_v=3)."""
    n = 0
    async for app in db.apps.find({"premium_site_v": {"$ne": 3}}, {"_id": 0}):
        await apply_premium(db, app)
        n += 1
    return n


class RebuildIn(BaseModel):
    niche: Optional[str] = None


def register(api, db, get_current_user, get_user_app, log_activity):
    @api.get("/public/showcase")
    async def public_showcase():
        apps = await db.apps.find({"name": {"$in": list(APP_MAP)}, "preview_enabled": True}, {"_id": 0, "name": 1, "industry": 1, "preview_token": 1, "thumbnail": 1, "video_url": 1, "site_niche": 1}).to_list(20)
        out = []
        for a in apps:
            n = NICHES.get(a.get("site_niche") or APP_MAP.get(a["name"], "saas"))
            out.append({"name": a["name"], "industry": a.get("industry"), "token": a.get("preview_token"), "thumbnail": a.get("thumbnail"), "video": a.get("video_url"), "niche": a.get("site_niche") or APP_MAP.get(a["name"]),
                        "brand": n["brand"], "tagline": n["title"], "summary": n["sub"], "sections": n["sections"], "primary": n["primary"]})
        return out

    @api.get("/site-niches")
    async def list_niches(user: dict = Depends(get_current_user)):
        return [{"key": k, "brand": v["brand"], "industry": v["industry"], "mood": v["mood"], "primary": v["primary"], "secondary": v["secondary"], "hero": v["hero"], "title": v["title"], "sections": v["sections"]} for k, v in NICHES.items()]

    @api.post("/apps/{app_id}/site/niche-preview")
    async def niche_preview(app_id: str, body: RebuildIn, user: dict = Depends(get_current_user)):
        app = await get_user_app(app_id, user)
        if body.niche not in NICHES:
            raise HTTPException(404, "Unknown niche")
        existing = await db.pages.find({"app_id": app_id}, {"_id": 0, "blocks": 1}).to_list(50)
        brand = extract_brand(app, existing)
        pages, theme, n = build_premium_site(app, body.niche, brand)
        return {"niche": body.niche, "brand": n["brand"], "theme": theme, "preserved": {k: v for k, v in brand.items() if v}, "pages": [{"name": a, "slug": b, "blocks": c} for a, b, c in pages]}

    class VoteIn(BaseModel):
        niche: str
        note: Optional[str] = None

    @api.get("/apps/{app_id}/site/look-options")
    async def look_options(app_id: str, user: dict = Depends(get_current_user)):
        app = await get_user_app(app_id, user)
        cur = app.get("site_niche") or niche_for(app)
        mood = NICHES[cur]["mood"]
        keys = [cur] + [k for k, v in NICHES.items() if k != cur and v["mood"] == mood][:2] + [k for k, v in NICHES.items() if k != cur and v["mood"] != mood][:2]
        return {"current": cur, "vote": app.get("look_vote"), "options": [{"key": k, "brand": app["name"], "sample": NICHES[k]["brand"], "industry": NICHES[k]["industry"], "mood": NICHES[k]["mood"], "primary": NICHES[k]["primary"], "secondary": NICHES[k]["secondary"], "hero": NICHES[k]["hero"], "title": NICHES[k]["title"], "bg": MOODS[NICHES[k]["mood"]]["bg"], "font": MOODS[NICHES[k]["mood"]]["font_heading"]} for k in keys[:5]]}

    @api.post("/apps/{app_id}/site/look-vote")
    async def look_vote(app_id: str, body: VoteIn, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        if body.niche not in NICHES:
            raise HTTPException(404, "Unknown niche")
        vote = {"niche": body.niche, "label": NICHES[body.niche]["industry"], "by": user.get("name") or user["email"], "user_id": user["user_id"], "note": (body.note or "")[:300], "voted_at": _now(), "applied": False}
        await db.apps.update_one({"app_id": app_id}, {"$set": {"look_vote": vote}})
        await log_activity(app_id, user["user_id"], "look.voted", f"Client voted for the {vote['label']} look ({body.niche})")
        return vote

    @api.post("/apps/{app_id}/site/premium-rebuild")
    async def premium_rebuild(app_id: str, body: RebuildIn, user: dict = Depends(get_current_user)):
        app = await get_user_app(app_id, user)
        if body.niche and body.niche not in NICHES:
            raise HTTPException(404, "Unknown niche")
        res = await apply_premium(db, app, body.niche)
        if app.get("look_vote") and app["look_vote"].get("niche") == res["niche"]:
            await db.apps.update_one({"app_id": app_id}, {"$set": {"look_vote.applied": True}})
        await log_activity(app_id, user["user_id"], "site.premium", f"Premium redesign applied ({res['niche']})")
        return res
