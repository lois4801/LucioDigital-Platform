import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Flame, Mail, MessageSquare, FileText, Star, Archive, CheckCheck, Inbox, ExternalLink } from "lucide-react";
import api from "@/lib/api";
import { LeadReply } from "@/components/LeadReply";
import { Attachments, AttachmentPill, attachmentCount } from "@/components/Attachments";

const SRC = { contact: { label: "Contact form", Icon: Mail }, chat: { label: "AI chat", Icon: MessageSquare }, request: { label: "Change request", Icon: FileText } };
const FILTERS = [["unread", "New"], ["read", "Reviewed"], ["archived", "Archived"], ["all", "All"]];

export default function Leads() {
  const nav = useNavigate();
  const [data, setData] = useState({ messages: [], unread: 0 });
  const [filter, setFilter] = useState("unread");
  const [open, setOpen] = useState(null);
  const [loading, setLoading] = useState(true);

  async function load() { try { const r = await api.get("/inbox"); setData(r.data); } catch { toast.error("Could not load leads"); } finally { setLoading(false); } }
  useEffect(() => { load(); }, []);

  const rows = useMemo(() => {
    const list = filter === "all" ? data.messages : data.messages.filter(m => m.status === filter);
    return [...list].sort((a, b) => (b.hot - a.hot) || ((b.score || 0) - (a.score || 0)) || (b.updated_at || "").localeCompare(a.updated_at || ""));
  }, [data, filter]);

  async function patch(m, upd) {
    const r = await api.patch(`/apps/${m.app_id}/inbox/${m.message_id}`, upd);
    setData(d => { const messages = d.messages.map(x => x.message_id === m.message_id ? { ...x, ...r.data } : x); return { messages, unread: messages.filter(x => x.status === "unread").length }; });
    if (open?.message_id === m.message_id) setOpen(o => ({ ...o, ...r.data }));
  }
  async function markAllRead() {
    const pending = data.messages.filter(m => m.status === "unread");
    await Promise.all(pending.map(m => api.patch(`/apps/${m.app_id}/inbox/${m.message_id}`, { status: "read" })));
    toast.success(`${pending.length} leads marked reviewed`); load();
  }
  function view(m) { setOpen(m); if (m.status === "unread") patch(m, { status: "read" }); }

  return (
    <div data-testid="leads-page" className="min-h-screen px-6 lg:px-14 py-8 max-w-7xl mx-auto">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
        <div>
          <button data-testid="leads-back-btn" onClick={() => nav("/dashboard")} className="text-sm text-[var(--mut)] hover:text-white inline-flex items-center gap-1 mb-3"><ArrowLeft size={14} /> Dashboard</button>
          <div className="overline mb-1 flex items-center gap-2"><Inbox size={12} className="text-[var(--acc)]" /> Lead inbox · all projects</div>
          <h1 className="font-display text-3xl lg:text-4xl font-bold tracking-tight">{data.unread} new lead{data.unread === 1 ? "" : "s"} <span data-testid="leads-unread-count" className="chip chip-active badge-glow align-middle ml-2">{data.unread}</span></h1>
        </div>
        <button data-testid="leads-mark-all-btn" onClick={markAllRead} disabled={!data.unread} className="btn-ghost text-sm flex items-center gap-2 disabled:opacity-40"><CheckCheck size={14} /> Mark all reviewed</button>
      </div>

      <div className="flex gap-1 mb-5 border-b border-[var(--line)]">
        {FILTERS.map(([k, l]) => { const c = k === "all" ? data.messages.length : data.messages.filter(m => m.status === k).length; return (
          <button key={k} data-testid={`leads-filter-${k}`} onClick={() => setFilter(k)} className={`px-4 py-2.5 text-sm border-b-2 -mb-px transition-colors ${filter === k ? "border-[var(--acc)] text-white" : "border-transparent text-[var(--mut)] hover:text-white"}`}>{l} <span className="font-mono text-[11px] text-[var(--dim)] ml-1">{c}</span></button>); })}
      </div>

      <div className="grid lg:grid-cols-[1fr_380px] gap-5">
        <div className="card-surface overflow-hidden">
          {loading ? <div className="p-10 text-center text-sm text-[var(--mut)]">Loading leads…</div> : rows.length === 0 ? (
            <div data-testid="leads-empty" className="p-14 text-center text-sm text-[var(--mut)]">No {filter === "all" ? "" : FILTERS.find(f => f[0] === filter)[1].toLowerCase()} leads. Leads arrive from contact forms, AI chat and client change requests on your live sites.</div>
          ) : (
            <table className="w-full text-sm">
              <thead><tr className="text-left text-[11px] uppercase tracking-wider text-[var(--dim)] border-b border-[var(--line)]">
                <th className="px-4 py-3 font-medium">Lead</th><th className="px-4 py-3 font-medium hidden md:table-cell">Contact</th><th className="px-4 py-3 font-medium hidden lg:table-cell">Source</th><th className="px-4 py-3 font-medium hidden md:table-cell">Received</th><th className="px-4 py-3 font-medium">Status</th><th className="px-2 py-3" /></tr></thead>
              <tbody>
                {rows.map(m => { const s = SRC[m.source] || SRC.contact; return (
                  <tr key={m.message_id} data-testid={`lead-row-${m.message_id}`} onClick={() => view(m)} className={`border-b border-[var(--line)]/60 cursor-pointer hover:bg-white/[0.03] ${open?.message_id === m.message_id ? "bg-[var(--acc)]/10" : ""}`}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">{m.status === "unread" && <span className="w-1.5 h-1.5 rounded-full bg-[var(--acc)] pulse-dot shrink-0" />}<span className={`truncate max-w-[220px] ${m.status === "unread" ? "font-semibold" : ""}`}>{m.from_name || "Website visitor"}</span>{m.hot && <Flame size={13} className="text-orange-400 shrink-0" />}</div>
                      <div className="text-xs text-[var(--mut)] truncate max-w-[260px] mt-0.5 flex items-center gap-1.5"><AttachmentPill count={attachmentCount(m.body)} /><span className="truncate">{m.subject || m.body?.slice(0, 70)}</span></div>
                      <div className="text-[10px] font-mono mt-1" style={{ color: m.app_color || "var(--dim)" }}>{m.app_name}</div>
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell text-[var(--mut)] text-xs">{m.from_email || "—"}</td>
                    <td className="px-4 py-3 hidden lg:table-cell"><span className="inline-flex items-center gap-1.5 text-xs text-[var(--mut)]"><s.Icon size={12} /> {s.label}</span></td>
                    <td className="px-4 py-3 hidden md:table-cell text-xs text-[var(--mut)] whitespace-nowrap">{new Date(m.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</td>
                    <td className="px-4 py-3"><span data-testid={`lead-status-${m.message_id}`} className={`chip ${m.status === "unread" ? "chip-active" : ""}`}>{m.status === "unread" ? "New" : m.replies?.length ? "Replied" : m.status === "read" ? "Reviewed" : "Archived"}</span>{m.score != null && <span className="ml-2 text-[10px] font-mono text-[var(--dim)]">{m.score}</span>}</td>
                    <td className="px-2 py-3 text-right"><button data-testid={`lead-star-${m.message_id}`} onClick={e => { e.stopPropagation(); patch(m, { starred: !m.starred }); }} className={`p-1.5 rounded-md hover:bg-white/10 ${m.starred ? "text-amber-400" : "text-[var(--dim)]"}`}><Star size={13} fill={m.starred ? "currentColor" : "none"} /></button></td>
                  </tr>); })}
              </tbody>
            </table>
          )}
        </div>

        <aside className="card-surface p-5 h-fit sticky top-6" data-testid="lead-detail">
          {!open ? <div className="text-sm text-[var(--mut)] text-center py-10">Select a lead to see details</div> : (
            <div className="space-y-4">
              <div>
                <div className="flex items-center gap-2">{open.hot && <Flame size={14} className="text-orange-400" />}<div className="font-display text-lg font-semibold">{open.from_name || "Website visitor"}</div></div>
                <div className="text-xs text-[var(--mut)] mt-1">{open.from_email ? <a href={`mailto:${open.from_email}`} className="hover:text-white">{open.from_email}</a> : "No email captured"}</div>
              </div>
              <dl className="grid grid-cols-2 gap-2 text-xs">
                <dt className="text-[var(--dim)]">Project</dt><dd style={{ color: open.app_color }}>{open.app_name}</dd>
                <dt className="text-[var(--dim)]">Source</dt><dd>{(SRC[open.source] || SRC.contact).label}</dd>
                <dt className="text-[var(--dim)]">Received</dt><dd>{new Date(open.created_at).toLocaleString()}</dd>
                <dt className="text-[var(--dim)]">Status</dt><dd className="capitalize">{open.status === "unread" ? "New" : open.status}</dd>
                {open.score != null && <><dt className="text-[var(--dim)]">AI score</dt><dd>{open.score}/100 · {open.intent}</dd></>}
              </dl>
              {open.score_reason && <div className="text-xs text-[var(--mut)] bg-white/5 rounded-lg p-3">{open.score_reason}</div>}
              <div className="text-sm whitespace-pre-wrap leading-relaxed max-h-[36vh] overflow-y-auto scrollbar-thin border-t border-[var(--line)] pt-3">{open.body}</div>
              <Attachments body={open.body} testid="lead-detail-attachments" />
              <div className="flex flex-wrap gap-2 pt-1">
                {open.status !== "unread" && <button data-testid="lead-mark-new-btn" onClick={() => patch(open, { status: "unread" })} className="btn-ghost text-xs !py-1.5 !px-3">Mark as new</button>}
                {open.status !== "archived" ? <button data-testid="lead-archive-btn" onClick={() => patch(open, { status: "archived" })} className="btn-ghost text-xs !py-1.5 !px-3 flex items-center gap-1"><Archive size={12} /> Archive</button>
                  : <button data-testid="lead-unarchive-btn" onClick={() => patch(open, { status: "read" })} className="btn-ghost text-xs !py-1.5 !px-3">Restore</button>}
                <button data-testid="lead-open-project-btn" onClick={() => nav(`/apps/${open.app_id}`)} className="btn-primary text-xs !py-1.5 !px-3 flex items-center gap-1">Open in project <ExternalLink size={12} /></button>
              </div>
              <LeadReply lead={open} onUpdated={(m) => { setOpen(m); setData(d => ({ ...d, messages: d.messages.map(x => x.message_id === m.message_id ? m : x) })); }} />
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
