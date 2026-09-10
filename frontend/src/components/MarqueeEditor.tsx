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
      if (slug) await api.put(`/apps/${appId}/marquee/pages${slug}`, patch);
      else await api.put(`/apps/${appId}/marquee`, patch);
      const { data } = await api.get(`/apps/${appId}/marquee`);
      setD(data);
      onSaved();
      toast.success(slug ? "Page ribbon updated on the live site" : "Text ribbon updated on the live site");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not save the text ribbon");
    } finally { setBusy(false); }
  }

  async function reset() {
    setBusy(true);
    try {
      if (slug) await api.delete(`/apps/${appId}/marquee/pages${slug}`);
      else await api.post(`/apps/${appId}/marquee/reset`);
      const { data } = await api.get(`/apps/${appId}/marquee`);
      setD(data);
      onSaved();
      toast.success(slug ? "This page is back to the site-wide ribbon" : "Project ribbon restored");
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
        {[["top_text", "Top ribbon", "top_source", "top_figure"], ["bottom_text", "Bottom ribbon", "bottom_source", "bottom_figure"]].map(([k, label, sk, fk]) => {
          const src = val(sk) || inherited(sk) || "static";
          return (
            <div key={k}>
              <div className="flex items-center justify-between mb-1">
                <div className="text-xs text-[var(--mut)]">{label}</div>
                <select data-testid={`marquee-${sk}`} value={src}
                  onChange={e => { setLocal(sk, e.target.value); save({ [sk]: e.target.value }); }}
                  className="bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2 py-1 text-[11px] outline-none focus:border-[var(--acc)]">
                  <option value="static">Your own wording</option>
                  <option value="review">Newest review quote</option>
                  <option value="offer">Current offer</option>
                  <option value="figure">A live figure</option>
                </select>
              </div>
              {src === "figure" ? (
                <select data-testid={`marquee-${fk}`} value={Number(val(fk) ?? inherited(fk) ?? 0)}
                  onChange={e => save({ [fk]: Number(e.target.value) })}
                  className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]">
                  {(d.figures || []).map((f: any) => <option key={f.index} value={f.index}>{f.value} {f.label}</option>)}
                  {(d.figures || []).length === 0 && <option value={0}>No figures yet — add them in your figures editor</option>}
                </select>
              ) : (
                <input data-testid={`marquee-${k}`} value={val(k) || ""} maxLength={160}
                  disabled={src !== "static"}
                  placeholder={src === "review" ? "Pulled live from your newest review"
                    : src === "offer" ? "Pulled live from the offer below" : (slug ? `Inherits: ${inherited(k) || "—"}` : "")}
                  onChange={e => setLocal(k, e.target.value)} onBlur={() => save({ [k]: val(k) || "" })}
                  onKeyDown={e => { if (e.key === "Enter") save({ [k]: val(k) || "" }); }}
                  className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)] disabled:opacity-50" />
              )}
              {src !== "static" && (
                <div className="text-[10px] text-[var(--mut)] mt-1" data-testid={`marquee-${k}-live`}>
                  Now showing: {(d.live || {})[k] || "—"}
                  {(d.live || {})[sk.replace("_source", "_live")] === "static" && " (falls back to your wording)"}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {!slug && (
        <div className="mt-3 rounded-xl border border-[var(--line)] p-3" data-testid="marquee-offer-block">
          <div className="text-xs text-[var(--mut)] mb-1">Current offer — shown by any ribbon set to “Current offer”</div>
          <input data-testid="marquee-offer_text" value={d.offer_text || ""} maxLength={160}
            placeholder="e.g. 15% OFF EVERY BOILER SERVICE BOOKED THIS MONTH"
            onChange={e => setD((s: any) => ({ ...s, offer_text: e.target.value }))}
            onBlur={() => save({ offer_text: d.offer_text || "" })}
            onKeyDown={e => { if (e.key === "Enter") save({ offer_text: d.offer_text || "" }); }}
            className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]" />
          {!textOnly && (
            <div className="mt-2 grid grid-cols-2 gap-3">
              {[["offer_from", "Starts (optional)"], ["offer_to", "Ends (optional)"]].map(([k, label]) => (
                <div key={k}>
                  <div className="text-[10px] text-[var(--mut)] mb-1">{label}</div>
                  <input type="date" data-testid={`marquee-${k}`} value={d[k] || ""}
                    onChange={e => save({ [k]: e.target.value })}
                    className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2.5 py-2 text-xs outline-none focus:border-[var(--acc)]" />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {!textOnly && (
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {slider("speed", "Scroll speed", 0.2, 3, 0.1, v => `${v.toFixed(1)}x`)}
          {slider("stroke_opacity", "Outline opacity", 0.05, 1, 0.05, v => `${Math.round(v * 100)}%`)}
          {slider("font_size", "Font size", 0.5, 2.5, 0.1, v => `${v.toFixed(1)}x`)}
        </div>
      )}

      <div className="mt-4 rounded-2xl overflow-hidden border border-[var(--line)]" data-testid="marquee-editor-preview">
        <MarqueeRibbon text={(d.live || {}).top_text || val("top_text") || inherited("top_text")} accent={accent}
          speed={Number(val("speed") || inherited("speed"))}
          strokeOpacity={Number(val("stroke_opacity") || inherited("stroke_opacity"))}
          fontSize={Math.min(0.6, Number(val("font_size") || inherited("font_size")) * 0.35)}
          mode={mode} testid="marquee-preview-ribbon" />
      </div>
    </div>
  );
}
