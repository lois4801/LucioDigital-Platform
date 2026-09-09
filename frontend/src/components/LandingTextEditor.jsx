import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Loader2, Pencil, Save, Search, X } from "lucide-react";

const LABELS = {
  brand_name: "Brand name", brand_suffix: "Brand suffix", hero_eyebrow: "Hero eyebrow",
  hero_h1: "Hero headline", hero_h1_accent: "Hero headline (accent)", hero_sub: "Hero subheading",
  hero_cta: "Hero button (visitor)", hero_cta_user: "Hero button (signed in)", hero_cta2: "Hero secondary button",
  showcase_view_all: "Showcase link",
};

/** Edit every landing-page text from inside the dashboard — no need to leave. */
export default function LandingTextEditor({ open, onClose }) {
  const [texts, setTexts] = useState(null);
  const [draft, setDraft] = useState({});
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setQ(""); setDraft({});
    api.get("/public/landing").then(({ data }) => setTexts(data.texts || {}))
      .catch(() => toast.error("Could not load the landing text"));
  }, [open]);

  const rows = useMemo(() => {
    const keys = Object.keys(texts || {}).sort();
    if (!q.trim()) return keys;
    const needle = q.toLowerCase();
    return keys.filter((k) => k.includes(needle) || String(texts[k]).toLowerCase().includes(needle));
  }, [texts, q]);

  const dirty = Object.keys(draft).length;

  async function save() {
    setBusy(true);
    try {
      await api.put("/admin/landing", { texts: { ...texts, ...draft } });
      setTexts((t) => ({ ...t, ...draft }));
      setDraft({});
      toast.success(`Saved ${dirty} text${dirty === 1 ? "" : "s"} — live on the landing page`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally { setBusy(false); }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[85] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
      data-testid="landing-text-editor" onClick={onClose}>
      <div className="card-surface w-full max-w-2xl max-h-[88vh] flex flex-col p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="overline">Landing page</div>
            <h3 className="font-display text-xl font-semibold tracking-tight mt-1 flex items-center gap-2">
              <Pencil size={15} className="text-[var(--acc)]" /> Edit landing text
            </h3>
          </div>
          <button data-testid="landing-text-close-btn" onClick={onClose} className="btn-ghost !p-2"><X size={15} /></button>
        </div>

        <div className="relative mt-4">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--mut)]" />
          <input data-testid="landing-text-search" value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Search headline, button, pricing…"
            className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl pl-9 pr-3 py-2.5 text-sm focus:border-[var(--acc)] outline-none" />
        </div>

        <div className="mt-4 flex-1 overflow-y-auto scrollbar-thin space-y-3 pr-1">
          {!texts ? (
            <div className="py-12 flex justify-center"><Loader2 size={18} className="animate-spin text-[var(--mut)]" /></div>
          ) : !rows.length ? (
            <div className="py-10 text-center text-sm text-[var(--mut)]">No text matches “{q}”.</div>
          ) : rows.map((k) => {
            const value = draft[k] ?? texts[k] ?? "";
            const long = String(texts[k] || "").length > 70;
            return (
              <label key={k} className="block" data-testid={`landing-text-row-${k}`}>
                <span className="overline block mb-1.5">{LABELS[k] || k.replace(/_/g, " ")}</span>
                {long ? (
                  <textarea data-testid={`landing-text-input-${k}`} rows={3} value={value}
                    onChange={(e) => setDraft((d) => ({ ...d, [k]: e.target.value }))}
                    className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm focus:border-[var(--acc)] outline-none resize-none" />
                ) : (
                  <input data-testid={`landing-text-input-${k}`} value={value}
                    onChange={(e) => setDraft((d) => ({ ...d, [k]: e.target.value }))}
                    className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm focus:border-[var(--acc)] outline-none" />
                )}
              </label>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-4 mt-2 border-t border-[var(--line)]">
          <button data-testid="landing-text-save-btn" onClick={save} disabled={!dirty || busy}
            className="btn-primary text-sm !py-2 !px-4 flex items-center gap-2 disabled:opacity-50">
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            {dirty ? `Save ${dirty} change${dirty === 1 ? "" : "s"}` : "Saved"}
          </button>
          <button data-testid="landing-text-cancel-btn" onClick={onClose} className="btn-ghost text-sm !py-2 !px-4">Close</button>
          <span className="text-[11px] text-[var(--dim)] ml-auto">Visitors see changes on their next page load.</span>
        </div>
      </div>
    </div>
  );
}
