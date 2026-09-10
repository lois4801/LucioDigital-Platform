import { useEffect, useRef, useState } from "react";

/** Signature hero motion layer.
 *  Every template's hero name maps to its own engine + parameter set, so no two templates
 *  animate identically. Background only: transforms/opacity, pointer-events none, z-0.
 */
const S = (engine, p = {}) => ({ engine, ...p });

export const HERO_SPECS = {
  // ── core 16 ──
  "curved-ribbon-scroll":     S("ribbon", { dur: 26, tilt: 8, rows: 2 }),
  "orbital-constellation":    S("orbit", { dur: 18, nodes: 7, radius: 34 }),
  "calm-pulse-wave":          S("pulse", { dur: 3, rings: 3, spread: 46 }),
  "kinetic-energy-burst":     S("burst", { dur: 1.1, shards: 14, blur: 1 }),
  "precision-grid-reveal":    S("scan", { dur: 4.2, cell: 26, thickness: 1 }),
  "slow-luxury-parallax":     S("parallax", { dur: 22, layers: 3, scale: 1.06 }),
  "blueprint-draft-on":       S("draw", { dur: 2.4, paths: "blueprint" }),
  "particle-network":         S("particles", { count: 46, link: 130, repel: 90 }),
  "scattered-gravity-drop":   S("drop", { dur: 1.4, items: 10, rot: 15 }),
  "spotlight-sweep":          S("spotlight", { dur: 4, size: 52, follow: true }),
  "data-dashboard-morph":     S("charts", { dur: 2.2, bars: 12 }),
  "product-orbit-carousel":   S("orbit", { dur: 30, nodes: 6, radius: 40, perspective: true }),
  "steam-aroma-drift":        S("drift", { dur: 9, wisps: 5, rise: 60, opacity: 0.3 }),
  "route-path-animation":     S("draw", { dur: 3.2, paths: "route", travellers: 2 }),
  "circuit-trace-draw":       S("draw", { dur: 2.5, paths: "circuit", nodePulse: true }),
  "thermal-current-drift":    S("drift", { dur: 12, wisps: 4, rise: 80, opacity: 0.22 }),
  // ── studio pack ──
  "paw-print-trail":          S("trail", { dur: 5, steps: 7, angle: -38 }),
  "precision-slide-in":       S("slide", { dur: 0.4, overshoot: 8, stagger: 0.06 }),
  "ledger-line-reveal":       S("rules", { dur: 1.8, lines: 12, dir: "lr" }),
  "organic-leaf-unfurl":      S("unfurl", { dur: 2, blobs: 4 }),
  "shutter-aperture-open":    S("aperture", { dur: 0.6, blades: 6 }),
  "gear-shift-acceleration":  S("streaks", { dur: 1.2, lines: 9, blur: 2 }),
  "float-and-bloom":          S("bloom", { dur: 1.4, petals: 6 }),
  "shield-assemble":          S("draw", { dur: 2.4, paths: "shield", segment: 0.2 }),
  "playful-bounce-trail":     S("bubbles", { dur: 7, dots: 12, bounce: true }),
  "pipe-flow-trace":          S("draw", { dur: 2.8, paths: "pipes", flow: true }),
  "desk-network-pulse":       S("particles", { count: 26, link: 150, pulse: true }),
  "breathing-canvas":         S("breathe", { dur: 6, scale: 1.03 }),
  "sweep-and-reveal":         S("sweep", { dur: 0.5, double: true }),
  "sound-wave-rhythm":        S("wave", { dur: 4, layers: 3, amp: 26 }),
  "community-ripple":         S("pulse", { dur: 3, rings: 3, spread: 70, fromCentre: true }),
  "structural-line-reveal":   S("draw", { dur: 3, paths: "structure" }),
  "modular-grid-build":       S("assemble", { dur: 2, blocks: 12, rot: 10 }),
  // ── reserved ──
  "matrix-code-rain":         S("rain", { dur: 6, columns: 22 }),
  "dna-helix-rotation":       S("helix", { dur: 14, rungs: 14 }),
  "stadium-wave-ripple":      S("wave", { dur: 5, layers: 2, amp: 40, roll: true }),
  "editorial-magazine-flip":  S("flip", { dur: 0.6, every: 4 }),
  "command-line-type-on":     S("type", { speed: 40 }),
  "metric-counter-cascade":   S("charts", { dur: 1.2, bars: 8, flip: true }),
  "museum-spotlight-pan":     S("spotlight", { dur: 4, size: 60, pan: true }),
  "aurora-wave":              S("aurora", { dur: 18, bands: 3 }),
  "ingredient-scatter":       S("drop", { dur: 1.2, items: 12, rot: 22, scatter: true }),
  "architectural-fly-through": S("parallax", { dur: 8, layers: 2, scale: 1.08, push: true }),
  "platform-drift-cards":     S("drift", { dur: 8, wisps: 0, cards: true }),
};

