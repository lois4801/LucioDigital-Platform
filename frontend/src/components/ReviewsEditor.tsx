import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Loader2, Plus, Trash2, GripVertical, RotateCcw, Star } from "lucide-react";
import api from "@/lib/api";

/** Reviews editor: edit every field, add or remove reviews, drag to reorder, and control the
 *  section's colours independently of the template. Saves instantly — no publish step. */
export default function ReviewsEditor({ appId, accent = "#10B981", compact = false }) {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<number | null>(0);
  const drag = useRef<number | null>(null);

  useEffect(() => {
    if (!appId) return;
    api.get(`/apps/${appId}/reviews`).then(r => setData(r.data)).catch(() => toast.error("Could not load the reviews"));
  }, [appId]);

  const set = (patch: any) => setData((s: any) => ({ ...s, ...patch }));

  async function save(next?: any) {
    const payload = next || { reviews: data.reviews, style: data.style };
    setBusy(true);
    try {
      const { data: got } = await api.put(`/apps/${appId}/reviews`, payload);
      setData(got);
      toast.success("Reviews updated on the live site");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not save the reviews");
    } finally { setBusy(false); }
  }

  async function reset() {
    setBusy(true);
    try {
      const { data: got } = await api.post(`/apps/${appId}/reviews/reset`);
      setData(got);
      toast.success("Template reviews and colours restored");
    } catch { toast.error("Could not restore the template reviews"); }
    finally { setBusy(false); }
  }

  const editRow = (i: number, key: string, val: any) =>
    set({ reviews: data.reviews.map((r: any, j: number) => j === i ? { ...r, [key]: val } : r) });

  function move(from: number, to: number) {
    if (from === to || to < 0 || to >= data.reviews.length) return;
    const rows = [...data.reviews];
    rows.splice(to, 0, rows.splice(from, 1)[0]);
    set({ reviews: rows });
  }

  function addReview() {
    const rows = [...data.reviews, {
      name: "New reviewer", title: "Job title", company: "Company name",
      company_desc: "What they do", quote: "What they said about working with you.",
      tags: ["Outcome one", "Outcome two"], city: "Toronto", country: "Canada", flag: "ca", rating: 5,
    }];
    set({ reviews: rows });
    setOpen(rows.length - 1);
  }

  if (!data) return (
    <div className="py-4 text-sm text-[var(--mut)] flex items-center gap-2" data-testid="reviews-editor-loading">
      <Loader2 size={14} className="animate-spin" /> Loading the reviews…
    </div>
  );

  const st = data.style || {};
  const inp = "w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2.5 py-1.5 text-xs outline-none focus:border-[var(--acc)]";

  return (
    <div className={compact ? "" : "py-4 border-b border-[var(--line)]"} data-testid="reviews-editor">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold flex items-center gap-2"><Star size={13} className="text-[var(--acc)]" /> Reviews &amp; testimonials</div>
          <div className="text-xs text-[var(--mut)] mt-0.5">
            {data.reviews.length} five-star reviews · {data.source === "custom" ? "edited for this tenant" : "written for this template"}. Colours follow the template unless you override them.
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button data-testid="reviews-add-btn" onClick={addReview} className="chip cursor-pointer hover:!text-white inline-flex items-center gap-1"><Plus size={11} /> Add review</button>
          <button data-testid="reviews-reset-btn" onClick={reset} disabled={busy} className="chip cursor-pointer hover:!text-white inline-flex items-center gap-1 disabled:opacity-50"><RotateCcw size={11} /> Reset to template default</button>
          <button data-testid="reviews-save-btn" onClick={() => save()} disabled={busy} className="btn-primary text-xs !py-1.5 !px-3 disabled:opacity-60">{busy ? "Saving…" : "Save reviews"}</button>
        </div>
      </div>

      <div className="mt-4 grid sm:grid-cols-2 gap-3">
        <label className="block"><span className="overline block mb-1">Section title</span>
          <input data-testid="reviews-title-input" value={st.title || ""} onChange={e => set({ style: { ...st, title: e.target.value } })} className={inp} /></label>
        <label className="block"><span className="overline block mb-1">Subtitle</span>
          <input data-testid="reviews-subtitle-input" value={st.subtitle || ""} onChange={e => set({ style: { ...st, subtitle: e.target.value } })} className={inp} /></label>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        {[["accent", "Accent (stars, tags, cursor)"], ["card_bg", "Card background"], ["title_color", "Title & subtitle"]].map(([k, label]) => (
          <label key={k} className="flex items-center gap-2 text-xs rounded-xl border border-[var(--line)] px-2.5 py-1.5" data-testid={`reviews-colour-${k}`}>
            <input type="color" value={st[k] || (k === "accent" ? accent : k === "card_bg" ? "#111111" : "#FFFFFF")}
              onChange={e => set({ style: { ...st, [k]: e.target.value.toUpperCase() } })}
              className="w-6 h-6 rounded bg-transparent border-0 p-0 cursor-pointer" />
            {label}
            {st[k] && <button data-testid={`reviews-colour-clear-${k}`} onClick={() => set({ style: { ...st, [k]: "" } })}
              className="text-[var(--mut)] hover:text-white">clear</button>}
          </label>
        ))}
      </div>

      <div className="mt-4 space-y-2 max-h-[520px] overflow-y-auto tenant-scroll pr-1">
        {data.reviews.map((r: any, i: number) => (
          <div key={r.id || i} draggable onDragStart={() => { drag.current = i; }}
            onDragOver={e => e.preventDefault()}
            onDrop={() => { if (drag.current !== null) move(drag.current, i); drag.current = null; }}
            className="rounded-xl border border-[var(--line)] p-2.5" data-testid={`reviews-row-${i}`}>
            <div className="flex items-center gap-2">
              <GripVertical size={12} className="text-[var(--dim)] cursor-grab shrink-0" data-testid={`reviews-drag-${i}`} />
              <button onClick={() => setOpen(open === i ? null : i)} className="flex-1 min-w-0 text-left">
                <span className="text-xs font-semibold truncate block">{r.company || r.name}</span>
                <span className="text-[11px] text-[var(--mut)] truncate block">{r.name} · {r.title}</span>
              </button>
              <button data-testid={`reviews-up-${i}`} onClick={() => move(i, i - 1)} className="chip cursor-pointer !px-2">↑</button>
              <button data-testid={`reviews-down-${i}`} onClick={() => move(i, i + 1)} className="chip cursor-pointer !px-2">↓</button>
              <button data-testid={`reviews-del-${i}`} onClick={() => set({ reviews: data.reviews.filter((_: any, j: number) => j !== i) })}
                className="chip cursor-pointer hover:!text-red-400 !px-2"><Trash2 size={11} /></button>
            </div>
            {open === i && (
              <div className="mt-2.5 grid sm:grid-cols-2 gap-2">
                {[["name", "Reviewer name"], ["title", "Job title"], ["company", "Company"], ["company_desc", "One-line description"],
                  ["city", "City"], ["country", "Country"], ["flag", "Flag code (ca, ng, jp)"], ["photo", "Photo URL"]].map(([k, label]) => (
                  <label key={k} className="block"><span className="overline block mb-1">{label}</span>
                    <input data-testid={`reviews-${k}-${i}`} value={r[k] || ""} onChange={e => editRow(i, k, e.target.value)} className={inp} /></label>
                ))}
                <label className="block sm:col-span-2"><span className="overline block mb-1">Review quote</span>
                  <textarea data-testid={`reviews-quote-${i}`} value={r.quote || ""} rows={3}
                    onChange={e => editRow(i, "quote", e.target.value)} className={inp} /></label>
                {[0, 1].map(t => (
                  <label key={t} className="block"><span className="overline block mb-1">Outcome tag {t + 1}</span>
                    <input data-testid={`reviews-tag-${t}-${i}`} value={(r.tags || [])[t] || ""}
                      onChange={e => { const tags = [...(r.tags || ["", ""])]; tags[t] = e.target.value; editRow(i, "tags", tags); }}
                      className={inp} /></label>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
