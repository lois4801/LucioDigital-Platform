import { useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Image as ImageIcon, Mic, Film, Sparkles, KeyRound, Trash2, Download, Loader2, CheckCircle2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const MODES = [
  { key: "image", label: "Images", icon: ImageIcon, model: "GPT-Image-1", hint: "Hero visuals, ad creatives, product mockups" },
  { key: "voice", label: "Voiceover", icon: Mic, model: "ElevenLabs", hint: "Narration for demos, ads and explainers" },
  { key: "video", label: "Video", icon: Film, model: "fal.ai · Hailuo-02", hint: "6–10s cinematic marketing clips" },
];

const PRESETS = {
  image: ["Premium product hero shot on dark studio backdrop, emerald accent lighting", "Lifestyle photo of a founder using a SaaS dashboard on laptop, golden hour", "Minimal 3D abstract shapes for a fintech landing page"],
  voice: ["Welcome to the future of your business. Launch faster, scale smarter, and hand off with confidence.", "Introducing a platform built for agencies who ship."],
  video: ["Cinematic slow push-in on a glowing analytics dashboard in a dark modern office, soft emerald light", "A sleek mobile app floating in space with holographic UI, luxurious, ad quality"],
};

export default function MediaStudio({ appId }) {
  const [mode, setMode] = useState("image");
  const [cfg, setCfg] = useState(null);
  const [prompt, setPrompt] = useState("");
  const [assets, setAssets] = useState([]);
  const [busy, setBusy] = useState(false);
  const [voices, setVoices] = useState([]);
  const [voiceId, setVoiceId] = useState("21m00Tcm4TlvDq8ikWAM");
  const [duration, setDuration] = useState("6");
  const [keyOpen, setKeyOpen] = useState(false);
  const [keyVal, setKeyVal] = useState("");
  const [task, setTask] = useState(null);
  const poll = useRef(null);

  useEffect(() => { loadCfg(); loadAssets(); return () => clearInterval(poll.current); }, [appId]);
  useEffect(() => { if (cfg?.elevenlabs) loadVoices(); }, [cfg?.elevenlabs]);

  async function loadCfg() { try { const { data } = await api.get("/media/config"); setCfg(data); } catch {} }
  async function loadAssets() { try { const { data } = await api.get(`/apps/${appId}/media`); setAssets(data); } catch {} }
  async function loadVoices() { try { const { data } = await api.get("/media/voices"); setVoices(data); if (data[0]) setVoiceId(data[0].voice_id); } catch {} }

  async function saveKey() {
    setBusy(true);
    try { await api.post("/media/config/elevenlabs", { api_key: keyVal }); toast.success("ElevenLabs connected"); setKeyOpen(false); setKeyVal(""); loadCfg(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not save key"); }
    finally { setBusy(false); }
  }

  async function generate() {
    if (!prompt.trim()) return;
    setBusy(true);
    try {
      if (mode === "image") {
        const { data } = await api.post(`/apps/${appId}/media/image`, { prompt }, { timeout: 120000 });
        setAssets([data, ...assets]); toast.success("Image generated");
      } else if (mode === "voice") {
        const { data } = await api.post(`/apps/${appId}/media/voice`, { text: prompt, voice_id: voiceId }, { timeout: 120000 });
        setAssets([data, ...assets]); toast.success("Voiceover generated");
      } else {
        const { data } = await api.post(`/apps/${appId}/media/video`, { prompt, duration });
        setTask(data); toast.info("Video rendering started — usually 1–4 minutes");
        poll.current = setInterval(async () => {
          try {
            const { data: t } = await api.get(`/apps/${appId}/media/tasks/${data.task_id}`);
            setTask(t);
            if (t.status !== "running") { clearInterval(poll.current); loadAssets(); t.status === "done" ? toast.success("Video ready") : toast.error(t.error || "Video failed"); }
          } catch { clearInterval(poll.current); }
        }, 5000);
      }
      setPrompt("");
    } catch (e) { toast.error(e.response?.data?.detail || "Generation failed"); }
    finally { setBusy(false); }
  }

  async function remove(id) { await api.delete(`/apps/${appId}/media/${id}`); setAssets(assets.filter(a => a.asset_id !== id)); }

  const voiceLocked = mode === "voice" && cfg && !cfg.elevenlabs;
  const m = MODES.find(x => x.key === mode);

  return (
    <div data-testid="media-studio" className="grid lg:grid-cols-[300px_1fr] gap-6">
      <aside className="space-y-4">
        <div className="card-surface p-3">
          <div className="overline mb-2 px-1">Generator</div>
          {MODES.map(x => (
            <button key={x.key} data-testid={`media-mode-${x.key}-btn`} onClick={() => setMode(x.key)}
              className={`w-full flex items-start gap-3 px-3 py-3 rounded-xl text-left transition-colors ${mode === x.key ? "bg-[var(--acc)]/10 border border-[var(--acc)]/30" : "hover:bg-white/5 border border-transparent"}`}>
              <x.icon size={16} className="text-[var(--acc)] mt-0.5" />
              <div className="flex-1">
                <div className="text-sm font-semibold flex items-center gap-2">{x.label}
                  {x.key === "voice" && cfg && (cfg.elevenlabs
                    ? <CheckCircle2 size={12} className="text-[var(--acc)]" />
                    : <span className="chip chip-maint" style={{ padding: "1px 6px" }}>Key needed</span>)}
                </div>
                <div className="text-[11px] text-[var(--mut)] mt-0.5">{x.hint}</div>
                <div className="font-mono text-[10px] text-[var(--dim)] mt-1">{x.model}</div>
              </div>
            </button>
          ))}
        </div>

        <div className={`card-surface p-4 ${cfg && !cfg.elevenlabs ? "!border-amber-500/50 shadow-[0_0_30px_-10px_rgba(245,158,11,0.5)]" : ""}`}>
          <div className="overline mb-2 flex items-center gap-2"><KeyRound size={12} className="text-amber-400" /> ElevenLabs</div>
          {cfg?.elevenlabs ? (
            <div className="text-sm text-[var(--acc)] flex items-center gap-2"><CheckCircle2 size={14} /> Connected</div>
          ) : (
            <>
              <p className="text-xs text-[var(--mut)]">Add your ElevenLabs API key to unlock studio-grade voiceovers.</p>
              <button data-testid="connect-elevenlabs-btn" onClick={() => setKeyOpen(true)}
                className="mt-3 w-full rounded-full bg-amber-400 text-black font-semibold text-sm py-2.5 hover:bg-amber-300 transition-colors animate-pulse hover:animate-none">
                Add ElevenLabs key
              </button>
            </>
          )}
          {cfg?.elevenlabs && <button data-testid="replace-elevenlabs-btn" onClick={() => setKeyOpen(true)} className="mt-2 text-xs text-[var(--mut)] hover:text-white underline">Replace key</button>}
        </div>
      </aside>

      <div className="space-y-6">
        <div className="card-surface p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="overline flex items-center gap-2"><Sparkles size={12} className="text-[var(--acc)]" /> {m.label} prompt</div>
            <div className="flex gap-2">
              {mode === "voice" && voices.length > 0 && (
                <select data-testid="voice-select" value={voiceId} onChange={e => setVoiceId(e.target.value)}
                  className="bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2 py-1 text-xs font-mono outline-none">
                  {voices.map(v => <option key={v.voice_id} value={v.voice_id}>{v.name}</option>)}
                </select>
              )}
              {mode === "video" && (
                <select data-testid="video-duration-select" value={duration} onChange={e => setDuration(e.target.value)}
                  className="bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2 py-1 text-xs font-mono outline-none">
                  <option value="6">6 seconds</option><option value="10">10 seconds</option>
                </select>
              )}
            </div>
          </div>
          <textarea data-testid="media-prompt-input" value={prompt} onChange={e => setPrompt(e.target.value)} rows={4}
            placeholder={mode === "voice" ? "Script to narrate…" : "Describe the visual you want…"}
            className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-4 py-3 text-sm outline-none focus:border-[var(--acc)] resize-none" />
          <div className="flex flex-wrap gap-2 mt-3">
            {PRESETS[mode].map((p, i) => (
              <button key={i} data-testid={`media-preset-${i}`} onClick={() => setPrompt(p)} className="chip cursor-pointer hover:!text-white normal-case tracking-normal !text-[11px]">{p.slice(0, 48)}…</button>
            ))}
          </div>
          <div className="flex items-center justify-between mt-4">
            <div className="text-xs text-[var(--mut)] font-mono">{mode === "image" ? "~30–60s · billed to Universal Key" : mode === "video" ? "~1–4 min · billed to Universal Key" : "~5s · billed to your ElevenLabs plan"}</div>
            <button data-testid="media-generate-btn" onClick={voiceLocked ? () => setKeyOpen(true) : generate} disabled={busy || !prompt.trim()}
              className="btn-primary text-sm flex items-center gap-2 !py-2.5 !px-5 disabled:opacity-50">
              {busy ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
              {voiceLocked ? "Connect ElevenLabs to generate" : busy ? "Generating…" : `Generate ${m.label.toLowerCase()}`}
            </button>
          </div>
          {task && task.status === "running" && (
            <div data-testid="video-task-status" className="mt-4 p-3 rounded-xl bg-[var(--bg-2)] border border-[var(--line)] flex items-center gap-3 text-sm">
              <Loader2 size={14} className="animate-spin text-[var(--acc)]" /> Rendering “{task.prompt.slice(0, 60)}”… <span className="font-mono text-xs text-[var(--mut)] ml-auto">{task.task_id}</span>
            </div>
          )}
          {task && task.status === "failed" && <div className="mt-4 text-sm text-red-400 font-mono">✕ {task.error}</div>}
        </div>

        <div>
          <div className="overline mb-3">Asset library · {assets.length}</div>
          {assets.length === 0 ? (
            <div className="card-surface p-12 text-center text-[var(--mut)] text-sm">Generated images, voiceovers and videos will appear here.</div>
          ) : (
            <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {assets.map(a => (
                <div key={a.asset_id} data-testid={`media-asset-${a.kind}`} className="card-surface overflow-hidden group">
                  {a.kind === "image" && <img src={a.data_url} alt={a.prompt} className="w-full aspect-square object-cover" />}
                  {a.kind === "video" && <video src={a.url} controls className="w-full aspect-video bg-black" />}
                  {a.kind === "voice" && <div className="p-4 bg-[var(--bg-2)]"><audio src={a.data_url} controls className="w-full" /></div>}
                  <div className="p-3 flex items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="chip" style={{ padding: "1px 6px" }}>{a.kind}</div>
                      <div className="text-xs text-[var(--mut)] mt-1.5 line-clamp-2">{a.prompt}</div>
                    </div>
                    <a href={a.data_url || a.url} download target="_blank" rel="noreferrer" className="p-1.5 text-[var(--mut)] hover:text-white"><Download size={13} /></a>
                    <button onClick={() => remove(a.asset_id)} className="p-1.5 text-[var(--mut)] hover:text-red-400"><Trash2 size={13} /></button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <Dialog open={keyOpen} onOpenChange={setKeyOpen}>
        <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)]">
          <DialogHeader><DialogTitle className="font-display">Connect ElevenLabs</DialogTitle></DialogHeader>
          <p className="text-sm text-[var(--mut)]">Paste an API key from <a className="text-[var(--acc)] underline" href="https://elevenlabs.io/app/settings/api-keys" target="_blank" rel="noreferrer">elevenlabs.io → Settings → API keys</a>. It's stored server-side and never exposed to clients.</p>
          <input data-testid="elevenlabs-key-input" type="password" value={keyVal} onChange={e => setKeyVal(e.target.value)} placeholder="sk_…"
            className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm font-mono outline-none focus:border-[var(--acc)]" />
          <button data-testid="elevenlabs-key-save-btn" onClick={saveKey} disabled={busy || keyVal.length < 10} className="btn-primary w-full disabled:opacity-50">{busy ? "Verifying…" : "Save & verify key"}</button>
        </DialogContent>
      </Dialog>
    </div>
  );
}
