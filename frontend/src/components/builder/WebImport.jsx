import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Globe, Loader2, Link2, Check } from "lucide-react";

// Imports run as a backend job (scrape + AI rebuild takes longer than the 60s request cap).
export async function pollImport(appId, jobId, { tries = 100, every = 4000 } = {}) {
  for (let i = 0; i < tries; i++) {
    await new Promise(r => setTimeout(r, every));
    const { data } = await api.get(`/apps/${appId}/site/import-job/${jobId}`);
    if (data.status === "done") return data.result;
    if (data.status === "error") throw new Error(data.error || "Import failed");
  }
  throw new Error("Import timed out — try again");
}

export function WebImportDialog({ appId, open, onOpenChange, onDone }) {
  const [url, setUrl] = useState("");
  const [scanning, setScanning] = useState(false);
  const [applying, setApplying] = useState(false);
  const [preview, setPreview] = useState(null);
  const [mode, setMode] = useState("replace");
  const [applyTheme, setApplyTheme] = useState(true);

  function reset() { setPreview(null); setUrl(""); setScanning(false); setApplying(false); }

  async function scan() {
    if (!url.trim()) return;
    setScanning(true); setPreview(null);
    try {
      const { data: job } = await api.post(`/apps/${appId}/site/import-preview`, { url });
      const res = await pollImport(appId, job.job_id);
      setPreview(res);
      toast.success(`Scanned ${res.source?.pages || 1} page(s) — ${res.pages.length} page(s) rebuilt`);
    } catch (e) { toast.error(e.response?.data?.detail || e.message || "Scan failed"); } finally { setScanning(false); }
  }

  async function apply() {
    setApplying(true);
    try {
      const { data } = await api.post(`/apps/${appId}/site/import-apply`, { import_id: preview.import_id, mode, apply_theme: applyTheme }, { timeout: 120000 });
      toast.success(`${mode === "replace" ? "Replaced" : "Added"} ${data.pages.length} page(s) from the website`);
      onOpenChange(false); reset(); onDone?.();
    } catch (e) { toast.error(e.response?.data?.detail || "Apply failed"); } finally { setApplying(false); }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) reset(); }}>
      <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)] max-w-3xl max-h-[88vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><Globe size={16} className="text-[var(--acc)]" /> Import from a website</DialogTitle></DialogHeader>
        <p className="text-sm text-[var(--mut)]">Paste any public website address. We read its pages, copy, images, contact details and brand colours, then rebuild it as editable pages for this tenant.</p>
        <div className="flex gap-2">
          <div className="flex-1 flex items-center gap-2 bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3">
            <Link2 size={14} className="text-[var(--dim)]" />
            <input data-testid="web-import-url-input" value={url} onChange={e => setUrl(e.target.value)} onKeyDown={e => e.key === "Enter" && scan()}
              placeholder="acmeplumbing.com" className="flex-1 bg-transparent py-3 text-sm outline-none" />
          </div>
          <button data-testid="web-import-scan-btn" onClick={scan} disabled={scanning || !url.trim()} className="btn-primary flex items-center gap-2 disabled:opacity-50">
            {scanning ? <Loader2 size={14} className="animate-spin" /> : <Globe size={14} />}{scanning ? "Reading site (30–60s)…" : "Scan website"}
          </button>
        </div>

        {preview && (
          <div data-testid="web-import-preview" className="space-y-4 mt-2">
            <div className="grid sm:grid-cols-2 gap-3">
              <div className="card-surface p-4">
                <div className="overline mb-2">Business found</div>
                <div className="font-display font-semibold">{preview.business?.name}</div>
                <div className="text-xs text-[var(--mut)] mt-1 space-y-0.5">
                  {preview.business?.industry && <div>{preview.business.industry}</div>}
                  {preview.business?.email && <div>{preview.business.email}</div>}
                  {preview.business?.phone && <div>{preview.business.phone}</div>}
                  {preview.business?.address && <div>{preview.business.address}</div>}
                </div>
              </div>
              <div className="card-surface p-4">
                <div className="overline mb-2">Brand & media</div>
                <div className="flex items-center gap-2">
                  {[preview.theme?.primary, preview.theme?.secondary].filter(Boolean).map(c => <span key={c} className="w-6 h-6 rounded-lg border border-white/15" style={{ background: c }} title={c} />)}
                  <span className="text-xs font-mono text-[var(--dim)]">{preview.theme?.mode} · {preview.theme?.font_heading}</span>
                </div>
                <div className="text-xs text-[var(--mut)] mt-2">{preview.source?.pages} page(s) read · {preview.source?.images} image(s) found</div>
              </div>
            </div>
            <div className="card-surface p-4">
              <div className="overline mb-2">Pages to create</div>
              <div className="space-y-2">
                {preview.pages.map(p => (
                  <div key={p.slug} data-testid={`web-import-page-${p.slug}`} className="flex items-center gap-2 text-sm">
                    <Check size={13} className="text-[var(--acc)]" />
                    <span className="font-medium">{p.name}</span>
                    <span className="font-mono text-[11px] text-[var(--dim)]">{p.slug}</span>
                    <span className="ml-auto font-mono text-[11px] text-[var(--mut)]">{p.blocks} sections</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex card-surface !p-0.5 rounded-full">
                {[["replace", "Replace my pages"], ["append", "Add alongside"]].map(([k, l]) => (
                  <button key={k} data-testid={`web-import-mode-${k}`} onClick={() => setMode(k)} className={`px-4 py-2 rounded-full text-xs ${mode === k ? "bg-[var(--acc)]/15 text-[var(--acc)]" : "text-[var(--mut)]"}`}>{l}</button>
                ))}
              </div>
              <label className="flex items-center gap-2 text-xs text-[var(--mut)] cursor-pointer">
                <input data-testid="web-import-theme-toggle" type="checkbox" checked={applyTheme} onChange={e => setApplyTheme(e.target.checked)} className="accent-[var(--acc)]" />
                Use the website's colours & fonts
              </label>
              <button data-testid="web-import-apply-btn" onClick={apply} disabled={applying} className="btn-primary ml-auto flex items-center gap-2 disabled:opacity-50">
                {applying ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}{applying ? "Applying…" : "Apply to this tenant"}
              </button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
