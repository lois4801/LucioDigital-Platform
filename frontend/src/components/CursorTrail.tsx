import { useEffect, useRef } from "react";

// Custom trailing cursor dot: lerp loop follows the pointer; disabled on touch devices.
export default function CursorTrail({ color = "#10B981" }) {
  const dot = useRef(null);
  useEffect(() => {
    if (window.matchMedia("(pointer: coarse)").matches) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const pos = { x: innerWidth / 2, y: innerHeight / 2 }, target = { ...pos };
    let raf, idle = 0;
    const move = (e) => { target.x = e.clientX; target.y = e.clientY; idle = 0; };
    const lerp = (a, b, t) => a + (b - a) * t;
    const loop = () => {
      // Park the loop when the pointer has settled or the tab is hidden — keeps pages smooth.
      if (document.hidden) { raf = requestAnimationFrame(loop); return; }
      const dx = target.x - pos.x, dy = target.y - pos.y;
      if (Math.abs(dx) < 0.2 && Math.abs(dy) < 0.2) {
        idle += 1;
        if (idle > 8) { raf = requestAnimationFrame(loop); return; }
      }
      pos.x = lerp(pos.x, target.x, 0.35); pos.y = lerp(pos.y, target.y, 0.35);
      if (dot.current) dot.current.style.transform = `translate3d(${pos.x - 4}px,${pos.y - 4}px,0)`;
      raf = requestAnimationFrame(loop);
    };
    window.addEventListener("mousemove", move, { passive: true }); raf = requestAnimationFrame(loop);
    document.documentElement.classList.add("has-cursor-trail");
    return () => { window.removeEventListener("mousemove", move); cancelAnimationFrame(raf); document.documentElement.classList.remove("has-cursor-trail"); };
  }, []);
  return <div ref={dot} data-testid="cursor-dot" className="fixed top-0 left-0 z-[9999] w-2 h-2 rounded-full pointer-events-none transition-colors duration-300" style={{ background: color }} />;
}
