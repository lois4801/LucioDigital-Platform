import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Circle, Loader2, RotateCcw, Rocket } from "lucide-react";
import api from "@/lib/api";

/** Onboarding checklist — ticks itself off from what the client has actually done,
 *  with manual tick or skip for anything we cannot detect. Disappears once complete. */
export default function OnboardingChecklist({ appId, compact = false }) {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    if (!appId) return;
    api.get(`/apps/${appId}/onboarding`).then(r => setData(r.data)).catch(() => {});
  }, [appId]);

  async function mark(id: string, state: string) {
    setBusy(id);
    try {
      const { data: got } = await api.post(`/apps/${appId}/onboarding/${id}`, { state });
      setData(got);
      if (got.complete) toast.success("Everything on the checklist is done — nice work");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not update the checklist");
    } finally { setBusy(""); }
  }

  if (!data) return null;
  if (data.complete) return (
    <div className={`${compact ? "" : "py-4 border-b border-[var(--line)]"} text-xs text-[var(--mut)] flex items-center gap-2`} data-testid="onboarding-complete">
      <Rocket size={13} className="text-[var(--acc)]" /> Setup checklist complete — this site is ready.
    </div>
  );

  const pct = data.total ? Math.round((data.done / data.total) * 100) : 0;

  return (
    <div className={compact ? "" : "py-4 border-b border-[var(--line)]"} data-testid="onboarding-checklist">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-semibold">Get your site ready</div>
          <div className="text-xs text-[var(--mut)] mt-0.5">Work down the list — each one ticks itself off as you go.</div>
        </div>
        <span className="text-xs font-mono text-[var(--acc)]" data-testid="onboarding-progress">{data.done} of {data.total} done</span>
      </div>

      <div className="mt-2.5 h-1.5 rounded-full bg-[var(--bg-2)] overflow-hidden">
        <div className="h-full rounded-full bg-[var(--acc)] transition-[width] duration-500" style={{ width: `${pct}%` }} />
      </div>

      <div className="mt-3 space-y-1.5">
        {data.steps.map((s: any) => (
          <div key={s.id} data-testid={`onboarding-step-${s.id}`} data-done={s.done ? "1" : "0"}
            className={`flex items-start gap-2.5 rounded-xl border px-3 py-2.5 ${s.done ? "border-[var(--acc)]/40 bg-[var(--acc)]/[0.06]" : "border-[var(--line)]"} ${s.skipped ? "opacity-50" : ""}`}>
            <button data-testid={`onboarding-tick-${s.id}`} disabled={!!busy}
              onClick={() => mark(s.id, s.done ? "reset" : "done")}
              title={s.done ? "Mark as not done" : "Mark as done"}
              className="mt-0.5 shrink-0 w-5 h-5 rounded-full grid place-items-center border"
              style={{ borderColor: s.done ? "var(--acc)" : "var(--line)", color: s.done ? "var(--acc)" : "var(--dim)" }}>
              {busy === s.id ? <Loader2 size={10} className="animate-spin" /> : s.done ? <Check size={11} /> : <Circle size={7} />}
            </button>
            <div className="min-w-0 flex-1">
              <div className={`text-xs font-semibold ${s.done ? "line-through opacity-70" : ""}`}>{s.label}</div>
              <div className="text-[11px] text-[var(--mut)] mt-0.5 leading-snug">{s.hint}</div>
            </div>
            {!s.done && !s.skipped && (
              <button data-testid={`onboarding-skip-${s.id}`} disabled={!!busy} onClick={() => mark(s.id, "skipped")}
                className="chip cursor-pointer hover:!text-white shrink-0 !px-2 text-[10px]">Skip</button>
            )}
            {s.skipped && (
              <button data-testid={`onboarding-unskip-${s.id}`} disabled={!!busy} onClick={() => mark(s.id, "reset")}
                className="chip cursor-pointer hover:!text-white shrink-0 !px-2 text-[10px] inline-flex items-center gap-1"><RotateCcw size={9} /> Undo</button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
