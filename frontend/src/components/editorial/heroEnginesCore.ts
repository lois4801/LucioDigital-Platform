/** Bespoke hero engines — the 16 core industry templates. One render function per hero. */
import {
  A, Draw, Engine, dashedPath, dens, easeInOutQuint, easeOutBack, easeOutExpo, loop, quadAt,
  rng, roundRect, softGlow,
} from "./heroUtils";

/** real_estate — long architectural ribbons curving across the frame. */
const curvedRibbonScroll: Engine = (accent, mobile) => {
  const rows = mobile ? 2 : 3;
  return (ctx, w, h, t) => {
    for (let r = 0; r < rows; r++) {
      const y = h * (0.28 + r * 0.22);
      const off = ((t * (26 + r * 7)) % (w + 400)) - 200;
      ctx.lineWidth = 26 - r * 6;
      ctx.strokeStyle = A(accent, 0.14 - r * 0.03);
      ctx.beginPath();
      ctx.moveTo(off - 300, y + 60);
      ctx.quadraticCurveTo(off + w * 0.25, y - 90 + r * 20, off + w * 0.7, y + 40);
      ctx.quadraticCurveTo(off + w * 1.05, y + 130, off + w * 1.4, y - 20);
      ctx.stroke();
    }
  };
};

/** education — nodes orbiting a knowledge core, linked back to centre. */
const orbitalConstellation: Engine = (accent, mobile) => {
  const n = dens(8, mobile);
  return (ctx, w, h, t) => {
    const cx = w * 0.5, cy = h * 0.5;
    softGlow(ctx, cx, cy, Math.min(w, h) * 0.12, accent, 0.16);
    for (let i = 0; i < n; i++) {
      const rr = Math.min(w, h) * (0.16 + (i % 3) * 0.11);
      const a = (t / (7 + (i % 3) * 3)) * Math.PI * 2 + (i / n) * Math.PI * 2;
      const x = cx + Math.cos(a) * rr * 1.5, y = cy + Math.sin(a) * rr;
      ctx.strokeStyle = A(accent, 0.1);
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(x, y); ctx.stroke();
      ctx.fillStyle = A(accent, 0.6);
      ctx.beginPath(); ctx.arc(x, y, 2.4 + (i % 3), 0, Math.PI * 2); ctx.fill();
    }
  };
};

