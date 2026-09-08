import AnalyticsCard from "@/components/AnalyticsCard";
import { useState, useEffect } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Activity, Cpu, HardDrive, Timer, Users, Lock, Unlock, Sparkles } from "lucide-react";
import { L, UiLabelsToolbar } from "@/components/UiLabels";
import { LockToggle, MasterLockButton, LockStateBadge, useLocks } from "@/components/locks/LockContext";
import ConvertToWebApp from "@/components/ConvertToWebApp";
import ClientTools from "@/components/ClientTools";
import LeadSummaryCard from "@/components/LeadSummaryCard";

const STATUS_OPTIONS = [
  { v: "active", label: "Active", cls: "chip-active" },
  { v: "maintenance", label: "In Maintenance", cls: "chip-maint" },
  { v: "handover", label: "Ready for Handover", cls: "chip-handover" },
];

const HOST_METRICS = [
  { icon: Activity, k: "metric_uptime", label: "Uptime", fmt: (m) => `${m.uptime}%` },
  { icon: Cpu, k: "metric_cpu", label: "CPU", fmt: (m) => `${m.cpu}%` },
  { icon: HardDrive, k: "metric_ram", label: "RAM", fmt: (m) => `${m.ram}%` },
  { icon: Timer, k: "metric_response", label: "Response", fmt: (m) => `${m.response_ms}ms` },
];

function SiteSnapshot({ appDoc }) {
  const [lock, setLock] = useState({ locked: true, snapshot: null });
  const [busy, setBusy] = useState(false);
  const [design, setDesign] = useState(appDoc.theme?.design_v2);
  const [upBusy, setUpBusy] = useState(false);
  useEffect(() => { setDesign(appDoc.theme?.design_v2); }, [appDoc.theme?.design_v2]);
  async function upgradeDesign() {
    setUpBusy(true);
    try {
      const { data } = await api.post(`/apps/${appDoc.app_id}/site/upgrade-design`);
      setDesign(true);
      toast.success(data.already ? "This site already uses the current design standard" : "Design upgraded — your copy and images are untouched. Undo it any time from History.");
    } catch (e) { toast.error(e.response?.data?.detail || "Upgrade failed"); } finally { setUpBusy(false); }
  }
  useEffect(() => { api.get(`/apps/${appDoc.app_id}/content-lock`).then(r => setLock(r.data)).catch(() => { }); }, [appDoc.app_id, appDoc.updated_at]);
  const snap = lock.snapshot || appDoc.site_snapshot;
  async function toggle() {
    const next = !lock.locked;
    if (next === false && !window.confirm("Unlock this tenant's site content? AI rebuilds and website imports will then be allowed to replace the saved pages.")) return;
    setBusy(true);
    try { await api.post(`/apps/${appDoc.app_id}/content-lock`, { locked: next }); setLock(l => ({ ...l, locked: next })); toast.success(next ? "Site content locked" : "Unlocked — remember to lock it again"); }
    catch { toast.error("Failed"); } finally { setBusy(false); }
  }
  return (
    <div className="mt-5 space-y-3" data-testid="site-snapshot">
      {snap && (
        <div className="rounded-xl border border-[var(--line)] bg-white/[0.03] p-4">
          <div className="overline mb-2">Live site (from Site Mode)</div>
          <div className="text-[10px] text-[var(--dim)] mb-2">Synced from Site Mode — the tenant name follows the Navbar brand, so edit it there.</div>
          <div data-testid="snapshot-headline" className="font-display font-semibold">{snap.headline || "—"}</div>
          {snap.subtitle && <div data-testid="snapshot-subtitle" className="text-sm text-[var(--mut)] mt-1">{snap.subtitle}</div>}
          {snap.description && <div data-testid="snapshot-description" className="text-xs text-[var(--mut)] mt-2 leading-relaxed line-clamp-3">{snap.description}</div>}
          {(snap.thumbnail || appDoc.thumbnail) && (
            <img data-testid="snapshot-thumbnail" src={snap.thumbnail || appDoc.thumbnail} alt=""
              key={snap.thumbnail || appDoc.thumbnail}
              onError={e => { e.currentTarget.style.display = "none"; }}
              className="mt-3 w-full max-h-40 object-cover rounded-lg border border-[var(--line)]" />
          )}
          <div className="font-mono text-[10px] text-[var(--dim)] mt-2" data-testid="snapshot-meta">
            {snap.pages} page(s) · {snap.sections} sections on home{snap.total_sections ? ` · ${snap.total_sections} total` : ""} · updated {new Date(snap.updated_at).toLocaleString()}
          </div>
        </div>
      )}
      <div className="group flex items-center gap-2 rounded-xl border border-[var(--line)] p-3">
        {lock.locked ? <Lock size={14} className="text-[var(--acc)]" /> : <Unlock size={14} className="text-amber-400" />}
        <div className="text-xs">
          <div className="font-semibold">{lock.locked ? "Content locked" : "Content unlocked"}</div>
          <div className="text-[var(--mut)]">{lock.locked ? "AI rebuilds and imports cannot replace this saved site. Manual edits still work." : "AI rebuilds and imports can overwrite this site."}</div>
        </div>
        <LockToggle kind="overview" itemId="default" name="Overview & site snapshot" alwaysVisible />
        <button data-testid="content-lock-toggle" onClick={toggle} disabled={busy} className="btn-ghost !py-1.5 text-[11px] disabled:opacity-50">{lock.locked ? "Unlock" : "Lock"}</button>
      </div>
      <ConvertToWebApp appId={appDoc.app_id} appName={appDoc.name} />
      <ClientTools appId={appDoc.app_id} appName={appDoc.name} converted={!!appDoc.webapp?.converted} />
      {!design && (
        <div data-testid="design-upgrade-card" className="rounded-xl border border-[var(--acc)]/40 bg-[var(--acc)]/5 p-4 flex flex-wrap items-center gap-3">
          <Sparkles size={15} className="text-[var(--acc)]" />
          <div className="flex-1 min-w-[220px] text-xs">
            <div className="font-semibold">This site is still on the legacy look</div>
            <div className="text-[var(--mut)]">Upgrade to the current standard — fluid type, glass depth, scroll reveals and a full-height hero. Every word and image stays exactly as it is, and History can undo it.</div>
          </div>
          <span data-testid="legacy-look-badge" className="chip chip-maint">Legacy look</span>
          <button data-testid="design-upgrade-btn" onClick={upgradeDesign} disabled={upBusy} className="btn-primary text-sm !py-2 !px-4 disabled:opacity-50">{upBusy ? "Upgrading…" : "Upgrade design"}</button>
        </div>
      )}
      <div data-testid="overview-master-lock" className="flex flex-wrap items-center gap-3 rounded-xl border border-[var(--line)] p-3">
        <div className="text-xs flex-1 min-w-[180px]">
          <div className="font-semibold">Master lock</div>
          <div className="text-[var(--mut)]">Lock or unlock every page, section, form, CMS entry and workflow in this tenant at once.</div>
        </div>
        <LockStateBadge testid="overview-lock-state-badge" />
        <MasterLockButton testid="overview-master-lock-btn" />
      </div>
    </div>
  );
}

