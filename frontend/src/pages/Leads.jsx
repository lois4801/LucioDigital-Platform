import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Flame, Mail, MessageSquare, FileText, Star, Archive, CheckCheck, Inbox, ExternalLink, FlaskConical, ArrowLeftRight } from "lucide-react";
import api from "@/lib/api";
import { LeadReply } from "@/components/LeadReply";
import { Attachments, AttachmentPill, attachmentCount } from "@/components/Attachments";

const SRC = { contact: { label: "Contact form", Icon: Mail }, chat: { label: "AI chat", Icon: MessageSquare }, request: { label: "Change request", Icon: FileText } };
const TABS = [["real", "Real Leads"], ["test", "Test Leads"], ["archived", "Archived"]];
const CHIPS = [["all", "All"], ["hot", "Hot"], ["unread", "Unread"], ["starred", "Starred"]];

export default function Leads() {
  const nav = useNavigate();
  const [data, setData] = useState({ messages: [], unread: 0 });
  const [tab, setTab] = useState("real");
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState(null);
  const [loading, setLoading] = useState(true);

  async function load() { try { const r = await api.get("/inbox"); setData(r.data); } catch { toast.error("Could not load leads"); } finally { setLoading(false); } }
  useEffect(() => { load(); }, []);

  const counts = useMemo(() => ({
    real: data.messages.filter(m => m.status !== "archived" && (m.lane || "real") === "real").length,
    test: data.messages.filter(m => m.status !== "archived" && m.lane === "test").length,
    archived: data.messages.filter(m => m.status === "archived").length,
  }), [data]);

  const rows = useMemo(() => {
    const inTab = data.messages.filter(m => tab === "archived" ? m.status === "archived"
      : m.status !== "archived" && (m.lane || "real") === tab);
    const list = inTab.filter(m => filter === "all" ? true : filter === "hot" ? m.hot : filter === "unread" ? m.status === "unread" : m.starred);
    const rank = m => tab !== "real" ? 1 : ((m.score ?? 0) > 60 ? 0 : (m.score != null && m.score < 30) ? 2 : 1);
    return [...list].sort((a, b) => (rank(a) - rank(b)) || (b.hot - a.hot)
      || ((b.score || 0) - (a.score || 0)) || (b.updated_at || "").localeCompare(a.updated_at || ""));
  }, [data, tab, filter]);

  async function setLane(m, lane) {
    try {
      const r = await api.patch(`/apps/${m.app_id}/inbox/${m.message_id}/lane`, { lane });
      setData(d => ({ ...d, messages: d.messages.map(x => x.message_id === m.message_id ? { ...x, ...r.data } : x) }));
      if (open?.message_id === m.message_id) setOpen(o => ({ ...o, ...r.data }));
      toast.success(lane === "test" ? "Moved to Test Leads" : "Moved to Real Leads");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not move that lead"); }
  }

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
    <div data-testid="leads-page" className="min-h-screen px-6 lg:px-10 py-8 max-w-[1600px] mx-auto">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
        <div>
          <button data-testid="leads-back-btn" onClick={() => nav("/dashboard")} className="text-sm text-[var(--mut)] hover:text-white inline-flex items-center gap-1 mb-3"><ArrowLeft size={14} /> Dashboard</button>
          <div className="overline mb-1 flex items-center gap-2"><Inbox size={12} className="text-[var(--acc)]" /> Lead inbox · all projects</div>
          <h1 className="font-display text-3xl lg:text-4xl font-bold tracking-tight">{data.unread} new lead{data.unread === 1 ? "" : "s"} <span data-testid="leads-unread-count" className="chip chip-active badge-glow align-middle ml-2">{data.unread}</span></h1>
        </div>
        <button data-testid="leads-mark-all-btn" onClick={markAllRead} disabled={!data.unread} className="btn-ghost text-sm flex items-center gap-2 disabled:opacity-40"><CheckCheck size={14} /> Mark all reviewed</button>
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-5 border-b border-[var(--line)] pb-3">
        {TABS.map(([k, l]) => (
          <button key={k} data-testid={`leads-tab-${k}`} onClick={() => { setTab(k); setOpen(null); }}
            className={`px-4 py-2 rounded-full text-sm flex items-center gap-2 transition-colors ${tab === k ? "bg-[var(--acc)] text-black font-semibold" : "text-[var(--mut)] hover:bg-white/5"}`}>
            {k === "real" ? <Inbox size={13} /> : k === "test" ? <FlaskConical size={13} /> : <Archive size={13} />}
            {l} <span className="font-mono text-[11px] opacity-70">{counts[k]}</span>
          </button>
        ))}
        <div className="flex-1" />
        {CHIPS.map(([k, l]) => (
          <button key={k} data-testid={`leads-filter-${k}`} onClick={() => setFilter(k)}
            className={`chip cursor-pointer ${filter === k ? "chip-active" : ""}`}>{l}</button>
        ))}
      </div>

      <div className="grid xl:grid-cols-[minmax(0,1fr)_360px] gap-5">
        <div className="card-surface overflow-hidden min-w-0">
          {loading ? <div className="p-10 text-center text-sm text-[var(--mut)]">Loading leads…</div> : rows.length === 0 ? (
            <div data-testid="leads-empty" className="p-14 text-center text-sm text-[var(--mut)]">No leads in {TABS.find(t => t[0] === tab)[1]}. Leads arrive from contact forms, AI chat and client change requests on your live sites — anything that looks like a test or demo submission is filed under Test Leads automatically.</div>
          ) : (
            <div className="w-full overflow-x-auto scrollbar-thin" data-testid="leads-table-scroll">
            <table className="w-full text-sm table-fixed min-w-[1040px]" data-testid="leads-table">
              <colgroup>
                <col style={{ width: "38%" }} /><col style={{ width: "20%" }} /><col style={{ width: "12%" }} />
                <col style={{ width: "14%" }} /><col style={{ width: "12%" }} /><col style={{ width: "72px" }} />
              </colgroup>
              <thead><tr className="text-left text-[11px] uppercase tracking-wider text-[var(--dim)] border-b border-[var(--line)]">
                <th className="px-4 py-3 font-medium">Lead</th><th className="px-4 py-3 font-medium">Contact</th><th className="px-4 py-3 font-medium">Source</th><th className="px-4 py-3 font-medium">Received</th><th className="px-4 py-3 font-medium">Status</th><th className="px-2 py-3" /></tr></thead>
              <tbody>
                {rows.map(m => { const s = SRC[m.source] || SRC.contact; return (
                  <tr key={m.message_id} data-testid={`lead-row-${m.message_id}`} onClick={() => view(m)} className={`border-b border-[var(--line)]/60 cursor-pointer hover:bg-white/[0.03] align-top ${open?.message_id === m.message_id ? "bg-[var(--acc)]/10" : ""}`}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">{m.status === "unread" && <span className="w-1.5 h-1.5 rounded-full bg-[var(--acc)] pulse-dot shrink-0" />}<span className={m.status === "unread" ? "font-semibold" : ""}>{m.from_name || "Website visitor"}</span>{m.hot && <Flame size={13} className="text-orange-400 shrink-0" />}</div>
                      <div className="text-xs text-[var(--mut)] mt-1 flex items-start gap-1.5"><AttachmentPill count={attachmentCount(m.body)} /><span className="break-words">{m.subject || m.body?.slice(0, 140)}</span></div>
                      <div className="text-[10px] font-mono mt-1.5" style={{ color: m.app_color || "var(--dim)" }}>{m.app_name}{m.app_archived ? " · archived" : ""}</div>
                    </td>
                    <td className="px-4 py-3 text-[var(--mut)] text-xs break-all">{m.from_email || "—"}</td>
                    <td className="px-4 py-3"><span className="inline-flex items-center gap-1.5 text-xs text-[var(--mut)]"><s.Icon size={12} className="shrink-0" /> <span className="break-words">{m.form_label || s.label}</span></span></td>
                    <td className="px-4 py-3 text-xs text-[var(--mut)]">{new Date(m.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</td>
                    <td className="px-4 py-3"><div className="flex flex-wrap items-center gap-1.5"><span data-testid={`lead-status-${m.message_id}`} className={`chip whitespace-nowrap ${m.status === "unread" ? "chip-active" : ""}`}>{m.status === "unread" ? "New" : m.replies?.length ? "Replied" : m.status === "read" ? "Reviewed" : "Archived"}</span>{m.score != null && <span data-testid={`lead-score-${m.message_id}`} className="text-[10px] font-mono text-[var(--dim)] whitespace-nowrap">{m.score}/100</span>}</div></td>
                    <td className="px-2 py-3 text-right whitespace-nowrap">
                      <button data-testid={`lead-lane-${m.message_id}`} title={m.lane === "test" ? "Move to Real Leads" : "Move to Test Leads"}
                        onClick={e => { e.stopPropagation(); setLane(m, m.lane === "test" ? "real" : "test"); }}
                        className="p-1.5 rounded-md hover:bg-white/10 text-[var(--dim)] hover:text-[var(--acc)]"><ArrowLeftRight size={13} /></button>
                      <button data-testid={`lead-star-${m.message_id}`} onClick={e => { e.stopPropagation(); patch(m, { starred: !m.starred }); }} className={`p-1.5 rounded-md hover:bg-white/10 ${m.starred ? "text-amber-400" : "text-[var(--dim)]"}`}><Star size={13} fill={m.starred ? "currentColor" : "none"} /></button>
                    </td>
                  </tr>); })}
              </tbody>
            </table>
            </div>
          )}
        </div>

        <aside className="card-surface p-5 h-fit sticky top-6 min-w-0" data-testid="lead-detail">
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
                <dt className="text-[var(--dim)]">Lane</dt><dd data-testid="lead-detail-lane">{open.lane === "test" ? "Test lead" : "Real lead"}{open.lane_manual ? " · manual" : ""}</dd>
                {open.score != null && <><dt className="text-[var(--dim)]">AI score</dt><dd>{open.score}/100 · {open.intent}</dd></>}
              </dl>
              {open.score_reason && <div className="text-xs text-[var(--mut)] bg-white/5 rounded-lg p-3">{open.score_reason}</div>}
              <div className="text-sm whitespace-pre-wrap leading-relaxed max-h-[36vh] overflow-y-auto scrollbar-thin border-t border-[var(--line)] pt-3">{open.body}</div>
              <Attachments body={open.body} testid="lead-detail-attachments" />
              <div className="flex flex-wrap gap-2 pt-1">
                <button data-testid="lead-detail-lane-btn" onClick={() => setLane(open, open.lane === "test" ? "real" : "test")}
                  className="btn-ghost text-xs !py-1.5 !px-3 flex items-center gap-1"><ArrowLeftRight size={12} /> Move to {open.lane === "test" ? "Real" : "Test"}</button>
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
