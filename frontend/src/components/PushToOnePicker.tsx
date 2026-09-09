import { useState } from "react";
import { ChevronDown, Rocket } from "lucide-react";

/** Small "Push to One …" picker used on the Test Lab tenant card and the Test Template card. */
export default function PushToOnePicker({ label, options, onPick, testid }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative" onClick={(e) => e.stopPropagation()}>
      <button data-testid={`${testid}-btn`} onClick={() => setOpen((o) => !o)}
        className="w-full btn-ghost text-xs !py-2 flex items-center justify-center gap-1.5">
        <Rocket size={11} /> {label} <ChevronDown size={11} />
      </button>
      {open && (
        <div data-testid={`${testid}-menu`}
          className="absolute z-30 left-0 right-0 mt-1 max-h-56 overflow-y-auto rounded-xl border border-[var(--line)] bg-[var(--bg-2)] shadow-xl">
          {!options.length && <div className="px-3 py-2 text-xs text-[var(--mut)]">Nothing to push to yet</div>}
          {options.map((o) => (
            <button key={o.value} data-testid={`${testid}-option-${o.value}`}
              onClick={() => { setOpen(false); onPick(o.value); }}
              className="w-full text-left px-3 py-2 text-xs hover:bg-white/5 flex items-center justify-between gap-2">
              <span className="truncate">{o.label}</span>
              {o.badge && <span className="chip chip-maint shrink-0">{o.badge}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
