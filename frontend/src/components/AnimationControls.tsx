import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Wand2 } from "lucide-react";
import api from "@/lib/api";
import { BOX_ANIMS, SECTIONS, animForTemplate, sectionAnimFor, durFor } from "@/lib/boxAnims";

/** Replays an entrance on three dummy boxes so a choice is obvious before it is saved. */
export function BoxAnimPreview({ anim, accent, speed = 1, stagger = 90 }) {
  const [n, setN] = useState(0);
  useEffect(() => { setN(v => v + 1); }, [anim, speed, stagger]);
  if (anim === "none") return <div className="mt-3 text-xs text-[var(--mut)]" data-testid="sm-boxanim-preview">Boxes appear instantly with no animation.</div>;
  return (
    <div className="mt-3" data-testid="sm-boxanim-preview" data-anim={anim}>
      <div className="grid grid-cols-3 gap-2">
        {[0, 1, 2].map(i => (
          <div key={`${anim}-${n}-${i}`}
            className={`cm-box cm-in cm-a-${anim} h-16 rounded-xl border border-[var(--line)] bg-[var(--bg-2)] flex items-center justify-center text-[10px] font-mono`}
            style={{ ["--cm-dur" as any]: `${Math.round(durFor(anim) / speed)}ms`, ["--cm-delay" as any]: `${i * stagger}ms`, color: accent }}>
            Box {i + 1}
          </div>
        ))}
      </div>
      <button data-testid="sm-boxanim-replay" onClick={() => setN(v => v + 1)}
        className="mt-2 chip cursor-pointer hover:!text-white">Play again</button>
    </div>
  );
}

/** Entrance animation, speed, stagger and per-section overrides for one client.
 *  Shared by the agency Site Mode panel and the client portal. */
export default function AnimationControls({ appId, accent = "#10B981", onSaved = () => {}, compact = false }) {
  const [sm, setSm] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [stagger, setStagger] = useState(90);

  useEffect(() => {
    if (!appId) return;
    api.get(`/apps/${appId}/site-mode`).then(({ data }) => {
      setSm(data); setSpeed(data.box_speed ?? 1); setStagger(data.box_stagger ?? 90);
    }).catch(() => {});
  }, [appId]);

  async function patch(next: any) {
    setBusy(true);
    try {
      const { data } = await api.put(`/apps/${appId}/site-mode`, next);
      setSm((s: any) => ({ ...s, ...data }));
      toast.success("Animation updated on the live site");
      onSaved();
    } catch (e: any) {
      if (e.response?.status === 429) {
        await new Promise(r => setTimeout(r, 1300));
        try {
          const { data } = await api.put(`/apps/${appId}/site-mode`, next);
          setSm((s: any) => ({ ...s, ...data }));
          toast.success("Animation updated on the live site");
          onSaved();
          return;
        } catch { /* fall through */ }
      }
      toast.error(e.response?.data?.detail || "Could not save the animation");
    } finally { setBusy(false); }
  }

  if (!sm) return (
    <div className="py-4 text-sm text-[var(--mut)] flex items-center gap-2" data-testid="animation-controls-loading">
      <Loader2 size={14} className="animate-spin" /> Loading animation settings…
    </div>
  );

  const tpl = sm.template_key || "";
  const siteAnim = sm.box_anim || animForTemplate(tpl);
  const secs = sm.box_anim_sections || {};
  const sel = "bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm outline-none focus:border-[var(--acc)]";

  return (
    <div className={compact ? "" : "py-4 border-b border-[var(--line)]"} data-testid="animation-controls">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold flex items-center gap-2"><Wand2 size={13} className="text-[var(--acc)]" /> Box entrance animation</div>
          <div className="text-xs text-[var(--mut)] mt-0.5">
            How every card, heading and text group enters as visitors scroll. Each template has its own by default.
          </div>
        </div>
        <select data-testid="sm-boxanim-select" value={sm.box_anim || ""} disabled={busy}
          onChange={e => patch({ box_anim: e.target.value })} className={sel}>
          <option value="">— inherit from template —</option>
          {BOX_ANIMS.map(a => <option key={a.key} value={a.key}>{a.label}</option>)}
        </select>
      </div>

      <BoxAnimPreview anim={siteAnim} accent={accent} speed={speed} stagger={stagger} />

      <div className="mt-4 grid sm:grid-cols-2 gap-4">
        <label className="block">
          <span className="overline flex items-center justify-between">Entrance speed <span className="font-mono text-[var(--acc)]">{speed.toFixed(2)}x</span></span>
          <input data-testid="sm-box-speed" type="range" min={0.5} max={2} step={0.05} value={speed}
            onChange={e => setSpeed(Number(e.target.value))}
            onMouseUp={() => patch({ box_speed: speed })} onTouchEnd={() => patch({ box_speed: speed })}
            className="w-full mt-1 accent-[var(--acc)] cursor-pointer" />
        </label>
        <label className="block">
          <span className="overline flex items-center justify-between">Stagger between boxes <span className="font-mono text-[var(--acc)]">{stagger}ms</span></span>
          <input data-testid="sm-box-stagger" type="range" min={0} max={200} step={5} value={stagger}
            onChange={e => setStagger(Number(e.target.value))}
            onMouseUp={() => patch({ box_stagger: stagger })} onTouchEnd={() => patch({ box_stagger: stagger })}
            className="w-full mt-1 accent-[var(--acc)] cursor-pointer" />
        </label>
      </div>

      <div className="mt-4">
        <div className="text-sm font-semibold">Per-section entrances</div>
        <div className="text-xs text-[var(--mut)] mt-0.5 mb-2">
          Give each section its own entrance, or leave it on inherit to follow the choice above.
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {SECTIONS.map(([key, label]) => (
            <label key={key} className="rounded-xl border border-[var(--line)] p-2.5" data-testid={`sm-section-row-${key}`}>
              <span className="block text-xs font-semibold mb-1.5">{label}</span>
              <select data-testid={`sm-section-anim-${key}`} value={secs[key] || ""} disabled={busy}
                onChange={e => patch({ box_anim_sections: { ...secs, [key]: e.target.value } })}
                className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2 py-1.5 text-xs outline-none focus:border-[var(--acc)]">
                <option value="">inherit · {sm.box_anim ? (BOX_ANIMS.find(a => a.key === sm.box_anim)?.label || sm.box_anim) : (BOX_ANIMS.find(a => a.key === sectionAnimFor(tpl, key))?.label || "template")}</option>
                {BOX_ANIMS.map(a => <option key={a.key} value={a.key}>{a.label}</option>)}
              </select>
            </label>
          ))}
        </div>
      </div>
      {busy && <div className="mt-2 text-xs text-[var(--mut)] flex items-center gap-2"><Loader2 size={12} className="animate-spin" /> Saving…</div>}
    </div>
  );
}
