import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Star, GripVertical, ChevronDown, ExternalLink } from "lucide-react";

/** Star clients for the public landing page and drag them into the order you want. */
export default function ShowcaseManager({ apps, onChange }) {
  const [open, setOpen] = useState(false);
  const [drag, setDrag] = useState(null);
  const [saving, setSaving] = useState(false);

  const featured = apps.filter(a => a.featured)
    .sort((a, b) => (a.showcase_order ?? 0) - (b.showcase_order ?? 0));

  async function persist(list) {
    setSaving(true);
    try {
      await api.put("/apps/showcase/order", { app_ids: list.map(a => a.app_id) });
      onChange(list.map((a, i) => ({ ...a, showcase_order: i })));
      toast.success("Showcase order saved");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not save the order"); }
    finally { setSaving(false); }
  }

  function onDrop(target) {
    if (!drag || drag === target.app_id) return;
    const list = [...featured];
    const from = list.findIndex(a => a.app_id === drag);
    const to = list.findIndex(a => a.app_id === target.app_id);
    const [moved] = list.splice(from, 1);
    list.splice(to, 0, moved);
    setDrag(null);
    persist(list);
  }

  async function unfeature(a) {
    try {
      await api.patch(`/apps/${a.app_id}/showcase`, { featured: false });
      onChange(apps.map(x => x.app_id === a.app_id ? { ...x, featured: false } : x));
    } catch { toast.error("Could not update that client"); }
  }

  return (
    <div data-testid="showcase-manager" className="card-surface p-4 mb-6">
      <button data-testid="showcase-manager-toggle" onClick={() => setOpen(o => !o)} className="w-full flex items-center gap-3 text-left">
        <Star size={15} className="text-amber-400" />
        <div className="flex-1">
          <div className="text-sm font-semibold">Landing page showcase</div>
          <div className="text-[11px] text-[var(--mut)]">
            {featured.length === 0
              ? "No clients starred — the landing page shows your newest clients. Star the ones you want to feature."
              : `${featured.length} starred client${featured.length === 1 ? "" : "s"} on the landing page · drag to reorder`}
          </div>
        </div>
        {saving && <span className="text-[10px] font-mono text-[var(--mut)]">saving…</span>}
        <ChevronDown size={14} className={`text-[var(--mut)] transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="mt-4 pt-4 border-t border-[var(--line)] space-y-2">
          {featured.length === 0 && (
            <div className="text-xs text-[var(--mut)]">Click the star on any client card below to feature it here.</div>
          )}
          {featured.map((a, i) => (
            <div key={a.app_id} data-testid={`showcase-order-row-${a.app_id}`}
              draggable onDragStart={() => setDrag(a.app_id)} onDragOver={e => e.preventDefault()} onDrop={() => onDrop(a)}
              className={`flex items-center gap-3 px-3 py-2 rounded-xl border cursor-grab active:cursor-grabbing transition-colors ${drag === a.app_id ? "border-[var(--acc)] bg-[var(--acc)]/10" : "border-[var(--line)] hover:bg-white/5"}`}>
              <GripVertical size={14} className="text-[var(--dim)]" />
              <span className="font-mono text-[10px] text-[var(--dim)] w-4">{i + 1}</span>
              {a.thumbnail && <img src={a.thumbnail} alt="" className="w-9 h-9 rounded-lg object-cover" />}
              <div className="flex-1 min-w-0">
                <div className="text-sm truncate">{a.name}</div>
                <div className="text-[10px] text-[var(--dim)] truncate">{a.industry} · {a.status}</div>
              </div>
              <div className="flex items-center gap-1">
                <button data-testid={`showcase-move-up-${a.app_id}`} disabled={i === 0}
                  onClick={() => { const l = [...featured]; l.splice(i - 1, 0, l.splice(i, 1)[0]); persist(l); }}
                  className="px-2 py-1 rounded-md text-[10px] font-mono hover:bg-white/10 disabled:opacity-30">↑</button>
                <button data-testid={`showcase-move-down-${a.app_id}`} disabled={i === featured.length - 1}
                  onClick={() => { const l = [...featured]; l.splice(i + 1, 0, l.splice(i, 1)[0]); persist(l); }}
                  className="px-2 py-1 rounded-md text-[10px] font-mono hover:bg-white/10 disabled:opacity-30">↓</button>
                <button data-testid={`showcase-unfeature-${a.app_id}`} onClick={() => unfeature(a)}
                  className="px-2 py-1 rounded-md text-amber-400 hover:bg-white/10"><Star size={12} fill="currentColor" /></button>
              </div>
            </div>
          ))}
          <a href="/" target="_blank" rel="noreferrer" data-testid="showcase-preview-link"
            className="inline-flex items-center gap-1.5 text-[11px] text-[var(--mut)] hover:text-[var(--acc)] pt-1">
            <ExternalLink size={11} /> View the landing page
          </a>
        </div>
      )}
    </div>
  );
}
