import { useState } from "react";
import { Plus, Trash2, FileText, Lock, Unlock } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

/** What each page is for, plus a short guide shown when it is selected. */
const GUIDES: Record<string, { desc: string; guide: string }> = {
  home: { desc: "Main landing page visitors see first.", guide: "Usually a hero, a few service cards, proof (stats or testimonials) and a closing call to action. Start with the hero headline and the main button." },
  about: { desc: "Your story, team, and mission.", guide: "Usually an intro, your story, the team and a values or timeline section. Start with the opening paragraph, then add real team photos." },
  services: { desc: "What you offer and how to get started.", guide: "Usually a short intro, a grid of services, pricing or packages and a booking call to action. Start by naming each service and its one-line benefit." },
  contact: { desc: "How clients reach you.", guide: "Usually a contact form, your phone, email, address and opening hours. Start with the form fields, then check the address so the map is right." },
  pricing: { desc: "Your plans and what each includes.", guide: "Usually a plan comparison, an FAQ and a call to action. Start with the plan names and prices, then trim each feature list." },
  blog: { desc: "News, guides and updates.", guide: "Usually a featured post, a list of recent posts and a newsletter sign-up. Start with the page intro line." },
  faq: { desc: "Answers to the questions you get most.", guide: "Usually grouped questions and a 'still stuck' contact prompt. Start with the five questions clients actually ask." },
  gallery: { desc: "Photos of your work or space.", guide: "Usually a filtered image grid and a short caption per project. Start by uploading your best six images." },
  careers: { desc: "Open roles and life at the company.", guide: "Usually a culture intro, open roles and how to apply. Start with the roles you are hiring for now." },
  work: { desc: "Case studies and past projects.", guide: "Usually a project grid with results per project. Start with your strongest project and its headline number." },
};
const FALLBACK = { desc: "A custom page on your site.", guide: "Add a hero for the page title, then the sections that suit it — text, images, a form or a call to action. Start with the hero heading." };

const infoFor = (p: any) => {
  const key = (p?.slug === "/" ? "home" : (p?.slug || "").replace("/", "")).toLowerCase();
  return GUIDES[key] || GUIDES[(p?.name || "").toLowerCase()] || FALLBACK;
};

const isLight = (hex: string) => {
  const h = (hex || "").replace("#", "");
  const full = h.length === 3 ? h.split("").map(c => c + c).join("") : h;
  if (full.length !== 6) return false;
  const lin = [0, 2, 4].map(i => parseInt(full.slice(i, i + 2), 16) / 255)
    .map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2] > 0.45;
};
const rgba = (hex: string, a: number) => {
  const h = (hex || "").replace("#", "");
  const full = h.length === 3 ? h.split("").map(c => c + c).join("") : h;
  if (full.length !== 6) return `rgba(139,92,246,${a})`;
  const [r, g, b] = [0, 2, 4].map(i => parseInt(full.slice(i, i + 2), 16));
  return `rgba(${r},${g},${b},${a})`;
};

/** Page Manager: every page as a tab with what it is for, an inline guide for the selected one,
 *  and an Add Page form that also places the page in the site navigation. */
