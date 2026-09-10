/** Bespoke hero engines — reserved industry profiles + the platform-exclusive hero. */
import {
  A, Engine, dens, easeOutBack, easeOutExpo, loop, rng, roundRect, softGlow,
} from "./heroUtils";

/** tech_code — katakana code rain in columns of varying speed. */
const matrixCodeRain: Engine = (accent, mobile) => {
  const cols = dens(26, mobile);
  const r = rng(101);
  const lanes = Array.from({ length: cols }, () => ({ y: r(), sp: 0.25 + r() * 0.7, len: 6 + Math.floor(r() * 12) }));
  return (ctx, w, h, t) => {
    const cw = w / cols;
    ctx.font = `${mobile ? 11 : 13}px ui-monospace, monospace`;
    lanes.forEach((l, i) => {
      const head = ((l.y + t * l.sp * 0.25) % 1.2) * h;
      for (let k = 0; k < l.len; k++) {
        const y = head - k * 16;
        if (y < -16 || y > h + 16) continue;
        const ch = String.fromCharCode(0x30a0 + ((i * 7 + k * 13 + Math.floor(t * 8)) % 90));
        ctx.fillStyle = A(accent, k === 0 ? 0.85 : Math.max(0, 0.35 - k * 0.03));
        ctx.fillText(ch, i * cw + 2, y);
      }
    });
  };
};

/** medical — a double helix rotating with base-pair rungs. */
const dnaHelixRotation: Engine = (accent, mobile) => {
  const rungs = dens(26, mobile);
  return (ctx, w, h, t) => {
    const cx = w / 2, amp = Math.min(w * 0.18, 130);
    const strand = (phase: number, alpha: number) => {
      ctx.strokeStyle = A(accent, alpha);
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let y = 0; y <= h; y += 6) ctx.lineTo(cx + Math.sin(y / 70 + t * 0.9 + phase) * amp, y);
      ctx.stroke();
    };
    for (let i = 0; i < rungs; i++) {
      const y = ((i + 0.5) / rungs) * h;
      const a = Math.sin(y / 70 + t * 0.9);
      const x1 = cx + a * amp, x2 = cx - a * amp;
      const depth = (Math.cos(y / 70 + t * 0.9) + 1) / 2;
      ctx.strokeStyle = A(accent, 0.1 + depth * 0.24);
      ctx.lineWidth = 1 + depth * 1.4;
      ctx.beginPath(); ctx.moveTo(x1, y); ctx.lineTo(x2, y); ctx.stroke();
      ctx.fillStyle = A(accent, 0.3 + depth * 0.35);
      ctx.beginPath(); ctx.arc(x1, y, 2.4, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(x2, y, 2.4, 0, Math.PI * 2); ctx.fill();
    }
    strand(0, 0.4); strand(Math.PI, 0.22);
  };
};

/** sports — a crowd wave rolling through the stands. */
const stadiumWaveRipple: Engine = (accent, mobile) => {
  const cols = dens(30, mobile), rows = dens(8, mobile);
  return (ctx, w, h, t) => {
    const cw = w / cols, ch = (h * 0.7) / rows;
    for (let c = 0; c < cols; c++) {
      const k = Math.sin((c / cols) * Math.PI * 2 - t * 1.8);
      const lift = Math.max(0, k) ** 2;
      for (let r2 = 0; r2 < rows; r2++) {
        const x = c * cw + cw / 2;
        const y = h * 0.22 + r2 * ch - lift * 22;
        ctx.fillStyle = A(accent, 0.1 + lift * 0.4);
        ctx.beginPath(); ctx.arc(x, y, Math.min(cw, ch) * 0.26, 0, Math.PI * 2); ctx.fill();
      }
    }
  };
};

/** fashion — magazine spreads flipping over the gutter. */
const editorialMagazineFlip: Engine = (accent, mobile) => {
  const n = dens(5, mobile);
  return (ctx, w, h, t) => {
    const gx = w * 0.5, pw = w * 0.3, ph = h * 0.62;
    ctx.strokeStyle = A(accent, 0.16);
    ctx.strokeRect(gx - pw, h * 0.19, pw, ph);
    ctx.strokeRect(gx, h * 0.19, pw, ph);
    for (let i = 0; i < n; i++) {
      const p = loop(t, 3.4, i, 0.9);
      const e = easeOutExpo(p);
      const scale = Math.cos(e * Math.PI);
      ctx.save();
      ctx.translate(gx, h * 0.19);
      ctx.transform(scale, 0, 0, 1, 0, 0);
      ctx.fillStyle = A(accent, 0.07 + 0.08 * Math.abs(scale));
      ctx.strokeStyle = A(accent, 0.3);
      ctx.fillRect(scale > 0 ? 0 : -pw, 0, pw, ph);
      ctx.strokeRect(scale > 0 ? 0 : -pw, 0, pw, ph);
      ctx.restore();
    }
  };
};

