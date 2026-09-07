import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Layers, Play, Pause, Mic, Image as ImageIcon, Film, CreditCard, Globe, Link2, GripVertical, Sparkles, ShieldCheck } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import ChatWidget from "@/components/ChatWidget";

const SHOWCASE = [
  { title: "Nexus Commerce", tag: "E-commerce", video: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4" },
  { title: "Orbit SaaS Portal", tag: "SaaS Portals", video: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4" },
  { title: "Fleet Command", tag: "Internal Tools", video: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4" },
  { title: "Aura Wellness", tag: "Service Booking", video: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoylikes.mp4" },
];
const LOGOS = ["Nexus", "Orbit", "Fleet", "Aura", "Ledger", "Studio", "Vanta", "Halo"];
const BENTO = [
  { icon: GripVertical, t: "Drag-and-drop builder", d: "Reorder hero, features, pricing and chart blocks with real physics — then ask Claude to rewrite any block in plain English.", span: "lg:col-span-7" },
  { icon: Sparkles, t: "AI Media Studio", d: "Generate ad-ready images (GPT-Image-1), cinematic video (fal.ai) and studio voiceovers (ElevenLabs) inside every tenant.", span: "lg:col-span-5", icons: [ImageIcon, Film, Mic] },
  { icon: CreditCard, t: "Stripe billing per tenant", d: "Import your price book from Excel or Word — tiers sync to Stripe and clients subscribe in one click.", span: "lg:col-span-4" },
  { icon: Globe, t: "Custom domains", d: "Bind app.clientbrand.com with a live DNS checklist and verified badge.", span: "lg:col-span-4" },
  { icon: Link2, t: "Live preview links", d: "Public read-only URLs partners can open before handoff. Revoke anytime.", span: "lg:col-span-4" },
];

const fade = { hidden: { opacity: 0, y: 18 }, show: (i = 0) => ({ opacity: 1, y: 0, transition: { delay: i * 0.08, duration: 0.55, ease: [0.22, 1, 0.36, 1] } }) };

function ShowcaseCard({ s, i }) {
  const [playing, setPlaying] = useState(true);
  return (
    <motion.div variants={fade} custom={i} data-testid={`showcase-card-${i}`}
      className="group relative rounded-2xl overflow-hidden border border-white/10 bg-[var(--card)] hover:border-[var(--acc)]/40 hover:-translate-y-1 transition-[transform,border-color] duration-300">
      <div className="aspect-[4/3] relative overflow-hidden">
        <video src={s.video} autoPlay muted loop playsInline ref={el => { if (el) playing ? el.play().catch(() => {}) : el.pause(); }}
          className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" />
        <div className="absolute inset-0 bg-gradient-to-t from-[var(--bg)] via-transparent to-transparent" />
        <button data-testid={`showcase-toggle-${i}`} onClick={() => setPlaying(!playing)}
          className="absolute bottom-3 right-3 w-9 h-9 rounded-full bg-black/60 backdrop-blur border border-white/10 flex items-center justify-center text-white opacity-0 group-hover:opacity-100 transition-opacity">
          {playing ? <Pause size={13} /> : <Play size={13} className="ml-0.5" />}
        </button>
        <div className="absolute top-3 left-3 chip">{s.tag}</div>
      </div>
      <div className="p-4 flex items-center justify-between">
        <div className="font-display text-lg">{s.title}</div>
        <span className="chip chip-active" style={{ padding: "2px 8px" }}><span className="pulse-dot" />Live</span>
      </div>
    </motion.div>
  );
}

export default function Landing() {
  const nav = useNavigate();
  const { user } = useAuth();
  const go = () => nav(user ? "/dashboard" : "/register");

  return (
    <div className="min-h-screen relative overflow-x-hidden">
      <div className="absolute inset-0 grid-bg pointer-events-none" />
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[900px] h-[500px] rounded-full bg-[var(--acc)]/10 blur-[140px]" />

      {/* Floating pill nav */}
      <header className="fixed top-5 inset-x-0 z-50 flex justify-center px-4">
        <nav data-testid="landing-nav-pill" className="flex items-center gap-1 rounded-full backdrop-blur-xl bg-[var(--bg)]/80 border border-white/10 shadow-2xl pl-4 pr-2 py-2">
          <Link to="/" className="flex items-center gap-2 pr-3 mr-1 border-r border-white/10">
            <Layers size={16} className="text-[var(--acc)]" />
            <span className="font-display font-semibold tracking-tight">Lucio<span className="text-[var(--acc)]">/</span>Studio</span>
          </Link>
          {[["Showcase", "#showcase"], ["Platform", "#platform"], ["Pricing", "#pricing"]].map(([l, h]) => (
            <a key={l} href={h} data-testid={`nav-pill-${l.toLowerCase()}-link`} className="hidden md:inline px-3 py-1.5 text-sm text-[var(--mut)] hover:text-white transition-colors">{l}</a>
          ))}
          {user ? (
            <button data-testid="nav-open-dashboard" onClick={() => nav("/dashboard")} className="ml-1 rounded-full bg-[var(--acc)] hover:bg-emerald-400 text-black font-semibold text-sm px-4 py-1.5 shadow-[0_0_20px_rgba(16,185,129,0.3)] transition-colors">Dashboard</button>
          ) : (
            <>
              <Link data-testid="nav-login" to="/login" className="px-3 py-1.5 text-sm text-[var(--mut)] hover:text-white">Sign in</Link>
              <Link data-testid="nav-register" to="/register" className="ml-1 rounded-full bg-[var(--acc)] hover:bg-emerald-400 text-black font-semibold text-sm px-4 py-1.5 shadow-[0_0_20px_rgba(16,185,129,0.3)] transition-colors">Start free</Link>
            </>
          )}
        </nav>
      </header>

      {/* Hero */}
      <section className="relative z-10 px-6 lg:px-14 pt-36 lg:pt-44 pb-20 text-center">
        <motion.div initial="hidden" animate="show" className="max-w-4xl mx-auto">
          <motion.div variants={fade} custom={0} className="inline-flex items-center gap-2 uppercase tracking-[0.2em] text-xs font-semibold text-emerald-400 bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/20">
            <Sparkles size={11} /> New · AI Media Studio + Stripe billing
          </motion.div>
          <motion.h1 variants={fade} custom={1} className="font-display text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.05] mt-7">
            The workspace where agencies<br className="hidden sm:block" /> build, bill and hand off <span className="text-[var(--acc)]">every client app.</span>
          </motion.h1>
          <motion.p variants={fade} custom={2} className="mt-6 text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
            Spin up tenants, design pages with drag-and-drop and AI, generate video, images and voice, charge clients monthly, and ship to their own domain.
          </motion.p>
          <motion.div variants={fade} custom={3} className="mt-9 flex flex-wrap justify-center gap-3">
            <button data-testid="hero-cta-primary" onClick={go} className="btn-primary flex items-center gap-2">{user ? "Open dashboard" : "Start building free"} <ArrowRight size={16} /></button>
            <button data-testid="hero-cta-demo" onClick={() => nav("/login")} className="btn-ghost flex items-center gap-2"><Play size={14} /> Watch the demo</button>
          </motion.div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35, duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          className="relative mt-16 max-w-6xl mx-auto">
          <div className="rounded-3xl border border-white/10 bg-[var(--card)] p-2 shadow-[0_40px_120px_-40px_rgba(16,185,129,0.35)]">
            <div className="rounded-2xl overflow-hidden aspect-[16/8] relative">
              <video data-testid="hero-video" src="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4" autoPlay muted loop playsInline className="w-full h-full object-cover" />
              <div className="absolute inset-0 bg-gradient-to-t from-[var(--bg)]/90 via-transparent to-transparent" />
              <div className="absolute bottom-5 left-5 right-5 flex flex-wrap items-end justify-between gap-3 text-left">
                <div>
                  <div className="overline">Live · Orbit SaaS Portal</div>
                  <div className="font-display text-2xl mt-1">B2B Success Analytics</div>
                </div>
                <div className="flex gap-2">
                  {["99.98% uptime", "84ms", "Stripe · Pro"].map(x => <span key={x} className="chip backdrop-blur bg-black/40">{x}</span>)}
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </section>

      {/* Marquee */}
      <section className="relative z-10 border-y border-white/5 py-6 overflow-hidden">
        <div className="marquee flex gap-16 whitespace-nowrap">
          {[...LOGOS, ...LOGOS].map((l, i) => <span key={i} className="font-display text-xl text-white/25 tracking-tight">{l}</span>)}
        </div>
      </section>

      {/* Showcase */}
      <section id="showcase" className="relative z-10 px-6 lg:px-14 py-24 lg:py-32">
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }} className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
            <motion.div variants={fade}>
              <div className="overline mb-3">Products we ship</div>
              <h2 className="font-display text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight">Every tenant, on-brand and always live.</h2>
            </motion.div>
            <motion.button variants={fade} custom={1} data-testid="showcase-view-all" onClick={() => nav(user ? "/dashboard" : "/login")} className="btn-ghost inline-flex items-center gap-2 self-start">View all tenants <ArrowRight size={14} /></motion.button>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {SHOWCASE.map((s, i) => <ShowcaseCard key={s.title} s={s} i={i} />)}
          </div>
        </motion.div>
      </section>

      {/* Bento */}
      <section id="platform" className="relative z-10 px-6 lg:px-14 py-24 lg:py-32 border-t border-white/5">
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }} className="max-w-7xl mx-auto">
          <motion.div variants={fade} className="max-w-2xl mb-14">
            <div className="overline mb-3">The platform</div>
            <h2 className="font-display text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight">Everything between “kickoff” and “handoff”.</h2>
          </motion.div>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {BENTO.map((f, i) => (
              <motion.div key={f.t} variants={fade} custom={i} data-testid={`bento-card-${i}`}
                className={`${f.span} relative rounded-2xl border border-slate-800 bg-[var(--card)] p-6 sm:p-8 overflow-hidden hover:border-emerald-500/40 hover:-translate-y-1 transition-[transform,border-color] duration-300`}>
                <div className="absolute inset-x-0 top-0 h-40 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-emerald-500/10 via-transparent to-transparent pointer-events-none" />
                <f.icon size={20} className="text-[var(--acc)]" />
                <div className="font-display text-xl mt-5">{f.t}</div>
                <p className="text-[var(--mut)] mt-2 text-sm leading-relaxed">{f.d}</p>
                {f.icons && <div className="flex gap-2 mt-5">{f.icons.map((I, k) => <span key={k} className="w-9 h-9 rounded-xl bg-[var(--bg-2)] border border-white/10 flex items-center justify-center"><I size={15} className="text-[var(--acc)]" /></span>)}</div>}
              </motion.div>
            ))}
          </div>
        </motion.div>
      </section>

      {/* Pricing teaser */}
      <section id="pricing" className="relative z-10 px-6 lg:px-14 py-24 lg:py-32 border-t border-white/5">
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }} className="max-w-5xl mx-auto text-center">
          <motion.div variants={fade}><div className="overline mb-3">Pricing</div>
            <h2 className="font-display text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight">Bill your clients, not your patience.</h2>
            <p className="text-[var(--mut)] mt-3 max-w-xl mx-auto">Default tiers below — or upload your own Excel/Word price book and we sync it to Stripe.</p></motion.div>
          <div className="grid md:grid-cols-3 gap-6 mt-12 text-left">
            {[["Starter", "$29", "1 hosted tenant"], ["Pro", "$99", "10 tenants + AI Media"], ["Scale", "$299", "Unlimited + SLA"]].map(([n, p, d], i) => (
              <motion.div key={n} variants={fade} custom={i} className={`rounded-2xl border p-8 bg-[var(--card)] ${i === 1 ? "border-[var(--acc)]/50 shadow-[0_0_60px_-20px_rgba(16,185,129,0.5)]" : "border-slate-800"}`}>
                <div className="overline">{n}</div>
                <div className="font-display text-4xl font-bold mt-3">{p}<span className="text-sm text-[var(--mut)] font-normal">/mo</span></div>
                <div className="text-sm text-[var(--mut)] mt-2">{d}</div>
                <button data-testid={`pricing-cta-${n.toLowerCase()}`} onClick={go} className={`mt-6 w-full rounded-full py-2.5 text-sm font-semibold ${i === 1 ? "bg-[var(--acc)] text-black" : "border border-white/10 hover:border-white/30"}`}>Get started</button>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </section>

      {/* CTA */}
      <section className="relative z-10 px-6 lg:px-14 pb-24">
        <div className="max-w-5xl mx-auto rounded-3xl border border-white/10 bg-[var(--card)] p-10 lg:p-16 text-center relative overflow-hidden">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-emerald-500/15 via-transparent to-transparent" />
          <ShieldCheck size={22} className="text-[var(--acc)] mx-auto relative" />
          <h2 className="font-display text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight mt-4 relative">Launch your agency workspace today.</h2>
          <button data-testid="footer-cta" onClick={go} className="btn-primary mt-8 relative inline-flex items-center gap-2">Get started <ArrowRight size={16} /></button>
        </div>
      </section>

      <footer className="relative z-10 px-6 lg:px-14 py-10 border-t border-white/5 text-[var(--mut)] text-xs font-mono flex flex-col sm:flex-row gap-2 justify-between">
        <span>© 2026 Lucio/Studio · Agency Multi-Tenant Platform</span>
        <span>Built for Emergent</span>
      </footer>
      <ChatWidget token="studio" brand="Lucio/Studio" accent="#10B981" />
    </div>
  );
}