/** healthcare — slow, calm heartbeat rings + a steady ECG trace. */
const calmPulseWave: Engine = (accent, mobile) => {
  const rings = dens(6, mobile);
  return (ctx, w, h, t) => {
    const cx = w * 0.5, cy = h * 0.5, max = Math.hypot(w, h) * 0.55;
    for (let i = 0; i < rings; i++) {
      const p = loop(t, 5.2, i, 5.2 / rings);
      // a floor keeps the field continuously present instead of dipping to nothing
      ctx.strokeStyle = A(accent, 0.09 + 0.13 * (1 - p));
      ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.arc(cx, cy, easeOutExpo(p) * max, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.strokeStyle = A(accent, 0.35);
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    for (let x = 0; x <= w; x += 4) {
      const s = ((x / w) * 3 + t * 0.25) % 1;
      const beat = s < 0.1 ? Math.sin(s * 31.4) * 34 : s < 0.16 ? -Math.sin((s - 0.1) * 52) * 14 : 0;
      ctx.lineTo(x, cy + beat);
    }
    ctx.stroke();
  };
};

/** fitness — explosive shards firing outward on a hard snap. */
const kineticEnergyBurst: Engine = (accent, mobile) => {
  const n = dens(16, mobile);
  const r = rng(7);
  const ang = Array.from({ length: n }, (_, i) => (i / n) * Math.PI * 2 + r() * 0.4);
  return (ctx, w, h, t) => {
    const cx = w * 0.5, cy = h * 0.5, max = Math.hypot(w, h) * 0.5;
    for (let i = 0; i < n; i++) {
      const p = loop(t, 1.6, i, 0.06);
      const e = easeOutExpo(p);
      const d = e * max, len = 60 * (1 - p) + 20;
      ctx.strokeStyle = A(accent, 0.5 * (1 - p));
      ctx.lineWidth = 3 * (1 - p) + 0.6;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(ang[i]) * d, cy + Math.sin(ang[i]) * d);
      ctx.lineTo(cx + Math.cos(ang[i]) * (d + len), cy + Math.sin(ang[i]) * (d + len));
      ctx.stroke();
    }
  };
};

/** legal — precise grid with a scan line lighting cells as it passes. */
const precisionGridReveal: Engine = (accent, mobile) => {
  const cell = mobile ? 44 : 30;
  return (ctx, w, h, t) => {
    const scan = ((t * 0.22) % 1) * h;
    ctx.strokeStyle = A(accent, 0.08);
    ctx.lineWidth = 1;
    for (let x = 0; x <= w; x += cell) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
    for (let y = 0; y <= h; y += cell) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
    for (let y = 0; y <= h; y += cell) {
      const d = Math.abs(y - scan);
      if (d > cell * 3) continue;
      ctx.fillStyle = A(accent, 0.1 * (1 - d / (cell * 3)));
      for (let x = 0; x <= w; x += cell) if ((x / cell + y / cell) % 3 === 0) ctx.fillRect(x, y, cell, cell);
    }
    ctx.strokeStyle = A(accent, 0.4);
    ctx.beginPath(); ctx.moveTo(0, scan); ctx.lineTo(w, scan); ctx.stroke();
  };
};

/** hospitality — three slow luxury parallax planes with a gold sheen. */
const slowLuxuryParallax: Engine = (accent) => (ctx, w, h, t) => {
  for (let l = 0; l < 3; l++) {
    const y = h * (0.3 + l * 0.2);
    const x = ((t * (6 + l * 5)) % (w * 1.6)) - w * 0.3;
    const g = ctx.createLinearGradient(x, 0, x + w * 0.7, 0);
    g.addColorStop(0, A(accent, 0));
    g.addColorStop(0.5, A(accent, 0.1 - l * 0.02));
    g.addColorStop(1, A(accent, 0));
    ctx.fillStyle = g;
    ctx.fillRect(x, y - 46 + l * 10, w * 0.7, 92 - l * 16);
  }
};

/** construction — blueprint rectangles + dimension lines drafted on. */
const blueprintDraftOn: Engine = (accent, mobile) => {
  const r = rng(3);
  const boxes = Array.from({ length: dens(7, mobile) }, () => ({
    x: r(), y: r(), w: 0.1 + r() * 0.25, h: 0.08 + r() * 0.2,
  }));
  return (ctx, w, h, t) => {
    ctx.lineWidth = 1.2;
    boxes.forEach((b, i) => {
      const p = easeInOutQuint(loop(t, 6, i, 0.1));
      const bw = b.w * w, bh = b.h * h, x = b.x * w * 0.8, y = b.y * h * 0.8;
      const per = 2 * (bw + bh);
      ctx.strokeStyle = A(accent, 0.3);
      dashedPath(ctx, [[x, y], [x + bw, y], [x + bw, y + bh], [x, y + bh], [x, y]],
        [per * p, per], 0);
      ctx.strokeStyle = A(accent, 0.16);
      dashedPath(ctx, [[x, y + bh + 12], [x + bw, y + bh + 12]], [4, 4], t * 12);
    });
  };
};

/** saas — live particle network. */
const particleNetwork: Engine = (accent, mobile) => {
  const n = dens(46, mobile);
  const r = rng(11);
  const pts = Array.from({ length: n }, () => ({ x: r(), y: r(), vx: (r() - 0.5) * 0.02, vy: (r() - 0.5) * 0.02 }));
  return (ctx, w, h, t) => {
    pts.forEach((p) => {
      p.x += p.vx * 0.004; p.y += p.vy * 0.004;
      if (p.x < 0 || p.x > 1) p.vx *= -1;
      if (p.y < 0 || p.y > 1) p.vy *= -1;
    });
    ctx.strokeStyle = A(accent, 0.13);
    ctx.lineWidth = 1;
    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        const dx = (pts[i].x - pts[j].x) * w, dy = (pts[i].y - pts[j].y) * h;
        if (Math.hypot(dx, dy) < 130) {
          ctx.beginPath(); ctx.moveTo(pts[i].x * w, pts[i].y * h); ctx.lineTo(pts[j].x * w, pts[j].y * h); ctx.stroke();
        }
      }
    }
    pts.forEach((p, i) => {
      ctx.fillStyle = A(accent, 0.55);
      const rr = 1.6 * (1 + 0.35 * Math.sin(t * 2 + i));
      ctx.beginPath(); ctx.arc(p.x * w, p.y * h, rr, 0, Math.PI * 2); ctx.fill();
    });
  };
};

