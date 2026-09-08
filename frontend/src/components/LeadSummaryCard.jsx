import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Sparkles, Loader2 } from "lucide-react";

/** AI summary of the last 7 days of leads — cached server-side, regenerated on demand. */
export const LeadSummaryCard = ({ appId, compact = false }) => {
  const [sum, setSum] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get(`/apps/${appId}/ai/lead-summary`).then(r => setSum(r.data?.summary ? r.data : null)).catch(() => {}); }, [appId]);

  async function run() {
    setBusy(true);
    try {
      const { data } = await api.post(`/apps/${appId}/ai/lead-summary`, {}, { timeout: 180000 });
      setSum(data);
      toast.success("Lead summary written");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not write the summary"); }
    finally { setBusy(false); }
  }

  return (
    <div data-testid="lead-summary-card" className={`rounded-xl border border-[var(--line)] ${compact ? "p-4" : "p-5"} space-y-3`}>
      <div className="flex flex-wrap items-center gap-3">
        <Sparkles size={15} className="text-[var(--acc)]" />
        <div className="flex-1 min-w-[160px]">
          <div className="text-sm font-semibold">Your week in leads</div>
          <div className="text-[11px] text-[var(--mut)]">
            {sum ? `${sum.counts?.leads ?? 0} lead(s), ${sum.counts?.hot ?? 0} hot · ${sum.model || "AI"}`
              : "AI reads the last 7 days and tells you who to chase"}
          </div>
        </div>
        <button data-testid="lead-summary-btn" onClick={run} disabled={busy}
          className="btn-primary !py-2 !px-4 text-xs flex items-center gap-1.5 disabled:opacity-50">
          {busy ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
          {busy ? "Summarising…" : sum ? "Summarise again" : "Summarise now"}
        </button>
      </div>
      {sum?.summary && (
        <div data-testid="lead-summary-text" className="text-xs leading-relaxed text-[var(--mut)] whitespace-pre-wrap border-t border-[var(--line)] pt-3">
          {sum.summary}
        </div>
      )}
    </div>
  );
};

export default LeadSummaryCard;
