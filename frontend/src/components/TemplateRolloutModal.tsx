import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { AlertTriangle, Loader2, ShieldCheck, X } from "lucide-react";

/** Same confirmation contract as the global rollout, scoped to one template's design. */
export default function TemplateRolloutModal({ template, onClose, onDone }) {
  const [word, setWord] = useState("");
  const [busy, setBusy] = useState(false);

  async function push() {
    setBusy(true);
    try {
      const { data } = await api.post(`/templates/${template.key}/rollout`, { confirm: word });
      toast.success(`Changes successfully applied to all clients. (${data.tenants_updated} using ${template.key})`);
      onDone?.();
      onClose();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Rollout failed");
    } finally { setBusy(false); }
  }

  async function discard() {
    try {
      await api.post(`/templates/${template.key}/discard`);
      toast.info("Pending change discarded — live clients keep their current design");
      onDone?.();
      onClose();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not discard"); }
  }

  return (
    <div className="fixed inset-0 z-[80] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
      data-testid="template-rollout-modal" onClick={onClose}>
      <div className="card-surface w-full max-w-lg p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="overline">Template rollout</div>
            <h3 className="font-display text-xl font-semibold tracking-tight mt-1">
              Push to all clients using “{template.brand || template.key}”
            </h3>
          </div>
          <button data-testid="template-rollout-close" onClick={onClose} className="btn-ghost !p-2"><X size={15} /></button>
        </div>

        <div className="mt-4 text-sm text-[var(--mut)]">
          This applies the current design of the <b>{template.key}</b> template to
          {" "}<b>{template.tenants_using ?? 0}</b> live client(s) using it. Their content is untouched.
        </div>

        <div className="mt-4 p-3 rounded-xl bg-amber-500/8 border border-amber-500/30 text-sm text-amber-200 flex items-start gap-2">
          <AlertTriangle size={15} className="mt-0.5 shrink-0" />
          Are you sure you want to apply all current Test Lab settings to all active clients? This cannot be undone.
        </div>

        <label className="block mt-4">
          <span className="overline block mb-2">Type CONFIRM to continue</span>
          <input data-testid="template-rollout-confirm-input" value={word} onChange={(e) => setWord(e.target.value)}
            placeholder="CONFIRM"
            className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm font-mono focus:border-[var(--acc)] outline-none" />
        </label>

        <div className="flex flex-wrap gap-2 mt-5">
          <button data-testid="template-rollout-confirm-btn" onClick={push}
            disabled={busy || word.trim().toUpperCase() !== "CONFIRM"}
            className="btn-primary text-sm !py-2 !px-4 flex items-center gap-2 disabled:opacity-50">
            {busy ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />} Confirm
          </button>
          <button data-testid="template-rollout-cancel-btn" onClick={onClose} className="btn-ghost text-sm !py-2 !px-4">Cancel</button>
          {template.status === "pending" && (
            <button data-testid="template-rollout-discard-btn" onClick={discard}
              className="btn-ghost text-sm !py-2 !px-4 ml-auto text-amber-300">Discard pending change</button>
          )}
        </div>
      </div>
    </div>
  );
}
