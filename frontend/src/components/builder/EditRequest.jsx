import { useState, useRef } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Loader2, MessageSquarePlus, Paperclip, Send, X } from "lucide-react";

export function EditRequestDialog({ appId, pageId, pageName, open, onOpenChange, onSent }) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const ref = useRef(null);

  async function attach(list) {
    for (const f of Array.from(list || [])) {
      const fd = new FormData(); fd.append("file", f);
      try { const { data } = await api.post(`/apps/${appId}/files`, fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 240000 }); setFiles(x => [...x, { name: data.original_filename, url: data.url }]); }
      catch (e) { toast.error(`${f.name}: ${e.response?.data?.detail || "upload failed"}`); }
    }
  }

  async function submit() {
    if (!text.trim()) return toast.error("Describe the change you'd like");
    setBusy(true);
    try {
      await api.post(`/apps/${appId}/pages/${pageId}/edit-request`, { description: text, attachments: files });
      toast.success("Sent to the agency — they'll approve or reply from their inbox");
      setText(""); setFiles([]); onOpenChange(false); onSent?.();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not send the request"); } finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)] max-w-lg">
        <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><MessageSquarePlus size={16} className="text-[var(--acc)]" /> Request a change — {pageName}</DialogTitle></DialogHeader>
        <p className="text-sm text-[var(--mut)]">This page is locked by the agency. Tell them what you'd like changed and they'll approve it or reply.</p>
        <textarea data-testid="edit-request-text" value={text} onChange={e => setText(e.target.value)} rows={5}
          placeholder="e.g. Please change the hero headline to 'Same-day repairs, guaranteed' and swap the photo for our new van."
          className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-3 text-sm outline-none focus:border-[var(--acc)]" />
        <div className="flex items-center gap-2 flex-wrap">
          <input ref={ref} data-testid="edit-request-file" type="file" multiple accept="image/*,.pdf,.docx,.txt" className="hidden" onChange={e => { attach(e.target.files); e.target.value = ""; }} />
          <button data-testid="edit-request-attach-btn" onClick={() => ref.current?.click()} className="btn-ghost text-xs !py-2 flex items-center gap-1.5"><Paperclip size={12} /> Attach a screenshot</button>
          {files.map(f => <span key={f.url} className="chip text-[10px] flex items-center gap-1">{f.name}<button onClick={() => setFiles(files.filter(x => x.url !== f.url))}><X size={9} /></button></span>)}
          <button data-testid="edit-request-send-btn" onClick={submit} disabled={busy} className="btn-primary text-sm ml-auto flex items-center gap-2 disabled:opacity-50">
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} Send request
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
