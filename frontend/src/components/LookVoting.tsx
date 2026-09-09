import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Palette, Check, Loader2, Vote } from "lucide-react";
import api from "@/lib/api";

export function LookVoting({ appId }) {
  const [data, setData] = useState(null);
  const [active, setActive] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { setData(null); api.get(`/apps/${appId}/site/look-options`).then(r => { setData(r.data); setActive(r.data.vote?.niche || r.data.current); }).catch(() => {}); }, [appId]);
  if (!data) return null;
  const opt = data.options.find(o => o.key === active) || data.options[0];

  async function vote() {
    setBusy(true);
    try { const { data: v } = await api.post(`/apps/${appId}/site/look-vote`, { niche: active }); setData(d => ({ ...d, vote: v })); toast.success(`Voted for the ${v.label} look — your agency has been notified`); }
    catch (e) { toast.error(e.response?.data?.detail || "Vote failed"); } finally { setBusy(false); }
  }

  return (
    <div className="card-surface p-5" data-testid="look-voting">
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm font-semibold flex items-center gap-2"><Palette size={14} className="text-[var(--acc)]" /> Choose your site's look</div>
        {data.vote && <span data-testid="look-vote-status" className={`chip ${data.vote.applied ? "chip-active" : ""}`}>{data.vote.applied ? "Applied" : `You voted: ${data.vote.label}`}</span>}
      </div>
      <motion.div key={opt.key} initial={{ opacity: 0.4, scale: 0.985 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.25 }} data-testid="look-preview" className="relative rounded-2xl overflow-hidden border border-[var(--line)] aspect-[21/9] mb-4" style={{ background: opt.bg, fontFamily: `'${opt.font}', sans-serif` }}>
        <img src={opt.hero} alt="" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0" style={{ background: `linear-gradient(105deg, ${opt.bg} 0%, ${opt.bg}cc 45%, ${opt.bg}44 100%)` }} />
        <div className="absolute inset-0 p-6 flex flex-col justify-end text-white">
          <div className="flex items-center gap-2 text-[11px] font-mono opacity-80 mb-2"><span className="w-5 h-5 rounded-md" style={{ background: opt.primary }} /> {opt.brand} · {opt.industry} look · {opt.mood}</div>
          <div className="text-xl lg:text-2xl font-bold leading-tight max-w-md">{opt.title}</div>
          <div className="mt-3 flex gap-2"><span className="px-4 py-1.5 rounded-full text-xs font-semibold text-white" style={{ background: opt.primary }}>Primary action</span><span className="px-4 py-1.5 rounded-full text-xs border border-white/30 bg-white/10 backdrop-blur">Secondary</span></div>
        </div>
      </motion.div>
      <div className="grid grid-cols-5 gap-2 mb-4">
        {data.options.map(o => (
          <motion.button key={o.key} data-testid={`look-option-${o.key}`} onClick={() => setActive(o.key)} whileHover={{ y: -3, scale: 1.02 }} whileTap={{ scale: 0.97 }} className={`relative rounded-xl overflow-hidden border text-left ${active === o.key ? "border-[var(--acc)] ring-2 ring-[var(--acc)]/40" : "border-[var(--line)]"}`} style={{ background: o.bg }}>
            <div className="aspect-[4/3] relative"><img src={o.hero} alt="" className="w-full h-full object-cover opacity-70" /><div className="absolute inset-x-0 bottom-0 h-1.5" style={{ background: o.primary }} />{data.current === o.key && <span className="absolute top-1 left-1 text-[9px] px-1.5 py-0.5 rounded bg-black/60 text-white">current</span>}{active === o.key && <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-[var(--acc)] text-black flex items-center justify-center"><Check size={10} /></span>}</div>
            <div className="px-2 py-1.5 text-[10px] font-semibold text-white truncate">{o.industry}</div>
          </motion.button>
        ))}
      </div>
      <button data-testid="look-vote-btn" onClick={vote} disabled={busy || data.vote?.niche === active} className="btn-primary w-full text-sm flex items-center justify-center gap-2 disabled:opacity-50">{busy ? <Loader2 size={14} className="animate-spin" /> : <Vote size={14} />} {data.vote?.niche === active ? "This is your current vote" : `Vote for the ${opt.industry} look`}</button>
      <p className="text-[11px] text-[var(--mut)] mt-2">Your business name, phone, email and address stay exactly as they are — only the design changes.</p>
    </div>
  );
}
