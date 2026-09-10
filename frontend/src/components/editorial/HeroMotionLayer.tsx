import { useEffect, useRef } from "react";
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
  className?: string;
};

export default function HeroMotionLayer({
  hero = "", accent = "#10B981", reduced = false, mobile, className = "",
}: Props) {
  const cvs = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const cv = cvs.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;

    const prefersReduced = typeof matchMedia === "function"
      && matchMedia("(prefers-reduced-motion: reduce)").matches;
    const isMobile = mobile ?? (typeof innerWidth === "number" && innerWidth < 768);
    const draw = engineFor(hero)(accent, isMobile);

    let w = 0, h = 0, raf = 0, start = 0, visible = true;
    const dpr = Math.min(devicePixelRatio || 1, 2);
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
      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = "lighter";
      draw(ctx, w, h, t);
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
      if (visible) frame((now - start) / 1000);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => { io.disconnect(); ro.disconnect(); cancelAnimationFrame(raf); };
  }, [hero, accent, reduced, mobile]);

  return (
    <div
      className={`hm-layer ${reduced ? "hm-static" : ""} ${className}`}
      data-testid="hero-motion-layer"
      data-hero={hero || "particle-network"}
      aria-hidden="true"
    >
      <canvas ref={cvs} className="hm-canvas" data-testid="hero-motion-canvas" />
    </div>
  );
}
