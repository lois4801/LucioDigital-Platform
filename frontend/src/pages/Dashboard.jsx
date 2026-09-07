import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import { toast } from "sonner";
import { Layers, Plus, Search, LogOut, Bell, Grid3x3, List, Play } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuLabel, DropdownMenuSeparator } from "@/components/ui/dropdown-menu";

const INDUSTRIES = ["All", "E-commerce", "SaaS Portals", "Internal Tools", "Service Booking"];
const KINDS = [["all", "All projects"], ["website", "Websites"], ["app", "Apps"]];
const STATUS_META = {
  active: { label: "Active", cls: "chip-active", dot: "" },
  maintenance: { label: "In Maintenance", cls: "chip-maint", dot: "amber" },
  handover: { label: "Ready for Handover", cls: "chip-handover", dot: "cyan" },
};

export default function Dashboard() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [industry, setIndustry] = useState("All");
  const [kind, setKind] = useState("all");
  const [inboxUnread, setInboxUnread] = useState(0);
  const [view, setView] = useState("grid");
  const [notifs, setNotifs] = useState([]);
  const [newOpen, setNewOpen] = useState(false);
  const [newApp, setNewApp] = useState({ name: "", industry: "SaaS Portals", description: "", kind: "website" });

  useEffect(() => { load(); loadNotifs(); api.get("/inbox").then(r => setInboxUnread(r.data.unread)).catch(() => {}); }, []);

  async function load() {
    setLoading(true);
    try { const { data } = await api.get("/apps"); setApps(data); }
    catch (e) { toast.error("Failed to load apps"); }
    finally { setLoading(false); }
  }
  async function loadNotifs() {
    try { const { data } = await api.get("/notifications"); setNotifs(data); } catch {}
  }

  const filtered = useMemo(() => apps.filter((a) => {
    if (industry !== "All" && a.industry !== industry) return false;
    if (kind !== "all" && (a.kind || "website") !== kind) return false;
    if (q && !`${a.name} ${a.description} ${(a.tags||[]).join(" ")}`.toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  }), [apps, industry, q, kind]);

  async function createApp() {
    if (!newApp.name) return toast.error("Name required");
    try {
      const { data } = await api.post("/apps", { ...newApp, status: "active" });
      setApps([data, ...apps]); setNewOpen(false);
      setNewApp({ name: "", industry: "SaaS Portals", description: "", kind: "website" });
      toast.success("Project created");
      nav(`/apps/${data.app_id}`);
    } catch (e) { toast.error("Create failed"); }
  }

  const counts = {
    total: apps.length,
    active: apps.filter(a => a.status === "active").length,
    maintenance: apps.filter(a => a.status === "maintenance").length,
    handover: apps.filter(a => a.status === "handover").length,
  };

  return (
    <div className="min-h-screen">
      {/* Top bar */}
      <header className="sticky top-0 z-30 backdrop-blur-xl bg-[var(--bg)]/85 border-b border-[var(--line)]">
        <div className="px-6 lg:px-10 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[var(--card)] border border-[var(--line)] flex items-center justify-center">
              <Layers size={18} className="text-[var(--acc)]" />
            </div>
            <div>
              <div className="font-display font-semibold tracking-tight text-lg leading-none">OmniStack<span className="text-[var(--acc)]"> AI</span></div>
              <div className="overline mt-1">Agency Workspace</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {inboxUnread > 0 && <span data-testid="dashboard-inbox-badge" className="chip chip-active">{inboxUnread} new leads</span>}
            <button data-testid="nav-deploy-hub-btn" onClick={() => nav("/deploy")} className="btn-ghost text-sm !py-2 !px-4 hidden md:inline-flex">Deployment Hub</button>
            <button data-testid="nav-portal-btn" onClick={() => nav("/portal")} className="btn-ghost text-sm !py-2 !px-4 hidden md:inline-flex">Client Portal</button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button data-testid="nav-notifications-btn" className="relative w-10 h-10 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-white/5">
                  <Bell size={16} />
                  {notifs.length > 0 && <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-[var(--acc)]" />}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-80 max-h-96 overflow-auto scrollbar-thin">
                <DropdownMenuLabel>Recent Activity</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {notifs.length === 0 && <div className="px-3 py-6 text-sm text-[var(--mut)] text-center">No activity yet</div>}
                {notifs.map((n) => (
                  <div key={n.log_id} className="px-3 py-2 text-xs">
                    <div className="font-mono text-[10px] uppercase text-[var(--mut)]">{n.kind}</div>
                    <div className="text-[var(--fg)] mt-0.5">{n.message}</div>
                  </div>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button data-testid="nav-user-menu" className="flex items-center gap-2 px-3 h-10 rounded-full border border-[var(--line)] hover:bg-white/5">
                  <div className="w-6 h-6 rounded-full bg-[var(--acc)] text-black text-xs flex items-center justify-center font-bold">
                    {(user?.name||user?.email||"?").charAt(0).toUpperCase()}
                  </div>
                  <span className="text-sm font-mono hidden md:inline">{user?.email}</span>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>{user?.name}</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem data-testid="nav-logout" onClick={async () => { await logout(); nav("/"); }}>
                  <LogOut size={14} className="mr-2" /> Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      <main data-testid="agency-master-dashboard" className="px-6 lg:px-10 py-8">
        {/* Hero row */}
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 mb-8">
          <div>
            <div className="overline mb-2">Master Workspace</div>
            <h1 className="font-display text-4xl lg:text-5xl font-semibold tracking-tighter">Your agency, at a glance.</h1>
            <p className="text-[var(--mut)] mt-2">Every client tenant, live metrics, and one-click handoff — all from here.</p>
          </div>
          <div className="grid grid-cols-4 gap-3 min-w-[420px]">
            {[
              { k: "Tenants", v: counts.total, dot: "" },
              { k: "Active", v: counts.active, dot: "" },
              { k: "Maint.", v: counts.maintenance, dot: "amber" },
              { k: "Handover", v: counts.handover, dot: "cyan" },
            ].map((s) => (
              <div key={s.k} className="card-surface px-4 py-3">
                <div className="flex items-center gap-2"><span className={`pulse-dot ${s.dot}`} /><span className="overline">{s.k}</span></div>
                <div className="font-display text-2xl font-semibold mt-1">{s.v}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Filter bar */}
        <div className="flex flex-col md:flex-row md:items-center gap-3 mb-6">
          <div className="relative flex-1 max-w-md">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--mut)]" />
            <input data-testid="dashboard-search-input" value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Search tenants, tags, tech…"
              className="w-full bg-[var(--card)] border border-[var(--line)] rounded-full pl-9 pr-4 py-2.5 text-sm font-mono focus:border-[var(--acc)] outline-none" />
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {KINDS.map(([k, l]) => (
              <button key={k} data-testid={`kind-filter-${k}-btn`} onClick={() => setKind(k)} className={`chip ${kind === k ? "!bg-[var(--cyan)]/12 !border-[var(--cyan)]/50 !text-[var(--cyan)]" : ""}`}>{l}</button>
            ))}
            <span className="w-px h-5 bg-[var(--line)] mx-1" />
            {INDUSTRIES.map((ind) => (
              <button key={ind} data-testid={`industry-filter-${ind.toLowerCase().replace(/\s+/g,'-')}-btn`}
                onClick={() => setIndustry(ind)}
                className={`chip ${industry === ind ? "!bg-[var(--acc)]/12 !border-[var(--acc)]/50 !text-[var(--acc)]" : ""}`}>
                {ind}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1 ml-auto card-surface !p-1">
            <button data-testid="view-grid-btn" onClick={() => setView("grid")}
              className={`w-9 h-9 rounded-lg flex items-center justify-center ${view === "grid" ? "bg-white/8 text-white" : "text-[var(--mut)]"}`}>
              <Grid3x3 size={15} />
            </button>
            <button data-testid="view-list-btn" onClick={() => setView("list")}
              className={`w-9 h-9 rounded-lg flex items-center justify-center ${view === "list" ? "bg-white/8 text-white" : "text-[var(--mut)]"}`}>
              <List size={15} />
            </button>
          </div>
          <Dialog open={newOpen} onOpenChange={setNewOpen}>
            <DialogTrigger asChild>
              <button data-testid="new-app-btn" className="btn-primary flex items-center gap-2">
                <Plus size={16} /> New project
              </button>
            </DialogTrigger>
            <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)]">
              <DialogHeader><DialogTitle className="font-display">Create a new project</DialogTitle></DialogHeader>
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  {[["website", "Website", "Framer-style site with pages, theme & AI"], ["app", "App", "Lovable-style app blueprint + starter code"]].map(([k, l, d]) => (
                    <button key={k} data-testid={`new-project-kind-${k}`} onClick={() => setNewApp({ ...newApp, kind: k })} className={`text-left p-3 rounded-xl border ${newApp.kind === k ? "border-[var(--acc)] bg-[var(--acc)]/10" : "border-[var(--line)] hover:bg-white/5"}`}>
                      <div className="font-display font-semibold">{l}</div><div className="text-[11px] text-[var(--mut)] mt-1">{d}</div></button>
                  ))}
                </div>
                <label className="block"><span className="overline block mb-1">Name</span>
                  <input data-testid="new-app-name-input" value={newApp.name} onChange={(e) => setNewApp({ ...newApp, name: e.target.value })}
                    className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm font-mono outline-none focus:border-[var(--acc)]" /></label>
                <label className="block"><span className="overline block mb-1">Industry</span>
                  <select data-testid="new-app-industry-select" value={newApp.industry} onChange={(e) => setNewApp({ ...newApp, industry: e.target.value })}
                    className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm font-mono outline-none">
                    {INDUSTRIES.filter(i => i !== "All").map(i => <option key={i}>{i}</option>)}
                  </select></label>
                <label className="block"><span className="overline block mb-1">Description</span>
                  <textarea data-testid="new-app-desc-input" rows={3} value={newApp.description} onChange={(e) => setNewApp({ ...newApp, description: e.target.value })}
                    className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm font-mono outline-none focus:border-[var(--acc)]" /></label>
                <button data-testid="new-app-create-btn" onClick={createApp} className="btn-primary w-full">Create {newApp.kind === "app" ? "app" : "website"}</button>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Grid or list */}
        {loading ? (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="card-surface aspect-[4/3.4] animate-pulse" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="card-surface p-12 text-center">
            <div className="overline mb-2">No tenants match</div>
            <div className="font-display text-xl">Try clearing filters or creating your first tenant.</div>
          </div>
        ) : view === "grid" ? (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5 fade-in">
            {filtered.map((a) => {
              const meta = STATUS_META[a.status] || STATUS_META.active;
              return (
                <div key={a.app_id} data-testid={`app-card-${a.name.toLowerCase().replace(/\s+/g,'-')}`}
                  onClick={() => nav(`/apps/${a.app_id}`)}
                  className="card-surface overflow-hidden cursor-pointer group">
                  <div className="relative aspect-video overflow-hidden">
                    {a.video_url ? (
                      <video src={a.video_url} poster={a.thumbnail || undefined} autoPlay muted loop playsInline preload="metadata"
                        className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
                    ) : (
                      <div className="w-full h-full bg-gradient-to-br from-[var(--card-hov)] to-[var(--bg-2)]" />
                    )}
                    <div className="absolute inset-0 bg-gradient-to-t from-[var(--card)] via-[var(--card)]/20 to-transparent" />
                    <div className="absolute top-3 left-3 flex gap-1.5">
                      <span className="chip">{a.industry}</span>
                      <span className={`chip ${a.kind === "app" ? "chip-handover" : ""}`}>{a.kind === "app" ? "App" : "Website"}</span>
                      {a.plan && <span className="chip chip-active">{a.plan}</span>}
                      {a.custom_domain && <span className={`chip ${a.domain_status === "verified" ? "chip-active" : "chip-maint"}`}>{a.custom_domain}</span>}
                    </div>
                    <div className="absolute top-3 right-3">
                      <span className={`chip ${meta.cls}`}><span className={`pulse-dot ${meta.dot}`} />{meta.label}</span>
                    </div>
                    <div className="absolute bottom-3 right-3 w-10 h-10 rounded-full bg-black/50 backdrop-blur flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                      <Play size={16} className="text-white ml-0.5" />
                    </div>
                  </div>
                  <div className="p-5">
                    <div className="font-display text-xl font-semibold">{a.name}</div>
                    <p className="text-sm text-[var(--mut)] mt-1 line-clamp-2">{a.description}</p>
                    <div className="mt-4 grid grid-cols-4 gap-2 font-mono text-[11px]">
                      <div><div className="text-[var(--dim)] uppercase">Uptime</div><div className="text-[var(--fg)]">{a.metrics?.uptime}%</div></div>
                      <div><div className="text-[var(--dim)] uppercase">CPU</div><div className="text-[var(--fg)]">{a.metrics?.cpu}%</div></div>
                      <div><div className="text-[var(--dim)] uppercase">Resp</div><div className="text-[var(--fg)]">{a.metrics?.response_ms}ms</div></div>
                      <div><div className="text-[var(--dim)] uppercase">24h</div><div className="text-[var(--fg)]">{a.metrics?.visitors_24h?.toLocaleString()}</div></div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="card-surface divide-y divide-[var(--line)] fade-in">
            {filtered.map((a) => {
              const meta = STATUS_META[a.status] || STATUS_META.active;
              return (
                <div key={a.app_id} onClick={() => nav(`/apps/${a.app_id}`)}
                  data-testid={`app-row-${a.name.toLowerCase().replace(/\s+/g,'-')}`}
                  className="flex items-center gap-4 px-4 py-3 cursor-pointer hover:bg-white/3">
                  <div className="w-3 h-3 rounded-full" style={{ background: a.color }} />
                  <div className="flex-1">
                    <div className="font-display text-base">{a.name}</div>
                    <div className="text-xs text-[var(--mut)]">{a.industry} · {a.description?.slice(0, 60)}</div>
                  </div>
                  <span className={`chip ${meta.cls}`}><span className={`pulse-dot ${meta.dot}`} />{meta.label}</span>
                  <div className="font-mono text-xs text-[var(--mut)] w-24 text-right">{a.metrics?.uptime}%</div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
