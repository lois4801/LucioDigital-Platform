import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { toast } from "sonner";
import { RotateCcw, Globe2 } from "lucide-react";
import api from "@/lib/api";
import { EditableText } from "@/components/InlineTextTools";

const Ctx = createContext(null);

export function UiLabelsProvider({ appId, children }) {
  const [state, setState] = useState({ labels: {}, styles: {}, tenant: {}, tenant_styles: {}, can_edit: false });

  useEffect(() => {
    if (!appId) return;
    api.get(`/apps/${appId}/ui_labels`).then(r => setState(r.data)).catch(() => {});
  }, [appId]);

  const save = useCallback(async (key, value, scope = "tenant") => {
    const { data } = await api.put(`/apps/${appId}/ui_labels`, { labels: { [key]: value }, scope });
    setState(s => ({ ...s, ...data }));
  }, [appId]);

  const saveStyle = useCallback(async (key, style) => {
    const { data } = await api.put(`/apps/${appId}/ui_labels`, { styles: { [key]: { font: style.font || "", color: style.color || "" } }, scope: "tenant" });
    setState(s => ({ ...s, ...data }));
  }, [appId]);

  const reset = useCallback(async (scope = "tenant") => {
    const { data } = await api.delete(`/apps/${appId}/ui_labels?scope=${scope}`);
    setState(s => ({ ...s, ...data }));
  }, [appId]);

  const applyAllTenants = useCallback(async () => {
    const labels = state.tenant || {};
    const styles = state.tenant_styles || {};
    if (!Object.keys(labels).length && !Object.keys(styles).length) { toast.info("Nothing to apply — edit some labels first."); return; }
    const { data } = await api.put(`/apps/${appId}/ui_labels`, { labels, styles, scope: "global" });
    setState(s => ({ ...s, ...data }));
    toast.success("Applied to all clients");
  }, [appId, state.tenant, state.tenant_styles]);

  return <Ctx.Provider value={{ ...state, save, saveStyle, reset, applyAllTenants }}>{children}</Ctx.Provider>;
}

export function useUiLabels() {
  return useContext(Ctx) || { labels: {}, styles: {}, can_edit: false, save: async () => {}, saveStyle: async () => {} };
}

// Inline click-to-edit label with font/colour toolbar. Admin/owner edits; others see plain text.
export function L({ k, d, as = "span", className, testid }) {
  const { labels, styles, can_edit, save, saveStyle } = useUiLabels();
  const value = labels[k] ?? d;
  const st = styles?.[k] || {};
  return (
    <EditableText
      as={as}
      value={value}
      className={className}
      editable={can_edit}
      font={st.font}
      color={st.color}
      testid={testid || `ui-label-${k}`}
      onCommit={async v => { try { await save(k, v); toast.success("Saved"); } catch { toast.error("Save failed"); } }}
      onStyleChange={async s => { try { await saveStyle(k, s); toast.success("Saved"); } catch { toast.error("Save failed"); } }}
    />
  );
}

export function UiLabelsToolbar() {
  const { can_edit, applyAllTenants, reset } = useUiLabels();
  if (!can_edit) return null;
  return (
    <div data-testid="ui-labels-toolbar" className="flex flex-wrap items-center gap-2 justify-end">
      <span className="text-xs text-[var(--dim)] mr-auto">Click any label to rename it, pick a font or colour · Ctrl+Z undoes while typing. The Overview title and summary follow Site Mode and can't be renamed here.</span>
      <button data-testid="ui-labels-apply-all-btn" onClick={applyAllTenants}
        className="btn-ghost text-xs !py-1.5 !px-3 flex items-center gap-1.5"><Globe2 size={12} /> Apply to all clients</button>
      <button data-testid="ui-labels-reset-btn"
        onClick={async () => { if (!confirm("Reset all label edits for this client back to defaults?")) return; try { await reset("tenant"); toast.success("Reset to defaults"); } catch { toast.error("Reset failed"); } }}
        className="btn-ghost text-xs !py-1.5 !px-3 flex items-center gap-1.5"><RotateCcw size={12} /> Reset all</button>
    </div>
  );
}
