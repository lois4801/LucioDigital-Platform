import { useState, useEffect } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { History, Loader2, Eye, RotateCcw, Clock, GitCompare } from "lucide-react";

const REASONS = { save: "Manual save", "before restore": "Before a restore", "before AI site generation": "Before AI rebuild" };

export function HistoryDialog({ appId, pageId, pageName, open, onOpenChange, onPreview, onRestored, onSiteRestored, onCompare }) {
  const [versions, setVersions] = useState([]);
  const [points, setPoints] = useState([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    if (!open || !pageId) return;
    setLoading(true);
    Promise.all([
      api.get(`/apps/${appId}/pages/${pageId}/versions`).then(r => setVersions(r.data.versions)),
      api.get(`/apps/${appId}/site/restore-points`).then(r => setPoints(r.data.restore_points)).catch(() => { }),
    ]).catch(() => toast.error("Could not load history")).finally(() => setLoading(false));
  }, [open, pageId, appId]);

  async function undoBatch(b) {
    if (!window.confirm(`Put the whole site back to how it was ${new Date(b.created_at).toLocaleString()} (${b.pages.length} page(s), ${b.reason})? The current site is snapshotted first.`)) return;
    setBusy(b.batch_id);
    try { const { data } = await api.post(`/apps/${appId}/site/restore-batch`, { batch_id: b.batch_id }); toast.success(`Site restored — ${data.pages.length} page(s) put back`); onOpenChange(false); onSiteRestored?.(); }
    catch (e) { toast.error(e.response?.data?.detail || "Undo failed"); } finally { setBusy(""); }
  }

  async function preview(v) {
    setBusy(v.version_id);
    try { const { data } = await api.get(`/apps/${appId}/pages/${pageId}/versions/${v.version_id}`); onPreview(data); onOpenChange(false); toast.info(`Previewing the ${new Date(v.created_at).toLocaleString()} version — nothing is saved until you restore it`); }
    catch (e) { toast.error(e.response?.data?.detail || "Preview failed"); } finally { setBusy(""); }
  }

  async function restore(v) {
    if (!window.confirm(`Restore "${pageName}" to the ${new Date(v.created_at).toLocaleString()} version? The current page is snapshotted first, so this is reversible.`)) return;
    setBusy(v.version_id);
    try { const { data } = await api.post(`/apps/${appId}/pages/${pageId}/versions/${v.version_id}/restore`); toast.success("Page restored"); onRestored?.(data); onOpenChange(false); }
    catch (e) { toast.error(e.response?.data?.detail || "Restore failed"); } finally { setBusy(""); }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)] max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><History size={16} className="text-[var(--acc)]" /> History — {pageName}</DialogTitle></DialogHeader>
        <p className="text-sm text-[var(--mut)]">Every save, import and rebuild is snapshotted (last 30 kept). Preview a version in the canvas without touching the live page, then restore it if you like it.</p>
        {points.length > 0 && (
          <div data-testid="restore-points" className="space-y-2">
            <div className="overline">Undo a whole site change</div>
            {points.slice(0, 5).map(b => (
              <div key={b.batch_id} data-testid={`restore-point-${b.batch_id}`} className="card-surface p-3 flex flex-wrap items-center gap-3 border-amber-400/30">
                <RotateCcw size={13} className="text-amber-400" />
                <div className="min-w-[190px]">
                  <div className="text-sm font-medium">{new Date(b.created_at).toLocaleString()}</div>
                  <div className="text-[10px] text-[var(--dim)]">{b.reason} · {b.pages.length} page(s) · {b.by}</div>
                </div>
                <button data-testid={`restore-point-btn-${b.batch_id}`} onClick={() => undoBatch(b)} disabled={!!busy} className="btn-ghost !py-1.5 text-[11px] ml-auto flex items-center gap-1.5 disabled:opacity-50">
                  {busy === b.batch_id ? <Loader2 size={11} className="animate-spin" /> : <RotateCcw size={11} />} Put this site back
                </button>
              </div>
            ))}
            <div className="overline pt-2">This page's versions</div>
          </div>
        )}
        {loading ? <div className="py-10 text-center"><Loader2 className="animate-spin mx-auto text-[var(--acc)]" /></div>
          : versions.length === 0 ? <div className="card-surface p-8 text-center text-sm text-[var(--mut)]" data-testid="history-empty">No history yet — the next save creates the first version.</div>
            : <div className="space-y-2" data-testid="history-list">
              {versions.map((v, i) => (
                <div key={v.version_id} data-testid={`history-item-${i}`} className="card-surface p-3 flex flex-wrap items-center gap-3">
                  <Clock size={13} className="text-[var(--dim)]" />
                  <div className="min-w-[170px]">
                    <div className="text-sm font-medium">{new Date(v.created_at).toLocaleString()}</div>
                    <div className="text-[10px] text-[var(--dim)]">{v.sections} sections · {v.by} · {REASONS[v.reason] || v.reason}</div>
                  </div>
                  {i === 0 && <span className="chip chip-active text-[9px]" style={{ padding: "0 6px" }}>latest</span>}
                  <div className="flex gap-1.5 ml-auto">
                    <button data-testid={`history-preview-${i}`} onClick={() => preview(v)} disabled={!!busy} className="btn-ghost !py-1.5 text-[11px] flex items-center gap-1.5 disabled:opacity-50"><Eye size={11} /> Preview</button>
                    <button data-testid={`history-restore-${i}`} onClick={() => onCompare?.(v)} disabled={!!busy} className="btn-primary !py-1.5 text-[11px] flex items-center gap-1.5 disabled:opacity-50"><GitCompare size={11} /> Compare & restore</button>
                  </div>
                </div>
              ))}
            </div>}
      </DialogContent>
    </Dialog>
  );
}