/** creative_studio — scattered tiles dropping in under gravity and settling. */
const scatteredGravityDrop: Engine = (accent, mobile) => {
  const n = dens(11, mobile);
  const r = rng(19);
  const items = Array.from({ length: n }, () => ({ x: r(), rest: 0.25 + r() * 0.55, s: 26 + r() * 46, rot: (r() - 0.5) * 0.6 }));
  return (ctx, w, h, t) => {
    items.forEach((it, i) => {
      const p = loop(t, 4.4, i, 0.09);
      const e = easeOutBack(Math.min(1, p * 1.6));
      const y = -100 + (it.rest * h + 100) * e;
      ctx.save();
      ctx.translate(it.x * w, y);
      ctx.rotate(it.rot * (1 - e) * 3 + it.rot);
      ctx.strokeStyle = A(accent, 0.3);
      ctx.fillStyle = A(accent, 0.07);
      roundRect(ctx, -it.s / 2, -it.s / 2, it.s, it.s * 0.72, 6);
      ctx.fill(); ctx.stroke();
      ctx.restore();
    });
  };
};

/** events — a hard spotlight sweeping the stage. */
const spotlightSweep: Engine = (accent) => (ctx, w, h, t) => {
  const p = (t * 0.2) % 2;
  const x = (p < 1 ? p : 2 - p) * w;
  const g = ctx.createRadialGradient(x, h * 0.42, 0, x, h * 0.42, Math.min(w, h) * 0.5);
  g.addColorStop(0, A(accent, 0.22));
  g.addColorStop(1, A(accent, 0));
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = A(accent, 0.05);
  ctx.beginPath();
  ctx.moveTo(x, -20); ctx.lineTo(x + 180, h); ctx.lineTo(x - 180, h); ctx.closePath(); ctx.fill();
};

/** finance — bars re-morphing into a rising trend line. */
const dataDashboardMorph: Engine = (accent, mobile) => {
  const n = dens(14, mobile);
  const r = rng(23);
  const base = Array.from({ length: n }, () => 0.2 + r() * 0.7);
  return (ctx, w, h, t) => {
    const bw = w / n;
    const vals = base.map((b, i) => b * (0.6 + 0.4 * Math.sin(t * 0.8 + i * 0.5)));
    vals.forEach((v, i) => {
      const bh = v * h * 0.6;
      ctx.fillStyle = A(accent, 0.12);
      ctx.fillRect(i * bw + bw * 0.2, h - bh, bw * 0.6, bh);
    });
    ctx.strokeStyle = A(accent, 0.5);
    ctx.lineWidth = 2;
    ctx.beginPath();
    vals.forEach((v, i) => ctx.lineTo(i * bw + bw / 2, h - v * h * 0.6 - 14));
    ctx.stroke();
  };
};

/** retail — product cards orbiting on a perspective carousel. */
const productOrbitCarousel: Engine = (accent, mobile) => {
  const n = dens(7, mobile);
  return (ctx, w, h, t) => {
    const cx = w / 2, cy = h * 0.55;
    for (let i = 0; i < n; i++) {
      const a = (t / 9) * Math.PI * 2 + (i / n) * Math.PI * 2;
      const depth = (Math.sin(a) + 1) / 2;
      const x = cx + Math.cos(a) * w * 0.34;
      const y = cy - depth * 26;
      const s = (0.55 + depth * 0.65) * (mobile ? 40 : 62);
      ctx.strokeStyle = A(accent, 0.14 + depth * 0.3);
      ctx.fillStyle = A(accent, 0.05 + depth * 0.06);
      roundRect(ctx, x - s / 2, y - s * 0.62, s, s * 1.24, 8);
      ctx.fill(); ctx.stroke();
    }
  };
};

/** restaurant — steam wisps rising and drifting with aroma bloom. */
const steamAromaDrift: Engine = (accent, mobile) => {
  const n = dens(9, mobile);
  const r = rng(29);
  const wisps = Array.from({ length: n }, () => ({ x: 0.1 + r() * 0.8, sp: 0.3 + r() * 0.5, ph: r() * 6.28, sz: 26 + r() * 46 }));
  return (ctx, w, h, t) => {
    wisps.forEach((s, i) => {
      const p = ((t * s.sp * 0.18) + i / n) % 1;
      const y = h * (1.05 - p * 1.15);
      const x = s.x * w + Math.sin(p * 5 + s.ph) * 44;
      softGlow(ctx, x, y, s.sz * (0.6 + p), accent, 0.16 * (1 - p));
    });
  };
};