/** internal_tools — a terminal typing itself out line by line. */
const commandLineTypeOn: Engine = (accent, mobile) => {
  const lines = ["$ lt deploy --tenant acme", "› building 42 modules", "› migrating schema", "✓ live in 1.8s", "$ lt status --watch"];
  return (ctx, w, h, t) => {
    ctx.font = `${mobile ? 12 : 15}px ui-monospace, monospace`;
    const cyc = (t * 0.35) % (lines.length + 1.5);
    lines.forEach((ln, i) => {
      const rel = cyc - i;
      if (rel <= 0) return;
      const chars = Math.min(ln.length, Math.floor(rel * 26));
      ctx.fillStyle = A(accent, i === lines.length - 1 ? 0.5 : 0.32);
      ctx.fillText(ln.slice(0, chars), w * 0.08, h * 0.3 + i * (mobile ? 20 : 26));
      if (chars < ln.length && Math.sin(t * 10) > 0) {
        ctx.fillStyle = A(accent, 0.7);
        ctx.fillRect(w * 0.08 + ctx.measureText(ln.slice(0, chars)).width + 2, h * 0.3 + i * (mobile ? 20 : 26) - 11, 7, 13);
      }
    });
  };
};

/** saas_portals — metric cards cascading with flipping digits. */
const metricCounterCascade: Engine = (accent, mobile) => {
  const n = dens(8, mobile);
  return (ctx, w, h, t) => {
    const cols = mobile ? 2 : 4, cw = w / cols, chh = h / Math.ceil(n / cols);
    for (let i = 0; i < n; i++) {
      const p = easeOutBack(Math.min(1, loop(t, 5, i, 0.08) * 2.2));
      const c = i % cols, r2 = Math.floor(i / cols);
      const x = c * cw + cw * 0.12, y = r2 * chh + chh * 0.18 + (1 - p) * 26;
      ctx.globalAlpha = Math.min(1, p * 1.5);
      ctx.strokeStyle = A(accent, 0.24);
      ctx.fillStyle = A(accent, 0.05);
      roundRect(ctx, x, y, cw * 0.76, chh * 0.62, 8);
      ctx.fill(); ctx.stroke();
      ctx.fillStyle = A(accent, 0.45);
      ctx.font = `600 ${mobile ? 16 : 22}px ui-monospace, monospace`;
      const val = Math.floor(((t * 40 + i * 37) % 1000));
      ctx.fillText(String(val).padStart(3, "0"), x + 14, y + chh * 0.4);
      ctx.globalAlpha = 1;
    }
  };
};

/** art_culture — a gallery spotlight panning across framed works. */
const museumSpotlightPan: Engine = (accent, mobile) => {
  const n = dens(5, mobile);
  return (ctx, w, h, t) => {
    const pan = (Math.sin(t * 0.25) + 1) / 2;
    const sx = pan * w;
    for (let i = 0; i < n; i++) {
      const x = ((i + 0.5) / n) * w;
      const lit = Math.max(0, 1 - Math.abs(x - sx) / (w / n));
      ctx.strokeStyle = A(accent, 0.12 + lit * 0.4);
      ctx.fillStyle = A(accent, 0.03 + lit * 0.1);
      const fw = w / n * 0.5, fh = h * 0.34;
      roundRect(ctx, x - fw / 2, h * 0.32, fw, fh, 2);
      ctx.fill(); ctx.stroke();
    }
    const g = ctx.createLinearGradient(sx, 0, sx, h);
    g.addColorStop(0, A(accent, 0.2));
    g.addColorStop(1, A(accent, 0));
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.moveTo(sx - 20, 0); ctx.lineTo(sx + 20, 0);
    ctx.lineTo(sx + 150, h); ctx.lineTo(sx - 150, h);
    ctx.closePath(); ctx.fill();
  };
};

/** mental_health — slow aurora bands. */
const auroraWave: Engine = (accent, mobile) => {
  const bands = dens(4, mobile);
  return (ctx, w, h, t) => {
    for (let b = 0; b < bands; b++) {
      const g = ctx.createLinearGradient(0, h * 0.2, w, h);
      g.addColorStop(0, A(accent, 0));
      g.addColorStop(0.5, A(accent, 0.14 - b * 0.025));
      g.addColorStop(1, A(accent, 0));
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.moveTo(0, h);
      for (let x = 0; x <= w; x += 12) {
        ctx.lineTo(x, h * (0.24 + b * 0.16) + Math.sin(x / 170 + t * (0.25 + b * 0.12)) * 52
          + Math.sin(x / 60 - t * 0.2) * 14);
      }
      ctx.lineTo(w, h); ctx.closePath(); ctx.fill();
    }
  };
};

