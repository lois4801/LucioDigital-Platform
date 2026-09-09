import { createContext, useContext, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X, Check, Loader2 } from "lucide-react";
import { themeVars } from "@/lib/theme";

/* Any CTA whose label implies the visitor wants to act or make contact gets a modal form. */
export const CTA_PATTERN = /\b(book|schedule|request|quote|estimate|contact|apply|enquir|inquir|reserve|reservation|consult|sign\s?up|get\s?started|learn\s?more|join|register|appointment|tour|call|start|talk|demo|availability|valuation|audit|in\s?touch|message|hire|order|subscribe|visit|trial|walkthrough|showing|assessment|plan|speak)\b/i;
export const isCtaLabel = (label) => CTA_PATTERN.test(String(label || "").trim());
export const ctaKey = (label) => String(label || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60);

/** { forms: {key: form}, open(label), edit(label) } — provided by the public site and the builder. */
export const CtaCtx = createContext(null);
export const useCta = () => useContext(CtaCtx);

const Field = ({ f, value, onChange }) => {
  const base = "w-full bg-[var(--tsf)] border border-[var(--tbd)] rounded-[calc(var(--tr)/2)] px-3 py-2.5 text-sm text-[var(--thead)] outline-none focus:border-[var(--tp)]";
  const common = { id: f.name, name: f.name, required: !!f.required, "data-testid": `cta-field-${f.name}`, value: value ?? "", onChange: (e) => onChange(f.name, e.target.value), className: base };
  if (f.type === "textarea") return <textarea rows={4} placeholder={f.placeholder || ""} {...common} />;
  if (f.type === "select" || f.type === "time") return (
    <select {...common}><option value="">{f.placeholder || "Select an option"}</option>
      {(f.options || []).map(o => <option key={o} value={o}>{o}</option>)}</select>
  );
  if (f.type === "toggle") return (
    <div className="flex gap-2" data-testid={`cta-field-${f.name}`}>
      {(f.options || []).map(o => (
        <button type="button" key={o} onClick={() => onChange(f.name, o)}
          className={`flex-1 px-3 py-2.5 rounded-[calc(var(--tr)/2)] border text-sm ${value === o ? "border-[var(--tp)] bg-[var(--tp)]/12 text-[var(--thead)]" : "border-[var(--tbd)] text-[var(--tbody)]"}`}>{o}</button>
      ))}
    </div>
  );
  if (f.type === "checkbox") return (
    <label className="flex items-center gap-2 text-sm text-[var(--tbody)]">
      <input type="checkbox" data-testid={`cta-field-${f.name}`} checked={value === true || value === "true"} required={!!f.required}
        onChange={(e) => onChange(f.name, e.target.checked)} className="w-4 h-4 accent-[var(--tp)]" />
      {f.placeholder || f.label}
    </label>
  );
  const type = f.type === "phone" ? "tel" : ["email", "date", "number"].includes(f.type) ? f.type : "text";
  return <input type={type} placeholder={f.placeholder || ""} {...common} />;
};

export default function CtaFormModal({ form, theme, onClose, onSubmit }) {
  const [values, setValues] = useState({});
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    const esc = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", esc);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", esc); document.body.style.overflow = prev; };
  }, [onClose]);

  const set = (k, v) => setValues(s => ({ ...s, [k]: v }));

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try { await onSubmit(values); setDone(true); }
    catch (e2) { setErr(e2?.response?.data?.detail || "Something went wrong — please try again."); }
    finally { setBusy(false); }
  }

  return createPortal(
    <div data-testid="cta-modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
      style={themeVars(theme)}
      className="fixed inset-0 z-[90] flex items-start sm:items-center justify-center p-4 sm:p-6 overflow-y-auto bg-black/70 backdrop-blur-sm">
      <div data-testid="cta-modal" role="dialog" aria-modal="true" aria-label={form.title}
        className="relative w-full max-w-lg my-auto rounded-[var(--tr)] border border-[var(--tbd)] shadow-[0_40px_120px_-40px_rgba(0,0,0,.7)]"
        style={{ background: `var(--tbg, ${theme?.bg || "#0A0A0F"})`, color: `var(--tbody, ${theme?.mode === "light" ? "#333333" : "#E5E5E5"})`, fontFamily: "var(--tfb)" }}>
        <button data-testid="cta-modal-close" aria-label="Close" onClick={onClose}
          className="absolute top-3 right-3 w-9 h-9 rounded-full border border-[var(--tbd)] flex items-center justify-center text-[var(--tbody)] hover:bg-[var(--tp)]/10">
          <X size={16} />
        </button>
        {done ? (
          <div className="p-10 text-center" data-testid="cta-modal-success">
            <div className="w-12 h-12 rounded-full mx-auto mb-4 flex items-center justify-center" style={{ background: `var(--tp, ${theme?.primary || "#F97316"})` }}><Check size={22} className="text-white" /></div>
            <div className="text-xl mb-2" style={{ fontFamily: "var(--tfh)", color: "var(--thead)" }}>{form.success_title || "Thank you!"}</div>
            <p className="text-sm">{form.success_message || "Thank you! We'll be in touch within 24 hours."}</p>
            <button data-testid="cta-modal-done" onClick={onClose} className="mt-6 px-5 py-2.5 rounded-full text-sm font-semibold border border-[var(--tbd)] text-[var(--thead)]">Close</button>
          </div>
        ) : (
          <form onSubmit={submit} className="p-6 sm:p-8" data-testid="cta-modal-form">
            <div className="text-2xl pr-10" style={{ fontFamily: "var(--tfh)", color: "var(--thead)" }} data-testid="cta-modal-title">{form.title}</div>
            {form.subtitle && <p className="text-sm mt-2">{form.subtitle}</p>}
            <div className="mt-6 space-y-4">
              {(form.fields || []).map(f => (
                <div key={f.name}>
                  {f.type !== "checkbox" && (
                    <label htmlFor={f.name} className="block text-xs uppercase tracking-wider mb-1.5" style={{ color: "var(--tmut)" }}>
                      {f.label}{f.required ? " *" : ""}
                    </label>
                  )}
                  <Field f={f} value={values[f.name]} onChange={set} />
                </div>
              ))}
            </div>
            {err && <div data-testid="cta-modal-error" className="mt-4 text-sm text-red-400">{err}</div>}
            <button type="submit" data-testid="cta-modal-submit" disabled={busy}
              className="mt-6 w-full px-6 py-3.5 rounded-full font-semibold text-sm text-white disabled:opacity-60 flex items-center justify-center gap-2"
              style={{ background: `var(--tp, ${theme?.primary || "#F97316"})` }}>
              {busy ? <><Loader2 size={15} className="animate-spin" /> Sending…</> : (form.submit_label || "Send request")}
            </button>
            <p className="text-[11px] mt-3 text-center" style={{ color: "var(--tmut)" }}>We reply to every enquiry within one business day.</p>
          </form>
        )}
      </div>
    </div>, document.body);
}