/** logistics — a route drawn across the map with travelling packages. */
const routePathAnimation: Engine = (accent, mobile) => {
  const legs = mobile ? 2 : 3;
  return (ctx, w, h, t) => {
    for (let l = 0; l < legs; l++) {
      const p0: [number, number] = [-40, h * (0.3 + l * 0.2)];
      const p1: [number, number] = [w * 0.5, h * (0.1 + l * 0.3)];
      const p2: [number, number] = [w + 40, h * (0.55 + l * 0.15)];
      ctx.strokeStyle = A(accent, 0.22);
      ctx.lineWidth = 1.6;
      const pts: [number, number][] = [];
      for (let s = 0; s <= 1.001; s += 0.05) pts.push(quadAt(p0, p1, p2, s));
      dashedPath(ctx, pts, [10, 8], t * 30);
      for (let k = 0; k < 2; k++) {
        const s = ((t * 0.16 + k / 2 + l * 0.2) % 1);
        const [x, y] = quadAt(p0, p1, p2, s);
        ctx.fillStyle = A(accent, 0.75);
        roundRect(ctx, x - 5, y - 5, 10, 10, 2); ctx.fill();
      }
    }
  };
};

/** it_services — orthogonal circuit traces drawn with pulsing junctions. */
const circuitTraceDraw: Engine = (accent, mobile) => {
  const n = dens(9, mobile);
  const r = rng(31);
  const traces = Array.from({ length: n }, () => ({ y: r(), x: r() * 0.5, len: 0.25 + r() * 0.4, up: r() > 0.5 }));
  return (ctx, w, h, t) => {
    ctx.lineWidth = 1.4;
    traces.forEach((tr, i) => {
      const x0 = tr.x * w, y0 = tr.y * h;
      const x1 = x0 + tr.len * w * 0.6, y1 = y0 + (tr.up ? -1 : 1) * h * 0.16;
      const pts: [number, number][] = [[x0, y0], [x1, y0], [x1, y1], [x1 + 40, y1]];
      const total = tr.len * w * 0.6 + h * 0.16 + 40;
      const p = easeOutExpo(loop(t, 5, i, 0.08));
      ctx.strokeStyle = A(accent, 0.3);
      dashedPath(ctx, pts, [total * p, total], 0);
      const pulse = 0.3 + 0.5 * Math.abs(Math.sin(t * 2 + i));
      ctx.fillStyle = A(accent, pulse * p);
      ctx.beginPath(); ctx.arc(x1 + 40, y1, 3, 0, Math.PI * 2); ctx.fill();
    });
  };
};

/** hvac — warm thermal currents rising in wobbling columns. */
const thermalCurrentDrift: Engine = (accent, mobile) => {
  const cols = dens(7, mobile);
  return (ctx, w, h, t) => {
    for (let c = 0; c < cols; c++) {
      const x = ((c + 0.5) / cols) * w;
      ctx.strokeStyle = A(accent, 0.2);
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let y = h; y > -20; y -= 8) {
        const k = (h - y) / h;
        ctx.lineTo(x + Math.sin(k * 7 + t * (1 + c * 0.2)) * (10 + k * 34), y);
      }
      ctx.stroke();
    }
  };
};

export const CORE_ENGINES: Record<string, Engine> = {
  "curved-ribbon-scroll": curvedRibbonScroll,
  "orbital-constellation": orbitalConstellation,
  "calm-pulse-wave": calmPulseWave,
  "kinetic-energy-burst": kineticEnergyBurst,
  "precision-grid-reveal": precisionGridReveal,
  "slow-luxury-parallax": slowLuxuryParallax,
  "blueprint-draft-on": blueprintDraftOn,
  "particle-network": particleNetwork,
  "scattered-gravity-drop": scatteredGravityDrop,
  "spotlight-sweep": spotlightSweep,
  "data-dashboard-morph": dataDashboardMorph,
  "product-orbit-carousel": productOrbitCarousel,
  "steam-aroma-drift": steamAromaDrift,
  "route-path-animation": routePathAnimation,
  "circuit-trace-draw": circuitTraceDraw,
  "thermal-current-drift": thermalCurrentDrift,
};

export type { Draw, Engine };
