"""Platform membership: free browsing, a one-time agency setup fee and the monthly hosting plan.

Payment routes: Stripe card checkout, Stripe pre-authorised bank debit (ACSS), or a manual
Interac e-Transfer that the admin confirms by hand. Access is resolved server-side on every request.
"""
import asyncio
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import stripe
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel

SETUP_LOOKUP = "lucio_setup_fee"
MONTHLY_LOOKUP = "lucio_monthly_hosting"
SETUP_AMOUNT = 100000          # $1,000.00 one-time, in cents
MONTHLY_AMOUNT = 30000         # $300.00 per month, in cents
CURRENCY = "usd"
TAX_CODE = "txcd_10103001"     # SaaS

PLANS = {
    "setup": {"kind": "setup", "name": "Agency setup fee", "lookup_key": SETUP_LOOKUP,
              "amount": SETUP_AMOUNT / 100, "currency": CURRENCY, "interval": None},
    "monthly": {"kind": "monthly", "name": "Hosting & maintenance", "lookup_key": MONTHLY_LOOKUP,
                "amount": MONTHLY_AMOUNT / 100, "currency": CURRENCY, "interval": "month"},
}

# Everything outside these prefixes needs a paid membership.
PUBLIC_PREFIXES = (
    "/api/auth", "/api/public", "/api/membership", "/api/admin", "/api/site/", "/api/sites/",
    "/api/p/", "/api/embed", "/api/stripe/webhook", "/api/webhook", "/api/health", "/api/leads/public",
    "/api/me/preferences", "/api/choose", "/api/templates/public",
)

FULL_ACCESS = ("admin", "paid", "client")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_admin_email(email: str) -> bool:
    return (email or "").lower().strip() == (os.environ.get("ADMIN_EMAIL") or "").lower().strip()


def is_gated(path: str) -> bool:
    return path.startswith("/api/") and not path.startswith(PUBLIC_PREFIXES)


async def stripe_key(db) -> str:
    """The admin's own key when they have supplied one, otherwise the built-in sandbox key."""
    doc = await db.settings.find_one({"key": "stripe_keys"}, {"_id": 0})
    return (doc or {}).get("secret_key") or os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"


async def resolve_access(db, user: dict) -> str:
    """admin | paid | client | setup_paid | suspended | free"""
    if is_admin_email(user.get("email")):
        return "admin"
    m = user.get("membership") or {}
    if m.get("suspended"):
        return "suspended"
    if m.get("grandfathered"):
        return "paid"
    status = m.get("status") or "free"
    if status == "active":
        end = m.get("current_period_end")
        if m.get("manual") and end and end <= now_iso():
            return "suspended"                       # a hand-confirmed month that has run out
        return "paid"
    if status == "setup_paid":
        return "setup_paid"
    if await db.memberships.count_documents({"user_id": user["user_id"]}, limit=1):
        return "client"
    return "free"


