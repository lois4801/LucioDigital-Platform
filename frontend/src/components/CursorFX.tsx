import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { Sparkles, Check, RotateCcw, Sliders } from "lucide-react";
import CursorTrail from "@/components/CursorTrail";
import { CURSOR_EFFECTS, DEFAULT_DENSITY, DEFAULT_EFFECT, DEFAULT_SPEED, isEffect, startCursorFX } from "@/lib/cursorEffects";

const clamp = (v, d = 1) => { const n = Number(v); return Number.isFinite(n) ? Math.max(0, Math.min(2, n)) : d; };
const Ctx = createContext(null);

export function CursorFXProvider({ children }) {
  // Session-only state: every page load starts on the platform defaults (Fairy Dust · 0.9× · 0.4×)
  // and the choice then survives in-app navigation until the visitor refreshes.
  const [saved, setSaved] = useState(DEFAULT_EFFECT);
  const [density, setDensity] = useState(DEFAULT_DENSITY);
  const [speed, setSpeed] = useState(DEFAULT_SPEED);
  const [preview, setPreview] = useState(null);   // hover preview in the picker
  const [override, setOverride] = useState(null); // per-tenant site override

  const choose = useCallback((id) => {
    if (!isEffect(id)) return;
    setSaved(id); setPreview(null);
  }, []);

  const setIntensity = useCallback((d, s) => {
    setDensity(clamp(d, DEFAULT_DENSITY)); setSpeed(clamp(s, DEFAULT_SPEED));
  }, []);

  const effect = preview || override?.effect || saved;
  const intensity = override ? { density: clamp(override.density), speed: clamp(override.speed) } : { density, speed };

  return (
    <Ctx.Provider value={{ effect, saved, density, speed, choose, setIntensity, setPreview, setOverride }}>
      {children}
      <CursorFXLayer effect={effect} density={intensity.density} speed={intensity.speed} />
    </Ctx.Provider>
  );
}

export function useCursorFX() {
  return useContext(Ctx) || { effect: "none", saved: "none", density: 1, speed: 1, choose: () => {}, setIntensity: () => {}, setPreview: () => {}, setOverride: () => {} };
}

// Applies a site/tenant effect for as long as the calling page is mounted.
export function useTenantCursorFX(effectId, density = 1, speed = 1) {
  const { setOverride } = useCursorFX();
  useEffect(() => {
    setOverride(isEffect(effectId) ? { effect: effectId, density, speed } : null);
    return () => setOverride(null);
  }, [effectId, density, speed, setOverride]);
}

function CursorFXLayer({ effect, density, speed }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current || effect === "none") return;
    if (window.matchMedia("(pointer: coarse)").matches) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    return startCursorFX(ref.current, effect, "#10B981", { density, speed });
  }, [effect, density, speed]);
  if (effect === "none") return null;
  return <canvas ref={ref} data-testid="cursor-fx-canvas" data-effect={effect} data-density={density} data-speed={speed}
    className="fixed inset-0 z-[105] pointer-events-none" />;
}

/** CORE PLATFORM UI — DO NOT REMOVE.
 *  The cursor effect picker lives at the application root as a fixed overlay, so no landing page
 *  edit, section change or redesign can drop it. It is deliberately NOT part of any page layout.
 *  Hidden only on client-facing public sites (/p/, /site/), which carry the client's own branding. */
export function GlobalCursorFX() {
  const { pathname } = useLocation();
  const onClientSite = pathname.startsWith("/p/") || pathname.startsWith("/site/") || pathname.startsWith("/compare/");
  const onLanding = pathname === "/" || pathname === "/classic-landing";   // the landing nav bar carries its own
  if (onClientSite || onLanding) return null;
  return (
    <div data-testid="global-cursor-fx" className="fixed bottom-5 right-5 z-[100] print:hidden">
      <CursorFXPicker up />
    </div>
  );
}

// Base dot + ring take their colour from the active cursor effect.
export function CursorTrailThemed() {
  const { effect } = useCursorFX();
  const e = CURSOR_EFFECTS.find(x => x.id === effect);
  const [dot] = e && e.id !== "none" ? e.swatch : ["#10B981"];
  return <CursorTrail color={dot} />;
}

