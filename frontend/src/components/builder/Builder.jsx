import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, ArrowUp, ArrowDown, Sparkles, Save, Type, LayoutGrid, DollarSign, Mail, BarChart3 } from "lucide-react";
import BlockPreview from "@/components/builder/BlockPreview";

const BLOCK_TEMPLATES = [
  { type: "hero", icon: Type, label: "Hero", defaults: { title: "Craft your story", subtitle: "A bold new intro.", cta: "Get Started", align: "left", accent: "#10B981" } },
  { type: "features", icon: LayoutGrid, label: "Features", defaults: { heading: "Why us", items: [{ title: "Fast", desc: "Sub-100ms." }, { title: "Secure", desc: "SOC2 aligned." }, { title: "Scalable", desc: "Ready for millions." }] } },
  { type: "pricing", icon: DollarSign, label: "Pricing", defaults: { heading: "Pricing", plans: [{ name: "Starter", price: "$29", features: ["Basic"] }, { name: "Pro", price: "$99", features: ["All features"] }] } },
  { type: "chart", icon: BarChart3, label: "Chart", defaults: { heading: "Growth", series: [{ m: "Jan", v: 12 }, { m: "Feb", v: 24 }, { m: "Mar", v: 48 }, { m: "Apr", v: 66 }] } },
  { type: "contact", icon: Mail, label: "Contact", defaults: { heading: "Contact", subtitle: "Talk to us.", email: "hello@example.com" } },
];

