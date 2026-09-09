import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { Sparkles, Check, RotateCcw } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import CursorTrail from "@/components/CursorTrail";
import { CURSOR_EFFECTS, isEffect, startCursorFX } from "@/lib/cursorEffects";

const KEY = "os_cursor_effect";
const KEY_D = "os_cursor_density";
const KEY_S = "os_cursor_speed";
const clamp = (v, d = 1) => { const n = Number(v); return Number.isFinite(n) ? Math.max(0.2, Math.min(3, n)) : d; };
const Ctx = createContext(null);

export function CursorFXProvider({ children }) {
  const { user } = useAuth();
  const [saved, setSaved] = useState(() => {
    const v = typeof localStorage !== "undefined" ? localStorage.getItem(KEY) : null;
    return isEffect(v) ? v : "none";
  });
  const [density, setDensity] = useState(() => clamp(localStorage.getItem(KEY_D)));
  const [speed, setSpeed] = useState(() => clamp(localStorage.getItem(KEY_S)));
  const [preview, setPreview] = useState(null);   // hover preview in the picker
  const [override, setOverride] = useState(null); // per-tenant site override

  // The signed-in user's stored preferences win over the local cache.
  useEffect(() => {
    if (isEffect(user?.cursor_effect)) { setSaved(user.cursor_effect); localStorage.setItem(KEY, user.cursor_effect); }
    if (user?.cursor_density !== undefined && user?.cursor_density !== null) setDensity(clamp(user.cursor_density));
    if (user?.cursor_speed !== undefined && user?.cursor_speed !== null) setSpeed(clamp(user.cursor_speed));
  }, [user?.cursor_effect, user?.cursor_density, user?.cursor_speed]);

  const choose = useCallback(async (id) => {
    if (!isEffect(id)) return;
    setSaved(id); setPreview(null);
    localStorage.setItem(KEY, id);
    // Visitors keep their pick in this browser; signed-in users also get it saved server-side.
    try { await api.patch("/me/preferences", { cursor_effect: id }); } catch { /* anonymous visitor */ }
  }, []);

  const saveTimer = useRef(null);
  const setIntensity = useCallback((d, s) => {
    const dd = clamp(d), ss = clamp(s);
    setDensity(dd); setSpeed(ss);
    localStorage.setItem(KEY_D, String(dd)); localStorage.setItem(KEY_S, String(ss));
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => { api.patch("/me/preferences", { cursor_density: dd, cursor_speed: ss }).catch(() => {}); }, 450);
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
    className="fixed inset-0 z-[9998] pointer-events-none" />;
}

// Base dot + ring take their colour from the active cursor effect.
export function CursorTrailThemed() {
  const { effect } = useCursorFX();
  const e = CURSOR_EFFECTS.find(x => x.id === effect);
  const [dot] = e && e.id !== "none" ? e.swatch : ["#10B981"];
  return <CursorTrail color={dot} />;
}

export function CursorFXPicker({ up = false }) {  const { saved, effect, density, speed, choose, setIntensity, setPreview } = useCursorFX();
  const [open, setOpen] = useState(false);
  const box = useRef(null);
  useEffect(() => {
    if (!open) return;
    const h = (e) => { if (box.current && !box.current.contains(e.target)) { setOpen(false); setPreview(null); } };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open, setPreview]);

  const active = CURSOR_EFFECTS.find(e => e.id === saved) || CURSOR_EFFECTS[0];
  const Slider = ({ label, value, testid, onChange }) => (
    <label className="block px-2 py-1.5">
      <span className="flex justify-between text-[11px] text-[var(--mut)]"><span>{label}</span><span className="font-mono">{value.toFixed(1)}×</span></span>
      <input data-testid={testid} type="range" min={0.2} max={3} step={0.1} value={value}
        onChange={e => onChange(Number(e.target.value))} className="w-full accent-[var(--acc)]" />
    </label>
  );

  return (
    <div className="relative" ref={box}>
      <button data-testid="cursor-fx-picker-btn" title={`Cursor effect · ${active.name}`} onClick={() => setOpen(o => !o)}
        className="w-10 h-10 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-white/5 relative">
        <Sparkles size={16} className={saved === "none" ? "text-[var(--mut)]" : "text-[var(--acc)]"} />
        {saved !== "none" && <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-[var(--acc)]" />}
      </button>
      {open && (
        <div data-testid="cursor-fx-menu" onMouseLeave={() => setPreview(null)}
          className={`absolute w-[min(18rem,calc(100vw-2.5rem))] max-h-[60vh] overflow-y-auto scrollbar-thin rounded-2xl border border-[var(--line)] bg-[var(--card)] shadow-2xl p-2 z-[80] ${up ? "left-0 bottom-full mb-2" : "left-0 sm:left-auto sm:right-0 mt-2"}`}>
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
            <Slider label="Speed" value={speed} testid="cursor-fx-speed-slider" onChange={v => setIntensity(density, v)} />
            <button data-testid="cursor-fx-intensity-reset-btn" onClick={() => setIntensity(1, 1)}
              className="mx-2 mb-1 btn-ghost text-[11px] !py-1 !px-2.5 flex items-center gap-1.5"><RotateCcw size={11} /> Reset intensity</button>
          </div>
        </div>
      )}
    </div>
  );
}
