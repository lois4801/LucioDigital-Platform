"""One-off: write 20 AI reviews for every template + the LucioDigital landing set."""
import asyncio
import os
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import reviews as R    # noqa: E402


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    only = sys.argv[1:] or list(R.BRIEFS.keys())

    async def one(key):
        for attempt in range(3):
            try:
                from emergentintegrations.llm.chat import LlmChat, UserMessage
                chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"reviews-{key}-{attempt}",
                               system_message=R.SYSTEM).with_model("anthropic", "claude-sonnet-4-6")
                raw = await chat.send_message(UserMessage(text=R.PROMPT.format(brief=R.BRIEFS[key])))
                import json
                import re
                txt = re.sub(r"^```(?:json)?|```$", "", str(raw).strip(), flags=re.M).strip()
                data = json.loads(txt[txt.find("{"):txt.rfind("}") + 1])
                rows = data.get("reviews") or []
                if len(rows) < 12:
                    raise ValueError(f"only {len(rows)} reviews")
                decorated = R.decorate(rows[:20], key)
                await db.template_reviews.update_one({"key": key}, {"$set": {
                    "key": key, "reviews": decorated, "source": "ai"}}, upsert=True)
                print(f"OK   {key}: {len(decorated)}", flush=True)
                return
            except Exception as e:
                print(f"retry {key} ({attempt + 1}/3): {e}", flush=True)
                await asyncio.sleep(3)
        print(f"FAIL {key}", flush=True)

    sem = asyncio.Semaphore(4)

    async def guarded(k):
        async with sem:
            await one(k)

    await asyncio.gather(*(guarded(k) for k in only))
    print("done", flush=True)


asyncio.run(main())