export default function Builder({ appId }) {
  const [blocks, setBlocks] = useState([]);
  const [selected, setSelected] = useState(null);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);

  useEffect(() => { load(); }, [appId]);

  async function load() {
    setLoading(true);
    try {
      const { data } = await api.get(`/apps/${appId}/page`);
      setBlocks(data.blocks || []);
      if (data.blocks?.length) setSelected(data.blocks[0].id);
    } catch { toast.error("Failed to load builder"); }
    finally { setLoading(false); }
  }

  function addBlock(tpl) {
    const id = `blk_${Math.random().toString(36).slice(2, 12)}`;
    const b = { id, type: tpl.type, props: JSON.parse(JSON.stringify(tpl.defaults)) };
    setBlocks([...blocks, b]);
    setSelected(id);
  }
  function removeBlock(id) {
    const next = blocks.filter(b => b.id !== id);
    setBlocks(next);
    if (selected === id) setSelected(next[0]?.id || null);
  }
  function move(id, dir) {
    const i = blocks.findIndex(b => b.id === id);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= blocks.length) return;
    const next = [...blocks];
    [next[i], next[j]] = [next[j], next[i]];
    setBlocks(next);
  }
  function updateProps(id, key, value) {
    setBlocks(blocks.map(b => b.id === id ? { ...b, props: { ...b.props, [key]: value } } : b));
  }
  async function save() {
    setSaving(true);
    try { await api.put(`/apps/${appId}/page`, { blocks }); toast.success("Page saved"); }
    catch { toast.error("Save failed"); }
    finally { setSaving(false); }
  }
  async function runAI() {
    if (!prompt || !selected) return;
    const block = blocks.find(b => b.id === selected);
    if (!block) return;
    setAiBusy(true);
    try {
      const { data } = await api.post(`/apps/${appId}/ai/edit`, { prompt, block });
      setBlocks(blocks.map(b => b.id === selected ? data : b));
      setPrompt("");
      toast.success("Claude updated the block");
    } catch (e) {
      toast.error(e.response?.data?.detail || "AI edit failed");
    } finally { setAiBusy(false); }
  }

  const sel = blocks.find(b => b.id === selected);

  if (loading) return <div className="overline text-center py-20">Loading builder…</div>;

  return (
    <div className="grid lg:grid-cols-[240px_1fr_320px] gap-4" data-testid="visual-builder">
      {/* Left: block palette + outline */}
      <aside className="space-y-4">
        <div className="card-surface p-3">
          <div className="overline mb-2 px-1">Add block</div>
          <div className="space-y-1">
            {BLOCK_TEMPLATES.map((t) => (
              <button key={t.type} data-testid={`builder-add-${t.type}-block-btn`} onClick={() => addBlock(t)}
                className="w-full flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-white/5 text-sm">
                <t.icon size={14} className="text-[var(--acc)]" /> {t.label}
                <Plus size={13} className="ml-auto text-[var(--mut)]" />
              </button>
            ))}
          </div>
        </div>

        <div className="card-surface p-3">
          <div className="overline mb-2 px-1">Page outline</div>
          <div className="space-y-1">
            {blocks.map((b, i) => (
              <div key={b.id}
                onClick={() => setSelected(b.id)}
                data-testid={`builder-outline-${b.type}-${i}`}
                className={`flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer ${selected === b.id ? "bg-[var(--acc)]/10 border border-[var(--acc)]/30" : "hover:bg-white/5"}`}>
                <span className="w-1.5 h-4 rounded" style={{ background: selected === b.id ? "var(--acc)" : "var(--line)" }} />
                <span className="text-sm capitalize flex-1 truncate">{b.type}</span>
                <button onClick={(e) => { e.stopPropagation(); move(b.id, -1); }} className="text-[var(--mut)] hover:text-white p-0.5"><ArrowUp size={12} /></button>
                <button onClick={(e) => { e.stopPropagation(); move(b.id, 1); }} className="text-[var(--mut)] hover:text-white p-0.5"><ArrowDown size={12} /></button>
                <button onClick={(e) => { e.stopPropagation(); removeBlock(b.id); }} className="text-[var(--mut)] hover:text-red-400 p-0.5"><Trash2 size={12} /></button>
              </div>
            ))}
            {blocks.length === 0 && <div className="text-xs text-[var(--mut)] px-2 py-4 text-center">Add your first block →</div>}
          </div>
        </div>
      </aside>

      {/* Center: preview */}
      <div className="min-h-[600px]">
        <div className="flex items-center justify-between mb-3">
          <div className="overline">Live preview</div>
          <button data-testid="builder-save-btn" onClick={save} disabled={saving}
            className="btn-primary text-sm flex items-center gap-2 !py-2 !px-4">
            <Save size={14} /> {saving ? "Saving…" : "Save page"}
          </button>
        </div>
        <div className="card-surface !p-0 overflow-hidden">
          <div className="max-h-[70vh] overflow-y-auto scrollbar-thin">
            {blocks.map((b) => (
              <div key={b.id} onClick={() => setSelected(b.id)}
                className={`relative ${selected === b.id ? "outline outline-2 outline-[var(--acc)]/50" : ""}`}>
                <BlockPreview block={b} />
              </div>
            ))}
            {blocks.length === 0 && <div className="p-20 text-center text-[var(--mut)]">Add a block from the palette to start building.</div>}
          </div>
        </div>
      </div>

      {/* Right: properties + AI */}
      <aside className="space-y-4">
        <div className="card-surface p-4">
          <div className="overline mb-3 flex items-center gap-2"><Sparkles size={12} className="text-[var(--acc)]" /> AI editor</div>
          <textarea data-testid="builder-ai-prompt-input" value={prompt} onChange={(e) => setPrompt(e.target.value)}
            placeholder={sel ? `Edit "${sel.type}" block… e.g. "Make it minimal and change CTA to 'Try free'"` : "Select a block first."}
            rows={3}
            className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm font-mono outline-none focus:border-[var(--acc)] resize-none" />
          <button data-testid="builder-ai-run-btn" onClick={runAI} disabled={!prompt || !sel || aiBusy}
            className="mt-3 w-full btn-primary flex items-center justify-center gap-2 !py-2 text-sm disabled:opacity-50">
            <Sparkles size={13} /> {aiBusy ? "Claude is editing…" : "Ask Claude"}
          </button>
        </div>

        {sel && (
          <div className="card-surface p-4">
            <div className="overline mb-3">{sel.type} properties</div>
            <div className="space-y-3 max-h-[40vh] overflow-y-auto scrollbar-thin pr-1">
              {Object.entries(sel.props).map(([k, v]) => (
                <div key={k}>
                  <div className="overline mb-1">{k}</div>
                  {typeof v === "string" ? (
                    <input value={v} onChange={(e) => updateProps(sel.id, k, e.target.value)}
                      data-testid={`prop-${k}-input`}
                      className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-md px-2 py-1.5 text-xs font-mono outline-none focus:border-[var(--acc)]" />
                  ) : (
                    <textarea value={JSON.stringify(v, null, 2)}
                      onChange={(e) => { try { updateProps(sel.id, k, JSON.parse(e.target.value)); } catch { /* ignore */ } }}
                      rows={4}
                      className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-md px-2 py-1.5 text-[11px] font-mono outline-none focus:border-[var(--acc)]" />
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}