export default function PageManager({ pages = [], current, onSelect, onCreate, onDelete, onToggleLock, canLock, theme }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [where, setWhere] = useState("end");
  const active = pages.find(p => p.page_id === current);
  const slug = name.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

  return (
    <div className="w-full" data-testid="page-manager">
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className="overline" data-testid="sm-group-label-pages">Pages</span>
        <span className="text-xs text-[var(--mut)]" data-testid="sm-group-hint-pages">Add pages and switch which one you are editing.</span>
      </div>

      <div className="mt-2 flex items-stretch gap-2.5 overflow-x-auto tenant-scroll pb-2 pr-4" data-testid="pages-bar">
        {pages.map(p => {
          const on = current === p.page_id;
          const brand = p?.theme_preview?.primary || theme?.primary || "#8B5CF6";
          const light = isLight(brand);
          const fg = on ? (light ? "#222222" : "#FFFFFF") : "var(--fg)";
          const tid = (p.slug || "").replace("/", "") || "home";
          return (
            <div key={p.page_id} data-testid={`page-tab-${tid}`} onClick={() => onSelect(p.page_id)}
              aria-current={on ? "true" : undefined} title={infoFor(p).desc}
              className="group shrink-0 w-[196px] min-h-[86px] rounded-xl px-3.5 py-3 cursor-pointer flex flex-col gap-1.5"
              style={{
                background: on ? rgba(brand, 0.85) : "var(--bg-2)",
                border: on ? `2px solid ${brand}` : "1px solid var(--line)",
                boxShadow: on ? `0 8px 26px ${rgba(brand, 0.3)}` : "none",
                color: fg,
                transition: "background-color .25s ease, border-color .25s ease, box-shadow .25s ease, color .25s ease",
              }}>
              <div className="flex items-center gap-1.5">
                {p.locked ? <Lock size={11} className="shrink-0" style={{ color: on ? fg : "#FBBF24" }} />
                  : <FileText size={11} className="shrink-0 opacity-70" />}
                <span className="text-sm font-semibold truncate" style={{ color: fg }}>{p.name}</span>
                {canLock && (
                  <button data-testid={`page-lock-${tid}`} title={p.locked ? "Unlock for clients" : "Lock so clients cannot edit"}
                    onClick={e => { e.stopPropagation(); onToggleLock(p); }}
                    className={`ml-auto w-4 h-4 flex items-center justify-center shrink-0 ${p.locked ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`}
                    style={{ color: on ? fg : "#FBBF24" }}>{p.locked ? <Lock size={9} /> : <Unlock size={9} />}</button>
                )}
                {p.slug !== "/" && (
                  <button data-testid={`page-delete-${tid}`} onClick={e => { e.stopPropagation(); onDelete(p); }}
                    className="w-4 h-4 flex items-center justify-center shrink-0 opacity-0 group-hover:opacity-100 hover:text-red-400"
                    style={{ color: on ? fg : "var(--dim)" }}><Trash2 size={9} /></button>
                )}
              </div>
              <p className="text-[11px] leading-snug" data-testid={`page-desc-${tid}`}
                style={{ color: on ? rgba(light ? "#000000" : "#FFFFFF", 0.78) : "var(--mut)" }}>
                {infoFor(p).desc}
              </p>
            </div>
          );
        })}
        <button data-testid="page-add-btn" onClick={() => setOpen(true)}
          className="shrink-0 min-h-[86px] px-4 rounded-xl border border-dashed border-[var(--line)] flex items-center gap-2 text-sm text-[var(--mut)] hover:text-white hover:border-white/40">
          <Plus size={14} /> Add Page
        </button>
      </div>

      {active && (
        <div className="mt-1 rounded-xl border border-[var(--line)] bg-[var(--bg-2)] px-4 py-3" data-testid="page-guide">
          <div className="text-xs font-semibold">{active.name} — {infoFor(active).desc}</div>
          <p className="text-xs text-[var(--mut)] mt-1 leading-relaxed">{infoFor(active).guide}</p>
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)]">
          <DialogHeader><DialogTitle className="font-display">Add a page</DialogTitle></DialogHeader>
          <label className="block"><span className="overline block mb-1">Page name</span>
            <input data-testid="page-name-input" value={name} onChange={e => setName(e.target.value)} placeholder="About us"
              className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--acc)]" /></label>
          <label className="block"><span className="overline block mb-1">Where should it appear in the navigation?</span>
            <select data-testid="page-nav-select" value={where} onChange={e => setWhere(e.target.value)}
              className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--acc)]">
              <option value="end">Last item in the menu</option>
              <option value="start">First item in the menu</option>
              {pages.map(p => <option key={p.page_id} value={`after:${p.slug}`}>Right after {p.name}</option>)}
              <option value="hidden">Do not add it to the menu</option>
            </select></label>
          <div className="text-xs font-mono text-[var(--mut)]">slug: /{slug}</div>
          <button data-testid="page-create-btn" disabled={!name.trim()}
            onClick={() => { onCreate(name.trim(), where); setName(""); setWhere("end"); setOpen(false); }}
            className="btn-primary w-full disabled:opacity-50">Create page</button>
        </DialogContent>
      </Dialog>
    </div>
  );
}
