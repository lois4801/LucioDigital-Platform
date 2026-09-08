import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Loader2, GitCompare, RotateCcw, Plus, Minus, Pencil } from "lucide-react";

const OP = {
  added: { icon: Plus, cls: "text-emerald-400 border-emerald-500/40 bg-emerald-500/[0.06]", label: "Comes back" },
  removed: { icon: Minus, cls: "text-red-400 border-red-500/40 bg-red-500/[0.06]", label: "Goes away" },
  edited: { icon: Pencil, cls: "text-amber-400 border-amber-500/40 bg-amber-500/[0.06]", label: "Changes" },
};

function Inline({ parts }) {
  return (
    <span className="text-xs leading-relaxed">
      {(parts || []).map((p, i) => (
        <span key={i} className={p.op === "added" ? "bg-emerald-500/20 text-emerald-300 rounded px-0.5" : p.op === "removed" ? "bg-red-500/20 text-red-300 line-through rounded px-0.5" : "text-[var(--mut)]"}>{p.text} </span>
      ))}
    </span>
  );
}

export function DiffDialog({ appId, pageId, version, open, onOpenChange, onRestored }) {
  const [diff, setDiff] = useState(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  async function load() {
    setLoading(true);
    try { const { data } = await api.get(`/apps/${appId}/pages/${pageId}/versions/${version.version_id}/diff`); setDiff(data); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not build the diff"); onOpenChange(false); } finally { setLoading(false); }
  }
  if (open && !diff && !loading) load();

  async function restore() {
    setBusy(true);
    try { const { data } = await api.post(`/apps/${appId}/pages/${pageId}/versions/${version.version_id}/restore`); toast.success("Page restored"); onOpenChange(false); setDiff(null); onRestored?.(data); }
    catch (e) { toast.error(e.response?.data?.detail || "Restore failed"); } finally { setBusy(false); }
  }

  const s = diff?.summary;
  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) setDiff(null); }}>
      <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)] max-w-3xl max-h-[88vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><GitCompare size={16} className="text-[var(--acc)]" /> What changes if you restore this</DialogTitle></DialogHeader>
        {loading || !diff ? <div className="py-12 text-center"><Loader2 className="animate-spin mx-auto text-[var(--acc)]" /></div> : <>
          <p className="text-sm text-[var(--mut)]">Comparing the live page with the {new Date(diff.version_at).toLocaleString()} version ({diff.reason}, saved by {diff.by}).</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2" data-testid="diff-summary">
            {[["added", s.added, "Sections back"], ["removed", s.removed, "Sections dropped"], ["edited", s.edited, "Sections changed"]].map(([k, v, l]) => (
              <div key={k} data-testid={`diff-count-${k}`} className={`card-surface p-3 text-center border ${OP[k].cls}`}>
                <div className="font-display text-xl font-bold">{v}</div><div className="text-[10px] uppercase tracking-wider">{l}</div>
              </div>
            ))}
            <div className="card-surface p-3 text-center"><div className="font-display text-xl font-bold">{s.sections_now} → {s.sections_after}</div><div className="text-[10px] uppercase tracking-wider text-[var(--mut)]">Sections</div></div>
          </div>
          {s.identical ? <div data-testid="diff-identical" className="card-surface p-6 text-center text-sm text-[var(--mut)]">This version is identical to the live page — nothing would change.</div>
            : <div className="space-y-2 max-h-72 overflow-y-auto scrollbar-thin" data-testid="diff-list">
              {diff.changes.map((c, i) => {
                const meta = OP[c.op]; const Icon = meta.icon;
                return (
                  <div key={i} data-testid={`diff-change-${i}`} className={`rounded-xl border p-3 ${meta.cls}`}>
                    <div className="flex items-center gap-2 text-xs font-semibold"><Icon size={12} /> {meta.label} · {c.type}{c.label ? ` — ${c.label}` : ""}{c.style_changed ? " · styling" : ""}</div>
                    <div className="mt-2 space-y-1.5">
                      {(c.fields || []).map((f, k) => (
                        <div key={k}><span className="font-mono text-[10px] text-[var(--dim)]">{f.field}</span><div><Inline parts={f.parts} /></div></div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>}
          <div className="flex gap-2 pt-1">
            <button data-testid="diff-cancel-btn" onClick={() => { onOpenChange(false); setDiff(null); }} className="btn-ghost text-sm">Cancel</button>
            <button data-testid="diff-restore-btn" onClick={restore} disabled={busy} className="btn-primary text-sm ml-auto flex items-center gap-2 disabled:opacity-50">
              {busy ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />} Restore this version
            </button>
          </div>
        </>}
      </DialogContent>
    </Dialog>
  );
}
