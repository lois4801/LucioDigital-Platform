import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Check, Inbox, Link2, Loader2, Sparkles, Star, X, LayoutDashboard } from "lucide-react";
import HeroMotionLayer from "@/components/editorial/HeroMotionLayer";
import MotionTuner from "@/components/editorial/MotionTuner";
import MotionPreviewOverlay from "@/components/editorial/MotionPreviewOverlay";

/** Permanently PUBLIC "Motion Systems — Live Template Index".
 *  Served at /motion and /hero-gallery. Admin-only controls (apply, favourites, client picks)
 *  render only for a signed-in owner; everything else is visible to any visitor. */
export default function HeroGallery() {
  const { user } = useAuth();
  const isAdmin = !!user;

  const [rows, setRows] = useState([]);
  const [industries, setIndustries] = useState([]);
  const [counts, setCounts] = useState({ active: 0, reserved: 0 });
  const [filter, setFilter] = useState("all");
  const [status, setStatus] = useState("all");
  const [q, setQ] = useState("");
  const [speed, setSpeed] = useState(1);
  const [intensity, setIntensity] = useState(1);
  const [previewKey, setPreviewKey] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);

  // client pick flow (public)
  const [pick, setPick] = useState("");
  const [form, setForm] = useState({ name: "", email: "", company: "", note: "" });
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState("");

  // admin-only state
  const [tenants, setTenants] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [tplTarget, setTplTarget] = useState("");
  const [target, setTarget] = useState("");
  const [favs, setFavs] = useState([]);
  const [applying, setApplying] = useState("");
  const [current, setCurrent] = useState("");
  const [picks, setPicks] = useState([]);
  const [showPicks, setShowPicks] = useState(false);

  useEffect(() => {
    api.get("/public/motion-reel").then(({ data }) => {
      setRows(data.heroes || []);
      setIndustries(data.industries || []);
      setCounts({ active: data.active || 0, reserved: data.reserved || 0 });
    }).catch(() => toast.error("Could not load the motion index"));
    const p = new URLSearchParams(window.location.search);
    if (p.get("industry")) setFilter(p.get("industry"));
    if (p.get("template")) setPreviewKey(p.get("template"));
    if (p.get("speed")) setSpeed(Number(p.get("speed")));
    if (p.get("intensity")) setIntensity(Number(p.get("intensity")));
  }, []);

  useEffect(() => {
    if (!isAdmin) return;
    api.get("/editorial/hero-favourites").then(r => setFavs(r.data.favourites || [])).catch(() => {});
    api.get("/editorial/profiles").then(r => {
      const t = Object.keys(r.data.templates || {});
      setTemplates(t); if (t[0]) setTplTarget(t[0]);
    }).catch(() => {});
    api.get("/apps").then(r => {
      const list = r.data.apps || r.data || [];
      setTenants(list);
      if (list[0]) setTarget(list[0].app_id);
    }).catch(() => {});
    api.get("/motion-picks").then(r => setPicks(r.data.picks || [])).catch(() => {});
  }, [isAdmin]);

  useEffect(() => {
    if (!isAdmin || !target) return;
    api.get(`/apps/${target}/site-mode`).then(r => {
      setCurrent(r.data.hero || "");
      setSpeed(r.data.motion_speed ?? 1);
      setIntensity(r.data.motion_intensity ?? 1);
    }).catch(() => {});
  }, [isAdmin, target]);

  const list = useMemo(() => rows.filter(r =>
    (filter === "all" || r.industry === filter)
    && (status === "all" || r.status === status)
    && (!q.trim() || `${r.hero} ${r.industry}`.toLowerCase().includes(q.trim().toLowerCase()))
  ), [rows, filter, status, q]);

  const share = () => {
    const u = new URL(window.location.origin + "/motion");
    if (filter !== "all") u.searchParams.set("industry", filter);
    u.searchParams.set("speed", String(speed));
    u.searchParams.set("intensity", String(intensity));
    navigator.clipboard?.writeText(u.toString());
    toast.success("Share link copied");
  };

  async function toggleFav(hero) {
    try {
      const { data } = await api.post("/editorial/hero-favourites", { hero });
      setFavs(data.favourites || []);
    } catch { toast.error("Could not update favourites"); }
  }

  async function apply(hero, opts: { speed?: number; intensity?: number } = {}) {
    if (!target) return toast.error("Pick a tenant first");
    const sp = opts.speed ?? speed, it = opts.intensity ?? intensity;
    setApplying(hero);
    try {
      await api.put(`/apps/${target}/site-mode`, { hero, style: "editorial", motion_speed: sp, motion_intensity: it });
      setCurrent(hero); setSpeed(sp); setIntensity(it);
      toast.success(`${hero} applied to ${tenants.find(t => t.app_id === target)?.name} · ${sp.toFixed(2)}x`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not apply that hero");
    } finally { setApplying(""); }
  }

  async function applyToTemplate(hero) {
    if (!tplTarget) return toast.error("Pick a template first");
    setApplying(hero);
    try {
      const { data } = await api.put(`/editorial/templates/${tplTarget}/hero`, { hero, apply_to_tenants: true });
      toast.success(`${tplTarget}: ${data.previous} → ${hero}${data.tenants_updated.length ? ` · ${data.tenants_updated.length} tenant(s) updated` : ""}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not update the template");
    } finally { setApplying(""); }
  }

  async function submitPick(e) {
    e.preventDefault();
    setSending(true);
    try {
      await api.post("/public/motion-picks", { hero: pick, ...form, speed, intensity });
      setSent(pick); setPick("");
      setForm({ name: "", email: "", company: "", note: "" });
      toast.success("Thanks — your pick is on its way to the studio");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not send your pick");
    } finally { setSending(false); }
  }

  const ordered = useMemo(() => isAdmin
    ? [...list].sort((a, b) => (favs.includes(b.hero) ? 1 : 0) - (favs.includes(a.hero) ? 1 : 0))
    : list, [list, favs, isAdmin]);

  return (
    <div className="min-h-screen bg-[#080808] text-white" data-testid="hero-gallery-page">
      <header className="sticky top-0 z-30 backdrop-blur-xl bg-[#080808]/92 border-b border-white/10 px-5 sm:px-10 py-4">
        <div className="flex flex-wrap items-center gap-3">
          <Link to="/" data-testid="motion-home-link" className="font-display text-lg font-semibold tracking-tight cursor-pointer">
            Lois<span className="text-[#84FF00]">-Tech</span>
          </Link>
          <div className="min-w-0">
            <div className="overline">Signature motion systems</div>
            <div className="font-display text-lg font-semibold" data-testid="motion-index-title">
              {rows.length} Motion Systems — Live Template Index
            </div>
            <div className="text-xs text-white/40 mt-0.5">
              <span data-testid="motion-count-active">{counts.active} active</span> · <span data-testid="motion-count-reserved">{counts.reserved} reserved</span>
            </div>
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2 w-full lg:w-auto min-w-0">
            <MotionTuner prefix="gallery" compact speed={speed} intensity={intensity}
              onChange={v => { if (v.speed !== undefined) setSpeed(v.speed); if (v.intensity !== undefined) setIntensity(v.intensity); }} />
            <button data-testid="motion-share-btn" onClick={share}
              className="chip cursor-pointer inline-flex items-center gap-1 hover:!text-white"><Link2 size={11} /> Share</button>
            {isAdmin && (
              <>
                <Link to="/dashboard" data-testid="hero-gallery-back"
                  className="chip cursor-pointer inline-flex items-center gap-1 hover:!text-white"><LayoutDashboard size={11} /> Dashboard</Link>
                <button data-testid="hero-gallery-picks-btn" onClick={() => setShowPicks(p => !p)}
                  className={`chip cursor-pointer inline-flex items-center gap-1 ${showPicks ? "chip-active" : "hover:!text-white"}`}>
                  <Inbox size={11} /> Client picks {picks.length ? `(${picks.length})` : ""}
                </button>
                <select data-testid="hero-gallery-tenant" value={target} onChange={e => setTarget(e.target.value)}
                  className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm outline-none focus:border-white/30">
                  {tenants.map(t => <option key={t.app_id} value={t.app_id}>{t.name}</option>)}
                </select>
                <select data-testid="hero-gallery-template" value={tplTarget} onChange={e => setTplTarget(e.target.value)}
                  className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm outline-none focus:border-white/30">
                  {templates.map(k => <option key={k} value={k}>{k}</option>)}
                </select>
              </>
            )}
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input data-testid="motion-search" value={q} onChange={e => setQ(e.target.value)} placeholder="Search a motion…"
            className="bg-white/5 border border-white/10 rounded-full px-4 py-1.5 text-sm outline-none focus:border-white/30 w-full sm:w-56" />
          <div className="flex flex-wrap gap-1.5" data-testid="motion-status-filters">
            {[["all", "All statuses"], ["active", "Active"], ["reserved", "Reserved"]].map(([v, l]) => (
              <button key={v} data-testid={`motion-status-${v}`} onClick={() => setStatus(v)}
                className={`chip cursor-pointer ${status === v ? "chip-active" : "hover:!text-white"}`}>{l}</button>
            ))}
          </div>
          <button data-testid="motion-filters-toggle" onClick={() => setFiltersOpen(o => !o)}
            className={`chip cursor-pointer sm:hidden ${filtersOpen ? "chip-active" : "hover:!text-white"}`}>
            {filter === "all" ? "Industries" : filter} {filtersOpen ? "▲" : "▼"}
          </button>
          <div className={`${filtersOpen ? "flex" : "hidden"} sm:flex flex-wrap gap-1.5 w-full sm:w-auto max-h-[38vh] sm:max-h-none overflow-y-auto`}>
            <button data-testid="motion-filter-all" onClick={() => { setFilter("all"); setFiltersOpen(false); }}
              className={`chip cursor-pointer ${filter === "all" ? "chip-active" : "hover:!text-white"}`}>All industries</button>
            {industries.map(i => (
              <button key={i} data-testid={`motion-filter-${i.replace(/[^a-zA-Z0-9]+/g, "-")}`} onClick={() => { setFilter(i); setFiltersOpen(false); }}
                className={`chip cursor-pointer ${filter === i ? "chip-active" : "hover:!text-white"}`}>{i}</button>
            ))}
          </div>
        </div>
      </header>

      {isAdmin && showPicks && (
        <section className="px-5 sm:px-10 pt-6" data-testid="hero-picks-panel">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <div className="overline">Client picks from the public index</div>
            {picks.length === 0
              ? <div className="text-sm text-white/40 mt-2" data-testid="hero-picks-empty">No picks yet — share <span className="font-mono">/motion</span> with a client.</div>
              : <ul className="mt-3 divide-y divide-white/10">
                {picks.map(p => (
                  <li key={p.pick_id} data-testid={`hero-pick-${p.pick_id}`} className="py-2.5 flex flex-wrap items-center gap-2 text-sm">
                    <span className="font-semibold">{p.hero}</span>
                    <span className="text-white/45">{p.name || "—"} · {p.email}{p.company ? ` · ${p.company}` : ""}</span>
                    <span className="chip ml-auto">{Number(p.speed || 1).toFixed(2)}x · {Number(p.intensity || 1).toFixed(2)}</span>
                    <button data-testid={`hero-pick-apply-${p.pick_id}`}
                      onClick={() => apply(p.hero, { speed: Number(p.speed) || 1, intensity: Number(p.intensity) || 1 })}
                      className="chip cursor-pointer hover:!text-white">Apply to tenant</button>
                  </li>
                ))}
              </ul>}
          </div>
        </section>
      )}

      <main className="px-5 sm:px-10 py-8 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5" data-testid="hero-gallery-grid">
        {ordered.map(r => {
          const active = r.status === "active";
          return (
            <article key={r.hero} data-testid={`motion-card-${r.hero}`}
              className={`rounded-2xl border overflow-hidden bg-black transition-colors ${sent === r.hero ? "border-[#84FF00]" : current === r.hero ? "border-[var(--acc)]" : favs.includes(r.hero) ? "border-amber-400/60" : "border-white/10 hover:border-white/30"}`}>
              <button data-testid={`motion-open-${r.hero}`} onClick={() => r.template_key && setPreviewKey(r.template_key)}
                title={r.template_key ? "Open this live motion system" : "No template assigned yet"}
                className="relative block w-full h-44 cursor-pointer text-left">
                <HeroMotionLayer hero={r.hero} accent={r.accent} speed={speed} intensity={intensity} />
                <span className="absolute inset-0 grid place-items-center">
                  <span className="font-mono text-[11px] text-white/40">{r.hero}</span>
                </span>
                <span data-testid={`motion-status-badge-${r.hero}`}
                  className={`absolute top-2 left-2 rounded-full px-2.5 py-1 text-[10px] font-bold tracking-[0.14em] ${active ? "bg-[#84FF00] text-black" : "bg-white/10 text-white/55 border border-white/15"}`}>
                  {active ? "ACTIVE" : "RESERVED"}
                </span>
              </button>
              <div className="p-4">
                <div className="flex items-start gap-2">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold truncate">{r.hero}</div>
                    <div className="text-[11px] text-white/55 truncate" data-testid={`motion-industry-${r.hero}`}>
                      {r.hero} — {r.industry}
                    </div>
                  </div>
                  {isAdmin && (
                    <button data-testid={`hero-fav-${r.hero}`} onClick={() => toggleFav(r.hero)} title="Favourite"
                      className={`ml-auto shrink-0 w-8 h-8 rounded-full bg-white/5 border border-white/10 flex items-center justify-center cursor-pointer ${favs.includes(r.hero) ? "text-amber-400" : "text-white/45 hover:text-amber-300"}`}>
                      <Star size={13} fill={favs.includes(r.hero) ? "currentColor" : "none"} />
                    </button>
                  )}
                </div>
                <div className="mt-3 flex items-center gap-1.5 flex-wrap">
                  <span className="chip" data-testid={`motion-template-badge-${r.hero}`}>TEMPLATE{r.template_key ? ` · ${r.template_key}` : ""}</span>
                  <span className="chip" data-testid={`motion-tenant-badge-${r.hero}`}>
                    {r.tenant_count ? `Tenant · ${r.tenants[0]}${r.tenant_count > 1 ? ` +${r.tenant_count - 1}` : ""}` : "Tenant · none yet"}
                  </span>
                  <div className="ml-auto flex items-center gap-1.5">
                    {isAdmin ? (
                      <>
                        <button data-testid={`hero-apply-template-${r.hero}`} disabled={applying === r.hero} onClick={() => applyToTemplate(r.hero)}
                          className="chip cursor-pointer hover:!text-white disabled:opacity-60">Template</button>
                        <button data-testid={`hero-apply-${r.hero}`} disabled={applying === r.hero || current === r.hero} onClick={() => apply(r.hero)}
                          className={`text-xs !py-2 !px-3 rounded-full inline-flex items-center gap-1.5 cursor-pointer ${current === r.hero ? "chip chip-active" : "bg-white text-black font-semibold hover:bg-white/85"} disabled:opacity-70`}>
                          {applying === r.hero ? <Loader2 size={11} className="animate-spin" /> : current === r.hero ? <Check size={11} /> : null}
                          {current === r.hero ? "Active" : "Tenant"}
                        </button>
                      </>
                    ) : (
                      <button data-testid={`motion-pick-${r.hero}`} onClick={() => setPick(r.hero)}
                        className="text-xs !py-2 !px-3 rounded-full inline-flex items-center gap-1.5 bg-white text-black font-semibold hover:bg-white/85 cursor-pointer">
                        {sent === r.hero ? <><Check size={11} /> Sent</> : <><Sparkles size={11} /> Choose</>}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </article>
          );
        })}
        {!ordered.length && <div className="text-sm text-white/40" data-testid="motion-empty">No motion matches that filter.</div>}
      </main>

      {pick && (
        <div className="fixed inset-0 z-[120] bg-black/80 backdrop-blur-sm grid place-items-center p-5" data-testid="motion-pick-modal">
          <form onSubmit={submitPick} className="w-full max-w-md rounded-2xl border border-white/10 bg-[#0c0c0c] p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="overline">Choose this look</div>
                <div className="font-display text-xl font-semibold mt-1">{pick.replace(/-/g, " ")}</div>
              </div>
              <button type="button" data-testid="motion-pick-close" onClick={() => setPick("")} aria-label="Close"
                className="w-9 h-9 rounded-full border border-white/15 flex items-center justify-center text-white/60 hover:text-white cursor-pointer"><X size={15} /></button>
            </div>
            <div className="relative h-28 rounded-xl overflow-hidden bg-black border border-white/10 mt-4">
              <HeroMotionLayer hero={pick} accent="#84FF00" speed={speed} intensity={intensity} />
            </div>
            <div className="mt-4 space-y-2.5">
              <input data-testid="motion-pick-name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="Your name" className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm outline-none focus:border-white/30" />
              <input data-testid="motion-pick-email" required type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                placeholder="Email *" className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm outline-none focus:border-white/30" />
              <input data-testid="motion-pick-company" value={form.company} onChange={e => setForm(f => ({ ...f, company: e.target.value }))}
                placeholder="Company" className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm outline-none focus:border-white/30" />
              <textarea data-testid="motion-pick-note" value={form.note} onChange={e => setForm(f => ({ ...f, note: e.target.value }))}
                placeholder="Anything you want us to know" rows={3}
                className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm outline-none focus:border-white/30" />
            </div>
            <button data-testid="motion-pick-submit" disabled={sending}
              className="mt-4 w-full rounded-full bg-[#84FF00] text-black font-semibold py-2.5 text-sm inline-flex items-center justify-center gap-2 disabled:opacity-70 cursor-pointer">
              {sending ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />} Send my pick
            </button>
            <div className="mt-2 text-[11px] text-white/35 text-center">
              Playing at {speed.toFixed(2)}x · intensity {intensity.toFixed(2)} — we'll build it exactly like this.
            </div>
          </form>
        </div>
      )}

      <MotionPreviewOverlay templateKey={previewKey} onClose={() => setPreviewKey("")} onSwitch={setPreviewKey} />
    </div>
  );
}
