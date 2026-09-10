/** Bespoke hero engines — the Studio 2026 pack (17 templates). */
import {
  A, Engine, dashedPath, dens, easeOutBack, easeOutElastic, easeOutExpo, loop, rng, roundRect, softGlow,
} from "./heroUtils";

/** veterinary — paw prints padding across on a diagonal, fading behind. */
const pawPrintTrail: Engine = (accent, mobile) => {
  const n = dens(9, mobile);
  const paw = (ctx: CanvasRenderingContext2D, x: number, y: number, s: number, a: number) => {
    ctx.fillStyle = A(accent, a);
    ctx.beginPath(); ctx.ellipse(x, y, s * 0.9, s * 0.7, 0, 0, Math.PI * 2); ctx.fill();
    for (let k = 0; k < 4; k++) {
      const ang = -Math.PI * 0.85 + k * (Math.PI * 0.23);
      ctx.beginPath();
      ctx.ellipse(x + Math.cos(ang) * s * 1.35, y + Math.sin(ang) * s * 1.35, s * 0.34, s * 0.42, ang, 0, Math.PI * 2);
      ctx.fill();
    }
  };
  return (ctx, w, h, t) => {
    for (let i = 0; i < n; i++) {
      const p = loop(t, 5.2, i, 0.1);
      const fade = p < 0.15 ? p / 0.15 : 1 - (p - 0.15) / 0.85;
      const x = w * (0.06 + (i / n) * 0.9);
      const y = h * (0.82 - (i / n) * 0.6) + (i % 2 ? 18 : -18);
      paw(ctx, x, y, mobile ? 6 : 8, 0.3 * Math.max(0, fade));
    }
  };
};

/** dental — clean bars sliding in from the left with an 8px overshoot. */
const precisionSlideIn: Engine = (accent, mobile) => {
  const n = dens(10, mobile);
  return (ctx, w, h, t) => {
    for (let i = 0; i < n; i++) {
      const p = loop(t, 4, i, 0.07);
      const e = easeOutBack(Math.min(1, p * 2.4));
      const len = w * (0.2 + ((i * 7) % 5) * 0.09);
      const y = h * (0.1 + (i / n) * 0.82);
      ctx.fillStyle = A(accent, 0.16 * Math.min(1, (1 - p) * 3));
      ctx.fillRect(-len + e * (len + w * 0.1), y, len, 3);
    }
  };
};

/** accounting — ruled ledger lines drawing with column ticks. */
const ledgerLineReveal: Engine = (accent, mobile) => {
  const rows = dens(14, mobile);
  return (ctx, w, h, t) => {
    ctx.lineWidth = 1;
    for (let i = 0; i < rows; i++) {
      const p = easeOutExpo(loop(t, 6, i, 0.08));
      const y = ((i + 1) / (rows + 1)) * h;
      ctx.strokeStyle = A(accent, 0.16);
      ctx.beginPath(); ctx.moveTo(w * 0.08, y); ctx.lineTo(w * 0.08 + (w * 0.84) * p, y); ctx.stroke();
      ctx.fillStyle = A(accent, 0.3 * p);
      ctx.fillRect(w * 0.08 + w * 0.84 * p, y - 4, 2, 8);
    }
    ctx.strokeStyle = A(accent, 0.22);
    [0.08, 0.62, 0.78, 0.92].forEach((x) => {
      ctx.beginPath(); ctx.moveTo(w * x, 0); ctx.lineTo(w * x, h); ctx.stroke();
    });
  };
};

/** landscaping — leaves unfurling from the corners along their stems. */
const organicLeafUnfurl: Engine = (accent, mobile) => {
  const n = dens(8, mobile);
  const r = rng(41);
  const leaves = Array.from({ length: n }, () => ({ x: r(), y: r(), rot: r() * 6.28, s: 30 + r() * 60 }));
  return (ctx, w, h, t) => {
    leaves.forEach((l, i) => {
      const p = loop(t, 7, i, 0.09);
      const e = easeOutExpo(Math.min(1, p * 1.5));
      ctx.save();
      ctx.translate(l.x * w, l.y * h);
      ctx.rotate(l.rot + (1 - e) * 0.7);
      ctx.scale(e, e);
      ctx.fillStyle = A(accent, 0.12 * (1 - p * 0.6));
      ctx.strokeStyle = A(accent, 0.3 * (1 - p * 0.6));
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.quadraticCurveTo(l.s * 0.5, -l.s * 0.5, l.s, 0);
      ctx.quadraticCurveTo(l.s * 0.5, l.s * 0.5, 0, 0);
      ctx.fill(); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(l.s, 0); ctx.stroke();
      ctx.restore();
    });
  };
};

