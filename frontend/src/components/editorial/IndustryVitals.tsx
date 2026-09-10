import { useEffect, useRef } from "react";

/** Per-industry live charts + located map, driven by the tenant's real vitals payload
 *  (editable in Site Mode, importable from Excel/CSV). Canvas, one 30fps loop, paused off-screen. */
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

const fmt = (n: number) => {
  const a = Math.abs(n);
  if (a >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (a >= 1000) return `${(n / 1000).toFixed(a >= 10000 ? 0 : 1)}k`;
  return `${Math.round(n * 10) / 10}`;
};

/** One chart, drawn from real numbers. `variant` keeps every industry visually distinct. */
export function LiveChart({ variant, accent, label, values = [], labels = [], testid = "industry-chart" }) {
  const ref = useRef(null);
  const nums = (values || []).map(Number).filter(n => Number.isFinite(n));
  const max = Math.max(...nums, 1), min = Math.min(...nums, 0);
  const span = max - min || 1;
  const norm = nums.map(n => 0.12 + 0.88 * ((n - min) / span));

  useLoop(ref, (ctx, w, h, t) => {
    if (!norm.length) return;
    const grow = Math.min(1, t / 0.9);
    // a hair of live drift so the figure feels alive without misreporting the number
    const v = norm.map((d, i) => Math.max(0.06, Math.min(1, d * (0.985 + 0.015 * Math.sin(t * 0.9 + i * 0.7)))));
    const pad = 16, bottom = 22, iw = w - pad * 2, ih = h - pad - bottom;
    const px = (i: number) => pad + (v.length > 1 ? (iw * i) / (v.length - 1) : iw / 2);
    const py = (y: number) => h - bottom - y * ih * grow;
    ctx.strokeStyle = A(accent, 0.5); ctx.fillStyle = A(accent, 0.18); ctx.lineWidth = 2;
    ctx.font = "9px ui-monospace, monospace"; ctx.textAlign = "center";

    const axis = (n: number) => {
      ctx.fillStyle = A(accent, 0.55);
      const stride = Math.ceil(n / 6);
      for (let i = 0; i < n; i += stride) if (labels[i]) ctx.fillText(String(labels[i]).slice(0, 7), px(i), h - 6);
    };

    if (variant === "area" || variant === "step" || variant === "wave") {
      ctx.beginPath(); ctx.moveTo(pad, h - bottom);
      v.forEach((y, i) => {
        if (variant === "step" && i) ctx.lineTo(px(i), py(v[i - 1]));
        ctx.lineTo(px(i), py(variant === "wave" ? y * (0.9 + 0.1 * Math.sin(t * 1.6 + i)) : y));
      });
      ctx.lineTo(px(v.length - 1), h - bottom); ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.fillStyle = A(accent, 0.95);
      const li = v.length - 1;
      ctx.beginPath(); ctx.arc(px(li), py(v[li]), 3.4, 0, Math.PI * 2); ctx.fill();
      ctx.fillText(fmt(nums[li]), Math.min(w - 16, px(li)), py(v[li]) - 8);
      axis(v.length);
    } else if (variant === "bars" || variant === "stacked" || variant === "candles") {
      const bw = iw / v.length;
      v.forEach((y, i) => {
        const x = pad + i * bw + bw * 0.18, bh = y * ih * grow;
        ctx.fillStyle = A(accent, 0.3 + y * 0.4);
        if (variant === "candles") {
          ctx.fillRect(x + bw * 0.28, h - bottom - bh, Math.max(1.5, bw * 0.08), bh);
          ctx.fillRect(x, h - bottom - bh * 0.72, bw * 0.64, bh * 0.44);
        } else if (variant === "stacked") {
          ctx.fillRect(x, h - bottom - bh, bw * 0.64, bh * 0.62);
          ctx.fillStyle = A(accent, 0.18);
          ctx.fillRect(x, h - bottom - bh * 0.38, bw * 0.64, bh * 0.38);
        } else ctx.fillRect(x, h - bottom - bh, bw * 0.64, bh);
      });
      axis(v.length);
    } else if (variant === "donut" || variant === "gauge") {
      const total = nums.reduce((a, b) => a + Math.abs(b), 0) || 1;
      const cx = w / 2, cy = variant === "gauge" ? h * 0.76 : h / 2 - 4;
      const R = Math.min(w, h) * (variant === "gauge" ? 0.4 : 0.3);
      const arcSpan = variant === "gauge" ? Math.PI : Math.PI * 2, base = variant === "gauge" ? Math.PI : -Math.PI / 2;
      ctx.lineWidth = Math.max(9, R * 0.3);
      let acc = 0;
      nums.forEach((n, i) => {
        const frac = (Math.abs(n) / total) * arcSpan * grow;
        ctx.strokeStyle = A(accent, 0.24 + (i % 5) * 0.15);
        ctx.beginPath(); ctx.arc(cx, cy, R, base + acc, base + acc + frac); ctx.stroke();
        acc += frac;
      });
      ctx.fillStyle = A(accent, 0.9); ctx.font = "600 13px ui-monospace, monospace";
      ctx.fillText(variant === "gauge" ? fmt(nums[nums.length - 1]) : fmt(total), cx, variant === "gauge" ? cy - 6 : cy + 4);
      ctx.font = "9px ui-monospace, monospace"; ctx.fillStyle = A(accent, 0.6);
      if (labels[0]) ctx.fillText(labels.slice(0, 3).join(" · ").slice(0, 34), w / 2, h - 6);
    } else if (variant === "radar") {
      const cx = w / 2, cy = h / 2 - 4, R = Math.min(w, h) * 0.34, n = Math.max(3, v.length);
      ctx.strokeStyle = A(accent, 0.16);
      for (let ring = 1; ring <= 3; ring++) {
        ctx.beginPath();
        for (let i = 0; i <= n; i++) {
          const a = (i / n) * Math.PI * 2 - Math.PI / 2;
          ctx.lineTo(cx + Math.cos(a) * R * (ring / 3), cy + Math.sin(a) * R * (ring / 3));
        }
        ctx.stroke();
      }
      ctx.strokeStyle = A(accent, 0.65); ctx.fillStyle = A(accent, 0.2);
      ctx.beginPath();
      for (let i = 0; i <= n; i++) {
        const a = (i / n) * Math.PI * 2 - Math.PI / 2, y = v[i % v.length];
        ctx.lineTo(cx + Math.cos(a) * R * y * grow, cy + Math.sin(a) * R * y * grow);
      }
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.fillStyle = A(accent, 0.6);
      if (labels[0]) ctx.fillText(labels.slice(0, 3).join(" · ").slice(0, 34), w / 2, h - 6);
    } else {
      v.forEach((y, i) => {
        ctx.fillStyle = A(accent, 0.18 + y * 0.32);
        ctx.beginPath(); ctx.arc(px(i), py(y), 4 + y * 13 * grow, 0, Math.PI * 2); ctx.fill();
      });
      axis(v.length);
    }
  }, [variant, accent, JSON.stringify(nums), JSON.stringify(labels)]);

  return (
    <div className="relative rounded-[var(--tr)] border border-[var(--tbd)] p-4 overflow-hidden"
      data-testid={testid} data-chart-variant={variant} data-chart-points={nums.length}>
      <div className="flex items-baseline justify-between gap-2">
        <div className="text-[10px] uppercase tracking-[0.18em] opacity-60">{label}</div>
        <div className="text-[10px] font-mono opacity-45">{nums.length} pts</div>
      </div>
      <canvas ref={ref} className="w-full h-[190px] block mt-2" data-testid={`${testid}-canvas`} />
    </div>
  );
}

function LocationMap({ accent, address, brand }) {
  const ref = useRef(null);
  const seed = seedOf(address || brand);
  useLoop(ref, (ctx, w, h, t) => {
    const r = rand(seed);
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
    ctx.fillStyle = A(accent, 0.05);
    for (let i = 0; i < 14; i++) ctx.fillRect(r() * w, r() * h, 20 + r() * 60, 14 + r() * 40);
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

export default function IndustryVitals({ templateKey = "", industry = "", accent = "#10B981", brand = "", address = "", vitals = null }) {
  const v = vitals || {};
  const metrics = (v.metrics || []).slice(0, 3);
  const variants = v.variants || ["area", "donut"];
  return (
    <section className="px-6 sm:px-10 py-14 border-t border-[var(--tbd)]" data-testid="industry-vitals"
      data-industry={industry} data-template={templateKey} data-vitals-source={v.source || "demo"}
      style={{ background: "var(--tbg)", color: "var(--tbody)" }}>
      <div className="text-[10px] uppercase tracking-[0.22em] opacity-60">{v.title || "Live performance"}</div>
      <h2 className="mt-2 font-display text-2xl sm:text-3xl font-semibold tracking-tight" style={{ fontFamily: "var(--tfh)" }}>
        {industry || "This month"} at a glance
      </h2>

      {metrics.length > 0 && (
        <div className="mt-6 grid sm:grid-cols-3 gap-4" data-testid="industry-metrics">
          {metrics.map((m, i) => (
            <div key={m.label || i} className="rounded-[var(--tr)] border border-[var(--tbd)] p-5"
              data-testid={`industry-metric-${i}`}>
              <div className="text-3xl sm:text-4xl font-semibold tracking-tight" style={{ color: accent }}
                data-testid={`industry-metric-value-${i}`}>
                {`${m.prefix || ""}${m.value}${m.suffix || ""}`}
              </div>
              <div className="mt-1.5 text-xs uppercase tracking-[0.16em] opacity-65">{m.label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 grid md:grid-cols-3 gap-4">
        <LiveChart variant={variants[0]} accent={accent} label={v.series_label || "Trend"}
          values={v.series || []} labels={v.labels || []} testid="industry-chart" />
        <LiveChart variant={variants[1]} accent={accent} label={v.series2_label || "Service mix"}
          values={v.series2 || []} labels={v.labels2 || []} testid="industry-chart-2" />
        <LocationMap accent={accent} address={address} brand={brand} />
      </div>
    </section>
  );
}
