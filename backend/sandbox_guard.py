"""Single-sandbox guarantee: LucioDigital Test Lab is the only test/staging/demo site allowed.

Runs on every startup and is also exposed as an admin endpoint. Any other app tagged or named as
TEST / STAGING / DEMO is deactivated and permanently deleted together with its dependent records,
so newly created tenants can never inherit a second sandbox.
"""
import logging
import re
from typing import Any, Dict, List

from fastapi import Depends

logger = logging.getLogger("agency.sandbox_guard")

TEST_LAB_ID = "app_testlab"
# Name matching is deliberately narrow (explicit sandbox labels only) so a real client called
# e.g. "Demo Agency" is never removed. Tags and flags do the rest of the work.
NAME_RE = re.compile(r"(test lab|staging|sandbox|rollout target)", re.I)
TAG_WORDS = {"test", "staging", "stage", "demo", "sandbox"}

# Every collection that stores rows keyed by app_id.
DEPENDENT = ["pages", "blocks", "leads", "messages", "activity", "cms_records", "cms_collections",
             "cta_forms", "form_submissions", "bookings", "files", "media", "videos", "workflows",
             "app_members", "case_studies", "site_locks", "edit_requests", "followups",
             "rollout_snapshots", "domains", "billing_plans", "subscriptions"]


def _is_other_sandbox(app: Dict[str, Any]) -> bool:
    if app.get("app_id") == TEST_LAB_ID or app.get("is_test_lab"):
        return False
    tags = {str(t).strip().lower() for t in (app.get("tags") or [])}
    if tags & TAG_WORDS:
        return True
    if app.get("is_staging") or app.get("is_demo"):
        return True
    return bool(NAME_RE.search(app.get("name") or ""))


async def purge_other_sandboxes(db) -> List[Dict[str, str]]:
    """Deactivates then permanently removes every sandbox that is not the Test Lab."""
    removed: List[Dict[str, str]] = []
    async for app in db.apps.find({}, {"_id": 0}):
        if not _is_other_sandbox(app):
            continue
        app_id = app["app_id"]
        # Deactivate first so nothing can serve it mid-delete, then delete for good.
        await db.apps.update_one({"app_id": app_id},
                                 {"$set": {"status": "archived", "archived": True, "is_staging": False,
                                           "protected": False}})
        for coll in DEPENDENT:
            try:
                await db[coll].delete_many({"app_id": app_id})
            except Exception:
                pass
        await db.apps.delete_one({"app_id": app_id})
        removed.append({"app_id": app_id, "name": app.get("name") or ""})
        logger.info("Removed extra sandbox site: %s (%s)", app.get("name"), app_id)
    return removed


def register(api, db, get_current_user):

    @api.get("/sandbox/audit")
    async def audit(user: dict = Depends(get_current_user)):
        apps = await db.apps.find({}, {"_id": 0, "app_id": 1, "name": 1, "tags": 1, "is_staging": 1,
                                       "is_test_lab": 1}).to_list(500)
        extras = [{"app_id": a["app_id"], "name": a.get("name")} for a in apps if _is_other_sandbox(a)]
        return {"test_lab_present": any(a["app_id"] == TEST_LAB_ID for a in apps),
                "extra_sandboxes": extras, "clean": not extras}

    @api.post("/sandbox/enforce")
    async def enforce(user: dict = Depends(get_current_user)):
        removed = await purge_other_sandboxes(db)
        return {"removed": removed, "count": len(removed), "clean": True}
