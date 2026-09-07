import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { RotateCcw, Globe2 } from "lucide-react";
import api from "@/lib/api";

const Ctx = createContext(null);

export function UiLabelsProvider({ appId, children }) {
  const [state, setState] = useState({ labels: {}, tenant: {}, global: {}, can_edit: false });

  useEffect(() => {
    if (!appId) return;
    api.get(`/apps/${appId}/ui_labels`).then(r => setState(r.data)).catch(() => {});
  }, [appId]);

  const save = useCallback(async (key, value, scope = "tenant") => {
    const { data } = await api.put(`/apps/${appId}/ui_labels`, { labels: { [key]: value }, scope });
    setState(s => ({ ...s, ...data }));
  }, [appId]);

  const reset = useCallback(async (scope = "tenant") => {
    const { data } = await api.delete(`/apps/${appId}/ui_labels?scope=${scope}`);
    setState(s => ({ ...s, ...data }));
  }, [appId]);

  const applyAllTenants = useCallback(async () => {
    const tenant = state.tenant || {};
    if (!Object.keys(tenant).length) { toast.info("Nothing to apply — edit some labels first."); return; }
    const { data } = await api.put(`/apps/${appId}/ui_labels`, { labels: tenant, scope: "global" });
    setState(s => ({ ...s, ...data }));
    toast.success("Applied to all tenants");
  }, [appId, state.tenant]);

  return <Ctx.Provider value={{ ...state, save, reset, applyAllTenants }}>{children}</Ctx.Provider>;
}

export function useUiLabels() {
  return useContext(Ctx) || { labels: {}, can_edit: false, save: async () => {} };
}

// Inline click-to-edit label. Admin/owner edits; everyone else sees plain text.
export function L({ k, d, as: Tag = "span", className, testid }) {
  const { labels, can_edit, save } = useUiLabels();
  const ref = useRef(null);
  const value = labels[k] ?? d;
  const tid = testid || `ui-label-${k}`;

  useEffect(() => { if (ref.current && ref.current.innerText !== value) ref.current.innerText = value; }, [value]);

  if (!can_edit) return <Tag className={className} data-testid={tid}>{value}</Tag>;
  return (
    <Tag
      ref={ref}
      data-testid={tid}
      data-label-key={k}
      contentEditable
      suppressContentEditableWarning
      title="Click to edit"
      className={`${className || ""} outline-none rounded-sm cursor-text hover:ring-1 hover:ring-[var(--acc)]/50 focus:ring-2 focus:ring-[var(--acc)] transition-shadow`}
      onKeyDown={e => {
        if (e.key === "Enter") { e.preventDefault(); ref.current.blur(); }
        if (e.key === "Escape") { ref.current.innerText = value; ref.current.blur(); }
      }}
      onBlur={async () => {
        const v = ref.current.innerText.trim();
        if (!v || v === value) { ref.current.innerText = value; return; }
        try { await save(k, v); toast.success("Saved"); }
        catch { toast.error("Save failed"); ref.current.innerText = value; }
      }}
    >
      {value}
    </Tag>
  );
}

export function UiLabelsToolbar() {
  const { can_edit, applyAllTenants, reset } = useUiLabels();
  if (!can_edit) return null;
  return (
    <div data-testid="ui-labels-toolbar" className="flex flex-wrap items-center gap-2 justify-end">
      <span className="text-xs text-[var(--dim)] mr-auto">Click any label to rename it — changes save to this tenant.</span>
      <button data-testid="ui-labels-apply-all-btn" onClick={applyAllTenants}
        className="btn-ghost text-xs !py-1.5 !px-3 flex items-center gap-1.5"><Globe2 size={12} /> Apply to all tenants</button>
      <button data-testid="ui-labels-reset-btn"
        onClick={async () => { if (!confirm("Reset all label edits for this tenant back to defaults?")) return; try { await reset("tenant"); toast.success("Reset to defaults"); } catch { toast.error("Reset failed"); } }}
        className="btn-ghost text-xs !py-1.5 !px-3 flex items-center gap-1.5"><RotateCcw size={12} /> Reset all</button>
    </div>
  );
}
