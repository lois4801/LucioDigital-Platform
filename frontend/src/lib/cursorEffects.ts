// Cursor Effects Engine — 10 canvas particle trails. Shared config + renderer.
export const CURSOR_EFFECTS = [
  { id: "none", name: "None", hint: "Plain cursor", swatch: ["#64748B", "#334155"] },
  { id: "fairy", name: "Fairy Dust", hint: "Glowing rotating stardust", swatch: ["#FDE68A", "#C084FC"] },
  { id: "bubbles", name: "Water Bubbles", hint: "Iridescent floating droplets", swatch: ["#7DD3FC", "#A7F3D0"] },
  { id: "smoke", name: "Mystic Smoke", hint: "Billowing dissolving fog", swatch: ["#94A3B8", "#1E293B"] },
  { id: "fire", name: "Fire & Embers", hint: "Sparking micro-flames", swatch: ["#FDBA74", "#DC2626"] },
  { id: "wind", name: "Wind & Petals", hint: "Drifting wisps and leaves", swatch: ["#FBCFE8", "#86EFAC"] },
  { id: "frost", name: "Frost & Snowfall", hint: "Ice crystals and snowflakes", swatch: ["#BAE6FD", "#E0F2FE"] },
  { id: "plasma", name: "Neon Plasma", hint: "High-voltage lightning arcs", swatch: ["#22D3EE", "#A855F7"] },
  { id: "ink", name: "Liquid Ink", hint: "Fluid merging paint drops", swatch: ["#6366F1", "#0EA5E9"] },
  { id: "comet", name: "Cosmic Comet", hint: "Gravitational stardust tail", swatch: ["#FDE68A", "#312E81"] },
  { id: "matrix", name: "Digital Matrix", hint: "Falling binary rain", swatch: ["#22C55E", "#052E16"] },
];

export const EFFECT_IDS = CURSOR_EFFECTS.map(e => e.id);
export const isEffect = (v) => EFFECT_IDS.includes(v);
export const DEFAULT_EFFECT = "bubbles";
export const swatchOf = (id) => (CURSOR_EFFECTS.find(e => e.id === id) || CURSOR_EFFECTS[0]).swatch;

// Lets UI (e.g. auth forms) emit the active effect at a point. Set by startCursorFX.
let emitter = null;
let lastBurst = 0;
export function burstCursorFX(x, y, n = 8) {
  const now = performance.now();
  if (!emitter || now - lastBurst < 70) return;   // throttled so bursts never flood the loop
  lastBurst = now;
  emitter(x, y, Math.max(1, Math.min(14, n)));
}

// Unthrottled single-point emission — used by the ambient auth-form emitters.
export function emitCursorFX(x, y, n = 1) {
  if (emitter) emitter(x, y, Math.max(1, Math.min(6, n)));
}
export function cursorFXActive() { return !!emitter; }

const rand = (a, b) => a + Math.random() * (b - a);
const TAU = Math.PI * 2;

// per-effect particles spawned each pointer sample
const SPAWN = { fairy: 1, bubbles: 1, smoke: 1, fire: 2, wind: 1, frost: 1, plasma: 1, ink: 1, comet: 2, matrix: 1 };
const MAX = 170;

