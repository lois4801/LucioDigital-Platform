"""Public project inquiries: one reusable form, emailed to every owner and saved for the inbox."""
import os
import secrets
from datetime import datetime, timezone
from html import escape
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

# label -> field, in the order the email should read
SECTIONS = [
    ("Personal & business", [
        ("full_name", "Full name"), ("email", "Email address"), ("phone", "Phone number"),
        ("company", "Company or business name"), ("website", "Business website"),
        ("industry", "Industry or niche"), ("industry_other", "Industry (other)"),
        ("business_description", "What the business does"), ("target_audience", "Target audience")]),
    ("Project details", [
        ("project_type", "Type of project"), ("project_type_other", "Project type (other)"),
        ("project_purpose", "Project purpose"), ("key_features", "Key features requested"),
        ("style", "Preferred style"), ("style_other", "Style (other)"),
        ("has_branding", "Existing branding"), ("brand_primary", "Primary colour"),
        ("brand_secondary", "Secondary colour"), ("reference_sites", "Reference websites"),
        ("page_count", "Pages or sections needed")]),
    ("Budget & timeline", [
        ("budget", "Budget range"), ("priority", "Project priority"),
        ("start_date", "Preferred start date"), ("end_date", "Preferred deadline")]),
    ("Consultation", [
        ("consult_date", "Preferred consultation date"), ("consult_time", "Preferred time"),
        ("timezone", "Timezone"), ("alt_consult_date", "Alternative date"),
        ("alt_consult_time", "Alternative time"), ("meeting_format", "Meeting format")]),
    ("Discovery", [("heard_from", "How they heard about us"), ("referral_name", "Referral name")]),
    ("Anything else", [("notes", "Anything else we should know")]),
]


class InquiryIn(BaseModel):
    project_key: Optional[str] = None
    project_name: Optional[str] = None
    source: str = "landing"                       # landing_hero | landing_footer | project_modal
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=3, max_length=40)
    company: str = Field(min_length=1, max_length=160)
    website: str = ""
    industry: str = Field(min_length=1, max_length=80)
    industry_other: str = ""
    business_description: str = Field(min_length=1, max_length=2000)
    target_audience: str = Field(min_length=1, max_length=2000)
    project_type: str = Field(min_length=1, max_length=80)
    project_type_other: str = ""
    project_purpose: str = Field(min_length=1, max_length=2000)
    key_features: str = Field(min_length=1, max_length=2000)
    style: str = Field(min_length=1, max_length=80)
    style_other: str = ""
    has_branding: bool = False
    brand_primary: str = ""
    brand_secondary: str = ""
    reference_sites: str = ""
    page_count: int = Field(ge=1, le=500)
    budget: str = Field(min_length=1, max_length=60)
    priority: str = Field(min_length=1, max_length=60)
    start_date: str = Field(min_length=4, max_length=30)
    end_date: str = Field(min_length=4, max_length=30)
    consult_date: str = Field(min_length=4, max_length=30)
    consult_time: str = Field(min_length=3, max_length=20)
    timezone: str = Field(min_length=2, max_length=80)
    alt_consult_date: str = ""
    alt_consult_time: str = ""
    meeting_format: str = Field(min_length=1, max_length=40)
    heard_from: str = Field(min_length=1, max_length=60)
    referral_name: str = ""
    notes: str = ""
    files: List[Dict[str, Any]] = []              # [{name, size, url}] uploaded before submit


def _row(label: str, value: Any) -> str:
    return (f'<tr><td style="padding:6px 12px 6px 0;color:#8a8f9c;font-size:12px;vertical-align:top;'
            f'white-space:nowrap">{escape(label)}</td>'
            f'<td style="padding:6px 0;color:#ffffff;font-size:13px">{escape(str(value))}</td></tr>')


