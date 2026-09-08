import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Inbox, Star, Archive, Trash2, MessageSquare, Mail, Loader2, CheckCheck, RotateCcw, Flame, Clock, Send, FlaskConical, ArrowLeftRight, CalendarPlus } from "lucide-react";
import { Attachments, AttachmentPill, attachmentCount } from "@/components/Attachments";
import { LeadReply } from "@/components/LeadReply";
import LeadSummaryCard from "@/components/LeadSummaryCard";

const TABS = [["real", "Real Leads"], ["test", "Test Leads"], ["archived", "Archived"]];
const CHIPS = [["all", "All"], ["hot", "Hot"], ["unread", "Unread"], ["starred", "Starred"]];
const ScoreBadge = ({ m }) => m.score == null ? <span className="chip" style={{ padding: "1px 6px" }} title="Scoring…">…</span>
  : <span data-testid="lead-score" title={m.score_reason || ""} className={`chip ${m.hot ? "chip-active badge-glow" : m.score >= 40 ? "chip-maint" : ""}`} style={{ padding: "1px 6px" }}>{m.hot ? "🔥 " : ""}{m.score}</span>;

export default function InboxPanel({ appId }) {
  const [msgs, setMsgs] = useState([]);
  const [unread, setUnread] = useState(0);
  const [hot, setHot] = useState(0);
  const [scoring, setScoring] = useState(false);
  async function scoreAll() { setScoring(true); try { const { data } = await api.post(`/apps/${appId}/inbox/score`, {}, { timeout: 180000 }); toast.success(`Scored ${data.scored} leads`); load(); } catch { toast.error("Scoring failed"); } finally { setScoring(false); } }
  const [tab, setTab] = useState("real");
  const [filter, setFilter] = useState("all");
  const [counts, setCounts] = useState({ real: 0, test: 0, archived: 0, review: 0, priority: 0 });
  const [laneBusy, setLaneBusy] = useState(false);
  const [sel, setSel] = useState(null);
  const [fu, setFu] = useState({ enabled: false, hours: 48, pending_drafts: 0 });
  const [fuBusy, setFuBusy] = useState(false);
  const [fuEdit, setFuEdit] = useState("");
  const [decisionReply, setDecisionReply] = useState("");
  useEffect(() => { api.get(`/apps/${appId}/inbox/followups`).then(r => setFu(r.data)).catch(() => {}); }, [appId]);
  useEffect(() => { setFuEdit(sel?.followup?.body || ""); }, [sel?.message_id, sel?.followup?.drafted_at]);
  function absorb(m) { setSel(m); setMsgs(ms => ms.map(x => x.message_id === m.message_id ? m : x)); }
  async function decideRequest(action) {
    setFuBusy(true);
    try {
      const { data } = await api.post(`/apps/${appId}/inbox/${sel.message_id}/edit-request/${action}`, { reply: decisionReply || undefined });
      absorb(data); setDecisionReply("");
      toast.success(action === "approve" ? "Approved — the page is unlocked for their change" : "Request rejected");
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } finally { setFuBusy(false); }
  }
  async function toggleFu(enabled) {
    setFu(f => ({ ...f, enabled }));
    try { await api.post(`/apps/${appId}/inbox/followups`, { enabled }); toast.success(enabled ? `Auto follow-ups on — drafts appear here after ${fu.hours}h of silence` : "Auto follow-ups off"); }
    catch { setFu(f => ({ ...f, enabled: !enabled })); toast.error("Failed"); }
  }
  async function fuAction(kind) {
    setFuBusy(true);
    try {
      const url = `/apps/${appId}/inbox/${sel.message_id}/followup-${kind}`;
      const { data } = await api.post(url, kind === "approve" ? { body: fuEdit } : {}, { timeout: 180000 });
      absorb(data);
      toast.success(kind === "draft" ? "Follow-up drafted" : kind === "approve" ? "Follow-up sent" : "Follow-up dismissed");
      api.get(`/apps/${appId}/inbox/followups`).then(r => setFu(r.data)).catch(() => {});
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } finally { setFuBusy(false); }
  }

  useEffect(() => { load(); }, [appId]);
  async function load() { try { const { data } = await api.get(`/apps/${appId}/inbox`); setMsgs(data.messages); setUnread(data.unread); setHot(data.hot || 0); setCounts(data.counts || counts); } catch { toast.error("Failed to load inbox"); } }
  async function setLane(m, lane) {
    setLaneBusy(true);
    try {
      const { data } = await api.patch(`/apps/${appId}/inbox/${m.message_id}/lane`, { lane });
      setMsgs(ms => ms.map(x => x.message_id === data.message_id ? data : x));
      if (sel?.message_id === data.message_id) setSel(data);
      toast.success(lane === "test" ? "Moved to Test Leads" : "Moved to Real Leads");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not move that lead"); }
    finally { setLaneBusy(false); }
  }
  async function bookingInvite(m) {
    setLaneBusy(true);
    try {
      const { data } = await api.post(`/apps/${appId}/inbox/${m.message_id}/booking-invite`);
      absorb(data.message);
      toast.success(`Booking invite sent to ${data.invite.to}${data.invite.copies?.length ? ` (copied to ${data.invite.copies.join(", ")})` : ""}`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not send the invite"); }
    finally { setLaneBusy(false); }
  }
  async function patch(m, body) { const { data } = await api.patch(`/apps/${appId}/inbox/${m.message_id}`, body); setMsgs(ms => { const next = ms.map(x => x.message_id === m.message_id ? data : x); setUnread(next.filter(x => x.status === "unread").length); return next; }); if (sel?.message_id === m.message_id) setSel(data); }
  function open(m) { setSel(m); if (m.status === "unread") patch(m, { status: "read" }); }
  async function del(m) { if (!confirm("Delete this message?")) return; await api.delete(`/apps/${appId}/inbox/${m.message_id}`); setMsgs(ms => ms.filter(x => x.message_id !== m.message_id)); if (sel?.message_id === m.message_id) setSel(null); }
  const inTab = msgs.filter(m => tab === "archived" ? m.status === "archived"
    : m.status !== "archived" && (m.lane || "real") === tab);
  const chipped = inTab.filter(m => filter === "all" ? true : filter === "hot" ? m.hot : filter === "unread" ? m.status === "unread" : m.starred);
  const priority = tab === "real" ? chipped.filter(m => (m.score ?? 0) > 60) : [];
  const review = tab === "real" ? chipped.filter(m => (m.score != null && m.score < 30) || m.review) : [];
  const reviewIds = new Set(review.map(m => m.message_id));
  const normal = chipped.filter(m => !reviewIds.has(m.message_id) && !(tab === "real" && (m.score ?? 0) > 60));
  const unscored = msgs.filter(m => m.score == null).length;

  const Row = ({ m }) => (
    <div key={m.message_id} data-testid={`inbox-row-${m.source}`} onClick={() => open(m)} className={`px-4 py-3 cursor-pointer hover:bg-white/3 ${sel?.message_id === m.message_id ? "bg-[var(--acc)]/8" : ""}`}>
      <div className="flex items-center gap-2">
        {m.source === "chat" ? <MessageSquare size={13} className="text-[var(--cyan)]" /> : <Mail size={13} className="text-[var(--acc)]" />}
        <span className={`text-sm flex-1 truncate ${m.status === "unread" ? "font-bold text-white" : "text-[var(--mut)]"}`}>{m.from_name || m.from_email || "Visitor"}</span>
        {(m.score ?? 0) > 60 && <Flame size={12} className="text-[var(--acc)]" data-testid="lead-priority-flame" />}
        <ScoreBadge m={m} />
        {m.lane === "test" && <span data-testid="lead-test-badge" className="chip text-[9px]" style={{ padding: "1px 5px" }} title={(m.lane_reasons || []).join(" · ")}>TEST</span>}
        {m.edit_request?.state === "pending" && <span data-testid="edit-request-badge" className="chip chip-active text-[9px]" style={{ padding: "1px 5px" }} title="Edit request">EDIT</span>}
        {m.followup?.status === "draft" && <span data-testid="followup-badge-draft" className="chip chip-active text-[9px]" style={{ padding: "1px 5px" }} title="Follow-up draft ready"><Clock size={9} /></span>}
        {m.followup?.status === "sent" && <span data-testid="followup-badge-sent" className="chip text-[9px]" style={{ padding: "1px 5px" }} title="Follow-up sent"><Send size={9} /></span>}
        <span className="text-[10px] font-mono text-[var(--dim)]">{new Date(m.updated_at).toLocaleDateString()}</span>
        <button data-testid={`lead-move-${m.lane === "test" ? "real" : "test"}-row`} title={m.lane === "test" ? "Move to Real Leads" : "Move to Test Leads"}
          onClick={e => { e.stopPropagation(); setLane(m, m.lane === "test" ? "real" : "test"); }}
          className="text-[var(--dim)] hover:text-[var(--acc)]"><ArrowLeftRight size={12} /></button>
        <button onClick={e => { e.stopPropagation(); patch(m, { starred: !m.starred }); }} className={m.starred ? "text-amber-400" : "text-[var(--dim)] hover:text-amber-400"}><Star size={12} fill={m.starred ? "currentColor" : "none"} /></button>
      </div>
      <div className={`text-xs mt-0.5 truncate ${m.status === "unread" ? "text-[var(--fg)]" : "text-[var(--mut)]"}`}>{m.subject}</div>
      <div className="text-[11px] text-[var(--dim)] mt-0.5 truncate flex items-center gap-1.5"><AttachmentPill count={attachmentCount(m.body)} /><span className="truncate">{m.body}</span></div>
    </div>
  );

  return (
    <div data-testid="inbox-panel" className="space-y-4">
    <LeadSummaryCard appId={appId} />
    <div data-testid="inbox-tabs" className="card-surface p-2 flex flex-wrap items-center gap-2">
      {TABS.map(([k, label]) => (
        <button key={k} data-testid={`inbox-tab-${k}`} onClick={() => { setTab(k); setSel(null); }}
          className={`px-4 py-2 rounded-full text-sm flex items-center gap-2 transition-colors ${tab === k ? "bg-[var(--acc)] text-black font-semibold" : "text-[var(--mut)] hover:bg-white/5"}`}>
          {k === "real" ? <Inbox size={13} /> : k === "test" ? <FlaskConical size={13} /> : <Archive size={13} />}
          {label}
          <span className={`text-[10px] font-mono ${tab === k ? "opacity-70" : "opacity-60"}`}>{counts[k] ?? 0}</span>
        </button>
      ))}
      <div className="flex-1" />
      {CHIPS.map(([k, label]) => (
        <button key={k} data-testid={`inbox-filter-${k}`} onClick={() => setFilter(k)}
          className={`chip cursor-pointer ${filter === k ? "chip-active" : ""}`}>{label}{k === "unread" && unread > 0 ? ` ${unread}` : ""}{k === "hot" && hot > 0 ? ` ${hot}` : ""}</button>
      ))}
    </div>
    <div className="grid lg:grid-cols-[200px_360px_1fr] gap-4 min-h-[560px]">
      <aside className="card-surface p-2 space-y-0.5">
        <div className="px-3 py-2 text-[11px] text-[var(--mut)] leading-relaxed">
          Leads are auto-sorted: anything that looks like a QA, demo or disposable-email submission lands in
          <strong className="text-[var(--fg)]"> Test Leads</strong>. Everything else is a real person.
        </div>
        <div className="px-3 pb-2 space-y-1 text-[10px] font-mono text-[var(--dim)]">
          <div data-testid="inbox-count-priority">{counts.priority || 0} priority (score &gt; 60)</div>
          <div data-testid="inbox-count-review">{counts.review || 0} in review (score &lt; 30)</div>
          <div>{counts.test || 0} test · {counts.archived || 0} archived</div>
        </div>
        <button data-testid="inbox-score-btn" onClick={scoreAll} disabled={scoring || unscored === 0} className="mt-2 w-full btn-ghost text-xs !py-1.5 flex items-center justify-center gap-1 disabled:opacity-40">{scoring ? <Loader2 size={11} className="animate-spin" /> : <Flame size={11} />} {unscored ? `Score ${unscored} leads` : "All leads scored"}</button>
        <button data-testid="inbox-reclassify-btn" onClick={async () => { try { const { data } = await api.post(`/apps/${appId}/inbox/classify?rerun=true`); toast.success(`Re-sorted: ${data.real} real · ${data.test} test`); load(); } catch { toast.error("Could not re-sort"); } }}
          className="mt-1 w-full btn-ghost text-xs !py-1.5">Re-sort real vs test</button>
        <div className="px-3 pt-4 text-[10px] text-[var(--dim)] leading-relaxed">Leads are scored 0–100 by AI on intent, budget and urgency; hottest first.</div>
        <div className="mt-3 border-t border-[var(--line)] pt-3 px-3">
          <label className="flex items-start gap-2 text-[11px] cursor-pointer">
            <input data-testid="followups-toggle" type="checkbox" checked={fu.enabled} onChange={e => toggleFu(e.target.checked)} className="mt-0.5 accent-[var(--acc)]" />
            <span className="text-[var(--mut)]">Auto follow-up after {fu.hours}h of silence — AI writes it, you approve before it sends</span>
          </label>
          {fu.pending_drafts > 0 && <div data-testid="followups-pending" className="mt-2 chip chip-active text-[10px]">{fu.pending_drafts} follow-up draft{fu.pending_drafts > 1 ? "s" : ""} waiting</div>}
        </div>
      </aside>

      <div className="card-surface divide-y divide-[var(--line)] overflow-y-auto max-h-[70vh] scrollbar-thin">
        {chipped.length === 0 && <div className="p-10 text-center text-sm text-[var(--mut)]">Nothing here yet.</div>}
        {priority.length > 0 && (
          <div data-testid="inbox-section-priority" className="px-4 py-2 text-[10px] font-mono uppercase tracking-wider text-[var(--acc)] flex items-center gap-1.5 bg-[var(--acc)]/5"><Flame size={11} /> priority · score above 60</div>
        )}
        {priority.map(m => <Row key={m.message_id} m={m} />)}
        {normal.map(m => <Row key={m.message_id} m={m} />)}
        {review.length > 0 && (
          <div data-testid="inbox-section-review" className="px-4 py-2 text-[10px] font-mono uppercase tracking-wider text-amber-300 bg-amber-500/5">review · score under 30, may be suspicious</div>
        )}
        {review.map(m => <Row key={m.message_id} m={m} />)}
      </div>

      <div className="card-surface p-6 flex flex-col">
        {!sel ? <div className="m-auto text-center text-sm text-[var(--mut)]"><Inbox size={28} className="mx-auto mb-3 text-[var(--dim)]" />Select a message to read and reply.</div> : (
          <>
            <div className="flex items-start justify-between gap-3">
              <div><div className="font-display text-xl font-semibold">{sel.subject}</div>
                <div className="text-xs text-[var(--mut)] mt-1 font-mono">{sel.from_name} {sel.from_email && `· ${sel.from_email}`} · via {sel.source} · {new Date(sel.created_at).toLocaleString()}</div>
                {sel.score != null && <div data-testid="lead-score-detail" className="mt-2 flex items-center gap-2 text-xs"><ScoreBadge m={sel} /><span className="text-[var(--mut)]">{sel.intent && <span className="font-mono uppercase text-[10px] mr-2">{sel.intent}</span>}{sel.score_reason}</span></div>}
                <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px]">
                  <span data-testid="lead-lane-badge" className={`chip ${sel.lane === "test" ? "chip-maint" : "chip-active"}`}>{sel.lane === "test" ? "Test lead" : "Real lead"}{sel.lane_manual ? " · manual" : ""}</span>
                  {(sel.lane_reasons || []).map((r, i) => <span key={i} className="text-[var(--dim)]">{r}</span>)}
                  {sel.lane !== "test" && (sel.review_reasons || []).map((r, i) => <span key={`v${i}`} className="text-amber-300/80">{r}</span>)}
                  {sel.booking_invite && <span data-testid="lead-invite-sent" className="chip">invite sent {new Date(sel.booking_invite.sent_at).toLocaleDateString()}</span>}
                </div></div>
              <div className="flex gap-1">
                <button data-testid="lead-move-lane-btn" title={sel.lane === "test" ? "Move to Real Leads" : "Move to Test Leads"} disabled={laneBusy}
                  onClick={() => setLane(sel, sel.lane === "test" ? "real" : "test")}
                  className="h-8 px-3 rounded-full border border-[var(--line)] flex items-center gap-1.5 text-[11px] hover:bg-white/5 disabled:opacity-50">
                  <ArrowLeftRight size={12} /> {sel.lane === "test" ? "Real" : "Test"}
                </button>
                {sel.lane !== "test" && sel.from_email && (
                  <button data-testid="lead-booking-invite-btn" title="Email this lead a booking invite" disabled={laneBusy}
                    onClick={() => bookingInvite(sel)}
                    className="h-8 px-3 rounded-full border border-[var(--acc)]/40 text-[var(--acc)] flex items-center gap-1.5 text-[11px] hover:bg-[var(--acc)]/10 disabled:opacity-50">
                    <CalendarPlus size={12} /> {sel.booking_invite ? "Invite again" : "Booking invite"}
                  </button>
                )}
                <button data-testid="inbox-mark-unread-btn" title="Mark unread" onClick={() => patch(sel, { status: "unread" })} className="w-8 h-8 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-white/5"><RotateCcw size={13} /></button>
                <button data-testid="inbox-archive-btn" title={sel.status === "archived" ? "Unarchive" : "Archive"} onClick={() => patch(sel, { status: sel.status === "archived" ? "read" : "archived" })} className="w-8 h-8 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-white/5">{sel.status === "archived" ? <CheckCheck size={13} /> : <Archive size={13} />}</button>
                <button data-testid="inbox-delete-btn" onClick={() => del(sel)} className="w-8 h-8 rounded-full border border-[var(--line)] flex items-center justify-center hover:text-red-400 hover:border-red-500/40"><Trash2 size={13} /></button>
              </div>
            </div>
            <div data-testid="inbox-message-body" className="mt-5 text-sm whitespace-pre-wrap leading-relaxed bg-[var(--bg-2)] border border-[var(--line)] rounded-xl p-4 max-h-[36vh] overflow-y-auto scrollbar-thin">{sel.body}</div>
            <Attachments body={sel.body} testid="inbox-attachments" />
            {sel.replies?.length > 0 && <div className="mt-4 space-y-2">{sel.replies.map(r => <div key={r.reply_id} className="text-sm border-l-2 border-[var(--acc)] pl-3"><div className="text-[10px] font-mono text-[var(--dim)]">{r.by} · {new Date(r.created_at).toLocaleString()} · {r.delivery.replace("_", " ")}</div><div className="mt-1 whitespace-pre-wrap">{r.body}</div>{r.attachments?.length > 0 && <Attachments testid="inbox-reply-attachments" body={r.attachments.map(a => `[attachment] ${a.name} — ${a.url}`).join("\n")} />}</div>)}</div>}
            <div className="mt-auto pt-4">
              {sel.edit_request && (
                <div data-testid="edit-request-card" className="mb-3 rounded-xl border border-[var(--acc)]/40 bg-[var(--acc)]/5 p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="overline">Edit request · {sel.edit_request.page_name}</span>
                    <span data-testid="edit-request-state" className={`chip text-[10px] ml-auto ${sel.edit_request.state === "pending" ? "chip-active" : ""}`}>{sel.edit_request.state}</span>
                  </div>
                  {sel.edit_request.state === "pending" ? (                    <div className="flex gap-2">
                      <button data-testid="edit-request-approve-btn" onClick={() => decideRequest("approve")} disabled={fuBusy} className="btn-primary text-xs !py-2 flex items-center gap-1.5 disabled:opacity-50">{fuBusy ? <Loader2 size={12} className="animate-spin" /> : <CheckCheck size={12} />} Approve & unlock</button>
                      <button data-testid="edit-request-reject-btn" onClick={() => decideRequest("reject")} disabled={fuBusy} className="btn-ghost text-xs !py-2">Reject</button>
                      <input data-testid="edit-request-reply-input" value={decisionReply} onChange={e => setDecisionReply(e.target.value)} placeholder="Optional reply to the client"
                        className="flex-1 min-w-[160px] bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2 py-2 text-xs outline-none" />
                    </div>
                  ) : <div className="text-xs text-[var(--mut)]">{sel.edit_request.state} by {sel.edit_request.decided_by} · {sel.edit_request.decided_at ? new Date(sel.edit_request.decided_at).toLocaleString() : ""}</div>}
                </div>
              )}
              {sel.from_email && (sel.followup?.status === "draft" ? (
                <div data-testid="followup-draft-card" className="mb-3 rounded-xl border border-[var(--acc)]/40 bg-[var(--acc)]/5 p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Clock size={12} className="text-[var(--acc)]" />
                    <span className="overline">Follow-up draft · {sel.followup.kind === "no_reply" ? "never replied" : "went quiet"}</span>
                    <span className="ml-auto font-mono text-[10px] text-[var(--dim)]">{new Date(sel.followup.drafted_at).toLocaleString()}</span>
                  </div>
                  <textarea data-testid="followup-draft-body" value={fuEdit} onChange={e => setFuEdit(e.target.value)} rows={5}
                    className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg p-3 text-sm outline-none focus:border-[var(--acc)]" />
                  <div className="flex gap-2 mt-2">
                    <button data-testid="followup-approve-btn" onClick={() => fuAction("approve")} disabled={fuBusy} className="btn-primary text-xs !py-2 flex items-center gap-1.5 disabled:opacity-50">{fuBusy ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />} Approve & send</button>
                    <button data-testid="followup-regenerate-btn" onClick={() => fuAction("draft")} disabled={fuBusy} className="btn-ghost text-xs !py-2">Rewrite</button>
                    <button data-testid="followup-dismiss-btn" onClick={() => fuAction("dismiss")} disabled={fuBusy} className="btn-ghost text-xs !py-2 ml-auto">Dismiss</button>
                  </div>
                </div>
              ) : (
                <button data-testid="followup-generate-btn" onClick={() => fuAction("draft")} disabled={fuBusy} className="btn-ghost text-xs !py-2 mb-3 flex items-center gap-1.5 disabled:opacity-50">
                  {fuBusy ? <Loader2 size={12} className="animate-spin" /> : <Clock size={12} />}
                  {sel.followup?.status === "sent" ? "Draft another follow-up" : "Draft a follow-up now"}
                </button>
              ))}
              <LeadReply lead={{ ...sel, app_id: appId }} onUpdated={(m) => { setSel(m); setMsgs(ms => ms.map(x => x.message_id === m.message_id ? m : x)); }} />
            </div>
          </>
        )}
      </div>
    </div>
    </div>
  );
}
