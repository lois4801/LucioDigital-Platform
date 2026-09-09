"""Context-aware modal forms on every CTA button, per tenant.

Forms are provisioned automatically from the tenant's industry template, stored per tenant
(`cta_forms` collection, keyed by app_id + the button label) and are editable live by the agency
admin and by client editors. Nothing is shared between tenants.
"""
import re
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel

# A CTA qualifies when its label implies the visitor wants to act or make contact.
CTA_PATTERN = re.compile(
    r"\b(book|schedule|request|quote|estimate|contact|apply|enquir|inquir|reserve|reservation|"
    r"consult|sign\s?up|get\s?started|learn\s?more|join|register|appointment|tour|call|start|talk|"
    r"demo|availability|valuation|audit|in\s?touch|message|hire|order|subscribe|visit|trial|"
    r"walkthrough|showing|assessment|estimate|plan|quote|speak)\b", re.I)

FIELD_KEYS = ("text", "email", "phone", "date", "time", "number", "checkbox", "select", "toggle", "textarea")


def qualifies(label: str) -> bool:
    return bool(CTA_PATTERN.search(str(label or "").strip()))


def key_of(label: str) -> str:
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", str(label or "").strip().lower()))[:60]


def _f(name, label, type="text", required=False, placeholder="", options=None):
    return {"name": name, "label": label, "type": type, "required": required,
            "placeholder": placeholder, "options": options or []}


NAME = _f("name", "Full name", "text", True, "Jane Doe")
EMAIL = _f("email", "Email", "email", True, "jane@email.com")
def PHONE(req=False): return _f("phone", "Phone", "phone", req, "(416) 555-0188")


MORNING_AFTERNOON_EVENING = ["Morning", "Afternoon", "Evening"]

# Industry-aware defaults. Keys map to site_content.LOOKS niches.
FIELD_SETS = {
    "real_estate": [NAME, EMAIL, PHONE(), _f("interest", "I am interested in", "select", True, "Choose one", ["Buying", "Selling", "Investing"]),
                    _f("contact_time", "Preferred contact time", "text", False, "Weekday evenings"),
                    _f("message", "Message", "textarea", False, "Anything we should know?")],
    "education": [NAME, EMAIL, PHONE(), _f("tour_date", "Preferred tour date", "date", True),
                  _f("tour_time", "Preferred tour time", "select", True, "Choose a window", ["Morning 9am-12pm", "Afternoon 12pm-3pm", "Late Afternoon 3pm-5pm"]),
                  _f("attendees", "Number of people attending", "number", True, "2"),
                  _f("questions", "Questions or special requests", "textarea", False, "Anything you'd like us to cover")],
    "healthcare": [NAME, EMAIL, PHONE(True), _f("reason", "Reason for visit", "textarea", True, "Briefly describe your concern"),
                   _f("appt_date", "Preferred appointment date", "date", True),
                   _f("appt_time", "Preferred appointment time", "select", True, "Choose a window", MORNING_AFTERNOON_EVENING),
                   _f("payment_type", "Payment type", "toggle", True, "", ["Insurance", "Self-Pay"])],
    "fitness": [NAME, EMAIL, PHONE(), _f("service", "Service or class interest", "text", False, "Small-group strength"),
                _f("schedule", "Preferred schedule", "text", False, "Weekday mornings"),
                _f("goals", "Fitness goals", "textarea", False, "What are you training for?")],
    "legal": [NAME, EMAIL, PHONE(True),
              _f("matter", "Type of legal matter", "select", True, "Choose one", ["Family", "Corporate", "Real Estate", "Criminal", "Other"]),
              _f("consult_date", "Preferred consultation date", "date", True),
              _f("consult_time", "Preferred consultation time", "select", True, "Choose a window", MORNING_AFTERNOON_EVENING),
              _f("description", "Brief description", "textarea", True, "A short summary of your matter")],
    "hospitality": [NAME, EMAIL, PHONE(), _f("res_date", "Reservation date", "date", True),
                    _f("party_size", "Party size", "number", True, "2"),
                    _f("requests", "Special requests", "textarea", False, "Dietary needs, occasion, seating")],
    "construction": [NAME, EMAIL, PHONE(True), _f("project_type", "Project type", "text", True, "Roof replacement"),
                     _f("start_date", "Estimated start date", "date", False),
                     _f("budget", "Budget range", "select", False, "Choose a range", ["Under $10K", "$10K-$50K", "$50K-$100K", "$100K+"]),
                     _f("description", "Project description", "textarea", True, "Scope, size and any deadlines")],
}
FALLBACK = [NAME, EMAIL, PHONE(), _f("service", "Service you are interested in", "text", False, "What can we help with?"),
            _f("preferred_date", "Preferred date", "date", False),
            _f("preferred_time", "Preferred time", "select", False, "Choose a window", MORNING_AFTERNOON_EVENING),
            _f("message", "Message", "textarea", False, "Tell us a little more")]

