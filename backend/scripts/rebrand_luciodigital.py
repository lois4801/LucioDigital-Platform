"""One-off: rewrite the old platform name in persisted documents."""
import asyncio
import os
import re

from motor.motor_asyncio import AsyncIOMotorClient

PAT = re.compile(r"Lois-Tech|Lois Tech|LoisTech|lois-tech")


def fix(v):
    if isinstance(v, str):
        return (v.replace("Lois-Tech", "LucioDigital").replace("Lois Tech", "LucioDigital")
                 .replace("LoisTech", "LucioDigital").replace("lois-tech.ca", "luciodigital.ca")
                 .replace("lois-tech", "luciodigital"))
    if isinstance(v, list):
        return [fix(x) for x in v]
    if isinstance(v, dict):
        return {k: fix(x) for k, x in v.items()}
    return v


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    total = 0
    for name in await db.list_collection_names():
        async for doc in db[name].find({}):
            raw = str({k: v for k, v in doc.items() if k != "_id"})
            if not PAT.search(raw):
                continue
            patch = {k: fix(v) for k, v in doc.items() if k != "_id"}
            await db[name].update_one({"_id": doc["_id"]}, {"$set": patch})
            total += 1
            print(f"{name}: rebranded 1 document")
    print("documents updated:", total)


asyncio.run(main())
