import { useState } from "react";
import { Plus, Trash2, FileText, Sparkles, Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import api from "@/lib/api";
import { toast } from "sonner";

export function PagesBar({ pages, current, onSelect, onCreate, onDelete }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  return (
    <div className="flex items-center gap-1 overflow-x-auto scrollbar-thin" data-testid="pages-bar">
      {pages.map(p => (
        <div key={p.page_id} className={`group flex items-center gap-1 rounded-full text-xs font-mono pl-3 pr-1 py-1 border cursor-pointer ${current === p.page_id ? "bg-[var(--acc)]/12 border-[var(--acc)]/50 text-[var(--acc)]" : "border-[var(--line)] text-[var(--mut)] hover:text-white"}`}
          data-testid={`page-tab-${p.slug.replace("/", "") || "home"}`} onClick={() => onSelect(p.page_id)}>
          <FileText size={11} /> {p.name}
          {p.slug !== "/" ? <button onClick={e => { e.stopPropagation(); onDelete(p); }} className="w-5 h-5 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 hover:text-red-400"><Trash2 size={10} /></button> : <span className="w-1" />}
        </div>
      ))}
      <button data-testid="page-add-btn" onClick={() => setOpen(true)} className="w-7 h-7 rounded-full border border-dashed border-[var(--line)] flex items-center justify-center text-[var(--mut)] hover:text-white hover:border-white/40"><Plus size={12} /></button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)]">
          <DialogHeader><DialogTitle className="font-display">New page</DialogTitle></DialogHeader>
          <input data-testid="page-name-input" value={name} onChange={e => setName(e.target.value)} placeholder="About us" className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--acc)]" />
          <div className="text-xs font-mono text-[var(--mut)]">slug: /{name.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "")}</div>
          <button data-testid="page-create-btn" disabled={!name.trim()} onClick={() => { onCreate(name.trim(), name); setName(""); setOpen(false); }} className="btn-primary w-full disabled:opacity-50">Create page</button>
        </DialogContent>
      </Dialog>
    </div>
  );
}

const EXAMPLES = ["Modern dental clinic in Toronto: whitening, implants, family dentistry, online booking", "Boutique fitness studio with HIIT + yoga classes, memberships from $49/mo", "B2B SaaS for restaurant inventory with AI forecasting and Shopify sync"];

export function GenerateSiteDialog({ open, onOpenChange, appId, onDone }) {
  const [brief, setBrief] = useState("");
  const [pages, setPages] = useState("Home, About, Services, Pricing, Contact");
  const [busy, setBusy] = useState(false);
  async function run() {
    setBusy(true);
    try {
      const { data } = await api.post(`/apps/${appId}/ai/generate-site`, { brief, pages: pages.split(",").map(s => s.trim()).filter(Boolean) }, { timeout: 300000 });
      toast.success(`Generated ${data.pages.length} pages`); onDone(data); onOpenChange(false); setBrief("");
    } catch (e) { toast.error(e.response?.data?.detail || "Generation failed"); }
    finally { setBusy(false); }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)] max-w-lg">
        <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><Sparkles size={16} className="text-[var(--acc)]" /> Generate a full website</DialogTitle></DialogHeader>
        <p className="text-sm text-[var(--mut)]">Describe the business. Claude designs every page — copy, layout, theme — in a light, Figma-grade style. <span className="text-amber-300">This replaces the current pages.</span></p>
        <textarea data-testid="site-brief-input" value={brief} onChange={e => setBrief(e.target.value)} rows={4} placeholder="e.g. Modern dental clinic in Toronto…" className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm outline-none focus:border-[var(--acc)] resize-none" />
        <div className="flex flex-wrap gap-2">{EXAMPLES.map((x, i) => <button key={i} data-testid={`site-example-${i}`} onClick={() => setBrief(x)} className="chip normal-case tracking-normal cursor-pointer hover:!text-white">{x.slice(0, 40)}…</button>)}</div>
        <label className="block"><span className="overline block mb-1">Pages</span>
          <input data-testid="site-pages-input" value={pages} onChange={e => setPages(e.target.value)} className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-xs font-mono outline-none" /></label>
        <button data-testid="site-generate-btn" onClick={run} disabled={busy || brief.trim().length < 10} className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50">
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} {busy ? "Designing your site (30–90s)…" : "Generate website"}
        </button>
      </DialogContent>
    </Dialog>
  );
}