# Restaurant shares the hospitality set; other niches use the fallback.
FIELD_SETS["restaurant"] = FIELD_SETS["hospitality"]


def fields_for(niche: Optional[str]) -> List[dict]:
    import copy
    return copy.deepcopy(FIELD_SETS.get(niche or "", FALLBACK))


def _title_for(label: str) -> str:
    lab = str(label or "").strip()
    return lab if len(lab) > 3 else "Get in touch"


def default_form(app_id: str, label: str, niche: Optional[str]) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "form_id": f"cf_{app_id[-8:]}_{key_of(label)}"[:64],
        "app_id": app_id, "key": key_of(label), "label": label,
        "title": _title_for(label), "subtitle": "Tell us a little about what you need and we'll take it from there.",
        "submit_label": label, "success_title": "Thank you!",
        "success_message": "Thank you! We'll be in touch within 24 hours.",
        "fields": fields_for(niche), "created_at": now, "updated_at": now,
    }


def cta_labels(pages: List[dict]) -> List[str]:
    """Every CTA label on the tenant's pages, in page order, de-duplicated."""
    out, seen = [], set()
    for pg in pages:
        for b in pg.get("blocks") or []:
            p = b.get("props") or {}
            cands = [p.get("cta"), p.get("cta2"), p.get("submit_label")]
            for pl in (p.get("plans") or []):
                if isinstance(pl, dict) and pl.get("name"):
                    cands.append(f"Choose {pl['name']}")
            for c in cands:
                c = str(c or "").strip()
                if c and qualifies(c) and key_of(c) not in seen:
                    seen.add(key_of(c))
                    out.append(c)
    return out


class FieldIn(BaseModel):
    name: str
    label: str
    type: str = "text"
    required: bool = False
    placeholder: str = ""
    options: List[str] = []


