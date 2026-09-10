"""Second pass: rename visible 'template' copy still stored on clients, pages and activity logs."""
import asyncio
import os
import re

from motor.motor_asyncio import AsyncIOMotorClient

WORDS = [("Templates", "Projects"), ("Template", "Project"), ("templates", "projects"), ("template", "project")]
TARGETS = {
    "apps": ["name", "description", "summary", "tagline"],
    "pages": ["name"],
    "activity_logs": ["message"],
    "case_studies": ["title", "challenge", "outcome", "summary"],
}


def swap(v):
    if not isinstance(v, str):
        return v
    for a, b in WORDS:
        v = re.sub(rf"\b{a}\b", b, v)
    return v


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    total = 0
    for coll, fields in TARGETS.items():
        async for doc in db[coll].find({}):
            patch = {f: swap(doc[f]) for f in fields
                     if isinstance(doc.get(f), str) and re.search(r"\btemplates?\b", doc[f], re.I)}
            patch = {k: v for k, v in patch.items() if v != doc[k]}
            if patch:
                await db[coll].update_one({"_id": doc["_id"]}, {"$set": patch})
                total += 1
    print("documents updated:", total)


asyncio.run(main())
