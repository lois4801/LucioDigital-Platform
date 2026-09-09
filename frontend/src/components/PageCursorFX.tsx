import { useCallback, useEffect, useRef } from "react";
import { useCursorFX } from "@/components/CursorFX";
import { startPageCursorFX } from "@/lib/cursorEffects";

// Full-page animation layer. Always z-0 and pointer-events-none: it can never block a click,
// and it dims itself behind anything marked [data-fx-content].
export default function PageCursorFX() {
  const { effect, density, speed } = useCursorFX();
  const cv = useRef(null);

  const getContentRects = useCallback(() => {
    const out = [];
    document.querySelectorAll("[data-fx-content]").forEach((el) => {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) out.push({ x: r.left, y: r.top, width: r.width, height: r.height });
    });
    return out;
  }, []);

  useEffect(() => {
    if (!cv.current || effect === "none") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    return startPageCursorFX(cv.current, effect, { density, speed, getContentRects });
  }, [effect, density, speed, getContentRects]);

  if (effect === "none") return null;
  return (
    <canvas ref={cv} data-testid="page-cursor-fx-canvas" data-effect={effect} aria-hidden="true"
      className="fixed inset-0 z-0 pointer-events-none" style={{ zIndex: 0, pointerEvents: "none" }} />
  );
}
