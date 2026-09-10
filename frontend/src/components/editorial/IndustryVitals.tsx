import { useEffect, useRef } from "react";

/** Per-industry live chart + located map. Both are canvas, deterministic dummy data, one shared
 *  30fps loop each, paused off-screen. Ten chart designs so no two industries look alike. */
const VARIANTS = ["area", "bars", "donut", "radar", "step", "candles", "gauge", "stacked", "bubble", "wave"];

const seedOf = (s: string) => Math.abs([...(s || "x")].reduce((a, c) => a * 31 + c.charCodeAt(0), 17));
const rand = (seed: number) => { let s = seed % 233280; return () => (s = (s * 9301 + 49297) % 233280) / 233280; };
const A = (c: string, a: number) => (c || "#10B981").slice(0, 7) + Math.round(Math.max(0, Math.min(1, a)) * 255).toString(16).padStart(2, "0");

function useLoop(ref: any, draw: (ctx: any, w: number, h: number, t: number) => void, deps: any[]) {
  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const ctx = cv.getContext("2d"); if (!ctx) return;
    const dpr = Math.min(devicePixelRatio || 1, 1.75);
    let w = 0, h = 0, raf = 0, start = 0, last = 0, vis = true;
    const size = () => {
      const r = cv.getBoundingClientRect();
      w = Math.max(1, r.width); h = Math.max(1, r.height);
      cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    size();
    const ro = new ResizeObserver(size); ro.observe(cv);
    const io = new IntersectionObserver(([e]) => { vis = e.isIntersecting; }, { threshold: 0 }); io.observe(cv);
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const step = (now: number) => {
      if (!start) start = now;
      if (vis && !document.hidden && now - last >= 33) {
        last = now; ctx.clearRect(0, 0, w, h); draw(ctx, w, h, (now - start) / 1000);
      }
      raf = requestAnimationFrame(step);
    };
    if (reduce) { ctx.clearRect(0, 0, w, h); draw(ctx, w, h, 1.6); }
    else raf = requestAnimationFrame(step);
    return () => { ro.disconnect(); io.disconnect(); cancelAnimationFrame(raf); };
  }, deps);
}

function LiveChart({ variant, accent, seed, label }) {
  const ref = useRef(null);
  const r = rand(seed || 7);
  const data = Array.from({ length: 12 }, () => 0.15 + r() * 0.85);
  useLoop(ref, (ctx, w, h, t) => {
    const v = data.map((d, i) => Math.max(0.06, Math.min(1, d * (0.72 + 0.28 * Math.sin(t * 0.8 + i * 0.6)))));
    const grow = Math.min(1, t / 0.9);
    const pad = 14, iw = w - pad * 2, ih = h - pad * 2;
    ctx.strokeStyle = A(accent, 0.5); ctx.fillStyle = A(accent, 0.18); ctx.lineWidth = 2;
    if (variant === "area" || variant === "step" || variant === "wave") {
      ctx.beginPath(); ctx.moveTo(pad, h - pad);
      v.forEach((y, i) => {
        const x = pad + (iw * i) / (v.length - 1), yy = h - pad - y * ih * grow;
        if (variant === "step" && i) ctx.lineTo(x, h - pad - v[i - 1] * ih * grow);
        if (variant === "wave") ctx.lineTo(x, h - pad - (0.5 + Math.sin(t * 2 + i) * 0.35 * y) * ih * grow);
        else ctx.lineTo(x, yy);
      });
      ctx.lineTo(w - pad, h - pad); ctx.closePath(); ctx.fill(); ctx.stroke();
    } else if (variant === "bars" || variant === "stacked" || variant === "candles") {
      const bw = iw / v.length;
      v.forEach((y, i) => {
        const x = pad + i * bw + bw * 0.2, bh = y * ih * grow;
        ctx.fillStyle = A(accent, 0.28 + y * 0.4);
        if (variant === "candles") {
          ctx.fillRect(x + bw * 0.24, h - pad - bh, bw * 0.14, bh);
          ctx.fillRect(x, h - pad - bh * 0.7, bw * 0.6, bh * 0.45);
        } else if (variant === "stacked") {
          ctx.fillRect(x, h - pad - bh, bw * 0.6, bh * 0.6);
          ctx.fillStyle = A(accent, 0.16);
          ctx.fillRect(x, h - pad - bh * 0.4, bw * 0.6, bh * 0.4);
        } else ctx.fillRect(x, h - pad - bh, bw * 0.6, bh);
      });
    } else if (variant === "donut" || variant === "gauge") {
      const cx = w / 2, cy = variant === "gauge" ? h * 0.78 : h / 2, R = Math.min(w, h) * (variant === "gauge" ? 0.42 : 0.32);
      const span = variant === "gauge" ? Math.PI : Math.PI * 2, base = variant === "gauge" ? Math.PI : -Math.PI / 2;
      let acc = 0;
      ctx.lineWidth = Math.max(9, R * 0.3);
      v.slice(0, 5).forEach((y, i) => {
        const frac = (y / v.slice(0, 5).reduce((a, b) => a + b, 0)) * span * grow;
        ctx.strokeStyle = A(accent, 0.22 + i * 0.14);
        ctx.beginPath(); ctx.arc(cx, cy, R, base + acc, base + acc + frac); ctx.stroke();
        acc += frac;
      });
    } else if (variant === "radar") {
      const cx = w / 2, cy = h / 2, R = Math.min(w, h) * 0.36, n = 6;
      ctx.strokeStyle = A(accent, 0.16);
      for (let ring = 1; ring <= 3; ring++) {
        ctx.beginPath();
        for (let i = 0; i <= n; i++) {
          const a = (i / n) * Math.PI * 2 - Math.PI / 2;
          ctx.lineTo(cx + Math.cos(a) * R * (ring / 3), cy + Math.sin(a) * R * (ring / 3));
        }
        ctx.stroke();
      }
      ctx.strokeStyle = A(accent, 0.6); ctx.fillStyle = A(accent, 0.18);
      ctx.beginPath();
      for (let i = 0; i <= n; i++) {
        const a = (i / n) * Math.PI * 2 - Math.PI / 2, y = v[i % v.length];
        ctx.lineTo(cx + Math.cos(a) * R * y * grow, cy + Math.sin(a) * R * y * grow);
      }
      ctx.closePath(); ctx.fill(); ctx.stroke();
    } else {
      v.forEach((y, i) => {
        const x = pad + (iw * i) / (v.length - 1);
        ctx.fillStyle = A(accent, 0.16 + y * 0.3);
        ctx.beginPath(); ctx.arc(x, h - pad - y * ih * grow, 4 + y * 14 * grow, 0, Math.PI * 2); ctx.fill();
      });
    }
  }, [variant, accent, seed]);

  return (
    <div className="relative rounded-[var(--tr)] border border-[var(--tbd)] p-4 overflow-hidden"
      data-testid="industry-chart" data-chart-variant={variant}>
      <div className="text-[10px] uppercase tracking-[0.18em] opacity-60">{label}</div>
      <canvas ref={ref} className="w-full h-[190px] block mt-2" data-testid="industry-chart-canvas" />
    </div>
  );
}

