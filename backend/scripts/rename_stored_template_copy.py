"""One-off: rename visible 'template' copy to 'project' inside stored content (reviews, CMS copy)."""
import asyncio
import os
import re

from motor.motor_asyncio import AsyncIOMotorClient

WORDS = [("Templates", "Projects"), ("Template", "Project"), ("templates", "projects"), ("template", "project")]


def swap(v):
    if isinstance(v, str):
        for a, b in WORDS:
            v = re.sub(rf"\b{a}\b", b, v)
        return v
    if isinstance(v, list):
        return [swap(x) for x in v]
    if isinstance(v, dict):
        return {k: (v[k] if k in ("key", "template_key", "slug", "kind", "status") else swap(x)) for k, x in v.items()}
    return v


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    total = 0
    for coll, fields in (("template_reviews", ["reviews"]), ("apps", ["reviews"]), ("site_settings", ["texts", "cards", "marquee"])):
        async for doc in db[coll].find({}):
            patch = {}
            for f in fields:
                if f in doc and re.search(r"\btemplates?\b", str(doc[f]), re.I):
                    patch[f] = swap(doc[f])
            if patch:
                await db[coll].update_one({"_id": doc["_id"]}, {"$set": patch})
                total += 1
    print("documents updated:", total)


asyncio.run(main())
