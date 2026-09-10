import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { Radio } from "lucide-react";

/** Always-live status strip. There is no rollout button, queue or pending state —
 *  every change reaches its template, its clients and future clients automatically. */
export default function EditorialRolloutCard() {
  const nav = useNavigate();
  const [status, setStatus] = useState(null);

  useEffect(() => {
    api.get("/auto-propagate/status").then(r => setStatus(r.data)).catch(() => {});
  }, []);

  return (
    <div className="card-surface p-5 mb-6" data-testid="auto-propagate-card">
      <div className="flex flex-wrap items-center gap-3">
        <Radio size={16} className="text-[var(--acc)] shrink-0" />
        <div className="min-w-0">
          <div className="font-display text-base">Always live · auto-propagation on</div>
          <div className="text-xs text-[var(--mut)] mt-0.5">
            Every design, motion and content change applies to its template instantly, pushes to all
            active clients using it, and is inherited by future clients. No pending state, no push step.
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="chip chip-active" data-testid="auto-propagate-pending">{status ? `${status.pending} pending` : "live"}</span>
          <button data-testid="dash-motion-index-btn" onClick={() => nav("/motion")} className="btn-ghost text-xs !py-1.5 !px-3">Motion systems</button>
          <button data-testid="dash-hero-gallery-btn" onClick={() => nav("/hero-gallery")} className="btn-ghost text-xs !py-1.5 !px-3">Hero gallery</button>
          <button data-testid="dash-accent-audit-btn" onClick={() => nav("/accent-audit")} className="btn-ghost text-xs !py-1.5 !px-3">Accent audit</button>
        </div>
      </div>
    </div>
  );
}
