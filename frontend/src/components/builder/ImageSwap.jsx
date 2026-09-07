import { useRef, useState } from "react";
import { toast } from "sonner";
import { ImagePlus, Sparkles, Link2, Loader2, Upload } from "lucide-react";
import api from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

// Hover overlay rendered on top of any canvas image; calls onSwap() to open the picker.
export function SwapOverlay({ onSwap, testid }) {
  return (
    <button type="button" data-testid={testid} onClick={(e) => { e.stopPropagation(); onSwap(); }} title="Replace image"
      className="absolute inset-0 z-10 flex items-center justify-center bg-black/0 hover:bg-black/45 opacity-0 hover:opacity-100 transition-[opacity,background-color] duration-200 cursor-pointer">
      <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold text-white border border-white/30 bg-black/60 backdrop-blur"><ImagePlus size={12} /> Replace image</span>
    </button>
  );
}

export function ImageSwapDialog({ appId, target, onClose, onApply, context }) {
  const ref = useRef(null);
  const [tab, setTab] = useState("upload");
  const [busy, setBusy] = useState(false);
  const [prompt, setPrompt] = useState(`${context || "brand"} marketing visual, premium, natural light`);
  const [url, setUrl] = useState("");
  const abs = (u) => (u?.startsWith("/api/") ? `${process.env.REACT_APP_BACKEND_URL}${u}` : u);

  async function upload(file) {
    if (!file) return;
    const fd = new FormData(); fd.append("file", file); setBusy(true);
    try { const { data } = await api.post(`/apps/${appId}/media/upload`, fd, { headers: { "Content-Type": "multipart/form-data" } }); onApply(data.url); toast.success("Image replaced"); }
    catch (e) { toast.error(e.response?.data?.detail || "Upload failed"); } finally { setBusy(false); }
  }
  async function generate() {
    setBusy(true);
    try { const { data } = await api.post(`/apps/${appId}/media/image`, { prompt, style: "website" }, { timeout: 180000 }); onApply(data.data_url); toast.success("AI image applied"); }
    catch (e) { toast.error(e.response?.data?.detail || "Generation failed"); } finally { setBusy(false); }
  }
  return (
    <Dialog open={!!target} onOpenChange={o => !o && onClose()}>
      <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)] max-w-lg" data-testid="image-swap-dialog">
        <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><ImagePlus size={15} className="text-[var(--acc)]" /> Replace image</DialogTitle></DialogHeader>
        {target?.current && <img src={abs(target.current)} alt="" className="w-full aspect-[16/7] object-cover rounded-xl border border-[var(--line)]" />}
        <div className="flex gap-1 border-b border-[var(--line)]">
          {[["upload", Upload, "Upload"], ["ai", Sparkles, "Generate with AI"], ["url", Link2, "Paste URL"]].map(([k, I, l]) => <button key={k} data-testid={`swap-tab-${k}`} onClick={() => setTab(k)} className={`px-3 py-2 text-xs flex items-center gap-1.5 border-b-2 -mb-px ${tab === k ? "border-[var(--acc)] text-white" : "border-transparent text-[var(--mut)]"}`}><I size={12} /> {l}</button>)}
        </div>
        {tab === "upload" && <div className="text-center py-6 rounded-xl border border-dashed border-[var(--line)]">
          <input ref={ref} type="file" accept=".png,.jpg,.jpeg,.svg,.webp,.gif" className="hidden" data-testid="swap-file-input" onChange={e => upload(e.target.files?.[0])} />
          <button data-testid="swap-upload-btn" onClick={() => ref.current?.click()} disabled={busy} className="btn-primary text-sm inline-flex items-center gap-2">{busy ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />} Choose image</button>
          <div className="text-[11px] text-[var(--mut)] mt-2">PNG, JPG, SVG, WEBP · up to 8 MB</div></div>}
        {tab === "ai" && <div className="space-y-2">
          <textarea data-testid="swap-ai-prompt" rows={3} value={prompt} onChange={e => setPrompt(e.target.value)} className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--acc)]" />
          <button data-testid="swap-ai-generate-btn" onClick={generate} disabled={busy || !prompt.trim()} className="btn-primary text-sm inline-flex items-center gap-2">{busy ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} Generate & apply</button>
          <div className="text-[11px] text-[var(--mut)]">Takes ~20–40s. Uses your AI Media credits.</div></div>}
        {tab === "url" && <form className="flex gap-2" onSubmit={e => { e.preventDefault(); if (url.trim()) { onApply(url.trim()); toast.success("Image replaced"); } }}>
          <input data-testid="swap-url-input" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://images.unsplash.com/…" className="flex-1 bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm font-mono outline-none focus:border-[var(--acc)]" />
          <button data-testid="swap-url-apply-btn" type="submit" className="btn-primary text-sm">Apply</button></form>}
      </DialogContent>
    </Dialog>
  );
}
