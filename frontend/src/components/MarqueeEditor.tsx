import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, RotateCcw } from "lucide-react";
import api from "@/lib/api";
import MarqueeRibbon from "@/components/editorial/MarqueeRibbon";

/** Text ribbon editor. "All pages" edits the site-wide ribbon; picking a page edits only that page,
 *  and any field left blank there inherits the site-wide wording. Saves straight to the live site.
 *  `textOnly` (client portal) hides speed / opacity / size / show-hide — those stay agency-only. */
export default function MarqueeEditor({ appId, accent = "#10B981", mode = "dark", textOnly = false, compact = false, onSaved = () => {} }) {
  const [d, setD] = useState<any>(null);
  const [slug, setSlug] = useState("");                 // "" = site-wide
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!appId) return;
    api.get(`/apps/${appId}/marquee`).then(r => setD(r.data)).catch(() => toast.error("Could not load the text ribbon"));
  }, [appId]);

  if (!d) return null;

  const pageRow = slug ? (d.pages || {})[slug] || {} : null;
  const val = (k: string) => (pageRow ? (pageRow[k] ?? "") : d[k]);
  const inherited = (k: string) => d[k];

  function setLocal(k: string, v: any) {
    if (!slug) return setD((s: any) => ({ ...s, [k]: v }));
    setD((s: any) => ({ ...s, pages: { ...(s.pages || {}), [slug]: { ...((s.pages || {})[slug] || {}), [k]: v } } }));
  }

  async function save(patch: any) {
    setBusy(true);
    try {
      const { data } = slug
        ? await api.put(`/apps/${appId}/marquee/pages${slug}`, patch)
        : await api.put(`/apps/${appId}/marquee`, patch);
      setD({ ...data, pages_list: d.pages_list });
      onSaved();
      toast.success(slug ? "Page ribbon updated on the live site" : "Text ribbon updated on the live site");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not save the text ribbon");
    } finally { setBusy(false); }
  }

  async function reset() {
    setBusy(true);
    try {
      const { data } = slug
        ? await api.delete(`/apps/${appId}/marquee/pages${slug}`)
        : await api.post(`/apps/${appId}/marquee/reset`);
      setD({ ...data, pages_list: d.pages_list });
      onSaved();
      toast.success(slug ? "This page is back to the site-wide ribbon" : "Template ribbon restored");
    } catch { toast.error("Could not restore the ribbon"); }
    finally { setBusy(false); }
  }

  const slider = (key: string, label: string, min: number, max: number, step: number, fmt: (v: number) => string) => {
    const v = Number(val(key) || inherited(key));
    return (
      <div>
        <div className="flex items-center justify-between text-xs text-[var(--mut)]">
          <span>{label}</span><span className="font-mono" style={{ color: accent }}>{fmt(v)}</span>
        </div>
        <input type="range" data-testid={`marquee-${key}`} min={min} max={max} step={step} value={v}
          onChange={e => setLocal(key, Number(e.target.value))}
          onMouseUp={e => save({ [key]: Number((e.target as HTMLInputElement).value) })}
          onTouchEnd={e => save({ [key]: Number((e.target as HTMLInputElement).value) })}
          className="w-full mt-1.5 accent-[var(--acc)] cursor-pointer" />
      </div>
    );
  };

  return (
    <div className={compact ? "" : "py-4 border-b border-[var(--line)]"} data-testid="marquee-editor-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold">Text ribbon</div>
          <div className="text-xs text-[var(--mut)] mt-0.5">
            Two looping outline-text bands: one under the hero, one before the closing call to action.
            {" "}Pick a page to give it its own wording.
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!textOnly && (
            <button data-testid="marquee-enabled-toggle" onClick={() => save({ enabled: !(val("enabled") ?? inherited("enabled")) })}
              className={`chip cursor-pointer ${(val("enabled") ?? inherited("enabled")) ? "chip-active" : ""}`}>
              {(val("enabled") ?? inherited("enabled")) ? "Showing" : "Hidden"}
            </button>
          )}
          <button data-testid="marquee-reset-btn" onClick={reset} disabled={busy}
            className="chip cursor-pointer flex items-center gap-1 hover:!text-white"><RotateCcw size={11} /> Reset</button>
          {busy && <Loader2 size={13} className="animate-spin text-[var(--mut)]" />}
        </div>
      </div>

      <div className="mt-3">
        <div className="text-xs text-[var(--mut)] mb-1">Editing</div>
        <select data-testid="marquee-page-select" value={slug} onChange={e => setSlug(e.target.value)}
          className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]">
          <option value="">All pages (site-wide ribbon)</option>
          {(d.pages_list || []).map((p: any) => (
            <option key={p.slug} value={p.slug}>
              {p.name} ({p.slug}){(d.pages || {})[p.slug] ? " · custom" : ""}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {[["top_text", "Top ribbon text"], ["bottom_text", "Bottom ribbon text"]].map(([k, label]) => (
          <div key={k}>
            <div className="text-xs text-[var(--mut)] mb-1">{label}</div>
            <input data-testid={`marquee-${k}`} value={val(k) || ""} maxLength={160}
              placeholder={slug ? `Inherits: ${inherited(k) || "—"}` : ""}
              onChange={e => setLocal(k, e.target.value)} onBlur={() => save({ [k]: val(k) || "" })}
              onKeyDown={e => { if (e.key === "Enter") save({ [k]: val(k) || "" }); }}
              className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]" />
          </div>
        ))}
      </div>

      {!textOnly && (
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {slider("speed", "Scroll speed", 0.2, 3, 0.1, v => `${v.toFixed(1)}x`)}
          {slider("stroke_opacity", "Outline opacity", 0.05, 1, 0.05, v => `${Math.round(v * 100)}%`)}
          {slider("font_size", "Font size", 0.5, 2.5, 0.1, v => `${v.toFixed(1)}x`)}
        </div>
      )}

      <div className="mt-4 rounded-2xl overflow-hidden border border-[var(--line)]" data-testid="marquee-editor-preview">
        <MarqueeRibbon text={val("top_text") || inherited("top_text")} accent={accent}
          speed={Number(val("speed") || inherited("speed"))}
          strokeOpacity={Number(val("stroke_opacity") || inherited("stroke_opacity"))}
          fontSize={Math.min(0.6, Number(val("font_size") || inherited("font_size")) * 0.35)}
          mode={mode} testid="marquee-preview-ribbon" />
      </div>
    </div>
  );
}
