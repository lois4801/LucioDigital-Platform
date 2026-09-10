import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { CheckCircle2, Loader2, Rocket } from "lucide-react";

// Runs the platform-wide editorial rollout with a live progress indicator.
export default function EditorialRolloutCard() {
  const nav = useNavigate();
  const [job, setJob] = useState(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef(0);

  useEffect(() => () => clearTimeout(timer.current), []);

  function poll(jobId) {
    api.get(`/editorial/rollout/${jobId}`).then(({ data }) => {
      setJob(data);
      if (data.status === "running") timer.current = window.setTimeout(() => poll(jobId), 900);
      else {
        setBusy(false);
        if (data.status === "done") toast.success(`Rollout complete — ${data.tenants} tenants, ${data.templates} templates`);
        else toast.error(data.error || "Rollout failed");
      }
    }).catch(() => setBusy(false));
  }

  async function start() {
    setBusy(true);
    try {
      const { data } = await api.post("/editorial/rollout");
      poll(data.job_id);
    } catch (e) {
      setBusy(false);
      toast.error(e.response?.data?.detail || "Could not start the rollout");
    }
  }

  const pct = job?.progress || 0;
  const done = job?.status === "done";

  return (
    <div className="card-surface p-5 mb-6" data-testid="editorial-rollout-card">
      <div className="flex flex-wrap items-center gap-3">
        <Rocket size={16} className="text-[var(--acc)] shrink-0" />
        <div className="min-w-0">
          <div className="font-display text-base">Editorial motion rollout</div>
          <div className="text-xs text-[var(--mut)] mt-0.5">
            Snapshots everything, then pushes the editorial system to all active tenants and every industry template. Undoable.
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button data-testid="dash-hero-gallery-btn" onClick={() => nav("/hero-gallery")} className="btn-ghost text-xs !py-1.5 !px-3">Hero gallery</button>
          <button data-testid="dash-accent-audit-btn" onClick={() => nav("/accent-audit")} className="btn-ghost text-xs !py-1.5 !px-3">Accent audit</button>
          <button data-testid="editorial-rollout-start" disabled={busy} onClick={start}
            className="btn-primary text-xs !py-2 !px-4 inline-flex items-center gap-2 disabled:opacity-60">
            {busy ? <Loader2 size={12} className="animate-spin" /> : <Rocket size={12} />} {busy ? "Rolling out…" : "Run rollout"}
          </button>
        </div>
      </div>
      {job && (
        <div className="mt-4" data-testid="editorial-rollout-progress">
          <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
            <div className="h-full bg-[var(--acc)] transition-[width] duration-500" style={{ width: `${pct}%` }} />
          </div>
          <div className="mt-2 text-xs text-[var(--mut)] flex items-center gap-2">
            {done ? <CheckCircle2 size={12} className="text-[var(--acc)]" /> : <Loader2 size={12} className="animate-spin" />}
            <span data-testid="editorial-rollout-step">{job.step}</span>
            <span className="font-mono ml-auto">{pct}%</span>
          </div>
          {done && (
            <div className="mt-2 text-xs text-[var(--acc)]" data-testid="editorial-rollout-done">
              {job.tenants} tenants · {job.templates} templates · {job.snapshots} snapshots saved for Undo Last Rollout
            </div>
          )}
        </div>
      )}
    </div>
  );
}
