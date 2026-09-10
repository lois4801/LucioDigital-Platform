"""Rename tenant -> client inside stored content: review copy and landing CMS text."""
import asyncio
import os
import re
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

WORD = re.compile(r"\b(Tenants|tenants|Tenant|tenant)\b")
MAP = {"Tenants": "Clients", "tenants": "clients", "Tenant": "Client", "tenant": "client"}
swap = lambda s: WORD.sub(lambda m: MAP[m.group(1)], s) if isinstance(s, str) else s


def walk(v):
    if isinstance(v, str):
        return swap(v)
    if isinstance(v, list):
        return [walk(x) for x in v]
    if isinstance(v, dict):
        # keys are contracts, values are copy
        return {k: (v[k] if k in ("key", "flag", "id", "photo") else walk(v[k])) for k in v}
    return v


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    n_rev = 0
    async for doc in db.template_reviews.find({}, {"_id": 0}):
        rows = walk(doc.get("reviews") or [])
        if rows != doc.get("reviews"):
            await db.template_reviews.update_one({"key": doc["key"]}, {"$set": {"reviews": rows}})
            n_rev += 1
    print("review sets updated:", n_rev, flush=True)

    for coll in ("landing_cms", "ui_labels", "apps"):
        n = 0
        async for doc in db[coll].find({}):
            patch = {}
            for k, v in doc.items():
                if k in ("_id", "app_id", "key", "user_id", "owner_id", "slug"):
                    continue
                new = walk(v)
                if new != v:
                    patch[k] = new
            if patch:
                await db[coll].update_one({"_id": doc["_id"]}, {"$set": patch})
                n += 1
        print(f"{coll}: {n} docs updated", flush=True)


asyncio.run(main())
