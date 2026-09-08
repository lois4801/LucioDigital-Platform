import { useState, useEffect } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Globe, Loader2, Link2, Check } from "lucide-react";

// Imports run as a backend job (scrape + AI rebuild takes longer than the 60s request cap).
export const IMPORT_STAGES = [["scanning", "Scanning site"], ["reading", "Reading pages"], ["rebuilding", "Rebuilding with AI"], ["applying", "Applying pages"]];

export function ImportProgress({ stage, started, testid = "import-progress" }) {
  const [secs, setSecs] = useState(0);
  useEffect(() => { const t = setInterval(() => setSecs(Math.round((Date.now() - started) / 1000)), 1000); return () => clearInterval(t); }, [started]);
  const idx = Math.max(0, IMPORT_STAGES.findIndex(s => s[0] === (stage?.stage || "scanning")));
  return (
    <div data-testid={testid} className="card-surface p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="overline">Importing website</div>
        <span className="font-mono text-[10px] text-[var(--dim)]">{secs}s elapsed</span>
      </div>
      <div className="space-y-2">
        {IMPORT_STAGES.map(([k, label], i) => (
          <div key={k} data-testid={`import-step-${k}`} className="flex items-center gap-2 text-sm">
            <span className={`w-5 h-5 rounded-full flex items-center justify-center border ${i < idx ? "border-[var(--acc)] bg-[var(--acc)]/20 text-[var(--acc)]" : i === idx ? "border-[var(--acc)] text-[var(--acc)]" : "border-[var(--line)] text-[var(--dim)]"}`}>
              {i < idx ? <Check size={11} /> : i === idx ? <Loader2 size={11} className="animate-spin" /> : <span className="text-[10px] font-mono">{i + 1}</span>}
            </span>
            <span className={i <= idx ? "text-[var(--fg)]" : "text-[var(--dim)]"}>{label}</span>
            {i === idx && stage?.stage_detail && <span className="text-[11px] text-[var(--mut)] truncate">— {stage.stage_detail}</span>}
          </div>
        ))}
      </div>
      <div className="h-1 rounded-full bg-white/8 overflow-hidden"><div className="h-full bg-[var(--acc)] transition-all duration-700" style={{ width: `${((idx + 0.5) / IMPORT_STAGES.length) * 100}%` }} /></div>
    </div>
  );
}

export async function pollImport(appId, jobId, { tries = 100, every = 4000, onStage } = {}) {
  for (let i = 0; i < tries; i++) {
    await new Promise(r => setTimeout(r, every));
    const { data } = await api.get(`/apps/${appId}/site/import-job/${jobId}`);
    onStage?.(data);
    if (data.status === "done") return data.result;
    if (data.status === "error") throw new Error(data.error || "Import failed");
  }
  throw new Error("Import timed out — try again");
}

export function WebImportDialog({ appId, open, onOpenChange, onDone }) {
  const [url, setUrl] = useState("");
  const [scanning, setScanning] = useState(false);
  const [stage, setStage] = useState(null);
  const [startedAt, setStartedAt] = useState(0);
  const [applying, setApplying] = useState(false);
  const [preview, setPreview] = useState(null);
  const [mode, setMode] = useState("replace");
  const [applyTheme, setApplyTheme] = useState(true);

  function reset() { setPreview(null); setUrl(""); setScanning(false); setApplying(false); }

  async function scan() {
    if (!url.trim()) return;
    setScanning(true); setPreview(null); setStage({ stage: "scanning", stage_detail: "Starting import" });
    const started = Date.now(); setStartedAt(started);
    try {
      const { data: job } = await api.post(`/apps/${appId}/site/import-preview`, { url });
      const res = await pollImport(appId, job.job_id, { onStage: setStage });
      setPreview(res);
      toast.success(`Scanned ${res.source?.pages || 1} page(s) in ${Math.round((Date.now() - started) / 1000)}s`);
    } catch (e) { toast.error(e.response?.data?.detail || e.message || "Scan failed"); } finally { setScanning(false); setStage(null); }
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
            {scanning ? <Loader2 size={14} className="animate-spin" /> : <Globe size={14} />}{scanning ? "Reading site…" : "Scan website"}
          </button>
        </div>

        {scanning && stage && <ImportProgress stage={stage} started={startedAt} testid="web-import-progress" />}

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
