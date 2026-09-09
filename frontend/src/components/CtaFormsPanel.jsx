import { useEffect, useState } from "react";
import { toast } from "sonner";
import { FileText, Loader2, RefreshCw } from "lucide-react";
import api from "@/lib/api";
import CtaFormEditor from "@/components/CtaFormEditor";

/** Lists every CTA button on the tenant site that has a modal form attached, with Edit Form. */
export default function CtaFormsPanel({ appId }) {
  const [state, setState] = useState({ forms: [], simplified: false, can_edit: true });
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(null);
  const [scanning, setScanning] = useState(false);

  const load = async () => {
    try { const { data } = await api.get(`/apps/${appId}/cta-forms`); setState(data); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not load the forms"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [appId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function rescan() {
    setScanning(true);
    try {
      const { data } = await api.post(`/apps/${appId}/cta-forms/scan`);
      setState(s => ({ ...s, forms: data.forms }));
      toast.success(data.provisioned ? `${data.provisioned} new CTA button(s) got a form` : "Every CTA button already has a form");
    } catch (e) { toast.error(e.response?.data?.detail || "Scan failed"); }
    finally { setScanning(false); }
  }

  if (loading) return <div className="p-10 text-center text-sm text-[var(--mut)]"><Loader2 size={16} className="animate-spin inline" /></div>;

  return (
    <div className="space-y-5" data-testid="cta-forms-panel">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="overline mb-1 flex items-center gap-2"><FileText size={12} className="text-[var(--acc)]" /> Modal forms · {state.forms.length} CTA button{state.forms.length === 1 ? "" : "s"}</div>
          <h2 className="font-display text-2xl font-semibold tracking-tight">Every call-to-action opens a form</h2>
          <p className="text-sm text-[var(--mut)] mt-1 max-w-2xl">Fields were pre-set from this tenant's industry. Edits save instantly and go live on the site with no rebuild.</p>
        </div>
        <button data-testid="cta-forms-rescan-btn" onClick={rescan} disabled={scanning} className="btn-ghost text-sm flex items-center gap-2 disabled:opacity-60">
          <RefreshCw size={13} className={scanning ? "animate-spin" : ""} /> Scan for new buttons
        </button>
      </div>

      {state.forms.length === 0 && (
        <div className="card-surface p-10 text-center text-sm text-[var(--mut)]" data-testid="cta-forms-empty">
          No qualifying CTA buttons on this site yet. Add a button labelled like “Book a call” or “Request a quote” and it gets a form automatically.
        </div>
      )}

      <div className="space-y-3">
        {state.forms.map(f => (
          <div key={f.form_id} className="card-surface p-4" data-testid={`cta-form-card-${f.key}`}>
            <div className="flex flex-wrap items-center gap-3">
              <div className="min-w-0">
                <div className="font-display text-base">{f.label}</div>
                <div className="text-xs text-[var(--mut)]">{f.fields.length} field{f.fields.length === 1 ? "" : "s"} · submit “{f.submit_label}”</div>
              </div>
              <button data-testid={`cta-edit-form-${f.key}`} onClick={() => setOpen(o => o === f.form_id ? null : f.form_id)}
                className="btn-primary text-xs !py-1.5 !px-3 ml-auto">{open === f.form_id ? "Close editor" : "Edit Form"}</button>
            </div>
            {open === f.form_id && (
              <div className="mt-4 pt-4 border-t border-[var(--line)]">
                <CtaFormEditor appId={appId} form={f} simplified={state.simplified}
                  onSaved={(next) => setState(s => ({ ...s, forms: s.forms.map(x => x.form_id === next.form_id ? next : x) }))}
                  onClose={() => setOpen(null)} />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
