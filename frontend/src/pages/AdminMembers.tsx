import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Loader2, Search, Mail, ShieldOff, ShieldCheck, ArrowUpCircle, ArrowDownCircle, Check, X, KeyRound } from "lucide-react";
import api from "@/lib/api";
import Logo from "@/components/Logo";

const fmt = (iso: string) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "—");

export default function AdminMembers() {
  const [rows, setRows] = useState<any[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [manual, setManual] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState("");
  const [open, setOpen] = useState<any>(null);
  const [payments, setPayments] = useState<any>(null);
  const [mail, setMail] = useState({ subject: "", body: "" });
  const [keys, setKeys] = useState<any>(null);
  const [keyForm, setKeyForm] = useState({ publishable_key: "", secret_key: "", interac_email: "", interac_instructions: "" });

  async function load() {
    try {
      const [m, mp, k] = await Promise.all([
        api.get("/admin/members", { params: { q } }),
        api.get("/admin/manual-payments", { params: { status: "pending" } }),
        api.get("/admin/stripe-keys"),
      ]);
      setRows(m.data.members || []);
      setPendingCount(m.data.pending_manual || 0);
      setManual(mp.data || []);
      setKeys(k.data);
      setKeyForm(f => ({ ...f, interac_email: k.data.interac_email || "", interac_instructions: k.data.interac_instructions || "" }));
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not load members");
    }
  }
  useEffect(() => { load(); }, [q]);

  async function act(userId: string, path: string, ok: string, body: any = {}) {
    setBusy(userId + path);
    try {
      await api.post(`/admin/members/${userId}/${path}`, body);
      toast.success(ok);
      await load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "That did not work");
    } finally { setBusy(""); }
  }

  async function decideManual(id: string, decision: "confirm" | "reject") {
    setBusy(id);
    try {
      await api.post(`/admin/manual-payments/${id}/${decision}`);
      toast.success(decision === "confirm" ? "Payment confirmed — access unlocked" : "Declaration rejected");
      await load();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "That did not work");
    } finally { setBusy(""); }
  }

  async function openMember(m: any) {
    setOpen(m); setPayments(null); setMail({ subject: "", body: "" });
    const { data } = await api.get(`/admin/members/${m.user_id}/payments`);
    setPayments(data);
  }

  async function sendMail() {
    if (!mail.subject.trim() || !mail.body.trim()) { toast.error("Add a subject and a message"); return; }
    setBusy("mail");
    try {
      await api.post(`/admin/members/${open.user_id}/email`, mail);
      toast.success(`Email sent to ${open.email}`);
      setMail({ subject: "", body: "" });
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not send that email");
    } finally { setBusy(""); }
  }

  async function saveKeys() {
    setBusy("keys");
    try {
      const { data } = await api.put("/admin/stripe-keys", keyForm);
      setKeys(data);
      setKeyForm(f => ({ ...f, publishable_key: "", secret_key: "" }));
      toast.success("Payment settings saved");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not save those settings");
    } finally { setBusy(""); }
  }

  return (
    <div className="min-h-screen" data-testid="admin-members-page">
      <header className="px-6 lg:px-10 py-5 flex items-center justify-between border-b border-[var(--line)]">
        <Link to="/dashboard" data-testid="admin-brand-link"><Logo variant="white" size={17} /></Link>
        <Link to="/dashboard" className="btn-ghost !py-1.5 !px-3 text-xs">Dashboard</Link>
      </header>

      <main className="px-6 lg:px-10 py-8 space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <span className="overline">Member management</span>
            <h1 className="font-display text-3xl tracking-tight mt-1">{rows.length} accounts</h1>
          </div>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--mut)]" />
            <input data-testid="member-search" value={q} onChange={e => setQ(e.target.value)} placeholder="Search name or email"
              className="bg-[var(--bg-2)] border border-[var(--line)] rounded-xl pl-9 pr-3 py-2 text-sm outline-none focus:border-[var(--acc)] w-64" />
          </div>
        </div>

        {pendingCount > 0 && (
          <div className="card-surface p-5" data-testid="manual-queue">
            <div className="overline mb-3">e-Transfers awaiting your confirmation ({pendingCount})</div>
            <div className="rounded-xl border border-[var(--line)] divide-y divide-[var(--line)]">
              {manual.map(m => (
                <div key={m.manual_id} className="p-3 flex flex-wrap items-center justify-between gap-3 text-sm" data-testid="manual-row">
                  <div className="min-w-0">
                    <div className="truncate">{m.email} · {m.plan_name}</div>
                    <div className="text-[10px] font-mono text-[var(--dim)]">${m.amount} {String(m.currency).toUpperCase()} · ref {m.reference} · {fmt(m.created_at)}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button data-testid={`manual-confirm-${m.manual_id}`} onClick={() => decideManual(m.manual_id, "confirm")}
                      disabled={!!busy} className="btn-primary !py-1.5 !px-3 text-xs flex items-center gap-1"><Check size={12} /> Confirm</button>
                    <button data-testid={`manual-reject-${m.manual_id}`} onClick={() => decideManual(m.manual_id, "reject")}
                      disabled={!!busy} className="btn-ghost !py-1.5 !px-3 text-xs flex items-center gap-1"><X size={12} /> Reject</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="card-surface p-5">
          <div className="rounded-xl border border-[var(--line)] divide-y divide-[var(--line)] overflow-hidden">
            <div className="hidden md:grid grid-cols-[2fr_1fr_1fr_1fr_auto] gap-3 px-3 py-2 overline">
              <span>Member</span><span>Access</span><span>Signed up</span><span>Last login</span><span>Actions</span>
            </div>
            {rows.map(m => (
              <div key={m.user_id} data-testid="member-row"
                className="grid md:grid-cols-[2fr_1fr_1fr_1fr_auto] gap-3 px-3 py-3 items-center text-sm">
                <button onClick={() => openMember(m)} data-testid={`member-open-${m.user_id}`} className="text-left min-w-0 cursor-pointer group">
                  <div className="truncate group-hover:text-[var(--acc)] transition-colors">{m.name || m.email}</div>
                  <div className="text-[10px] font-mono text-[var(--dim)] truncate">{m.email} · {m.clients} client{m.clients === 1 ? "" : "s"} · {m.payments} payment{m.payments === 1 ? "" : "s"}</div>
                </button>
                <span className={`chip w-fit ${["admin", "paid", "client"].includes(m.access) ? "chip-active" : ""}`} data-testid={`member-access-${m.user_id}`}>
                  {m.suspended ? "suspended" : m.access}
                </span>
                <span className="text-xs text-[var(--mut)]">{fmt(m.created_at)}</span>
                <span className="text-xs text-[var(--mut)]">{fmt(m.last_login_at)}</span>
                <div className="flex items-center gap-1.5">
                  {m.access !== "admin" && (m.access === "paid" ? (
                    <button title="Downgrade to free" data-testid={`member-downgrade-${m.user_id}`} disabled={!!busy}
                      onClick={() => act(m.user_id, "tier", `${m.email} moved to free`, { tier: "free" })}
                      className="chip cursor-pointer flex items-center gap-1"><ArrowDownCircle size={11} /> Free</button>
                  ) : (
                    <button title="Upgrade to paid" data-testid={`member-upgrade-${m.user_id}`} disabled={!!busy}
                      onClick={() => act(m.user_id, "tier", `${m.email} upgraded to paid`, { tier: "paid" })}
                      className="chip cursor-pointer flex items-center gap-1"><ArrowUpCircle size={11} /> Paid</button>
                  ))}
                  {m.access !== "admin" && (m.suspended ? (
                    <button title="Reactivate" data-testid={`member-reactivate-${m.user_id}`} disabled={!!busy}
                      onClick={() => act(m.user_id, "reactivate", `${m.email} reactivated`)}
                      className="chip cursor-pointer flex items-center gap-1"><ShieldCheck size={11} /> Reactivate</button>
                  ) : (
                    <button title="Suspend" data-testid={`member-suspend-${m.user_id}`} disabled={!!busy}
                      onClick={() => act(m.user_id, "suspend", `${m.email} suspended`)}
                      className="chip cursor-pointer flex items-center gap-1"><ShieldOff size={11} /> Suspend</button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card-surface p-5" data-testid="stripe-settings-card">
          <div className="overline flex items-center gap-2 mb-1"><KeyRound size={11} className="text-[var(--acc)]" /> Payment settings</div>
          <div className="text-xs text-[var(--mut)] mb-4">
            {keys?.using_own_keys
              ? `Using your own Stripe keys (${keys.mode} mode, secret ending ${keys.secret_key_hint}).`
              : "Using the built-in Stripe test connection. Paste your own keys to take over billing."}
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            <input data-testid="stripe-publishable-input" value={keyForm.publishable_key} placeholder={keys?.publishable_key || "pk_live_…"}
              onChange={e => setKeyForm({ ...keyForm, publishable_key: e.target.value })}
              className="bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]" />
            <input data-testid="stripe-secret-input" type="password" value={keyForm.secret_key} placeholder="sk_live_…"
              onChange={e => setKeyForm({ ...keyForm, secret_key: e.target.value })}
              className="bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]" />
            <input data-testid="interac-email-input" value={keyForm.interac_email} placeholder="e-Transfer email"
              onChange={e => setKeyForm({ ...keyForm, interac_email: e.target.value })}
              className="bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]" />
            <input data-testid="interac-instructions-input" value={keyForm.interac_instructions} placeholder="e-Transfer instructions shown to members"
              onChange={e => setKeyForm({ ...keyForm, interac_instructions: e.target.value })}
              className="bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]" />
          </div>
          <button data-testid="save-stripe-keys-btn" onClick={saveKeys} disabled={busy === "keys"} className="btn-primary mt-4">
            {busy === "keys" ? <Loader2 size={14} className="animate-spin" /> : "Save payment settings"}
          </button>
        </div>
      </main>

      {open && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" data-testid="member-drawer"
          onClick={e => { if (e.target === e.currentTarget) setOpen(null); }}>
          <div className="card-surface w-full max-w-lg max-h-[85vh] overflow-y-auto p-6">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="overline">{open.access}</div>
                <div className="font-display text-2xl truncate">{open.name || open.email}</div>
                <div className="text-xs text-[var(--mut)] font-mono truncate">{open.email}</div>
              </div>
              <button onClick={() => setOpen(null)} data-testid="member-drawer-close" className="chip cursor-pointer"><X size={12} /></button>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div><div className="overline">Signed up</div>{fmt(open.created_at)}</div>
              <div><div className="overline">Last login</div>{fmt(open.last_login_at)}</div>
              <div><div className="overline">Next billing</div>{fmt(open.current_period_end)}</div>
              <div><div className="overline">Clients</div>{open.clients}</div>
            </div>

            <div className="overline mt-5 mb-2">Stripe payments</div>
            {!payments && <Loader2 size={14} className="animate-spin text-[var(--mut)]" />}
            <div className="rounded-xl border border-[var(--line)] divide-y divide-[var(--line)]">
              {payments && [...(payments.stripe || []), ...(payments.manual || [])].length === 0 && (
                <div className="p-3 text-xs text-[var(--mut)]">No payments recorded.</div>
              )}
              {(payments?.stripe || []).map(p => (
                <div key={p.session_id} className="p-2.5 flex justify-between text-xs" data-testid="member-payment-row">
                  <span className="truncate">{p.plan_name || p.lookup_key} · {fmt(p.created_at)}</span>
                  <span className="font-mono">${p.amount} {p.payment_status}</span>
                </div>
              ))}
              {(payments?.manual || []).map(p => (
                <div key={p.manual_id} className="p-2.5 flex justify-between text-xs" data-testid="member-payment-row">
                  <span className="truncate">{p.plan_name} e-Transfer · ref {p.reference}</span>
                  <span className="font-mono">${p.amount} {p.status}</span>
                </div>
              ))}
            </div>

            <div className="overline mt-5 mb-2 flex items-center gap-2"><Mail size={11} /> Send this member an email</div>
            <input data-testid="member-mail-subject" value={mail.subject} onChange={e => setMail({ ...mail, subject: e.target.value })}
              placeholder="Subject" className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]" />
            <textarea data-testid="member-mail-body" value={mail.body} onChange={e => setMail({ ...mail, body: e.target.value })}
              rows={4} placeholder="Your message" className="w-full mt-2 bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]" />
            <button data-testid="member-mail-send" onClick={sendMail} disabled={busy === "mail"} className="btn-primary mt-3">
              {busy === "mail" ? <Loader2 size={14} className="animate-spin" /> : "Send email"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