function makeParticle(effect, x, y, vx, vy) {
  const speed = Math.hypot(vx, vy);
  switch (effect) {
    case "fairy":
      return { x: x + rand(-6, 6), y: y + rand(-6, 6), vx: rand(-0.4, 0.4), vy: rand(-0.9, -0.2), life: 1, decay: rand(0.012, 0.024), size: rand(3, 7), rot: rand(0, TAU), vr: rand(-0.09, 0.09), hue: rand(38, 300) };
    case "bubbles":
      return { x: x + rand(-10, 10), y: y + rand(-8, 8), vx: rand(-0.35, 0.35), vy: rand(-1.2, -0.45), life: 1, decay: rand(0.006, 0.014), size: rand(4, 13), hue: rand(170, 215), wob: rand(0, TAU) };
    case "smoke":
      return { x: x + rand(-8, 8), y: y + rand(-8, 8), vx: rand(-0.35, 0.35) + vx * 0.05, vy: rand(-0.7, -0.15), life: 1, decay: rand(0.006, 0.013), size: rand(16, 34), grow: rand(0.35, 0.9) };
    case "fire":
      return { x: x + rand(-5, 5), y: y + rand(-4, 4), vx: rand(-0.5, 0.5), vy: rand(-2.2, -0.8), life: 1, decay: rand(0.02, 0.045), size: rand(2.5, 7), ember: Math.random() < 0.25 };
    case "wind":
      return { x: x + rand(-14, 14), y: y + rand(-10, 10), vx: rand(0.4, 1.8), vy: rand(0.15, 0.8), life: 1, decay: rand(0.005, 0.011), size: rand(4, 9), rot: rand(0, TAU), vr: rand(-0.06, 0.06), sway: rand(0, TAU), petal: Math.random() < 0.55, hue: rand(320, 360) };
    case "frost":
      return { x: x + rand(-12, 12), y: y + rand(-10, 10), vx: rand(-0.3, 0.3), vy: rand(0.3, 1.1), life: 1, decay: rand(0.005, 0.011), size: rand(4, 10), rot: rand(0, TAU), vr: rand(-0.04, 0.04), sway: rand(0, TAU), shard: Math.random() < 0.4 };
    case "plasma":
      return { x, y, vx: 0, vy: 0, life: 1, decay: rand(0.07, 0.14), size: Math.max(18, Math.min(90, speed * 4)), seed: Math.random() * 999, hue: rand(170, 300) };
    case "ink":
      return { x: x + rand(-7, 7), y: y + rand(-7, 7), vx: vx * 0.08 + rand(-0.3, 0.3), vy: vy * 0.08 + rand(0.1, 0.7), life: 1, decay: rand(0.004, 0.009), size: rand(6, 20), grow: rand(0.1, 0.5), hue: rand(190, 270) };
    case "comet":
      return { x: x + rand(-3, 3), y: y + rand(-3, 3), vx: -vx * rand(0.05, 0.2) + rand(-0.4, 0.4), vy: -vy * rand(0.05, 0.2) + rand(-0.4, 0.4), life: 1, decay: rand(0.012, 0.03), size: rand(1, 3.4), star: Math.random() < 0.15, hue: rand(35, 60) };
    case "matrix":
      return { x: Math.round((x + rand(-16, 16)) / 12) * 12, y: y + rand(-8, 8), vx: 0, vy: rand(2.2, 5.2), life: 1, decay: rand(0.012, 0.026), size: 13, glyph: Math.random() < 0.5 ? "0" : "1" };
    default:
      return null;
  }
}

function step(effect, p) {
  p.x += p.vx; p.y += p.vy; p.life -= p.decay;
  if (p.rot !== undefined) p.rot += p.vr;
  switch (effect) {
    case "fairy": p.vy -= 0.006; p.vx *= 0.99; break;
    case "bubbles": p.wob += 0.13; p.x += Math.sin(p.wob) * 0.5; p.vy *= 0.995; break;
    case "smoke": p.size += p.grow; p.vy -= 0.004; p.vx *= 0.99; break;
    case "fire": p.vy -= 0.03; p.vx *= 0.97; p.size *= 0.985; break;
    case "wind": p.sway += 0.06; p.y += Math.sin(p.sway) * 0.7; p.vx *= 0.995; break;
    case "frost": p.sway += 0.05; p.x += Math.sin(p.sway) * 0.6; break;
    case "ink": p.size += p.grow; p.vy += 0.02; p.vx *= 0.96; break;
    case "comet": p.vx *= 0.97; p.vy *= 0.97; break;
    default: break;
  }
}

function star(ctx, r, points = 4) {
  ctx.beginPath();
  for (let i = 0; i < points * 2; i++) {
    const rad = i % 2 === 0 ? r : r * 0.36;
    const a = (i * Math.PI) / points;
    ctx[i ? "lineTo" : "moveTo"](Math.cos(a) * rad, Math.sin(a) * rad);
  }
  ctx.closePath();
}

