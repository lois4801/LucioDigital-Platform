import { Activity, Cpu, HardDrive, Timer, Users } from "lucide-react";

const STATUS_OPTIONS = [
  { v: "active", label: "Active", cls: "chip-active" },
  { v: "maintenance", label: "In Maintenance", cls: "chip-maint" },
  { v: "handover", label: "Ready for Handover", cls: "chip-handover" },
];

export default function OverviewPanel({ appDoc, patch }) {
  const m = appDoc.metrics || {};
  return (
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
            <h2 className="font-display text-2xl font-semibold tracking-tight mt-4">{appDoc.name}</h2>
            <p className="text-[var(--mut)] mt-2">{appDoc.description}</p>
          </div>
        </div>

        <div className="card-surface p-6">
          <div className="overline mb-4">Lifecycle status</div>
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
          <div className="overline mb-4">Live hosting metrics</div>
          <div className="grid grid-cols-2 gap-4">
            {[
              { icon: Activity, label: "Uptime", value: `${m.uptime}%` },
              { icon: Cpu, label: "CPU", value: `${m.cpu}%` },
              { icon: HardDrive, label: "RAM", value: `${m.ram}%` },
              { icon: Timer, label: "Response", value: `${m.response_ms}ms` },
            ].map((s) => (
              <div key={s.label} className="p-4 rounded-xl bg-[var(--bg-2)] border border-[var(--line)]">
                <s.icon size={14} className="text-[var(--acc)]" />
                <div className="overline mt-2">{s.label}</div>
                <div className="font-display text-2xl font-semibold mt-1">{s.value}</div>
              </div>
            ))}
          </div>
          <div className="mt-4 p-4 rounded-xl bg-[var(--bg-2)] border border-[var(--line)] flex items-center gap-3">
            <Users size={16} className="text-[var(--acc)]" />
            <div className="flex-1">
              <div className="overline">Visitors · 24h</div>
              <div className="font-display text-xl font-semibold mt-0.5">{m.visitors_24h?.toLocaleString()}</div>
            </div>
          </div>
        </div>

        <div className="card-surface p-6">
          <div className="overline mb-3">Quick links</div>
          <div className="text-sm font-mono space-y-2 text-[var(--mut)]">
            <div><span className="text-[var(--dim)]">app_id</span> · {appDoc.app_id}</div>
            <div><span className="text-[var(--dim)]">owner_id</span> · {appDoc.owner_id}</div>
            {appDoc.live_url && <div><span className="text-[var(--dim)]">live</span> · {appDoc.live_url}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
