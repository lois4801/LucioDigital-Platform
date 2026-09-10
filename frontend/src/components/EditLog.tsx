import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Clock, User } from "lucide-react";
import api from "@/lib/api";

/** Edit log: who changed what on the live site, and when. `mine` shows only the viewer's own edits. */
export default function EditLog({ appId, mine = false, compact = false, limit = 60 }) {
  const [rows, setRows] = useState<any[]>([]);
  const [areas, setAreas] = useState<string[]>([]);
  const [area, setArea] = useState("");
  const [who, setWho] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!appId) return;
    setLoading(true);
    api.get(`/apps/${appId}/edit-log`, { params: { mine, limit } })
      .then(r => { setRows(r.data.entries || []); setAreas(r.data.areas || []); })
      .catch(() => toast.error("Could not load the edit log"))
      .finally(() => setLoading(false));
  }, [appId, mine, limit]);

  const shown = rows.filter(r => (!area || r.area === area) && (!who || r.role === who));

  return (
    <div className={compact ? "" : "py-4 border-b border-[var(--line)]"} data-testid="edit-log-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold">{mine ? "Your changes" : "Activity — who changed what"}</div>
          <div className="text-xs text-[var(--mut)] mt-0.5">
            {mine ? "Every edit you have made to your live site." : "Every content edit on this client's live site, newest first."}
          </div>
        </div>
        {!mine && (
          <div className="flex items-center gap-2">
            <select data-testid="edit-log-area" value={area} onChange={e => setArea(e.target.value)}
              className="bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2.5 py-1.5 text-xs outline-none focus:border-[var(--acc)]">
              <option value="">All areas</option>
              {areas.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
            <select data-testid="edit-log-who" value={who} onChange={e => setWho(e.target.value)}
              className="bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2.5 py-1.5 text-xs outline-none focus:border-[var(--acc)]">
              <option value="">Everyone</option>
              <option value="agency">Agency</option>
              <option value="client">Client</option>
            </select>
            {loading && <Loader2 size={13} className="animate-spin text-[var(--mut)]" />}
          </div>
        )}
      </div>

      <div className="mt-3 max-h-[320px] overflow-y-auto tenant-scroll rounded-xl border border-[var(--line)] divide-y divide-[var(--line)]">
        {shown.length === 0 && !loading && (
          <div className="p-4 text-xs text-[var(--mut)]" data-testid="edit-log-empty">No edits recorded yet.</div>
        )}
        {shown.map(r => (
          <div key={r.log_id} data-testid="edit-log-row" className="p-3 flex items-start gap-3">
            <span className={`chip shrink-0 ${r.role === "agency" ? "chip-active" : ""}`}>{r.area}</span>
            <div className="min-w-0 flex-1">
              <div className="text-sm truncate">{r.message}</div>
              <div className="text-[10px] font-mono text-[var(--dim)] mt-0.5 flex items-center gap-2 flex-wrap">
                <span className="flex items-center gap-1"><User size={9} /> {r.is_you ? "You" : r.actor} · {r.role}</span>
                <span className="flex items-center gap-1"><Clock size={9} /> {new Date(r.created_at).toLocaleString()}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
