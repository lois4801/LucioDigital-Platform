import Logo, { LogoMark } from "@/components/Logo";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Layers } from "lucide-react";
import api from "@/lib/api";
import { Counter, HeadingWipe, Reveal } from "@/components/editorial/motion";

// Public case study index — bento grid of every published client story.
export default function Showcase() {
  const nav = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/public/case-studies").then(r => setRows(r.data.case_studies || []))
      .catch(() => {}).finally(() => setLoading(false));
  }, []);

  // Bento rhythm: first card wide, then alternating sizes.
  const span = (i) => (i === 0 ? "lg:col-span-7 lg:row-span-2" : i % 3 === 1 ? "lg:col-span-5" : "lg:col-span-4");

  return (
    <div className="ed-scope min-h-screen overflow-x-hidden" data-testid="showcase-page">
      <header className="relative z-30 px-6 sm:px-10 py-6 flex items-center justify-between gap-4">
        <Link to="/" data-testid="brand-home-link" className="inline-flex items-center gap-3 cursor-pointer group">
          <span className="w-9 h-9 rounded-lg border border-white/12 bg-white/[0.04] flex items-center justify-center">
            <Layers size={18} className="text-[var(--ed-lime)]" />
          </span>
          <span className="font-display font-semibold tracking-tight text-lg"><Logo variant="lime" size={17} /></span>
        </Link>
        <button data-testid="showcase-cta" onClick={() => nav("/register")} className="ed-cta rounded-full bg-white text-black font-semibold text-sm py-2">Start free</button>
      </header>

      <section className="px-6 sm:px-10 pt-10 pb-16">
        <div className="max-w-7xl mx-auto">
          <span className="ed-pill">Client work</span>
          <HeadingWipe testid="showcase-heading" className="mt-5 font-display text-4xl sm:text-6xl font-bold tracking-[-0.035em] max-w-4xl leading-[1.02]">
            Every client, shipped as a product.
          </HeadingWipe>
          <p className="mt-6 max-w-xl text-white/45">Published case studies from the workspace — the brief, the build and the numbers.</p>
        </div>
      </section>

      <section className="px-6 sm:px-10 pb-28">
        <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-4 sm:gap-5" data-testid="showcase-grid">
          {rows.map((c, i) => (
            <Reveal key={c.slug} i={i} className={`${span(i)} min-w-0`} testid={`showcase-card-${i}`}>
              <button onClick={() => nav(`/work/${c.slug}`)}
                className="ed-bento group h-full w-full text-left rounded-2xl overflow-hidden relative"
                style={{ ["--ed-tone"]: c.accent || "#10B981" }}>
                {c.thumbnail && (
                  <div className={`overflow-hidden ${i === 0 ? "aspect-[16/9]" : "aspect-[16/10]"}`}>
                    <img src={c.thumbnail} alt="" loading="lazy" onError={e => { e.currentTarget.style.display = "none"; }}
                      className="w-full h-full object-cover grayscale group-hover:grayscale-0 transition-[filter] duration-500" />
                  </div>
                )}
                <div className="p-6">
                  <div className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: c.accent || "#10B981" }} />
                    <span className="text-[10px] uppercase tracking-[0.18em] text-white/40">{c.industry}</span>
                  </div>
                  <div className="mt-3 font-display text-2xl font-semibold tracking-tight">{c.tenant_name}</div>
                  <div className="mt-2 text-sm text-white/45 line-clamp-2">{c.tagline}</div>
                  <div className="mt-5 flex items-center justify-between gap-3">
                    <div className="font-mono text-sm" style={{ color: c.accent || "#10B981" }}>
                      <Counter to={Number(c.headline_stat?.value) || 0} />{c.headline_stat?.suffix || ""}
                      <span className="text-white/35 ml-2 text-[10px] uppercase tracking-[0.16em]">{c.headline_stat?.label}</span>
                    </div>
                    <ArrowRight size={16} className="text-white/40 group-hover:text-white transition-colors" />
                  </div>
                </div>
              </button>
            </Reveal>
          ))}
          {!loading && rows.length === 0 && (
            <div data-testid="showcase-empty" className="col-span-full text-sm text-white/40 border border-dashed border-white/10 rounded-2xl p-10 text-center">
              No case studies published yet — publish one from the dashboard and it appears here.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
