import { useEffect, useState } from "react";
import api from "@/lib/api";
import { AlertTriangle, Info, CheckCircle2, Wrench } from "lucide-react";

const ICON = {
  error: { i: AlertTriangle, c: "text-red-400", bg: "bg-red-500/10" },
  warning: { i: Wrench, c: "text-amber-400", bg: "bg-amber-500/10" },
  info: { i: Info, c: "text-cyan-400", bg: "bg-cyan-500/10" },
  success: { i: CheckCircle2, c: "text-emerald-400", bg: "bg-emerald-500/10" },
};

export default function ActivityLog({ appId }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    (async () => {
      try { const { data } = await api.get(`/apps/${appId}/activity`); setLogs(data); }
      finally { setLoading(false); }
    })();
  }, [appId]);

  if (loading) return <div className="overline text-center py-16">Loading activity…</div>;

  return (
    <div className="max-w-3xl">
      <div className="overline mb-4">Activity timeline · last 100 events</div>
      {logs.length === 0 ? (
        <div className="card-surface p-10 text-center text-[var(--mut)]">No activity yet.</div>
      ) : (
        <div className="relative pl-6 border-l border-[var(--line)]">
          {logs.map((l) => {
            const meta = ICON[l.severity] || ICON.info;
            const Icon = meta.i;
            return (
              <div key={l.log_id} data-testid={`log-${l.kind}`} className="relative mb-4 pl-4 fade-in">
                <div className={`absolute -left-[34px] w-7 h-7 rounded-full ${meta.bg} border border-[var(--line)] flex items-center justify-center`}>
                  <Icon size={13} className={meta.c} />
                </div>
                <div className="card-surface p-3">
                  <div className="flex items-center gap-2">
                    <span className="overline">{l.kind}</span>
                    <span className="text-[10px] font-mono text-[var(--dim)] ml-auto">{new Date(l.created_at).toLocaleString()}</span>
                  </div>
                  <div className="text-sm mt-1">{l.message}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
