/** Site Mode control groups. Every control declares an id; `groupOf()` decides where it lands,
 *  so a new feature can never appear orphaned — it is placed automatically by function.
 *  Groups with more than MAX_VISIBLE items collapse into an expandable "More" section. */

export const MAX_VISIBLE = 5;

export type GroupDef = { key: string; label: string; hint: string };

export const GROUPS: GroupDef[] = [
  { key: "pages", label: "Pages", hint: "Add pages and switch which one you are editing." },
  { key: "design", label: "Design", hint: "Control how your site looks and moves." },
  { key: "publishing", label: "Publishing", hint: "Choose who can see your site right now." },
  { key: "tools", label: "Tools", hint: "Make big changes or import content." },
  { key: "more", label: "More", hint: "Anything new lands here until it has a home." },
];

/** id keyword -> group. Checked as substrings so new ids are classified automatically. */
const RULES: [string, string][] = [
  ["page", "pages"],
  ["design", "design"], ["mode", "design"], ["theme", "design"], ["accent", "design"],
  ["colour", "design"], ["color", "design"], ["hero", "design"], ["motion", "design"],
  ["anim", "design"], ["logo", "design"], ["skin", "design"],
  ["publish", "publishing"], ["draft", "publishing"], ["live", "publishing"],
  ["preview", "publishing"], ["domain", "publishing"],
  ["generate", "tools"], ["import", "tools"], ["export", "tools"], ["history", "tools"],
  ["lock", "tools"], ["ai", "tools"], ["upload", "tools"], ["save", "tools"],
  ["request", "tools"], ["reset", "tools"], ["sync", "tools"],
];

export function groupOf(id: string, explicit?: string) {
  if (explicit && GROUPS.some(g => g.key === explicit)) return explicit;
  const key = (id || "").toLowerCase();
  for (const [needle, group] of RULES) if (key.includes(needle)) return group;
  return "more";
}

export type ToolItem = { id: string; group?: string; node: any };

/** Buckets controls into their groups, preserving declaration order. */
export function groupItems(items: ToolItem[]) {
  const out: { def: GroupDef; items: ToolItem[] }[] = [];
  for (const def of GROUPS) {
    const mine = items.filter(it => it && groupOf(it.id, it.group) === def.key);
    if (mine.length) out.push({ def, items: mine });
  }
  return out;
}
