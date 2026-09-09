import { createContext, useCallback, useContext, useEffect, useRef } from "react";
import { useCursorFX } from "@/components/CursorFX";
import { startScopedCursorFX } from "@/lib/cursorEffects";

const Ctx = createContext(null);
export function useScopedFXBurst() { return useContext(Ctx) || (() => {}); }

// Wraps a panel so the active cursor effect emits from its controls and stays clipped inside its box.
const BAND = 44;   // width of each side gutter the effects live in

export default function ScopedCursorFX({ children, className = "", burstRef = null, selector = "button:not([data-fx-skip] *), input:not([data-fx-skip] *)", every = 200 }) {
  const { effect, density, speed } = useCursorFX();
  const wrap = useRef(null);
  const cv = useRef(null);
  const api = useRef(null);

  useEffect(() => {
    api.current = null;
    if (effect === "none" || !cv.current) return;
    if (window.matchMedia("(pointer: coarse)").matches) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const inst = startScopedCursorFX(cv.current, effect, { density, speed, sideBand: BAND });
    api.current = inst;
    return () => { inst.stop(); api.current = null; };
  }, [effect, density, speed]);

  useEffect(() => {
    if (effect === "none") return;
    let timer = 0;
    const tick = () => {
      const box = wrap.current?.getBoundingClientRect();
      if (api.current && box && !document.hidden) {
        wrap.current.querySelectorAll(selector).forEach((el) => {
          const r = el.getBoundingClientRect();
          if (r.height < 4) return;
          // Spawn only in the left/right gutters, level with each control.
          const y = r.top - box.top + r.height * (0.2 + Math.random() * 0.7);
          const b = Math.min(BAND, box.width * 0.14);
          const x = Math.random() < 0.5 ? Math.random() * b : box.width - Math.random() * b;
          api.current.emit(x, y, 1);
        });
      }
      timer = window.setTimeout(tick, every);
    };
    timer = window.setTimeout(tick, every);
    return () => clearTimeout(timer);
  }, [effect, selector, every]);

  const burst = useCallback((el, n = 6) => {
    const box = wrap.current?.getBoundingClientRect();
    if (!el || !box || !api.current) return;
    const r = el.getBoundingClientRect();
    const y = r.top - box.top + r.height / 2;
    const half = Math.max(1, Math.ceil(Math.min(10, n) / 2));
    const b = Math.min(BAND, box.width * 0.14);
    for (let i = 0; i < half; i++) {
      api.current.emit(Math.random() * b, y, 1);
      api.current.emit(box.width - Math.random() * b, y, 1);
    }
  }, []);

  if (burstRef) burstRef.current = burst;

  return (
    <Ctx.Provider value={burst}>
      <div ref={wrap} data-testid="scoped-cursor-fx" className={`relative overflow-hidden ${className}`}>
        {/* Behind the controls and dimmed so it never competes with the text. */}
        <canvas ref={cv} className="absolute inset-0 w-full h-full pointer-events-none z-0 opacity-60" />
        <div className="relative z-10">{children}</div>
      </div>
    </Ctx.Provider>
  );
}
