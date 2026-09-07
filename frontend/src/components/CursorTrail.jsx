import { useEffect, useRef } from "react";

// Custom trailing cursor: lerp loop follows the pointer; disabled on touch devices.
export default function CursorTrail({ color = "#10B981", ringColor }) {
  const dot = useRef(null), ring = useRef(null);
  useEffect(() => {
    if (window.matchMedia("(pointer: coarse)").matches) return;
    const pos = { x: innerWidth / 2, y: innerHeight / 2 }, target = { ...pos }, ringPos = { ...pos };
    let raf, hovering = false;
    const move = (e) => { target.x = e.clientX; target.y = e.clientY; hovering = !!e.target.closest("a,button,[role=button],input,textarea,select,[contenteditable]"); };
    const lerp = (a, b, t) => a + (b - a) * t;
    const loop = () => {
      pos.x = lerp(pos.x, target.x, 0.35); pos.y = lerp(pos.y, target.y, 0.35);
      ringPos.x = lerp(ringPos.x, target.x, 0.12); ringPos.y = lerp(ringPos.y, target.y, 0.12);
      if (dot.current) dot.current.style.transform = `translate3d(${pos.x - 4}px,${pos.y - 4}px,0)`;
      if (ring.current) ring.current.style.transform = `translate3d(${ringPos.x - 18}px,${ringPos.y - 18}px,0) scale(${hovering ? 1.6 : 1})`;
      raf = requestAnimationFrame(loop);
    };
    window.addEventListener("mousemove", move, { passive: true }); raf = requestAnimationFrame(loop);
    document.documentElement.classList.add("has-cursor-trail");
    return () => { window.removeEventListener("mousemove", move); cancelAnimationFrame(raf); document.documentElement.classList.remove("has-cursor-trail"); };
  }, []);
  return (
    <>
      <div ref={dot} data-testid="cursor-dot" className="fixed top-0 left-0 z-[9999] w-2 h-2 rounded-full pointer-events-none transition-colors duration-300" style={{ background: color }} />
      <div ref={ring} data-testid="cursor-ring" className="fixed top-0 left-0 z-[9999] w-9 h-9 rounded-full pointer-events-none border transition-transform duration-200" style={{ borderColor: ringColor || color, opacity: 0.7, mixBlendMode: "difference" }} />
    </>
  );
}
