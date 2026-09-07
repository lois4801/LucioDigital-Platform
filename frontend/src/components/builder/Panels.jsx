import { FONTS } from "@/lib/theme";
import { Sun, Moon } from "lucide-react";

const SWATCHES = [["#F97316", "#14B8A6"], ["#EA580C", "#0EA5E9"], ["#F59E0B", "#10B981"], ["#FB7185", "#6366F1"], ["#0F172A", "#F97316"], ["#7C3AED", "#22D3EE"]];

export function ThemePanel({ theme, onChange }) {
  const set = (k, v) => onChange({ ...theme, [k]: v });
  const Color = ({ k, label }) => (
    <label className="flex items-center justify-between text-xs">
      <span className="text-[var(--mut)]">{label}</span>
      <span className="flex items-center gap-2 font-mono"><input data-testid={`theme-${k}-input`} type="color" value={theme[k]} onChange={e => set(k, e.target.value)} className="w-6 h-6 rounded border-0 bg-transparent cursor-pointer" />{theme[k]}</span>
    </label>
  );
  return (
    <div className="card-surface p-4 space-y-3" data-testid="theme-panel">
      <div className="overline">Design theme</div>
      <div className="flex gap-1.5">{SWATCHES.map(([p, s], i) => (
        <button key={i} data-testid={`theme-swatch-${i}`} onClick={() => onChange({ ...theme, primary: p, secondary: s })} className={`w-8 h-8 rounded-full border-2 ${theme.primary === p ? "border-white" : "border-transparent"}`} style={{ background: `linear-gradient(135deg, ${p} 50%, ${s} 50%)` }} />
      ))}</div>
      <Color k="primary" label="Primary" /><Color k="secondary" label="Secondary" />
      <div className="flex items-center justify-between text-xs"><span className="text-[var(--mut)]">Mode</span>
        <div className="flex rounded-full border border-[var(--line)] overflow-hidden">
          {[["light", Sun], ["dark", Moon]].map(([m, I]) => <button key={m} data-testid={`theme-mode-${m}`} onClick={() => set("mode", m)} className={`px-3 py-1 flex items-center gap-1 ${theme.mode === m ? "bg-[var(--acc)]/15 text-[var(--acc)]" : "text-[var(--mut)]"}`}><I size={11} /> {m}</button>)}
        </div></div>
      {[["font_heading", "Heading font"], ["font_body", "Body font"]].map(([k, l]) => (
        <label key={k} className="flex items-center justify-between text-xs"><span className="text-[var(--mut)]">{l}</span>
          <select data-testid={`theme-${k}-select`} value={theme[k]} onChange={e => set(k, e.target.value)} className="bg-[var(--bg-2)] border border-[var(--line)] rounded-md px-2 py-1 text-xs outline-none">{FONTS.map(f => <option key={f}>{f}</option>)}</select></label>
      ))}
      <label className="block text-xs"><div className="flex justify-between text-[var(--mut)]"><span>Corner radius</span><span className="font-mono">{theme.radius}px</span></div>
        <input data-testid="theme-radius-input" type="range" min={0} max={32} value={theme.radius} onChange={e => set("radius", Number(e.target.value))} className="w-full accent-[var(--acc)]" /></label>
    </div>
  );
}

export function StylePanel({ block, onChange }) {
  const s = block.style || { bg: "default", align: "left", padding: "md" };
  const set = (k, v) => onChange({ ...s, [k]: v });
  const Seg = ({ k, opts }) => (
    <div className="flex rounded-lg border border-[var(--line)] overflow-hidden text-[11px]">
      {opts.map(o => <button key={o} data-testid={`style-${k}-${o}`} onClick={() => set(k, o)} className={`flex-1 py-1.5 capitalize ${s[k] === o ? "bg-[var(--acc)]/15 text-[var(--acc)]" : "text-[var(--mut)] hover:text-white"}`}>{o}</button>)}
    </div>
  );
  return (
    <div className="space-y-2" data-testid="style-panel">
      <div className="overline">Section style</div>
      <div><div className="text-[10px] text-[var(--dim)] mb-1">Background</div><Seg k="bg" opts={["default", "muted", "accent", "dark"]} /></div>
      <div className="grid grid-cols-2 gap-2">
        <div><div className="text-[10px] text-[var(--dim)] mb-1">Align</div><Seg k="align" opts={["left", "center"]} /></div>
        <div><div className="text-[10px] text-[var(--dim)] mb-1">Padding</div><Seg k="padding" opts={["sm", "md", "lg"]} /></div>
      </div>
      {block.type === "hero" && <div><div className="text-[10px] text-[var(--dim)] mb-1">Hero variant</div>
        <div className="flex rounded-lg border border-[var(--line)] overflow-hidden text-[11px]">{["left", "centered", "split"].map(o => <button key={o} data-testid={`hero-variant-${o}`} onClick={() => onChange(s, { variant: o })} className={`flex-1 py-1.5 capitalize ${block.props.variant === o ? "bg-[var(--acc)]/15 text-[var(--acc)]" : "text-[var(--mut)]"}`}>{o}</button>)}</div></div>}
    </div>
  );
}
