import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, GripVertical, Sparkles, Save, Type, LayoutGrid, DollarSign, Mail, BarChart3 } from "lucide-react";
import { DndContext, closestCenter, PointerSensor, KeyboardSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import BlockPreview from "@/components/builder/BlockPreview";

const BLOCK_TEMPLATES = [
  { type: "hero", icon: Type, label: "Hero", defaults: { title: "Craft your story", subtitle: "A bold new intro.", cta: "Get Started", align: "left", accent: "#10B981" } },
  { type: "features", icon: LayoutGrid, label: "Features", defaults: { heading: "Why us", items: [{ title: "Fast", desc: "Sub-100ms." }, { title: "Secure", desc: "SOC2 aligned." }, { title: "Scalable", desc: "Ready for millions." }] } },
  { type: "pricing", icon: DollarSign, label: "Pricing", defaults: { heading: "Pricing", plans: [{ name: "Starter", price: "$29", features: ["Basic"] }, { name: "Pro", price: "$99", features: ["All features"] }] } },
  { type: "chart", icon: BarChart3, label: "Chart", defaults: { heading: "Growth", series: [{ m: "Jan", v: 12 }, { m: "Feb", v: 24 }, { m: "Mar", v: 48 }, { m: "Apr", v: 66 }] } },
  { type: "contact", icon: Mail, label: "Contact", defaults: { heading: "Contact", subtitle: "Talk to us.", email: "hello@example.com" } },
];

function OutlineItem({ block, index, selected, onSelect, onRemove }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: block.id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.6 : 1 };
  return (
    <div ref={setNodeRef} style={style} onClick={onSelect} data-testid={`builder-outline-${block.type}-${index}`}
      className={`flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer select-none ${selected ? "bg-[var(--acc)]/10 border border-[var(--acc)]/30" : "hover:bg-white/5 border border-transparent"} ${isDragging ? "shadow-2xl ring-1 ring-[var(--acc)]/50 bg-[var(--card-hov)]" : ""}`}>
      <button {...attributes} {...listeners} data-testid={`builder-drag-handle-${index}`} onClick={e => e.stopPropagation()}
        className="text-[var(--dim)] hover:text-white cursor-grab active:cursor-grabbing p-0.5 touch-none" aria-label="Drag to reorder">
        <GripVertical size={14} />
      </button>
      <span className="text-sm capitalize flex-1 truncate">{block.type}</span>
      <span className="font-mono text-[10px] text-[var(--dim)]">{index + 1}</span>
      <button onClick={e => { e.stopPropagation(); onRemove(); }} className="text-[var(--mut)] hover:text-red-400 p-0.5"><Trash2 size={12} /></button>
    </div>
  );
}

function CanvasItem({ block, selected, onSelect }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: block.id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };
  return (
    <div ref={setNodeRef} style={style} onClick={onSelect} className={`relative group ${selected ? "outline outline-2 outline-[var(--acc)]/50" : ""}`}>
      <button {...attributes} {...listeners} onClick={e => e.stopPropagation()}
        className="absolute left-2 top-2 z-10 w-8 h-8 rounded-lg bg-black/60 backdrop-blur border border-white/10 flex items-center justify-center text-white/70 opacity-0 group-hover:opacity-100 cursor-grab active:cursor-grabbing touch-none transition-opacity">
        <GripVertical size={14} />
      </button>
      <BlockPreview block={block} />
    </div>
  );
}

export default function Builder({ appId }) {
  const [blocks, setBlocks] = useState([]);
  const [selected, setSelected] = useState(null);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }), useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }));

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
    setBlocks([...blocks, { id, type: tpl.type, props: JSON.parse(JSON.stringify(tpl.defaults)) }]);
    setSelected(id);
  }
  function removeBlock(id) {
    const next = blocks.filter(b => b.id !== id);
    setBlocks(next);
    if (selected === id) setSelected(next[0]?.id || null);
  }
  function onDragEnd({ active, over }) {
    if (!over || active.id === over.id) return;
    const from = blocks.findIndex(b => b.id === active.id), to = blocks.findIndex(b => b.id === over.id);
    setBlocks(arrayMove(blocks, from, to));
    setSelected(active.id);
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
    } catch (e) { toast.error(e.response?.data?.detail || "AI edit failed"); }
    finally { setAiBusy(false); }
  }

  const sel = blocks.find(b => b.id === selected);
  const ids = blocks.map(b => b.id);
  if (loading) return <div className="overline text-center py-20">Loading builder…</div>;

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
      <div className="grid lg:grid-cols-[240px_1fr_320px] gap-4" data-testid="visual-builder">
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
            <div className="overline mb-2 px-1 flex items-center justify-between">Page outline <span className="text-[9px] normal-case tracking-normal text-[var(--dim)]">drag to reorder</span></div>
            <SortableContext items={ids} strategy={verticalListSortingStrategy}>
              <div className="space-y-1" data-testid="builder-outline-list">
                {blocks.map((b, i) => (
                  <OutlineItem key={b.id} block={b} index={i} selected={selected === b.id} onSelect={() => setSelected(b.id)} onRemove={() => removeBlock(b.id)} />
                ))}
                {blocks.length === 0 && <div className="text-xs text-[var(--mut)] px-2 py-4 text-center">Add your first block →</div>}
              </div>
            </SortableContext>
          </div>
        </aside>

        <div className="min-h-[600px]">
          <div className="flex items-center justify-between mb-3">
            <div className="overline">Live preview</div>
            <button data-testid="builder-save-btn" onClick={save} disabled={saving} className="btn-primary text-sm flex items-center gap-2 !py-2 !px-4">
              <Save size={14} /> {saving ? "Saving…" : "Save page"}
            </button>
          </div>
          <div className="card-surface !p-0 overflow-hidden">
            <div className="max-h-[70vh] overflow-y-auto scrollbar-thin">
              <SortableContext items={ids} strategy={verticalListSortingStrategy}>
                {blocks.map((b) => <CanvasItem key={b.id} block={b} selected={selected === b.id} onSelect={() => setSelected(b.id)} />)}
              </SortableContext>
              {blocks.length === 0 && <div className="p-20 text-center text-[var(--mut)]">Add a block from the palette to start building.</div>}
            </div>
          </div>
        </div>

        <aside className="space-y-4">
          <div className="card-surface p-4">
            <div className="overline mb-3 flex items-center gap-2"><Sparkles size={12} className="text-[var(--acc)]" /> AI editor</div>
            <textarea data-testid="builder-ai-prompt-input" value={prompt} onChange={(e) => setPrompt(e.target.value)}
              placeholder={sel ? `Edit "${sel.type}" block… e.g. "Make it minimal and change CTA to 'Try free'"` : "Select a block first."} rows={3}
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
                      <input value={v} onChange={(e) => updateProps(sel.id, k, e.target.value)} data-testid={`prop-${k}-input`}
                        className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-md px-2 py-1.5 text-xs font-mono outline-none focus:border-[var(--acc)]" />
                    ) : (
                      <textarea value={JSON.stringify(v, null, 2)} rows={4}
                        onChange={(e) => { try { updateProps(sel.id, k, JSON.parse(e.target.value)); } catch { /* ignore */ } }}
                        className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-md px-2 py-1.5 text-[11px] font-mono outline-none focus:border-[var(--acc)]" />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>
    </DndContext>
  );
}
