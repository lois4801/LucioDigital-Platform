import { useState, useEffect, useRef } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Globe, Loader2, Link2, Check, AlertTriangle, Image as ImageIcon, FileText, Layers, Upload, X } from "lucide-react";

// Imports run as a backend job (crawl + media + AI rebuild takes far longer than the 60s request cap).
export const IMPORT_STAGES = [["scanning", "Scanning site"], ["reading", "Crawling pages"], ["media", "Saving images"], ["rebuilding", "Rebuilding with AI"], ["applying", "Applying pages"], ["videos", "Sourcing videos"]];

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

export async function pollImport(appId, jobId, { tries = 160, every = 4000, onStage } = {}) {
  for (let i = 0; i < tries; i++) {
    await new Promise(r => setTimeout(r, every));
    const { data } = await api.get(`/apps/${appId}/site/import-job/${jobId}`);
    onStage?.(data);
    if (data.status === "done") return data.result;
    if (data.status === "error") throw new Error(data.error || "Import failed");
  }
  throw new Error("Import timed out — try again");
}

const Stat = ({ icon: Icon, value, label, testid }) => (
  <div data-testid={testid} className="card-surface p-3 text-center">
    <Icon size={14} className="mx-auto text-[var(--acc)]" />
    <div className="font-display text-xl font-bold mt-1">{value}</div>
    <div className="text-[10px] uppercase tracking-wider text-[var(--mut)]">{label}</div>
  </div>
);

