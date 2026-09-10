import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { groupItems, MAX_VISIBLE, type ToolItem } from "@/lib/siteModeGroups";

/** Grouped, labelled Site Mode controls. Each group carries a one-line description, and any
 *  group longer than five items collapses into an expandable section so nothing gets crowded. */
export default function SiteModeToolbar({ items = [] as ToolItem[] }) {
  const groups = groupItems(items.filter(Boolean));
  return (
    <div className="flex flex-col gap-4" data-testid="site-mode-toolbar">
      {groups.map(({ def, items: list }) => (
        <Group key={def.key} def={def} list={list} />
      ))}
    </div>
  );
}

function Group({ def, list }) {
  const [open, setOpen] = useState(false);
  const overflow = list.length > MAX_VISIBLE;
  const shown = overflow && !open ? list.slice(0, MAX_VISIBLE) : list;
  return (
    <section data-testid={`sm-group-${def.key}`} data-count={list.length}>
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className="overline" data-testid={`sm-group-label-${def.key}`}>{def.label}</span>
        <span className="text-xs text-[var(--mut)]" data-testid={`sm-group-hint-${def.key}`}>{def.hint}</span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2.5">
        {shown.map(it => <div key={it.id} data-testid={`sm-item-${it.id}`}>{it.node}</div>)}
        {overflow && (
          <button data-testid={`sm-group-more-${def.key}`} onClick={() => setOpen(o => !o)}
            className="btn-ghost text-sm !py-2 !px-3 flex items-center gap-1.5">
            <ChevronDown size={13} className={`transition-transform ${open ? "rotate-180" : ""}`} />
            {open ? "Show less" : `${list.length - MAX_VISIBLE} more`}
          </button>
        )}
      </div>
    </section>
  );
}
