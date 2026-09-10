import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import api from "@/lib/api";
import { ArrowLeft, Check, Loader2, Star } from "lucide-react";
import HeroMotionLayer from "@/components/editorial/HeroMotionLayer";

// All signature hero engines side by side, with one-click apply to any tenant.
export default function HeroGallery() {
  const nav = useNavigate();
  const [heroes, setHeroes] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [tplTarget, setTplTarget] = useState("");
  const [favs, setFavs] = useState([]);
  const [target, setTarget] = useState("");
  const [applying, setApplying] = useState("");
  const [current, setCurrent] = useState("");

  useEffect(() => {
    api.get("/editorial/heroes").then(r => setHeroes(r.data.heroes || [])).catch(() => {});
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
  }, []);

  async function toggleFav(hero) {
    try {
      const { data } = await api.post("/editorial/hero-favourites", { hero });
      setFavs(data.favourites || []);
    } catch { toast.error("Could not update favourites"); }
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

  useEffect(() => {
    if (!target) return;
    api.get(`/apps/${target}/site-mode`).then(r => setCurrent(r.data.hero || "")).catch(() => {});
  }, [target]);

  const accent = "#10B981";

  async function apply(hero) {
    if (!target) return toast.error("Pick a tenant first");
    setApplying(hero);
    try {
      await api.put(`/apps/${target}/site-mode`, { hero, style: "editorial" });
      setCurrent(hero);
      toast.success(`${hero} applied to ${tenants.find(t => t.app_id === target)?.name}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not apply that hero");
    } finally { setApplying(""); }
  }

  return (
    <div className="min-h-screen" data-testid="hero-gallery-page">
      <header className="sticky top-0 z-30 backdrop-blur-xl bg-[var(--bg)]/90 border-b border-[var(--line)] px-6 lg:px-10 py-4 flex flex-wrap items-center gap-3">
        <button data-testid="hero-gallery-back" onClick={() => nav("/dashboard")} className="btn-ghost text-sm !py-2 !px-4 inline-flex items-center gap-2"><ArrowLeft size={14} /> Dashboard</button>
        <div className="min-w-0">
          <div className="overline">Signature hero engines</div>
          <div className="font-display text-lg font-semibold">{heroes.length} motion systems</div>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <span className="overline hidden sm:inline">Tenant</span>
          <select data-testid="hero-gallery-tenant" value={target} onChange={e => setTarget(e.target.value)}
            className="bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm outline-none focus:border-[var(--acc)]">
            {tenants.map(t => <option key={t.app_id} value={t.app_id}>{t.name}</option>)}
          </select>
          <span className="overline hidden sm:inline">Template</span>
          <select data-testid="hero-gallery-template" value={tplTarget} onChange={e => setTplTarget(e.target.value)}
            className="bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm outline-none focus:border-[var(--acc)]">
            {templates.map(k => <option key={k} value={k}>{k}</option>)}
          </select>
        </div>
      </header>

      <main className="px-6 lg:px-10 py-8 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5" data-testid="hero-gallery-grid">
        {[...heroes].sort((a, b) => (favs.includes(b.hero) ? 1 : 0) - (favs.includes(a.hero) ? 1 : 0)).map(({ hero, used_by }) => (
          <div key={hero} data-testid={`hero-card-${hero}`}
            className={`rounded-2xl border overflow-hidden bg-[#080808] transition-colors ${current === hero ? "border-[var(--acc)]" : favs.includes(hero) ? "border-amber-400/60" : "border-[var(--line)] hover:border-white/25"}`}>
            <div className="relative h-44">
              <HeroMotionLayer hero={hero} accent={accent} />
              <div className="absolute inset-0 grid place-items-center">
                <span className="font-mono text-[11px] text-white/40 px-2 text-center">{hero}</span>
              </div>
              <button data-testid={`hero-fav-${hero}`} onClick={() => toggleFav(hero)} title="Favourite"
                className={`absolute top-2 right-2 w-8 h-8 rounded-full bg-black/60 border border-white/10 flex items-center justify-center transition-colors ${favs.includes(hero) ? "text-amber-400" : "text-white/45 hover:text-amber-300"}`}>
                <Star size={13} fill={favs.includes(hero) ? "currentColor" : "none"} />
              </button>
            </div>
            <div className="p-4 flex items-center gap-2">
              <div className="min-w-0">
                <div className="text-sm font-semibold truncate">{hero}</div>
                <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--dim)] truncate">{used_by || "unassigned"}</div>
              </div>
              <div className="ml-auto shrink-0 flex items-center gap-1.5">
                <button data-testid={`hero-apply-template-${hero}`} disabled={applying === hero} onClick={() => applyToTemplate(hero)}
                  title={`Set as ${tplTarget} template hero — new tenants inherit it`}
                  className="chip cursor-pointer hover:!text-white disabled:opacity-60">Template</button>
                <button data-testid={`hero-apply-${hero}`} disabled={applying === hero || current === hero} onClick={() => apply(hero)}
                  className={`text-xs !py-2 !px-3 rounded-full inline-flex items-center gap-1.5 ${current === hero ? "chip chip-active" : "btn-primary"} disabled:opacity-70`}>
                  {applying === hero ? <Loader2 size={11} className="animate-spin" /> : current === hero ? <Check size={11} /> : null}
                  {current === hero ? "Active" : "Tenant"}
                </button>
              </div>
            </div>
          </div>
        ))}
      </main>
    </div>
  );
}