class FormIn(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    submit_label: Optional[str] = None
    success_title: Optional[str] = None
    success_message: Optional[str] = None
    fields: Optional[List[FieldIn]] = None


class SubmitIn(BaseModel):
    values: dict = {}


def register(api, db, get_current_user, get_user_app, log_activity, new_message=None):

    async def _role(app_id, user):
        app = await get_user_app(app_id, user)
        from page_guard import role_of
        return app, await role_of(db, app, user)

    async def _provision(app_id: str, niche: Optional[str]):
        """Create any missing form for the tenant's current CTA buttons. Never touches other tenants."""
        pages = await db.pages.find({"app_id": app_id}, {"_id": 0, "slug": 1, "order": 1, "blocks": 1}).to_list(60)
        pages.sort(key=lambda p: (p.get("slug") != "/", p.get("order", 0)))
        made = 0
        for label in cta_labels(pages):
            k = key_of(label)
            if await db.cta_forms.find_one({"app_id": app_id, "key": k}, {"_id": 0, "key": 1}):
                continue
            await db.cta_forms.insert_one(default_form(app_id, label, niche))
            made += 1
        return made

    async def _forms(app_id: str):
        return await db.cta_forms.find({"app_id": app_id}, {"_id": 0}).sort("created_at", 1).to_list(100)

    @api.get("/apps/{app_id}/cta-forms")
    async def list_forms(app_id: str, user: dict = Depends(get_current_user)):
        app, role = await _role(app_id, user)
        created = await _provision(app_id, app.get("site_niche"))
        return {"forms": await _forms(app_id), "provisioned": created,
                "can_edit": role in ("owner", "admin", "editor"),
                "simplified": role not in ("owner", "admin")}

    @api.post("/apps/{app_id}/cta-forms/scan")
    async def scan_forms(app_id: str, user: dict = Depends(get_current_user)):
        app, role = await _role(app_id, user)
        created = await _provision(app_id, app.get("site_niche"))
        return {"provisioned": created, "forms": await _forms(app_id)}

    @api.put("/apps/{app_id}/cta-forms/{form_id}")
    async def update_form(app_id: str, form_id: str, body: FormIn, user: dict = Depends(get_current_user)):
        app, role = await _role(app_id, user)
        if role not in ("owner", "admin", "editor"):
            raise HTTPException(403, "You do not have permission to edit this form")
        doc = await db.cta_forms.find_one({"app_id": app_id, "form_id": form_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Form not found")
        upd = {k: v for k, v in body.model_dump(exclude_none=True).items() if k != "fields"}
        if body.fields is not None:
            fields = [f.model_dump() for f in body.fields]
            for f in fields:
                if f["type"] not in FIELD_KEYS:
                    raise HTTPException(400, f"Unsupported field type: {f['type']}")
            if not any(f["type"] == "email" or f["name"] == "email" for f in fields):
                raise HTTPException(400, "The email field is always required and cannot be removed")
            for f in fields:
                if f["name"] == "email":
                    f["required"] = True
            upd["fields"] = fields
        upd["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.cta_forms.update_one({"app_id": app_id, "form_id": form_id}, {"$set": upd})
        await log_activity(app_id, user["user_id"], "form.updated", f"Form '{doc['label']}' updated")
        return await db.cta_forms.find_one({"app_id": app_id, "form_id": form_id}, {"_id": 0})

    # ---------- public site ----------
    async def _site(token: str):
        doc = await db.apps.find_one({"preview_token": token, "preview_enabled": True}, {"_id": 0, "app_id": 1, "name": 1, "site_niche": 1})
        if not doc:
            raise HTTPException(404, "Preview link is invalid or has been revoked")
        return doc

    @api.get("/public/site/{token}/cta-forms")
    async def public_forms(token: str):
        doc = await _site(token)
        await _provision(doc["app_id"], doc.get("site_niche"))
        forms = await _forms(doc["app_id"])
        return {"forms": {f["key"]: f for f in forms}}

    @api.post("/public/site/{token}/cta-forms/{form_id}/submit")
    async def public_submit(token: str, form_id: str, body: SubmitIn, request: Request):
        doc = await _site(token)
        form = await db.cta_forms.find_one({"app_id": doc["app_id"], "form_id": form_id}, {"_id": 0})
        if not form:
            raise HTTPException(404, "Form not found")
        vals = body.values or {}
        for f in form["fields"]:
            if f.get("required") and not str(vals.get(f["name"], "")).strip():
                raise HTTPException(400, f"{f['label']} is required")
        name = str(vals.get("name") or "Website visitor")[:120]
        email = str(vals.get("email") or "").lower()[:160]
        lines = [f"{f['label']}: {vals.get(f['name'], '')}" for f in form["fields"] if str(vals.get(f["name"], "")).strip()]
        body_text = f"{form['label']}\n\n" + "\n".join(lines)
        meta = {"form_label": form["label"], "cta_form_id": form_id, "values": {k: str(v)[:2000] for k, v in vals.items()}}
        if new_message:
            doc_msg = await new_message(doc["app_id"], "contact", name, email, form["label"][:160], body_text, None, meta)
            if doc_msg and doc_msg.get("message_id"):
                await db.messages.update_one({"message_id": doc_msg["message_id"]},
                                             {"$set": {"form_label": form["label"], "cta_form_id": form_id}})
        await db.submissions.insert_one({
            "submission_id": f"sub_{form_id[-10:]}_{int(datetime.now(timezone.utc).timestamp())}",
            "app_id": doc["app_id"], "form_id": form_id, "form_name": form["label"], "page": None,
            "name": name, "email": email, "fields": meta["values"], "status": "new",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"ok": True, "success_message": form.get("success_message") or "Thank you! We'll be in touch within 24 hours."}

    return {"provision_forms": _provision, "qualifies": qualifies}
