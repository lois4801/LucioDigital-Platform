import { useEffect, useRef, useState } from "react";

export const FONTS = [
  { label: "Inter", css: "'Inter', sans-serif" },
  { label: "Poppins", css: "'Poppins', sans-serif" },
  { label: "Roboto", css: "'Roboto', sans-serif" },
  { label: "Playfair Display", css: "'Playfair Display', serif" },
  { label: "Space Grotesk", css: "'Space Grotesk', sans-serif" },
  { label: "DM Sans", css: "'DM Sans', sans-serif" },
  { label: "Sora", css: "'Sora', sans-serif" },
  { label: "Outfit", css: "'Outfit', sans-serif" },
];

const FONT_HREF = "https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Inter:wght@400;600;700&family=Outfit:wght@400;600;700&family=Playfair+Display:wght@400;600;700&family=Poppins:wght@400;600;700&family=Roboto:wght@400;500;700&family=Sora:wght@400;600;700&family=Space+Grotesk:wght@400;600;700&display=swap";

if (typeof document !== "undefined" && !document.getElementById("inline-text-fonts")) {
  const l = document.createElement("link");
  l.id = "inline-text-fonts"; l.rel = "stylesheet"; l.href = FONT_HREF;
  document.head.appendChild(l);
}

function caretToEnd(el) {
  const r = document.createRange(); r.selectNodeContents(el); r.collapse(false);
  const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
}

function InlineToolbar({ font, color, onChange }) {
  return (
    <span data-testid="inline-text-toolbar" contentEditable={false}
      onClick={e => e.stopPropagation()}
      className="absolute z-50 bottom-full left-0 mb-1.5 flex items-center gap-1.5 px-2 py-1.5 rounded-xl bg-[#0B0F17]/95 backdrop-blur border border-white/15 shadow-2xl whitespace-nowrap normal-case tracking-normal">
      <select data-testid="inline-font-select" value={font || ""} onChange={e => onChange({ font: e.target.value, color })}
        className="bg-[#141B26] text-white text-[11px] rounded-md px-1.5 py-1 border border-white/10 outline-none cursor-pointer">
        <option value="">Default font</option>
        {FONTS.map(f => <option key={f.label} value={f.css}>{f.label}</option>)}
      </select>
      <input data-testid="inline-color-input" type="color" value={color || "#ffffff"} onChange={e => onChange({ font, color: e.target.value })}
        title="Text colour" className="w-7 h-6 rounded-md bg-transparent border border-white/10 cursor-pointer p-0" />
      {(font || color) && (
        <button data-testid="inline-style-clear-btn" title="Clear formatting" onClick={() => onChange({ font: "", color: "" })}
          className="text-[10px] text-white/60 hover:text-white px-1">Clear</button>
      )}
    </span>
  );
}

// Inline click-to-edit text with per-element font + colour toolbar and Ctrl+Z undo.
export function EditableText({ as: Tag = "span", value, className, style, editable, font, color, onCommit, onStyleChange, testid, singleLine = true, wrapClassName }) {
  const ref = useRef(null);
  const wrap = useRef(null);
  const [open, setOpen] = useState(false);
  const undo = useRef([]);

  useEffect(() => { if (ref.current && ref.current.innerText !== value) ref.current.innerText = value; }, [value, editable]);
  useEffect(() => {
    if (!open) return;
    const h = (e) => { if (wrap.current && !wrap.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);

  const textStyle = { ...(style || {}), ...(font ? { fontFamily: font } : {}), ...(color ? { color } : {}) };
  if (!editable) return <Tag className={className} style={textStyle} data-testid={testid}>{value}</Tag>;

  return (
    <span ref={wrap} className={`relative inline-block max-w-full ${wrapClassName || ""}`}>
      <Tag ref={ref} data-testid={testid} contentEditable suppressContentEditableWarning style={textStyle}
        title="Click to edit · Ctrl+Z to undo"
        className={`${className || ""} outline-none rounded-sm cursor-text hover:ring-1 hover:ring-[var(--acc)]/50 focus:ring-2 focus:ring-[var(--acc)] transition-shadow`}
        onFocus={() => { undo.current = [value]; setOpen(true); }}
        onClick={e => { if (!e.target.closest("button")) e.stopPropagation(); }}
        onInput={() => {
          const t = ref.current.innerText;
          const st = undo.current;
          if (st[st.length - 1] !== t) st.push(t);
          if (st.length > 60) st.shift();
        }}
        onKeyDown={e => {
          if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) {
            e.preventDefault();
            e.stopPropagation();
            const st = undo.current;
            if (st.length > 1) st.pop();
            ref.current.innerText = st[st.length - 1] ?? value;
            caretToEnd(ref.current);
            return;
          }
          if (e.key === "Enter" && singleLine) { e.preventDefault(); ref.current.blur(); }
          if (e.key === "Escape") { ref.current.innerText = value; ref.current.blur(); }
        }}
        onBlur={() => {
          const v = ref.current.innerText.trim();
          if (!v || v === value || undo.current.length < 2) { ref.current.innerText = value; return; }
          onCommit(v);
        }}>
        {value}
      </Tag>
      {open && onStyleChange && <InlineToolbar font={font} color={color} onChange={onStyleChange} />}
    </span>
  );
}
