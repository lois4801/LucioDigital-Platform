"""Client edit log: who changed what on a live site, and when."""
from typing import Any, Dict, List

from fastapi import Depends

# Only content edits that change what a visitor sees. Keyed by activity `kind` prefix.
AREAS = {
    "marquee": "Text ribbon",
    "reviews": "Reviews",
    "vitals": "Figures & charts",
    "onboarding": "Onboarding",
    "anim": "Animations",
    "site_mode": "Design & motion",
    "theme": "Design & motion",
    "look": "Design & motion",
    "cms": "Content",
    "page": "Pages",
    "sections": "Pages",
    "brand": "Branding",
    "file": "Files & media",
    "media": "Files & media",
    "form": "Forms",
    "domain": "Domain",
    "request": "Change requests",
}


def area_of(kind: str) -> str:
    return AREAS.get((kind or "").split(".")[0], "")


def register(api, db, get_current_user, get_user_app):

    @api.get("/apps/{app_id}/edit-log")
    async def edit_log(app_id: str, mine: bool = False, limit: int = 60,
                       user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        q: Dict[str, Any] = {"app_id": app_id}
        if mine:
            q["user_id"] = user["user_id"]
        rows = await db.activity_logs.find(q, {"_id": 0}).sort("created_at", -1).limit(400).to_list(400)
        rows = [r for r in rows if area_of(r.get("kind"))][:max(1, min(limit, 200))]

        ids = list({r["user_id"] for r in rows if isinstance(r.get("user_id"), str)})
        people = await db.users.find({"user_id": {"$in": ids}}, {"_id": 0, "user_id": 1, "name": 1, "email": 1}).to_list(200)
        by_id = {p["user_id"]: p for p in people}
        members = await db.memberships.find({"app_id": app_id, "user_id": {"$in": ids}},
                                            {"_id": 0, "user_id": 1, "role": 1}).to_list(200)
        role_by_id = {m["user_id"]: m.get("role") for m in members}
        app = await db.apps.find_one({"app_id": app_id}, {"_id": 0, "owner_id": 1})

        out: List[Dict[str, Any]] = []
        for r in rows:
            uid = r.get("user_id") if isinstance(r.get("user_id"), str) else ""
            person = by_id.get(uid) or {}
            role = "agency" if uid and uid == (app or {}).get("owner_id") else (role_by_id.get(uid) or "client")
            out.append({"log_id": r.get("log_id"), "kind": r.get("kind"), "area": area_of(r.get("kind")),
                        "message": r.get("message"), "created_at": r.get("created_at"),
                        "actor": person.get("name") or person.get("email") or "Someone",
                        "actor_email": person.get("email") or "", "role": role,
                        "is_you": uid == user["user_id"]})
        areas = sorted({r["area"] for r in out})
        return {"entries": out, "areas": areas, "count": len(out)}