// Horizontal top strip — fits mobile/tablet widths without any overflowing dropdown.
export function CursorFXBar() {
  const { saved, effect, density, speed, choose, setIntensity, setPreview } = useCursorFX();
  const [tune, setTune] = useState(false);
  return (
    <div data-testid="cursor-fx-bar" className="w-full rounded-2xl border border-[var(--line)] bg-[var(--card)]/70 backdrop-blur-md p-2">
      <div className="flex items-center gap-2">
        <Sparkles size={14} className={saved === "none" ? "text-[var(--mut)] shrink-0" : "text-[var(--acc)] shrink-0"} />
        <div className="overline shrink-0 hidden sm:block">Cursor</div>
        <div className="flex-1 min-w-0 flex items-center gap-1.5 overflow-x-auto scrollbar-thin py-0.5"
          onMouseLeave={() => setPreview(null)}>
          {CURSOR_EFFECTS.map(e => (
            <button key={e.id} data-testid={`cursor-fx-option-${e.id}`} title={`${e.name} · ${e.hint}`}
              onMouseEnter={() => setPreview(e.id === "none" ? null : e.id)}
              onClick={() => choose(e.id)}
              className={`relative shrink-0 w-8 h-8 rounded-full border transition-transform hover:scale-110 ${effect === e.id ? "border-[var(--acc)]" : "border-white/10"}`}
              style={{ background: `linear-gradient(135deg, ${e.swatch[0]}, ${e.swatch[1]})` }}>
              {saved === e.id && <Check size={12} className="absolute inset-0 m-auto text-black/80" />}
            </button>
          ))}
        </div>
        <button data-testid="cursor-fx-tune-btn" onClick={() => setTune(t => !t)} title="Intensity"
          className="shrink-0 w-8 h-8 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-white/5">
          <Sliders size={13} className="text-[var(--mut)]" />
        </button>
      </div>
      {tune && (
        <div className="grid grid-cols-2 gap-2 pt-2 mt-2 border-t border-[var(--line)]">
          <label className="block">
            <span className="flex justify-between text-[10px] text-[var(--mut)]"><span>Thickness</span><span className="font-mono">{density.toFixed(1)}×</span></span>
            <input data-testid="cursor-fx-density-slider" type="range" min={0.2} max={3} step={0.1} value={density}
              onChange={e => setIntensity(Number(e.target.value), speed)} className="w-full accent-[var(--acc)]" />
          </label>
          <label className="block">
            <span className="flex justify-between text-[10px] text-[var(--mut)]"><span>Speed</span><span className="font-mono">{speed.toFixed(1)}×</span></span>
            <input data-testid="cursor-fx-speed-slider" type="range" min={0.2} max={3} step={0.1} value={speed}
              onChange={e => setIntensity(density, Number(e.target.value))} className="w-full accent-[var(--acc)]" />
          </label>
          <button data-testid="cursor-fx-intensity-reset-btn" onClick={() => setIntensity(DEFAULT_DENSITY, DEFAULT_SPEED)}
            className="btn-ghost text-[11px] !py-1 !px-2.5 flex items-center gap-1.5 w-fit"><RotateCcw size={11} /> Reset</button>
        </div>
      )}
    </div>
  );
}

