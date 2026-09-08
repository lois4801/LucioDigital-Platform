"""Booking calendar admin actions, the Monday client digest, and the paid members area.
Stripe reuses the sandbox already provisioned for this app (extras.py / STRIPE_SECRET_KEY)."""
import asyncio
import hmac
import logging
import os
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict, Any

import stripe
from fastapi import HTTPException, Depends, Request, BackgroundTasks
from pydantic import BaseModel, EmailStr

logger = logging.getLogger("agency.pro")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"


def _iso():
    return datetime.now(timezone.utc).isoformat()


def _uid(p):
    import uuid
    return f"{p}_{uuid.uuid4().hex[:12]}"


class BookingIn(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: str = ""
    service: str = "Booking"
    date: str
    slot: str = ""
    duration_min: int = 60
    notes: str = ""
    notify: bool = True


class BookingEdit(BookingIn):
    name: Optional[str] = None
    date: Optional[str] = None


class FollowupSendIn(BaseModel):
    kind: str = "reminder"
    body: str = ""


class DigestIn(BaseModel):
    enabled: bool = True
    hour: int = 8
    recipients: List[str] = []


class PaidIn(BaseModel):
    enabled: bool
    mode: str = "one_time"            # one_time | subscription
    price: float = 19.0
    currency: str = "usd"
    interval: str = "month"
    page_ids: List[str] = []


def register(api, db, get_current_user, get_user_app, log_activity, send_email=None):

    async def app_by_token(token: str) -> dict:
        doc = await db.apps.find_one({"preview_token": token}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Site not found")
        return doc

    async def notify(to, subject, body):
        if send_email and to:
            try:
                await send_email(to, subject, body)
            except Exception:
                logger.exception("pro feature email failed")

    async def _panel(request: Request, token: str):
        from site_app import register as _r  # noqa: F401  (module import for side-effect-free helpers)
        doc = await app_by_token(token)
        # Reuse the site_app panel guard semantics: site admin token, or agency owner/admin session.
        from site_app import SITE_AUD
        import jwt as _jwt
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            try:
                p = _jwt.decode(auth[7:], os.environ["JWT_SECRET"], algorithms=["HS256"], audience=SITE_AUD)
                if p.get("app") == doc["app_id"] and p.get("role") == "admin":
                    return doc, {"site_user_id": p["sub"], "role": "admin"}
            except _jwt.PyJWTError:
                pass
        agency = await get_current_user(request)
        app_doc = await get_user_app(doc["app_id"], agency)
        from page_guard import role_of
        if await role_of(db, app_doc, agency) not in ("owner", "admin"):
            raise HTTPException(403, "Admin access only")
        return doc, {"site_user_id": agency["user_id"], "role": "admin", "agency": True}

    # ---------- admin booking create / edit / cancel ----------

    @api.post("/site/{token}/admin/bookings")
    async def create_booking(token: str, body: BookingIn, request: Request):
        doc, _me = await _panel(request, token)
        row = {"submission_id": _uid("sub"), "app_id": doc["app_id"], "form_id": None,
               "form_name": body.service or "Booking", "page": None, "name": body.name[:120],
               "email": (str(body.email) if body.email else "").lower(), "site_user_id": None,
               "fields": {"phone": body.phone[:60], "service": body.service[:120], "notes": body.notes[:1000]},
               "status": "handled", "created_at": _iso(), "created_by_admin": True,
               "booking": {"date": body.date[:10], "slot": body.slot[:20] or None, "duration_min": max(15, min(480, body.duration_min)),
                           "status": "confirmed", "requested_at": _iso(), "confirmed_at": _iso()}}
        await db.submissions.insert_one(dict(row))
        if body.notify and row["email"]:
            await notify(row["email"], f"Your booking is confirmed — {doc.get('name')}",
                         f"Hi {row['name']},\n\nYour {body.service} is booked for {body.date} {body.slot or ''} "
                         f"({row['booking']['duration_min']} minutes).\n\n{body.notes}".strip())
        row.pop("_id", None)
        return {"booking": row}

    @api.put("/site/{token}/admin/bookings/{submission_id}")
    async def edit_booking(token: str, submission_id: str, body: BookingEdit, request: Request):
        doc, _me = await _panel(request, token)
        row = await db.submissions.find_one({"app_id": doc["app_id"], "submission_id": submission_id}, {"_id": 0})
        if not row or not row.get("booking"):
            raise HTTPException(404, "Booking not found")
        bk = dict(row["booking"])
        if body.date:
            bk["date"] = body.date[:10]
        if body.slot is not None:
            bk["slot"] = body.slot[:20] or None
        if body.duration_min:
            bk["duration_min"] = max(15, min(480, body.duration_min))
        bk["status"] = "confirmed"
        bk["confirmed_at"] = _iso()
        fields = dict(row.get("fields") or {})
        for k, v in (("phone", body.phone), ("service", body.service), ("notes", body.notes)):
            if v:
                fields[k] = str(v)[:1000]
        upd = {"booking": bk, "fields": fields}
        if body.name:
            upd["name"] = body.name[:120]
        if body.email:
            upd["email"] = str(body.email).lower()
        if body.service:
            upd["form_name"] = body.service[:120]
        await db.submissions.update_one({"submission_id": submission_id}, {"$set": upd})
        if body.notify and (upd.get("email") or row.get("email")):
            await notify(upd.get("email") or row["email"], f"Your booking has been updated — {doc.get('name')}",
                         f"Your booking is now on {bk['date']} {bk.get('slot') or ''} ({bk.get('duration_min', 60)} minutes).")
        return {"submission_id": submission_id, "booking": bk}

    @api.delete("/site/{token}/admin/bookings/{submission_id}")
    async def cancel_booking(token: str, submission_id: str, request: Request, notify_client: bool = True):
        doc, _me = await _panel(request, token)
        row = await db.submissions.find_one({"app_id": doc["app_id"], "submission_id": submission_id}, {"_id": 0})
        if not row or not row.get("booking"):
            raise HTTPException(404, "Booking not found")
        bk = {**row["booking"], "status": "cancelled", "cancelled_at": _iso()}
        await db.submissions.update_one({"submission_id": submission_id}, {"$set": {"booking": bk, "status": "archived"}})
        if notify_client and row.get("email"):
            await notify(row["email"], f"Your booking was cancelled — {doc.get('name')}",
                         f"Your booking on {bk['date']} {bk.get('slot') or ''} has been cancelled. Reply to this email to rebook.")
        return {"submission_id": submission_id, "booking": bk}

    # ---------- AI booking follow-ups (draft, review, send) ----------

    FOLLOWUP_KINDS = {
        "reminder": ("a friendly reminder sent before the appointment: confirm the date and time, say what to "
                     "prepare or bring, and invite them to reply if they need to reschedule"),
        "thankyou": ("a warm thank-you sent after the appointment: thank them, check they are happy, ask for a "
                     "short public review and mention they can book again any time"),
    }

    @api.post("/site/{token}/admin/bookings/{submission_id}/ai-followup")
    async def draft_booking_followup(token: str, submission_id: str, request: Request, kind: str = "reminder"):
        doc, _me = await _panel(request, token)
        if kind not in FOLLOWUP_KINDS:
            raise HTTPException(400, "kind must be 'reminder' or 'thankyou'")
        row = await db.submissions.find_one({"app_id": doc["app_id"], "submission_id": submission_id}, {"_id": 0})
        if not row or not row.get("booking"):
            raise HTTPException(404, "Booking not found")
        bk = row["booking"]
        import ai_models
        system = (f"You write short booking follow-up emails on behalf of {doc.get('name')} "
                  f"({doc.get('industry') or 'local business'}). Write {FOLLOWUP_KINDS[kind]}. "
                  "Plain text, no subject line, under 110 words, warm and professional, sign off with the business name.")
        prompt = (f"Customer: {row.get('name')}\nService: {row.get('form_name')}\n"
                  f"Date: {bk.get('date')} {bk.get('slot') or ''} ({bk.get('duration_min', 60)} minutes)\n"
                  f"Notes: {(row.get('fields') or {}).get('notes') or '-'}")
        try:
            text, model = await ai_models.run_text(doc["app_id"], "copy_rewrite", system, prompt,
                                                   f"bookfu-{submission_id}-{kind}")
        except Exception as e:
            logger.exception("booking follow-up draft failed")
            raise HTTPException(500, f"Draft failed: {str(e)[:140]}")
        draft = {"kind": kind, "body": text[:2000], "model": model, "drafted_at": _iso()}
        await db.submissions.update_one({"app_id": doc["app_id"], "submission_id": submission_id},
                                        {"$set": {f"booking.followups.{kind}": draft}})
        return draft

    @api.post("/site/{token}/admin/bookings/{submission_id}/followup-send")
    async def send_booking_followup(token: str, submission_id: str, body: FollowupSendIn, request: Request):
        doc, _me = await _panel(request, token)
        if body.kind not in FOLLOWUP_KINDS:
            raise HTTPException(400, "kind must be 'reminder' or 'thankyou'")
        row = await db.submissions.find_one({"app_id": doc["app_id"], "submission_id": submission_id}, {"_id": 0})
        if not row or not row.get("booking"):
            raise HTTPException(404, "Booking not found")
        text = (body.body or "").strip()
        if not text:
            raise HTTPException(400, "Write or draft a message first")
        if not row.get("email"):
            raise HTTPException(400, "This booking has no email address")
        subject = (f"Your booking on {row['booking'].get('date')} — {doc.get('name')}" if body.kind == "reminder"
                   else f"Thanks for visiting {doc.get('name')}")
        await notify(row["email"], subject, text)
        sent = {"kind": body.kind, "body": text[:2000], "sent_at": _iso(), "to": row["email"]}
        await db.submissions.update_one({"app_id": doc["app_id"], "submission_id": submission_id},
                                        {"$set": {f"booking.followups.{body.kind}": sent}})
        return sent

    # ---------- weekly client digest ----------

    async def build_digest(app_id: str) -> dict:
        app_doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0, "name": 1, "logo": 1, "theme": 1, "webapp": 1, "preview_token": 1})
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        upto = (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat()
        today = datetime.now(timezone.utc).date().isoformat()
        subs = await db.submissions.find({"app_id": app_id, "created_at": {"$gte": since}}, {"_id": 0}).sort("created_at", -1).to_list(50)
        bookings = await db.submissions.find({"app_id": app_id, "booking.date": {"$gte": today, "$lte": upto},
                                              "booking.status": {"$ne": "cancelled"}}, {"_id": 0}).sort("booking.date", 1).to_list(50)
        edits = await db.messages.find({"app_id": app_id, "kind": "edit_request", "edit_request.state": "pending"}, {"_id": 0}).to_list(30)
        ai_summary = ""
        try:
            import ai_models
            ai_summary = (await ai_models.build_lead_summary(db, app_id, 7))["summary"]
        except Exception:
            logger.exception("digest AI lead summary failed for %s", app_id)
        return {"app": {"name": (app_doc or {}).get("name"), "logo": (app_doc or {}).get("logo") or "",
                        "token": (app_doc or {}).get("preview_token")},
                "submissions": subs, "bookings": bookings, "edit_requests": edits, "ai_summary": ai_summary,
                "counts": {"submissions": len(subs), "bookings": len(bookings), "edit_requests": len(edits)}}

    def digest_text(d: dict) -> str:
        a = d["app"]
        lines = [f"{a['name']} — your week at a glance", ""]
        if a.get("logo"):
            lines += [a["logo"], ""]
        if d.get("ai_summary"):
            lines += ["AI SUMMARY OF YOUR LEADS", d["ai_summary"], ""]
        lines.append(f"NEW SUBMISSIONS (last 7 days): {d['counts']['submissions']}")
        for s in d["submissions"][:10]:
            lines.append(f"  · {s.get('form_name')} — {s.get('name') or 'Anonymous'} <{s.get('email') or '-'}> [{s.get('status')}]")
        lines += ["", f"UPCOMING BOOKINGS (next 7 days): {d['counts']['bookings']}"]
        for b in d["bookings"][:10]:
            bk = b.get("booking") or {}
            lines.append(f"  · {bk.get('date')} {bk.get('slot') or ''} — {b.get('name')} ({bk.get('status')})")
        lines += ["", f"PENDING EDIT REQUESTS: {d['counts']['edit_requests']}"]
        for e in d["edit_requests"][:10]:
            lines.append(f"  · {(e.get('edit_request') or {}).get('page_name')} — {e.get('from_name')}")
        if a.get("token"):
            lines += ["", f"Open your admin panel: /site-admin/{a['token']}"]
        return "\n".join(lines)

    async def digest_recipients(app_id: str, settings: dict) -> List[str]:
        if settings.get("recipients"):
            return settings["recipients"][:10]
        admins = await db.site_users.find({"app_id": app_id, "role": "admin", "status": "active"}, {"_id": 0, "email": 1}).to_list(20)
        out = [a["email"] for a in admins]
        app_doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0, "owner_id": 1})
        owner = await db.users.find_one({"user_id": (app_doc or {}).get("owner_id")}, {"_id": 0, "email": 1})
        if owner and owner["email"] not in out:
            out.append(owner["email"])
        return out

    async def send_digest(app_id: str) -> dict:
        app_doc = await db.apps.find_one({"app_id": app_id}, {"_id": 0, "webapp": 1, "name": 1})
        settings = ((app_doc or {}).get("webapp") or {}).get("digest") or {}
        d = await build_digest(app_id)
        to = await digest_recipients(app_id, settings)
        body = digest_text(d)
        for addr in to:
            await notify(addr, f"[{d['app']['name']}] Your weekly summary", body)
        await db.apps.update_one({"app_id": app_id}, {"$set": {"webapp.digest.last_sent": _iso()}})
        return {"recipients": to, **d["counts"]}

    @api.patch("/apps/{app_id}/webapp/digest")
    async def digest_settings(app_id: str, body: DigestIn, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        from page_guard import role_of
        if await role_of(db, doc, user) not in ("owner", "admin"):
            raise HTTPException(403, "Only the agency owner or an admin can change the digest")
        if not 0 <= body.hour <= 23:
            raise HTTPException(400, "Send hour must be between 0 and 23")
        s = {"enabled": body.enabled, "hour": body.hour, "recipients": [e.strip().lower() for e in body.recipients if e.strip()][:10]}
        await db.apps.update_one({"app_id": app_id}, {"$set": {"webapp.digest": s}})
        return s

    @api.get("/apps/{app_id}/digest/preview")
    async def digest_preview(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        d = await build_digest(app_id)
        settings = (doc.get("webapp") or {}).get("digest") or {}
        return {**d, "text": digest_text(d), "recipients": await digest_recipients(app_id, settings),
                "settings": {"enabled": bool(settings.get("enabled")), "hour": settings.get("hour", 8),
                             "recipients": settings.get("recipients", []), "last_sent": settings.get("last_sent")}}

    @api.post("/apps/{app_id}/digest/test")
    async def digest_test(app_id: str, user: dict = Depends(get_current_user)):
        await get_user_app(app_id, user)
        d = await build_digest(app_id)
        await notify(user["email"], f"[TEST] [{d['app']['name']}] Your weekly summary", digest_text(d))
        return {"sent_to": user["email"], **d["counts"]}

    async def _run_weekly_digests():
        hour = datetime.now(timezone.utc).hour
        cursor = db.apps.find({"webapp.digest.enabled": True}, {"_id": 0, "app_id": 1, "webapp": 1})
        async for a in cursor:
            try:
                if int(((a.get("webapp") or {}).get("digest") or {}).get("hour", 8)) != hour:
                    continue
                await send_digest(a["app_id"])
            except Exception:
                logger.exception("weekly digest failed for %s", a.get("app_id"))

    @api.post("/cron/weekly-digest")
    async def cron_weekly_digest(request: Request, tasks: BackgroundTasks):
        # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
        secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
        auth = request.headers.get("Authorization", "")
        if not secret or not auth.startswith("Bearer ") or not hmac.compare_digest(auth[7:], secret):
            raise HTTPException(401, "Unauthorized")
        tasks.add_task(_run_weekly_digests)
        return {"accepted": True, "run_id": request.headers.get("X-Webhook-Id")}

    # ---------- paid members area ----------

    def _sync_price(app_id: str, body: PaidIn) -> str:
        lookup = f"members_{app_id}_{body.mode}"
        product = None
        for p in stripe.Product.list(active=True, limit=100).auto_paging_iter():
            if p.to_dict().get("metadata", {}).get("emergent_product_id") == f"members_{app_id}":
                product = p
                break
        if not product:
            product = stripe.Product.create(name=f"Members area — {app_id}", tax_code="txcd_10103001",
                                            metadata={"managed_by": "emergent", "emergent_product_id": f"members_{app_id}"})
        amount = int(round(body.price * 100))
        existing = stripe.Price.list(lookup_keys=[lookup], active=True, limit=1).data
        if existing and (existing[0].unit_amount != amount or existing[0].currency != body.currency):
            stripe.Price.modify(existing[0].id, active=False)
            existing = []
        if not existing:
            kw = dict(product=product.id, unit_amount=amount, currency=body.currency,
                      lookup_key=lookup, transfer_lookup_key=True)
            if body.mode == "subscription":
                kw["recurring"] = {"interval": body.interval}
            stripe.Price.create(**kw)
        return lookup

    @api.patch("/apps/{app_id}/webapp/paid")
    async def paid_settings(app_id: str, body: PaidIn, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        from page_guard import role_of
        if await role_of(db, doc, user) not in ("owner", "admin"):
            raise HTTPException(403, "Only the agency owner or an admin can change the paid area")
        if body.mode not in ("one_time", "subscription"):
            raise HTTPException(400, "mode must be one_time or subscription")
        if body.enabled and body.price <= 0:
            raise HTTPException(400, "Set a price above zero")
        lookup = ""
        if body.enabled:
            try:
                lookup = await asyncio.to_thread(_sync_price, app_id, body)
            except stripe.error.StripeError as e:
                raise HTTPException(502, f"Stripe rejected that price: {e.user_message or str(e)}")
        paid = {"enabled": body.enabled, "mode": body.mode, "price": float(body.price),
                "currency": body.currency.lower(), "interval": body.interval, "lookup_key": lookup,
                "page_ids": body.page_ids}
        await db.apps.update_one({"app_id": app_id}, {"$set": {"webapp.paid": paid}})
        await db.pages.update_many({"app_id": app_id}, {"$set": {"paid": False}})
        if body.enabled and body.page_ids:
            await db.pages.update_many({"app_id": app_id, "page_id": {"$in": body.page_ids}}, {"$set": {"paid": True}})
        await log_activity(app_id, user["user_id"], "paid.settings",
                           f"Paid members area {'enabled' if body.enabled else 'disabled'} ({len(body.page_ids)} page(s))")
        return paid

    @api.get("/apps/{app_id}/paid-members")
    async def paid_members(app_id: str, user: dict = Depends(get_current_user)):
        doc = await get_user_app(app_id, user)
        access = await db.member_access.find({"app_id": app_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
        emails = {a["site_user_id"]: a for a in access}
        users = await db.site_users.find({"app_id": app_id, "site_user_id": {"$in": list(emails)}},
                                          {"_id": 0, "site_user_id": 1, "email": 1, "name": 1}).to_list(500)
        by_id = {u["site_user_id"]: u for u in users}
        pays = await db.payment_transactions.find({"metadata.app_id": app_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
        return {"members": [{**a, "email": by_id.get(a["site_user_id"], {}).get("email"),
                             "name": by_id.get(a["site_user_id"], {}).get("name")} for a in access],
                "payments": [{"session_id": p.get("session_id"), "amount": p.get("amount"), "currency": p.get("currency"),
                              "status": p.get("payment_status"), "created_at": str(p.get("created_at"))} for p in pays],
                "paid": (doc.get("webapp") or {}).get("paid") or {"enabled": False}}

    async def _site_user(request: Request, doc: dict):
        from site_app import SITE_AUD
        import jwt as _jwt
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        try:
            p = _jwt.decode(auth[7:], os.environ["JWT_SECRET"], algorithms=["HS256"], audience=SITE_AUD)
        except _jwt.PyJWTError:
            return None
        if p.get("app") != doc["app_id"]:
            return None
        return await db.site_users.find_one({"site_user_id": p["sub"]}, {"_id": 0, "password_hash": 0})

    async def has_access(app_id: str, site_user_id: str) -> bool:
        a = await db.member_access.find_one({"app_id": app_id, "site_user_id": site_user_id, "status": "active"}, {"_id": 0})
        return bool(a)

    @api.get("/site/{token}/paywall")
    async def paywall_info(token: str, request: Request):
        doc = await app_by_token(token)
        paid = (doc.get("webapp") or {}).get("paid") or {}
        u = await _site_user(request, doc)
        return {"enabled": bool(paid.get("enabled")), "mode": paid.get("mode", "one_time"),
                "price": paid.get("price"), "currency": paid.get("currency", "usd"), "interval": paid.get("interval", "month"),
                "signed_in": bool(u), "has_access": bool(u and await has_access(doc["app_id"], u["site_user_id"]))}

    @api.post("/site/{token}/paywall/checkout")
    async def paywall_checkout(token: str, body: dict, request: Request):
        doc = await app_by_token(token)
        paid = (doc.get("webapp") or {}).get("paid") or {}
        if not paid.get("enabled") or not paid.get("lookup_key"):
            raise HTTPException(409, "The paid members area is not switched on for this site")
        u = await _site_user(request, doc)
        if not u:
            raise HTTPException(401, "Sign in first, then complete payment")
        origin = str(body.get("origin_url") or "").rstrip("/")
        if not origin.startswith("http"):
            raise HTTPException(400, "origin_url is required")
        prices = await asyncio.to_thread(lambda: stripe.Price.list(lookup_keys=[paid["lookup_key"]], active=True, limit=1).data)
        if not prices:
            raise HTTPException(500, "That price is no longer available — ask the agency to re-save the paid settings")
        price = prices[0]
        meta = {"app_id": doc["app_id"], "site_user_id": u["site_user_id"], "kind": "members_access"}
        try:
            session = await asyncio.to_thread(lambda: stripe.checkout.Session.create(
                line_items=[{"price": price.id, "quantity": 1}],
                mode="subscription" if price.recurring else "payment",
                success_url=f"{origin}/p/{token}?members_session={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{origin}/p/{token}",
                customer_email=u["email"], metadata=meta))
        except stripe.error.StripeError as e:
            raise HTTPException(502, f"Stripe could not start checkout: {e.user_message or str(e)}")
        await db.payment_transactions.insert_one({
            "session_id": session.id, "user_id": u["site_user_id"], "lookup_key": paid["lookup_key"],
            "amount": (price.unit_amount or 0) / 100, "currency": price.currency, "metadata": meta,
            "status": "initiated", "payment_status": "pending",
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)})
        return {"checkout_url": session.url, "session_id": session.id}

    @api.get("/site/{token}/paywall/status/{session_id}")
    async def paywall_status(token: str, session_id: str):
        doc = await app_by_token(token)
        rec = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if not rec:
            raise HTTPException(404, "Transaction not found")
        if rec.get("payment_status") != "paid":
            try:
                s = await asyncio.to_thread(stripe.checkout.Session.retrieve, session_id)
                if s.payment_status == "paid" or s.status == "complete":
                    await db.payment_transactions.update_one(
                        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                        {"$set": {"status": "completed", "payment_status": "paid",
                                  "stripe_subscription_id": s.subscription, "updated_at": datetime.now(timezone.utc)}})
                    rec = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
            except stripe.error.StripeError:
                pass
        if rec.get("payment_status") == "paid":
            meta = rec.get("metadata") or {}
            paid = (doc.get("webapp") or {}).get("paid") or {}
            await db.member_access.update_one(
                {"app_id": doc["app_id"], "site_user_id": meta.get("user_id") or rec.get("user_id")},
                {"$set": {"app_id": doc["app_id"], "site_user_id": meta.get("site_user_id") or rec.get("user_id"),
                          "level": paid.get("mode", "one_time"), "status": "active", "session_id": session_id,
                          "amount": rec.get("amount"), "currency": rec.get("currency"), "created_at": _iso()}},
                upsert=True)
        return {"session_id": session_id, "status": rec.get("status"), "payment_status": rec.get("payment_status")}

    return {"has_access": has_access, "send_digest": send_digest}