const rand = (a, b) => a + Math.random() * (b - a);

export default function HeroMotionLayer({ hero = "", accent = "#10B981", reduced = false, mobile = false }) {
  const spec = HERO_SPECS[hero] || HERO_SPECS["platform-drift-cards"];
  const cvs = useRef(null);
  const [seed] = useState(() => Math.random());

  // Canvas engines (particles / rain / wave / aurora) — GPU-light, capped, halved on mobile.
  useEffect(() => {
    const engine = spec.engine;
    if (reduced || !cvs.current || !["particles", "rain", "wave", "aurora", "helix"].includes(engine)) return;
    const cv = cvs.current, ctx = cv.getContext("2d");
    let w = 0, h = 0, raf = 0, t = 0;
    const dpr = Math.min(devicePixelRatio || 1, 2);
    const resize = () => {
      const r = cv.getBoundingClientRect();
      w = r.width; h = r.height;
      cv.width = w * dpr; cv.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize); ro.observe(cv);

    const n = Math.round((spec.count || spec.columns || spec.layers || 30) * (mobile ? 0.5 : 1));
    const pts = Array.from({ length: n }, () => ({
      x: rand(0, 1), y: rand(0, 1), vx: rand(-0.02, 0.02), vy: rand(-0.02, 0.02),
      s: rand(0.4, 1), o: rand(0.2, 0.6),
    }));

    const loop = () => {
      t += 0.016;
      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = "lighter";
      if (engine === "particles") {
        pts.forEach(p => { p.x += p.vx * 0.004; p.y += p.vy * 0.004; if (p.x < 0 || p.x > 1) p.vx *= -1; if (p.y < 0 || p.y > 1) p.vy *= -1; });
        ctx.strokeStyle = `${accent}22`; ctx.lineWidth = 1;
        for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) {
          const dx = (pts[i].x - pts[j].x) * w, dy = (pts[i].y - pts[j].y) * h;
          const d = Math.hypot(dx, dy);
          if (d < (spec.link || 130)) { ctx.beginPath(); ctx.moveTo(pts[i].x * w, pts[i].y * h); ctx.lineTo(pts[j].x * w, pts[j].y * h); ctx.stroke(); }
        }
        pts.forEach(p => {
          ctx.fillStyle = `${accent}${spec.pulse ? "cc" : "88"}`;
          const r = 1.6 * p.s * (spec.pulse ? 1 + 0.4 * Math.sin(t * 2 + p.x * 9) : 1);
          ctx.beginPath(); ctx.arc(p.x * w, p.y * h, r, 0, Math.PI * 2); ctx.fill();
        });
      } else if (engine === "rain") {
        ctx.font = "12px ui-monospace, monospace";
        pts.forEach((p, i) => {
          p.y += 0.004 + p.s * 0.006; if (p.y > 1.1) p.y = -0.1;
          ctx.fillStyle = `${accent}${i % 5 === 0 ? "dd" : "55"}`;
          ctx.fillText(String.fromCharCode(0x30a0 + ((i * 7 + Math.floor(t * 6)) % 90)), p.x * w, p.y * h);
        });
      } else if (engine === "wave") {
        for (let l = 0; l < (spec.layers || 3); l++) {
          ctx.strokeStyle = `${accent}${l === 0 ? "66" : "33"}`; ctx.lineWidth = 1.5;
          ctx.beginPath();
          for (let x = 0; x <= w; x += 6) {
            const k = spec.roll ? Math.sin((x / w) * 6 - t * 1.6) : Math.sin(x / 90 + t * (1 + l * 0.4));
            ctx.lineTo(x, h / 2 + k * (spec.amp || 26) * (1 - l * 0.25));
          }
          ctx.stroke();
        }
      } else if (engine === "aurora") {
        for (let b = 0; b < (spec.bands || 3); b++) {
          const g = ctx.createLinearGradient(0, 0, w, h);
          g.addColorStop(0, `${accent}00`); g.addColorStop(0.5, `${accent}${b === 0 ? "33" : "1f"}`); g.addColorStop(1, `${accent}00`);
          ctx.fillStyle = g; ctx.beginPath();
          for (let x = 0; x <= w; x += 10) ctx.lineTo(x, h * (0.25 + b * 0.2) + Math.sin(x / 160 + t * (0.3 + b * 0.15)) * 48);
          ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.fill();
        }
      } else if (engine === "helix") {
        ctx.lineWidth = 1.4;
        for (let i = 0; i < (spec.rungs || 14); i++) {
          const y = (i / (spec.rungs || 14)) * h;
          const a = Math.sin(t * 0.5 + i * 0.5) * (w * 0.14);
          ctx.strokeStyle = `${accent}44`;
          ctx.beginPath(); ctx.moveTo(w / 2 - a, y); ctx.lineTo(w / 2 + a, y); ctx.stroke();
          ctx.fillStyle = `${accent}66`;
          ctx.beginPath(); ctx.arc(w / 2 - a, y, 2, 0, Math.PI * 2); ctx.fill();
          ctx.beginPath(); ctx.arc(w / 2 + a, y, 2, 0, Math.PI * 2); ctx.fill();
        }
      }
      ctx.globalCompositeOperation = "source-over";
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => { ro.disconnect(); cancelAnimationFrame(raf); };
  }, [spec, accent, reduced, mobile]);

  const style = {
    ["--hm-accent"]: accent,
    ["--hm-dur"]: `${spec.dur || 8}s`,
    ["--hm-scale"]: spec.scale || 1.04,
    ["--hm-amp"]: `${spec.amp || 26}px`,
    ["--hm-tilt"]: `${spec.tilt || 6}deg`,
  };
  const count = Math.round((spec.items || spec.shards || spec.dots || spec.steps || spec.lines
    || spec.blocks || spec.petals || spec.blobs || spec.rings || spec.nodes || spec.bars || 8) * (mobile ? 0.5 : 1));

  const canvasEngine = ["particles", "rain", "wave", "aurora", "helix"].includes(spec.engine);

  return (
    <div className={`hm-layer hm-${spec.engine} ${reduced ? "hm-static" : ""}`} style={style}
      data-testid="hero-motion-layer" data-hero={hero} aria-hidden="true">
      {canvasEngine
        ? <canvas ref={cvs} className="hm-canvas" />
        : Array.from({ length: Math.max(3, Math.min(16, count)) }).map((_, i) => (
          <span key={i} className="hm-el" style={{
            ["--i"]: i,
            ["--d"]: `${(i * (spec.stagger || 0.09)).toFixed(2)}s`,
            ["--x"]: `${((seed * 97 + i * 37) % 90) + 5}%`,
            ["--y"]: `${((seed * 53 + i * 61) % 80) + 8}%`,
            ["--r"]: `${(((seed * 31 + i * 17) % (2 * (spec.rot || 8))) - (spec.rot || 8)).toFixed(1)}deg`,
          }} />
        ))}
    </div>
  );
}
