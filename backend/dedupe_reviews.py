"""Make reviewer names (and repeated company names) unique across all 34 review sets.
Quotes are already unique and are never touched."""
import asyncio
import os
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SURNAMES = """Alderton Ashworth Bellamy Bergqvist Blackwood Brannigan Calloway Cardoso Castellan
Chikwendu Delacroix Devlin Draycott Eriksen Falkner Fontaine Gallardo Garnier Halloran Hartigan
Havelock Ijeoma Ishikawa Jovanovic Kaminski Karlsson Keswani Kirkbride Kolawole Larrañaga Lindqvist
Lockhart Machado Maitland Mancini Marchetti Marwood Matsuda Mbeki Mehrotra Merriweather Nakagawa
Navarrete Nkemdirim Nordstrom Okonjo Oyelaran Pemberton Petrossian Quintero Radcliffe Rasmussen
Ravenscroft Redmayne Rosales Salvatore Sandoval Sarpong Sepulveda Shackleton Sinclaire Solberg
Stavros Szymanski Takahara Thackeray Thorvaldsen Trelawney Vasquez Verhoeven Villanueva Waithaka
Whitlock Wickramasinghe Yamazaki Zabala Zielinski Abernathy Ballantyne Cavanaugh Dembele Fitzgerald
Guttierez Hollingworth Ivanovic Jamieson Kowalczyk Lindstrand Montenegro Nwachukwu Oduladipo
Pastorelli Ramaswamy Sandberg Tanaka-Reid Underhill Valdivia Wentworth Xiomara Yusupova Zamorano""".split()

GENERIC = {"homeowner", "parent", "patient", "member", "client", "guest", "resident", "freelancer",
           "customer", "student", "owner", "tenant", "volunteer", "donor", "pet owner"}


def generic(label: str) -> bool:
    low = (label or "").lower()
    return any(g in low for g in GENERIC) or len(low) < 3


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    used_names, used_companies = set(), set()
    fixed_names = fixed_companies = 0
    pool = iter(SURNAMES)

    async for doc in db.template_reviews.find({}, {"_id": 0}).sort("key", 1):
        rows = doc.get("reviews") or []
        for r in rows:
            name = (r.get("name") or "").strip()
            if name.lower() in used_names:
                first = name.split()[0] if name.split() else "Alex"
                for surname in list(SURNAMES):
                    cand = f"{first} {surname}"
                    if cand.lower() not in used_names:
                        r["name"] = cand
                        fixed_names += 1
                        break
                name = r["name"]
            used_names.add(name.lower())

            comp = (r.get("company") or "").strip()
            quote = r.get("quote") or ""
            if comp and not generic(comp) and comp.lower() in used_companies and comp not in quote:
                head = comp.split()[0]
                for surname in list(SURNAMES):
                    cand = f"{surname} {' '.join(comp.split()[1:]) or head}"
                    if cand.lower() not in used_companies:
                        r["company"] = cand
                        fixed_companies += 1
                        break
                comp = r["company"]
            if comp:
                used_companies.add(comp.lower())

        await db.template_reviews.update_one({"key": doc["key"]}, {"$set": {"reviews": rows}})

    print(f"renamed {fixed_names} reviewers, {fixed_companies} companies", flush=True)
    # verify
    seen = {}
    dupes = 0
    async for doc in db.template_reviews.find({}, {"_id": 0}):
        for r in doc["reviews"]:
            k = (r["name"] or "").lower()
            if k in seen and seen[k] != doc["key"]:
                dupes += 1
            seen[k] = doc["key"]
    print("remaining cross-template name collisions:", dupes, flush=True)


asyncio.run(main())
