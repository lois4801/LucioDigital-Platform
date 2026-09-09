import { useState } from "react";
import { AlertTriangle, ArrowLeft, Layers, Rocket, ShieldCheck } from "lucide-react";

const CAT_ORDER = ["Design", "Animations", "Features", "Content", "Forms"];

const fmt = (v) => {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "on" : "off";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
};

const isColour = (v) => typeof v === "string" && /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(v);

function Swatch({ value }) {
  if (!isColour(value)) return null;
  return <span className="inline-block w-3 h-3 rounded-sm border border-white/20 align-middle mr-1.5" style={{ background: value }} />;
}

/** Read-only diff table. Used by the Diff Viewer and by each Rollout History entry. */
export function DiffTable({ diff, selected, onToggle }) {
  const cats = CAT_ORDER.filter((c) => (diff?.by_category?.[c] || []).length);
  if (!cats.length) {
    return <div data-testid="diff-empty" className="p-6 text-sm text-[var(--mut)] text-center border border-dashed border-[var(--line)] rounded-xl">
      Nothing differs between the Test Lab and your live tenants right now.
    </div>;
  }
  return (
    <div className="space-y-6">
      {cats.map((cat) => (
        <div key={cat} data-testid={`diff-category-${cat.toLowerCase()}`}>
          <div className="overline flex items-center gap-2 mb-2">
            <Layers size={11} className="text-[var(--acc)]" /> {cat}
            <span className="font-mono text-[10px] text-[var(--dim)]">{diff.by_category[cat].length}</span>
          </div>
          <div className="rounded-xl border border-[var(--line)] overflow-hidden">
            <div className="grid grid-cols-[1fr_1fr] text-[10px] uppercase tracking-wider text-[var(--dim)] bg-[var(--bg-2)] border-b border-[var(--line)]">
              <div className="px-3 py-2">Live tenants now</div>
              <div className="px-3 py-2 border-l border-[var(--line)]">Test Lab (incoming)</div>
            </div>
            {diff.by_category[cat].map((c) => (
              <div key={c.id} data-testid={`diff-row-${c.id}`}
                className="border-b border-[var(--line)] last:border-b-0">
                <div className="px-3 pt-2.5 flex items-center gap-2 flex-wrap">
                  {onToggle && (
                    <input type="checkbox" data-testid={`diff-check-${c.id}`} checked={selected.includes(c.id)}
                      onChange={() => onToggle(c.id)} className="accent-[var(--acc)]" />
                  )}
                  <span className="text-sm font-semibold">{c.label}</span>
                  <span className={`chip ${c.kind === "removed" ? "chip-down" : c.kind === "added" ? "chip-active" : ""}`}>
                    {c.kind}
                  </span>
                  <span className="font-mono text-[10px] text-[var(--dim)]">affects {c.tenants} tenant{c.tenants === 1 ? "" : "s"}</span>
                  {c.variance && <span className="chip chip-maint">tenants differ</span>}
                </div>
                <div className="grid grid-cols-[1fr_1fr] mt-1.5">
                  <div className="px-3 py-2.5 text-xs font-mono break-all text-red-300/90 line-through decoration-red-400/60">
                    <Swatch value={c.old} />{fmt(c.old)}
                  </div>
                  <div className="px-3 py-2.5 text-xs font-mono break-all border-l border-[var(--line)] text-emerald-300 bg-emerald-500/[0.06]">
                    <Swatch value={c.new} />{fmt(c.new)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/** Full-screen viewer shown BEFORE the confirmation modal. */
export default function DiffViewer({ diff, onBack, onPush }) {
  const all = (diff?.changes || []).map((c) => c.id);
  const [selected, setSelected] = useState(all);

  function toggle(id) {
    setSelected(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);
  }

  return (
    <div className="fixed inset-0 z-[75] bg-[var(--bg)] overflow-y-auto" data-testid="diff-viewer">
      <div className="max-w-6xl mx-auto px-5 py-8">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="overline">Test Lab · rollout review</div>
            <h2 className="font-display text-3xl font-semibold tracking-tight mt-1">What will change</h2>
            <p className="text-sm text-[var(--mut)] mt-2 max-w-2xl">
              {diff.total} change{diff.total === 1 ? "" : "s"} across {diff.target_count} live tenant
              {diff.target_count === 1 ? "" : "s"}. Old values are struck through in red, incoming Test Lab
              values are green. Tenant text, images, pages, leads and CMS records are never touched.
            </p>
          </div>
          <button data-testid="diff-back-btn" onClick={onBack} className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2">
            <ArrowLeft size={14} /> Back
          </button>
        </div>

        <div className="mt-7">
          <DiffTable diff={diff} selected={selected} onToggle={toggle} />
        </div>

        {!!diff.total && (
          <div className="mt-6 p-3 rounded-xl bg-amber-500/8 border border-amber-500/30 text-sm text-amber-200 flex items-start gap-2">
            <AlertTriangle size={15} className="mt-0.5 shrink-0" />
            Nothing has been pushed yet — you will be asked to confirm on the next screen.
          </div>
        )}

        <div className="sticky bottom-0 mt-6 -mx-5 px-5 py-4 bg-[var(--bg)]/95 backdrop-blur border-t border-[var(--line)] flex flex-wrap gap-2">
          <button data-testid="diff-back-btn-bottom" onClick={onBack} className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2">
            <ArrowLeft size={14} /> Back
          </button>
          <button data-testid="diff-push-selected-btn" onClick={() => onPush(selected)}
            disabled={!selected.length}
            className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2 disabled:opacity-50">
            <ShieldCheck size={14} /> Push Selected ({selected.length})
          </button>
          <button data-testid="diff-push-all-btn" onClick={() => onPush(all)} disabled={!all.length}
            className="btn-primary text-sm !py-2 !px-4 flex items-center gap-2 disabled:opacity-50">
            <Rocket size={14} /> Push All ({all.length})
          </button>
        </div>
      </div>
    </div>
  );
}
