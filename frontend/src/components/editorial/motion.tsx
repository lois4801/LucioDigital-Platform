import { useEffect, useRef, useState } from "react";

export const EASE = [0.16, 1, 0.3, 1];
export const EASE_CSS = "cubic-bezier(0.16, 1, 0.3, 1)";

export function useReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const m = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(m.matches);
    const on = () => setReduced(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return reduced;
}

export function useIsMobile(bp = 768) {
  const [m, setM] = useState(() => (typeof window !== "undefined" ? window.innerWidth < bp : false));
  useEffect(() => {
    const on = () => setM(window.innerWidth < bp);
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, [bp]);
  return m;
}

// Normalised cursor position (-1..1) for parallax. Desktop only.
export function useCursorParallax(enabled = true) {
  const pos = useRef({ x: 0, y: 0 });
  const [, force] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    let raf = 0;
    const on = (e) => {
      pos.current = { x: (e.clientX / window.innerWidth) * 2 - 1, y: (e.clientY / window.innerHeight) * 2 - 1 };
      if (!raf) raf = requestAnimationFrame(() => { raf = 0; force(n => n + 1); });
    };
    window.addEventListener("mousemove", on, { passive: true });
    return () => { window.removeEventListener("mousemove", on); if (raf) cancelAnimationFrame(raf); };
  }, [enabled]);
  return pos.current;
}

// Fires once when the element scrolls into view.
export function useInView(margin = "-12%") {
  const ref = useRef(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setSeen(true); io.disconnect(); } },
      { rootMargin: `0px 0px ${margin} 0px` });
    io.observe(el);
    return () => io.disconnect();
  }, [seen, margin]);
  return [ref, seen];
}

// Fade + 30px rise, 0.5s, 80ms stagger per index. Transform/opacity only.
export function Reveal({ children, i = 0, className = "", as: As = "div", scale = false, testid }) {
  const reduced = useReducedMotion();
  const [ref, seen] = useInView();
  const on = reduced || seen;
  return (
    <As ref={ref} data-testid={testid} className={className}
      style={{
        opacity: on ? 1 : 0,
        transform: on ? "none" : `translate3d(0,30px,0)${scale ? " scale(0.95)" : ""}`,
        transition: reduced ? "none" : `opacity .5s ${EASE_CSS} ${i * 0.08}s, transform .5s ${EASE_CSS} ${i * 0.08}s`,
        willChange: "transform, opacity",
      }}>
      {children}
    </As>
  );
}

// Section heading: left-to-right clip-path wipe, 0.6s.
export function HeadingWipe({ children, className = "", as: As = "h2", testid }) {
  const reduced = useReducedMotion();
  const [ref, seen] = useInView();
  const on = reduced || seen;
  return (
    <As ref={ref} data-testid={testid} className={className}
      style={{
        clipPath: on ? "inset(0 0% 0 0)" : "inset(0 100% 0 0)",
        transition: reduced ? "none" : `clip-path .6s ${EASE_CSS}`,
        willChange: "clip-path",
      }}>
      {children}
    </As>
  );
}

// Headline: word-by-word wipe with a 105% overshoot settle.
export function OvershootWords({ text, className = "", accentFrom = 999, testid }) {
  const reduced = useReducedMotion();
  const words = String(text).split(" ");
  return (
    <h1 data-testid={testid} className={className} aria-label={text}>
      {words.map((w, i) => (
        <span key={`${w}-${i}`} className="inline-block overflow-hidden align-bottom">
          <span className={`inline-block ${reduced ? "" : "ed-word"} ${i >= accentFrom ? "text-[var(--ed-lime)]" : ""}`}
            style={reduced ? undefined : { animationDelay: `${i * 0.06}s` }}>
            {w}&nbsp;
          </span>
        </span>
      ))}
    </h1>
  );
}

// Odometer-style count-up with comma formatting.
export function Counter({ to = 0, duration = 1400, className = "", testid }) {
  const reduced = useReducedMotion();
  const [ref, seen] = useInView("0px");
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!seen) return;
    if (reduced) { setV(to); return; }
    let raf = 0; const t0 = performance.now();
    const tick = (now) => {
      const p = Math.min(1, (now - t0) / duration);
      setV(Math.round(to * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [seen, to, duration, reduced]);
  return <span ref={ref} data-testid={testid} className={className}>{v.toLocaleString()}</span>;
}
