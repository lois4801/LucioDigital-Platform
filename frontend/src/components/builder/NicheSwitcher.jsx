import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Palette, Loader2, Check, X, Eye } from "lucide-react";
import api from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export function NicheSwitcher({ appId, current, onPreview, open, onOpenChange }) {
  const [niches, setNiches] = useState([]);
  const [busy, setBusy] = useState(null);
  useEffect(() => { if (open && !niches.length) api.get("/site-niches").then(r => setNiches(r.data)).catch(() => {}); }, [open, niches.length]);
  async function preview(n) {
    setBusy(n.key);
    try { const { data } = await api.post(`/apps/${appId}/site/niche-preview`, { niche: n.key }); onPreview(data); onOpenChange(false); }
    catch (e) { toast.error(e.response?.data?.detail || "Preview failed"); } finally { setBusy(null); }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)] max-w-5xl">
        <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><Palette size={16} className="text-[var(--acc)]" /> Try your site in another industry look</DialogTitle></DialogHeader>
        <p className="text-sm text-[var(--mut)]">Preview is non-destructive — nothing is saved until you click <b>Apply this look</b>.</p>
        <div data-testid="niche-switcher-grid" className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 max-h-[60vh] overflow-y-auto scrollbar-thin pr-1">
          {niches.map(n => (
            <button key={n.key} data-testid={`niche-option-${n.key}`} onClick={() => preview(n)} disabled={!!busy} className={`card-lift text-left rounded-2xl border overflow-hidden bg-[var(--bg-2)] relative ${current === n.key ? "border-[var(--acc)]" : "border-[var(--line)]"}`}>
              <div className="aspect-[16/9] relative"><img src={n.hero} alt="" className="w-full h-full object-cover" /><div className="absolute inset-0" style={{ background: `linear-gradient(180deg, transparent 30%, #0A0A0F 100%)` }} /><span className="absolute top-2 left-2 chip normal-case tracking-normal">{n.industry}</span>{current === n.key && <span className="absolute top-2 right-2 chip chip-active"><Check size={10} /> current</span>}</div>
              <div className="p-3"><div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full" style={{ background: n.primary }} /><span className="w-2.5 h-2.5 rounded-full" style={{ background: n.secondary }} /><div className="font-display font-semibold text-sm truncate">{n.brand}</div></div><div className="text-[11px] text-[var(--mut)] mt-1 line-clamp-2">{n.title}</div><div className="text-[10px] font-mono text-[var(--dim)] mt-2 capitalize">{n.mood} · {n.sections.length} sections</div></div>
              {busy === n.key && <div className="absolute inset-0 bg-black/50 flex items-center justify-center"><Loader2 size={18} className="animate-spin text-[var(--acc)]" /></div>}
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function NichePreviewBar({ preview, onApply, onExit, applying }) {
  if (!preview) return null;
  return (
    <div data-testid="niche-preview-bar" className="flex flex-wrap items-center gap-3 px-4 py-2.5 rounded-xl border border-[var(--acc)]/40 bg-[var(--acc)]/10 text-sm">
      <Eye size={14} className="text-[var(--acc)]" /><span>Previewing <b>{preview.brand}</b> ({preview.niche.replace(/_/g, " ")}) — {preview.pages.length} pages. Your saved site is untouched.</span>
      <div className="ml-auto flex gap-2">
        <button data-testid="niche-preview-exit" onClick={onExit} className="btn-ghost text-xs !py-1.5 !px-3 flex items-center gap-1"><X size={12} /> Back to my site</button>
        <button data-testid="niche-preview-apply" onClick={onApply} disabled={applying} className="btn-primary text-xs !py-1.5 !px-3 flex items-center gap-1">{applying ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />} Apply this look</button>
      </div>
    </div>
  );
}