/** photography — six aperture blades opening and closing on the shutter. */
const shutterApertureOpen: Engine = (accent, mobile) => {
  const blades = 6;
  return (ctx, w, h, t) => {
    const cx = w / 2, cy = h / 2, R = Math.min(w, h) * (mobile ? 0.42 : 0.36);
    const cyc = (t * 0.28) % 1;
    const open = cyc < 0.5 ? easeOutExpo(cyc * 2) : 1 - easeOutExpo((cyc - 0.5) * 2);
    for (let i = 0; i < blades; i++) {
      const a = (i / blades) * Math.PI * 2 + open * 0.5 + t * 0.05;
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(a);
      ctx.fillStyle = A(accent, 0.1);
      ctx.strokeStyle = A(accent, 0.3);
      ctx.beginPath();
      ctx.moveTo(R * (0.2 + open * 0.5), 0);
      ctx.lineTo(R, -R * 0.5);
      ctx.lineTo(R, R * 0.5);
      ctx.closePath();
      ctx.fill(); ctx.stroke();
      ctx.restore();
    }
    ctx.strokeStyle = A(accent, 0.2);
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.stroke();
  };
};

/** automotive — a gear ring stepping up through the revs while streaks accelerate. */
const gearShiftAcceleration: Engine = (accent, mobile) => {
  const n = dens(12, mobile);
  const r = rng(47);
  const lanes = Array.from({ length: n }, () => ({ y: r(), sp: 0.6 + r() * 0.8, len: 0.1 + r() * 0.35 }));
  return (ctx, w, h, t) => {
    const gear = Math.floor((t * 0.5) % 5);
    const accel = ((t * 0.5) % 1);
    lanes.forEach((l, i) => {
      const speed = (0.35 + gear * 0.22) * l.sp;
      const x = ((t * speed * w * 0.5 + i * 137) % (w * 1.6)) - w * 0.3;
      const g = ctx.createLinearGradient(x, 0, x + l.len * w, 0);
      g.addColorStop(0, A(accent, 0));
      g.addColorStop(1, A(accent, 0.28 * (0.4 + accel * 0.6)));
      ctx.fillStyle = g;
      ctx.fillRect(x, l.y * h, l.len * w, 2.5);
    });
    ctx.save();
    ctx.translate(w * 0.5, h * 0.5);
    ctx.rotate(t * (0.6 + gear * 0.5));
    ctx.strokeStyle = A(accent, 0.22);
    ctx.lineWidth = 2;
    const R = Math.min(w, h) * 0.2;
    for (let k = 0; k < 12; k++) {
      const a = (k / 12) * Math.PI * 2;
      ctx.beginPath();
      ctx.moveTo(Math.cos(a) * R, Math.sin(a) * R);
      ctx.lineTo(Math.cos(a) * R * 1.18, Math.sin(a) * R * 1.18);
      ctx.stroke();
    }
    ctx.beginPath(); ctx.arc(0, 0, R, 0, Math.PI * 2); ctx.stroke();
    ctx.restore();
  };
};

