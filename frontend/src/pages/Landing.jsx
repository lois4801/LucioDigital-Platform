import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Layers, Box, Cpu, Rocket, ShieldCheck, Radio } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const SHOWCASE = [
  { title: "Nexus Commerce", tag: "E-commerce", video: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4" },
  { title: "Orbit SaaS Portal", tag: "SaaS Portals", video: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4" },
  { title: "Fleet Command", tag: "Internal Tools", video: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4" },
  { title: "Aura Wellness", tag: "Service Booking", video: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoylikes.mp4" },
];

export default function Landing() {
  const nav = useNavigate();
  const { user } = useAuth();

  return (
    <div className="min-h-screen relative overflow-hidden">
      <div className="absolute inset-0 grid-bg pointer-events-none" />

      {/* Nav */}
      <header className="relative z-10 flex items-center justify-between px-6 lg:px-14 py-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-[var(--card)] border border-[var(--line)] flex items-center justify-center">
            <Layers size={18} className="text-[var(--acc)]" />
          </div>
          <div className="font-display font-semibold tracking-tight text-lg">Lucio<span className="text-[var(--acc)]">/</span>Studio</div>
        </div>
        <div className="flex items-center gap-3">
          {user ? (
            <button data-testid="nav-open-dashboard" onClick={() => nav("/dashboard")} className="btn-primary">
              Open dashboard <ArrowRight size={16} className="inline ml-1" />
            </button>
          ) : (
            <>
              <Link data-testid="nav-login" to="/login" className="btn-ghost">Sign in</Link>
              <Link data-testid="nav-register" to="/register" className="btn-primary">Get started</Link>
            </>
          )}
        </div>
      </header>

      {/* Hero */}
      <section className="relative z-10 px-6 lg:px-14 pt-10 lg:pt-20 pb-16 fade-in">
        <div className="grid lg:grid-cols-[1.05fr_1fr] gap-14 items-center">
          <div>
            <div className="overline mb-6 flex items-center gap-3">
              <Radio size={12} className="text-[var(--acc)]" /> Agency Operating System · v2.4
            </div>
            <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tighter leading-[1.02]">
              Ship, showcase and<br/>
              hand off every client app<br/>
              from <span className="text-[var(--acc)]">one master workspace.</span>
            </h1>
            <p className="mt-6 text-[var(--mut)] max-w-xl text-base lg:text-lg">
              A control center for agencies. Build tenant sub-apps with a block editor, monitor uptime,
              export production-ready bundles, and transfer full ownership when the retainer ends.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <button data-testid="hero-cta-primary" onClick={() => nav(user ? "/dashboard" : "/register")} className="btn-primary">
                {user ? "Open dashboard" : "Start free trial"} <ArrowRight size={16} className="inline ml-1" />
              </button>
              <button data-testid="hero-cta-demo" onClick={() => nav("/login")} className="btn-ghost">See live demo</button>
            </div>

            <div className="mt-12 grid grid-cols-3 gap-6 max-w-xl">
              {[
                { k: "Uptime", v: "99.98%", icon: ShieldCheck },
                { k: "Client apps", v: "42", icon: Box },
                { k: "AI edits/mo", v: "18.4k", icon: Cpu },
              ].map((s) => (
                <div key={s.k} className="card-surface p-4">
                  <s.icon size={16} className="text-[var(--acc)]" />
                  <div className="font-display text-2xl font-semibold mt-2">{s.v}</div>
                  <div className="overline mt-1">{s.k}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Video hero card */}
          <div className="relative">
            <div className="card-surface overflow-hidden aspect-[4/3.2] relative">
              <video
                data-testid="hero-video"
                src="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4"
                autoPlay muted loop playsInline
                className="w-full h-full object-cover opacity-90"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-[var(--bg)] via-transparent to-transparent" />
              <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between">
                <div>
                  <div className="overline">Live · Orbit SaaS Portal</div>
                  <div className="font-display text-xl mt-1">B2B Success Analytics</div>
                </div>
                <span className="chip chip-active"><span className="pulse-dot"/>Active</span>
              </div>
            </div>

            <div className="absolute -bottom-6 -left-6 card-surface p-3 hidden md:block">
              <div className="overline mb-1">CPU · Response</div>
              <div className="flex items-center gap-4 font-mono text-sm">
                <span>32%</span>
                <span className="text-[var(--mut)]">|</span>
                <span>84ms</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Showcase strip */}
      <section className="relative z-10 px-6 lg:px-14 py-12 border-t border-[var(--line)]">
        <div className="flex items-end justify-between mb-8">
          <div>
            <div className="overline mb-2">Live client showcase</div>
            <h2 className="font-display text-3xl font-semibold tracking-tight">Every tenant, always on-brand.</h2>
          </div>
          <button data-testid="showcase-view-all" onClick={() => nav(user ? "/dashboard" : "/login")} className="btn-ghost hidden md:inline-flex items-center gap-2">
            View all <ArrowRight size={14} />
          </button>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-5">
          {SHOWCASE.map((s, i) => (
            <div key={s.title} data-testid={`showcase-card-${i}`} className="card-surface overflow-hidden group">
              <div className="aspect-video relative overflow-hidden">
                <video src={s.video} autoPlay muted loop playsInline
                  className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
                <div className="absolute inset-0 bg-gradient-to-t from-[var(--card)] via-transparent to-transparent" />
              </div>
              <div className="p-4">
                <div className="overline">{s.tag}</div>
                <div className="font-display text-lg mt-1">{s.title}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Feature strip */}
      <section className="relative z-10 px-6 lg:px-14 py-16 border-t border-[var(--line)]">
        <div className="grid md:grid-cols-3 gap-6">
          {[
            { icon: Layers, t: "Block-based sub-app builder", d: "Compose hero, features, pricing, contact and charts — or ask Claude to redesign a block in plain English." },
            { icon: Rocket, t: "Export & handoff pipeline", d: "One-click .zip source bundles + iOS/Android build panel with client transfer mode for retainer endings." },
            { icon: ShieldCheck, t: "Multi-tenant isolation", d: "Role-based access, per-app activity logs, notifications, and secure DB partitioning by default." },
          ].map((f) => (
            <div key={f.t} className="card-surface p-6">
              <f.icon size={20} className="text-[var(--acc)]" />
              <div className="font-display text-xl mt-4">{f.t}</div>
              <p className="text-[var(--mut)] mt-2 text-sm">{f.d}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="relative z-10 px-6 lg:px-14 py-10 border-t border-[var(--line)] text-[var(--mut)] text-xs font-mono flex justify-between">
        <span>© 2026 Lucio/Studio · Agency Multi-Tenant Platform</span>
        <span>Built for Emergent</span>
      </footer>
    </div>
  );
}