/** food_beverage — ingredients tossed in and landing with a bounce. */
const ingredientScatter: Engine = (accent, mobile) => {
  const n = dens(14, mobile);
  const r = rng(103);
  const items = Array.from({ length: n }, () => ({
    x: 0.08 + r() * 0.84, rest: 0.4 + r() * 0.45, s: 8 + r() * 16, rot: r() * 6.28, spin: (r() - 0.5) * 8,
  }));
  return (ctx, w, h, t) => {
    items.forEach((it, i) => {
      const p = loop(t, 4.6, i, 0.09);
      const e = easeOutBack(Math.min(1, p * 1.8));
      const x = it.x * w - (1 - e) * w * 0.2;
      const y = -60 + (it.rest * h + 60) * e;
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(it.rot + it.spin * (1 - e));
      ctx.fillStyle = A(accent, 0.22);
      ctx.beginPath();
      if (i % 3 === 0) ctx.ellipse(0, 0, it.s, it.s * 0.5, 0, 0, Math.PI * 2);
      else if (i % 3 === 1) ctx.arc(0, 0, it.s * 0.6, 0, Math.PI * 2);
      else { roundRect(ctx, -it.s / 2, -it.s / 2, it.s, it.s, 3); }
      ctx.fill();
      ctx.restore();
    });
  };
};

/** property_mgmt — nested floor plates flying toward the viewer. */
const architecturalFlyThrough: Engine = (accent, mobile) => {
  const n = dens(9, mobile);
  return (ctx, w, h, t) => {
    for (let i = 0; i < n; i++) {
      const p = ((t * 0.16) + i / n) % 1;
      const z = easeOutExpo(p);
      const s = 0.1 + z * 1.6;
      const a = 0.3 * (1 - p) * Math.min(1, p * 6);
      ctx.strokeStyle = A(accent, a);
      ctx.lineWidth = 1 + z;
      const bw = w * 0.5 * s, bh = h * 0.42 * s;
      ctx.strokeRect(w / 2 - bw / 2, h / 2 - bh / 2, bw, bh);
      ctx.strokeStyle = A(accent, a * 0.5);
      ctx.beginPath();
      ctx.moveTo(w / 2 - bw / 2, h / 2); ctx.lineTo(w / 2 + bw / 2, h / 2);
      ctx.stroke();
    }
  };
};

/** lois-tech.ca ONLY — drifting product cards with parallax depth. */
const platformDriftCards: Engine = (accent, mobile) => {
  const n = dens(10, mobile);
  const r = rng(2026);
  const cards = Array.from({ length: n }, () => ({
    x: r(), y: r(), s: 60 + r() * 120, sp: 0.4 + r(), ph: r() * 6.28, depth: r(),
  }));
  return (ctx, w, h, t) => {
    cards.forEach((c) => {
      const x = c.x * w + Math.sin(t * 0.28 * c.sp + c.ph) * (20 + c.depth * 46);
      const y = c.y * h + Math.cos(t * 0.22 * c.sp + c.ph) * (14 + c.depth * 30);
      const s = c.s * (0.6 + c.depth * 0.7);
      ctx.strokeStyle = A(accent, 0.1 + c.depth * 0.22);
      ctx.fillStyle = A(accent, 0.03 + c.depth * 0.04);
      roundRect(ctx, x - s / 2, y - s * 0.32, s, s * 0.64, 10);
      ctx.fill(); ctx.stroke();
      if (c.depth > 0.7) softGlow(ctx, x, y, s * 0.8, accent, 0.05);
    });
  };
};

export const RESERVED_ENGINES: Record<string, Engine> = {
  "matrix-code-rain": matrixCodeRain,
  "dna-helix-rotation": dnaHelixRotation,
  "stadium-wave-ripple": stadiumWaveRipple,
  "editorial-magazine-flip": editorialMagazineFlip,
  "command-line-type-on": commandLineTypeOn,
  "metric-counter-cascade": metricCounterCascade,
  "museum-spotlight-pan": museumSpotlightPan,
  "aurora-wave": auroraWave,
  "ingredient-scatter": ingredientScatter,
  "architectural-fly-through": architecturalFlyThrough,
  "platform-drift-cards": platformDriftCards,
};
