import { useCursorParallax, useIsMobile, useReducedMotion, EASE_CSS } from "./motion";

// Abstract UI cards: client sites, templates, dashboards. Scattered, tilted, slow sine drift,
// staggered entrance and cursor parallax (cards move opposite the pointer).
const CARDS = [
  { k: "client-a", label: "Orbit SaaS", kind: "Client", x: 6, y: 14, w: 210, rot: -6, dur: 7.5, depth: 1, accent: "lime" },
  { k: "tmpl-a", label: "Dental · template", kind: "Template", x: 78, y: 10, w: 190, rot: 5, dur: 9, depth: 0.6, accent: "teal" },
  { k: "dash-a", label: "Revenue · $48,210", kind: "Dashboard", x: 71, y: 62, w: 235, rot: -4, dur: 6.5, depth: 1.2, accent: "orange" },
  { k: "client-b", label: "Halo Studio", kind: "Client", x: 3, y: 63, w: 195, rot: 7, dur: 8.5, depth: 0.9, accent: "teal" },
  { k: "tmpl-b", label: "Law firm · template", kind: "Template", x: 16, y: 38, w: 165, rot: -8, dur: 10, depth: 0.5, accent: "lime" },
  { k: "dash-b", label: "Leads · 1,284", kind: "Dashboard", x: 86, y: 36, w: 175, rot: 6, dur: 7, depth: 0.7, accent: "lime" },
  { k: "client-c", label: "Ledger Fintech", kind: "Client", x: 12, y: 86, w: 180, rot: 4, dur: 8, depth: 1.1, accent: "orange" },
  { k: "tmpl-c", label: "Restaurant · template", kind: "Template", x: 62, y: 80, w: 170, rot: -5, dur: 9.5, depth: 0.8, accent: "teal" },
  { k: "dash-c", label: "Uptime · 99.98%", kind: "Dashboard", x: 52, y: 4, w: 160, rot: 3, dur: 6, depth: 0.6, accent: "lime" },
  { k: "client-d", label: "Vanta Clinic", kind: "Client", x: 90, y: 78, w: 165, rot: -7, dur: 8.2, depth: 0.5, accent: "orange" },
];

const TONE = {
  lime: "var(--ed-lime)",
  teal: "var(--ed-teal)",
  orange: "var(--ed-orange)",
};

export default function HeroCards() {
  const reduced = useReducedMotion();
  const mobile = useIsMobile();
  const p = useCursorParallax(!mobile && !reduced);
  // Half the cards on mobile for smooth performance.
  const cards = mobile ? CARDS.filter((_, i) => i % 2 === 0) : CARDS;

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-25 md:opacity-70" data-testid="hero-floating-cards" aria-hidden="true">
      <TrimPaths reduced={reduced} />
      {cards.map((c, i) => {
        const shift = reduced ? { x: 0, y: 0 } : { x: -p.x * 12 * c.depth, y: -p.y * 12 * c.depth };
        return (
          <div key={c.k} data-testid={`hero-card-${c.k}`}
            className={`absolute ${reduced ? "" : "ed-card-in"}`}
            style={{
              left: `${c.x}%`, top: `${c.y}%`, width: c.w,
              animationDelay: `${i * 0.1}s`,
              willChange: "transform, opacity",
            }}>
            <div style={{
              transform: `translate3d(${shift.x}px, ${shift.y}px, 0)`,
              transition: `transform .45s ${EASE_CSS}`,
              willChange: "transform",
            }}>
              <div className={reduced ? "" : "ed-float"} style={{ animationDuration: `${c.dur}s`, animationDelay: `${i * 0.4}s`, willChange: "transform" }}>
                <article className="rounded-xl border border-white/10 bg-[#101010]/70 p-3 shadow-[0_24px_60px_-30px_rgba(0,0,0,0.9)]"
                  style={{ transform: `rotate(${c.rot}deg)` }}>
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: TONE[c.accent] }} />
                    <span className="text-[9px] uppercase tracking-[0.18em] text-white/40">{c.kind}</span>
                  </div>
                  <div className="mt-2 text-[11px] font-semibold text-white/85 truncate">{c.label}</div>
                  <div className="mt-2.5 space-y-1.5">
                    <div className="h-1.5 rounded-full bg-white/10" />
                    <div className="h-1.5 rounded-full bg-white/[0.07] w-2/3" />
                  </div>
                  <div className="mt-3 flex gap-1">
                    {[0, 1, 2, 3].map(b => (
                      <div key={b} className="flex-1 rounded-sm bg-white/[0.06]"
                        style={{ height: 10 + ((i + b) % 4) * 7, background: b === 1 ? `${TONE[c.accent]}55` : undefined }} />
                    ))}
                  </div>
                </article>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Glowing accent segments racing along invisible paths between the cards, looping.
function TrimPaths({ reduced }) {
  const paths = [
    "M 60 180 C 320 60, 620 260, 940 120",
    "M 120 620 C 420 520, 700 700, 1180 560",
    "M 900 140 C 1020 340, 760 520, 520 700",
  ];
  return (
    <svg className="absolute inset-0 w-full h-full" viewBox="0 0 1280 760" preserveAspectRatio="none" data-testid="hero-trim-paths">
      {paths.map((d, i) => (
        <path key={i} d={d} fill="none" strokeLinecap="round" strokeWidth="1.5"
          stroke={i === 1 ? "var(--ed-teal)" : i === 2 ? "var(--ed-orange)" : "var(--ed-lime)"}
          className={reduced ? "" : "ed-trim"}
          style={{ opacity: reduced ? 0.15 : undefined, animationDelay: `${i * 1.6}s`, willChange: "stroke-dashoffset, opacity" }} />
      ))}
    </svg>
  );
}