function draw(ctx, effect, p, accent) {
  const a = Math.max(0, Math.min(1, p.life));
  ctx.save();
  switch (effect) {
    case "fairy": {
      ctx.translate(p.x, p.y); ctx.rotate(p.rot);
      // No shadowBlur: additive compositing gives the glow at a fraction of the cost.
      ctx.fillStyle = `hsla(${p.hue},95%,${68 + 18 * (1 - a)}%,${a})`;
      star(ctx, p.size); ctx.fill();
      break;
    }
    case "bubbles": {
      // Cheap two-pass bubble (no per-frame gradient allocation).
      ctx.globalAlpha = a * 0.75;
      ctx.fillStyle = `hsla(${p.hue},90%,72%,0.30)`;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.size, 0, TAU); ctx.fill();
      ctx.strokeStyle = `hsla(${p.hue},95%,85%,${a * 0.55})`; ctx.lineWidth = 1; ctx.stroke();
      ctx.fillStyle = `rgba(255,255,255,${a * 0.5})`;
      ctx.beginPath(); ctx.arc(p.x - p.size * 0.3, p.y - p.size * 0.35, Math.max(0.6, p.size * 0.18), 0, TAU); ctx.fill();
      break;
    }
    case "smoke": {
      ctx.globalAlpha = a * 0.10;
      ctx.fillStyle = "rgb(170,188,210)";
      ctx.beginPath(); ctx.arc(p.x, p.y, p.size, 0, TAU); ctx.fill();
      break;
    }
    case "fire": {
      const hue = p.ember ? 24 : 18 + 40 * a;
      ctx.fillStyle = p.ember ? `hsla(30,100%,${55 + 20 * a}%,${a})` : `hsla(${hue},100%,${45 + 35 * a}%,${a})`;
      ctx.beginPath(); ctx.ellipse(p.x, p.y, p.size * 0.7, p.size * 1.25, 0, 0, TAU); ctx.fill();
      break;
    }
    case "wind": {
      ctx.translate(p.x, p.y); ctx.rotate(p.rot); ctx.globalAlpha = a;
      if (p.petal) {
        ctx.fillStyle = `hsla(${p.hue},85%,82%,${a})`;
        ctx.beginPath(); ctx.ellipse(0, 0, p.size, p.size * 0.45, 0, 0, TAU); ctx.fill();
      } else {
        ctx.strokeStyle = `rgba(226,240,255,${a * 0.6})`; ctx.lineWidth = 1.4;
        ctx.beginPath(); ctx.moveTo(-p.size * 1.8, 0); ctx.quadraticCurveTo(0, -p.size * 0.9, p.size * 1.8, 0); ctx.stroke();
      }
      break;
    }
    case "frost": {
      ctx.translate(p.x, p.y); ctx.rotate(p.rot);
      ctx.strokeStyle = `rgba(224,242,254,${a})`; ctx.lineWidth = 1.3;
      if (p.shard) { star(ctx, p.size, 3); ctx.fillStyle = `rgba(186,230,253,${a * 0.5})`; ctx.fill(); ctx.stroke(); }
      else {
        for (let i = 0; i < 6; i++) {
          const ang = (i * Math.PI) / 3;
          ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(Math.cos(ang) * p.size, Math.sin(ang) * p.size);
          ctx.moveTo(Math.cos(ang) * p.size * 0.6, Math.sin(ang) * p.size * 0.6);
          ctx.lineTo(Math.cos(ang + 0.5) * p.size * 0.85, Math.sin(ang + 0.5) * p.size * 0.85);
          ctx.stroke();
        }
      }
      break;
    }
    case "plasma": {
      ctx.globalAlpha = a;
      ctx.strokeStyle = `hsla(${p.hue},100%,${70 + 20 * a}%,${a})`; ctx.lineWidth = 1.8;
      ctx.beginPath(); ctx.moveTo(p.x, p.y);
      let x = p.x, y = p.y;
      for (let i = 0; i < 5; i++) {
        x += Math.sin(p.seed + i * 2.1) * (p.size / 4) + rand(-6, 6);
        y += Math.cos(p.seed + i * 1.7) * (p.size / 4) + rand(-6, 6);
        ctx.lineTo(x, y);
      }
      ctx.stroke();
      break;
    }
    case "ink": {
      ctx.globalAlpha = a * 0.5;
      ctx.fillStyle = `hsla(${p.hue},85%,58%,1)`;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.size, 0, TAU); ctx.fill();
      break;
    }
    case "comet": {
      ctx.globalAlpha = a;
      ctx.fillStyle = p.star ? "#FFFFFF" : `hsla(${p.hue},100%,${72 + 20 * (1 - a)}%,1)`;
      if (p.star) { ctx.translate(p.x, p.y); star(ctx, p.size * 2.2); ctx.fill(); }
      else { ctx.beginPath(); ctx.arc(p.x, p.y, p.size, 0, TAU); ctx.fill(); }
      break;
    }
    case "matrix": {
      ctx.globalAlpha = a;
      ctx.font = `700 ${p.size}px 'JetBrains Mono', ui-monospace, monospace`;
      ctx.fillStyle = a > 0.85 ? "#DCFCE7" : "#22C55E";
      ctx.fillText(p.glyph, p.x, p.y);
      break;
    }
    default: break;
  }
  ctx.restore();
  void accent;
}

