import HeroMotionLayer from "./HeroMotionLayer";
import { Counter, OvershootWords, Reveal, HeadingWipe } from "./motion";

/** One template's FULL live motion context, rendered in real time:
 *  hero choreography + accent + scroll reveals + stats counters + layout cards.
 *  Everything is transform/opacity only; the motion layer is pointer-events none. */
export default function MotionStage({ profile, industry = "", speed = 1, intensity = 1, dense = false }) {
  const accent = profile?.accent || "#10B981";
  const hero = profile?.hero || "particle-network";
  const cards = dense ? 4 : 6;

  return (
    <div className="relative min-h-full bg-[#080808] text-white ed-scope" data-testid="motion-stage"
      data-template={profile?.template_key || ""} data-hero={hero}
      style={{ ["--ed-lime"]: accent, ["--ed-teal"]: accent, ["--ed-orange"]: accent } as any}>
      <section className="relative overflow-hidden px-6 sm:px-12 pt-16 pb-14" data-testid="motion-stage-hero">
        <HeroMotionLayer hero={hero} accent={accent} speed={speed} intensity={intensity} />
        <div className="relative z-10 max-w-3xl">
          <span className="ed-pill" data-testid="motion-stage-industry">{industry || profile?.template_key}</span>
          <OvershootWords testid="motion-stage-headline"
            text={`${industry || "This template"} sites that win the enquiry.`}
            accentFrom={3}
            className="mt-5 font-display text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight leading-[0.95]" />
          <p className="mt-5 text-sm md:text-base text-white/45 max-w-prose">
            {hero.replace(/-/g, " ")} hero choreography, {profile?.reveal?.replace(/-/g, " ") || "scroll reveals"} on scroll
            and a {profile?.counter?.replace(/-/g, " ") || "counter"} stat rhythm — the exact motion a new tenant inherits.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <span className="rounded-full px-5 py-2.5 text-sm font-semibold text-black" style={{ background: accent }}>Get a quote</span>
            <span className="rounded-full px-5 py-2.5 text-sm font-semibold border border-white/20">See the work</span>
          </div>
          <div className="mt-10 grid grid-cols-3 gap-6 max-w-md">
            {[["Projects", 248], ["Clients", 96], ["Years", 12]].map(([l, n], i) => (
              <Reveal key={l} i={i} testid={`motion-stage-stat-${i}`}>
                <div className="font-display text-3xl font-semibold" style={{ color: accent }}>
                  <Counter to={Number(n)} testid={`motion-stage-counter-${i}`} /><span>+</span>
                </div>
                <div className="overline mt-1">{l}</div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="relative z-10 px-6 sm:px-12 pb-20" data-testid="motion-stage-layout">
        <HeadingWipe testid="motion-stage-section-title" className="font-display text-2xl sm:text-3xl font-semibold tracking-tight">
          {profile?.layout?.replace(/-/g, " ") || "layout"}
        </HeadingWipe>
        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: cards }).map((_, i) => (
            <Reveal key={i} i={i} testid={`motion-stage-card-${i}`} className="min-w-0">
              <article className="ed-bento h-full rounded-2xl p-6 relative overflow-hidden"
                style={{ ["--ed-tone"]: accent } as any}>
                <span className="ed-pill">{String(i + 1).padStart(2, "0")}</span>
                <h3 className="mt-5 font-display text-lg font-semibold">Service {i + 1}</h3>
                <p className="mt-2 text-sm text-white/40 leading-relaxed">
                  Copy, imagery and CTA forms are generated per tenant — this card only demonstrates the motion.
                </p>
                <span className="mt-5 block h-px w-full" style={{ background: `linear-gradient(90deg,${accent}88,transparent)` }} />
              </article>
            </Reveal>
          ))}
        </div>
      </section>
    </div>
  );
}
