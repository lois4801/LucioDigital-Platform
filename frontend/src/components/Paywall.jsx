import { useEffect, useState } from "react";
import axios from "axios";
import { Lock, CreditCard, Loader2 } from "lucide-react";
import MemberGate from "@/components/MemberGate";

const BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;
const err = (e) => {
  const d = e.response?.data?.detail;
  return typeof d === "string" ? d : Array.isArray(d) ? d.map(x => x?.msg || "").join(" ") : e.message || "Something went wrong";
};

/** Paywall for a paid page: sign in first (existing auth), then Stripe checkout. */
export default function Paywall({ token, jwt, user, paid, pageName, signupMode, onSignedIn, onPaid }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  // Returning from Stripe: confirm the payment, then unlock.
  useEffect(() => {
    const sid = new URLSearchParams(window.location.search).get("members_session");
    if (!sid) return;
    let tries = 0;
    const poll = async () => {
      try {
        const { data } = await axios.get(`${BASE}/site/${token}/paywall/status/${sid}`);
        if (data.payment_status === "paid") { onPaid(); return; }
      } catch { }
      if (++tries < 8) setTimeout(poll, 2000);
      else setMsg("We haven't seen that payment confirmed yet. Refresh in a moment.");
    };
    poll();
  }, [token]);

  if (!user) return (
    <>
      <div className="pt-16 text-center px-6">
        <div className="inline-flex items-center gap-2 rounded-full border border-[var(--tbd)] px-4 py-1.5 text-xs text-[var(--tp)]"><Lock size={12} /> Paid members area</div>
      </div>
      <MemberGate token={token} pageName={pageName} signupMode={signupMode} onSignedIn={onSignedIn} />
    </>
  );

  async function pay() {
    setBusy(true); setMsg("");
    try {
      const { data } = await axios.post(`${BASE}/site/${token}/paywall/checkout`, { origin_url: window.location.origin },
        { headers: { Authorization: `Bearer ${jwt}` } });
      window.location.href = data.checkout_url;
    } catch (e) { setMsg(err(e)); setBusy(false); }
  }

  const price = `${String(paid.currency || "usd").toUpperCase()} ${Number(paid.price || 0).toFixed(2)}`;
  return (
    <section data-testid="paywall" className="min-h-[70svh] flex items-center justify-center px-6 py-20">
      <div className="w-full max-w-md rounded-[var(--tr)] border border-[var(--tbd)] tcard p-7 space-y-4 text-center">
        <div className="inline-flex items-center gap-2 text-[var(--tp)]"><Lock size={15} /><span className="font-[var(--tfh)] font-bold text-[var(--tfg)]">Members only</span></div>
        <p className="text-sm text-[var(--tmut)]">{pageName || "This page"} is part of the paid members area. Unlock every members page for</p>
        <div data-testid="paywall-price" className="font-[var(--tfh)] t-h2 font-bold">{price}<span className="text-sm text-[var(--tmut)] font-normal">{paid.mode === "subscription" ? ` / ${paid.interval}` : " once"}</span></div>
        <p className="text-xs text-[var(--tmut)]">Signed in as {user.email}</p>
        {msg && <div data-testid="paywall-msg" className="text-xs text-[var(--tp)]">{msg}</div>}
        <button data-testid="paywall-pay-btn" onClick={pay} disabled={busy}
          className="tbtn tbtn-solid w-full rounded-full bg-[var(--tp)] px-6 py-3 text-sm font-semibold text-white disabled:opacity-50 flex items-center justify-center gap-2">
          {busy ? <Loader2 size={14} className="animate-spin" /> : <CreditCard size={14} />} {busy ? "Opening checkout…" : "Unlock access"}
        </button>
        <p className="text-[10px] text-[var(--tmut)]">Secure checkout by Stripe · card, Apple Pay and Google Pay</p>
      </div>
    </section>
  );
}