export function ImportReport({ report, testid = "import-report" }) {
  if (!report) return null;
  return (
    <div data-testid={testid} className="space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <Stat icon={Layers} value={report.pages_imported} label="Pages imported" testid="report-pages" />
        <Stat icon={ImageIcon} value={`${report.images_saved}/${report.images_found}`} label="Images saved" testid="report-images" />
        <Stat icon={FileText} value={report.forms_detected} label="Forms rebuilt" testid="report-forms" />
        {report.zip_files > 0 && <Stat icon={Layers} value={`${report.assets_saved}/${report.zip_files}`} label="ZIP assets" testid="report-zip" />}
        <Stat icon={Link2} value={`${report.nav_items}${report.dropdowns ? ` · ${report.dropdowns}▾` : ""}`} label="Nav items" testid="report-nav" />
        {report.videos_found > 0 && <Stat icon={Layers} value={`${report.videos_embedded}/${report.videos_found}`} label="Videos" testid="report-videos" />}
      </div>
      {report.failures?.length > 0 && (
        <div data-testid="report-failures" className="card-surface p-3">
          <div className="flex items-center gap-2 mb-2"><AlertTriangle size={13} className="text-amber-400" /><span className="overline">{report.failed_count} item(s) need you to fill them in manually</span></div>
          <div className="max-h-40 overflow-y-auto scrollbar-thin space-y-1">
            {report.failures.map((f, i) => (
              <div key={i} className="text-[11px] flex gap-2"><span className="font-mono text-[var(--dim)] truncate max-w-[55%]">{f.item}</span><span className="text-[var(--mut)]">{f.reason}</span></div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function WebImportDialog({ appId, open, onOpenChange, onDone }) {
  const [url, setUrl] = useState("");
  const [maxPages, setMaxPages] = useState(100);
  const [scanning, setScanning] = useState(false);
  const [applying, setApplying] = useState(false);
  const [preview, setPreview] = useState(null);
  const [stage, setStage] = useState(null);
  const [startedAt, setStartedAt] = useState(0);
  const [mode, setMode] = useState("replace");
  const [applyTheme, setApplyTheme] = useState(true);
  const [uploads, setUploads] = useState([]);
  const [discovery, setDiscovery] = useState(null);
  const [picked, setPicked] = useState({});
  const [sourceVideos, setSourceVideos] = useState(true);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);
  const zipRef = useRef(null);

  async function importZip(f) {
    if (!f) return;
    setApplying(true); setPreview(null); setDiscoveryNull(); setStage({ stage: "scanning", stage_detail: `Unpacking ${f.name}` }); setStartedAt(Date.now());
    try {
      const fd = new FormData(); fd.append("file", f); fd.append("mode", mode); fd.append("apply_theme", String(applyTheme));
      const { data: job } = await api.post(`/apps/${appId}/site/import-zip`, fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 600000 });
      const res = await pollImport(appId, job.job_id, { onStage: setStage });
      setPreview(res);
      toast.success(`Imported ${res.applied?.pages?.length || res.pages.length} page(s) from ${f.name}`);
      onDone?.();
    } catch (e) { toast.error(e.response?.data?.detail || e.message || "ZIP import failed"); } finally { setApplying(false); setStage(null); }
  }
  const setDiscoveryNull = () => setDiscovery(null);

  function reset() { setPreview(null); setUrl(""); setScanning(false); setApplying(false); setStage(null); setUploads([]); setDiscovery(null); setPicked({}); }

  async function discover() {
    if (!url.trim()) return;
    setScanning(true); setPreview(null); setDiscovery(null); setStage({ stage: "scanning", stage_detail: "Discovering pages" });
    const started = Date.now(); setStartedAt(started);
    try {
      const { data: job } = await api.post(`/apps/${appId}/site/discover`, { url, max_pages: Number(maxPages) || 100 });
      const res = await pollImport(appId, job.job_id, { onStage: setStage, every: 3000 });
      setDiscovery(res);
      setPicked(Object.fromEntries(res.pages.map(p => [p.slug, p.important])));
      toast.success(`Found ${res.totals.pages} page(s) in ${Math.round((Date.now() - started) / 1000)}s — ${res.totals.important} look important`);
    } catch (e) { toast.error(e.response?.data?.detail || e.message || "Discovery failed"); } finally { setScanning(false); setStage(null); }
  }

  async function importSelected() {
    const slugs = Object.entries(picked).filter(([, v]) => v).map(([k]) => k);
    if (!slugs.length) return toast.error("Tick at least one page");
    setApplying(true); setStage({ stage: "media", stage_detail: `Rebuilding ${slugs.length} page(s)` }); setStartedAt(Date.now());
    try {
      const { data: job } = await api.post(`/apps/${appId}/site/import-selected`, { discovery_id: discovery.discovery_id, slugs, mode, apply_theme: applyTheme, source_videos: sourceVideos });
      const res = await pollImport(appId, job.job_id, { onStage: setStage });
      setPreview(res);
      toast.success(`Imported ${res.applied?.pages?.length || res.pages.length} page(s)${res.videos?.saved ? ` + ${res.videos.saved} video(s)` : ""}`);
      onDone?.();
    } catch (e) { toast.error(e.response?.data?.detail || e.message || "Import failed"); } finally { setApplying(false); setStage(null); }
  }

  async function scan() {
    if (!url.trim()) return;
    setScanning(true); setPreview(null); setStage({ stage: "scanning", stage_detail: "Starting full-site crawl" });
    const started = Date.now(); setStartedAt(started);
    try {
      const { data: job } = await api.post(`/apps/${appId}/site/import-preview`, { url, max_pages: Number(maxPages) || 25 });
      const res = await pollImport(appId, job.job_id, { onStage: setStage });
      setPreview(res);
      toast.success(`Crawled ${res.report.crawled} page(s) in ${Math.round((Date.now() - started) / 1000)}s`);
    } catch (e) { toast.error(e.response?.data?.detail || e.message || "Scan failed"); } finally { setScanning(false); setStage(null); }
  }

  async function apply() {
    setApplying(true);
    try {
      const { data } = await api.post(`/apps/${appId}/site/import-apply`, { import_id: preview.import_id, mode, apply_theme: applyTheme }, { timeout: 180000 });
      toast.success(`${mode === "replace" ? "Replaced" : "Added"} ${data.pages.length} page(s) from the website`);
      onOpenChange(false); reset(); onDone?.();
    } catch (e) { toast.error(e.response?.data?.detail || "Apply failed"); } finally { setApplying(false); }
  }

  async function addFiles(list) {
    const files = Array.from(list || []);
    if (!files.length) return;
    setUploading(true);
    for (const f of files) {
      const fd = new FormData(); fd.append("file", f);
      try {
        const { data } = await api.post(`/apps/${appId}/files`, fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 240000 });
        setUploads(u => [...u, { name: data.original_filename, url: data.url, type: data.content_type }]);
      } catch (e) { toast.error(`${f.name}: ${e.response?.data?.detail || "upload failed"}`); }
    }
    setUploading(false);
    toast.success("Added to this client's media library — pick them from any image or video block");
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) reset(); }}>
      <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)] max-w-3xl max-h-[88vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><Globe size={16} className="text-[var(--acc)]" /> Import a whole website</DialogTitle></DialogHeader>
        <p className="text-sm text-[var(--mut)]">Paste a website, hit <strong>Find pages</strong> to see everything it has, then tick the pages you want. We download all images and videos, rebuild every form (wired to your Inbox), recreate the navigation and dropdowns, and pull the colour scheme.</p>
        <div className="flex flex-wrap gap-2">
          <div className="flex-1 min-w-[240px] flex items-center gap-2 bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3">
            <Link2 size={14} className="text-[var(--dim)]" />
            <input data-testid="web-import-url-input" value={url} onChange={e => setUrl(e.target.value)} onKeyDown={e => e.key === "Enter" && scan()}
              placeholder="acmeplumbing.com" className="flex-1 bg-transparent py-3 text-sm outline-none" />
          </div>
          <div className="flex items-center gap-2 bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3">
            <span className="text-[11px] text-[var(--mut)]">Max pages</span>
            <input data-testid="web-import-maxpages-input" type="number" min={1} max={100} value={maxPages} onChange={e => setMaxPages(e.target.value)} className="w-14 bg-transparent py-3 text-sm font-mono outline-none" />
          </div>
          <button data-testid="web-import-discover-btn" onClick={discover} disabled={scanning || applying || !url.trim()} className="btn-primary flex items-center gap-2 disabled:opacity-50">
            {scanning ? <Loader2 size={14} className="animate-spin" /> : <Globe size={14} />}{scanning ? "Discovering…" : "Find pages"}
          </button>
          <button data-testid="web-import-scan-btn" onClick={scan} disabled={scanning || applying || !url.trim()} className="btn-ghost text-sm flex items-center gap-2 disabled:opacity-50">
            Crawl everything
          </button>
        </div>

        {(scanning || applying) && stage && <ImportProgress stage={stage} started={startedAt} testid="web-import-progress" />}

        {discovery && !preview && (
          <div data-testid="web-import-discovery" className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="overline">{discovery.totals.pages} pages found on {discovery.brand}</span>
              <span className="text-[11px] text-[var(--mut)]">{discovery.totals.images} images · {discovery.totals.forms} forms · {discovery.totals.videos} videos</span>
              <div className="ml-auto flex gap-1.5">
                <button data-testid="pick-important-btn" onClick={() => setPicked(Object.fromEntries(discovery.pages.map(p => [p.slug, p.important])))} className="btn-ghost !py-1.5 text-[11px]">Important only</button>
                <button data-testid="pick-all-btn" onClick={() => setPicked(Object.fromEntries(discovery.pages.map(p => [p.slug, true])))} className="btn-ghost !py-1.5 text-[11px]">Select all</button>
                <button data-testid="pick-none-btn" onClick={() => setPicked({})} className="btn-ghost !py-1.5 text-[11px]">Clear</button>
              </div>
            </div>
            <div className="card-surface p-3 max-h-72 overflow-y-auto scrollbar-thin space-y-1">
              {discovery.pages.map(p => (
                <label key={p.slug} data-testid={`discovery-page-${p.slug}`} className="flex items-center gap-2 text-sm py-1 cursor-pointer">
                  <input type="checkbox" data-testid={`discovery-check-${p.slug}`} checked={!!picked[p.slug]} onChange={e => setPicked({ ...picked, [p.slug]: e.target.checked })} className="accent-[var(--acc)]" />
                  <span className="truncate max-w-[45%]">{p.title}</span>
                  <span className="font-mono text-[11px] text-[var(--dim)] truncate">{p.slug}</span>
                  {p.important && <span className="chip chip-active text-[9px]" style={{ padding: "0 5px" }}>key</span>}
                  <span className="ml-auto font-mono text-[10px] text-[var(--mut)] whitespace-nowrap">{p.words}w · {p.images}img{p.forms ? ` · ${p.forms}form` : ""}{p.videos ? ` · ${p.videos}vid` : ""}</span>
                </label>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex card-surface !p-0.5 rounded-full">
                {[["replace", "Replace my pages"], ["append", "Add alongside"]].map(([k, l]) => (
                  <button key={k} data-testid={`discovery-mode-${k}`} onClick={() => setMode(k)} className={`px-4 py-2 rounded-full text-xs ${mode === k ? "bg-[var(--acc)]/15 text-[var(--acc)]" : "text-[var(--mut)]"}`}>{l}</button>
                ))}
              </div>
              <label className="flex items-center gap-2 text-xs text-[var(--mut)] cursor-pointer">
                <input type="checkbox" checked={applyTheme} onChange={e => setApplyTheme(e.target.checked)} className="accent-[var(--acc)]" /> Use their colours
              </label>
              <label className="flex items-center gap-2 text-xs text-[var(--mut)] cursor-pointer">
                <input data-testid="discovery-videos-toggle" type="checkbox" checked={sourceVideos} onChange={e => setSourceVideos(e.target.checked)} className="accent-[var(--acc)]" /> Add matching free videos
              </label>
              <button data-testid="discovery-import-btn" onClick={importSelected} disabled={applying} className="btn-primary ml-auto flex items-center gap-2 disabled:opacity-50">
                {applying ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} Import {Object.values(picked).filter(Boolean).length} page(s)
              </button>
            </div>
          </div>
        )}

        <div className="card-surface p-3">
          <div className="flex items-center gap-2 flex-wrap">
            <Upload size={13} className="text-[var(--acc)]" />
            <span className="text-sm">Import a ZIP package (HTML, CSS, images, assets)</span>
            <input ref={zipRef} data-testid="zip-import-input" type="file" accept=".zip" className="hidden" onChange={e => { importZip(e.target.files?.[0]); e.target.value = ""; }} />
            <button data-testid="zip-import-btn" onClick={() => zipRef.current?.click()} disabled={scanning || applying} className="btn-ghost text-xs !py-1.5 ml-auto flex items-center gap-1.5 disabled:opacity-50">
              {applying ? <Loader2 size={11} className="animate-spin" /> : <Upload size={11} />} Choose a .zip
            </button>
          </div>
        </div>

        <div className="card-surface p-3">
          <div className="flex items-center gap-2 flex-wrap">
            <Upload size={13} className="text-[var(--acc)]" />
            <span className="text-sm">Add your own images, videos or documents to use while building</span>
            <input ref={fileRef} data-testid="web-import-file-input" type="file" multiple accept="image/*,video/*,.pdf,.doc,.docx,.csv,.txt,.zip,.mp3,.wav" onChange={e => { addFiles(e.target.files); e.target.value = ""; }} className="hidden" />
            <button data-testid="web-import-upload-btn" onClick={() => fileRef.current?.click()} disabled={uploading} className="btn-ghost text-xs !py-1.5 ml-auto flex items-center gap-1.5 disabled:opacity-50">
              {uploading ? <Loader2 size={11} className="animate-spin" /> : <Upload size={11} />} {uploading ? "Uploading…" : "Choose files"}
            </button>
          </div>
          {uploads.length > 0 && (
            <div data-testid="web-import-uploads" className="mt-2 flex flex-wrap gap-2">
              {uploads.map(u => <span key={u.url} className="chip text-[10px] flex items-center gap-1">{u.type?.startsWith("video") ? "▶" : u.type?.startsWith("image") ? "🖼" : "📄"} {u.name}</span>)}
            </div>
          )}
        </div>

        {preview && (
          <div data-testid="web-import-preview" className="space-y-4 mt-2">
            <ImportReport report={preview.report} testid="web-import-report" />
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
                <div className="overline mb-2">Colour scheme</div>
                <div className="flex items-center gap-2 flex-wrap">
                  {[preview.theme?.primary, preview.theme?.secondary, preview.theme?.bg, preview.theme?.fg].filter(Boolean).map((c, i) => <span key={i} className="w-6 h-6 rounded-lg border border-white/15" style={{ background: c }} title={c} />)}
                  <span className="text-xs font-mono text-[var(--dim)]">{preview.theme?.mode} · {preview.theme?.font_heading}</span>
                </div>
                {preview.logo && <div className="mt-3 flex items-center gap-2 text-xs text-[var(--mut)]"><Check size={12} className="text-[var(--acc)]" /> Logo saved to library</div>}
              </div>
            </div>
            <div className="card-surface p-4">
              <div className="overline mb-2">Pages to create</div>
              <div className="space-y-2 max-h-56 overflow-y-auto scrollbar-thin">
                {preview.pages.map(p => (
                  <div key={p.slug} data-testid={`web-import-page-${p.slug}`} className="flex items-center gap-2 text-sm">
                    <Check size={13} className="text-[var(--acc)]" />
                    <span className="font-medium truncate">{p.name}</span>
                    <span className="font-mono text-[11px] text-[var(--dim)] truncate">{p.slug}</span>
                    <span className="ml-auto font-mono text-[11px] text-[var(--mut)] whitespace-nowrap">{p.blocks} sections{p.forms ? ` · ${p.forms} form${p.forms > 1 ? "s" : ""}` : ""}{p.images ? ` · ${p.images} img` : ""}</span>
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
                {applying ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}{applying ? "Applying…" : `Apply ${preview.pages.length} page(s)`}
              </button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
