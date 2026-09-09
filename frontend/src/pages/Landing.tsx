import { useEffect, useState, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, Layers, Play, Pause, Mic, Image as ImageIcon, Film, CreditCard, Globe, Link2, GripVertical, Sparkles, ShieldCheck, X, ExternalLink, LogIn } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { CursorFXPicker } from "@/components/CursorFX";
import { Words, Spotlight, fast } from "@/components/motion";
import ChatWidget from "@/components/ChatWidget";
import api from "@/lib/api";
import { toast } from "sonner";
import { AdminText, MarqueeEditor, saveLanding } from "@/components/LandingAdmin";
import { Settings2 } from "lucide-react";

const LOGOS = ["Nexus", "Orbit", "Fleet", "Aura", "Ledger", "Studio", "Vanta", "Halo"];
const BENTO = [
  { icon: GripVertical, t: "Drag-and-drop builder", d: "Reorder hero, features, pricing and chart blocks with real physics — then ask Claude to rewrite any block in plain English.", span: "lg:col-span-7" },
  { icon: Sparkles, t: "AI Media Studio", d: "Generate ad-ready images (GPT-Image-1), cinematic video (fal.ai) and studio voiceovers (ElevenLabs) inside every tenant.", span: "lg:col-span-5", icons: [ImageIcon, Film, Mic] },
  { icon: CreditCard, t: "Stripe billing per tenant", d: "Import your price book from Excel or Word — tiers sync to Stripe and clients subscribe in one click.", span: "lg:col-span-4" },
  { icon: Globe, t: "Custom domains", d: "Bind app.clientbrand.com with a live DNS checklist and verified badge.", span: "lg:col-span-4" },
  { icon: Link2, t: "Live preview links", d: "Public read-only URLs partners can open before handoff. Revoke anytime.", span: "lg:col-span-4" },
];

const fade = { hidden: { opacity: 0, y: 18 }, show: (i = 0) => ({ opacity: 1, y: 0, transition: { delay: i * 0.08, duration: 0.55, ease: [0.22, 1, 0.36, 1] } }) };

