"""One-off restore: a past editorial rollout overwrote every stored template look with a single
identical palette (techno / #22D3EE / Space Grotesk / hero "centered"), which flattened all 33
designs and hid every hero photograph (the "centered" hero variant renders no image).

This restores each template's own palette, typography, radius, preset and hero variant from the
source definitions in site_content.LOOKS while KEEPING every motion key that was rolled out
(editorial flags, ed_hero, ed_layout, ed_reveal_style, ed_counter_style, ed_accent...).
No page, block, copy, image, form, CTA or stat is touched.
"""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

VISUAL_KEYS = ("mode", "primary", "secondary", "bg", "surface", "border", "fg", "muted",
               "font_heading", "font_body", "radius", "preset", "hero", "glass", "grain", "studio")


async def restore(db) -> dict:
    import importlib
    import site_content
    import studio_pack
    importlib.reload(site_content)          # pristine, override-free definitions
    importlib.reload(studio_pack)
    studio_pack.install()                   # the Studio 2026 pack lives in its own module
    SRC = site_content.LOOKS
    fixed, skipped = [], []
    async for doc in db.template_looks.find({}, {"_id": 0}):
        key, look = doc.get("key"), dict(doc.get("look") or {})
        src = SRC.get(key)
        if not src:
            skipped.append(key)
            continue
        motion = {k: v for k, v in look.items() if k.startswith("ed_") or k in ("editorial", "look_v")}
        restored = {**look, **{k: src[k] for k in VISUAL_KEYS if k in src}, **motion}
        await db.template_looks.update_one({"key": key}, {"$set": {"key": key, "look": restored}}, upsert=True)
        fixed.append(key)
    return {"restored": fixed, "skipped": skipped}


async def main():
    from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    res = await restore(db)
    print(f"restored {len(res['restored'])} template looks; skipped {res['skipped']}")


if __name__ == "__main__":
    asyncio.run(main())
