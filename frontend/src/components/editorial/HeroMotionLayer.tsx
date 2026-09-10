import { useEffect, useRef, useState } from "react";
import { engineFor, HERO_ENGINES, HERO_NAMES } from "./heroEngines";

/** Signature hero motion layer.
 *  Every template's hero maps to its OWN bespoke render engine (see heroEngines*.ts).
 *  Background only: pointer-events none, z-0, accent-tinted, density halved < 768px,
 *  a single static frame when motion is reduced.
 */
export { HERO_ENGINES, HERO_NAMES };

type Props = {
  hero?: string;
  accent?: string;
  reduced?: boolean;
  mobile?: boolean;
  speed?: number;       // 0.25x – 2x playback of the engine's own clock
  intensity?: number;   // 0.2 (subtle) – 1.5 (bold) presence
  mode?: string;        // "light" | "dark" — drives blend, contrast and stroke weight
  className?: string;
};

const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, Number.isFinite(v) ? v : 1));

/** Pull a hex accent toward black so it still reads on a white page. */
const darken = (hex: string, amount: number) => {
  const h = (hex || "#10B981").replace("#", "").slice(0, 6);
  if (h.length !== 6) return hex;
  const [r, g, b] = [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16));
  const k = 1 - clamp(amount, 0, 1);
  return "#" + [r, g, b].map(c => Math.round(c * k).toString(16).padStart(2, "0")).join("");
};

const rgb = (hex: string) => {
  const h = (hex || "#10B981").replace("#", "").slice(0, 6);
  return h.length === 6 ? [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)) : [16, 185, 129];
};
const hex = (c: number[]) => "#" + c.map(v => Math.round(clamp(v, 0, 255)).toString(16).padStart(2, "0")).join("");
const luma = (c: number[]) => (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255;
const ratio = (a: number, b: number) => (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);

/** Contrast guard: lift (or deepen) the accent until it separates from its own background. */
const guardAccent = (accent: string, bg: number, target = 2.6) => {
  let c = rgb(accent);
  for (let i = 0; i < 14 && ratio(luma(c), bg) < target; i++) {
    c = bg > 0.45
      ? c.map(v => v * 0.82)                       // light page → deepen
      : c.map(v => v + (255 - v) * 0.16);          // dark page → brighten
  }
  return hex(c);
};

/** Per-hero stroke rhythm: each engine gets its own weight signature so lines read as
 *  hairlines, mid strokes and bold accents instead of one flat width. */
const RHYTHMS = [
  [0.55, 1, 1.8, 2.8], [0.7, 1.5, 1, 2.3], [1, 0.6, 2.4, 1.4],
  [0.5, 1.2, 2.1, 3.2], [0.85, 1.9, 0.6, 1.35], [1.1, 0.65, 1.6, 2.6],
];
const rhythmFor = (hero: string) =>
  RHYTHMS[Math.abs([...(hero || "x")].reduce((a, ch) => a * 31 + ch.charCodeAt(0), 7)) % RHYTHMS.length];

/** Engines set ctx.lineWidth freely; we scale it for legibility and vary it for depth. */
const withStrokeRhythm = (ctx: CanvasRenderingContext2D, boost: number, weights: number[], min = 0.5) => {
  let i = 0, j = 0;
  const radii = [0.82, 1.18, 0.94, 1.4];      // gentle size variation on dots, rings and glows
  const proxy = new Proxy(ctx, {
    get(t, k) {
      if (k === "arc") {
        return (x: number, y: number, r: number, a0: number, a1: number, ccw?: boolean) =>
          t.arc(x, y, Math.max(0.4, r * radii[j++ % radii.length]), a0, a1, ccw);
      }
      const v = (t as any)[k];
      return typeof v === "function" ? v.bind(t) : v;
    },
    set(t, k, v) {
      (t as any)[k] = k === "lineWidth"
        ? Math.max(min, (v as number) * boost * weights[i++ % weights.length])
        : v;
      return true;
    },
  }) as CanvasRenderingContext2D;
  // Counters reset every frame, so element N always gets the SAME weight and radius.
  // Without this the pattern walks each frame and the motion flickers / vibrates.
  return { paint: proxy, reset: () => { i = 0; j = 0; } };
};

/** Relative luminance of any CSS colour string, or null when it is transparent. */
const lumaOf = (css: string): number | null => {
  const m = (css || "").match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  const p = m[1].split(",").map(s => parseFloat(s.trim()));
  if (p.length > 3 && p[3] < 0.5) return null;
  return (0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2]) / 255;
};