function ShowcaseCard({ s, i, onOpen }) {
  const [playing, setPlaying] = useState(true);
  const live = s.status ? s.status === "LIVE" : !!s.token;
  return (
    <motion.div variants={fade} custom={i} data-testid={`showcase-card-${i}`} layoutId={`showcase-${i}`} onClick={() => onOpen(s, i)} whileHover={{ y: -6 }} whileTap={{ scale: 0.98 }}
      className="card-lift group relative rounded-2xl overflow-hidden border border-white/10 bg-[var(--card)] cursor-pointer">
      <div className="aspect-[4/3] relative overflow-hidden">
        {s.thumbnail ? <img src={s.thumbnail} alt="" onError={e => { e.currentTarget.style.display = "none"; }} className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" /> :
          <video src={s.video} autoPlay muted loop playsInline ref={el => { if (el) playing ? el.play().catch(() => {}) : el.pause(); }} className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" />}
        <div className="absolute inset-0 bg-gradient-to-t from-[var(--bg)] via-transparent to-transparent" />
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"><span className="rounded-full bg-[var(--acc)] text-black text-xs font-semibold px-4 py-2 flex items-center gap-1.5 shadow-[0_0_30px_rgba(16,185,129,0.5)]">{s.token ? "Open live demo" : "See what's included"} <ArrowRight size={12} /></span></div>
        {!s.thumbnail && <button data-testid={`showcase-toggle-${i}`} onClick={(e) => { e.stopPropagation(); setPlaying(!playing); }}
          className="absolute bottom-3 right-3 w-9 h-9 rounded-full bg-black/60 backdrop-blur border border-white/10 flex items-center justify-center text-white opacity-0 group-hover:opacity-100 transition-opacity">
          {playing ? <Pause size={13} /> : <Play size={13} className="ml-0.5" />}
        </button>}
        <div className="absolute top-3 left-3 chip" data-testid={`showcase-tag-${i}`}>{s.tag}</div>
      </div>
      <div className="p-4 flex items-center justify-between gap-2">
        <div className="font-display text-lg truncate" data-testid={`showcase-name-${i}`}>{s.title}</div>
        <span data-testid={`showcase-status-${i}`} className={`chip ${live ? "chip-active badge-glow" : ""} shrink-0`} style={{ padding: "2px 8px" }}>
          {live && <span className="pulse-dot" />}{live ? "LIVE" : "TEMPLATE"}
        </span>
      </div>
    </motion.div>
  );
}

function NicheModal({ s, i, onClose, onStart }) {
  return (
    <motion.div data-testid="niche-modal" className="fixed inset-0 z-[80] flex items-center justify-center p-6 bg-black/70 backdrop-blur-md" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
      <motion.div layoutId={`showcase-${i}`} onClick={e => e.stopPropagation()} className="relative w-full max-w-2xl rounded-3xl border border-white/10 bg-[var(--card)] overflow-hidden shadow-2xl">
        <div className="aspect-[21/9] relative">{s.thumbnail ? <img src={s.thumbnail} alt="" className="w-full h-full object-cover" /> : <video src={s.video} autoPlay muted loop playsInline className="w-full h-full object-cover" />}<div className="absolute inset-0 bg-gradient-to-t from-[var(--card)] to-transparent" /><div className="absolute top-4 left-4 chip">{s.tag}</div>
          <button data-testid="niche-modal-close" onClick={onClose} className="absolute top-4 right-4 w-9 h-9 rounded-full bg-black/60 border border-white/10 flex items-center justify-center hover:bg-black/80"><X size={14} /></button></div>
        <div className="p-7">
          <div className="overline mb-2">{s.tag}{s.status === "TEMPLATE" ? " template" : " · live tenant"}</div>
          <h3 className="font-display text-2xl font-bold tracking-tight">{s.title || s.name}</h3>
          <p className="text-[var(--mut)] mt-3">{s.summary || s.blurb}</p>
          <div className="mt-5 flex flex-wrap gap-2">{(s.sections || []).map(x => <span key={x} className="chip normal-case tracking-normal">{typeof x === "string" ? x.replace(/_/g, " ") : x}</span>)}</div>
          <p className="text-xs text-[var(--dim)] mt-4">Includes: dark premium design system, glass cards, niche hero imagery, AI chat widget, lead inbox, workflows, CMS and one-click export.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <button data-testid="niche-modal-cta" onClick={onStart} className="btn-primary btn-glow arrow-slide inline-flex items-center gap-2">Get started with this template <ArrowRight size={14} /></button>
            <a data-testid="niche-modal-demo" href="mailto:jaybernabe@luciodigital.com?subject=Demo request" className="btn-ghost">Request a demo</a>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

const DEMOS = [
  { title: "Site Mode — prompt to a multi-page site in 60 seconds", tag: "Framer-style builder", len: "1:24", video: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4" },
  { title: "App Mode — 18 industry templates with live prototypes", tag: "Lovable-style app builder", len: "0:58", video: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4" },
  { title: "Export & handoff — GitHub, .zip, custom domains", tag: "Handoff pipeline", len: "0:46", video: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4" },
];

function DemoVideo({ d, i, big }) {
  const [playing, setPlaying] = useState(false);
  return (
    <motion.div variants={fade} custom={i} data-testid={`demo-video-${i}`} className="card-lift group relative rounded-2xl overflow-hidden border border-white/10 bg-[var(--card)]">
      <div className={`${big ? "aspect-video lg:h-full" : "aspect-[21/9]"} relative overflow-hidden`}>
        {/youtube\.com|youtu\.be/.test(d.video) ? <iframe src={d.video} title={d.title} allow="autoplay; encrypted-media" allowFullScreen className="w-full h-full" /> : <video src={d.video} muted loop playsInline preload="metadata" ref={el => { if (el) playing ? el.play().catch(() => {}) : el.pause(); }} className="w-full h-full object-cover" />}
        <div className="absolute inset-0 bg-gradient-to-t from-[var(--bg)] via-[var(--bg)]/20 to-transparent" />
        <button data-testid={`demo-play-${i}`} onClick={() => setPlaying(!playing)} className={`absolute inset-0 m-auto rounded-full bg-[var(--acc)] text-black flex items-center justify-center shadow-[0_0_40px_rgba(16,185,129,0.45)] transition-transform hover:scale-105 ${big ? "w-16 h-16" : "w-12 h-12"} ${playing ? "opacity-0 group-hover:opacity-100" : ""}`}>
          {playing ? <Pause size={big ? 22 : 16} /> : <Play size={big ? 22 : 16} className="ml-1" />}
        </button>
        <div className="absolute top-3 left-3 chip">{d.tag}</div>
        <span className="absolute top-3 right-3 text-[11px] font-mono bg-black/60 backdrop-blur px-2 py-0.5 rounded-full border border-white/10">{d.len}</span>
        <div className={`absolute bottom-0 inset-x-0 p-5 font-display ${big ? "text-xl lg:text-2xl" : "text-base"}`}>{d.titleNode || d.title}</div>
        {d.onVideoUrl && <button data-testid={`demo-video-url-${i}`} onClick={(e) => { e.stopPropagation(); d.onVideoUrl(); }} className="absolute bottom-4 right-4 chip chip-active cursor-pointer">Set video URL</button>}
      </div>
    </motion.div>
  );
}

export default function Landing() {
  const nav = useNavigate();
  const { user } = useAuth();
  const go = () => nav(user ? "/dashboard" : "/register");
  const [activeNav, setActiveNav] = useState("Showcase");
  const [showcase, setShowcase] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [modal, setModal] = useState(null);
  const [leaving, setLeaving] = useState(false);
  const isAdmin = !!user?.is_admin;
  const [editMode, setEditMode] = useState(() => localStorage.getItem("os_landing_edit") !== "0");
  const admin = isAdmin && editMode;
  const toggleEditMode = () => setEditMode(v => { localStorage.setItem("os_landing_edit", v ? "0" : "1"); return !v; });
  const [cms, setCms] = useState({ cards: [], marquee: LOGOS, texts: {} });
  const [tickerOpen, setTickerOpen] = useState(false);
  const chatColorTimer = useRef(null);
  useEffect(() => { api.get("/public/landing").then(r => setCms(r.data)).catch(() => {}); }, []);
  const tx = (k, fallback) => cms.texts?.[k] ?? fallback;
  const saveText = (k) => async (v) => setCms(await saveLanding({ texts: { [k]: v } }));
  const Tx = ({ k, f, as = "span", className, testid }) => <AdminText admin={admin} value={tx(k, f)} onSave={saveText(k)} as={as} className={className} testid={testid || `text-${k}`} />;
  const demoAt = (i) => ({ ...DEMOS[i], title: tx(`demo_${i}_title`, DEMOS[i].title), tag: tx(`demo_${i}_tag`, DEMOS[i].tag), len: tx(`demo_${i}_len`, DEMOS[i].len), video: tx(`demo_${i}_video`, DEMOS[i].video),
    titleNode: <Tx k={`demo_${i}_title`} f={DEMOS[i].title} />,
    onVideoUrl: admin ? async () => { const u = window.prompt("Paste the video URL (MP4 or YouTube embed link) for this demo", tx(`demo_${i}_video`, DEMOS[i].video)); if (u && u.trim()) { try { await saveText(`demo_${i}_video`)(u.trim()); toast.success("Demo video updated"); } catch { toast.error("Save failed"); } } } : undefined });
  async function saveMarquee(list) { try { setCms(await saveLanding({ marquee: list })); setTickerOpen(false); toast.success("Ticker updated"); } catch { toast.error("Save failed"); } }
  // Tenant cards + niche template cards are 100% database-driven and refresh on focus / every 30s.
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [t, n] = await Promise.all([api.get("/public/landing/tenants"), api.get("/public/landing/templates")]);
        if (!alive) return;
        setShowcase((t.data.tenants || []).map(x => ({ ...x, title: x.name, thumbnail: x.cover, blurb: x.summary })));
        setTemplates(n.data.templates || []);
      } catch (e) { console.warn("Could not load showcase data", e?.response?.status || e?.message); }
    };
    load();
    const timer = setInterval(load, 30000);
    window.addEventListener("focus", load);
    return () => { alive = false; clearInterval(timer); window.removeEventListener("focus", load); };
  }, []);
  function openShowcase(s, i) {
    if (s.token) { setLeaving(true); setTimeout(() => nav(`/p/${s.token}`), 380); } else setModal({ s, i });
  }

  return (
    <div className="min-h-screen relative overflow-x-hidden">
      <AnimatePresence>{leaving && <motion.div data-testid="demo-transition" className="fixed inset-0 z-[90] bg-[var(--bg)] flex items-center justify-center" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}><div className="flex items-center gap-3 text-sm text-[var(--mut)]"><span className="w-2 h-2 rounded-full bg-[var(--acc)] pulse-dot" /> Opening live demo…</div></motion.div>}</AnimatePresence>
      <AnimatePresence>{modal && <NicheModal s={modal.s} i={modal.i} onClose={() => setModal(null)} onStart={go} />}</AnimatePresence>
      {isAdmin && (
        <div className="fixed top-4 left-4 z-[80] flex items-center gap-2" data-testid="landing-admin-bar">
          <button data-testid="landing-edit-mode-toggle" onClick={toggleEditMode}
            className={`rounded-full px-3.5 py-2 text-[11px] font-semibold backdrop-blur-xl border shadow-2xl transition-colors ${editMode ? "bg-[var(--acc)] text-black border-transparent" : "bg-black/70 text-white/80 border-white/15 hover:text-white"}`}>
            {editMode ? "Editing on · click to browse" : "Editing off · click to edit"}
          </button>
          <button data-testid="landing-admin-dashboard-btn" onClick={() => nav("/dashboard")}
            className="rounded-full px-3.5 py-2 text-[11px] font-semibold backdrop-blur-xl bg-black/70 text-white/80 border border-white/15 hover:text-white shadow-2xl transition-colors">
            Dashboard
          </button>
        </div>
      )}
      <div className="absolute inset-0 grid-bg pointer-events-none" />
      <div className="hero-glow pointer-events-none absolute -top-40 left-1/2 w-[900px] h-[500px] rounded-full bg-[var(--acc)]/12 blur-[140px]" />
      <Spotlight />

      {/* Floating pill nav */}
      <header className="fixed top-5 inset-x-0 z-50 flex justify-center px-4">
        <nav data-testid="landing-nav-pill" className="flex items-center gap-1 rounded-full backdrop-blur-xl bg-[var(--bg)]/80 border border-white/10 shadow-2xl pl-4 pr-2 py-2">
          <Link to="/" className="flex items-center gap-2 pr-3 mr-1 border-r border-white/10">
            <Layers size={16} className="text-[var(--acc)]" />
            <span className="font-display font-semibold tracking-tight"><Tx k="brand_name" f="Lois-" /><span className="text-[var(--acc)]"><Tx k="brand_suffix" f="Tech" /></span></span>
          </Link>
          {[["Showcase", "#showcase"], ["Platform", "#platform"], ["Pricing", "#pricing"]].map(([l, h]) => (
            <a key={l} href={h} onClick={() => setActiveNav(l)} data-testid={`nav-pill-${l.toLowerCase()}-link`} className={`relative hidden md:inline px-3 py-1.5 text-sm transition-colors ${activeNav === l ? "text-white" : "text-[var(--mut)] hover:text-white"}`}>
              {activeNav === l && <motion.span layoutId="nav-pill" className="absolute inset-0 rounded-full bg-white/10" transition={{ duration: 0.25, ease: fast }} />}<span className="relative">{l}</span></a>
          ))}
          {/* Identical for owners, users and visitors — admin controls live in the top-left bar. */}
          <Link data-testid="nav-login" to="/login" className="px-3 py-1.5 text-sm text-[var(--mut)] hover:text-white">Sign in</Link>
          <Link data-testid="nav-register" to="/register" className="ml-1 rounded-full bg-[var(--acc)] hover:bg-emerald-400 text-black font-semibold text-sm px-4 py-1.5 shadow-[0_0_20px_rgba(16,185,129,0.3)] transition-colors">Start free</Link>
        </nav>
      </header>

      {/* Every visitor gets the same floating controls */}
      <div className="fixed bottom-5 left-5 z-[60] flex flex-col items-start gap-2" data-testid="landing-floating-actions">
        <div className="rounded-full backdrop-blur-xl bg-[var(--bg)]/85 border border-white/10 shadow-2xl p-1">
          <CursorFXPicker up />
        </div>
        <Link data-testid="floating-signin-btn" to="/login"
          className="rounded-full bg-[var(--acc)] hover:bg-emerald-400 text-black font-semibold text-sm px-5 py-2.5 shadow-[0_0_24px_rgba(16,185,129,0.35)] transition-colors flex items-center gap-2">
          <LogIn size={14} /> Sign in
        </Link>
      </div>

      {/* Hero */}
      <section className="relative z-10 px-6 lg:px-14 pt-36 lg:pt-44 pb-20 text-center">
        <motion.div initial="hidden" animate="show" className="max-w-4xl mx-auto">
          <motion.div variants={fade} custom={0} className="shimmer inline-flex items-center gap-2 uppercase tracking-[0.2em] text-xs font-semibold text-emerald-400 bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/20">
            <Sparkles size={11} /> <Tx k="hero_eyebrow" f="New · AI Media Studio + Stripe billing" />
          </motion.div>
          <div className="mt-7">{admin ? <><Tx k="hero_h1" f="The workspace where agencies build, bill and hand off" as="h1" className="font-display text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.05]" testid="hero-headline" /><Tx k="hero_h1_accent" f="every client app." as="h1" className="font-display text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.05] text-[var(--acc)]" /></> : <><Words as="h1" testid="hero-headline" text={tx("hero_h1", "The workspace where agencies build, bill and hand off")} className="font-display text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.05]" delay={0.1} />
            <Words as="h1" text={tx("hero_h1_accent", "every client app.")} className="font-display text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.05] text-[var(--acc)]" delay={0.55} /></>}</div>
          <motion.p variants={fade} custom={2} className="mt-6 text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
            <Tx k="hero_sub" f="Spin up tenants, design pages with drag-and-drop and AI, generate video, images and voice, charge clients monthly, and ship to their own domain." />
          </motion.p>
          <motion.div variants={fade} custom={3} className="mt-9 flex flex-wrap justify-center gap-3">
            <button data-testid="hero-cta-primary" onClick={admin ? undefined : go} className="btn-primary btn-glow arrow-slide flex items-center gap-2"><Tx k="hero_cta" f="Start building free" /> <ArrowRight size={16} /></button>
            <button data-testid="hero-cta-demo" onClick={admin ? undefined : () => nav("/login")} className="btn-ghost btn-glow flex items-center gap-2"><Play size={14} /> <Tx k="hero_cta2" f="Watch the demo" /></button>
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
                  <AdminText admin={admin} value={tx("hero_caption_overline", "Live · Orbit SaaS Portal")} onSave={saveText("hero_caption_overline")} as="div" className="overline" testid="text-hero-caption-overline" />
                  <AdminText admin={admin} value={tx("hero_caption_title", "B2B Success Analytics")} onSave={saveText("hero_caption_title")} as="div" className="font-display text-2xl mt-1" testid="text-hero-caption-title" />
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
      <section className="relative z-10 border-y border-white/5 py-6 overflow-hidden group/marquee" data-testid="marquee-section">
        {admin && <button data-testid="marquee-edit-btn" onClick={() => setTickerOpen(true)} className="absolute right-6 top-1/2 -translate-y-1/2 z-10 chip chip-active flex items-center gap-1 cursor-pointer"><Settings2 size={11} /> Edit ticker</button>}
        <div className="marquee flex gap-16 whitespace-nowrap">
          {[...cms.marquee, ...cms.marquee].map((l, i) => <span key={i} data-testid={i < cms.marquee.length ? `marquee-text-${i}` : undefined} className="font-display text-xl text-white/25 tracking-tight">{l}</span>)}
        </div>
      </section>
      <MarqueeEditor items={cms.marquee} open={tickerOpen} onClose={() => setTickerOpen(false)} onSave={saveMarquee} />

      {/* Niche templates — pulled live from the platform's template library */}
      <section className="relative z-10 px-6 lg:px-14 py-16" data-testid="niche-cards-section">
        <div className="max-w-7xl mx-auto mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="overline">Niche templates</div>
            <div className="text-sm text-[var(--mut)] mt-1">{templates.length} industry template{templates.length === 1 ? "" : "s"} ready to spin up — this list updates itself as templates are added or removed.</div>
          </div>
        </div>
        <div className="max-w-7xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-4">
          {templates.slice(0, 8).map((c, i) => (
            <div key={c.key} data-testid={`landing-image-${i}`} className={`group card-lift relative rounded-2xl overflow-hidden border border-white/10 hover:scale-[1.02] ${i % 2 ? "md:mt-8" : ""}`}>
              <div className="w-full aspect-[4/5]" style={{ background: `linear-gradient(160deg, ${c.primary}40, #0B0F14)` }}>
                <img src={c.image} alt="" onError={e => { e.currentTarget.style.display = "none"; }}
                  className="w-full h-full object-cover hover:scale-105 transition-transform duration-700" />
              </div>
              <div className="absolute inset-x-0 bottom-0 p-4 bg-gradient-to-t from-black/85 to-transparent">
                <div className="text-sm font-semibold" data-testid={`landing-card-title-${i}`}>{c.title}</div>
                {c.description && <div className="text-[11px] text-white/70 mt-1 line-clamp-2">{c.description}</div>}
                <div className="text-[10px] font-mono text-white/50 mt-1">{c.sections} sections</div>
              </div>
            </div>
          ))}
          {templates.length === 0 && <div className="col-span-2 md:col-span-4 text-sm text-[var(--mut)]">Loading templates…</div>}
        </div>
      </section>

      {/* Showcase */}
      <section id="showcase" className="relative z-10 px-6 lg:px-14 py-24 lg:py-32">
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }} className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
            <motion.div variants={fade}>
              <AdminText admin={admin} value={tx("products_overline", "Products we ship")} onSave={saveText("products_overline")} as="div" className="overline mb-3" testid="text-products-overline" />
              <AdminText admin={admin} value={tx("products_heading", "Every tenant, on-brand and always live.")} onSave={saveText("products_heading")} as="h2" className="font-display text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight" testid="text-products-heading" />
              <div className="text-sm text-[var(--mut)] mt-2" data-testid="showcase-counts">{showcase.length} tenant{showcase.length === 1 ? "" : "s"} in the workspace · {showcase.filter(s => s.status === "LIVE").length} live</div>
            </motion.div>
            <motion.button variants={fade} custom={1} data-testid="showcase-view-all" onClick={() => nav(user ? "/dashboard" : "/login")} className="btn-ghost arrow-slide inline-flex items-center gap-2 self-start"><Tx k="showcase_view_all" f="View all tenants" /> <ArrowRight size={14} /></motion.button>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {showcase.slice(0, 8).map((s, i) => <ShowcaseCard key={s.app_id || s.title} s={s} i={i} onOpen={openShowcase} />)}
            {showcase.length === 0 && <div data-testid="showcase-empty" className="col-span-full text-sm text-[var(--mut)]">No tenants in the workspace yet — create one and it appears here automatically.</div>}
          </div>
        </motion.div>
      </section>

      {/* See it in action */}
      <section id="demos" data-testid="demos-section" className="relative z-10 px-6 lg:px-14 py-24 lg:py-32 border-t border-white/5">
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }} className="max-w-7xl mx-auto">
          <motion.div variants={fade} className="mb-12 max-w-2xl">
            <AdminText admin={admin} value={tx("demos_overline", "See it in action")} onSave={saveText("demos_overline")} as="div" className="overline mb-3" testid="text-demos-overline" />
            <AdminText admin={admin} value={tx("demos_heading", "Watch Lois-Tech build, brand and ship a product.")} onSave={saveText("demos_heading")} as="h2" className="font-display text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight" testid="text-demos-heading" />
            <p className="text-[var(--mut)] mt-3"><Tx k="demos_sub" f="Three short walkthroughs: Site Mode, App Mode with industry templates, and the export & handoff pipeline." /></p>
          </motion.div>
          <div className="grid lg:grid-cols-[1.6fr_1fr] gap-6">
            <DemoVideo big d={demoAt(0)} i={0} />
            <div className="grid gap-6">{[1, 2].map(i => <DemoVideo key={i} d={demoAt(i)} i={i} />)}</div>
          </div>
        </motion.div>
      </section>

      {/* Bento */}
      <section id="platform" className="relative z-10 px-6 lg:px-14 py-24 lg:py-32 border-t border-white/5">
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }} className="max-w-7xl mx-auto">
          <motion.div variants={fade} className="max-w-2xl mb-14">
            <AdminText admin={admin} value={tx("platform_overline", "The platform")} onSave={saveText("platform_overline")} as="div" className="overline mb-3" testid="text-platform-overline" />
            <AdminText admin={admin} value={tx("platform_heading", "Everything between “kickoff” and “handoff”.")} onSave={saveText("platform_heading")} as="h2" className="font-display text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight" testid="text-platform-heading" />
          </motion.div>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {BENTO.map((f, i) => (
              <motion.div key={f.t} variants={fade} custom={i} data-testid={`bento-card-${i}`}
                className={`${f.span} card-lift relative rounded-2xl border border-slate-800 bg-[var(--card)] p-6 sm:p-8 overflow-hidden`}>
                <div className="absolute inset-x-0 top-0 h-40 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-emerald-500/10 via-transparent to-transparent pointer-events-none" />
                <span className="icon-pulse inline-flex"><f.icon size={20} className="text-[var(--acc)]" /></span>
                <div className="font-display text-xl mt-5"><Tx k={`bento_${i}_title`} f={f.t} /></div>
                <p className="text-[var(--mut)] mt-2 text-sm leading-relaxed"><Tx k={`bento_${i}_desc`} f={f.d} /></p>
                {f.icons && <div className="flex gap-2 mt-5">{f.icons.map((I, k) => <span key={k} className="w-9 h-9 rounded-xl bg-[var(--bg-2)] border border-white/10 flex items-center justify-center"><I size={15} className="text-[var(--acc)]" /></span>)}</div>}
              </motion.div>
            ))}
          </div>
        </motion.div>
      </section>

      {/* Pricing teaser */}
      <section id="pricing" className="relative z-10 px-6 lg:px-14 py-24 lg:py-32 border-t border-white/5">
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true, margin: "-80px" }} className="max-w-5xl mx-auto text-center">
          <motion.div variants={fade}><Tx k="pricing_overline" f="Pricing" as="div" className="overline mb-3" />
            {admin ? <Tx k="pricing_heading" f="Bill your clients, not your patience." as="h2" className="font-display text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight" /> : <Words as="h2" text={tx("pricing_heading", "Bill your clients, not your patience.")} className="font-display text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight" />}
            <p className="text-[var(--mut)] mt-3 max-w-xl mx-auto"><Tx k="pricing_sub" f="Default tiers below — or upload your own Excel/Word price book and we sync it to Stripe." /></p></motion.div>
          <div className="grid md:grid-cols-3 gap-6 mt-12 text-left" data-testid="pricing-tiers">
            {[["Starter", "$29", "1 hosted tenant"], ["Pro", "$99", "10 tenants + AI Media"], ["Scale", "$299", "Unlimited + SLA"]].map(([n, p, d], i) => (
              <motion.div key={n} variants={fade} custom={i} className={`card-lift rounded-2xl border p-8 bg-[var(--card)] ${i === 1 ? "border-[var(--acc)]/50 pro-glow" : "border-slate-800"}`}>
                <Tx k={`pricing_${i}_name`} f={n} as="div" className="overline" />
                <div className="font-display text-4xl font-bold mt-3"><Tx k={`pricing_${i}_price`} f={p} /><span className="text-sm text-[var(--mut)] font-normal">/<Tx k={`pricing_${i}_period`} f="mo" /></span></div>
                <div className="text-sm text-[var(--mut)] mt-2"><Tx k={`pricing_${i}_desc`} f={d} /></div>
                <button data-testid={`pricing-cta-${n.toLowerCase()}`} onClick={admin ? undefined : go} className={`shimmer shimmer-hover btn-glow mt-6 w-full rounded-full py-2.5 text-sm font-semibold ${i === 1 ? "bg-[var(--acc)] text-black" : "border border-white/10 hover:border-white/30"}`}><Tx k={`pricing_${i}_cta`} f="Get started" /></button>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </section>

      {/* CTA */}
      <section className="relative z-10 px-6 lg:px-14 pb-24">
        <motion.div initial={{ opacity: 0, scale: 0.95 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true, margin: "-80px" }} transition={{ duration: 0.5, ease: fast }} className="gradient-border max-w-5xl mx-auto rounded-3xl border border-white/10 bg-[var(--card)] p-10 lg:p-16 text-center relative overflow-hidden">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-emerald-500/15 via-transparent to-transparent" />
          <span className="icon-shimmer mx-auto relative"><ShieldCheck size={22} className="text-[var(--acc)] relative z-10" /></span>
          <AdminText admin={admin} value={tx("cta_heading", "Launch your agency workspace today.")} onSave={saveText("cta_heading")} as="h2" className="font-display text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight mt-4 relative" testid="text-cta-heading" />
          <button data-testid="footer-cta" onClick={admin ? undefined : go} className="btn-primary btn-glow pulse-soft mt-8 relative inline-flex items-center gap-2"><Tx k="footer_cta" f="Get started" /> <ArrowRight size={16} /></button>
        </motion.div>
      </section>

      <footer className="relative z-10 px-6 lg:px-14 py-10 border-t border-white/5 text-[var(--mut)] text-xs font-mono flex flex-col sm:flex-row gap-2 justify-between">
        <span><Tx k="footer_copy" f="© 2026 Lois-Tech · Agency Multi-Tenant Platform" /></span>
        <span>Built for Emergent</span>
      </footer>
      <ChatWidget token="studio" brand="Lois-Tech" accent="#10B981" textColor={tx("chat_text_color", "#000000")} admin={admin}
        onTextColor={(v) => {
          setCms(c => ({ ...c, texts: { ...c.texts, chat_text_color: v } }));
          clearTimeout(chatColorTimer.current);
          chatColorTimer.current = setTimeout(async () => { try { await saveText("chat_text_color")(v); } catch { toast.error("Save failed"); } }, 400);
        }} />
    </div>
  );
}
