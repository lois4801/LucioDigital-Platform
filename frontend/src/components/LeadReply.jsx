import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Sparkles, Send, Loader2, Reply, ChevronDown, CheckCheck, Mail } from "lucide-react";
import api from "@/lib/api";

export function LeadReply({ lead, onUpdated }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [sending, setSending] = useState(false);
  const replies = lead.replies || [];

  async function draft() {
    setDrafting(true);
    try { const { data } = await api.post(`/apps/${lead.app_id}/inbox/${lead.message_id}/ai-draft`); setText(data.draft); setOpen(true); }
    catch (e) { toast.error(e.response?.data?.detail || "AI draft failed"); } finally { setDrafting(false); }
  }
  async function send() {
    if (!text.trim()) return;
    setSending(true);
    try { const { data } = await api.post(`/apps/${lead.app_id}/inbox/${lead.message_id}/reply`, { body: text }); onUpdated(data); setText(""); setOpen(false); toast.success(data.replies?.at(-1)?.delivery === "email_sent" ? "Reply emailed to lead" : "Reply saved"); }
    catch (e) { toast.error(e.response?.data?.detail || "Send failed"); } finally { setSending(false); }
  }

  return (
    <div className="border-t border-[var(--line)] pt-3 space-y-3" data-testid="lead-reply">
      {replies.length > 0 && (
        <div className="space-y-2" data-testid="lead-reply-history">
          <div className="text-[10px] uppercase tracking-wider text-[var(--dim)] flex items-center gap-1"><CheckCheck size={11} className="text-[var(--acc)]" /> {replies.length} repl{replies.length === 1 ? "y" : "ies"} sent</div>
          {replies.map(r => <div key={r.reply_id} className="text-xs border-l-2 border-[var(--acc)] pl-3 py-1"><div className="whitespace-pre-wrap text-[var(--fg)]/90">{r.body}</div><div className="text-[10px] font-mono text-[var(--dim)] mt-1">{r.by} · {new Date(r.created_at).toLocaleString()} · <span className={r.delivery === "email_sent" ? "text-[var(--acc)]" : ""}>{r.delivery?.replace("_", " ")}</span></div></div>)}
        </div>
      )}
      <div className="flex gap-2">
        <button data-testid="lead-reply-toggle" onClick={() => setOpen(o => !o)} className="btn-ghost text-xs !py-1.5 !px-3 flex items-center gap-1"><Reply size={12} /> {open ? "Hide" : "Reply"} <ChevronDown size={11} className={`transition-transform ${open ? "rotate-180" : ""}`} /></button>
        <button data-testid="lead-ai-draft-btn" onClick={draft} disabled={drafting} className="btn-primary text-xs !py-1.5 !px-3 flex items-center gap-1">{drafting ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />} AI draft reply</button>
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div key="composer" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }} className="overflow-hidden">
            <textarea data-testid="lead-reply-input" value={text} onChange={e => setText(e.target.value)} rows={6} placeholder={`Reply to ${lead.from_name || "this lead"}…`} className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)] resize-y" />
            <div className="flex items-center justify-between mt-2 text-[11px] text-[var(--mut)]">
              <span className="flex items-center gap-1"><Mail size={11} /> {lead.from_email ? `Will email ${lead.from_email}` : "No email on lead — saved to thread only"}</span>
              <button data-testid="lead-reply-send-btn" onClick={send} disabled={sending || !text.trim()} className="btn-primary text-xs !py-1.5 !px-4 flex items-center gap-1 disabled:opacity-50">{sending ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />} Send reply</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
