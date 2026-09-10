import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Layers, Play } from "lucide-react";
import api from "@/lib/api";
import { Counter, HeadingWipe, OvershootWords, Reveal, useIsMobile } from "@/components/editorial/motion";
import HeroCards from "@/components/editorial/HeroCards";
import HeroMotionLayer from "@/components/editorial/HeroMotionLayer";
import { useAuth } from "@/context/AuthContext";
import Ribbon from "@/components/editorial/Ribbon";
import BentoGrid from "@/components/editorial/BentoGrid";
import ReviewsSection from "@/components/editorial/ReviewsSection";

const RIBBON_TOP = ["Orbit SaaS", "Halo Studio", "Ledger Fintech", "Vanta Clinic", "Aura Spa", "Fleet Logistics", "Nexus Legal"];
const RIBBON_BOTTOM = ["Site mode", "App mode", "AI media studio", "Stripe billing", "Custom domains", "Supabase export", "Handoff bundle"];

export default function TestLabLanding() {
  const nav = useNavigate();
  const { user } = useAuth();
  const isAdmin = !!user;
  const mobile = useIsMobile();
  const [stats, setStats] = useState({ tenants: 0, templates: 0, live: 0 });
  const [templates, setTemplates] = useState([]);
  const [platformReviews, setPlatformReviews] = useState([]);
  useEffect(() => {
    api.get("/public/reviews/luciodigital").then(r => setPlatformReviews(r.data.reviews || [])).catch(() => {});
  }, []);

  useEffect(() => {
    Promise.all([api.get("/public/landing/tenants"), api.get("/public/landing/templates")])
      .then(([t, n]) => {
        const clients = t.data.tenants || [];
        setTemplates(n.data.templates || []);
        setStats({ tenants: clients.length, templates: (n.data.templates || []).length, live: clients.filter(x => x.status === "LIVE").length });
      }).catch(() => {});
  }, []);

  return (
    <div className="ed-scope min-h-screen relative overflow-x-hidden" data-testid="testlab-landing">
      {/* Admin-only quick links — invisible to visitors. */}
      {isAdmin && (
        <div className="sticky top-0 z-40 bg-[var(--ed-lime)] text-black text-[11px] font-semibold tracking-wide px-4 py-2 flex flex-wrap items-center gap-x-3 gap-y-1" data-testid="testlab-sandbox-banner">
          <span>Admin · live landing page</span>
          <Link to="/hero-gallery" className="underline">Hero gallery</Link>
          <Link to="/motion" className="underline" data-testid="landing-motion-reel-link">Motion reel</Link>
          <Link to="/accent-audit" className="underline">Accent audit</Link>
          <Link to="/dashboard" className="underline ml-auto">Dashboard</Link>
        </div>
      )}

      <header className="relative z-30 px-4 sm:px-10 py-6 flex items-center gap-2 sm:gap-4">
        <Link to="/" data-testid="brand-home-link" title="Back to the Lois-Tech home page" className="inline-flex items-center gap-3 cursor-pointer group">
          <span className="w-9 h-9 rounded-lg border border-white/12 bg-white/[0.04] flex items-center justify-center group-hover:border-[var(--ed-lime)]/60 transition-colors">
            <Layers size={18} className="text-[var(--ed-lime)]" />
          </span>
          <span className="font-display font-semibold tracking-tight text-lg whitespace-nowrap">Lois-<span className="text-[var(--ed-lime)]">Tech</span></span>
        </Link>
        <nav className="hidden md:flex items-center gap-7 text-sm text-white/50 ml-auto">
          {["Work", "Platform"].map(l => <a key={l} href={`#${l.toLowerCase()}`} className="hover:text-white transition-colors">{l}</a>)}
          <Link to="/work" className="hover:text-white transition-colors">Client work</Link>
          {/* Always available: unauthenticated visitors are sent to sign-in by the route guard. */}
          <Link to="/dashboard" data-testid="nav-dashboard-link" className="text-[var(--ed-lime)] hover:text-white transition-colors">Dashboard</Link>
          {!isAdmin && <Link to="/login" data-testid="nav-signin-link" className="hover:text-white transition-colors">Sign in</Link>}
        </nav>
        {/* Mobile: always one tap from the dashboard. */}
        <Link to="/dashboard" data-testid="nav-dashboard-mobile" aria-label="Dashboard"
          className="md:hidden ml-auto mr-1 rounded-full border border-white/15 px-3 py-1.5 text-xs font-semibold text-[var(--ed-lime)]">
          Dashboard
        </Link>
        <div className="flex items-center gap-2 md:ml-4">
          <button data-testid="nav-cta" onClick={() => nav(isAdmin ? "/dashboard" : "/register")}
            className="ed-cta shrink-0 rounded-full bg-white text-black font-semibold text-xs sm:text-sm py-2 !px-4 sm:!px-7">
            {isAdmin ? <><span className="hidden sm:inline">My workspace</span><span className="sm:hidden">Workspace</span></> : "Start free"}
          </button>
        </div>
      </header>

      {/* ── Hero ───────────────────────────────────────────────────── */}
      <section className="relative min-h-[86vh] flex items-center px-6 sm:px-10 pb-20" data-testid="hero-section">
      <HeroCards />
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <HeroMotionLayer hero="platform-drift-cards" accent="#84FF00" />
      </div>
      <div className="absolute inset-0 z-10 pointer-events-none" aria-hidden="true"
        style={{ background: "radial-gradient(60% 55% at 38% 45%, rgba(8,8,8,0.92) 0%, rgba(8,8,8,0.6) 45%, rgba(8,8,8,0) 78%)" }} />
        <div className="relative z-20 max-w-4xl mx-auto text-center md:text-left">
          <span className="ed-pill">Master workspace · v2.4</span>
          <OvershootWords testid="hero-headline" accentFrom={mobile ? 99 : 8}
            text="Ship, showcase and hand off every client app from one master workspace."
            className="mt-6 font-display font-extrabold tracking-[-0.03em] leading-[1.02] text-[2.6rem] sm:text-6xl lg:text-7xl" />
          <Reveal i={2} className="mt-7 max-w-xl mx-auto md:mx-0">
            <p className="text-base sm:text-lg text-white/45 leading-relaxed">
              Spin up clients, design with drag-and-drop and AI, bill monthly, and ship to your client's own domain.
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
            {[["Clients created", stats.tenants], ["Templates ready", stats.templates], ["Live clients", stats.live]].map(([label, value], i) => (
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

      {/* ── Work / client table ────────────────────────────────────── */}
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

      {/* ── Close ──────────────────────────────────────────────────── */}

      {/* Reviews from the agencies, studios and freelancers shipping on LucioDigital */}
      {platformReviews.length > 0 && (
        <div className="relative z-10 lois-reviews" data-testid="landing-reviews">
          <ReviewsSection reviews={platformReviews} limeLock
            style={{ title: "Loved by the studios shipping on it", subtitle: "Agency owners, digital studios and freelancers on client management, template speed, motion quality and client handoff." }} />
        </div>
      )}

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
        <span>© 2026 Lois-Tech · lois-tech.ca</span>
        <span>Editorial motion system · platform identity</span>
      </footer>
    </div>
  );
}
