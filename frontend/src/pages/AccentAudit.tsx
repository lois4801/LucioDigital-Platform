import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import api from "@/lib/api";
import { ArrowLeft, Wand2, Loader2 } from "lucide-react";

const TONE = { dull: "#F87171", ok: "#FBBF24", vivid: "#34D399" };

// Every client's accent shown on the real #080808 base with its contrast ratio.
export default function AccentAudit() {
  const nav = useNavigate();
  const [rows, setRows] = useState([]);
  const [base, setBase] = useState("#080808");
  const [busy, setBusy] = useState("");
  const [loading, setLoading] = useState(true);

  const load = () => api.get("/editorial/accent-audit").then(({ data }) => {
    setRows(data.tenants || []); setBase(data.base || "#080808");
  }).catch(() => {}).finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  async function brighten(r) {
    setBusy(r.app_id);
    try {
      await api.put(`/apps/${r.app_id}/site-mode`, { accent: r.suggested });
      toast.success(`${r.name} accent brightened to ${r.suggested}`);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not update the accent");
    } finally { setBusy(""); }
  }

  async function autotune() {
    setBusy("all");
    try {
      const { data } = await api.post("/editorial/accent-autotune");
      toast.success(data.count ? `Brightened ${data.count} accent(s)` : "Nothing to brighten — all accents read well");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Auto-tune failed");
    } finally { setBusy(""); }
  }

  async function setAccent(r, hex) {    try {
      await api.put(`/apps/${r.app_id}/site-mode`, { accent: hex });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not update the accent"); }
  }

  const dull = rows.filter(r => r.verdict === "dull").length;

  return (
    <div className="min-h-screen" data-testid="accent-audit-page">
      <header className="sticky top-0 z-30 backdrop-blur-xl bg-[var(--bg)]/90 border-b border-[var(--line)] px-6 lg:px-10 py-4 flex flex-wrap items-center gap-3">
        <button data-testid="accent-audit-back" onClick={() => nav("/dashboard")} className="btn-ghost text-sm !py-2 !px-4 inline-flex items-center gap-2"><ArrowLeft size={14} /> Dashboard</button>
        <div>
          <div className="overline">Client accent audit</div>
          <div className="font-display text-lg font-semibold">{rows.length} clients · {dull} reading dull on {base}</div>
        </div>
        <button data-testid="accent-autotune-btn" disabled={!dull || busy === "all"} onClick={autotune}
          className="ml-auto btn-primary text-xs !py-2 !px-4 inline-flex items-center gap-2 disabled:opacity-50">
          {busy === "all" ? <Loader2 size={12} className="animate-spin" /> : <Wand2 size={12} />} Brighten all dull ({dull})
        </button>
      </header>

      <main className="px-6 lg:px-10 py-8">
        {loading && <div className="text-sm text-[var(--mut)] flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Measuring contrast…</div>}
        <div className="space-y-3" data-testid="accent-audit-rows">
          {rows.map(r => (
            <div key={r.app_id} data-testid={`accent-row-${r.app_id}`}
              className="rounded-2xl border border-[var(--line)] overflow-hidden">
              <div className="flex flex-col lg:flex-row">
                {/* the accent shown exactly as it renders on the dark base */}
                <div className="lg:w-[38%] p-6 flex items-center gap-4" style={{ background: base }}>
                  <span className="w-12 h-12 rounded-xl shrink-0" style={{ background: r.accent, boxShadow: `0 0 32px -6px ${r.accent}` }} />
                  <div className="min-w-0">
                    <div className="font-display text-lg font-semibold text-white truncate">{r.name}</div>
                    <div className="font-mono text-xs" style={{ color: r.accent }}>{r.accent} · {r.hero || "no hero"}</div>
                  </div>
                </div>
                <div className="flex-1 p-6 flex flex-wrap items-center gap-4">
                  <div>
                    <div className="overline">Contrast on {base}</div>
                    <div className="font-mono text-2xl" style={{ color: TONE[r.verdict] }} data-testid={`accent-contrast-${r.app_id}`}>
                      {r.contrast_on_080808}:1
                    </div>
                  </div>
                  <span className="chip" style={{ color: TONE[r.verdict], borderColor: TONE[r.verdict] }}>{r.verdict}</span>
                  <div className="ml-auto flex items-center gap-2">
                    <input type="color" data-testid={`accent-picker-${r.app_id}`} value={r.accent}
                      onChange={e => setAccent(r, e.target.value.toUpperCase())}
                      className="w-10 h-10 rounded-xl bg-transparent border border-[var(--line)] p-0 cursor-pointer" />
                    {r.verdict === "dull" && (
                      <button data-testid={`accent-brighten-${r.app_id}`} disabled={busy === r.app_id} onClick={() => brighten(r)}
                        className="btn-primary text-xs !py-2 !px-3 inline-flex items-center gap-1.5 disabled:opacity-60">
                        {busy === r.app_id ? <Loader2 size={11} className="animate-spin" /> : <Wand2 size={11} />} Brighten to {r.suggested}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
        <p className="mt-6 text-xs text-[var(--dim)]">
          Under 3:1 reads dull on the near-black base, 3–4.5:1 is comfortable, above 4.5:1 is vivid. Lime is reserved for lois-tech.ca and is rejected here.
        </p>
      </main>
    </div>
  );
}
