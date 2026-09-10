import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Check, Loader2, CreditCard, Landmark, Send, ArrowRight, ShieldCheck } from "lucide-react";
import api from "@/lib/api";
import Logo from "@/components/Logo";
import { useMembership } from "@/lib/membership";

const SETUP_INCLUDES = [
  "Create unlimited client projects",
  "All 33+ industry templates, fully editable",
  "The full client management dashboard",
  "Site Mode visual editor for every client site",
];
const MONTHLY_INCLUDES = [
  "Hosting for every client site you publish",
  "Ongoing maintenance and platform updates",
  "Reviews, e-commerce, motion design & template switcher",
  "Client portals with live previews",
];

const METHODS = [
  { key: "card", label: "Card, Apple Pay & Google Pay", icon: CreditCard, note: "Instant — unlocks the moment Stripe confirms" },
  { key: "bank", label: "Bank debit (pre-authorised)", icon: Landmark, note: "Takes about 5 business days to clear" },
  { key: "interac", label: "Interac e-Transfer", icon: Send, note: "We unlock your access once we confirm it" },
];

export default function Upgrade() {
  const nav = useNavigate();
  const { member, loading, refresh } = useMembership();
  const [plans, setPlans] = useState<any>(null);
  const [method, setMethod] = useState("card");
  const [busy, setBusy] = useState("");
  const [interac, setInterac] = useState<any>(null);

  useEffect(() => { api.get("/membership/plans").then(r => setPlans(r.data)).catch(() => {}); }, []);
  useEffect(() => { if (!loading && member?.full_access) nav("/dashboard", { replace: true }); }, [loading, member, nav]);

  const status = member?.status || "free";
  const setupDone = status === "setup_paid" || status === "active" || !!member?.setup_paid_at;
  const step: "setup" | "monthly" = setupDone ? "monthly" : "setup";

  async function pay(kind: "setup" | "monthly") {
    if (!member) { nav("/login?next=/upgrade"); return; }
    setBusy(kind);
    try {
      if (method === "interac") {
        const { data } = await api.post("/membership/interac", { kind });
        setInterac(data);
        await refresh();
      } else {
        const { data } = await api.post("/membership/checkout", { kind, method, origin_url: window.location.origin });
        window.location.href = data.checkout_url;
      }
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not start that payment");
    } finally { setBusy(""); }
  }

  const Tier = ({ kind, badge, title, price, cadence, includes, active }) => (
    <div data-testid={`tier-${kind}`}
      className={`rounded-3xl border p-7 flex flex-col ${active ? "border-[var(--acc)]/60 bg-[var(--acc)]/[0.04]" : "border-[var(--line)] bg-[var(--card)]/60"}`}>
      <div className="flex items-center justify-between">
        <span className="overline">{badge}</span>
        {active && <span className="chip chip-active">Next step</span>}
      </div>
      <h2 className="font-display text-2xl mt-3">{title}</h2>
      <div className="mt-4 flex items-end gap-2">
        <span className="font-display text-5xl tracking-tight">${price}</span>
        <span className="text-sm text-[var(--mut)] pb-1.5">{cadence}</span>
      </div>
      <ul className="mt-6 space-y-2.5 flex-1">
        {includes.map(i => (
          <li key={i} className="flex gap-2.5 text-sm text-[var(--mut)]">
            <Check size={15} className="text-[var(--acc)] shrink-0 mt-0.5" /> {i}
          </li>
        ))}
      </ul>
      {kind === "setup" && setupDone ? (
        <div className="mt-6 chip chip-active w-fit" data-testid="setup-paid-badge">Setup fee paid</div>
      ) : (
        <button data-testid={`pay-${kind}-btn`} onClick={() => pay(kind)} disabled={!!busy || (kind === "monthly" && !setupDone)}
          className="btn-primary mt-6 flex items-center justify-center gap-2 disabled:opacity-40">
          {busy === kind ? <Loader2 size={15} className="animate-spin" /> : <ArrowRight size={15} />}
          {kind === "setup" ? "Pay the setup fee" : "Start monthly hosting"}
        </button>
      )}
      {kind === "monthly" && !setupDone && (
        <div className="text-[11px] text-[var(--mut)] mt-2">Unlocks right after the setup fee clears.</div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-[#080808] text-white" data-testid="upgrade-page">
      <header className="px-6 sm:px-10 py-5 flex items-center justify-between border-b border-white/[0.07]">
        <Link to="/" data-testid="upgrade-brand-link"><Logo variant="white" size={17} /></Link>
        <div className="flex items-center gap-3 text-xs">
          {member ? <span className="text-white/50" data-testid="upgrade-email">{member.email}</span>
            : <Link to="/login" className="btn-ghost !py-1.5 !px-3">Sign in</Link>}
        </div>
      </header>

      <main className="px-6 sm:px-10 py-14 max-w-5xl mx-auto">
        <span className="ed-pill">Membership</span>
        <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl tracking-tight mt-5 max-w-2xl">
          Two payments and the whole platform is yours.
        </h1>
        <p className="text-base text-white/55 mt-4 max-w-xl">
          Browsing the templates is free forever. Building, publishing and managing client sites needs an
          active membership — a one-time setup fee, then hosting and maintenance every month.
        </p>

        {member?.suspended && (
          <div className="mt-8 rounded-2xl border border-amber-500/30 bg-amber-500/[0.07] p-4 text-sm" data-testid="suspended-banner">
            Your membership is paused, so your workspace is locked. Your clients, sites and data are all
            preserved — restart the monthly payment below to get straight back in.
          </div>
        )}

        <div className="mt-10">
          <div className="overline mb-3">How would you like to pay?</div>
          <div className="grid sm:grid-cols-3 gap-3">
            {METHODS.map(m => (
              <button key={m.key} data-testid={`method-${m.key}`} onClick={() => { setMethod(m.key); setInterac(null); }}
                className={`text-left rounded-2xl border p-4 transition-colors cursor-pointer ${method === m.key ? "border-[var(--acc)]/60 bg-white/[0.04]" : "border-white/10 hover:border-white/25"}`}>
                <m.icon size={16} className={method === m.key ? "text-[var(--acc)]" : "text-white/45"} />
                <div className="text-sm font-semibold mt-2">{m.label}</div>
                <div className="text-[11px] text-white/45 mt-1">{m.note}</div>
              </button>
            ))}
          </div>
        </div>

        {interac && (
          <div className="mt-6 rounded-2xl border border-[var(--acc)]/40 bg-[var(--acc)]/[0.05] p-5" data-testid="interac-instructions">
            <div className="text-sm font-semibold">Send your e-Transfer</div>
            <div className="text-sm text-white/60 mt-2">{plans?.interac?.instructions}</div>
            <div className="mt-3 grid sm:grid-cols-3 gap-3 text-sm font-mono">
              <div><div className="overline">Send to</div>{interac.send_to}</div>
              <div><div className="overline">Amount</div>${interac.amount} {String(interac.currency).toUpperCase()}</div>
              <div><div className="overline">Reference</div><span data-testid="interac-reference">{interac.reference}</span></div>
            </div>
            <div className="text-[11px] text-white/45 mt-3">We will unlock your access as soon as the transfer is confirmed.</div>
          </div>
        )}

        {!!member?.pending_manual?.length && !interac && (
          <div className="mt-6 rounded-2xl border border-white/10 p-4 text-sm text-white/60" data-testid="pending-manual-note">
            You have an e-Transfer awaiting confirmation ({member.pending_manual[0].plan_name},
            reference {member.pending_manual[0].reference}).
          </div>
        )}

        <div className="mt-10 grid md:grid-cols-2 gap-5">
          <Tier kind="setup" badge="Tier 1 · one-time" title="Agency setup fee" price="1,000"
            cadence="once, not recurring" includes={SETUP_INCLUDES} active={step === "setup"} />
          <Tier kind="monthly" badge="Tier 2 · monthly" title="Hosting & maintenance" price="300"
            cadence="per month" includes={MONTHLY_INCLUDES} active={step === "monthly"} />
        </div>

        <div className="mt-8 flex items-start gap-2.5 text-xs text-white/40">
          <ShieldCheck size={14} className="shrink-0 mt-0.5" />
          Payments and receipts are handled by Stripe — we never see your card details. Cancel the monthly
          plan whenever you like from your account settings; access runs to the end of the period you paid for.
        </div>

        <div className="mt-10 flex flex-wrap gap-3">
          <Link to="/templates" className="btn-ghost" data-testid="browse-templates-link">Keep browsing the templates</Link>
          {member && <Link to="/account" className="btn-ghost" data-testid="upgrade-account-link">Account settings</Link>}
        </div>
      </main>
    </div>
  );
}
