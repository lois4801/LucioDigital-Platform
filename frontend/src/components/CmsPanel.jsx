import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Database, Plus, Trash2, Pencil, Eye, EyeOff, Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const EMPTY = { title: "", slug: "", excerpt: "", body: "", cover: "", date: "", tags: [], published: true };

export default function CmsPanel({ appId }) {
  const [cols, setCols] = useState([]);
  const [cur, setCur] = useState(null);
  const [edit, setEdit] = useState(null);
  const [newCol, setNewCol] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { load(); }, [appId]);
  async function load() { const { data } = await api.get(`/apps/${appId}/cms`); setCols(data); setCur(c => c || data[0]?.collection_id); }
  const col = cols.find(c => c.collection_id === cur);
  async function addCol() { if (!newCol.trim()) return; try { const { data } = await api.post(`/apps/${appId}/cms`, { name: newCol }); setCols([...cols, data]); setCur(data.collection_id); setNewCol(""); } catch (e) { toast.error(e.response?.data?.detail || "Failed"); } }
  async function delCol(c) { if (!confirm(`Delete "${c.name}" and all its items?`)) return; await api.delete(`/apps/${appId}/cms/${c.collection_id}`); const rest = cols.filter(x => x.collection_id !== c.collection_id); setCols(rest); setCur(rest[0]?.collection_id); }
  async function save() {
    setBusy(true);
    const payload = { ...edit, tags: typeof edit.tags === "string" ? edit.tags.split(",").map(t => t.trim()).filter(Boolean) : edit.tags };
    try {
      const { data } = edit.item_id ? await api.put(`/apps/${appId}/cms/${cur}/items/${edit.item_id}`, payload) : await api.post(`/apps/${appId}/cms/${cur}/items`, payload);
      setCols(cols.map(c => c.collection_id !== cur ? c : { ...c, items: edit.item_id ? c.items.map(i => i.item_id === data.item_id ? data : i) : [data, ...c.items] }));
      setEdit(null); toast.success("Saved");
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); } finally { setBusy(false); }
  }
  async function togglePub(it) { const { data } = await api.put(`/apps/${appId}/cms/${cur}/items/${it.item_id}`, { ...it, published: !it.published }); setCols(cols.map(c => c.collection_id !== cur ? c : { ...c, items: c.items.map(i => i.item_id === data.item_id ? data : i) })); }
  async function delItem(it) { if (!confirm("Delete item?")) return; await api.delete(`/apps/${appId}/cms/${cur}/items/${it.item_id}`); setCols(cols.map(c => c.collection_id !== cur ? c : { ...c, items: c.items.filter(i => i.item_id !== it.item_id) })); }
  const inp = "w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--acc)]";

  return (
    <div data-testid="cms-panel" className="grid lg:grid-cols-[240px_1fr] gap-5">
      <aside className="card-surface p-3 space-y-1">
        <div className="overline px-1 mb-2 flex items-center gap-2"><Database size={11} className="text-[var(--acc)]" /> Collections</div>
        {cols.map(c => <div key={c.collection_id} className={`group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer text-sm ${cur === c.collection_id ? "bg-[var(--acc)]/10 text-[var(--acc)]" : "hover:bg-white/5"}`} data-testid={`cms-collection-${c.slug}`} onClick={() => setCur(c.collection_id)}>
          <span>{c.name} <span className="font-mono text-[10px] text-[var(--dim)]">/{c.slug}</span></span><span className="flex items-center gap-2"><span className="font-mono text-[10px] text-[var(--dim)]">{c.items.length}</span><button onClick={e => { e.stopPropagation(); delCol(c); }} className="opacity-0 group-hover:opacity-100 hover:text-red-400"><Trash2 size={11} /></button></span></div>)}
        <div className="flex gap-1 pt-2"><input data-testid="cms-new-collection-input" value={newCol} onChange={e => setNewCol(e.target.value)} placeholder="New collection" className="flex-1 bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2 py-1.5 text-xs outline-none" /><button data-testid="cms-new-collection-btn" onClick={addCol} className="w-8 h-8 rounded-lg border border-[var(--line)] flex items-center justify-center hover:bg-white/5"><Plus size={12} /></button></div>
        <div className="px-1 pt-3 text-[10px] text-[var(--dim)] leading-relaxed">Add a “Collection list” block in Site Mode to display items. Each published item exports as its own page.</div>
      </aside>
      <div className="card-surface p-5">
        {col && <>
          <div className="flex items-center justify-between mb-4"><div><div className="overline">{col.name}</div><div className="text-xs text-[var(--mut)] font-mono">block collection key: <span className="text-[var(--fg)]">{col.slug}</span></div></div>
            <button data-testid="cms-new-item-btn" onClick={() => setEdit({ ...EMPTY })} className="btn-primary text-sm !py-2 !px-4 flex items-center gap-2"><Plus size={14} /> New item</button></div>
          {col.items.length === 0 ? <div className="p-12 text-center text-sm text-[var(--mut)]">No items yet.</div> : (
            <div className="divide-y divide-[var(--line)]">{col.items.map(it => (
              <div key={it.item_id} data-testid="cms-item-row" className="py-3 flex items-center gap-3">
                {it.cover ? <img src={it.cover} alt="" className="w-14 h-10 object-cover rounded-md" /> : <div className="w-14 h-10 rounded-md bg-[var(--bg-2)]" />}
                <div className="flex-1 min-w-0"><div className="text-sm font-semibold truncate">{it.title}</div><div className="text-[11px] font-mono text-[var(--dim)] truncate">/{col.slug}/{it.slug} · {it.date} {it.tags?.length ? "· " + it.tags.join(", ") : ""}</div></div>
                <span className={`chip ${it.published ? "chip-active" : ""}`} style={{ padding: "1px 6px" }}>{it.published ? "published" : "draft"}</span>
                <button data-testid="cms-item-toggle-btn" onClick={() => togglePub(it)} className="w-8 h-8 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-white/5">{it.published ? <EyeOff size={12} /> : <Eye size={12} />}</button>
                <button data-testid="cms-item-edit-btn" onClick={() => setEdit({ ...it, tags: (it.tags || []).join(", ") })} className="w-8 h-8 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-white/5"><Pencil size={12} /></button>
                <button onClick={() => delItem(it)} className="w-8 h-8 rounded-full border border-[var(--line)] flex items-center justify-center hover:text-red-400"><Trash2 size={12} /></button>
              </div>))}</div>)}
        </>}
      </div>
      <Dialog open={!!edit} onOpenChange={o => !o && setEdit(null)}>
        <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)] max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-display">{edit?.item_id ? "Edit item" : "New item"}</DialogTitle></DialogHeader>
          {edit && <div className="space-y-3">
            <input data-testid="cms-item-title-input" value={edit.title} onChange={e => setEdit({ ...edit, title: e.target.value })} placeholder="Title" className={inp} />
            <div className="grid grid-cols-2 gap-3"><input value={edit.slug} onChange={e => setEdit({ ...edit, slug: e.target.value })} placeholder="slug (auto)" className={inp} /><input type="date" value={edit.date || ""} onChange={e => setEdit({ ...edit, date: e.target.value })} className={inp} /></div>
            <input data-testid="cms-item-cover-input" value={edit.cover} onChange={e => setEdit({ ...edit, cover: e.target.value })} placeholder="Cover image URL" className={inp} />
            <textarea data-testid="cms-item-excerpt-input" value={edit.excerpt} onChange={e => setEdit({ ...edit, excerpt: e.target.value })} rows={2} placeholder="Excerpt" className={inp} />
            <textarea data-testid="cms-item-body-input" value={edit.body} onChange={e => setEdit({ ...edit, body: e.target.value })} rows={8} placeholder="Body (paragraphs separated by new lines)" className={inp} />
            <input value={edit.tags} onChange={e => setEdit({ ...edit, tags: e.target.value })} placeholder="tags, comma, separated" className={inp} />
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={edit.published} onChange={e => setEdit({ ...edit, published: e.target.checked })} /> Published</label>
            <button data-testid="cms-item-save-btn" onClick={save} disabled={busy || !edit.title.trim()} className="btn-primary w-full disabled:opacity-50">{busy ? <Loader2 size={14} className="animate-spin mx-auto" /> : "Save item"}</button>
          </div>}
        </DialogContent>
      </Dialog>
    </div>
  );
}
