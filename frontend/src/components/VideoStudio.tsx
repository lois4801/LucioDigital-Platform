import { useState, useEffect, useRef } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Video, Sparkles, Loader2, Download, Wand2, Upload, ExternalLink, PlusCircle } from "lucide-react";

export default function VideoStudio({ appId, appDoc }) {
  const [state, setState] = useState({ videos: [], stock_enabled: false, providers: {}, ai_models: [], ai_enabled: false });
  const [busy, setBusy] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState("veo3.1");
  const [aspect, setAspect] = useState("16:9");
  const fileRef = useRef(null);

  async function load() { try { const { data } = await api.get(`/apps/${appId}/videos`); setState(data); setModel(data.ai_models?.[0]?.id || "veo3.1"); } catch { } }
  useEffect(() => { load(); }, [appId]);

  async function autoSource() {
    setBusy("auto");
    try {
      const { data } = await api.post(`/apps/${appId}/videos/auto-source`, { query: query || undefined, count: 2, place: true }, { timeout: 300000 });
      toast.success(`${data.saved.length} free video(s) added for "${data.query}"${data.placed ? ` and placed on ${data.placed.page_slug}` : ""}`);
      if (data.failures?.length) toast.info(`${data.failures.length} skipped — see the library for what saved`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Sourcing failed"); } finally { setBusy(""); }
  }

  async function search() {
    setBusy("search");
    try { const { data } = await api.get(`/apps/${appId}/videos/stock-search`, { params: { q: query || undefined } }); setResults(data.results); if (!data.results.length) toast.info("No matches — try another keyword"); }
    catch (e) { toast.error(e.response?.data?.detail || "Search failed"); } finally { setBusy(""); }
  }

  async function importOne(v, place) {
    setBusy(`import-${v.provider_id}`);
    try {
      await api.post(`/apps/${appId}/videos/import-one`, { provider: v.provider, download_url: v.download_url, title: v.title, source_url: v.source_url, contributor: v.contributor, place }, { timeout: 300000 });
      toast.success(place ? "Saved and placed on the site" : "Saved to the media library");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Import failed"); } finally { setBusy(""); }
  }

  async function generate() {
    setBusy("ai");
    try {
      const { data: job } = await api.post(`/apps/${appId}/videos/ai-generate`, { prompt: prompt || undefined, model, aspect_ratio: aspect, place: true });
      toast.info(`${job.model} is rendering — this usually takes 1-3 minutes`);
      for (let i = 0; i < 120; i++) {
        await new Promise(r => setTimeout(r, 5000));
        const { data } = await api.get(`/apps/${appId}/videos/job/${job.job_id}`);
        if (data.status === "done") { toast.success("AI video ready and placed on the site"); load(); break; }
        if (data.status === "error") { toast.error(data.error || "Generation failed"); break; }
      }
    } catch (e) { toast.error(e.response?.data?.detail || "Generation failed"); } finally { setBusy(""); }
  }

  async function upload(files) {
    if (!files?.length) return;
    setBusy("upload");
    for (const f of Array.from(files)) {
      const fd = new FormData(); fd.append("file", f);
      try { await api.post(`/apps/${appId}/files`, fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 600000 }); }
      catch (e) { toast.error(`${f.name}: ${e.response?.data?.detail || "upload failed"}`); }
    }
    setBusy(""); toast.success("Uploaded to the media library"); load();
  }

  async function place(v) {
    setBusy(`place-${v.file_id}`);
    try { const { data } = await api.post(`/apps/${appId}/videos/place`, { url: v.url, heading: `${appDoc?.name || "We"} in action` }); toast.success(`Placed on ${data.page_slug}`); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not place it"); } finally { setBusy(""); }
  }

  return (
    <div className="space-y-6" data-testid="video-studio">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <h2 className="font-display text-2xl font-bold">Video Studio</h2>
          <p className="text-sm text-[var(--mut)] mt-1">Source free niche-matched videos, generate one with AI, or upload your own — then drop them straight onto the site.</p>
        </div>
        <input ref={fileRef} data-testid="video-upload-input" type="file" multiple accept="video/*" className="hidden" onChange={e => { upload(e.target.files); e.target.value = ""; }} />
        <button data-testid="video-upload-btn" onClick={() => fileRef.current?.click()} disabled={!!busy} className="btn-ghost text-sm flex items-center gap-2 ml-auto disabled:opacity-50">
          {busy === "upload" ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />} Upload my videos
        </button>
      </div>

      <div className="card-surface p-5 space-y-3">
        <div className="flex items-center gap-2"><Download size={14} className="text-[var(--acc)]" /><span className="overline">Free stock videos</span>
          {!state.stock_enabled && <span className="chip text-[10px] ml-auto">Add a Pexels or Pixabay API key to enable</span>}
        </div>
        <div className="flex flex-wrap gap-2">
          <input data-testid="video-query-input" value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === "Enter" && search()}
            placeholder={appDoc?.site_niche || appDoc?.industry || "plumbing service van"}
            className="flex-1 min-w-[220px] bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-3 text-sm outline-none focus:border-[var(--acc)]" />
          <button data-testid="video-search-btn" onClick={search} disabled={!state.stock_enabled || !!busy} className="btn-ghost text-sm disabled:opacity-50">{busy === "search" ? <Loader2 size={14} className="animate-spin" /> : "Search"}</button>
          <button data-testid="video-auto-btn" onClick={autoSource} disabled={!state.stock_enabled || !!busy} className="btn-primary text-sm flex items-center gap-2 disabled:opacity-50">
            {busy === "auto" ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} Auto-source & place
          </button>
        </div>
        {results.length > 0 && (
          <div data-testid="video-results" className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-2">
            {results.map(v => (
              <div key={`${v.provider}-${v.provider_id}`} data-testid={`video-result-${v.provider_id}`} className="rounded-xl overflow-hidden border border-[var(--line)] bg-[var(--bg-2)]">
                {v.thumb ? <img src={v.thumb} alt={v.title} className="w-full h-32 object-cover" /> : <div className="w-full h-32 grid place-items-center text-[var(--dim)]"><Video size={20} /></div>}
                <div className="p-3 space-y-2">
                  <div className="text-xs truncate">{v.title || "Stock video"}</div>
                  <div className="text-[10px] text-[var(--dim)] flex items-center gap-1">{v.provider} · {v.duration}s · {v.contributor}
                    {v.source_url && <a href={v.source_url} target="_blank" rel="noreferrer" className="ml-auto hover:text-[var(--acc)]"><ExternalLink size={11} /></a>}</div>
                  <div className="flex gap-1.5">
                    <button data-testid={`video-save-${v.provider_id}`} onClick={() => importOne(v, false)} disabled={!!busy} className="btn-ghost !py-1.5 text-[11px] flex-1 disabled:opacity-50">{busy === `import-${v.provider_id}` ? "…" : "Save"}</button>
                    <button data-testid={`video-place-${v.provider_id}`} onClick={() => importOne(v, true)} disabled={!!busy} className="btn-primary !py-1.5 text-[11px] flex-1 disabled:opacity-50">Save & place</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card-surface p-5 space-y-3">
        <div className="flex items-center gap-2"><Wand2 size={14} className="text-[var(--acc)]" /><span className="overline">Create a video with AI</span>
          <span className="chip text-[10px] ml-auto">Billed from your Universal Key balance</span></div>
        <textarea data-testid="video-prompt-input" value={prompt} onChange={e => setPrompt(e.target.value)} rows={3}
          placeholder={`Leave blank to auto-write a brand film for ${appDoc?.name || "this business"}`}
          className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-3 text-sm outline-none focus:border-[var(--acc)]" />
        <div className="flex flex-wrap gap-2 items-center">
          <select data-testid="video-model-select" value={model} onChange={e => setModel(e.target.value)} className="bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-xs outline-none">
            {state.ai_models.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
          <div className="flex card-surface !p-0.5 rounded-full">
            {["16:9", "9:16"].map(a => <button key={a} data-testid={`video-aspect-${a.replace(":", "-")}`} onClick={() => setAspect(a)} className={`px-3 py-1.5 rounded-full text-[11px] ${aspect === a ? "bg-[var(--acc)]/15 text-[var(--acc)]" : "text-[var(--mut)]"}`}>{a}</button>)}
          </div>
          <button data-testid="video-generate-btn" onClick={generate} disabled={!state.ai_enabled || !!busy} className="btn-primary text-sm flex items-center gap-2 ml-auto disabled:opacity-50">
            {busy === "ai" ? <Loader2 size={14} className="animate-spin" /> : <Wand2 size={14} />}{busy === "ai" ? "Rendering (1-3 min)…" : "Generate video"}
          </button>
        </div>
      </div>

      <div>
        <div className="overline mb-3">This tenant's videos ({state.videos.length})</div>
        {state.videos.length === 0 ? <div className="card-surface p-8 text-center text-sm text-[var(--mut)]">No videos yet — auto-source, generate or upload one.</div> : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="video-library">
            {state.videos.map(v => (
              <div key={v.file_id} data-testid={`video-item-${v.file_id}`} className="rounded-xl overflow-hidden border border-[var(--line)] bg-[var(--bg-2)]">
                <video src={v.url} controls preload="metadata" className="w-full h-40 object-cover bg-black" />
                <div className="p-3 space-y-2">
                  <div className="text-xs truncate">{v.original_filename}</div>
                  <div className="text-[10px] text-[var(--dim)]">{v.uploaded_by} · {(v.size / 1048576).toFixed(1)} MB{v.contributor ? ` · ${v.contributor}` : ""}</div>
                  <button data-testid={`video-place-btn-${v.file_id}`} onClick={() => place(v)} disabled={!!busy} className="btn-ghost !py-1.5 text-[11px] w-full flex items-center justify-center gap-1.5 disabled:opacity-50">
                    <PlusCircle size={11} /> Place on the site
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
