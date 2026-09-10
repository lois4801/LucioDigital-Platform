import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Plus, RefreshCw, Trash2, X, ExternalLink } from "lucide-react";
import api from "@/lib/api";

const field = "w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]";

// Admin editor for a tenant's case study: copy, screenshots, metrics, quote, draft/published.
export default function CaseStudyEditor({ appId, appName, open, onClose, onSaved }) {
  const [cs, setCs] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open || !appId) return;
    setCs(null);
    api.get(`/apps/${appId}/case-study`).then(r => setCs(r.data))
      .catch(() => toast.error("Could not load this case study"));
  }, [open, appId]);

  if (!open) return null;

  const set = (k) => (v) => setCs(c => ({ ...c, [k]: v }));
  const setStat = (i, k, v) => setCs(c => ({ ...c, stats: c.stats.map((s, j) => j === i ? { ...s, [k]: v } : s) }));
  const setShot = (i, k, v) => setCs(c => ({ ...c, shots: c.shots.map((s, j) => j === i ? { ...s, [k]: v } : s) }));

  async function syncMetrics() {
    setBusy(true);
    try {
      const { data } = await api.post(`/apps/${appId}/case-study/sync-metrics`);
      setCs(c => ({ ...c, stats: data.stats }));
      toast.success("Pulled this tenant's real leads, pages and days live");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not sync metrics");
    } finally { setBusy(false); }
  }

  async function save(status) {
    setBusy(true);
    try {
      const body = { ...cs, status: status || cs.status };
      delete body.app_id; delete body.slug; delete body.updated_at; delete body.tenant_name;
      const { data } = await api.put(`/apps/${appId}/case-study`, body);
      setCs(data);
      toast.success(data.status === "published" ? "Case study published" : "Case study saved as draft");
      onSaved?.(data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-[95] bg-black/75 backdrop-blur-md flex items-start sm:items-center justify-center p-4 overflow-y-auto"
      data-testid="case-study-editor" onClick={onClose}>
      <div onClick={e => e.stopPropagation()} className="w-full max-w-3xl my-8 rounded-3xl border border-[var(--line)] bg-[var(--card)] shadow-2xl">
        <div className="px-6 py-4 border-b border-[var(--line)] flex items-center justify-between gap-3">
          <div>
            <div className="overline">Case study</div>
            <div className="font-display text-xl font-semibold">{appName}</div>
          </div>
          <div className="flex items-center gap-2">
            {cs?.status === "published" && (
              <a href={`/work/${cs.slug}`} target="_blank" rel="noreferrer" data-testid="case-study-open-public"
                className="chip chip-active inline-flex items-center gap-1"><ExternalLink size={11} /> View live</a>
            )}
            <span data-testid="case-study-status" className={`chip ${cs?.status === "published" ? "chip-active" : "chip-maint"}`}>{cs?.status || "…"}</span>
            <button data-testid="case-study-close" onClick={onClose} className="w-9 h-9 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-white/5"><X size={14} /></button>
          </div>
        </div>

        {!cs ? (
          <div className="p-10 flex items-center justify-center text-[var(--mut)] text-sm gap-2"><Loader2 size={14} className="animate-spin" /> Loading…</div>
        ) : (
          <div className="p-6 space-y-5 max-h-[70vh] overflow-y-auto">
            <div className="grid sm:grid-cols-2 gap-4">
              <label className="block"><span className="overline block mb-2">Industry tag</span>
                <input data-testid="cs-industry" className={field} value={cs.industry || ""} onChange={e => set("industry")(e.target.value)} /></label>
              <label className="block"><span className="overline block mb-2">Accent colour</span>
                <div className="flex gap-2">
                  <input type="color" data-testid="cs-accent" value={cs.accent || "#10B981"} onChange={e => set("accent")(e.target.value)}
                    className="w-11 h-11 rounded-xl bg-transparent border border-[var(--line)] p-0 cursor-pointer" />
                  <input className={field} value={cs.accent || ""} onChange={e => set("accent")(e.target.value)} />
                </div></label>
            </div>
            <label className="block"><span className="overline block mb-2">Tagline</span>
              <input data-testid="cs-tagline" className={field} value={cs.tagline || ""} onChange={e => set("tagline")(e.target.value)} /></label>
            <label className="block"><span className="overline block mb-2">Hero image URL</span>
              <input data-testid="cs-hero-image" className={field} value={cs.hero_image || ""} onChange={e => set("hero_image")(e.target.value)} /></label>
            <label className="block"><span className="overline block mb-2">The challenge</span>
              <textarea data-testid="cs-challenge" rows={3} className={field} value={cs.challenge || ""} onChange={e => set("challenge")(e.target.value)} /></label>
            <label className="block"><span className="overline block mb-2">The solution — intro line</span>
              <textarea data-testid="cs-solution" rows={2} className={field} value={cs.solution_intro || ""} onChange={e => set("solution_intro")(e.target.value)} /></label>

            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="overline">Screenshots ({(cs.shots || []).length})</span>
                <button data-testid="cs-add-shot" onClick={() => setCs(c => ({ ...c, shots: [...(c.shots || []), { url: "", caption: "" }] }))}
                  className="chip inline-flex items-center gap-1 cursor-pointer"><Plus size={11} /> Add</button>
              </div>
              <div className="space-y-2">
                {(cs.shots || []).map((s, i) => (
                  <div key={i} className="flex gap-2">
                    <input data-testid={`cs-shot-url-${i}`} placeholder="Image URL" className={field} value={s.url} onChange={e => setShot(i, "url", e.target.value)} />
                    <input data-testid={`cs-shot-caption-${i}`} placeholder="Caption" className={`${field} max-w-[38%]`} value={s.caption} onChange={e => setShot(i, "caption", e.target.value)} />
                    <button data-testid={`cs-shot-remove-${i}`} onClick={() => setCs(c => ({ ...c, shots: c.shots.filter((_, j) => j !== i) }))}
                      className="w-11 h-11 shrink-0 rounded-xl border border-[var(--line)] flex items-center justify-center text-white/50 hover:text-red-300"><Trash2 size={13} /></button>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <span className="overline block mb-2">Results — three metrics</span>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-[var(--mut)]">Type them, or pull this tenant's real numbers.</span>
                <button data-testid="cs-sync-metrics" disabled={busy} onClick={syncMetrics}
                  className="chip cursor-pointer hover:!text-white inline-flex items-center gap-1 disabled:opacity-60">
                  <RefreshCw size={11} /> Sync real metrics
                </button>
              </div>
              <div className="space-y-2">
                {(cs.stats || []).map((s, i) => (
                  <div key={i} className="flex gap-2">
                    <input data-testid={`cs-stat-label-${i}`} placeholder="Label" className={field} value={s.label} onChange={e => setStat(i, "label", e.target.value)} />
                    <input data-testid={`cs-stat-value-${i}`} type="number" placeholder="0" className={`${field} max-w-[26%]`} value={s.value} onChange={e => setStat(i, "value", Number(e.target.value))} />
                    <input data-testid={`cs-stat-suffix-${i}`} placeholder="+ / % / d" className={`${field} max-w-[18%]`} value={s.suffix} onChange={e => setStat(i, "suffix", e.target.value)} />
                  </div>
                ))}
              </div>
            </div>

            <label className="block"><span className="overline block mb-2">Testimonial</span>
              <textarea data-testid="cs-quote" rows={3} className={field} value={cs.quote || ""} onChange={e => set("quote")(e.target.value)} /></label>
            <div className="grid sm:grid-cols-2 gap-4">
              <label className="block"><span className="overline block mb-2">Client name</span>
                <input data-testid="cs-quote-name" className={field} value={cs.quote_name || ""} onChange={e => set("quote_name")(e.target.value)} /></label>
              <label className="block"><span className="overline block mb-2">Client role</span>
                <input data-testid="cs-quote-role" className={field} value={cs.quote_role || ""} onChange={e => set("quote_role")(e.target.value)} /></label>
            </div>
          </div>
        )}

        {cs && (
          <div className="px-6 py-4 border-t border-[var(--line)] flex flex-wrap items-center justify-end gap-2">
            <button data-testid="cs-save-draft" disabled={busy} onClick={() => save("draft")} className="btn-ghost text-sm !py-2 !px-4 disabled:opacity-50">Save as draft</button>
            <button data-testid="cs-publish" disabled={busy} onClick={() => save("published")} className="btn-primary text-sm !py-2 !px-5 disabled:opacity-50">
              {busy ? "Saving…" : "Publish to showcase"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