// Scoped variant: particles live inside one element's box (auth panel) and are clipped to it.
// Returns { emit(x, y, n), stop() } with coordinates local to the canvas.
export function startScopedCursorFX(canvas, effect, opts = {}) {
  const density = Math.max(0.2, Math.min(3, Number(opts.density) || 1));
  const speed = Math.max(0.2, Math.min(3, Number(opts.speed) || 1));
  const bandMax = Math.max(0, Number(opts.sideBand) || 0);   // only these left/right gutters are drawn
  let band = bandMax;
  const ctx = canvas.getContext("2d");
  let w = 0, h = 0;
  const resize = () => {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const r = canvas.getBoundingClientRect();
    w = r.width; h = r.height;
    band = Math.min(bandMax, w * 0.14);   // narrower gutters on small screens
    canvas.width = Math.max(1, Math.round(w * dpr));
    canvas.height = Math.max(1, Math.round(h * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };
  resize();
  const ro = new ResizeObserver(resize);
  ro.observe(canvas);

  const parts = [];
  const MAX_SCOPED = 90;
  const emit = (x, y, n = 1) => {
    for (let i = 0; i < n; i++) {
      if (parts.length >= MAX_SCOPED) break;
      const p = makeParticle(effect, x, y, rand(-6, 6), rand(-6, 6));
      if (!p) continue;
      p.size *= 0.6 + 0.4 * density;
      p.vx *= speed; p.vy *= speed; p.decay *= speed;
      parts.push(p);
    }
  };

  let raf = 0;
  const loop = () => {
    if (!document.hidden) {
      ctx.clearRect(0, 0, w, h);
      ctx.save();
      if (band > 0) {
        // Draw only inside the left/right gutters so the centre stays readable.
        ctx.beginPath();
        ctx.rect(0, 0, band, h);
        ctx.rect(w - band, 0, band, h);
        ctx.clip();
      }
      ctx.globalCompositeOperation = effect === "ink" || effect === "smoke" ? "source-over" : "lighter";
      for (let i = parts.length - 1; i >= 0; i--) {
        const p = parts[i];
        step(effect, p);
        // Fade anything that wanders past the panel edges so nothing escapes the perimeter.
        if (p.life <= 0 || p.y < -20 || p.y > h + 20 || p.x < -20 || p.x > w + 20) { parts.splice(i, 1); continue; }
        draw(ctx, effect, p, "#10B981");
      }
      ctx.globalCompositeOperation = "source-over";
      ctx.restore();
    }
    raf = requestAnimationFrame(loop);
  };
  raf = requestAnimationFrame(loop);

  return {
    emit,
    stop: () => { ro.disconnect(); cancelAnimationFrame(raf); ctx.clearRect(0, 0, w, h); },
  };
}
export function startCursorFX(canvas, effect, accent = "#10B981", opts = {}) {
  const density = Math.max(0.2, Math.min(3, Number(opts.density) || 1));
  const speed = Math.max(0.2, Math.min(3, Number(opts.speed) || 1));
  const ctx = canvas.getContext("2d");
  let dpr = Math.min(window.devicePixelRatio || 1, 2);
  const resize = () => {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = innerWidth * dpr; canvas.height = innerHeight * dpr;
    canvas.style.width = `${innerWidth}px`; canvas.style.height = `${innerHeight}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };
  resize();

  const parts = [];
  let last = null, raf = 0;
  const onMove = (e) => {
    const vx = last ? e.clientX - last.x : 0, vy = last ? e.clientY - last.y : 0;
    last = { x: e.clientX, y: e.clientY };
    const n = Math.max(1, Math.round((SPAWN[effect] || 1) * density));
    for (let i = 0; i < n; i++) {
      if (parts.length >= MAX) break;
      const p = makeParticle(effect, e.clientX, e.clientY, vx, vy);
      if (!p) continue;
      p.size *= 0.6 + 0.4 * density;
      p.vx *= speed; p.vy *= speed; p.decay *= speed;
      parts.push(p);
    }
  };

  const loop = () => {
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    ctx.globalCompositeOperation = effect === "ink" || effect === "smoke" ? "source-over" : "lighter";
    for (let i = parts.length - 1; i >= 0; i--) {
      const p = parts[i];
      step(effect, p);
      if (p.life <= 0 || p.y < -80 || p.y > innerHeight + 120) { parts.splice(i, 1); continue; }
      draw(ctx, effect, p, accent);
    }
    ctx.globalCompositeOperation = "source-over";
    raf = requestAnimationFrame(loop);
  };

  const spawnAt = (x, y, n) => {
    for (let i = 0; i < n; i++) {
      if (parts.length >= MAX) break;
      const p = makeParticle(effect, x, y, rand(-6, 6), rand(-6, 6));
      if (!p) continue;
      p.size *= 0.6 + 0.4 * density;
      p.vx *= speed; p.vy *= speed; p.decay *= speed;
      parts.push(p);
    }
  };
  emitter = spawnAt;

  window.addEventListener("mousemove", onMove, { passive: true });
  window.addEventListener("resize", resize);
  raf = requestAnimationFrame(loop);
  return () => {
    if (emitter === spawnAt) emitter = null;
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("resize", resize);
    cancelAnimationFrame(raf);
    ctx.clearRect(0, 0, innerWidth, innerHeight);
  };
}