export default function OverviewPanel({ appDoc, patch }) {
  const m = appDoc.metrics || {};
  return (
    <div className="space-y-6">
    <UiLabelsToolbar />
    <AnalyticsCard appId={appDoc.app_id} />
    <div className="grid lg:grid-cols-[1.4fr_1fr] gap-6">
      <div className="space-y-6">
        <div className="card-surface overflow-hidden">
          {appDoc.video_url && (
            <div className="aspect-video relative">
              <video src={appDoc.video_url} poster={appDoc.thumbnail || undefined} autoPlay muted loop playsInline
                className="w-full h-full object-cover" />
              <div className="absolute inset-0 bg-gradient-to-t from-[var(--card)] via-transparent to-transparent" />
            </div>
          )}
          <div className="p-6">
            <div className="flex items-center gap-2">
              <span className="chip">{appDoc.industry}</span>
              {(appDoc.tags || []).map((t) => <span key={t} className="chip">{t}</span>)}
            </div>
            <h2 data-testid="label-overview-card-title" className="font-display text-2xl font-semibold tracking-tight mt-4 block">{appDoc.name}</h2>
            <p data-testid="label-overview-card-desc" className="text-[var(--mut)] mt-2 block">{appDoc.description || "—"}</p>
            <div className="text-[10px] text-[var(--dim)] mt-1">Name and summary follow Site Mode — edit them in the Navbar brand and hero copy.</div>
            <SiteSnapshot appDoc={appDoc} />
          </div>
        </div>

        <div className="card-surface p-6">
          <L k="section_lifecycle" d="Lifecycle status" as="div" className="overline mb-4" testid="label-lifecycle" />
          <div className="flex flex-wrap gap-2">
            {STATUS_OPTIONS.map((s) => (
              <button key={s.v} data-testid={`status-${s.v}-btn`} onClick={() => patch({ status: s.v })}
                className={`chip cursor-pointer ${appDoc.status === s.v ? s.cls : ""}`}>
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="space-y-6">
        <LeadSummaryCard appId={appDoc.app_id} compact />
        <div className="card-surface p-6">
          <L k="section_hosting_metrics" d="Live hosting metrics" as="div" className="overline mb-4" testid="label-hosting-metrics" />
          <div className="grid grid-cols-2 gap-4">
            {HOST_METRICS.map((s) => (
              <div key={s.k} className="p-4 rounded-xl bg-[var(--bg-2)] border border-[var(--line)]">
                <s.icon size={14} className="text-[var(--acc)]" />
                <L k={s.k} d={s.label} as="div" className="overline mt-2" />
                <div className="font-display text-2xl font-semibold mt-1">{s.fmt(m)}</div>
              </div>
            ))}
          </div>
          <div className="mt-4 p-4 rounded-xl bg-[var(--bg-2)] border border-[var(--line)] flex items-center gap-3">
            <Users size={16} className="text-[var(--acc)]" />
            <div className="flex-1">
              <L k="metric_visitors_24h" d="Visitors · 24h" as="div" className="overline" />
              <div className="font-display text-xl font-semibold mt-0.5">{m.visitors_24h?.toLocaleString()}</div>
            </div>
          </div>
        </div>

        <div className="card-surface p-6">
          <L k="section_quick_links" d="Quick links" as="div" className="overline mb-3" testid="label-quick-links" />
          <div className="text-sm font-mono space-y-2 text-[var(--mut)]">
            <div><span className="text-[var(--dim)]">app_id</span> · {appDoc.app_id}</div>
            <div><span className="text-[var(--dim)]">owner_id</span> · {appDoc.owner_id}</div>
            {appDoc.live_url && <div><span className="text-[var(--dim)]">live</span> · {appDoc.live_url}</div>}
          </div>
        </div>
      </div>
    </div>
    </div>
  );
}
