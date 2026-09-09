import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { GripVertical, Loader2, Plus, Trash2, X } from "lucide-react";
import api from "@/lib/api";

const TYPES = [["text", "Text line"], ["textarea", "Text box"], ["select", "Dropdown"], ["checkbox", "Checkbox"],
  ["date", "Date"], ["time", "Time dropdown"], ["phone", "Phone"], ["number", "Number"], ["email", "Email"]];
const DEFAULT_TIMES = ["Morning", "Afternoon", "Evening"];
const slug = (s) => String(s || "field").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 32) || "field";

/** Drag-and-drop form builder. `simplified` = client editor (no reordering, no removing required fields). */
export default function CtaFormEditor({ appId, form, simplified = false, onSaved, onClose }) {
  const [draft, setDraft] = useState(form);
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const dragIdx = useRef(null);
  const timer = useRef(null);

  useEffect(() => setDraft(form), [form?.form_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = (next) => {
    setDraft(next);
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      setSaving(true);
      try {
        const { data } = await api.put(`/apps/${appId}/cta-forms/${next.form_id}`, {
          title: next.title, subtitle: next.subtitle, submit_label: next.submit_label,
          success_title: next.success_title, success_message: next.success_message, fields: next.fields,
        });
        onSaved?.(data);
      } catch (e) { toast.error(e.response?.data?.detail || "Could not save that change"); }
      finally { setSaving(false); }
    }, 500);
  };

  const patchField = (i, upd) => save({ ...draft, fields: draft.fields.map((f, k) => k === i ? { ...f, ...upd } : f) });
  const removeField = (i) => {
    const f = draft.fields[i];
    if (f.name === "email" || f.type === "email") return toast.error("The email field is always required and cannot be removed");
    if (simplified && f.required) return toast.error("Ask your agency to remove a required field");
    save({ ...draft, fields: draft.fields.filter((_, k) => k !== i) });
  };
  const addField = (type) => {
    setAdding(false);
    const label = TYPES.find(t => t[0] === type)[1];
    let name = slug(`${type}_${draft.fields.length + 1}`);
    while (draft.fields.some(f => f.name === name)) name = `${name}_x`;
    save({ ...draft, fields: [...draft.fields, { name, label, type, required: false, placeholder: "", options: type === "select" || type === "time" ? DEFAULT_TIMES : [] }] });
  };
  const drop = (to) => {
    const from = dragIdx.current;
    dragIdx.current = null;
    if (from == null || from === to || simplified) return;
    const fields = [...draft.fields];
    fields.splice(to, 0, fields.splice(from, 1)[0]);
    save({ ...draft, fields });
  };

  const canDrag = !simplified;
  const busy = useMemo(() => saving, [saving]);

  return (
    <div className="space-y-4" data-testid={`cta-form-editor-${draft.form_id}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="overline mb-1">Form on “{draft.label}”</div>
          <div className="font-display text-lg">Modal form fields</div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-[var(--mut)] flex items-center gap-1" data-testid="cta-form-save-state">
            {busy ? <><Loader2 size={11} className="animate-spin" /> Saving…</> : "Saved · live on the site"}
          </span>
          {onClose && <button data-testid="cta-form-editor-close" onClick={onClose} className="p-1.5 rounded-md hover:bg-white/10 text-[var(--mut)]"><X size={14} /></button>}
        </div>
      </div>

      <div className="grid sm:grid-cols-2 gap-3">
        <label className="block"><span className="overline block mb-1">Modal title</span>
          <input data-testid="cta-form-title-input" value={draft.title || ""} onChange={e => save({ ...draft, title: e.target.value })}
            className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--acc)]" /></label>
        <label className="block"><span className="overline block mb-1">Submit button label</span>
          <input data-testid="cta-form-submit-label-input" value={draft.submit_label || ""} onChange={e => save({ ...draft, submit_label: e.target.value })}
            className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--acc)]" /></label>
        <label className="block sm:col-span-2"><span className="overline block mb-1">Confirmation message</span>
          <input data-testid="cta-form-success-input" value={draft.success_message || ""} onChange={e => save({ ...draft, success_message: e.target.value })}
            className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--acc)]" /></label>
      </div>

      <div className="space-y-2">
        {draft.fields.map((f, i) => {
          const locked = f.name === "email" || f.type === "email";
          return (
            <div key={f.name} data-testid={`cta-field-row-${f.name}`}
              draggable={canDrag} onDragStart={() => { dragIdx.current = i; }} onDragOver={e => e.preventDefault()} onDrop={() => drop(i)}
              className="card-surface !p-3 flex items-start gap-2">
              {canDrag && <button data-testid={`cta-field-drag-${f.name}`} className="mt-2 text-[var(--dim)] cursor-grab active:cursor-grabbing"><GripVertical size={14} /></button>}
              <div className="flex-1 grid sm:grid-cols-2 gap-2 min-w-0">
                <input data-testid={`cta-field-label-${f.name}`} value={f.label} onChange={e => patchField(i, { label: e.target.value })}
                  placeholder="Field label" className="bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2.5 py-1.5 text-sm outline-none focus:border-[var(--acc)]" />
                <input data-testid={`cta-field-placeholder-${f.name}`} value={f.placeholder || ""} onChange={e => patchField(i, { placeholder: e.target.value })}
                  placeholder="Placeholder text" className="bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2.5 py-1.5 text-sm outline-none focus:border-[var(--acc)]" />
                {(f.type === "select" || f.type === "time" || f.type === "toggle") && (
                  <input data-testid={`cta-field-options-${f.name}`} value={(f.options || []).join(", ")} onChange={e => patchField(i, { options: e.target.value.split(",").map(s => s.trim()).filter(Boolean) })}
                    placeholder="Option one, Option two" className="sm:col-span-2 bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2.5 py-1.5 text-sm outline-none focus:border-[var(--acc)]" />
                )}
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="chip !text-[10px]">{TYPES.find(t => t[0] === f.type)?.[1] || f.type}</span>
                <button data-testid={`cta-field-required-${f.name}`} disabled={locked} onClick={() => patchField(i, { required: !f.required })}
                  className={`chip cursor-pointer !text-[10px] disabled:opacity-60 ${f.required ? "chip-active" : ""}`}>{f.required ? "Required" : "Optional"}</button>
                <button data-testid={`cta-field-remove-${f.name}`} disabled={locked} onClick={() => removeField(i)}
                  className="p-1.5 rounded-md text-[var(--dim)] hover:text-red-300 hover:bg-white/10 disabled:opacity-30"><Trash2 size={13} /></button>
              </div>
            </div>
          );
        })}
      </div>

      <div>
        <button data-testid="cta-add-field-btn" onClick={() => setAdding(v => !v)} className="btn-ghost text-sm flex items-center gap-1.5"><Plus size={14} /> Add a Field</button>
        {adding && (
          <div data-testid="cta-add-field-menu" className="card-surface !p-2 mt-2 grid grid-cols-2 sm:grid-cols-3 gap-1.5 max-w-lg">
            {TYPES.filter(([t]) => t !== "email").map(([t, l]) => (
              <button key={t} data-testid={`cta-add-field-${t}`} onClick={() => addField(t)}
                className="text-left px-3 py-2 rounded-lg text-sm hover:bg-white/5 border border-[var(--line)]">{l}</button>
            ))}
          </div>
        )}
      </div>
      {simplified && <p className="text-[11px] text-[var(--mut)]">You can rename fields, change placeholders, add fields and switch optional fields on or off. Where submissions are delivered is managed by your agency.</p>}
    </div>
  );
}
