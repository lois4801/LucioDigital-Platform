import { createContext, useCallback, useContext, useEffect, useRef } from "react";
import { useCursorFX } from "@/components/CursorFX";
import { startScopedCursorFX } from "@/lib/cursorEffects";

const Ctx = createContext(null);
export function useScopedFXBurst() { return useContext(Ctx) || (() => {}); }

// Wraps a panel so the active cursor effect emits from its controls and stays clipped inside its box.
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
    const inst = startScopedCursorFX(cv.current, effect, { density, speed });
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
          const x = r.left - box.left + Math.random() * r.width;
          const y = r.top - box.top + r.height * (0.2 + Math.random() * 0.7);
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
    api.current.emit(r.left - box.left + r.width / 2, r.top - box.top + r.height / 2, Math.min(10, n));
  }, []);

  if (burstRef) burstRef.current = burst;

  return (
    <Ctx.Provider value={burst}>
      <div ref={wrap} data-testid="scoped-cursor-fx" className={`relative overflow-hidden ${className}`}>
        <canvas ref={cv} className="absolute inset-0 w-full h-full pointer-events-none z-[5]" />
        {children}
      </div>
    </Ctx.Provider>
  );
}