function LocationMap({ accent, address, brand }) {
  const ref = useRef(null);
  const seed = seedOf(address || brand);
  useLoop(ref, (ctx, w, h, t) => {
    const r = rand(seed);
    // street grid seeded by the address, so every location draws a different city block
    ctx.strokeStyle = A(accent, 0.12); ctx.lineWidth = 1;
    const cols = 6 + (seed % 4), rows = 4 + (seed % 3);
    for (let i = 1; i < cols; i++) {
      const x = (w * i) / cols + Math.sin(i * seed) * 6;
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x + 14, h); ctx.stroke();
    }
    for (let j = 1; j < rows; j++) {
      const y = (h * j) / rows + Math.cos(j * seed) * 5;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y + 8); ctx.stroke();
    }
    // blocks
    ctx.fillStyle = A(accent, 0.05);
    for (let i = 0; i < 14; i++) ctx.fillRect(r() * w, r() * h, 20 + r() * 60, 14 + r() * 40);
    // the pin: pulsing service radius + marker
    const cx = w * (0.3 + (seed % 40) / 100), cy = h * (0.32 + (seed % 30) / 100);
    for (let k = 0; k < 3; k++) {
      const p = ((t * 0.45 + k / 3) % 1);
      ctx.strokeStyle = A(accent, 0.42 * (1 - p)); ctx.lineWidth = 2 * (1 - p) + 0.6;
      ctx.beginPath(); ctx.arc(cx, cy, p * Math.min(w, h) * 0.45, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.fillStyle = A(accent, 0.9);
    ctx.beginPath(); ctx.arc(cx, cy, 5.5, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = A(accent, 0.9); ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(cx, cy + 5); ctx.lineTo(cx, cy + 16); ctx.stroke();
    // a van running the route to the pin
    const s = (t * 0.14) % 1;
    const rx = w * 0.05 + (cx - w * 0.05) * s, ry = h * 0.92 + (cy + 16 - h * 0.92) * s;
    ctx.strokeStyle = A(accent, 0.3); ctx.setLineDash([8, 8]); ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.moveTo(w * 0.05, h * 0.92); ctx.lineTo(cx, cy + 16); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = A(accent, 0.8);
    ctx.fillRect(rx - 4, ry - 3, 9, 6);
  }, [accent, address, brand]);

  return (
    <div className="relative rounded-[var(--tr)] border border-[var(--tbd)] p-4 overflow-hidden" data-testid="industry-map">
      <div className="text-[10px] uppercase tracking-[0.18em] opacity-60">Where to find us</div>
      <canvas ref={ref} className="w-full h-[190px] block mt-2" data-testid="industry-map-canvas" />
      <div className="mt-3 text-sm font-semibold">{brand}</div>
      <div className="text-xs opacity-70 pb-12 sm:pb-0" data-testid="industry-map-address">{address || "Address on request"}</div>
    </div>
  );
}

export default function IndustryVitals({ templateKey = "", industry = "", accent = "#10B981", brand = "", address = "" }) {
  const seed = seedOf(templateKey || industry || brand);
  const variant = VARIANTS[seed % VARIANTS.length];
  return (
    <section className="px-6 sm:px-10 py-14 border-t border-[var(--tbd)]" data-testid="industry-vitals"
      data-industry={industry} style={{ background: "var(--tbg)", color: "var(--tbody)" }}>
      <div className="text-[10px] uppercase tracking-[0.22em] opacity-60">Live performance</div>
      <h2 className="mt-2 font-display text-2xl sm:text-3xl font-semibold tracking-tight" style={{ fontFamily: "var(--tfh)" }}>
        {industry || "This month"} at a glance
      </h2>
      <div className="mt-6 grid md:grid-cols-3 gap-4">
        <LiveChart variant={variant} accent={accent} seed={seed} label={`${industry || "Demand"} trend`} />
        <LiveChart variant={VARIANTS[(seed + 4) % VARIANTS.length]} accent={accent} seed={seed + 91} label="Service mix" />
        <LocationMap accent={accent} address={address} brand={brand} />
      </div>
    </section>
  );
}
