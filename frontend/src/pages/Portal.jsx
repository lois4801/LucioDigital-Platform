import { PageSkeleton } from "@/components/PageTransition";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { LookVoting } from "@/components/LookVoting";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { ExternalLink, Receipt, Inbox, MessageSquarePlus, Loader2, Layers, LogOut, Globe } from "lucide-react";

export default function Portal() {
  const nav = useNavigate();
  const { user, logout } = useAuth();
  const [data, setData] = useState(null);
  const [sel, setSel] = useState(null);
  const [req, setReq] = useState({ title: "", details: "" });
  const [busy, setBusy] = useState(false);
  useEffect(() => { load(); }, []);
  async function load() { try { const { data } = await api.get("/portal"); setData(data); setSel(s => s || data.apps[0]?.app_id); } catch { toast.error("Failed to load portal"); } }
  const app = data?.apps.find(a => a.app_id === sel);
  async function submit() {
    setBusy(true);
    try { await api.post(`/portal/${sel}/request`, req); setReq({ title: "", details: "" }); toast.success("Request sent to your agency"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); } finally { setBusy(false); }
  }
  if (!data) return <PageSkeleton testid="portal-skeleton" />;
  const inp = "w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--acc)]";

  return (
    <div className="min-h-screen" data-testid="client-portal">
      <header className="sticky top-0 z-30 backdrop-blur-xl bg-[var(--bg)]/85 border-b border-[var(--line)] px-6 lg:px-10 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3"><Layers size={18} className="text-[var(--acc)]" /><div><div className="overline">Client Portal</div><div className="font-display text-lg font-semibold">Welcome, {data.user.name || data.user.email}</div></div></div>
        <div className="flex items-center gap-2">{app?.role === "owner" && <button data-testid="portal-to-dashboard-btn" onClick={() => nav("/dashboard")} className="btn-ghost text-sm !py-2 !px-4">Agency dashboard</button>}<button data-testid="portal-logout-btn" onClick={logout} className="w-10 h-10 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-white/5"><LogOut size={14} /></button></div>
      </header>
      <main className="px-6 lg:px-10 py-8 grid lg:grid-cols-[260px_1fr] gap-6">
        <aside className="space-y-2">
          <div className="overline px-1 mb-2">Your projects</div>
          {data.apps.map(a => <button key={a.app_id} data-testid={`portal-app-${a.app_id}`} onClick={() => setSel(a.app_id)} className={`w-full text-left card-surface p-3 flex items-center gap-3 ${sel === a.app_id ? "!border-[var(--acc)]/50" : ""}`}>
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: a.color }} /><div className="min-w-0 flex-1"><div className="font-semibold text-sm truncate">{a.name}</div><div className="text-[10px] font-mono text-[var(--dim)]">{a.kind} · {a.role}</div></div>{a.leads_unread > 0 && <span className="chip chip-active" style={{ padding: "1px 6px" }}>{a.leads_unread}</span>}</button>)}
          {data.apps.length === 0 && <div className="text-sm text-[var(--mut)] p-3">No projects shared with you yet.</div>}
        </aside>
        {app && <div className="space-y-5">
          <div className="card-surface overflow-hidden">
            {app.thumbnail && <img src={app.thumbnail} alt="" className="w-full h-44 object-cover" />}
            <div className="p-6 flex flex-wrap items-center gap-3">
              <div className="flex-1"><div className="font-display text-2xl font-semibold">{app.name}</div><div className="text-xs font-mono text-[var(--mut)] mt-1">{app.industry} · status {app.status} · plan {app.plan || "—"}</div></div>
              {app.custom_domain && <span className={`chip ${app.domain_status === "verified" ? "chip-active" : "chip-maint"}`}><Globe size={11} /> {app.custom_domain}</span>}
              {app.preview_token ? <a data-testid="portal-live-link" href={`/p/${app.preview_token}`} target="_blank" rel="noreferrer" className="btn-primary text-sm !py-2 !px-4 flex items-center gap-2"><ExternalLink size={14} /> Open live site</a> : <span className="chip">Not published yet</span>}
            </div>
          </div>
          <LookVoting appId={app.app_id} />
          <div className="grid md:grid-cols-3 gap-4">
            <div className="card-surface p-5"><div className="overline flex items-center gap-2 mb-3"><Receipt size={11} /> Invoices</div>
              {app.invoices.length === 0 ? <div className="text-xs text-[var(--mut)]">No invoices yet.</div> : app.invoices.map(i => <div key={i.session_id} data-testid="portal-invoice-row" className="flex justify-between text-xs py-1.5 border-b border-[var(--line)] last:border-0"><span>{i.plan_name}<div className="font-mono text-[10px] text-[var(--dim)]">{new Date(i.created_at).toLocaleDateString()}</div></span><span className="text-right font-mono">${i.amount}<div className={`text-[10px] ${i.payment_status === "paid" ? "text-[var(--acc)]" : "text-amber-300"}`}>{i.payment_status}</div></span></div>)}</div>
            <div className="card-surface p-5"><div className="overline flex items-center gap-2 mb-3"><Inbox size={11} /> Leads</div><div className="font-display text-4xl font-bold">{app.leads}</div><div className="text-xs text-[var(--mut)] mt-1">{app.leads_unread} awaiting reply · collected from your site's contact form and AI chat</div></div>
            <div className="card-surface p-5"><div className="overline mb-3">Recent activity</div>{app.activity.slice(0, 5).map((l, i) => <div key={i} className="text-[11px] py-1 border-b border-[var(--line)] last:border-0 truncate"><span className="text-[var(--dim)] font-mono">{new Date(l.created_at).toLocaleDateString()}</span> {l.message}</div>)}</div>
          </div>
          <div className="grid lg:grid-cols-2 gap-4">
            <div className="card-surface p-5"><div className="overline flex items-center gap-2 mb-3"><MessageSquarePlus size={11} className="text-[var(--acc)]" /> Request a change</div>
              <div className="space-y-2"><input data-testid="portal-request-title-input" value={req.title} onChange={e => setReq({ ...req, title: e.target.value })} placeholder="e.g. Update the pricing page" className={inp} /><textarea data-testid="portal-request-details-input" value={req.details} onChange={e => setReq({ ...req, details: e.target.value })} rows={4} placeholder="Describe what you'd like changed…" className={inp} />
                <button data-testid="portal-request-submit-btn" onClick={submit} disabled={busy || !req.title.trim() || !req.details.trim()} className="btn-primary w-full text-sm disabled:opacity-50">{busy ? <Loader2 size={14} className="animate-spin mx-auto" /> : "Send request"}</button></div></div>
            <div className="card-surface p-5"><div className="overline mb-3">Your requests</div>
              {app.requests.length === 0 ? <div className="text-xs text-[var(--mut)]">No requests yet.</div> : app.requests.map(r => <div key={r.message_id} data-testid="portal-request-row" className="py-2 border-b border-[var(--line)] last:border-0"><div className="text-sm font-semibold">{r.subject.replace("Change request: ", "")}</div><div className="text-[10px] font-mono text-[var(--dim)]">{new Date(r.created_at).toLocaleString()} · {r.replies?.length ? `${r.replies.length} reply` : r.status === "read" ? "seen by agency" : "pending"}</div>{r.replies?.map(x => <div key={x.reply_id} className="mt-1 text-xs border-l-2 border-[var(--acc)] pl-2">{x.body}</div>)}</div>)}</div>
          </div>
        </div>}
      </main>
    </div>
  );
}
