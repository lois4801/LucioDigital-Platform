import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Loader2, CreditCard, CalendarClock, RotateCcw, XCircle } from "lucide-react";
import api from "@/lib/api";
import Logo from "@/components/Logo";
import { useMembership } from "@/lib/membership";

const fmt = (iso: string) => (iso ? new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" }) : "—");

export default function Account() {
  const { member, loading, refresh } = useMembership();
  const [pay, setPay] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get("/membership/payments").then(r => setPay(r.data)).catch(() => {}); }, []);

  async function act(path: string, ok: string) {
    setBusy(true);
    try {
      await api.post(`/membership/${path}`);
      await refresh();
      toast.success(ok);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "That did not go through");
    } finally { setBusy(false); }
  }

  if (loading) return null;

  const status = member?.status || "free";
  const label = member?.is_admin ? "Platform admin"
    : member?.suspended ? "Paused"
    : status === "active" ? (member?.cancel_at_period_end ? "Cancelling" : "Active")
    : status === "setup_paid" ? "Setup fee paid" : "Free account";

  return (
    <div className="min-h-screen" data-testid="account-page">
      <header className="px-6 lg:px-10 py-5 flex items-center justify-between border-b border-[var(--line)]">
        <Link to="/dashboard" data-testid="account-brand-link"><Logo variant="white" size={17} /></Link>
        <div className="flex items-center gap-2">
          {member?.is_admin && <Link to="/admin/members" className="btn-ghost !py-1.5 !px-3 text-xs" data-testid="account-admin-link">Members</Link>}
          <Link to="/dashboard" className="btn-ghost !py-1.5 !px-3 text-xs">Dashboard</Link>
        </div>
      </header>

      <main className="px-6 lg:px-10 py-10 max-w-3xl space-y-5">
        <div>
          <span className="overline">Account settings</span>
          <h1 className="font-display text-3xl sm:text-4xl tracking-tight mt-2">{member?.name || member?.email}</h1>
        </div>

        <div className="card-surface p-6" data-testid="account-status-card">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="overline">Membership</div>
              <div className="font-display text-2xl mt-1" data-testid="account-status">{label}</div>
            </div>
            <span className={`chip ${member?.full_access ? "chip-active" : ""}`}>{member?.access}</span>
          </div>

          <div className="mt-5 grid sm:grid-cols-2 gap-4 text-sm">
            <div className="flex items-start gap-2.5">
              <CreditCard size={15} className="text-[var(--acc)] mt-0.5" />
              <div>
                <div className="text-[var(--mut)] text-xs">Setup fee</div>
                <div data-testid="account-setup">{member?.setup_paid_at ? `Paid ${fmt(member.setup_paid_at)}` : member?.grandfathered ? "Included" : "Not paid yet"}</div>
              </div>
            </div>
            <div className="flex items-start gap-2.5">
              <CalendarClock size={15} className="text-[var(--acc)] mt-0.5" />
              <div>
                <div className="text-[var(--mut)] text-xs">{member?.cancel_at_period_end ? "Access ends" : "Next billing date"}</div>
                <div data-testid="account-period-end">{member?.grandfathered && !member?.current_period_end ? "No monthly billing on your account" : fmt(member?.current_period_end)}</div>
              </div>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap gap-2">
            {!member?.full_access && <Link to="/upgrade" className="btn-primary" data-testid="account-upgrade-btn">Upgrade now</Link>}
            {status === "active" && !member?.cancel_at_period_end && !member?.grandfathered && (
              <button data-testid="account-cancel-btn" onClick={() => act("cancel", "Monthly plan cancels at the end of this period")}
                disabled={busy} className="btn-ghost flex items-center gap-2"><XCircle size={14} /> Cancel monthly plan</button>
            )}
            {member?.cancel_at_period_end && (
              <button data-testid="account-resume-btn" onClick={() => act("resume", "Monthly plan resumed")}
                disabled={busy} className="btn-primary flex items-center gap-2"><RotateCcw size={14} /> Keep my plan</button>
            )}
            {busy && <Loader2 size={15} className="animate-spin text-[var(--mut)] self-center" />}
          </div>
          <div className="text-[11px] text-[var(--mut)] mt-3">
            Receipts and invoices are emailed automatically by Stripe. Cancelling keeps your access until the
            end of the period you have already paid for — nothing is deleted.
          </div>
        </div>

        <div className="card-surface p-6" data-testid="account-payments-card">
          <div className="overline mb-3">Payment history</div>
          <div className="rounded-xl border border-[var(--line)] divide-y divide-[var(--line)]">
            {[...(pay?.stripe || []), ...(pay?.manual || [])].length === 0 && (
              <div className="p-4 text-xs text-[var(--mut)]">No payments yet.</div>
            )}
            {(pay?.stripe || []).map(p => (
              <div key={p.session_id} className="p-3 flex items-center justify-between gap-3 text-sm" data-testid="payment-row">
                <div className="min-w-0">
                  <div className="truncate">{p.plan_name}</div>
                  <div className="text-[10px] font-mono text-[var(--dim)]">{fmt(p.created_at)} · {p.method === "bank" ? "bank debit" : "card"}</div>
                </div>
                <span className={`chip ${p.payment_status === "paid" ? "chip-active" : ""}`}>${p.amount} · {p.payment_status}</span>
              </div>
            ))}
            {(pay?.manual || []).map(p => (
              <div key={p.manual_id} className="p-3 flex items-center justify-between gap-3 text-sm" data-testid="payment-row">
                <div className="min-w-0">
                  <div className="truncate">{p.plan_name} · e-Transfer</div>
                  <div className="text-[10px] font-mono text-[var(--dim)]">{fmt(p.created_at)} · ref {p.reference}</div>
                </div>
                <span className={`chip ${p.status === "confirmed" ? "chip-active" : ""}`}>${p.amount} · {p.status}</span>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
