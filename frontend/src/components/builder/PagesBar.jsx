import { useState } from "react";
import { Plus, Trash2, FileText, Sparkles, Loader2, Lock, Unlock } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import api from "@/lib/api";
import { toast } from "sonner";

/** Relative luminance → decides whether a brand colour needs white or dark text. */
function isLight(hex) {
  const h = (hex || "").replace("#", "");
  if (h.length !== 3 && h.length !== 6) return false;
  const full = h.length === 3 ? h.split("").map(c => c + c).join("") : h;
  const [r, g, b] = [0, 2, 4].map(i => parseInt(full.slice(i, i + 2), 16) / 255);
  const lin = [r, g, b].map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2] > 0.45;
}

const rgba = (hex, a) => {
  const h = (hex || "").replace("#", "");
  const full = h.length === 3 ? h.split("").map(c => c + c).join("") : h;
  if (full.length !== 6) return `rgba(139,92,246,${a})`;
  const [r, g, b] = [0, 2, 4].map(i => parseInt(full.slice(i, i + 2), 16));
  return `rgba(${r},${g},${b},${a})`;
};

/** Brand colour is read live from the page's own template theme, then the tenant theme. */
const brandOf = (page, theme) => page?.theme_preview?.primary || theme?.primary || "#8B5CF6";

export function PagesBar({ pages, current, onSelect, onCreate, onDelete, onToggleLock, canLock, theme }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  return (
    <div className="flex-1 min-w-0" data-testid="pages-bar-wrap">
      <div className="flex items-stretch gap-2 tenant-scroll pb-2.5" data-testid="pages-bar">
        {pages.map(p => {
          const on = current === p.page_id;
          const brand = brandOf(p, theme);
          const light = isLight(brand);
          const fg = on ? (light ? "#222222" : "#FFFFFF") : "var(--mut)";
          const tag = p.template_key || (p.slug === "/" ? "home" : p.slug.replace("/", ""));
          const tid = p.slug.replace("/", "") || "home";
          return (
            <div key={p.page_id} data-testid={`page-tab-${tid}`} onClick={() => onSelect(p.page_id)}
              aria-current={on ? "true" : undefined}
              className="group shrink-0 max-w-[210px] rounded-xl px-3 py-2 cursor-pointer"
              style={{
                background: on ? rgba(brand, 0.85) : "var(--bg-2)",
                border: on ? `2px solid ${brand}` : "1px solid var(--line)",
                boxShadow: on ? `0 8px 26px ${rgba(brand, 0.3)}` : "none",
                color: fg,
                transition: "background-color 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease, color 0.25s ease",
              }}>
              <div className="flex items-center gap-1.5">
                {p.locked ? <Lock size={11} className="shrink-0" style={{ color: on ? fg : "#FBBF24" }} />
                  : <FileText size={11} className="shrink-0 opacity-70" />}
                <span className="text-xs font-mono truncate" style={{ color: fg }}>{p.name}</span>
                {canLock && (
                  <button data-testid={`page-lock-${tid}`} title={p.locked ? "Unlock for clients" : "Lock so clients cannot edit"}
                    onClick={e => { e.stopPropagation(); onToggleLock(p); }}
                    className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0 ${p.locked ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`}
                    style={{ color: on ? fg : "#FBBF24" }}>
                    {p.locked ? <Lock size={9} /> : <Unlock size={9} />}
                  </button>
                )}
                {p.slug !== "/" && (
                  <button data-testid={`page-delete-${tid}`} onClick={e => { e.stopPropagation(); onDelete(p); }}
                    className="w-4 h-4 rounded-full flex items-center justify-center shrink-0 opacity-0 group-hover:opacity-100 hover:text-red-400"
                    style={{ color: on ? fg : "var(--dim)" }}><Trash2 size={9} /></button>
                )}
              </div>
              <span data-testid={`page-tag-${tid}`}
                className="mt-1.5 inline-block text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded truncate max-w-full"
                style={{
                  background: on ? "rgba(0,0,0,0.26)" : "rgba(255,255,255,0.04)",
                  color: on ? rgba(light ? "#000000" : "#FFFFFF", 0.72) : "var(--dim)",
                }}>
                {tag}
              </span>
            </div>
          );
        })}
        <button data-testid="page-add-btn" onClick={() => setOpen(true)}
          className="shrink-0 w-9 self-stretch rounded-xl border border-dashed border-[var(--line)] flex items-center justify-center text-[var(--mut)] hover:text-white hover:border-white/40">
          <Plus size={13} />
        </button>
      </div>
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
