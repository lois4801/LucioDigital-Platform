import AnalyticsCard from "@/components/AnalyticsCard";
import { Activity, Cpu, HardDrive, Timer, Users } from "lucide-react";
import { L, UiLabelsToolbar } from "@/components/UiLabels";

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
            <L k="overview_card_title" d={appDoc.name} as="h2" className="font-display text-2xl font-semibold tracking-tight mt-4 block" testid="label-overview-card-title" />
            <L k="overview_card_description" d={appDoc.description || "—"} as="p" className="text-[var(--mut)] mt-2 block" testid="label-overview-card-desc" />
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