/** beauty — petals floating up and blooming open. */
const floatAndBloom: Engine = (accent, mobile) => {
  const n = dens(12, mobile);
  const r = rng(53);
  const petals = Array.from({ length: n }, () => ({ x: r(), sp: 0.5 + r(), s: 14 + r() * 26, rot: r() * 6.28 }));
  return (ctx, w, h, t) => {
    petals.forEach((p, i) => {
      const k = ((t * p.sp * 0.1) + i / n) % 1;
      const y = h * (1.05 - k * 1.1);
      const x = p.x * w + Math.sin(k * 4 + i) * 40;
      const e = easeOutElastic(Math.min(1, k * 2));
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(p.rot + k * 2);
      ctx.fillStyle = A(accent, 0.2 * (1 - k));
      for (let q = 0; q < 5; q++) {
        ctx.rotate((Math.PI * 2) / 5);
        ctx.beginPath();
        ctx.ellipse(p.s * 0.5 * e, 0, p.s * 0.5 * e, p.s * 0.22 * e, 0, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    });
  };
};

/** insurance — shield segments flying in and locking together. */
const shieldAssemble: Engine = (accent, mobile) => {
  const segs = dens(8, mobile);
  return (ctx, w, h, t) => {
    const cx = w / 2, cy = h * 0.5, R = Math.min(w, h) * 0.28;
    const p = easeOutExpo(loop(t, 5.5, 0, 0));
    const shield = (sx: number, sy: number, s: number) => {
      ctx.beginPath();
      ctx.moveTo(sx, sy - s);
      ctx.lineTo(sx + s * 0.8, sy - s * 0.55);
      ctx.quadraticCurveTo(sx + s * 0.8, sy + s * 0.5, sx, sy + s);
      ctx.quadraticCurveTo(sx - s * 0.8, sy + s * 0.5, sx - s * 0.8, sy - s * 0.55);
      ctx.closePath();
    };
    for (let i = 0; i < segs; i++) {
      const a = (i / segs) * Math.PI * 2;
      const off = (1 - easeOutExpo(Math.max(0, Math.min(1, p * 1.4 - i * 0.06)))) * R * 2.4;
      ctx.save();
      ctx.translate(Math.cos(a) * off, Math.sin(a) * off);
      ctx.strokeStyle = A(accent, 0.26);
      ctx.lineWidth = 1.4;
      shield(cx, cy, R * (0.35 + (i % 3) * 0.22));
      ctx.stroke();
      ctx.restore();
    }
    ctx.fillStyle = A(accent, 0.06 * p);
    shield(cx, cy, R); ctx.fill();
  };
};

/** pet_grooming — playful dots bouncing along with elastic squash. */
const playfulBounceTrail: Engine = (accent, mobile) => {
  const n = dens(12, mobile);
  return (ctx, w, h, t) => {
    for (let i = 0; i < n; i++) {
      const x = ((i + 0.5) / n) * w;
      const ph = t * 2 + i * 0.5;
      const b = Math.abs(Math.sin(ph));
      const y = h * 0.75 - b * h * 0.4;
      const squash = 1 + (1 - b) * 0.5;
      ctx.save();
      ctx.translate(x, y);
      ctx.scale(squash, 1 / squash);
      ctx.fillStyle = A(accent, 0.3 + b * 0.3);
      ctx.beginPath(); ctx.arc(0, 0, mobile ? 7 : 10, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    }
  };
};

/** hvac_plumbing — pipe network with flowing fluid dashes. */
const pipeFlowTrace: Engine = (accent, mobile) => {
  const rows = dens(5, mobile);
  return (ctx, w, h, t) => {
    ctx.lineWidth = 6;
    ctx.lineCap = "round";
    for (let i = 0; i < rows; i++) {
      const y = h * (0.16 + i * 0.17);
      const mid = w * (0.3 + (i % 3) * 0.2);
      const pts: [number, number][] = [[-20, y], [mid, y], [mid, y + h * 0.12], [w + 20, y + h * 0.12]];
      ctx.strokeStyle = A(accent, 0.12);
      dashedPath(ctx, pts, [], 0);
      ctx.lineWidth = 2.4;
      ctx.strokeStyle = A(accent, 0.5);
      dashedPath(ctx, pts, [12, 22], t * (60 + i * 10));
      ctx.lineWidth = 6;
    }
    ctx.lineCap = "butt";
  };
};

/** coworking — desks lighting up as pulses travel across the floor plan. */
const deskNetworkPulse: Engine = (accent, mobile) => {
  const cols = dens(6, mobile), rows = dens(4, mobile);
  return (ctx, w, h, t) => {
    for (let c = 0; c < cols; c++) {
      for (let r2 = 0; r2 < rows; r2++) {
        const x = ((c + 0.5) / cols) * w, y = ((r2 + 0.5) / rows) * h;
        const ph = Math.sin(t * 1.6 - (c + r2) * 0.6);
        const on = Math.max(0, ph);
        ctx.strokeStyle = A(accent, 0.1 + on * 0.25);
        roundRect(ctx, x - 22, y - 12, 44, 24, 4);
        ctx.stroke();
        if (on > 0.6) softGlow(ctx, x, y, 34, accent, 0.16 * on);
        if (c < cols - 1) {
          ctx.strokeStyle = A(accent, 0.07);
          ctx.beginPath(); ctx.moveTo(x + 22, y); ctx.lineTo(x + w / cols - 22, y); ctx.stroke();
        }
      }
    }
  };
};

/** wellness — the whole canvas breathing in and out. */
const breathingCanvas: Engine = (accent) => (ctx, w, h, t) => {
  const b = (Math.sin(t * (Math.PI * 2) / 8) + 1) / 2;
  const R = Math.min(w, h) * (0.25 + b * 0.2);
  softGlow(ctx, w / 2, h / 2, R * 2, accent, 0.1 + b * 0.08);
  ctx.strokeStyle = A(accent, 0.16);
  ctx.lineWidth = 1.2;
  for (let i = 0; i < 3; i++) {
    ctx.beginPath(); ctx.arc(w / 2, h / 2, R * (0.6 + i * 0.3), 0, Math.PI * 2); ctx.stroke();
  }
};

/** cleaning — a brush sweeping across, lifting speckles. */
const sweepAndReveal: Engine = (accent, mobile) => {
  const n = dens(50, mobile);
  const r = rng(59);
  const specks = Array.from({ length: n }, () => ({ x: r(), y: r(), s: 1 + r() * 2 }));
  return (ctx, w, h, t) => {
    const p = (t * 0.22) % 1.4;
    const edge = p * w;
    specks.forEach((s) => {
      const d = s.x * w - edge;
      const a = d > 0 ? 0.22 : Math.max(0, 0.22 + d / 260);
      ctx.fillStyle = A(accent, a);
      ctx.beginPath(); ctx.arc(s.x * w, s.y * h + (d < 0 ? Math.sin(t * 6 + s.y * 9) * 6 : 0), s.s, 0, Math.PI * 2); ctx.fill();
    });
    const g = ctx.createLinearGradient(edge - 120, 0, edge + 30, 0);
    g.addColorStop(0, A(accent, 0));
    g.addColorStop(1, A(accent, 0.22));
    ctx.fillStyle = g;
    ctx.fillRect(edge - 120, 0, 150, h);
  };
};

/** music_school — equalizer bars plus a live waveform. */
const soundWaveRhythm: Engine = (accent, mobile) => {
  const n = dens(26, mobile);
  const r = rng(61);
  const seedv = Array.from({ length: n }, () => r());
  return (ctx, w, h, t) => {
    const bw = w / n;
    seedv.forEach((s, i) => {
      const v = Math.abs(Math.sin(t * (2 + s * 3) + i * 0.7)) * (0.25 + s * 0.6);
      const bh = v * h * 0.45;
      ctx.fillStyle = A(accent, 0.18 + v * 0.2);
      ctx.fillRect(i * bw + bw * 0.25, h * 0.62 - bh, bw * 0.5, bh);
      ctx.fillRect(i * bw + bw * 0.25, h * 0.66, bw * 0.5, bh * 0.4);
    });
    ctx.strokeStyle = A(accent, 0.35);
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let x = 0; x <= w; x += 5) ctx.lineTo(x, h * 0.24 + Math.sin(x / 40 + t * 3) * Math.sin(x / 300 + t) * 26);
    ctx.stroke();
  };
};

/** nonprofit — overlapping ripples spreading out from several communities. */
const communityRipple: Engine = (accent, mobile) => {
  const src = mobile ? 2 : 3;
  const r = rng(67);
  const pts = Array.from({ length: src }, () => ({ x: 0.2 + r() * 0.6, y: 0.2 + r() * 0.6 }));
  return (ctx, w, h, t) => {
    pts.forEach((p, i) => {
      for (let k = 0; k < 3; k++) {
        const prog = loop(t, 4.5, k + i * 0.5, 1.2);
        ctx.strokeStyle = A(accent, 0.24 * (1 - prog));
        ctx.lineWidth = 1.6 * (1 - prog) + 0.4;
        ctx.beginPath();
        ctx.arc(p.x * w, p.y * h, easeOutExpo(prog) * Math.min(w, h) * 0.5, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.fillStyle = A(accent, 0.5);
      ctx.beginPath(); ctx.arc(p.x * w, p.y * h, 3, 0, Math.PI * 2); ctx.fill();
    });
  };
};

/** architecture — a structural wireframe drawing itself upward. */
const structuralLineReveal: Engine = (accent, mobile) => {
  const bays = dens(6, mobile), levels = 4;
  return (ctx, w, h, t) => {
    const p = easeOutExpo(loop(t, 7, 0, 0));
    ctx.lineWidth = 1.2;
    ctx.strokeStyle = A(accent, 0.26);
    const x0 = w * 0.1, x1 = w * 0.9, y0 = h * 0.85, y1 = h * 0.18;
    for (let b = 0; b <= bays; b++) {
      const x = x0 + ((x1 - x0) * b) / bays;
      const g = Math.max(0, Math.min(1, p * 1.4 - b * 0.05));
      ctx.beginPath(); ctx.moveTo(x, y0); ctx.lineTo(x, y0 + (y1 - y0) * g); ctx.stroke();
    }
    for (let l = 0; l <= levels; l++) {
      const y = y0 + ((y1 - y0) * l) / levels;
      const g = Math.max(0, Math.min(1, p * 1.6 - l * 0.14));
      ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x0 + (x1 - x0) * g, y); ctx.stroke();
      if (l < levels) {
        ctx.strokeStyle = A(accent, 0.12);
        ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x0 + (x1 - x0) * g, y + (y1 - y0) / levels); ctx.stroke();
        ctx.strokeStyle = A(accent, 0.26);
      }
    }
  };
};

/** test_template — broken modules assembling into a modular grid. */
const modularGridBuild: Engine = (accent, mobile) => {
  const cols = dens(6, mobile), rows = dens(4, mobile);
  const r = rng(71);
  const off = Array.from({ length: cols * rows }, () => ({ dx: (r() - 0.5) * 2, dy: (r() - 0.5) * 2, rot: (r() - 0.5) }));
  return (ctx, w, h, t) => {
    const cw = w / cols, ch = h / rows;
    off.forEach((o, i) => {
      const p = easeOutExpo(loop(t, 5, i, 0.05));
      const c = i % cols, r2 = Math.floor(i / cols);
      ctx.save();
      ctx.translate(c * cw + cw / 2 + o.dx * cw * (1 - p), r2 * ch + ch / 2 + o.dy * ch * (1 - p));
      ctx.rotate(o.rot * (1 - p));
      ctx.strokeStyle = A(accent, 0.24 * p);
      ctx.fillStyle = A(accent, 0.05 * p);
      roundRect(ctx, -cw * 0.36, -ch * 0.34, cw * 0.72, ch * 0.68, 4);
      ctx.fill(); ctx.stroke();
      ctx.restore();
    });
  };
};

export const STUDIO_ENGINES: Record<string, Engine> = {
  "paw-print-trail": pawPrintTrail,
  "precision-slide-in": precisionSlideIn,
  "ledger-line-reveal": ledgerLineReveal,
  "organic-leaf-unfurl": organicLeafUnfurl,
  "shutter-aperture-open": shutterApertureOpen,
  "gear-shift-acceleration": gearShiftAcceleration,
  "float-and-bloom": floatAndBloom,
  "shield-assemble": shieldAssemble,
  "playful-bounce-trail": playfulBounceTrail,
  "pipe-flow-trace": pipeFlowTrace,
  "desk-network-pulse": deskNetworkPulse,
  "breathing-canvas": breathingCanvas,
  "sweep-and-reveal": sweepAndReveal,
  "sound-wave-rhythm": soundWaveRhythm,
  "community-ripple": communityRipple,
  "structural-line-reveal": structuralLineReveal,
  "modular-grid-build": modularGridBuild,
};
