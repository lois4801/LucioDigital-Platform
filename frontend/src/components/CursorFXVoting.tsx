import { useEffect, useState } from "react";
import { toast } from "sonner";
import { MousePointer2, Check, Loader2, Vote } from "lucide-react";
import api from "@/lib/api";
import { CURSOR_EFFECTS } from "@/lib/cursorEffects";
import { useCursorFX } from "@/components/CursorFX";

// Clients try cursor effects on their own site and vote for a favourite.
export function CursorFXVoting({ appId }) {
  const { setPreview } = useCursorFX();
  const [vote, setVote] = useState(null);
  const [active, setActive] = useState("fairy");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setVote(null);
    api.get(`/apps/${appId}/cursor-vote`).then(r => {
      setVote(r.data.vote || null);
      setActive(r.data.vote?.effect || r.data.current || "fairy");
    }).catch(() => {});
    return () => setPreview(null);
  }, [appId, setPreview]);

  const options = CURSOR_EFFECTS.filter(e => e.id !== "none");
  const opt = options.find(o => o.id === active) || options[0];

  async function send() {
    setBusy(true);
    try {
      const { data } = await api.post(`/apps/${appId}/cursor-vote`, { effect: active });
      setVote(data.vote);
      toast.success(`Voted for ${data.vote.label} — your agency has been notified`);
    } catch (e) { toast.error(e.response?.data?.detail || "Vote failed"); }
    finally { setBusy(false); }
  }

  return (
    <div className="card-surface p-5" data-testid="cursor-fx-voting">
      <div className="flex items-center justify-between mb-1">
        <div className="text-sm font-semibold flex items-center gap-2"><MousePointer2 size={14} className="text-[var(--acc)]" /> Pick your site's cursor effect</div>
        {vote && <span data-testid="cursor-vote-status" className={`chip ${vote.applied ? "chip-active" : ""}`}>{vote.applied ? "Applied" : `You voted: ${vote.label}`}</span>}
      </div>
      <p className="text-[11px] text-[var(--mut)] mb-4">Hover any effect to try it right here, then vote — your agency applies it to your live site.</p>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-4" onMouseLeave={() => setPreview(null)}>
        {options.map(o => (
          <button key={o.id} data-testid={`cursor-vote-option-${o.id}`}
            onMouseEnter={() => setPreview(o.id)}
            onClick={() => { setActive(o.id); setPreview(o.id); }}
            className={`relative rounded-xl border p-3 text-left transition-transform hover:-translate-y-0.5 ${active === o.id ? "border-[var(--acc)] ring-2 ring-[var(--acc)]/40" : "border-[var(--line)]"}`}>
            <span className="block w-8 h-8 rounded-full border border-white/10" style={{ background: `linear-gradient(135deg, ${o.swatch[0]}, ${o.swatch[1]})` }} />
            <span className="block text-[11px] font-semibold mt-2 truncate">{o.name}</span>
            <span className="block text-[10px] text-[var(--mut)] truncate">{o.hint}</span>
            {active === o.id && <span className="absolute top-2 right-2 w-4 h-4 rounded-full bg-[var(--acc)] text-black flex items-center justify-center"><Check size={10} /></span>}
          </button>
        ))}
      </div>
      <button data-testid="cursor-vote-btn" onClick={send} disabled={busy || vote?.effect === active}
        className="btn-primary w-full text-sm flex items-center justify-center gap-2 disabled:opacity-50">
        {busy ? <Loader2 size={14} className="animate-spin" /> : <Vote size={14} />} {vote?.effect === active ? "This is your current vote" : `Vote for ${opt.name}`}
      </button>
    </div>
  );
}
