"""Grandfather existing agency accounts so the new membership gate breaks nothing."""
import asyncio
import os
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    admin = (os.environ.get("ADMIN_EMAIL") or "").lower().strip()
    now = datetime.now(timezone.utc).isoformat()
    done = 0
    async for u in db.users.find({}, {"_id": 0, "user_id": 1, "email": 1, "membership": 1}):
        owns = await db.apps.count_documents({"owner_id": u["user_id"]}, limit=1)
        is_admin = (u.get("email") or "").lower().strip() == admin
        if not owns and not is_admin:
            continue                                    # invited client users keep portal access for free
        m = dict(u.get("membership") or {})
        if m.get("grandfathered"):
            continue
        m.update({"status": "active", "grandfathered": True, "manual": True, "suspended": False,
                  "welcomed": True, "updated_at": now})
        await db.users.update_one({"user_id": u["user_id"]}, {"$set": {"membership": m}})
        done += 1
        print("grandfathered", u.get("email"))
    print("accounts updated:", done)


asyncio.run(main())
