import { GripVertical, Sparkles, CreditCard, Globe, Link2, ShieldCheck } from "lucide-react";
import { Reveal, useReducedMotion } from "./motion";

const FEATURES = [
  { icon: GripVertical, t: "Drag-and-drop builder", d: "Reorder hero, features, pricing and chart blocks with real physics — then ask Claude to rewrite any block in plain English.", span: "lg:col-span-7 lg:row-span-2", tone: "lime", art: "draw" },
  { icon: Sparkles, t: "AI Media Studio", d: "Ad-ready images, cinematic video and studio voiceovers inside every tenant.", span: "lg:col-span-5", tone: "teal", art: "orbit" },
  { icon: CreditCard, t: "Stripe billing per tenant", d: "Import your price book — tiers sync to Stripe and clients subscribe in one click.", span: "lg:col-span-5", tone: "orange", art: "pulse" },
  { icon: Globe, t: "Custom domains", d: "Bind app.clientbrand.com with a live DNS checklist.", span: "lg:col-span-4", tone: "teal", art: "orbit" },
  { icon: Link2, t: "Live preview links", d: "Public read-only URLs partners open before handoff. Revoke anytime.", span: "lg:col-span-4", tone: "lime", art: "pulse" },
  { icon: ShieldCheck, t: "Export & handoff", d: "Full-stack bundle, Supabase migration and plugin packages in one click.", span: "lg:col-span-4", tone: "orange", art: "draw" },
];

const TONE = { lime: "var(--ed-lime)", teal: "var(--ed-teal)", orange: "var(--ed-orange)" };

function Art({ kind, tone, reduced }) {
  const c = TONE[tone];
  if (kind === "orbit") {
    return (
      <span className="relative inline-flex w-10 h-10 items-center justify-center">
        <span className="absolute inset-0 rounded-full border border-white/10" />
        <span className={`absolute inset-0 ${reduced ? "" : "ed-orbit"}`} style={{ willChange: "transform" }}>
          <span className="absolute -top-0.5 left-1/2 w-1.5 h-1.5 rounded-full" style={{ background: c }} />
        </span>
        <span className="w-2 h-2 rounded-full" style={{ background: `${c}99` }} />
      </span>
    );
  }
  if (kind === "pulse") {
    return (
      <span className="relative inline-flex w-10 h-10 items-center justify-center">
        <span className={`absolute w-8 h-8 rounded-full ${reduced ? "" : "ed-pulse"}`} style={{ border: `1px solid ${c}`, willChange: "transform, opacity" }} />
        <span className="w-2.5 h-2.5 rounded-full" style={{ background: c }} />
      </span>
    );
  }
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" className="overflow-visible">
      <path d="M4 30 C 12 8, 22 34, 36 12" fill="none" stroke={c} strokeWidth="1.6" strokeLinecap="round"
        className={reduced ? "" : "ed-draw"} style={{ willChange: "stroke-dashoffset" }} />
    </svg>
  );
}

export default function BentoGrid() {
  const reduced = useReducedMotion();
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-4 sm:gap-5" data-testid="bento-grid">
      {FEATURES.map((f, i) => (
        <Reveal key={f.t} i={i} className={`${f.span} min-w-0`} testid={`bento-card-${i}`}>
          <article className="ed-bento group h-full rounded-2xl p-6 sm:p-8 relative overflow-hidden"
            style={{ ["--ed-tone"]: TONE[f.tone] }}>
            <div className="flex items-start justify-between gap-4">
              <Art kind={f.art} tone={f.tone} reduced={reduced} />
              <span className="ed-pill">{String(i + 1).padStart(2, "0")}</span>
            </div>
            <h3 className="mt-6 font-display text-xl sm:text-2xl font-semibold tracking-tight leading-tight ed-child" style={{ animationDelay: "60ms" }}>{f.t}</h3>
            <p className="mt-3 text-sm text-white/45 leading-relaxed max-w-prose ed-child" style={{ animationDelay: "120ms" }}>{f.d}</p>
          </article>
        </Reveal>
      ))}
    </div>
  );
}
