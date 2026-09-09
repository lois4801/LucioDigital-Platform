import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Inbox, Download, Search } from "lucide-react";

export default function SubmissionsPanel({ appId }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  useEffect(() => {
    api.get(`/apps/${appId}/submissions`, { params: { q } })
      .then(r => { setRows(r.data.submissions); setTotal(r.data.total); })
      .catch(e => toast.error(e.response?.data?.detail || "Could not load submissions"));
  }, [appId, q]);

  async function exportCsv() {
    try {
      const r = await api.get(`/apps/${appId}/submissions`, { params: { export: true }, responseType: "blob" });
      const url = URL.createObjectURL(new Blob([r.data], { type: "text/csv" }));
      const a = document.createElement("a");
      a.href = url; a.download = "submissions.csv"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { toast.error("Export failed"); }
  }

  return (
    <div className="space-y-3" data-testid="submissions-panel">
      <div className="flex flex-wrap items-center gap-3">
        <Inbox size={15} className="text-[var(--acc)]" />
        <div className="text-xs flex-1 min-w-[200px]">
          <div className="font-semibold">Form submissions</div>
          <div className="text-[var(--mut)]">{total} stored submission(s) from every form on this site.</div>
        </div>
        <div className="relative">
          <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--dim)]" />
          <input data-testid="submissions-panel-search" value={q} onChange={e => setQ(e.target.value)} placeholder="Search…"
            className="bg-[var(--bg-2)] border border-[var(--line)] rounded-xl pl-8 pr-3 py-2 text-sm outline-none focus:border-[var(--acc)]" />
        </div>
        <button data-testid="submissions-export-btn" onClick={exportCsv} className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-1.5"><Download size={13} /> CSV</button>
      </div>
      {rows.length === 0 && <div className="text-sm text-[var(--mut)]">No submissions yet. Convert this site to a web app and every form will store its entries here.</div>}
      {rows.map(s => (
        <div key={s.submission_id} data-testid="submission-panel-row" className="rounded-xl border border-[var(--line)] p-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-semibold">{s.name || "Anonymous"}</span>
            <span className="text-xs text-[var(--mut)]">{s.email}</span>
            <span className="chip">{s.form_name}</span>
            {s.page && <span className="font-mono text-[10px] text-[var(--dim)]">{s.page}</span>}
            <span className={`chip ${s.status === "new" ? "chip-active" : ""}`}>{s.status}</span>
            <span className="ml-auto text-[10px] text-[var(--dim)]">{new Date(s.created_at).toLocaleString()}</span>
          </div>
          <div className="mt-1.5 text-xs text-[var(--mut)] space-y-0.5">
            {Object.entries(s.fields || {}).map(([k, v]) => <div key={k}><span className="text-[var(--dim)]">{k}:</span> {v}</div>)}
          </div>
        </div>
      ))}
    </div>
  );
}
