import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowRight, Layers } from "lucide-react";
import api from "@/lib/api";
import { Counter, HeadingWipe, OvershootWords, Reveal, useCursorParallax, useIsMobile, useReducedMotion, EASE_CSS } from "@/components/editorial/motion";
import Ribbon from "@/components/editorial/Ribbon";

// Public, per-tenant editorial case study. Motion system identical to the Test Lab landing.
export default function CaseStudy() {
  const { slug } = useParams();
  const nav = useNavigate();
  const mobile = useIsMobile();
  const reduced = useReducedMotion();
  const p = useCursorParallax(!mobile && !reduced);
  const [cs, setCs] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.get(`/public/case-studies/${slug}`).then(r => setCs(r.data))
      .catch(() => setErr("That case study isn't published yet."));
  }, [slug]);

  if (err) return (
    <div className="ed-scope min-h-screen flex flex-col items-center justify-center gap-4 px-6 text-center">
      <div className="font-display text-2xl">{err}</div>
      <Link to="/work" className="ed-cta rounded-full border border-white/15 py-2.5 text-sm">Back to client work</Link>
    </div>
  );
  if (!cs) return <div className="ed-scope min-h-screen grid place-items-center text-white/40 text-sm">Loading…</div>;

  const accent = cs.accent || "#10B981";
  const shots = cs.shots || [];
  const stats = cs.stats || [];

  return (
    <div className="ed-scope min-h-screen overflow-x-hidden" data-testid="case-study-page" style={{ ["--ed-lime"]: accent }}>
      <header className="relative z-30 px-6 sm:px-10 py-6 flex items-center justify-between gap-4">
        <Link to="/" data-testid="brand-home-link" className="inline-flex items-center gap-3 cursor-pointer group">
          <span className="w-9 h-9 rounded-lg border border-white/12 bg-white/[0.04] flex items-center justify-center">
            <Layers size={18} style={{ color: accent }} />
          </span>
          <span className="font-display font-semibold tracking-tight text-lg">Lois-<span style={{ color: accent }}>Tech</span></span>
        </Link>
        <Link to="/work" data-testid="case-study-back" className="text-sm text-white/50 hover:text-white transition-colors">All client work</Link>
      </header>

      {/* Hero */}
      <section className="relative px-6 sm:px-10 pt-8 pb-20 sm:pb-28" data-testid="case-hero">
        <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 1200 620" preserveAspectRatio="none" aria-hidden="true">
          {["M 40 300 C 320 140, 700 400, 1160 200", "M 80 540 C 420 460, 760 600, 1140 420"].map((d, i) => (
            <path key={i} d={d} fill="none" stroke={accent} strokeWidth="1.5" strokeLinecap="round"
              className={reduced ? "" : "ed-trim"} style={{ opacity: reduced ? 0.15 : undefined, animationDelay: `${i * 1.8}s` }} />
          ))}
        </svg>
        <div className="relative max-w-7xl mx-auto grid lg:grid-cols-[1.1fr_1fr] gap-12 items-center">
          <div>
            <span className="ed-pill" data-testid="case-industry">{cs.industry}</span>
            <OvershootWords testid="case-title" text={cs.tenant_name}
              className="mt-5 font-display font-extrabold tracking-[-0.035em] leading-[0.98] text-[3rem] sm:text-6xl lg:text-7xl" />
            <Reveal i={2}><p className="mt-6 max-w-xl text-base sm:text-lg text-white/50 leading-relaxed" data-testid="case-tagline">{cs.tagline}</p></Reveal>
            <Reveal i={3} className="mt-8">
              <button data-testid="case-hero-cta" onClick={() => nav("/register")}
                className="ed-cta rounded-full font-semibold py-3.5 text-black inline-flex items-center gap-2" style={{ background: accent }}>
                Start free <ArrowRight size={16} />
              </button>
            </Reveal>
          </div>
          {cs.hero_image && (
            <Reveal i={1} scale>
              <div style={{ transform: reduced ? "none" : `translate3d(${-p.x * 12}px, ${-p.y * 12}px, 0)`, transition: `transform .45s ${EASE_CSS}`, willChange: "transform" }}>
                <div className={reduced ? "" : "ed-float"} style={{ animationDuration: "9s" }}>
                  <img src={cs.hero_image} alt="" data-testid="case-hero-image"
                    className="w-full rounded-2xl border border-white/10 shadow-[0_50px_120px_-50px_rgba(0,0,0,1)]"
                    style={{ transform: "rotate(-2.5deg)" }} />
                </div>
              </div>
            </Reveal>
          )}
        </div>
      </section>

      <Ribbon top={[cs.tenant_name, cs.industry, "Site mode", "Lead inbox", "Stripe billing", "Custom domain"]}
        bottom={["Designed", "Built", "Billed", "Handed off", "Supported"]} />

      {/* Challenge */}
      <section className="px-6 sm:px-10 py-24 sm:py-32" data-testid="case-challenge">
        <div className="max-w-4xl mx-auto">
          <span className="ed-pill">The challenge</span>
          <HeadingWipe className="mt-5 font-display text-2xl sm:text-4xl font-bold tracking-[-0.02em] leading-snug">
            {cs.challenge}
          </HeadingWipe>
        </div>
      </section>

      {/* Solution — floating editorial cards */}
      <section className="px-6 sm:px-10 pb-24 sm:pb-32" data-testid="case-solution">
        <div className="max-w-7xl mx-auto">
          <span className="ed-pill">The solution</span>
          <HeadingWipe className="mt-5 font-display text-3xl sm:text-5xl font-bold tracking-[-0.03em] max-w-3xl">
            {cs.solution_intro}
          </HeadingWipe>
          <div className="mt-14 grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {shots.map((s, i) => (
              <Reveal key={`${s.url}-${i}`} i={i} scale testid={`case-shot-${i}`}>
                <figure className={reduced ? "" : "ed-float"} style={{ animationDuration: `${7 + i}s`, animationDelay: `${i * 0.5}s` }}>
                  <div className="rounded-2xl overflow-hidden border border-white/10 bg-white/[0.02] transition-transform duration-[250ms] ease-out hover:scale-[1.02]"
                    style={{ transform: `rotate(${i % 2 ? 1.6 : -1.6}deg)`, willChange: "transform" }}>
                    <img src={s.url} alt="" loading="lazy" className="w-full aspect-[4/3] object-cover" />
                  </div>
                  {s.caption && <figcaption className="mt-3 text-[10px] uppercase tracking-[0.18em] text-white/35">{s.caption}</figcaption>}
                </figure>
              </Reveal>
            ))}
            {shots.length === 0 && <div className="text-sm text-white/35">No screenshots added yet.</div>}
          </div>
        </div>
      </section>

      {/* Results */}
      <section className="px-6 sm:px-10 py-20 border-y border-white/[0.07] bg-white/[0.015]" data-testid="case-results">
        <div className="max-w-6xl mx-auto">
          <span className="ed-pill">Results</span>
          <div className="mt-10 grid grid-cols-1 sm:grid-cols-3 gap-10">
            {stats.map((s, i) => (
              <Reveal key={s.label + i} i={i}>
                <div className="font-display text-4xl sm:text-6xl font-bold tracking-tight">
                  <Counter to={Number(s.value) || 0} testid={`case-stat-${i}`} />
                  <span style={{ color: accent }}>{s.suffix || ""}</span>
                </div>
                <div className="mt-2 text-[10px] uppercase tracking-[0.18em] text-white/35">{s.label}</div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonial */}
      <section className="px-6 sm:px-10 py-24 sm:py-32" data-testid="case-testimonial">
        <Reveal className="max-w-4xl mx-auto text-center">
          <blockquote className="font-display italic text-2xl sm:text-4xl leading-snug tracking-[-0.02em]">“{cs.quote}”</blockquote>
          <div className="mt-8 text-sm font-semibold" data-testid="case-quote-name">{cs.quote_name}</div>
          <div className="text-xs text-white/40 mt-1">{cs.quote_role}</div>
        </Reveal>
      </section>

      {/* Close */}
      <section className="px-6 sm:px-10 pb-28" data-testid="case-cta">
        <Reveal className="max-w-5xl mx-auto rounded-3xl border border-white/[0.09] bg-white/[0.02] p-12 sm:p-20 text-center">
          <HeadingWipe className="font-display text-3xl sm:text-6xl font-bold tracking-[-0.03em]">Ready to build yours?</HeadingWipe>
          <button data-testid="case-footer-cta" onClick={() => nav("/register")}
            className="ed-cta mt-9 rounded-full font-semibold py-3.5 text-black inline-flex items-center gap-2" style={{ background: accent }}>
            Start free <ArrowRight size={16} />
          </button>
        </Reveal>
      </section>
    </div>
  );
}
