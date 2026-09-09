import { useEffect, useState } from "react";
import api, { API } from "@/lib/api";
import { toast } from "sonner";
import { Database, Download, Loader2, CheckCircle2, UploadCloud } from "lucide-react";

export default function SupabaseExportCard({ appDoc }) {
  const [status, setStatus] = useState(null);
  const [uri, setUri] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get(`/apps/${appDoc.app_id}/supabase/status`).then(({ data }) => setStatus(data)).catch(() => {});
  }, [appDoc.app_id]);

  async function push() {
    setBusy(true);
    try {
      const { data } = await api.post(`/apps/${appDoc.app_id}/supabase/push`, uri.trim() ? { connection_uri: uri.trim() } : {});
      setStatus((s) => ({ ...(s || {}), last_push: data, has_saved_connection: s?.has_saved_connection || !!uri.trim() }));
      toast.success(`Pushed ${data.total_rows} row(s) into Supabase`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Supabase push failed");
    } finally { setBusy(false); }
  }

  async function downloadSql() {
    try {
      const res = await fetch(`${API}/apps/${appDoc.app_id}/supabase/sql`, { credentials: "include" });
      if (!res.ok) throw new Error("failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(appDoc.name || "tenant").toLowerCase().replace(/\s+/g, "-")}-supabase.sql`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast.success("Migration file downloaded");
    } catch { toast.error("Could not generate the .sql file"); }
  }

  const last = status?.last_push;

  return (
    <div className="card-surface p-6 lg:col-span-2" data-testid="supabase-export-card">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-[var(--acc)]/10 border border-[var(--acc)]/30 flex items-center justify-center">
          <Database size={18} className="text-[var(--acc)]" />
        </div>
        <div className="flex-1">
          <div className="overline">Supabase</div>
          <h3 className="font-display text-xl font-semibold tracking-tight mt-1">Push this tenant into their own Supabase</h3>
          <p className="text-sm text-[var(--mut)] mt-2 max-w-2xl">
            Creates the tables, loads every record and turns on Row Level Security in the client's own Postgres.
            Re-run it any time — the migration is idempotent. Prefer to run it yourself? Download the .sql instead.
          </p>

          <label className="block mt-5 max-w-2xl">
            <span className="overline block mb-2">Connection URI {status?.has_saved_connection ? "(saved connection will be used if left blank)" : "(Supabase → Project Settings → Database)"}</span>
            <input data-testid="supabase-uri-input" value={uri} onChange={(e) => setUri(e.target.value)}
              placeholder="postgresql://postgres.xxxx:password@aws-0-region.pooler.supabase.com:6543/postgres"
              className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-xs font-mono focus:border-[var(--acc)] outline-none" />
          </label>

          <div className="flex flex-wrap gap-2 mt-4">
            <button data-testid="supabase-push-btn" onClick={push} disabled={busy}
              className="btn-primary flex items-center gap-2 text-sm !py-2 !px-4 disabled:opacity-60">
              {busy ? <Loader2 size={14} className="animate-spin" /> : <UploadCloud size={14} />}
              {busy ? "Pushing…" : "Push to Supabase"}
            </button>
            <button data-testid="supabase-sql-btn" onClick={downloadSql}
              className="btn-ghost flex items-center gap-2 text-sm !py-2 !px-4">
              <Download size={14} /> Download migration .sql
            </button>
          </div>

          {last && (
            <div data-testid="supabase-last-push" className="mt-4 p-3 rounded-xl bg-[var(--bg-2)] border border-[var(--line)] text-xs font-mono flex items-start gap-2">
              <CheckCircle2 size={13} className="text-[var(--acc)] mt-0.5 shrink-0" />
              <span>
                {last.total_rows} row(s) across {last.tables} table(s) · prefix <b>{last.prefix}</b> · {new Date(last.pushed_at).toLocaleString()}
              </span>
            </div>
          )}
          {!!status?.tables?.length && (
            <div className="mt-3 text-[10px] text-[var(--dim)]">
              Tables: {status.tables.map((t) => `lt_${t}`).join(" · ")}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
