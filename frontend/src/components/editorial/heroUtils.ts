/** Shared primitives for the signature hero motion engines. */

export type Draw = (ctx: CanvasRenderingContext2D, w: number, h: number, t: number) => void;
export type Engine = (accent: string, mobile: boolean) => Draw;

/** accent + alpha (0..1) as an 8-digit hex. */
export const A = (c: string, a: number) => {
  const hex = (c || "#10B981").slice(0, 7);
  const v = Math.max(0, Math.min(1, a));
  return hex + Math.round(v * 255).toString(16).padStart(2, "0");
};

/** Deterministic pseudo-random so every reload paints the same composition. */
export const rng = (seed: number) => {
  let s = seed * 9301 + 49297;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
};

// Aggressive editorial easings (the CSS cubic-beziers, as functions).
export const easeOutExpo = (x: number) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x));
export const easeOutBack = (x: number) => 1 + 2.2 * Math.pow(x - 1, 3) + 1.6 * Math.pow(x - 1, 2);
export const easeInOutQuint = (x: number) =>
  x < 0.5 ? 16 * x * x * x * x * x : 1 - Math.pow(-2 * x + 2, 5) / 2;
export const easeOutElastic = (x: number) =>
  x === 0 || x === 1 ? x : Math.pow(2, -9 * x) * Math.sin((x * 10 - 0.75) * ((2 * Math.PI) / 3)) + 1;

/** Looping 0..1 progress with a per-index stagger of 60-100ms. */
export const loop = (t: number, dur: number, i = 0, stagger = 0.08) => {
  const p = ((t - i * stagger) % dur) / dur;
  return p < 0 ? 0 : p;
};

export const dens = (n: number, mobile: boolean) => Math.max(2, Math.round(n * (mobile ? 0.5 : 1)));

export const roundRect = (
  ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number,
) => {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
};

export const dashedPath = (
  ctx: CanvasRenderingContext2D, pts: [number, number][], dash: number[], offset: number,
) => {
  ctx.setLineDash(dash);
  ctx.lineDashOffset = -offset;
  ctx.beginPath();
  pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.lineDashOffset = 0;
};

/** Point on a quadratic curve — used by the ribbon / route / pipe engines. */
export const quadAt = (
  p0: [number, number], p1: [number, number], p2: [number, number], s: number,
): [number, number] => {
  const k = 1 - s;
  return [
    k * k * p0[0] + 2 * k * s * p1[0] + s * s * p2[0],
    k * k * p0[1] + 2 * k * s * p1[1] + s * s * p2[1],
  ];
};

export const softGlow = (
  ctx: CanvasRenderingContext2D, x: number, y: number, r: number, accent: string, a: number,
) => {
  const g = ctx.createRadialGradient(x, y, 0, x, y, Math.max(1, r));
  g.addColorStop(0, A(accent, a));
  g.addColorStop(1, A(accent, 0));
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(x, y, Math.max(1, r), 0, Math.PI * 2);
  ctx.fill();
};
