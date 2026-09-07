import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Inbox, Star, Archive, Trash2, Reply, MessageSquare, Mail, Loader2, CheckCheck, RotateCcw, Flame } from "lucide-react";
import { Attachments, AttachmentPill, attachmentCount } from "@/components/Attachments";

const FILTERS = [["all", "Inbox"], ["hot", "Hot leads"], ["unread", "Unread"], ["starred", "Starred"], ["archived", "Archived"]];
const ScoreBadge = ({ m }) => m.score == null ? <span className="chip" style={{ padding: "1px 6px" }} title="Scoring…">…</span>
  : <span data-testid="lead-score" title={m.score_reason || ""} className={`chip ${m.hot ? "chip-active badge-glow" : m.score >= 40 ? "chip-maint" : ""}`} style={{ padding: "1px 6px" }}>{m.hot ? "🔥 " : ""}{m.score}</span>;

export default function InboxPanel({ appId }) {
  const [msgs, setMsgs] = useState([]);
  const [unread, setUnread] = useState(0);
  const [hot, setHot] = useState(0);
  const [scoring, setScoring] = useState(false);
  async function scoreAll() { setScoring(true); try { const { data } = await api.post(`/apps/${appId}/inbox/score`, {}, { timeout: 180000 }); toast.success(`Scored ${data.scored} leads`); load(); } catch { toast.error("Scoring failed"); } finally { setScoring(false); } }
  const [filter, setFilter] = useState("all");
  const [sel, setSel] = useState(null);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { load(); }, [appId]);
  async function load() { try { const { data } = await api.get(`/apps/${appId}/inbox`); setMsgs(data.messages); setUnread(data.unread); setHot(data.hot || 0); } catch { toast.error("Failed to load inbox"); } }
  async function patch(m, body) { const { data } = await api.patch(`/apps/${appId}/inbox/${m.message_id}`, body); setMsgs(ms => { const next = ms.map(x => x.message_id === m.message_id ? data : x); setUnread(next.filter(x => x.status === "unread").length); return next; }); if (sel?.message_id === m.message_id) setSel(data); }
  function open(m) { setSel(m); setReply(""); if (m.status === "unread") patch(m, { status: "read" }); }
  async function del(m) { if (!confirm("Delete this message?")) return; await api.delete(`/apps/${appId}/inbox/${m.message_id}`); setMsgs(ms => ms.filter(x => x.message_id !== m.message_id)); if (sel?.message_id === m.message_id) setSel(null); }
  async function sendReply() {
    setBusy(true);
    try { const { data } = await api.post(`/apps/${appId}/inbox/${sel.message_id}/reply`, { body: reply }); setSel(data); setMsgs(ms => ms.map(x => x.message_id === data.message_id ? data : x)); setReply(""); toast.success(data.from_email ? "Reply saved · email delivery queued (connect an email provider to send)" : "Reply saved to conversation"); }
    catch { toast.error("Reply failed"); } finally { setBusy(false); }
  }
  const list = msgs.filter(m => filter === "all" ? m.status !== "archived" : filter === "hot" ? m.hot && m.status !== "archived" : filter === "unread" ? m.status === "unread" : filter === "starred" ? m.starred : m.status === "archived");
  const unscored = msgs.filter(m => m.score == null).length;

  return (
    <div data-testid="inbox-panel" className="grid lg:grid-cols-[200px_360px_1fr] gap-4 min-h-[560px]">
      <aside className="card-surface p-2 space-y-0.5">
        {FILTERS.map(([k, l]) => <button key={k} data-testid={`inbox-filter-${k}`} onClick={() => setFilter(k)} className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm ${filter === k ? "bg-[var(--acc)]/10 text-[var(--acc)]" : "text-[var(--mut)] hover:bg-white/5"}`}>
          <span className="flex items-center gap-2">{k === "all" ? <Inbox size={14} /> : k === "hot" ? <Flame size={14} /> : k === "starred" ? <Star size={14} /> : k === "archived" ? <Archive size={14} /> : <Mail size={14} />} {l}</span>
          {k === "unread" && unread > 0 && <span data-testid="inbox-unread-count" className="text-[10px] font-mono bg-[var(--acc)] text-black rounded-full px-1.5">{unread}</span>}
          {k === "hot" && hot > 0 && <span data-testid="inbox-hot-count" className="text-[10px] font-mono bg-[var(--acc)] text-black rounded-full px-1.5">{hot}</span>}
        </button>)}
        <button data-testid="inbox-score-btn" onClick={scoreAll} disabled={scoring || unscored === 0} className="mt-2 w-full btn-ghost text-xs !py-1.5 flex items-center justify-center gap-1 disabled:opacity-40">{scoring ? <Loader2 size={11} className="animate-spin" /> : <Flame size={11} />} {unscored ? `Score ${unscored} leads` : "All leads scored"}</button>
        <div className="px-3 pt-4 text-[10px] text-[var(--dim)] leading-relaxed">Leads are scored 0–100 by AI on intent, budget and urgency; hottest first.</div>
      </aside>

      <div className="card-surface divide-y divide-[var(--line)] overflow-y-auto max-h-[70vh] scrollbar-thin">
        {list.length === 0 && <div className="p-10 text-center text-sm text-[var(--mut)]">Nothing here yet.</div>}
        {list.map(m => (
          <div key={m.message_id} data-testid={`inbox-row-${m.source}`} onClick={() => open(m)} className={`px-4 py-3 cursor-pointer hover:bg-white/3 ${sel?.message_id === m.message_id ? "bg-[var(--acc)]/8" : ""}`}>
            <div className="flex items-center gap-2">
              {m.source === "chat" ? <MessageSquare size={13} className="text-[var(--cyan)]" /> : <Mail size={13} className="text-[var(--acc)]" />}
              <span className={`text-sm flex-1 truncate ${m.status === "unread" ? "font-bold text-white" : "text-[var(--mut)]"}`}>{m.from_name || m.from_email || "Visitor"}</span>
              <ScoreBadge m={m} />
              <span className="text-[10px] font-mono text-[var(--dim)]">{new Date(m.updated_at).toLocaleDateString()}</span>
              <button onClick={e => { e.stopPropagation(); patch(m, { starred: !m.starred }); }} className={m.starred ? "text-amber-400" : "text-[var(--dim)] hover:text-amber-400"}><Star size={12} fill={m.starred ? "currentColor" : "none"} /></button>
            </div>
            <div className={`text-xs mt-0.5 truncate ${m.status === "unread" ? "text-[var(--fg)]" : "text-[var(--mut)]"}`}>{m.subject}</div>
            <div className="text-[11px] text-[var(--dim)] mt-0.5 truncate flex items-center gap-1.5"><AttachmentPill count={attachmentCount(m.body)} /><span className="truncate">{m.body}</span></div>
          </div>
        ))}
      </div>

      <div className="card-surface p-6 flex flex-col">
        {!sel ? <div className="m-auto text-center text-sm text-[var(--mut)]"><Inbox size={28} className="mx-auto mb-3 text-[var(--dim)]" />Select a message to read and reply.</div> : (
          <>
            <div className="flex items-start justify-between gap-3">
              <div><div className="font-display text-xl font-semibold">{sel.subject}</div>
                <div className="text-xs text-[var(--mut)] mt-1 font-mono">{sel.from_name} {sel.from_email && `· ${sel.from_email}`} · via {sel.source} · {new Date(sel.created_at).toLocaleString()}</div>
                {sel.score != null && <div data-testid="lead-score-detail" className="mt-2 flex items-center gap-2 text-xs"><ScoreBadge m={sel} /><span className="text-[var(--mut)]">{sel.intent && <span className="font-mono uppercase text-[10px] mr-2">{sel.intent}</span>}{sel.score_reason}</span></div>}</div>
              <div className="flex gap-1">
                <button data-testid="inbox-mark-unread-btn" title="Mark unread" onClick={() => patch(sel, { status: "unread" })} className="w-8 h-8 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-white/5"><RotateCcw size={13} /></button>
                <button data-testid="inbox-archive-btn" title={sel.status === "archived" ? "Unarchive" : "Archive"} onClick={() => patch(sel, { status: sel.status === "archived" ? "read" : "archived" })} className="w-8 h-8 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-white/5">{sel.status === "archived" ? <CheckCheck size={13} /> : <Archive size={13} />}</button>
                <button data-testid="inbox-delete-btn" onClick={() => del(sel)} className="w-8 h-8 rounded-full border border-[var(--line)] flex items-center justify-center hover:text-red-400 hover:border-red-500/40"><Trash2 size={13} /></button>
              </div>
            </div>
            <div data-testid="inbox-message-body" className="mt-5 text-sm whitespace-pre-wrap leading-relaxed bg-[var(--bg-2)] border border-[var(--line)] rounded-xl p-4 max-h-[36vh] overflow-y-auto scrollbar-thin">{sel.body}</div>
            <Attachments body={sel.body} testid="inbox-attachments" />
            {sel.replies?.length > 0 && <div className="mt-4 space-y-2">{sel.replies.map(r => <div key={r.reply_id} className="text-sm border-l-2 border-[var(--acc)] pl-3"><div className="text-[10px] font-mono text-[var(--dim)]">{r.by} · {new Date(r.created_at).toLocaleString()} · {r.delivery.replace("_", " ")}</div><div className="mt-1 whitespace-pre-wrap">{r.body}</div></div>)}</div>}
            <div className="mt-auto pt-4">
              <textarea data-testid="inbox-reply-input" value={reply} onChange={e => setReply(e.target.value)} rows={3} placeholder={`Reply to ${sel.from_name || "visitor"}…`} className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-4 py-3 text-sm outline-none focus:border-[var(--acc)] resize-none" />
              <div className="flex justify-end mt-2"><button data-testid="inbox-reply-btn" onClick={sendReply} disabled={busy || !reply.trim()} className="btn-primary text-sm !py-2 !px-4 flex items-center gap-2 disabled:opacity-50">{busy ? <Loader2 size={13} className="animate-spin" /> : <Reply size={13} />} Send reply</button></div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
