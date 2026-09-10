import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Loader2, AlertTriangle, ShieldCheck, X, Plus, Trash2, History } from "lucide-react";
import { Link } from "react-router-dom";
import DiffViewer from "@/components/DiffViewer";

/** Confirmation + scoped, background rollout of Test Lab settings to every active client. */
export default function RolloutModal({ open, onClose, targetAppId = null, targetName = "" }) {
  const [preview, setPreview] = useState(null);
  const [diff, setDiff] = useState(null);
  const [stage, setStage] = useState("diff"); // diff → confirm
  const [picked, setPicked] = useState(null);
  const [scopes, setScopes] = useState(["theme", "mode", "skin", "motion"]);
  const [word, setWord] = useState("");
  const [job, setJob] = useState(null);
  const [busy, setBusy] = useState(false);
  const [admins, setAdmins] = useState(null);
  const [newAdmin, setNewAdmin] = useState("");

  useEffect(() => {
    if (!open) return;
    setStage("diff"); setJob(null); setWord(""); setPicked(null);
    api.get("/test-lab/rollout/preview").then(({ data }) => setPreview(data)).catch(() => toast.error("Could not load the rollout summary"));
    api.get("/test-lab/diff", { params: targetAppId ? { app_id: targetAppId } : {} })
      .then(({ data }) => setDiff(data)).catch(() => toast.error("Could not build the diff"));
    api.get("/rollout-admins").then(({ data }) => setAdmins(data)).catch(() => {});
  }, [open, targetAppId]);

  useEffect(() => {
    if (!job || job.status !== "running") return;
    const timer = setInterval(async () => {
      try {
        const { data } = await api.get(`/test-lab/rollout/jobs/${job.job_id}`);
        setJob(data);
        if (data.status === "done") {
          clearInterval(timer);
          toast.success("Changes successfully applied to all clients.");
        }
      } catch { clearInterval(timer); }
    }, 1200);
    return () => clearInterval(timer);
  }, [job]);

  function toggle(key) {
    setScopes((s) => (s.includes(key) ? s.filter((k) => k !== key) : [...s, key]));
  }

  async function confirm() {
    setBusy(true);
    try {
      const payload = picked ? { changes: picked, confirm: word } : { scopes, confirm: word };
      if (targetAppId) payload.target_app_ids = [targetAppId];
      const { data } = await api.post("/test-lab/rollout", payload);
      setJob(data);
      toast.info("Rollout started — you can keep working while it runs");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Rollout failed to start");
    } finally { setBusy(false); }
  }

  async function addAdmin() {
    try {
      const { data } = await api.post("/rollout-admins", { email: newAdmin });
      setAdmins(data); setNewAdmin("");
      toast.success("Rollout admin added");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not add that admin"); }
  }

  async function removeAdmin(email) {
    try {
      const { data } = await api.delete(`/rollout-admins/${encodeURIComponent(email)}`);
      setAdmins(data);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not remove that admin"); }
  }

  if (!open) return null;

  if (stage === "diff" && !job) {
    if (!diff) {
      return (
        <div className="fixed inset-0 z-[75] bg-[var(--bg)] flex items-center justify-center" data-testid="diff-loading">
          <Loader2 size={20} className="animate-spin text-[var(--mut)]" />
        </div>
      );
    }
    return (
      <DiffViewer diff={diff} onBack={onClose}
        onPush={(ids) => { setPicked(ids); setStage("confirm"); }} />
    );
  }

  return (
    <div className="fixed inset-0 z-[80] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
      data-testid="rollout-modal" onClick={onClose}>
      <div className="card-surface w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="overline">Global rollout</div>
            <h3 className="font-display text-2xl font-semibold tracking-tight mt-1">
              {targetAppId ? `Push to ${targetName || "one client"}` : "Push to All Clients"}
            </h3>
          </div>
          <button data-testid="rollout-close-btn" onClick={onClose} className="btn-ghost !p-2"><X size={15} /></button>
        </div>

        {!preview ? (
          <div className="py-10 flex justify-center"><Loader2 size={18} className="animate-spin text-[var(--mut)]" /></div>
        ) : job ? (
          <div className="mt-6" data-testid="rollout-progress">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-[var(--mut)]">{job.detail || "Applying settings"}</span>
              <span>{job.pct || 0}%</span>
            </div>
            <div className="h-2 mt-2 rounded-full bg-[var(--line)] overflow-hidden">
              <div style={{ width: `${job.pct || 0}%` }} className="h-full bg-[var(--acc)] transition-all duration-500" />
            </div>
            <div className="mt-3 text-xs text-[var(--mut)]">
              {job.done || 0} of {job.total} client(s) processed · {job.changed || 0} updated
            </div>
            {job.status === "done" && (
              <div data-testid="rollout-done" className="mt-4 p-3 rounded-xl bg-[var(--acc)]/10 border border-[var(--acc)]/30 text-sm text-[var(--acc)] flex items-center gap-2">
                <ShieldCheck size={15} /> Changes successfully applied to all clients.
              </div>
            )}
            <button data-testid="rollout-finish-btn" onClick={onClose} className="mt-5 btn-primary text-sm !py-2 !px-4">Done</button>
          </div>
        ) : (
          <>
            <p className="text-sm text-[var(--mut)] mt-3">
              {picked
                ? `${picked.length} change(s) selected in the diff viewer will be applied to the ${preview.target_count} active client(s).`
                : `Pick what gets copied from the Test Lab onto the ${preview.target_count} active client(s).`}
              {" "}Client content — text, images, pages, leads and CMS records — is never touched.
            </p>

            {!picked && (
            <div className="mt-5 space-y-2">
              {preview.scopes.map((s) => (
                <label key={s.key} data-testid={`rollout-scope-${s.key}`}
                  className="flex items-start gap-3 p-3 rounded-xl border border-[var(--line)] hover:border-[var(--acc)]/40 cursor-pointer transition-colors">
                  <input type="checkbox" data-testid={`rollout-scope-input-${s.key}`} checked={scopes.includes(s.key)}
                    onChange={() => toggle(s.key)} className="mt-0.5 accent-[var(--acc)]" />
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold">{s.label}</span>
                    <span className="block text-xs text-[var(--mut)]">{s.description}</span>
                    <span className="block text-[10px] font-mono text-[var(--dim)] mt-1 truncate">
                      {JSON.stringify(preview.current?.[s.key])}
                    </span>
                  </span>
                </label>
              ))}
            </div>
            )}

            {picked && (
              <div className="mt-5 max-h-52 overflow-y-auto rounded-xl border border-[var(--line)] divide-y divide-[var(--line)]"
                data-testid="rollout-selected-list">
                {(diff?.changes || []).filter((c) => picked.includes(c.id)).map((c) => (
                  <div key={c.id} className="px-3 py-2 text-xs flex items-center justify-between gap-2">
                    <span className="truncate"><b className="text-[var(--dim)] font-mono mr-2">{c.category}</b>{c.label}</span>
                    <span className="font-mono text-[10px] text-emerald-300 truncate max-w-[40%]">{typeof c.new === "object" ? JSON.stringify(c.new) : String(c.new)}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-5 p-3 rounded-xl bg-amber-500/8 border border-amber-500/30 text-sm text-amber-200 flex items-start gap-2">
              <AlertTriangle size={15} className="mt-0.5 shrink-0" />
              {targetAppId
                ? "Are you sure you want to apply these changes? This cannot be undone."
                : "Are you sure you want to apply all current Test Lab settings to all active clients? This cannot be undone."}
            </div>

            <label className="block mt-4">
              <span className="overline block mb-2">Type CONFIRM to continue</span>
              <input data-testid="rollout-confirm-input" value={word} onChange={(e) => setWord(e.target.value)}
                placeholder="CONFIRM"
                className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm font-mono focus:border-[var(--acc)] outline-none" />
            </label>

            <div className="flex flex-wrap gap-2 mt-5">
              <button data-testid="rollout-confirm-btn" onClick={confirm}
                disabled={busy || (!picked && !scopes.length) || word.trim().toUpperCase() !== "CONFIRM"}
                className="btn-primary text-sm !py-2 !px-4 flex items-center gap-2 disabled:opacity-50">
                {busy ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />} Confirm
              </button>
              <button data-testid="rollout-cancel-btn" onClick={onClose} className="btn-ghost text-sm !py-2 !px-4">Cancel</button>
              {picked && (
                <button data-testid="rollout-back-to-diff-btn" onClick={() => { setStage("diff"); setPicked(null); }}
                  className="btn-ghost text-sm !py-2 !px-4">Back to diff</button>
              )}
              <Link to="/rollout-history" data-testid="rollout-history-link"
                className="btn-ghost text-sm !py-2 !px-4 ml-auto flex items-center gap-2"><History size={13} /> History</Link>
            </div>

            {admins && (
              <div className="mt-6 pt-5 border-t border-[var(--line)]" data-testid="rollout-admins">
                <div className="overline">Rollout admins</div>
                <div className="mt-2 flex flex-wrap gap-1.5 items-center">
                  <span className="chip chip-active">{admins.owner} · owner</span>
                  {(admins.extra || []).map((e) => (
                    <span key={e} className="chip inline-flex items-center gap-1.5">
                      {e}
                      <button data-testid={`rollout-admin-remove-${e}`} onClick={() => removeAdmin(e)}
                        className="text-[var(--mut)] hover:text-red-300"><Trash2 size={10} /></button>
                    </span>
                  ))}
                </div>
                <div className="flex gap-2 mt-3">
                  <input data-testid="rollout-admin-input" value={newAdmin} onChange={(e) => setNewAdmin(e.target.value)}
                    placeholder="teammate@yourdomain.com"
                    className="flex-1 bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-xs font-mono focus:border-[var(--acc)] outline-none" />
                  <button data-testid="rollout-admin-add-btn" onClick={addAdmin} disabled={!newAdmin.includes("@")}
                    className="btn-ghost text-xs !py-2 !px-3 flex items-center gap-1.5 disabled:opacity-50"><Plus size={12} /> Add</button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
