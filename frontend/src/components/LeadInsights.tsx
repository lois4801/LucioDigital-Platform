import { useEffect, useState } from "react";
import api from "@/lib/api";
import { BarChart3, Flame, ChevronDown } from "lucide-react";

const Bar = ({ v, max }) => (
  <div className="h-1 rounded-full bg-[var(--line)] overflow-hidden w-16">
    <div className="h-full bg-[var(--acc)]" style={{ width: `${max ? Math.round((v / max) * 100) : 0}%` }} />
  </div>
);

const Table = ({ title, rows, label, testid }) => {
  const max = Math.max(1, ...rows.map(r => r.avg_score || 0));
  return (
    <div data-testid={testid} className="min-w-[220px] flex-1">
      <div className="overline mb-2">{title}</div>
      {rows.length === 0 && <div className="text-[11px] text-[var(--dim)]">No real leads yet.</div>}
      <div className="space-y-1.5">
        {rows.map(r => (
          <div key={r.key} className="flex items-center gap-2 text-[11px]">
            <span className="flex-1 truncate font-mono text-[var(--mut)]" title={r.key}>{r.key}</span>
            <span className="text-[var(--dim)]">{r.leads} {label}</span>
            {r.hot > 0 && <span className="flex items-center gap-0.5 text-[var(--acc)]"><Flame size={9} />{r.hot}</span>}
            <Bar v={r.avg_score || 0} max={max} />
            <span className="w-8 text-right font-mono">{r.avg_score ?? "—"}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

/** Which pages, forms and channels bring in the highest-scoring real leads. */
export default function LeadInsights({ appId }) {
  const [d, setD] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => { api.get(`/apps/${appId}/inbox/insights`).then(r => setD(r.data)).catch(() => {}); }, [appId]);
  if (!d) return null;

  return (
    <div data-testid="lead-insights-card" className="card-surface p-4">
      <button data-testid="lead-insights-toggle" onClick={() => setOpen(o => !o)} className="w-full flex items-center gap-3 text-left">
        <BarChart3 size={15} className="text-[var(--acc)]" />
        <div className="flex-1">
          <div className="text-sm font-semibold">Where your best leads come from</div>
          <div className="text-[11px] text-[var(--mut)]">
            {d.leads} real lead(s) in {d.days} days · {d.hot} hot · average score {d.avg_score ?? "—"}
          </div>
        </div>
        <ChevronDown size={14} className={`text-[var(--mut)] transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="mt-4 pt-4 border-t border-[var(--line)] flex flex-wrap gap-6">
          <Table title="Top pages" rows={d.pages} label="leads" testid="insights-pages" />
          <Table title="Top forms" rows={d.forms} label="leads" testid="insights-forms" />
          <Table title="Channels" rows={d.sources} label="leads" testid="insights-sources" />
          <div data-testid="insights-best" className="min-w-[220px] flex-1">
            <div className="overline mb-2">Highest scoring leads</div>
            <div className="space-y-1.5">
              {(d.best || []).map(b => (
                <div key={b.message_id} className="flex items-center gap-2 text-[11px]">
                  <span className="flex-1 truncate">{b.name}</span>
                  <span className="font-mono text-[var(--dim)] truncate max-w-[90px]">{b.page}</span>
                  <span className="chip chip-active" style={{ padding: "1px 6px" }}>{b.score}</span>
                </div>
              ))}
              {!d.best?.length && <div className="text-[11px] text-[var(--dim)]">Score your leads to see this.</div>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
