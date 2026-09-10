"""Re-spread reviewer photos across the widened portrait pool so a single set repeats less."""
import asyncio
import os
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import reviews as R    # noqa: E402


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    n = 0
    async for doc in db.template_reviews.find({}, {"_id": 0}).sort("key", 1):
        rows = doc.get("reviews") or []
        for i, r in enumerate(rows):
            r["photo"] = R.portrait(i * 3 + len(doc["key"]))
        await db.template_reviews.update_one({"key": doc["key"]}, {"$set": {"reviews": rows}})
        n += 1
    print(f"photos re-spread across {len(R.PORTRAITS)} portraits for {n} sets", flush=True)


asyncio.run(main())
