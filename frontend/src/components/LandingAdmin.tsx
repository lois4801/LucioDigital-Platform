import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Pencil, Trash2, Plus, X, Check, Settings2 } from "lucide-react";
import api from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export async function saveLanding(patch) {
  const { data } = await api.put("/admin/landing", patch);
  return data;
}

// Click-to-edit headline for admins; plain text for visitors.
export function AdminText({ admin, value, onSave, as: Tag = "span", className, testid }) {
  const ref = useRef(null);
  if (!admin) return <Tag className={className} data-testid={testid}>{value}</Tag>;
  return (
    <Tag ref={ref} data-testid={testid} contentEditable suppressContentEditableWarning title="Click to edit"
      className={`${className || ""} outline-none rounded-sm cursor-text hover:ring-1 hover:ring-[var(--acc)]/50 focus:ring-2 focus:ring-[var(--acc)] transition-shadow`}
      onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); ref.current.blur(); } if (e.key === "Escape") { ref.current.innerText = value; ref.current.blur(); } }}
      onBlur={async () => { const v = ref.current.innerText.trim(); if (v && v !== value) { try { await onSave(v); toast.success("Saved"); } catch { toast.error("Save failed"); ref.current.innerText = value; } } }}>
      {value}
    </Tag>
  );
}

export function CardEditor({ card, open, onClose, onSave }) {
  const [f, setF] = useState(card || {});
  useEffect(() => setF(card || {}), [card]);
  return (
    <Dialog open={open} onOpenChange={o => !o && onClose()}>
      <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)] max-w-md" data-testid="card-editor">
        <DialogHeader><DialogTitle className="font-display">{card?.id ? "Edit card" : "New card"}</DialogTitle></DialogHeader>
        {f.image && <img src={f.image} alt="" className="w-full aspect-[16/9] object-cover rounded-xl border border-[var(--line)]" />}
        <label className="text-xs text-[var(--mut)]">Title<input data-testid="card-title-input" value={f.title || ""} onChange={e => setF({ ...f, title: e.target.value })} className="mt-1 w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm text-[var(--fg)] outline-none focus:border-[var(--acc)]" /></label>
        <label className="text-xs text-[var(--mut)]">Description<textarea data-testid="card-desc-input" rows={3} value={f.description || ""} onChange={e => setF({ ...f, description: e.target.value })} className="mt-1 w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm text-[var(--fg)] outline-none focus:border-[var(--acc)]" /></label>
        <label className="text-xs text-[var(--mut)]">Cover image URL<input data-testid="card-image-input" value={f.image || ""} onChange={e => setF({ ...f, image: e.target.value })} placeholder="https://images.unsplash.com/…" className="mt-1 w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm font-mono text-[var(--fg)] outline-none focus:border-[var(--acc)]" /></label>
        <div className="flex justify-end gap-2"><button onClick={onClose} className="btn-ghost text-sm">Cancel</button><button data-testid="card-save-btn" disabled={!f.title?.trim()} onClick={() => onSave(f)} className="btn-primary text-sm disabled:opacity-50">Save card</button></div>
      </DialogContent>
    </Dialog>
  );
}

export function MarqueeEditor({ items, open, onClose, onSave }) {
  const [list, setList] = useState(items);
  const [draft, setDraft] = useState("");
  useEffect(() => setList(items), [items, open]);
  return (
    <Dialog open={open} onOpenChange={o => !o && onClose()}>
      <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)] max-w-md" data-testid="marquee-editor">
        <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><Settings2 size={15} className="text-[var(--acc)]" /> Ticker items</DialogTitle></DialogHeader>
        <div className="space-y-2 max-h-[50vh] overflow-y-auto scrollbar-thin pr-1">
          {list.map((m, i) => (
            <div key={i} className="flex gap-2 items-center">
              <input data-testid={`marquee-item-${i}`} value={m} onChange={e => setList(list.map((x, k) => k === i ? e.target.value : x))} className="flex-1 bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-1.5 text-sm text-[var(--fg)] outline-none focus:border-[var(--acc)]" />
              <button data-testid={`marquee-remove-${i}`} onClick={() => setList(list.filter((_, k) => k !== i))} className="p-1.5 rounded-md text-[var(--dim)] hover:text-red-400 hover:bg-red-400/10"><X size={13} /></button>
            </div>
          ))}
        </div>
        <form className="flex gap-2" onSubmit={e => { e.preventDefault(); if (draft.trim()) { setList([...list, draft.trim()]); setDraft(""); } }}>
          <input data-testid="marquee-new-input" value={draft} onChange={e => setDraft(e.target.value)} placeholder="Add item…" className="flex-1 bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-1.5 text-sm text-[var(--fg)] outline-none focus:border-[var(--acc)]" />
          <button data-testid="marquee-add-btn" type="submit" className="btn-ghost text-sm !py-1.5 !px-3 flex items-center gap-1"><Plus size={13} /> Add</button>
        </form>
        <div className="flex justify-end gap-2"><button onClick={onClose} className="btn-ghost text-sm">Cancel</button><button data-testid="marquee-save-btn" onClick={() => onSave(list)} className="btn-primary text-sm flex items-center gap-1"><Check size={13} /> Save ticker</button></div>
      </DialogContent>
    </Dialog>
  );
}

export function CardAdminControls({ onEdit, onDelete }) {
  return (
    <div className="absolute top-3 right-3 flex gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity z-10" onClick={e => e.stopPropagation()}>
      <button data-testid="card-edit-btn" onClick={onEdit} className="w-8 h-8 rounded-full bg-black/70 backdrop-blur border border-white/15 flex items-center justify-center hover:bg-[var(--acc)] hover:text-black transition-colors" title="Edit card"><Pencil size={13} /></button>
      <button data-testid="card-delete-btn" onClick={onDelete} className="w-8 h-8 rounded-full bg-black/70 backdrop-blur border border-white/15 flex items-center justify-center hover:bg-red-500 transition-colors" title="Delete card"><Trash2 size={13} /></button>
    </div>
  );
}
