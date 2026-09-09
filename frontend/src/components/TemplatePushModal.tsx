import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { AlertTriangle, Loader2, ShieldCheck, X } from "lucide-react";
import DiffViewer from "@/components/DiffViewer";

const SCOPES = [
  { key: "all", label: "All templates" },
  { key: "classic", label: "Classic only" },
  { key: "studio", label: "Studio 2026 only" },
];

/** Test Template → real templates. Diff viewer first, then the confirmation modal. */
export default function TemplatePushModal({ open, initialScope = "all", targetKey = null, staging = false, onClose, onDone }) {
  const [scope, setScope] = useState(targetKey ? "selected" : initialScope);
  const [diff, setDiff] = useState(null);
  const [stage, setStage] = useState("diff");
  const [picked, setPicked] = useState(null);
  const [word, setWord] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setStage("diff"); setPicked(null); setWord(""); setDiff(null);
    const params = scope === "selected" ? { scope: "selected", keys: targetKey } : { scope };
    api.get("/test-template/diff", { params })
      .then(({ data }) => setDiff(data))
      .catch(() => toast.error("Could not build the template diff"));
  }, [open, scope, targetKey]);

  async function confirm() {
    setBusy(true);
    try {
      const { data } = staging
        ? await api.post("/test-template/push-staging", { changes: picked, confirm: word })
        : await api.post("/test-template/rollout", {
            scope, keys: scope === "selected" ? [targetKey] : null, changes: picked, confirm: word,
          });
      toast.success(staging
        ? "Changes successfully applied to the staging tenant."
        : `Changes successfully applied to ${data.templates_updated} template(s).`);
      onDone?.();
      onClose();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Template rollout failed");
    } finally { setBusy(false); }
  }

  if (!open) return null;

  if (stage === "diff") {
    if (!diff) {
      return <div className="fixed inset-0 z-[75] bg-[var(--bg)] flex items-center justify-center" data-testid="template-diff-loading">
        <Loader2 size={20} className="animate-spin text-[var(--mut)]" />
      </div>;
    }
    return (
      <div data-testid="template-diff-wrap">
        {!targetKey && !staging && (
          <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[76] flex gap-1.5 p-1 rounded-full bg-[var(--bg-2)] border border-[var(--line)]">
            {SCOPES.map((s) => (
              <button key={s.key} data-testid={`template-scope-${s.key}`} onClick={() => setScope(s.key)}
                className={`text-xs px-3 py-1.5 rounded-full transition-colors ${scope === s.key ? "bg-[var(--acc)] text-black font-semibold" : "text-[var(--mut)] hover:text-white"}`}>
                {s.label}
              </button>
            ))}
          </div>
        )}
        <DiffViewer diff={diff} onBack={onClose} onPush={(ids) => { setPicked(ids); setStage("confirm"); }} />
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-[80] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
      data-testid="template-push-modal" onClick={onClose}>
      <div className="card-surface w-full max-w-lg p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="overline">Test Template rollout</div>
            <h3 className="font-display text-xl font-semibold tracking-tight mt-1">
              {staging ? "Push to Staging" : targetKey ? `Push to “${targetKey}”` : `Push to ${diff?.target_count ?? 0} template(s)`}
            </h3>
          </div>
          <button data-testid="template-push-close" onClick={onClose} className="btn-ghost !p-2"><X size={15} /></button>
        </div>

        <div className="mt-4 text-sm text-[var(--mut)]">
          {picked?.length ?? 0} change(s) from the Test Template will be applied.
        </div>

        <div className="mt-4 p-3 rounded-xl bg-amber-500/8 border border-amber-500/30 text-sm text-amber-200 flex items-start gap-2">
          <AlertTriangle size={15} className="mt-0.5 shrink-0" />
          Are you sure you want to apply these changes? This cannot be undone.
        </div>

        <label className="block mt-4">
          <span className="overline block mb-2">Type CONFIRM to continue</span>
          <input data-testid="template-push-confirm-input" value={word} onChange={(e) => setWord(e.target.value)}
            placeholder="CONFIRM"
            className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm font-mono focus:border-[var(--acc)] outline-none" />
        </label>

        <div className="flex flex-wrap gap-2 mt-5">
          <button data-testid="template-push-confirm-btn" onClick={confirm}
            disabled={busy || word.trim().toUpperCase() !== "CONFIRM"}
            className="btn-primary text-sm !py-2 !px-4 flex items-center gap-2 disabled:opacity-50">
            {busy ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />} Confirm
          </button>
          <button data-testid="template-push-cancel-btn" onClick={onClose} className="btn-ghost text-sm !py-2 !px-4">Cancel</button>
          <button data-testid="template-push-back-btn" onClick={() => setStage("diff")} className="btn-ghost text-sm !py-2 !px-4">Back to diff</button>
        </div>
      </div>
    </div>
  );
}
