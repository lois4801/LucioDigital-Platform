import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Layers, Play } from "lucide-react";
import api from "@/lib/api";
import { Counter, HeadingWipe, OvershootWords, Reveal, useIsMobile } from "@/components/editorial/motion";
import HeroCards from "@/components/editorial/HeroCards";
import Ribbon from "@/components/editorial/Ribbon";
import BentoGrid from "@/components/editorial/BentoGrid";

const RIBBON_TOP = ["Orbit SaaS", "Halo Studio", "Ledger Fintech", "Vanta Clinic", "Aura Spa", "Fleet Logistics", "Nexus Legal"];
const RIBBON_BOTTOM = ["Site mode", "App mode", "AI media studio", "Stripe billing", "Custom domains", "Supabase export", "Handoff bundle"];

export default function TestLabLanding() {
  const nav = useNavigate();
  const mobile = useIsMobile();
  const [stats, setStats] = useState({ tenants: 0, templates: 0, live: 0 });
  const [templates, setTemplates] = useState([]);

  useEffect(() => {
    Promise.all([api.get("/public/landing/tenants"), api.get("/public/landing/templates")])
      .then(([t, n]) => {
        const tenants = t.data.tenants || [];
        setTemplates(n.data.templates || []);
        setStats({ tenants: tenants.length, templates: (n.data.templates || []).length, live: tenants.filter(x => x.status === "LIVE").length });
      }).catch(() => {});
  }, []);

  return (
    <div className="ed-scope min-h-screen relative overflow-x-hidden" data-testid="testlab-landing">
      {/* Sandbox banner — this design is scoped to the Test Lab tenant until pushed. */}
      <div className="sticky top-0 z-40 bg-[var(--ed-lime)] text-black text-[11px] font-semibold tracking-wide px-4 py-2 flex flex-wrap items-center gap-x-3 gap-y-1" data-testid="testlab-sandbox-banner">
        <span>LucioDigital Test Lab · editorial redesign preview</span>
        <span className="opacity-70">Not applied to lois-tech.ca or any live tenant</span>
        <Link to="/dashboard" className="underline ml-auto">Back to dashboard</Link>
      </div>

      <header className="relative z-30 px-6 sm:px-10 py-6 flex items-center justify-between gap-4">
        <Link to="/" data-testid="brand-home-link" title="Back to the Lois-Tech home page" className="inline-flex items-center gap-3 cursor-pointer group">
          <span className="w-9 h-9 rounded-lg border border-white/12 bg-white/[0.04] flex items-center justify-center group-hover:border-[var(--ed-lime)]/60 transition-colors">
            <Layers size={18} className="text-[var(--ed-lime)]" />
          </span>
          <span className="font-display font-semibold tracking-tight text-lg">Lois-<span className="text-[var(--ed-lime)]">Tech</span></span>
        </Link>
        <nav className="hidden md:flex items-center gap-7 text-sm text-white/50">
          {["Work", "Platform", "Pricing"].map(l => <a key={l} href={`#${l.toLowerCase()}`} className="hover:text-white transition-colors">{l}</a>)}
        </nav>
        <button data-testid="nav-cta" onClick={() => nav("/register")}
          className="ed-cta rounded-full bg-white text-black font-semibold text-sm py-2">Start free</button>
      </header>

      {/* ── Hero ───────────────────────────────────────────────────── */}
      <section className="relative min-h-[86vh] flex items-center px-6 sm:px-10 pb-20" data-testid="hero-section">
      <HeroCards />
      <div className="absolute inset-0 z-10 pointer-events-none" aria-hidden="true"
        style={{ background: "radial-gradient(60% 55% at 38% 45%, rgba(8,8,8,0.92) 0%, rgba(8,8,8,0.6) 45%, rgba(8,8,8,0) 78%)" }} />
        <div className="relative z-20 max-w-4xl mx-auto text-center md:text-left">
          <span className="ed-pill">Master workspace · v2.4</span>
          <OvershootWords testid="hero-headline" accentFrom={mobile ? 99 : 8}
            text="Ship, showcase and hand off every client app from one master workspace."
            className="mt-6 font-display font-extrabold tracking-[-0.03em] leading-[1.02] text-[2.6rem] sm:text-6xl lg:text-7xl" />
          <Reveal i={2} className="mt-7 max-w-xl mx-auto md:mx-0">
            <p className="text-base sm:text-lg text-white/45 leading-relaxed">
              Spin up tenants, design with drag-and-drop and AI, bill monthly, and ship to your client's own domain.
            </p>
          </Reveal>
          <Reveal i={3} className="mt-9 flex flex-col sm:flex-row gap-3 justify-center md:justify-start">
            <button data-testid="hero-cta-primary" onClick={() => nav("/register")}
              className="ed-cta rounded-full bg-[var(--ed-lime)] text-black font-semibold py-3.5 flex items-center justify-center gap-2">
              Start building free <ArrowRight size={16} />
            </button>
            <button data-testid="hero-cta-demo" onClick={() => nav("/login")}
              className="ed-cta rounded-full border border-white/15 text-white font-semibold py-3.5 flex items-center justify-center gap-2 hover:border-white/35 transition-colors">
              <Play size={14} /> Watch the demo
            </button>
          </Reveal>

          <div className="mt-14 grid grid-cols-3 gap-4 sm:gap-8 max-w-lg mx-auto md:mx-0" data-testid="hero-stats">
            {[["Tenants created", stats.tenants], ["Templates ready", stats.templates], ["Live clients", stats.live]].map(([label, value], i) => (
              <Reveal key={label} i={i} className="text-center md:text-left">
                <div className="font-display text-3xl sm:text-4xl font-bold tracking-tight">
                  <Counter to={Number(value)} testid={`hero-stat-${i}`} />
                  <span className="text-[var(--ed-teal)]">+</span>
                </div>
                <div className="mt-1 text-[10px] uppercase tracking-[0.18em] text-white/35">{label}</div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <Ribbon top={RIBBON_TOP} bottom={RIBBON_BOTTOM} />

      {/* ── Bento features ─────────────────────────────────────────── */}
      <section id="platform" className="relative z-10 px-6 sm:px-10 py-24 sm:py-32" data-testid="platform-section">
        <div className="max-w-7xl mx-auto">
          <span className="ed-pill">The platform</span>
          <HeadingWipe testid="platform-heading" className="mt-5 font-display text-3xl sm:text-5xl font-bold tracking-[-0.03em] leading-[1.05] max-w-3xl">
            Everything between kickoff and handoff.
          </HeadingWipe>
          <div className="mt-14"><BentoGrid /></div>
        </div>
      </section>

      {/* ── Work / tenant table ────────────────────────────────────── */}
      <section id="work" className="relative z-10 px-6 sm:px-10 py-24 sm:py-32 border-t border-white/[0.07]" data-testid="work-section">
        <div className="max-w-7xl mx-auto">
          <span className="ed-pill">Selected work</span>
          <HeadingWipe testid="work-heading" className="mt-5 font-display text-3xl sm:text-5xl font-bold tracking-[-0.03em] max-w-3xl">
            Templates, shipped as products.
          </HeadingWipe>
          <div className="mt-12 grid grid-cols-2 lg:grid-cols-4 gap-4">
            {templates.slice(0, 8).map((c, i) => (
              <Reveal key={c.key} i={i} scale testid={`work-card-${i}`}>
                <article className="group rounded-2xl overflow-hidden border border-white/[0.09] bg-white/[0.02] transition-transform duration-[250ms] ease-out hover:scale-[1.02]"
                  style={{ transform: `rotate(${i % 2 ? 0.6 : -0.6}deg)`, willChange: "transform" }}>
                  <div className="aspect-[4/5] overflow-hidden">
                    <img src={c.image} alt="" loading="lazy" onError={e => { e.currentTarget.style.display = "none"; }}
                      className="w-full h-full object-cover grayscale group-hover:grayscale-0 transition-[filter] duration-500" />
                  </div>
                  <div className="p-4">
                    <div className="text-sm font-semibold truncate">{c.title}</div>
                    <div className="mt-1 text-[10px] font-mono uppercase tracking-[0.16em] text-white/35">{c.sections} sections</div>
                  </div>
                </article>
              </Reveal>
            ))}
            {templates.length === 0 && <div className="col-span-full text-sm text-white/40">Loading templates…</div>}
          </div>
        </div>
      </section>

      {/* ── Pricing rows ───────────────────────────────────────────── */}
      <section id="pricing" className="relative z-10 px-6 sm:px-10 py-24 sm:py-32 border-t border-white/[0.07]" data-testid="pricing-section">
        <div className="max-w-5xl mx-auto">
          <span className="ed-pill">Pricing</span>
          <HeadingWipe testid="pricing-heading" className="mt-5 font-display text-3xl sm:text-5xl font-bold tracking-[-0.03em]">
            Bill your clients, not your patience.
          </HeadingWipe>
          <div className="mt-12 divide-y divide-white/[0.07] border-y border-white/[0.07]">
            {[["Starter", "$29", "1 hosted tenant", false], ["Pro", "$99", "10 tenants + AI media", true], ["Scale", "$299", "Unlimited + SLA", false]].map(([n, p, d, hot], i) => (
              <Reveal key={n} i={i}>
                <div data-testid={`pricing-row-${i}`} className="group flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-6 py-6 transition-colors hover:bg-white/[0.02] px-1">
                  <div className="sm:w-40 font-display text-xl font-semibold flex items-center gap-3">
                    {n} {hot && <span className="ed-pill" style={{ color: "var(--ed-orange)", borderColor: "var(--ed-orange)" }}>Popular</span>}
                  </div>
                  <div className="sm:w-32 font-mono text-2xl">{p}<span className="text-xs text-white/35">/mo</span></div>
                  <div className="flex-1 text-sm text-white/45">{d}</div>
                  <button data-testid={`pricing-cta-${i}`} onClick={() => nav("/register")}
                    className={`ed-cta rounded-full py-2.5 text-sm font-semibold ${hot ? "bg-[var(--ed-lime)] text-black" : "border border-white/15 hover:border-white/35"}`}>
                    Get started
                  </button>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── Close ──────────────────────────────────────────────────── */}
      <section className="relative z-10 px-6 sm:px-10 pb-28" data-testid="cta-section">
        <Reveal className="max-w-5xl mx-auto rounded-3xl border border-white/[0.09] bg-white/[0.02] p-10 sm:p-16 text-center">
          <HeadingWipe className="font-display text-3xl sm:text-5xl font-bold tracking-[-0.03em]">Launch your agency workspace today.</HeadingWipe>
          <button data-testid="footer-cta" onClick={() => nav("/register")}
            className="ed-cta mt-9 rounded-full bg-white text-black font-semibold py-3.5 inline-flex items-center gap-2">
            Get started <ArrowRight size={16} />
          </button>
        </Reveal>
      </section>

      <footer className="relative z-10 px-6 sm:px-10 py-10 border-t border-white/[0.07] text-white/35 text-xs font-mono flex flex-col sm:flex-row gap-2 justify-between">
        <span>© 2026 Lois-Tech · Test Lab preview</span>
        <span>Editorial motion system</span>
      </footer>
    </div>
  );
}