def build_email(data: Dict[str, Any]) -> str:
    blocks = []
    for title, fields in SECTIONS:
        rows = [_row(label, data[f]) for f, label in fields
                if data.get(f) not in (None, "", [], False) or (f == "has_branding" and data.get(f))]
        if not rows:
            continue
        blocks.append(f'<div style="margin:18px 0 4px;color:#84FF00;font-size:11px;letter-spacing:1.5px;'
                      f'text-transform:uppercase">{escape(title)}</div>'
                      f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%">{"".join(rows)}</table>')
    files = data.get("files") or []
    if files:
        links = "".join(f'<div style="font-size:12px"><a href="{escape(f.get("url") or "#")}" '
                        f'style="color:#84FF00">{escape(f.get("name") or "file")}</a></div>' for f in files)
        blocks.append('<div style="margin:18px 0 4px;color:#84FF00;font-size:11px;letter-spacing:1.5px;'
                      f'text-transform:uppercase">Attachments</div>{links}')
    picked = data.get("project_name")
    head = (f'<div style="color:#84FF00;font-size:12px;letter-spacing:1.5px;text-transform:uppercase">'
            f'New project inquiry</div>'
            f'<div style="color:#fff;font-size:22px;font-weight:700;margin-top:6px">{escape(data["full_name"])}'
            f' · {escape(data["company"])}</div>'
            + (f'<div style="color:#8a8f9c;font-size:13px;margin-top:4px">Selected project: '
               f'<span style="color:#fff">{escape(picked)}</span></div>' if picked else "")
            + f'<div style="color:#8a8f9c;font-size:12px;margin-top:2px">Submitted from: {escape(data.get("source") or "landing")}</div>')
    return ('<table role="presentation" width="100%" style="background:#080808;padding:28px 0">'
            '<tr><td align="center"><table role="presentation" width="620" style="max-width:620px;'
            'background:#0d0d0d;border:1px solid #84FF0033;border-radius:16px;padding:26px;'
            'font-family:Arial,Helvetica,sans-serif">'
            f'<tr><td>{head}{"".join(blocks)}'
            '<div style="margin-top:22px;color:#4a4f5c;font-size:11px">Sent automatically by LucioDigital</div>'
            '</td></tr></table></td></tr></table>')


def register(api, db, get_current_user, log_activity):

    @api.post("/public/inquiries")
    async def create_inquiry(body: InquiryIn):
        from access import owner_emails
        data = body.dict()
        doc = {"inquiry_id": f"inq_{secrets.token_hex(8)}", **data,
               "created_at": datetime.now(timezone.utc).isoformat(), "status": "new"}
        await db.inquiries.insert_one(dict(doc))
        doc.pop("_id", None)

        html = build_email(data)
        sent, failed = [], []
        from auth_extra import send_email
        for to in await owner_emails(db):
            try:
                await send_email(to=to, subject=f"New project inquiry — {data['full_name']} ({data['company']})",
                                 html=html)
                sent.append(to)
            except Exception as e:                       # a rate-limited provider must not lose the inquiry
                failed.append({"to": to, "error": str(e)[:160]})
        await db.inquiries.update_one({"inquiry_id": doc["inquiry_id"]},
                                      {"$set": {"emailed_to": sent, "email_errors": failed}})
        return {"inquiry_id": doc["inquiry_id"], "received": True, "emailed_to": sent,
                "message": "Thank you. Your inquiry has been received. We will be in touch within 24 hours."}

    @api.get("/admin/inquiries")
    async def list_inquiries(status: str = "all", user: dict = Depends(get_current_user)):
        from access import is_owner
        if not await is_owner(db, user.get("email")):
            raise HTTPException(403, "Owners only")
        q = {} if status == "all" else {"status": status}
        rows = await db.inquiries.find(q, {"_id": 0}).sort("created_at", -1).limit(300).to_list(300)
        return {"inquiries": rows, "count": len(rows),
                "new": await db.inquiries.count_documents({"status": "new"})}

    @api.post("/admin/inquiries/{inquiry_id}/status")
    async def set_status(inquiry_id: str, status: str = "read", user: dict = Depends(get_current_user)):
        from access import is_owner
        if not await is_owner(db, user.get("email")):
            raise HTTPException(403, "Owners only")
        await db.inquiries.update_one({"inquiry_id": inquiry_id}, {"$set": {"status": status}})
        return {"inquiry_id": inquiry_id, "status": status}