def register(api, db, get_current_user, log_activity):

    class CheckoutIn(BaseModel):
        kind: str                       # setup | monthly
        method: str = "card"            # card | bank
        origin_url: str

    class InteracIn(BaseModel):
        kind: str
        note: str = ""

    class TierIn(BaseModel):
        tier: str                       # paid | free

    class MailIn(BaseModel):
        subject: str
        body: str

    class KeysIn(BaseModel):
        publishable_key: str = ""
        secret_key: str = ""
        interac_email: str = ""
        interac_instructions: str = ""

    async def _require_admin(user: dict) -> dict:
        if not is_admin_email(user.get("email")):
            raise HTTPException(403, "Admins only")
        return user

    async def _user(user_id: str) -> dict:
        doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
        if not doc:
            raise HTTPException(404, "Member not found")
        return doc

    async def _set_membership(user_id: str, patch: Dict[str, Any]):
        cur = (await db.users.find_one({"user_id": user_id}, {"_id": 0, "membership": 1}) or {}).get("membership") or {}
        cur.update({**patch, "updated_at": now_iso()})
        await db.users.update_one({"user_id": user_id}, {"$set": {"membership": cur}})
        return cur

    # ---------- Stripe catalogue ----------

    def _ensure_price(key: str, plan: dict) -> Any:
        found = stripe.Price.list(lookup_keys=[plan["lookup_key"]], active=True, limit=1, api_key=key).data
        amount = int(round(plan["amount"] * 100))
        if found and (found[0].unit_amount != amount or found[0].currency != plan["currency"]):
            stripe.Price.modify(found[0].id, active=False, api_key=key)
            found = []
        if found:
            return found[0]
        product = None
        for p in stripe.Product.list(active=True, limit=100, api_key=key).auto_paging_iter():
            if p.to_dict().get("metadata", {}).get("emergent_product_id") == f"lucio_{plan['kind']}":
                product = p
                break
        if not product:
            product = stripe.Product.create(name=f"LucioDigital — {plan['name']}", tax_code=TAX_CODE,
                                            metadata={"managed_by": "emergent", "emergent_product_id": f"lucio_{plan['kind']}"},
                                            api_key=key)
        kw: Dict[str, Any] = dict(product=product.id, unit_amount=amount, currency=plan["currency"],
                                  lookup_key=plan["lookup_key"], transfer_lookup_key=True, api_key=key)
        if plan["interval"]:
            kw["recurring"] = {"interval": plan["interval"]}
        return stripe.Price.create(**kw)

    def _session(key: str, price, plan: dict, method: str, origin: str, user: dict) -> Any:
        kwargs: Dict[str, Any] = dict(
            line_items=[{"price": price.id, "quantity": 1}],
            mode="subscription" if plan["interval"] else "payment",
            success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/payment/cancel",
            customer_email=user.get("email"),
            metadata={"user_id": user["user_id"], "membership_kind": plan["kind"], "lookup_key": plan["lookup_key"]},
            api_key=key,
        )
        if method == "bank":
            # Pre-authorised debit: an explicit method list rules out Stripe-managed payments.
            # `currency` belongs on the mandate only in subscription mode.
            acss: Dict[str, Any] = {"mandate_options": {"transaction_type": "business"}}
            if plan["interval"]:
                acss["currency"] = "usd"
                acss["mandate_options"].update({"payment_schedule": "interval", "interval_description": "monthly hosting"})
            else:
                acss["mandate_options"]["payment_schedule"] = "sporadic"
            return stripe.checkout.Session.create(
                **kwargs, payment_method_types=["acss_debit"],
                payment_method_options={"acss_debit": acss},
                billing_address_collection="required")
        try:
            return stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True})
        except stripe.error.InvalidRequestError as e:
            msg = (e.user_message or str(e)).lower()
            if "managed payments" in msg or "ineligible" in msg:
                return stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True},
                                                      billing_address_collection="required")
            raise

    # ---------- entitlement ----------

    async def _welcome_email(user: dict):
        try:
            from auth_extra import _shell, send_email
            html = _shell(
                "Welcome to LucioDigital",
                f"<p>Your membership is active, {user.get('name') or user.get('email')}.</p>"
                "<p>Your agency setup fee is paid and hosting &amp; maintenance is billing monthly. "
                "You now have full access: unlimited client projects, all 33+ industry projects, the client "
                "dashboard and Site Mode. Receipts and invoices come straight from Stripe.</p>",
                "Open your dashboard", f"{os.environ.get('FRONTEND_URL') or ''}/dashboard", "LucioDigital")
            await send_email(to=user["email"], subject="Welcome to LucioDigital — your membership is active", html=html)
        except Exception:
            pass

    async def _activate(user_id: str, kind: str, extra: Dict[str, Any]):
        """Setup fee paid -> setup_paid. Monthly started -> active (full access)."""
        if kind == "setup":
            await _set_membership(user_id, {"status": "setup_paid", "setup_paid_at": now_iso(), **extra})
            return
        end = extra.pop("current_period_end", None) or (datetime.now(timezone.utc) + timedelta(days=31)).isoformat()
        cur = await _set_membership(user_id, {"status": "active", "current_period_end": end,
                                              "cancel_at_period_end": False, "suspended": False, **extra})
        if not cur.get("welcomed"):
            await _set_membership(user_id, {"welcomed": True})
            await _welcome_email(await _user(user_id))

    async def _reconcile(session_id: str) -> dict:
        rec = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if not rec:
            raise HTTPException(404, "Payment not found")
        if rec.get("payment_status") != "paid":
            key = await stripe_key(db)
            try:
                s = await asyncio.to_thread(stripe.checkout.Session.retrieve, session_id, api_key=key)
            except stripe.error.StripeError:
                s = None
            if s and (s.payment_status == "paid" or s.status == "complete"):
                await db.payment_transactions.update_one(
                    {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                    {"$set": {"status": "completed", "payment_status": "paid",
                              "stripe_subscription_id": s.get("subscription"),
                              "stripe_customer_id": s.get("customer"),
                              "stripe_payment_intent_id": s.get("payment_intent"), "updated_at": now_iso()}})
                rec = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
                if rec.get("user_id") and rec.get("membership_kind"):
                    await _activate(rec["user_id"], rec["membership_kind"],
                                    {"stripe_customer_id": s.get("customer"),
                                     "stripe_subscription_id": s.get("subscription")})
        return rec

    # ---------- member endpoints ----------

    @api.get("/membership/plans")
    async def plans():
        cfg = await db.settings.find_one({"key": "stripe_keys"}, {"_id": 0}) or {}
        return {"plans": [PLANS["setup"], PLANS["monthly"]],
                "interac": {"email": cfg.get("interac_email") or os.environ.get("ADMIN_EMAIL") or "",
                            "instructions": cfg.get("interac_instructions")
                            or "Send an Interac e-Transfer for the amount shown, using the reference code as the message. Access unlocks as soon as we confirm it."},
                "methods": ["card", "bank", "interac"]}

    @api.get("/membership/me")
    async def my_membership(user: dict = Depends(get_current_user)):
        fresh = await _user(user["user_id"])
        access = await resolve_access(db, fresh)
        m = fresh.get("membership") or {}
        pending = await db.manual_payments.find({"user_id": fresh["user_id"], "status": "pending"},
                                                {"_id": 0}).sort("created_at", -1).to_list(10)
        return {"access": access, "full_access": access in FULL_ACCESS,
                "status": m.get("status") or "free", "grandfathered": bool(m.get("grandfathered")),
                "suspended": bool(m.get("suspended")), "setup_paid_at": m.get("setup_paid_at"),
                "current_period_end": m.get("current_period_end"),
                "cancel_at_period_end": bool(m.get("cancel_at_period_end")),
                "manual": bool(m.get("manual")), "favorites": fresh.get("favorites") or [],
                "pending_manual": pending, "is_admin": is_admin_email(fresh.get("email")),
                "email": fresh.get("email"), "name": fresh.get("name")}

    @api.post("/membership/checkout")
    async def start_checkout(body: CheckoutIn, user: dict = Depends(get_current_user)):
        plan = PLANS.get(body.kind)
        if not plan:
            raise HTTPException(400, "Unknown plan")
        if body.method not in ("card", "bank"):
            raise HTTPException(400, "Choose card or bank for Stripe checkout")
        fresh = await _user(user["user_id"])
        m = fresh.get("membership") or {}
        if body.kind == "monthly" and (m.get("status") or "free") == "free" and not m.get("grandfathered"):
            raise HTTPException(400, "The one-time setup fee comes first")
        key = await stripe_key(db)
        try:
            price = await asyncio.to_thread(_ensure_price, key, plan)
            session = await asyncio.to_thread(_session, key, price, plan, body.method, body.origin_url.rstrip("/"), fresh)
        except stripe.error.StripeError as e:
            raise HTTPException(502, f"Stripe could not start checkout: {e.user_message or str(e)[:160]}")
        await db.payment_transactions.insert_one({
            "session_id": session.id, "user_id": fresh["user_id"], "email": fresh.get("email"),
            "membership_kind": plan["kind"], "lookup_key": plan["lookup_key"], "method": body.method,
            "plan_name": plan["name"], "amount": plan["amount"], "currency": plan["currency"],
            "status": "initiated", "payment_status": "pending", "created_at": now_iso(), "updated_at": now_iso()})
        await log_activity(None, fresh["user_id"], "membership.checkout", f"Started the {plan['name']} checkout")
        return {"checkout_url": session.url, "session_id": session.id}

    @api.get("/membership/status/{session_id}")
    async def checkout_status(session_id: str):
        rec = await _reconcile(session_id)
        return {"session_id": rec["session_id"], "status": rec["status"], "payment_status": rec["payment_status"],
                "membership_kind": rec.get("membership_kind"), "plan_name": rec.get("plan_name")}

    @api.post("/membership/interac")
    async def request_interac(body: InteracIn, user: dict = Depends(get_current_user)):
        plan = PLANS.get(body.kind)
        if not plan:
            raise HTTPException(400, "Unknown plan")
        fresh = await _user(user["user_id"])
        code = f"LD-{secrets.token_hex(3).upper()}"
        doc = {"manual_id": f"mp_{secrets.token_hex(8)}", "user_id": fresh["user_id"], "email": fresh.get("email"),
               "name": fresh.get("name") or "", "kind": plan["kind"], "plan_name": plan["name"],
               "amount": plan["amount"], "currency": plan["currency"], "method": "interac",
               "reference": code, "note": body.note[:400], "status": "pending", "created_at": now_iso()}
        await db.manual_payments.insert_one(doc)
        doc.pop("_id", None)
        await log_activity(None, fresh["user_id"], "membership.interac", f"Declared an Interac e-Transfer for {plan['name']}")
        cfg = await db.settings.find_one({"key": "stripe_keys"}, {"_id": 0}) or {}
        return {**doc, "send_to": cfg.get("interac_email") or os.environ.get("ADMIN_EMAIL") or ""}

    @api.post("/membership/cancel")
    async def cancel(user: dict = Depends(get_current_user)):
        fresh = await _user(user["user_id"])
        m = fresh.get("membership") or {}
        sub = m.get("stripe_subscription_id")
        if sub:
            key = await stripe_key(db)
            try:
                s = await asyncio.to_thread(stripe.Subscription.modify, sub, cancel_at_period_end=True, api_key=key)
                end = datetime.fromtimestamp(s.current_period_end, timezone.utc).isoformat()
            except stripe.error.StripeError as e:
                raise HTTPException(502, f"Stripe could not cancel that plan: {e.user_message or str(e)[:160]}")
        else:
            end = m.get("current_period_end")
        await _set_membership(fresh["user_id"], {"cancel_at_period_end": True, "current_period_end": end})
        await log_activity(None, fresh["user_id"], "membership.cancel", "Cancelled the monthly plan at period end")
        return {"cancel_at_period_end": True, "current_period_end": end}

    @api.post("/membership/resume")
    async def resume(user: dict = Depends(get_current_user)):
        fresh = await _user(user["user_id"])
        sub = (fresh.get("membership") or {}).get("stripe_subscription_id")
        if sub:
            key = await stripe_key(db)
            try:
                await asyncio.to_thread(stripe.Subscription.modify, sub, cancel_at_period_end=False, api_key=key)
            except stripe.error.StripeError as e:
                raise HTTPException(502, f"Stripe could not resume that plan: {e.user_message or str(e)[:160]}")
        await _set_membership(fresh["user_id"], {"cancel_at_period_end": False})
        await log_activity(None, fresh["user_id"], "membership.resume", "Resumed the monthly plan")
        return {"cancel_at_period_end": False}

    @api.get("/membership/payments")
    async def my_payments(user: dict = Depends(get_current_user)):
        rows = await db.payment_transactions.find({"user_id": user["user_id"], "membership_kind": {"$exists": True}},
                                                  {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
        manual = await db.manual_payments.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
        return {"stripe": rows, "manual": manual}

    @api.post("/membership/favorites/{key}")
    async def toggle_favorite(key: str, user: dict = Depends(get_current_user)):
        favs = (await _user(user["user_id"])).get("favorites") or []
        favs = [f for f in favs if f != key] if key in favs else [*favs, key]
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"favorites": favs}})
        return {"favorites": favs}

    # ---------- admin: members ----------

    @api.get("/admin/members")
    async def list_members(q: str = "", user: dict = Depends(get_current_user)):
        await _require_admin(user)
        query: Dict[str, Any] = {}
        if q.strip():
            query = {"$or": [{"email": {"$regex": q.strip(), "$options": "i"}},
                             {"name": {"$regex": q.strip(), "$options": "i"}}]}
        rows = await db.users.find(query, {"_id": 0, "password_hash": 0}).sort("created_at", -1).limit(500).to_list(500)
        out = []
        for r in rows:
            m = r.get("membership") or {}
            out.append({"user_id": r["user_id"], "email": r.get("email"), "name": r.get("name") or "",
                        "created_at": r.get("created_at"), "last_login_at": r.get("last_login_at"),
                        "auth_provider": r.get("auth_provider") or "password",
                        "access": await resolve_access(db, r), "status": m.get("status") or "free",
                        "grandfathered": bool(m.get("grandfathered")), "suspended": bool(m.get("suspended")),
                        "current_period_end": m.get("current_period_end"),
                        "cancel_at_period_end": bool(m.get("cancel_at_period_end")),
                        "clients": await db.apps.count_documents({"owner_id": r["user_id"]}),
                        "payments": await db.payment_transactions.count_documents(
                            {"user_id": r["user_id"], "payment_status": "paid"})})
        pending = await db.manual_payments.count_documents({"status": "pending"})
        return {"members": out, "count": len(out), "pending_manual": pending}

    @api.get("/admin/members/{user_id}/payments")
    async def member_payments(user_id: str, user: dict = Depends(get_current_user)):
        await _require_admin(user)
        rows = await db.payment_transactions.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
        manual = await db.manual_payments.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
        return {"stripe": rows, "manual": manual}

    @api.post("/admin/members/{user_id}/tier")
    async def set_tier(user_id: str, body: TierIn, user: dict = Depends(get_current_user)):
        await _require_admin(user)
        target = await _user(user_id)
        if body.tier == "paid":
            await _set_membership(user_id, {"status": "active", "grandfathered": True, "suspended": False,
                                            "manual": True, "cancel_at_period_end": False})
        elif body.tier == "free":
            await _set_membership(user_id, {"status": "free", "grandfathered": False, "manual": False})
        else:
            raise HTTPException(400, "Tier must be paid or free")
        await log_activity(None, user["user_id"], "membership.admin", f"Set {target.get('email')} to {body.tier}")
        return await my_membership_for(user_id)

    @api.post("/admin/members/{user_id}/suspend")
    async def suspend(user_id: str, user: dict = Depends(get_current_user)):
        await _require_admin(user)
        target = await _user(user_id)
        if is_admin_email(target.get("email")):
            raise HTTPException(400, "You cannot suspend the platform admin account")
        await _set_membership(user_id, {"suspended": True})
        await log_activity(None, user["user_id"], "membership.admin", f"Suspended {target.get('email')}")
        return await my_membership_for(user_id)

    @api.post("/admin/members/{user_id}/reactivate")
    async def reactivate(user_id: str, user: dict = Depends(get_current_user)):
        await _require_admin(user)
        target = await _user(user_id)
        await _set_membership(user_id, {"suspended": False})
        await log_activity(None, user["user_id"], "membership.admin", f"Reactivated {target.get('email')}")
        return await my_membership_for(user_id)

    @api.post("/admin/members/{user_id}/email")
    async def email_member(user_id: str, body: MailIn, user: dict = Depends(get_current_user)):
        await _require_admin(user)
        target = await _user(user_id)
        if not body.subject.strip() or not body.body.strip():
            raise HTTPException(400, "Add a subject and a message")
        from auth_extra import _shell, send_email
        html = _shell(body.subject.strip(), "".join(f"<p>{line}</p>" for line in body.body.strip().splitlines() if line.strip()),
                      "Open LucioDigital", f"{os.environ.get('FRONTEND_URL') or ''}/dashboard", "LucioDigital")
        res = await send_email(to=target["email"], subject=body.subject.strip(), html=html)
        await log_activity(None, user["user_id"], "membership.admin", f"Emailed {target.get('email')}")
        provider = "resend"
        if isinstance(res, dict):
            provider = res.get("provider", "resend")
        return {"sent": True, "provider": provider}

    @api.get("/admin/manual-payments")
    async def manual_payments(status: str = "pending", user: dict = Depends(get_current_user)):
        await _require_admin(user)
        q = {} if status == "all" else {"status": status}
        return await db.manual_payments.find(q, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)

    @api.post("/admin/manual-payments/{manual_id}/confirm")
    async def confirm_manual(manual_id: str, user: dict = Depends(get_current_user)):
        await _require_admin(user)
        row = await db.manual_payments.find_one({"manual_id": manual_id}, {"_id": 0})
        if not row:
            raise HTTPException(404, "That payment declaration is gone")
        if row["status"] == "confirmed":
            return row
        await db.manual_payments.update_one({"manual_id": manual_id},
                                            {"$set": {"status": "confirmed", "confirmed_at": now_iso(),
                                                      "confirmed_by": user["user_id"]}})
        extra = {"manual": True}
        if row["kind"] == "monthly":
            extra["current_period_end"] = (datetime.now(timezone.utc) + timedelta(days=31)).isoformat()
        await _activate(row["user_id"], row["kind"], extra)
        await log_activity(None, user["user_id"], "membership.admin",
                           f"Confirmed the {row['plan_name']} e-Transfer from {row.get('email')}")
        return {**row, "status": "confirmed"}

    @api.post("/admin/manual-payments/{manual_id}/reject")
    async def reject_manual(manual_id: str, user: dict = Depends(get_current_user)):
        await _require_admin(user)
        row = await db.manual_payments.find_one({"manual_id": manual_id}, {"_id": 0})
        if not row:
            raise HTTPException(404, "That payment declaration is gone")
        await db.manual_payments.update_one({"manual_id": manual_id},
                                            {"$set": {"status": "rejected", "rejected_at": now_iso()}})
        await log_activity(None, user["user_id"], "membership.admin", f"Rejected an e-Transfer from {row.get('email')}")
        return {**row, "status": "rejected"}

    @api.get("/admin/stripe-keys")
    async def get_keys(user: dict = Depends(get_current_user)):
        await _require_admin(user)
        cfg = await db.settings.find_one({"key": "stripe_keys"}, {"_id": 0}) or {}
        secret = cfg.get("secret_key") or ""
        return {"publishable_key": cfg.get("publishable_key") or os.environ.get("STRIPE_PUBLISHABLE_KEY") or "",
                "secret_key_set": bool(secret), "secret_key_hint": f"…{secret[-4:]}" if secret else "",
                "using_own_keys": bool(secret), "mode": "live" if secret.startswith("sk_live") else "test",
                "interac_email": cfg.get("interac_email") or os.environ.get("ADMIN_EMAIL") or "",
                "interac_instructions": cfg.get("interac_instructions") or ""}

    @api.put("/admin/stripe-keys")
    async def put_keys(body: KeysIn, user: dict = Depends(get_current_user)):
        await _require_admin(user)
        patch: Dict[str, Any] = {"key": "stripe_keys", "updated_at": now_iso()}
        if body.publishable_key.strip():
            patch["publishable_key"] = body.publishable_key.strip()
        if body.secret_key.strip():
            if not body.secret_key.strip().startswith("sk_"):
                raise HTTPException(400, "That does not look like a Stripe secret key")
            patch["secret_key"] = body.secret_key.strip()
        if body.interac_email.strip():
            patch["interac_email"] = body.interac_email.strip()
        if body.interac_instructions.strip():
            patch["interac_instructions"] = body.interac_instructions.strip()[:600]
        await db.settings.update_one({"key": "stripe_keys"}, {"$set": patch}, upsert=True)
        await log_activity(None, user["user_id"], "membership.admin", "Updated the platform payment settings")
        return await get_keys(user)

    async def my_membership_for(user_id: str) -> dict:
        target = await _user(user_id)
        m = target.get("membership") or {}
        return {"user_id": user_id, "email": target.get("email"), "access": await resolve_access(db, target),
                "status": m.get("status") or "free", "suspended": bool(m.get("suspended")),
                "grandfathered": bool(m.get("grandfathered"))}

    # ---------- webhook handling (called from the shared Stripe webhook) ----------

    async def handle_event(event: dict):
        obj, t = event["data"]["object"], event["type"]
        if t in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            meta = obj.get("metadata") or {}
            kind, uid = meta.get("membership_kind"), meta.get("user_id")
            if kind and uid:
                await db.payment_transactions.update_one(
                    {"session_id": obj["id"]},
                    {"$set": {"status": "completed", "payment_status": "paid",
                              "stripe_subscription_id": obj.get("subscription"),
                              "stripe_customer_id": obj.get("customer"),
                              "stripe_payment_intent_id": obj.get("payment_intent"), "updated_at": now_iso()}})
                await _activate(uid, kind, {"stripe_customer_id": obj.get("customer"),
                                            "stripe_subscription_id": obj.get("subscription")})
        elif t in ("invoice.paid", "invoice.payment_succeeded"):
            sub = obj.get("subscription")
            row = await db.users.find_one({"membership.stripe_subscription_id": sub}, {"_id": 0, "user_id": 1})
            if row:
                end = obj.get("lines", {}).get("data", [{}])[0].get("period", {}).get("end")
                await _activate(row["user_id"], "monthly",
                                {"current_period_end": datetime.fromtimestamp(end, timezone.utc).isoformat() if end else None,
                                 "manual": False})
        elif t in ("invoice.payment_failed", "customer.subscription.deleted", "customer.subscription.paused"):
            sub = obj.get("subscription") or obj.get("id")
            row = await db.users.find_one({"membership.stripe_subscription_id": sub}, {"_id": 0, "user_id": 1})
            if row:
                await _set_membership(row["user_id"], {"status": "setup_paid", "suspended": True,
                                                       "suspend_reason": t})
        elif t == "customer.subscription.updated":
            row = await db.users.find_one({"membership.stripe_subscription_id": obj.get("id")}, {"_id": 0, "user_id": 1})
            if row:
                end = obj.get("current_period_end")
                patch = {"cancel_at_period_end": bool(obj.get("cancel_at_period_end")),
                         "current_period_end": datetime.fromtimestamp(end, timezone.utc).isoformat() if end else None}
                if obj.get("status") in ("active", "trialing"):
                    patch.update({"status": "active", "suspended": False})
                elif obj.get("status") in ("past_due", "unpaid", "canceled", "incomplete_expired"):
                    patch.update({"status": "setup_paid", "suspended": True, "suspend_reason": obj.get("status")})
                await _set_membership(row["user_id"], patch)

    return handle_event
