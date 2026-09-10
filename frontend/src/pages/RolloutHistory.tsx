import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { toast } from "sonner";
import { AlertTriangle, ArrowLeft, ChevronDown, ChevronRight, Clock, History, Loader2, Rocket, RotateCcw, ShieldCheck, X } from "lucide-react";
import { DiffTable } from "@/components/DiffViewer";

const STATUS = {
  done: { label: "Completed", cls: "chip-active" },
  partial: { label: "Partial", cls: "chip-maint" },
  failed: { label: "Failed", cls: "chip-down" },
  running: { label: "Running", cls: "chip-maint" },
  undone: { label: "Undone", cls: "chip-down" },
};

const when = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  const tz = new Intl.DateTimeFormat(undefined, { timeZoneName: "short" }).formatToParts(d)
    .find((p) => p.type === "timeZoneName")?.value || "";
  return `${d.toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" })}, ${d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })} ${tz}`;
};

function UndoModal({ entry, onClose, onDone }) {
  const [busy, setBusy] = useState(false);
  const [pct, setPct] = useState(null);

  async function confirm() {
    setBusy(true);
    try {
      await api.post(`/test-lab/rollout/jobs/${entry.job_id}/undo`, { confirm: "CONFIRM" });
      setPct(0);
      const timer = setInterval(async () => {
        const { data } = await api.get("/test-lab/rollout/history");
        const j = data.entries.find((e) => e.job_id === entry.job_id);
        setPct(j?.undo_pct ?? 0);
        if (j?.undone_at) {
          clearInterval(timer);
          toast.success("Rollout undone. All clients restored to their previous state.");
          onDone?.();
          onClose();
        }
      }, 1000);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Undo failed");
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[80] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
      data-testid="undo-modal" onClick={onClose}>
      <div className="card-surface w-full max-w-lg p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="overline">Undo rollout</div>
            <h3 className="font-display text-xl font-semibold tracking-tight mt-1">Restore the previous state</h3>
          </div>
          <button data-testid="undo-close-btn" onClick={onClose} className="btn-ghost !p-2"><X size={15} /></button>
        </div>

        <div className="mt-4 p-3 rounded-xl bg-amber-500/8 border border-amber-500/30 text-sm text-amber-200 flex items-start gap-2">
          <AlertTriangle size={15} className="mt-0.5 shrink-0" />
          This will restore all {entry.total || 0} clients to their state before this rollout. This cannot be undone. Are you sure?
        </div>

        {pct !== null ? (
          <div className="mt-5" data-testid="undo-progress">
            <div className="h-2 rounded-full bg-[var(--line)] overflow-hidden">
              <div style={{ width: `${pct}%` }} className="h-full bg-[var(--acc)] transition-all duration-500" />
            </div>
            <div className="mt-2 text-xs font-mono text-[var(--mut)]">Restoring… {pct}%</div>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2 mt-5">
            <button data-testid="undo-confirm-btn" onClick={confirm} disabled={busy}
              className="btn-primary text-sm !py-2 !px-4 flex items-center gap-2 disabled:opacity-60">
              {busy ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />} Confirm
            </button>
            <button data-testid="undo-cancel-btn" onClick={onClose} className="btn-ghost text-sm !py-2 !px-4">Cancel</button>
          </div>
        )}
      </div>
    </div>
  );
}

function Entry({ e, onUndo }) {
  const [open, setOpen] = useState(false);
  const st = STATUS[e.status] || STATUS.done;
  return (
    <div className="card-surface overflow-hidden" data-testid={`history-entry-${e.job_id}`}>
      <button onClick={() => setOpen((o) => !o)} data-testid={`history-toggle-${e.job_id}`}
        className="w-full text-left p-5 hover:bg-white/[0.02] transition-colors">
        <div className="flex items-start gap-3 flex-wrap">
          {open ? <ChevronDown size={16} className="mt-1 text-[var(--mut)]" /> : <ChevronRight size={16} className="mt-1 text-[var(--mut)]" />}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-display text-base font-semibold">{when(e.created_at)}</span>
              <span className={`chip ${st.cls}`} data-testid={`history-status-${e.job_id}`}>{st.label}</span>
              {e.kind === "template" && <span className="chip">template · {e.template_key}</span>}
              {e.undone_at && <span className="chip chip-down" data-testid={`history-undone-${e.job_id}`}>Undone {when(e.undone_at)}</span>}
            </div>
            <div className="text-xs text-[var(--mut)] mt-1.5 font-mono">
              {e.by_name ? `${e.by_name} · ` : ""}{e.by_email} · {e.changed ?? 0} of {e.total ?? 0} client(s) affected
            </div>
            <div className="flex gap-1.5 mt-2 flex-wrap">
              {(e.categories || []).map((c) => <span key={c} className="chip">{c}</span>)}
              <span className="chip">{e.diff?.total ?? 0} change(s)</span>
            </div>
          </div>
        </div>
      </button>

      {open && (
        <div className="px-5 pb-5 border-t border-[var(--line)] pt-5">
          {e.can_undo && !e.undone_at && (
            <button data-testid={`history-undo-btn-${e.job_id}`} onClick={() => onUndo(e)}
              className="btn-primary text-sm !py-2 !px-4 flex items-center gap-2 mb-5">
              <RotateCcw size={14} /> Undo This Rollout
            </button>
          )}
          {e.diff ? <DiffTable diff={e.diff} /> : <div className="text-sm text-[var(--mut)]">No diff was recorded for this rollout.</div>}
        </div>
      )}
    </div>
  );
}

export default function RolloutHistory() {
  const [data, setData] = useState(null);
  const [undoing, setUndoing] = useState(null);

  const load = () => api.get("/test-lab/rollout/history").then(({ data }) => setData(data))
    .catch(() => toast.error("Could not load the rollout history"));
  useEffect(() => { load(); }, []);

  return (
    <div className="min-h-screen" data-testid="page-rollout-history">
      <header className="border-b border-[var(--line)] px-5 py-4 flex items-center gap-3">
        <Link to="/dashboard" data-testid="history-back-link" className="btn-ghost !p-2"><ArrowLeft size={15} /></Link>
        <div>
          <div className="overline flex items-center gap-2"><History size={12} className="text-[var(--acc)]" /> Rollout history</div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Every change pushed to live clients</h1>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-5 py-8">
        <p className="text-sm text-[var(--mut)]">
          Permanent, read-only record. Only the most recent completed rollout can be undone.
        </p>
        {!data ? (
          <div className="py-16 flex justify-center"><Loader2 size={18} className="animate-spin text-[var(--mut)]" /></div>
        ) : !data.entries.length ? (
          <div data-testid="history-empty" className="mt-8 p-10 text-center border border-dashed border-[var(--line)] rounded-2xl">
            <Rocket size={22} className="mx-auto text-[var(--mut)]" />
            <div className="font-display text-lg mt-3">No rollouts yet</div>
            <p className="text-sm text-[var(--mut)] mt-1">Push something from the Test Lab and it will appear here.</p>
          </div>
        ) : (
          <div className="mt-6 space-y-3">
            {data.entries.map((e) => <Entry key={e.job_id} e={e} onUndo={setUndoing} />)}
          </div>
        )}
        <div className="mt-8 text-[11px] text-[var(--dim)] flex items-center gap-1.5">
          <Clock size={11} /> Entries cannot be edited or deleted.
        </div>
      </main>

      {undoing && <UndoModal entry={undoing} onClose={() => setUndoing(null)} onDone={load} />}
    </div>
  );
}