export function CursorFXPicker({ up = false, label = false, testid = "cursor-fx-picker-btn" }) {
  const { saved, effect, density, speed, choose, setIntensity, setPreview } = useCursorFX();
  const [open, setOpen] = useState(false);
  const box = useRef(null);
  useEffect(() => {
    if (!open) return;
    const h = (e) => { if (box.current && !box.current.contains(e.target)) { setOpen(false); setPreview(null); } };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open, setPreview]);

  const active = CURSOR_EFFECTS.find(e => e.id === saved) || CURSOR_EFFECTS[0];
  const Slider = ({ label: text, value, testid: tid, onChange }) => (
    <label className="block px-2 py-1.5">
      <span className="flex justify-between text-[11px] text-[var(--mut)]"><span>{text}</span><span className="font-mono">{value.toFixed(1)}×</span></span>
      <input data-testid={tid} type="range" min={0} max={2} step={0.1} value={value}
        onChange={e => onChange(Number(e.target.value))} className="w-full accent-[var(--acc)]" />
    </label>
  );

  return (
    <div className="relative" ref={box}>
      {label ? (
        <button data-testid={testid} title={`Cursor effect · ${active.name}`} onClick={() => setOpen(o => !o)}
          className="flex items-center gap-2 rounded-full border border-white/12 bg-white/[0.04] px-3.5 py-1.5 text-xs font-medium hover:border-[var(--acc)]/60 hover:bg-white/[0.08] transition-colors">
          <Sparkles size={13} className={saved === "none" ? "text-[var(--mut)]" : "text-[var(--acc)]"} />
          <span className="whitespace-nowrap" data-testid="cursor-fx-active-name">{active.name}</span>
        </button>
      ) : (
        <button data-testid={testid} title={`Cursor effect · ${active.name}`} onClick={() => setOpen(o => !o)}
          className="w-10 h-10 rounded-full border border-[var(--line)] bg-[var(--card)]/85 backdrop-blur-md shadow-lg flex items-center justify-center hover:bg-white/10 transition-colors relative">
          <Sparkles size={16} className={saved === "none" ? "text-[var(--mut)]" : "text-[var(--acc)]"} />
          {saved !== "none" && <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-[var(--acc)]" />}
        </button>
      )}
      {open && (
        <div data-testid="cursor-fx-menu" onMouseLeave={() => setPreview(null)}
          className={`absolute w-[min(18rem,calc(100vw-2.5rem))] max-h-[70vh] overflow-y-auto scrollbar-thin rounded-2xl border border-[var(--line)] bg-[var(--card)] shadow-2xl p-2 z-[110] cursor-fx-panel-in ${up ? "right-0 bottom-full mb-2" : "left-0 sm:left-auto sm:right-0 mt-2"}`}>
          <div className="px-2 py-1.5">
            <div className="overline">Cursor effects</div>
            <div className="text-[10px] text-[var(--dim)] mt-1">Hover to try · click to keep</div>
          </div>
          {CURSOR_EFFECTS.map(e => (
            <button key={e.id} data-testid={`cursor-fx-option-${e.id}`}
              onMouseEnter={() => setPreview(e.id === "none" ? null : e.id)}
              onClick={() => { choose(e.id); setOpen(false); }}
              className={`w-full flex items-center gap-3 px-2 py-2 rounded-xl text-left transition-colors ${effect === e.id ? "bg-white/8" : "hover:bg-white/5"}`}>
              <span className="w-7 h-7 rounded-full shrink-0 border border-white/10" style={{ background: `linear-gradient(135deg, ${e.swatch[0]}, ${e.swatch[1]})` }} />
              <span className="flex-1 min-w-0">
                <span className="block text-sm font-medium truncate">{e.name}</span>
                <span className="block text-[11px] text-[var(--mut)] truncate">{e.hint}</span>
              </span>
              {saved === e.id && <Check size={14} className="text-[var(--acc)] shrink-0" />}
            </button>
          ))}
          <div className="mt-2 pt-2 border-t border-[var(--line)]">
            <div className="px-2 overline">Intensity</div>
            <Slider label="Thickness" value={density} testid="cursor-fx-density-slider" onChange={v => setIntensity(v, speed)} />
            <Slider label="Speed" value={speed} testid="cursor-fx-speed-slider" onChange={v => setIntensity(density, v)} />            <button data-testid="cursor-fx-intensity-reset-btn" onClick={() => setIntensity(DEFAULT_DENSITY, DEFAULT_SPEED)}
              className="mx-2 mb-1 btn-ghost text-[11px] !py-1 !px-2.5 flex items-center gap-1.5"><RotateCcw size={11} /> Reset intensity</button>
          </div>
        </div>
      )}
    </div>
  );
}
