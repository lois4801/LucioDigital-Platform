import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, RotateCcw } from "lucide-react";
import api from "@/lib/api";
import MarqueeRibbon from "@/components/editorial/MarqueeRibbon";

/** Text ribbon editor: phrases, scroll speed, outline opacity and size. Saves straight to the live site. */
export default function MarqueeEditor({ appId, accent = "#10B981", mode = "dark", onSaved = () => {} }) {
  const [d, setD] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!appId) return;
    api.get(`/apps/${appId}/marquee`).then(r => setD(r.data)).catch(() => toast.error("Could not load the text ribbon"));
  }, [appId]);

  const set = (p: any) => setD((s: any) => ({ ...s, ...p }));

  async function save(p: any = null) {
    const payload = p || {
      top_text: d.top_text, bottom_text: d.bottom_text,
      speed: d.speed, stroke_opacity: d.stroke_opacity, font_size: d.font_size, enabled: d.enabled,
    };
    setBusy(true);
    try {
      const { data } = await api.put(`/apps/${appId}/marquee`, payload);
      setD(data);
      onSaved();
      toast.success("Text ribbon updated on the live site");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not save the text ribbon");
    } finally { setBusy(false); }
  }

  async function reset() {
    setBusy(true);
    try {
      const { data } = await api.post(`/apps/${appId}/marquee/reset`);
      setD(data);
      onSaved();
      toast.success("Template ribbon restored");
    } catch { toast.error("Could not restore the template ribbon"); }
    finally { setBusy(false); }
  }

  if (!d) return null;

  const slider = (key: string, label: string, min: number, max: number, step: number, fmt: (v: number) => string) => (
    <div>
      <div className="flex items-center justify-between text-xs text-[var(--mut)]">
        <span>{label}</span><span className="font-mono" style={{ color: accent }}>{fmt(d[key])}</span>
      </div>
      <input type="range" data-testid={`marquee-${key}`} min={min} max={max} step={step} value={d[key]}
        onChange={e => set({ [key]: Number(e.target.value) })}
        onMouseUp={e => save({ [key]: Number((e.target as HTMLInputElement).value) })}
        onTouchEnd={e => save({ [key]: Number((e.target as HTMLInputElement).value) })}
        className="w-full mt-1.5 accent-[var(--acc)] cursor-pointer" />
    </div>
  );

  return (
    <div className="py-4 border-b border-[var(--line)]" data-testid="marquee-editor-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold">Text ribbon</div>
          <div className="text-xs text-[var(--mut)] mt-0.5">Two looping outline-text bands: one under the hero, one before the closing CTA.</div>
        </div>
        <div className="flex items-center gap-2">
          <button data-testid="marquee-enabled-toggle" onClick={() => save({ enabled: !d.enabled })}
            className={`chip cursor-pointer ${d.enabled ? "chip-active" : ""}`}>{d.enabled ? "Showing" : "Hidden"}</button>
          <button data-testid="marquee-reset-btn" onClick={reset} disabled={busy}
            className="chip cursor-pointer flex items-center gap-1 hover:!text-white"><RotateCcw size={11} /> Reset</button>
          {busy && <Loader2 size={13} className="animate-spin text-[var(--mut)]" />}
        </div>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {[["top_text", "Top ribbon text"], ["bottom_text", "Bottom ribbon text"]].map(([k, label]) => (
          <div key={k}>
            <div className="text-xs text-[var(--mut)] mb-1">{label}</div>
            <input data-testid={`marquee-${k}`} value={d[k] || ""} maxLength={160}
              onChange={e => set({ [k]: e.target.value })} onBlur={() => save({ [k]: d[k] || "" })}
              onKeyDown={e => { if (e.key === "Enter") save({ [k]: d[k] || "" }); }}
              className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]" />
          </div>
        ))}
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        {slider("speed", "Scroll speed", 0.2, 3, 0.1, v => `${v.toFixed(1)}x`)}
        {slider("stroke_opacity", "Outline opacity", 0.05, 1, 0.05, v => `${Math.round(v * 100)}%`)}
        {slider("font_size", "Font size", 0.5, 2.5, 0.1, v => `${v.toFixed(1)}x`)}
      </div>

      <div className="mt-4 rounded-2xl overflow-hidden border border-[var(--line)]" data-testid="marquee-editor-preview">
        <MarqueeRibbon text={d.top_text} accent={accent} speed={d.speed} strokeOpacity={d.stroke_opacity}
          fontSize={Math.min(0.6, d.font_size * 0.35)} mode={mode} testid="marquee-preview-ribbon" />
      </div>
    </div>
  );
}
