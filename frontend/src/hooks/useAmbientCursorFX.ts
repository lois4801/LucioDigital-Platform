import { useEffect } from "react";
import { emitCursorFX } from "@/lib/cursorEffects";

// Continuously emits the active cursor effect from the edges of the matched elements
// (auth buttons, inputs) so the sign-in surface always shows the chosen effect.
export function useAmbientCursorFX(rootRef, selector, effect, { every = 220, per = 1 } = {}) {
  useEffect(() => {
    if (!effect || effect === "none") return;
    if (window.matchMedia("(pointer: coarse)").matches) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let timer = 0;
    const tick = () => {
      if (!document.hidden && rootRef.current) {
        const els = rootRef.current.querySelectorAll(selector);
        els.forEach((el) => {
          const r = el.getBoundingClientRect();
          if (r.height < 4 || r.bottom < 0 || r.top > innerHeight) return;
          const x = r.left + Math.random() * r.width;
          const y = r.top + r.height * (0.25 + Math.random() * 0.7);
          emitCursorFX(x, y, per);
        });
      }
      timer = window.setTimeout(tick, every);
    };
    timer = window.setTimeout(tick, every);
    return () => clearTimeout(timer);
  }, [rootRef, selector, effect, every, per]);
}