export default function HeroMotionLayer({
  hero = "", accent = "#10B981", reduced = false, mobile, speed = 1, intensity = 1,
  mode, className = "",
}: Props) {
  const cvs = useRef<HTMLCanvasElement | null>(null);
  // An explicit mode (a project's own theme) wins; otherwise measure the real backdrop.
  const [measured, setMeasured] = useState<number | null>(null);
  const light = mode === "light" || mode === "dark" ? mode === "light" : ((measured ?? 0) > 0.45);
  const bgLuma = measured ?? (light ? 0.96 : 0.05);
  const sp = clamp(speed, 0.25, 2);
  const it = clamp(intensity, 0.2, 1.5) * (light ? 1.45 : 1);
  const isNarrow = mobile ?? (typeof window !== "undefined" && window.innerWidth < 768);
  const baseOpacity = isNarrow ? (light ? 0.55 : 0.42) : (light ? 0.8 : 0.62);
  const tint = guardAccent(light ? darken(accent, 0.3) : accent, bgLuma);

  useEffect(() => {
    let el: HTMLElement | null = cvs.current?.parentElement || null;
    for (let i = 0; i < 12 && el; i++, el = el.parentElement) {
      const l = lumaOf(getComputedStyle(el).backgroundColor);
      if (l !== null) { setMeasured(l); return; }
    }
    setMeasured(null);
  }, [hero, mode]);

  useEffect(() => {
    const cv = cvs.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;

    const prefersReduced = typeof matchMedia === "function"
      && matchMedia("(prefers-reduced-motion: reduce)").matches;
    const isMobile = mobile ?? (typeof innerWidth === "number" && innerWidth < 768);
    const draw = engineFor(hero)(tint, isMobile);
    const { paint, reset } = withStrokeRhythm(
      ctx, light ? 1.55 : 1.15, rhythmFor(hero), light ? 1 : 0.6);

    let w = 0, h = 0, raf = 0, start = 0, visible = true, last = 0;
    const minStep = 1000 / 30;                    // 30fps ceiling keeps the cursor and scroll smooth
    const dpr = Math.min(devicePixelRatio || 1, 1.75);
    const resize = () => {
      const r = cv.getBoundingClientRect();
      w = Math.max(1, r.width); h = Math.max(1, r.height);
      cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(cv);

    const frame = (t: number) => {
      reset();
      ctx.clearRect(0, 0, w, h);
      // dark pages add light; light pages darken, so motion is visible either way
      ctx.globalCompositeOperation = light ? "source-over" : "lighter";
      draw(paint, w, h, t);
      ctx.globalCompositeOperation = "source-over";
    };

    if (reduced || prefersReduced) {
      // one composed still frame, no rAF loop
      const still = () => frame(1.2);
      still();
      const t2 = setTimeout(still, 60);
      return () => { clearTimeout(t2); ro.disconnect(); };
    }

    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; }, { threshold: 0 });
    io.observe(cv);

    const loop = (now: number) => {
      if (!start) start = now;
      if (visible && !document.hidden && now - last >= minStep) {
        last = now;
        frame(((now - start) / 1000) * sp);
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => { io.disconnect(); ro.disconnect(); cancelAnimationFrame(raf); };
  }, [hero, accent, reduced, mobile, sp, light, tint]);

  return (
    <div
      className={`hm-layer ${reduced ? "hm-static" : ""} ${className}`}
      data-testid="hero-motion-layer"
      data-hero={hero || "particle-network"}
      data-speed={sp}
      data-intensity={it}
      data-mode={light ? "light" : "dark"}
      style={{ mixBlendMode: light ? "multiply" : "screen" }}
      aria-hidden="true"
    >
      <canvas ref={cvs} className="hm-canvas" data-testid="hero-motion-canvas"
        style={{ opacity: Math.min(1, baseOpacity * it) }} />
    </div>
  );
}
