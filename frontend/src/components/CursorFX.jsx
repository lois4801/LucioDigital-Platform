import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { Sparkles, Check } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { CURSOR_EFFECTS, isEffect, startCursorFX } from "@/lib/cursorEffects";

const KEY = "os_cursor_effect";
const Ctx = createContext(null);

export function CursorFXProvider({ children }) {
  const { user } = useAuth();
  const [saved, setSaved] = useState(() => {
    const v = typeof localStorage !== "undefined" ? localStorage.getItem(KEY) : null;
    return isEffect(v) ? v : "none";
  });
  const [preview, setPreview] = useState(null);   // hover preview in the picker
  const [override, setOverride] = useState(null); // per-tenant site override

  // The signed-in user's stored preference wins over the local cache.
  useEffect(() => {
    const v = user?.cursor_effect;
    if (isEffect(v)) { setSaved(v); localStorage.setItem(KEY, v); }
  }, [user?.cursor_effect]);

  const choose = useCallback(async (id) => {
    if (!isEffect(id)) return;
    setSaved(id); setPreview(null);
    localStorage.setItem(KEY, id);
    try { await api.patch("/me/preferences", { cursor_effect: id }); } catch {}
  }, []);

  const effect = preview || override || saved;
  return (
    <Ctx.Provider value={{ effect, saved, choose, setPreview, setOverride }}>
      {children}
      <CursorFXLayer effect={effect} />
    </Ctx.Provider>
  );
}

export function useCursorFX() {
  return useContext(Ctx) || { effect: "none", saved: "none", choose: () => {}, setPreview: () => {}, setOverride: () => {} };
}

// Applies a site/tenant effect for as long as the calling page is mounted.
export function useTenantCursorFX(effectId) {
  const { setOverride } = useCursorFX();
  useEffect(() => {
    setOverride(isEffect(effectId) ? effectId : null);
    return () => setOverride(null);
  }, [effectId, setOverride]);
}

function CursorFXLayer({ effect }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current || effect === "none") return;
    if (window.matchMedia("(pointer: coarse)").matches) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    return startCursorFX(ref.current, effect);
  }, [effect]);
  if (effect === "none") return null;
  return <canvas ref={ref} data-testid="cursor-fx-canvas" data-effect={effect} className="fixed inset-0 z-[9998] pointer-events-none" />;
}

export function CursorFXPicker() {
  const { saved, effect, choose, setPreview } = useCursorFX();
  const [open, setOpen] = useState(false);
  const box = useRef(null);
  useEffect(() => {
    if (!open) return;
    const h = (e) => { if (box.current && !box.current.contains(e.target)) { setOpen(false); setPreview(null); } };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open, setPreview]);

  const active = CURSOR_EFFECTS.find(e => e.id === saved) || CURSOR_EFFECTS[0];
  return (
    <div className="relative" ref={box}>
      <button data-testid="cursor-fx-picker-btn" title={`Cursor effect · ${active.name}`} onClick={() => setOpen(o => !o)}
        className="w-10 h-10 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-white/5 relative">
        <Sparkles size={16} className={saved === "none" ? "text-[var(--mut)]" : "text-[var(--acc)]"} />
        {saved !== "none" && <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-[var(--acc)]" />}
      </button>
      {open && (
        <div data-testid="cursor-fx-menu" onMouseLeave={() => setPreview(null)}
          className="absolute right-0 mt-2 w-72 max-h-[70vh] overflow-y-auto scrollbar-thin rounded-2xl border border-[var(--line)] bg-[var(--card)] shadow-2xl p-2 z-[80]">
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
        </div>
      )}
    </div>
  );
}
