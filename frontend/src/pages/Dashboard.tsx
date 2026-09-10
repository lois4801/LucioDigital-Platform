import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { CountUp, fast, stagger, fadeUp } from "@/components/motion";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import { toast } from "sonner";
import { Layers, Plus, Search, LogOut, Bell, Grid3x3, List, Play, Star, Archive, RotateCcw, Trash2, Sparkles, Check, Rocket, FlaskConical, Loader2, ExternalLink } from "lucide-react";
import ShowcaseManager from "@/components/ShowcaseManager";
import RolloutModal from "@/components/RolloutModal";
import PushToOnePicker from "@/components/PushToOnePicker";
import LandingTextEditor from "@/components/LandingTextEditor";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuLabel, DropdownMenuSeparator } from "@/components/ui/dropdown-menu";
import { CursorFXPicker } from "@/components/CursorFX";
import { pollImport, ImportProgress, ImportReport } from "@/components/builder/WebImport";
import { LockStateBadge } from "@/components/locks/LockContext";
import SkinToggle from "@/components/SkinToggle";
import CaseStudyEditor from "@/components/CaseStudyEditor";
import EditorialRolloutCard from "@/components/EditorialRolloutCard";

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
  const [newApp, setNewApp] = useState({ name: "", industry: "SaaS Portals", description: "", kind: "website", url: "" });
  const [importing, setImporting] = useState(false);
  const [impStage, setImpStage] = useState(null);
  const [impStarted, setImpStarted] = useState(0);
  const [impReport, setImpReport] = useState(null);
  const [zipFile, setZipFile] = useState(null);
  const [lockStates, setLockStates] = useState({});
  const [showArchived, setShowArchived] = useState(false);
  const [rolloutOpen, setRolloutOpen] = useState(false);
  const [rolloutTarget, setRolloutTarget] = useState(null);
  const [staging, setStaging] = useState(null);
  const [landingEditor, setLandingEditor] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [caseStudyApp, setCaseStudyApp] = useState(null);
  const [redesign, setRedesign] = useState(null);

  async function runTest() { /* Run Test removed from the Test Lab UI. */ }
  const [archived, setArchived] = useState([]);
  const [deleting, setDeleting] = useState("");
  const [trash, setTrash] = useState([]);
  const [picks, setPicks] = useState([]);
  const [upBusy, setUpBusy] = useState(false);
  const [pluginBusy, setPluginBusy] = useState(false);
  const legacyCount = apps.filter(a => !a.theme?.design_v2).length;
  async function bulkUpgrade() {
    if (!window.confirm(`Upgrade ${legacyCount} site(s) to the current design standard? Copy and images stay exactly as they are, and each site keeps an undo point in History.`)) return;
    setUpBusy(true);
    try {
      const { data } = await api.post("/site/upgrade-design-all");
      toast.success(`${data.count} site(s) upgraded — content untouched`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Bulk upgrade failed"); } finally { setUpBusy(false); }
  }

  useEffect(() => { load(); loadNotifs(); loadArchived(); loadTrash(); loadPicks(); api.get("/redesign/pending").then(r => setRedesign(r.data)).catch(() => {}); api.get("/inbox").then(r => setInboxUnread(r.data.unread)).catch(() => {}); api.get("/locks/summary").then(r => setLockStates(r.data.tenants || {})).catch(() => {}); }, []);
  useEffect(() => { load(); }, [showArchived]);

  async function loadArchived() {
    try { const { data } = await api.get("/apps/archived/summary"); setArchived(data.tenants); } catch { /* non-blocking */ }
  }
  async function loadPicks() {
    try { const { data } = await api.get("/template-shares"); setPicks(data.pending || []); } catch { /* non-blocking */ }
  }
  async function restoreTenant(a) {
    try {
      await api.post(`/apps/${a.app_id}/archive`, { archived: false });
      setArchived(list => list.filter(x => x.app_id !== a.app_id));
      toast.success(`${a.name} restored with all its pages, leads and settings`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not restore that tenant"); }
  }
  async function purgeTenant(a) {
    const s = a.snapshot || {};
    if (!window.confirm(`Permanently delete ${a.name}? This erases ${s.pages || 0} page(s), ${s.leads || 0} lead(s), ${s.bookings || 0} booking(s) and ${s.files || 0} file(s). This cannot be undone.`)) return;
    if (!window.confirm(`Last check — type-free confirmation. Delete ${a.name} forever?`)) return;
    try {
      await api.delete(`/apps/${a.app_id}/purge`);
      setArchived(list => list.filter(x => x.app_id !== a.app_id));
      toast.success(`${a.name} permanently deleted`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not delete that tenant"); }
  }
  /** Delete = move to the 30-day trash. Nothing is erased: the site goes offline and everything
   *  (pages, leads, bookings, files) stays restorable for 30 days. */
  async function deleteTenant(a) {
    if (a.is_test_lab || a.protected) return toast.error("The master workspace cannot be deleted");
    if (!window.confirm(`Delete ${a.name}? Its site goes offline now and you can restore it any time in the next 30 days.`)) return;
    setDeleting(a.app_id);
    try {
      const { data } = await api.post(`/apps/${a.app_id}/trash`);
      setApps(list => list.filter(x => x.app_id !== a.app_id));
      toast.success(`${a.name} deleted — restorable for ${data.days_left} days`);
      loadTrash();
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not delete that tenant");
    } finally { setDeleting(""); }
  }
  async function loadTrash() {
    try { const { data } = await api.get("/apps-trash"); setTrash(data.tenants || []); } catch { /* non-blocking */ }
  }
  async function untrash(t) {
    try {
      await api.post(`/apps/${t.app_id}/untrash`);
      setTrash(list => list.filter(x => x.app_id !== t.app_id));
      toast.success(`${t.name} restored with all its pages and leads`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not restore that tenant"); }
  }
  async function eraseNow(t) {
    if (!window.confirm(`Erase ${t.name} forever? This removes ${t.pages || 0} page(s) and ${t.leads || 0} lead(s) and cannot be undone.`)) return;
    try {
      await api.delete(`/apps/${t.app_id}/trash`);
      setTrash(list => list.filter(x => x.app_id !== t.app_id));
      toast.success(`${t.name} erased permanently`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not erase that tenant"); }
  }
  async function ackPick(p) {
    try { await api.post(`/template-shares/${p.token}/ack`); setPicks(list => list.filter(x => x.token !== p.token)); }
    catch { /* non-blocking */ }
  }

  async function load() {
    setLoading(true);
    try { const { data } = await api.get("/apps", { params: showArchived ? { archived: true } : {} }); setApps(data); }
    catch (e) { toast.error("Failed to load apps"); }
    finally { setLoading(false); }
  }

  async function toggleArchive(a) {
    const archiving = !showArchived;
    if (archiving && !window.confirm(`Archive ${a.name}? The site goes offline and disappears from your workspace. Its pages, leads, bookings, members and files are all kept and come back if you restore it — and every lead stays in your admin inbox.`)) return;
    try {
      const { data } = await api.post(`/apps/${a.app_id}/archive`, { archived: archiving });
      setApps(list => list.filter(x => x.app_id !== a.app_id));
      loadArchived();
      toast.success(archiving ? `${a.name} archived — ${data.leads_kept} lead(s) kept in your inbox` : `${a.name} restored`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not archive that tenant"); }
  }
  async function toggleFeatured(a) {
    try {
      const { data } = await api.patch(`/apps/${a.app_id}/showcase`, { featured: !a.featured });
      setApps(list => list.map(x => x.app_id === a.app_id ? { ...x, featured: data.featured, showcase_order: data.showcase_order } : x));
      toast.success(data.featured ? `${a.name} is now featured on the landing page` : `${a.name} removed from the landing page`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not update that tenant"); }
  }

  async function loadNotifs() {
    try { const { data } = await api.get("/notifications"); setNotifs(data); }
    catch (e) { console.warn("Could not load notifications", e?.response?.status || e?.message); }
  }

  const filtered = useMemo(() => apps.filter((a) => {
    if (industry !== "All" && a.industry !== industry) return false;
    if (kind !== "all" && (a.kind || "website") !== kind) return false;
    if (q && !`${a.name} ${a.description} ${(a.tags||[]).join(" ")}`.toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  }).sort((a, b) => (b.is_test_lab ? 1 : 0) - (a.is_test_lab ? 1 : 0)), [apps, industry, q, kind]);

  async function createApp() {
    if (!newApp.name) return toast.error("Name required");
    try {
      const { name, industry, description, kind, url } = newApp;
      const { data } = await api.post("/apps", { name, industry, description, kind, status: "active" });
      setApps([data, ...apps]);
      setNewApp({ name: "", industry: "SaaS Portals", description: "", kind: "website", url: "" });
      if (zipFile) {
        setImporting(true); setImpStage({ stage: "scanning", stage_detail: `Unpacking ${zipFile.name}` }); setImpStarted(Date.now());
        try {
          const fd = new FormData(); fd.append("file", zipFile); fd.append("mode", "replace"); fd.append("apply_theme", "true");
          const { data: job } = await api.post(`/apps/${data.app_id}/site/import-zip`, fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 600000 });
          const res = await pollImport(data.app_id, job.job_id, { onStage: setImpStage });
          setImpReport({ ...res.report, app_id: data.app_id });
          toast.success(`Imported ${res.applied?.pages?.length || res.pages.length} page(s) from ${zipFile.name}`);
          setZipFile(null);
          return;
        } catch (e) { toast.error(e.response?.data?.detail || e.message || "ZIP import failed — the project was still created"); }
        finally { setImporting(false); setImpStage(null); }
      }
      if (url?.trim()) {
        setImporting(true); setImpStage({ stage: "scanning", stage_detail: "Starting full-site crawl" }); setImpStarted(Date.now());
        try {
          const { data: job } = await api.post(`/apps/${data.app_id}/site/import`, { url, mode: "replace", apply_theme: true });
          const res = await pollImport(data.app_id, job.job_id, { onStage: setImpStage });
          setImpReport({ ...res.report, app_id: data.app_id });
          toast.success(`Imported ${res.pages.length} page(s) from ${url}`);
          return;
        } catch (e) { toast.error(e.response?.data?.detail || e.message || "Website import failed — the project was still created"); }
        finally { setImporting(false); setImpStage(null); }
      } else toast.success("Project created");
      setNewOpen(false);
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
          <button data-testid="dashboard-logo-home-btn" onClick={() => nav("/")} title="View your landing page"
            className="flex items-center gap-3 group cursor-pointer text-left">
            <div className="w-9 h-9 rounded-lg bg-[var(--card)] border border-[var(--line)] flex items-center justify-center group-hover:border-[var(--acc)]/50 transition-colors">
              <Layers size={18} className="text-[var(--acc)]" />
            </div>
            <div>
              <div className="font-display font-semibold tracking-tight text-lg leading-none">Lois-<span className="text-[var(--acc)]">Tech</span></div>
              <div className="overline mt-1">Agency Workspace</div>
            </div>
          </button>
          <div className="flex items-center gap-2">
            {legacyCount > 0 && <button data-testid="bulk-upgrade-design-btn" onClick={bulkUpgrade} disabled={upBusy}
              className="chip chip-maint cursor-pointer hover:!text-white disabled:opacity-50">{upBusy ? "Upgrading…" : `Upgrade ${legacyCount} legacy site${legacyCount === 1 ? "" : "s"}`}</button>}
            <button data-testid="dashboard-inbox-badge" onClick={() => nav("/leads")} className={`chip cursor-pointer hover:!text-white transition-colors ${inboxUnread > 0 ? "chip-active badge-glow" : ""}`}>{inboxUnread > 0 ? `${inboxUnread} new lead${inboxUnread === 1 ? "" : "s"}` : "Leads"}</button>
            <button data-testid="nav-view-landing-btn" onClick={() => nav("/")} title="Open your landing page"
              className="btn-ghost text-sm !py-2 !px-4 inline-flex items-center gap-2">
              <ExternalLink size={13} /> <span className="hidden sm:inline">View landing page</span>
            </button>
            <button data-testid="nav-landing-text-btn" onClick={() => setLandingEditor(true)} className="btn-ghost text-sm !py-2 !px-4 hidden md:inline-flex">Edit landing text</button>
            <button data-testid="nav-rollout-history-btn" onClick={() => nav("/rollout-history")} className="btn-ghost text-sm !py-2 !px-4 hidden md:inline-flex">Rollout History</button>
            <button data-testid="nav-deploy-hub-btn" onClick={() => nav("/deploy")} className="btn-ghost text-sm !py-2 !px-4 hidden md:inline-flex">Deployment Hub</button>
            <label data-testid="import-plugin-btn" className="btn-ghost text-sm !py-2 !px-4 hidden md:inline-flex cursor-pointer">
              {pluginBusy ? "Restoring…" : "Import plugin package"}
              <input type="file" accept=".zip" className="hidden" disabled={pluginBusy}
                onChange={async (e) => {
                  const f = e.target.files?.[0]; e.target.value = "";
                  if (!f) return;
                  setPluginBusy(true);
                  try {
                    const fd = new FormData(); fd.append("file", f);
                    const { data } = await api.post("/site/import-plugin", fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 600000 });
                    toast.success(`Restored "${data.app.name}" — ${data.restored.pages} page(s)`);
                    setApps((a) => [data.app, ...a]);
                    nav(`/apps/${data.app.app_id}`);
                  } catch (err) { toast.error(err.response?.data?.detail || "Could not restore that plugin package"); }
                  finally { setPluginBusy(false); }
                }} />
            </label>
            <button data-testid="nav-portal-btn" onClick={() => nav("/portal")} className="btn-ghost text-sm !py-2 !px-4 hidden md:inline-flex">Client Portal</button>
            <CursorFXPicker />
            <SkinToggle />
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
                <DropdownMenuItem data-testid="nav-logout" onClick={async () => { nav("/login", { replace: true }); await logout(); }}>
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
            <motion.h1 initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: fast }} className="font-display text-4xl lg:text-5xl font-semibold tracking-tighter">Your agency, at a glance.</motion.h1>
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
                <div className="font-display text-2xl font-semibold mt-1" data-testid={`stat-${s.k.toLowerCase().replace('.', '')}`}><CountUp value={s.v} /></div>
              </div>
            ))}
          </div>
        </div>

        {/* Always-live: no approval banner, no pending state. */}
        <EditorialRolloutCard />

        {/* Client template picks */}        {picks.length > 0 && (
          <div className="space-y-2 mb-6" data-testid="client-picks">
            {picks.map(p => (
              <div key={p.token} data-testid={`client-pick-${p.token}`} className="card-surface p-4 flex flex-wrap items-center gap-3 !border-[var(--acc)]/40">
                <Check size={16} className="text-[var(--acc)]" />
                <div className="min-w-0">
                  <div className="font-display text-base"><span className="text-[var(--acc)]">{p.client_name}</span> chose the {p.selected_brand} design</div>
                  {p.client_note && <div className="text-xs text-[var(--mut)] mt-0.5">“{p.client_note}”</div>}
                </div>
                <div className="ml-auto flex items-center gap-2">
                  <button data-testid={`client-pick-create-${p.token}`} onClick={() => nav("/templates")} className="btn-primary text-xs !py-1.5 !px-3">Create the tenant</button>
                  <button data-testid={`client-pick-dismiss-${p.token}`} onClick={() => ackPick(p)} className="btn-ghost text-xs !py-1.5 !px-3">Dismiss</button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Filter bar */}
        <ShowcaseManager apps={apps} onChange={(next) => setApps(list => list.map(x => next.find(n => n.app_id === x.app_id) || x))} />
        <div className="flex flex-col md:flex-row md:items-center gap-3 mb-6">
          <div className="relative flex-1 max-w-md">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--mut)]" />
            <input data-testid="dashboard-search-input" value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Search tenants, tags, tech…"
              className="w-full bg-[var(--card)] border border-[var(--line)] rounded-full pl-9 pr-4 py-2.5 text-sm font-mono focus:border-[var(--acc)] outline-none" />
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {KINDS.map(([k, l]) => (
              <button key={k} data-testid={`kind-filter-${k}-btn`} onClick={() => setKind(k)} className={`chip relative ${kind === k ? "!border-[var(--cyan)]/50 !text-[var(--cyan)]" : ""}`}>{kind === k && <motion.span layoutId="kind-pill" className="absolute inset-0 rounded-full bg-[var(--cyan)]/12" transition={{ duration: 0.25, ease: fast }} />}<span className="relative">{l}</span></button>
            ))}
            <span className="w-px h-5 bg-[var(--line)] mx-1" />
            <button data-testid="toggle-archived-btn" onClick={() => setShowArchived(v => !v)}
              className={`chip cursor-pointer inline-flex items-center gap-1.5 ${showArchived ? "!border-[var(--acc)]/50 !text-[var(--acc)]" : ""}`}>
              <Archive size={12} /> {showArchived ? "Viewing archived" : "Archived"}
            </button>
            <span className="w-px h-5 bg-[var(--line)] mx-1" />
            {INDUSTRIES.map((ind) => (
              <button key={ind} data-testid={`industry-filter-${ind.toLowerCase().replace(/\s+/g,'-')}-btn`}
                onClick={() => setIndustry(ind)}
                className={`chip relative ${industry === ind ? "!border-[var(--acc)]/50 !text-[var(--acc)]" : ""}`}>
                {industry === ind && <motion.span layoutId="industry-pill" className="absolute inset-0 rounded-full bg-[var(--acc)]/12" transition={{ duration: 0.25, ease: fast }} />}<span className="relative">{ind}</span>
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
            <button data-testid="new-app-btn" onClick={() => nav("/templates")} className="btn-primary flex items-center gap-2">
              <Plus size={16} /> New project
            </button>
            <DialogTrigger asChild>
              <button data-testid="new-app-advanced-btn" className="btn-ghost text-sm !py-2 !px-4">Blank / import</button>
            </DialogTrigger>
            <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)]">
              <DialogHeader><DialogTitle className="font-display">Create a blank project or import one</DialogTitle></DialogHeader>
              <div className="space-y-3">
                <button data-testid="new-app-gallery-link" onClick={() => { setNewOpen(false); nav("/templates"); }}
                  className="w-full text-left p-3 rounded-xl border border-[var(--acc)]/40 bg-[var(--acc)]/8 hover:bg-[var(--acc)]/12 flex items-center gap-3">
                  <Sparkles size={16} className="text-[var(--acc)]" />
                  <span><span className="font-display font-semibold block">Browse the 16 template designs</span>
                    <span className="text-xs text-[var(--mut)]">The recommended way to start a tenant</span></span>
                </button>
                <div className="grid grid-cols-2 gap-2">
                  {[["website", "Website"], ["app", "App"]].map(([k, l]) => (
                    <button key={k} data-testid={`new-project-kind-${k}`} onClick={() => setNewApp({ ...newApp, kind: k })} className={`text-left p-3 rounded-xl border ${newApp.kind === k ? "border-[var(--acc)] bg-[var(--acc)]/10" : "border-[var(--line)] hover:bg-white/5"}`}>
                      <div className="font-display font-semibold">{l}</div></button>
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
                <label className="block"><span className="overline block mb-1">Import from a website (optional)</span>
                  <input data-testid="new-app-url-input" value={newApp.url} onChange={(e) => setNewApp({ ...newApp, url: e.target.value })} placeholder="acmeplumbing.com"
                    className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm font-mono outline-none focus:border-[var(--acc)]" />
                  <span className="text-[11px] text-[var(--mut)] mt-1 block">We crawl every page, save all images to the media library, rebuild the forms and nav, and copy the colour scheme.</span></label>
                <label className="block"><span className="overline block mb-1">…or import a ZIP package</span>
                  <input data-testid="new-app-zip-input" type="file" accept=".zip" onChange={(e) => setZipFile(e.target.files?.[0] || null)}
                    className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-xs outline-none file:mr-3 file:rounded-md file:border-0 file:bg-[var(--acc)]/15 file:text-[var(--acc)] file:px-2 file:py-1" />
                  <span className="text-[11px] text-[var(--mut)] mt-1 block">HTML, CSS, images and assets — each page becomes its own tenant page.</span></label>
                {importing && impStage && <ImportProgress stage={impStage} started={impStarted} testid="new-app-import-progress" />}
                {impReport && <div className="space-y-3">
                  <ImportReport report={impReport} testid="new-app-import-report" />
                  <button data-testid="new-app-open-project-btn" onClick={() => { const id = impReport.app_id; setImpReport(null); setNewOpen(false); nav(`/apps/${id}`); }} className="btn-primary w-full">Open the imported project</button>
                </div>}
                {!impReport && <button data-testid="new-app-create-btn" onClick={createApp} disabled={importing} className="btn-primary w-full disabled:opacity-60">{importing ? "Importing website…" : `Create ${newApp.kind === "app" ? "app" : "website"}`}</button>}
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Grid or list */}
        {loading ? (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[...Array(6)].map((_, i) => (
              <div key={i} data-testid="dashboard-skeleton-card" className="card-surface aspect-[4/3.4] overflow-hidden"><div className="skeleton h-1/2 w-full rounded-none" /><div className="p-4 space-y-3"><div className="skeleton h-4 w-2/3" /><div className="skeleton h-3 w-full" /><div className="skeleton h-3 w-1/2" /></div></div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="card-surface p-12 text-center">
            <div className="overline mb-2">{showArchived ? "Nothing archived" : "No tenants yet"}</div>
            <div className="font-display text-xl">{showArchived ? "Archived tenants will appear here and can be restored any time." : "Click New project to create your first tenant — nothing is ever created automatically."}</div>
          </div>
        ) : view === "grid" ? (
          <motion.div variants={stagger} initial="hidden" animate="show" className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtered.map((a) => {
              const meta = STATUS_META[a.status] || STATUS_META.active;
              return (
                <motion.div variants={fadeUp} key={a.app_id} data-testid={`app-card-${a.name.toLowerCase().replace(/\s+/g,'-')}`}
                  onClick={() => nav(`/apps/${a.app_id}`)}
                  className="card-surface card-lift overflow-hidden cursor-pointer group">
                  <div className="relative aspect-video overflow-hidden">
                    {a.video_url ? (
                      <video src={a.video_url} poster={a.thumbnail || undefined} autoPlay muted loop playsInline preload="metadata"
                        className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
                    ) : (
                      <div className="w-full h-full bg-gradient-to-br from-[var(--card-hov)] to-[var(--bg-2)]" />
                    )}
                    <div className="absolute inset-0 bg-gradient-to-t from-[var(--card)] via-[var(--card)]/20 to-transparent" />
                    <div className="absolute top-3 left-3 flex gap-1.5">
                      {a.is_staging && <span data-testid={`tenant-staging-badge-${a.app_id}`} className="chip inline-flex items-center gap-1" style={{ background: "rgba(249,115,22,0.18)", color: "#FB923C", borderColor: "rgba(249,115,22,0.45)" }}><Rocket size={10} /> STAGING</span>}
                      <span className="chip" data-testid={`tenant-industry-badge-${a.app_id}`}>{a.is_test_lab ? "INTERNAL TOOLS" : a.industry}</span>
                      {a.theme?.site_skin === "studio" && <span data-testid={`tenant-studio-badge-${a.app_id}`} className="chip chip-active inline-flex items-center gap-1"><Sparkles size={10} /> New design</span>}
                      <span className={`chip ${a.kind === "app" ? "chip-handover" : ""}`}>{a.kind === "app" ? "App" : "Website"}</span>
                      {a.plan && <span className="chip chip-active">{a.plan}</span>}
                      {a.custom_domain && <span className={`chip ${a.domain_status === "verified" ? "chip-active" : "chip-maint"}`}>{a.custom_domain}</span>}
                      {!a.theme?.design_v2 && <span data-testid={`card-legacy-badge-${a.app_id}`} className="chip chip-maint">Legacy look</span>}
                    </div>
                    <div className="absolute top-3 right-3 flex flex-col items-end gap-1.5">
                      {!a.is_test_lab && !a.is_staging && (
                      <button data-testid={`archive-toggle-${a.app_id}`} title={showArchived ? "Restore this tenant" : "Archive this tenant (leads are kept)"}
                        onClick={(e) => { e.stopPropagation(); toggleArchive(a); }}
                        className="w-8 h-8 rounded-full bg-black/55 backdrop-blur border border-white/10 flex items-center justify-center text-white/50 hover:text-red-300 transition-colors">
                        {showArchived ? <RotateCcw size={13} /> : <Archive size={13} />}
                      </button>
                      )}
                      {a.is_test_lab || a.protected ? (
                      <button data-testid={`delete-tenant-${a.app_id}`} disabled
                        onClick={(e) => e.stopPropagation()}
                        className="w-8 h-8 rounded-full bg-black/55 backdrop-blur border border-white/10 flex items-center justify-center text-white/25 cursor-not-allowed"
                        title="The master workspace is permanent and cannot be deleted">
                        <Trash2 size={13} />
                      </button>
                      ) : (
                      <button data-testid={`delete-tenant-${a.app_id}`}
                        disabled={deleting === a.app_id}
                        onClick={(e) => { e.stopPropagation(); deleteTenant(a); }}
                        className="w-8 h-8 rounded-full bg-black/55 backdrop-blur border border-red-400/25 flex items-center justify-center text-red-300/80 hover:text-red-300 hover:border-red-400/60 hover:bg-red-500/10 transition-all disabled:opacity-60"
                        title="Delete this tenant — restorable for 30 days">
                        {deleting === a.app_id ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                      </button>
                      )}
                      <button data-testid={`feature-toggle-${a.app_id}`} title={a.featured ? "Remove from the landing showcase" : "Feature on the landing page"}
                        onClick={(e) => { e.stopPropagation(); toggleFeatured(a); }}
                        className={`w-8 h-8 rounded-full bg-black/55 backdrop-blur border border-white/10 flex items-center justify-center transition-colors ${a.featured ? "text-amber-400" : "text-white/50 hover:text-amber-300"}`}>
                        <Star size={13} fill={a.featured ? "currentColor" : "none"} />
                      </button>
                      <button data-testid={`case-study-edit-${a.app_id}`} title="Edit this tenant's case study page"
                        onClick={(e) => { e.stopPropagation(); setCaseStudyApp(a); }}
                        className="chip cursor-pointer hover:!text-white transition-colors">Edit Case Study</button>
                      <span className={`chip badge-glow ${meta.cls}`}><span className={`pulse-dot ${meta.dot}`} />{meta.label}</span>
                      <LockStateBadge state={lockStates[a.app_id]?.state} testid={`card-lock-badge-${a.app_id}`} />
                    </div>
                    <div className="absolute bottom-3 right-3 w-10 h-10 rounded-full bg-black/50 backdrop-blur flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                      <Play size={16} className="text-white ml-0.5" />
                    </div>
                  </div>
                  <div className="p-5">
                    <div className="font-display text-xl font-semibold">{a.name}</div>
                    <p className="text-sm text-[var(--mut)] mt-1 line-clamp-2">{a.description}</p>
                    {/* Test Lab action panel removed permanently — no action buttons in Test Lab UI. */}
                    <div className="mt-4 grid grid-cols-4 gap-2 font-mono text-[11px]">
                      <div><div className="text-[var(--dim)] uppercase">Uptime</div><div className="text-[var(--fg)]">{a.metrics?.uptime}%</div></div>
                      <div><div className="text-[var(--dim)] uppercase">CPU</div><div className="text-[var(--fg)]">{a.metrics?.cpu}%</div></div>
                      <div><div className="text-[var(--dim)] uppercase">Resp</div><div className="text-[var(--fg)]">{a.metrics?.response_ms}ms</div></div>
                      <div><div className="text-[var(--dim)] uppercase">24h</div><div className="text-[var(--fg)]">{a.metrics?.visitors_24h?.toLocaleString()}</div></div>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </motion.div>
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
                  <span className={`chip badge-glow ${meta.cls}`}><span className={`pulse-dot ${meta.dot}`} />{meta.label}</span>
                  <button data-testid={`archive-row-${a.app_id}`} title={showArchived ? "Restore this tenant" : "Archive this tenant (leads are kept)"}
                    onClick={(e) => { e.stopPropagation(); toggleArchive(a); }}
                    className="p-1.5 rounded-md text-[var(--dim)] hover:text-red-300 hover:bg-white/10">
                    {showArchived ? <RotateCcw size={13} /> : <Archive size={13} />}
                  </button>
                  {!a.is_test_lab && !a.protected && (
                    <button data-testid={`delete-row-${a.app_id}`} title="Delete this tenant — restorable for 30 days"
                      disabled={deleting === a.app_id}
                      onClick={(e) => { e.stopPropagation(); deleteTenant(a); }}
                      className="p-1.5 rounded-md text-[var(--dim)] hover:text-red-400 hover:bg-white/10 disabled:opacity-60">
                      {deleting === a.app_id ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                    </button>
                  )}
                  <LockStateBadge state={lockStates[a.app_id]?.state} testid={`row-lock-badge-${a.app_id}`} />
                  <div className="font-mono text-xs text-[var(--mut)] w-24 text-right">{a.metrics?.uptime}%</div>
                </div>
              );
            })}
          </div>
        )}

        {/* Recently deleted — 30-day restore window before anything is erased */}
        {trash.length > 0 && (
          <section className="mt-12" data-testid="trash-section">
            <div className="flex flex-wrap items-end justify-between gap-3 mb-4 border-b border-[var(--line)] pb-3">
              <div>
                <div className="overline mb-1 flex items-center gap-2"><Trash2 size={12} className="text-red-400/80" /> Recently deleted</div>
                <h2 className="font-display text-2xl font-semibold tracking-tight">{trash.length} tenant{trash.length === 1 ? "" : "s"} restorable</h2>
              </div>
              <p className="text-xs text-[var(--mut)] max-w-sm">Deleted tenants stay here for 30 days with every page, lead, booking and file intact. Restore any time inside the window — after that they are erased automatically.</p>
            </div>
            <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
              {trash.map(t => (
                <div key={t.app_id} data-testid={`trash-card-${t.app_id}`} className="card-surface p-5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ background: t.color }} />
                    <div className="font-display text-lg font-semibold truncate">{t.name}</div>
                    <span data-testid={`trash-days-${t.app_id}`}
                      className={`chip ml-auto ${t.days_left <= 5 ? "chip-maint" : ""}`}>{t.days_left} day{t.days_left === 1 ? "" : "s"} left</span>
                  </div>
                  <div className="text-xs text-[var(--mut)] mt-2 line-clamp-2">{t.description}</div>
                  <div className="mt-3 font-mono text-[11px] text-[var(--dim)]">{t.pages || 0} page(s) · {t.leads || 0} lead(s) kept</div>
                  <div className="mt-4 flex items-center gap-2">
                    <button data-testid={`trash-restore-${t.app_id}`} onClick={() => untrash(t)}
                      className="btn-primary text-xs !py-2 !px-3 inline-flex items-center gap-1.5"><RotateCcw size={12} /> Restore</button>
                    <button data-testid={`trash-erase-${t.app_id}`} onClick={() => eraseNow(t)}
                      className="chip cursor-pointer hover:!text-red-300">Erase now</button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Archived tenants — recoverable, and not counted as active */}
        {archived.length > 0 && (
          <section className="mt-12" data-testid="archived-tenants-section">
            <div className="flex flex-wrap items-end justify-between gap-3 mb-4 border-b border-[var(--line)] pb-3">
              <div>
                <div className="overline mb-1 flex items-center gap-2"><Archive size={12} className="text-[var(--mut)]" /> Archived tenants</div>
                <h2 className="font-display text-2xl font-semibold tracking-tight">{archived.length} tenant{archived.length === 1 ? "" : "s"} kept safe</h2>
              </div>
              <p className="text-xs text-[var(--mut)] max-w-sm">Restore brings a tenant back exactly as it was — pages, content, design, forms, leads, bookings and settings. Archived tenants never count toward your active total.</p>
            </div>
            <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
              {archived.map(a => {
                const s = a.snapshot || {};
                return (
                  <div key={a.app_id} data-testid={`archived-card-${a.app_id}`} className="card-surface p-4 opacity-90 hover:opacity-100 transition-opacity">
                    <div className="flex items-start gap-3">
                      <div className="w-2.5 h-2.5 rounded-full mt-2 shrink-0" style={{ background: a.color || "var(--dim)" }} />
                      <div className="min-w-0 flex-1">
                        <div className="font-display text-lg font-semibold truncate">{a.name}</div>
                        <div className="text-xs text-[var(--mut)] mt-0.5">{a.industry} · last active {s.last_active ? new Date(s.last_active).toLocaleDateString(undefined, { dateStyle: "medium" }) : "unknown"}</div>
                      </div>
                      <span className="chip shrink-0">Archived</span>
                    </div>
                    <div className="mt-3 grid grid-cols-5 gap-2 font-mono text-[11px]" data-testid={`archived-snapshot-${a.app_id}`}>
                      {[["Pages", s.pages], ["Leads", s.leads], ["Books", s.bookings], ["Members", s.members], ["Files", s.files]].map(([k, v]) => (
                        <div key={k}><div className="text-[var(--dim)] uppercase">{k}</div><div className="text-[var(--fg)]">{v ?? 0}</div></div>
                      ))}
                    </div>
                    <div className="mt-4 flex items-center gap-2">
                      <button data-testid={`restore-tenant-${a.app_id}`} onClick={() => restoreTenant(a)} className="btn-primary text-xs !py-1.5 !px-3 flex items-center gap-1.5"><RotateCcw size={12} /> Restore</button>
                      <button data-testid={`purge-tenant-${a.app_id}`} onClick={() => purgeTenant(a)} className="btn-ghost text-xs !py-1.5 !px-3 flex items-center gap-1.5 hover:!text-red-300 hover:!border-red-400/40"><Trash2 size={12} /> Permanently delete</button>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}
      </main>
      <LandingTextEditor open={landingEditor} onClose={() => setLandingEditor(false)} />
      <RolloutModal open={rolloutOpen} onClose={() => { setRolloutOpen(false); setRolloutTarget(null); }}
        targetAppId={rolloutTarget?.app_id || null} targetName={rolloutTarget?.name || ""} />
      <CaseStudyEditor open={!!caseStudyApp} appId={caseStudyApp?.app_id} appName={caseStudyApp?.name}
        onClose={() => setCaseStudyApp(null)} />
    </div>
  );
}
