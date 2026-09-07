import { useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Sparkles, Send, Loader2, Reply, ChevronDown, CheckCheck, Mail, Paperclip, X } from "lucide-react";
import api from "@/lib/api";
import { Attachments } from "@/components/Attachments";

export function LeadReply({ lead, onUpdated }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [sending, setSending] = useState(false);
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);
  const replies = lead.replies || [];

  async function draft() {
    setDrafting(true);
    try { const { data } = await api.post(`/apps/${lead.app_id}/inbox/${lead.message_id}/ai-draft`); setText(data.draft); setOpen(true); }
    catch (e) { toast.error(e.response?.data?.detail || "AI draft failed"); } finally { setDrafting(false); }
  }

  async function pick(e) {
    const list = Array.from(e.target.files || []);
    e.target.value = "";
    if (!list.length) return;
    setUploading(true);
    try {
      for (const f of list) {
        const fd = new FormData(); fd.append("file", f);
        const { data } = await api.post(`/apps/${lead.app_id}/attachments`, fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 180000 });
        setFiles(fs => [...fs, data]);
      }
    } catch (err) { toast.error(err.response?.data?.detail || "Upload failed"); }
    finally { setUploading(false); }
  }

  async function send() {
    if (!text.trim() && files.length === 0) return;
    setSending(true);
    try {
      const { data } = await api.post(`/apps/${lead.app_id}/inbox/${lead.message_id}/reply`,
        { body: text, attachments: files.map(f => ({ name: f.name, url: f.url })) });
      onUpdated(data); setText(""); setFiles([]); setOpen(false);
      toast.success(data.replies?.at(-1)?.delivery === "email_sent" ? "Reply emailed to lead" : "Reply saved");
    } catch (e) { toast.error(e.response?.data?.detail || "Send failed"); } finally { setSending(false); }
  }

  return (
    <div className="border-t border-[var(--line)] pt-3 space-y-3" data-testid="lead-reply">
      {replies.length > 0 && (
        <div className="space-y-2" data-testid="lead-reply-history">
          <div className="text-[10px] uppercase tracking-wider text-[var(--dim)] flex items-center gap-1"><CheckCheck size={11} className="text-[var(--acc)]" /> {replies.length} repl{replies.length === 1 ? "y" : "ies"} sent</div>
          {replies.map(r => (
            <div key={r.reply_id} className="text-xs border-l-2 border-[var(--acc)] pl-3 py-1">
              <div className="whitespace-pre-wrap text-[var(--fg)]/90">{r.body}</div>
              {r.attachments?.length > 0 && <Attachments testid="reply-attachments" body={r.attachments.map(a => `[attachment] ${a.name} — ${a.url}`).join("\n")} />}
              <div className="text-[10px] font-mono text-[var(--dim)] mt-1">{r.by} · {new Date(r.created_at).toLocaleString()} · <span className={r.delivery === "email_sent" ? "text-[var(--acc)]" : ""}>{r.delivery?.replace("_", " ")}</span></div>
            </div>
          ))}
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
            {files.length > 0 && (
              <div data-testid="reply-attachment-list" className="flex flex-wrap gap-2 mt-2">
                {files.map(f => (
                  <span key={f.url} className="chip flex items-center gap-1.5" style={{ padding: "3px 8px" }}>
                    <Paperclip size={10} /> <span className="truncate max-w-[160px]">{f.name}</span>
                    <button data-testid={`reply-attachment-remove-${f.name}`} onClick={() => setFiles(fs => fs.filter(x => x.url !== f.url))} className="opacity-60 hover:opacity-100"><X size={10} /></button>
                  </span>
                ))}
              </div>
            )}
            <div className="flex items-center justify-between gap-2 mt-2 text-[11px] text-[var(--mut)]">
              <span className="flex items-center gap-1"><Mail size={11} /> {lead.from_email ? `Will email ${lead.from_email}` : "No email on lead — saved to thread only"}</span>
              <div className="flex items-center gap-2">
                <input ref={fileRef} data-testid="reply-file-input" type="file" multiple onChange={pick} className="hidden"
                  accept=".png,.jpg,.jpeg,.webp,.gif,.svg,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.zip" />
                <button data-testid="reply-attach-btn" title="Attach quotes, mockups or docs" onClick={() => fileRef.current?.click()} disabled={uploading}
                  className="btn-ghost text-xs !py-1.5 !px-3 flex items-center gap-1 disabled:opacity-50">{uploading ? <Loader2 size={12} className="animate-spin" /> : <Paperclip size={12} />} Attach</button>
                <button data-testid="lead-reply-send-btn" onClick={send} disabled={sending || (!text.trim() && files.length === 0)} className="btn-primary text-xs !py-1.5 !px-4 flex items-center gap-1 disabled:opacity-50">{sending ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />} Send reply</button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
