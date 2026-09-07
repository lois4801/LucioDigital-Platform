import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, GripVertical, Sparkles, Save, Type, LayoutGrid, DollarSign, Mail, BarChart3, Navigation, Quote, Images, Film, HelpCircle, Megaphone, PanelBottom, Award, Wand2, Monitor, Smartphone, Tablet, Eye, Loader2, Database } from "lucide-react";
import { DndContext, closestCenter, PointerSensor, KeyboardSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import BlockPreview from "@/components/builder/BlockPreview";
import EffectWrap from "@/components/builder/EffectWrap";
import CursorTrail from "@/components/CursorTrail";
import { PagesBar, GenerateSiteDialog } from "@/components/builder/PagesBar";
import { ThemePanel, StylePanel } from "@/components/builder/Panels";
import { DEFAULT_THEME, themeVars, loadFonts } from "@/lib/theme";

const IMG = "https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=1200&q=80";
const BLOCK_TEMPLATES = [
  { type: "navbar", icon: Navigation, label: "Navbar", defaults: { brand: "Brand", links: [{ label: "Home", href: "/" }, { label: "About", href: "/about" }, { label: "Pricing", href: "/pricing" }], cta: "Get started" } },
  { type: "hero", icon: Type, label: "Hero", defaults: { variant: "centered", badge: "New", title: "Craft your story", subtitle: "A bold, minimal introduction to what you do.", cta: "Get started", cta2: "Learn more", image: IMG } },
  { type: "logos", icon: Award, label: "Logo cloud", defaults: { heading: "Trusted by teams at", names: ["Acme", "Globex", "Umbrella", "Initech", "Hooli"] } },
  { type: "features", icon: LayoutGrid, label: "Features", defaults: { heading: "Why teams choose us", subheading: "Everything you need, nothing you don't.", items: [{ title: "Fast", desc: "Sub-100ms.", icon: "Zap" }, { title: "Secure", desc: "SOC2 aligned.", icon: "Shield" }, { title: "Scalable", desc: "Ready for millions.", icon: "Rocket" }] } },
  { type: "gallery", icon: Images, label: "Gallery", defaults: { heading: "Our work", images: [IMG, "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=1200&q=80", "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=1200&q=80"] } },
  { type: "video", icon: Film, label: "Video", defaults: { heading: "See it in action", url: "", caption: "A 60-second tour." } },
  { type: "testimonials", icon: Quote, label: "Testimonials", defaults: { heading: "Loved by customers", items: [{ quote: "Changed how we work.", name: "Ana Lopez", role: "COO, Acme" }, { quote: "Beautiful and fast.", name: "Sam Chen", role: "Founder, Globex" }, { quote: "Support is superb.", name: "Priya N.", role: "Ops lead" }] } },
  { type: "pricing", icon: DollarSign, label: "Pricing", defaults: { heading: "Simple pricing", plans: [{ name: "Starter", price: "$29", period: "mo", features: ["1 project", "Email support"] }, { name: "Pro", price: "$99", period: "mo", features: ["10 projects", "Priority support"], highlight: true }, { name: "Scale", price: "$299", period: "mo", features: ["Unlimited", "SLA"] }] } },
  { type: "faq", icon: HelpCircle, label: "FAQ", defaults: { heading: "Questions & answers", items: [{ q: "How do I get started?", a: "Sign up and follow the 2-minute setup." }, { q: "Can I cancel anytime?", a: "Yes, no lock-in." }] } },
  { type: "chart", icon: BarChart3, label: "Chart", defaults: { heading: "Growth", series: [{ m: "Jan", v: 12 }, { m: "Feb", v: 24 }, { m: "Mar", v: 48 }, { m: "Apr", v: 66 }] } },
  { type: "cta", icon: Megaphone, label: "Call to action", defaults: { title: "Ready to get started?", subtitle: "Join thousands of happy customers.", cta: "Start free" } },
  { type: "contact", icon: Mail, label: "Contact", defaults: { heading: "Contact us", subtitle: "We reply within a day.", email: "hello@example.com", phone: "+1 (555) 010-2030", address: "100 King St W, Toronto" } },
  { type: "collection_list", icon: Database, label: "Collection list", defaults: { heading: "Latest from the blog", collection: "blog", limit: 6 } },
  { type: "footer", icon: PanelBottom, label: "Footer", defaults: { brand: "Brand", tagline: "Made with care.", columns: [{ title: "Product", links: ["Features", "Pricing"] }, { title: "Company", links: ["About", "Contact"] }, { title: "Legal", links: ["Privacy", "Terms"] }] } },
];

function OutlineItem({ block, index, selected, onSelect, onRemove }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: block.id });
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.6 : 1 }} onClick={onSelect} data-testid={`builder-outline-${block.type}-${index}`}
      className={`flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer select-none ${selected ? "bg-[var(--acc)]/10 border border-[var(--acc)]/30" : "hover:bg-white/5 border border-transparent"}`}>
      <button {...attributes} {...listeners} data-testid={`builder-drag-handle-${index}`} onClick={e => e.stopPropagation()} className="text-[var(--dim)] hover:text-white cursor-grab active:cursor-grabbing p-0.5 touch-none"><GripVertical size={14} /></button>
      <span className="text-sm capitalize flex-1 truncate">{block.type}</span>
      <button onClick={e => { e.stopPropagation(); onRemove(); }} className="text-[var(--mut)] hover:text-red-400 p-0.5"><Trash2 size={12} /></button>
    </div>
  );
}

function CanvasItem({ block, selected, onSelect, onEdit, onNavigate, collections, motionOn }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: block.id });
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 }} onClick={onSelect} className={`relative group ${selected ? "outline outline-2 outline-[var(--tp)]" : "hover:outline hover:outline-1 hover:outline-[var(--tp)]/40"}`}>
      <button {...attributes} {...listeners} onClick={e => e.stopPropagation()} className="absolute left-2 top-2 z-10 w-8 h-8 rounded-lg bg-black/70 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 cursor-grab active:cursor-grabbing touch-none transition-opacity"><GripVertical size={14} /></button>
      <span className="absolute right-2 top-2 z-10 text-[10px] font-mono uppercase bg-black/70 text-white px-2 py-0.5 rounded opacity-0 group-hover:opacity-100">{block.type}</span>
      <EffectWrap effects={block.style?.effects} motionOn={motionOn}><BlockPreview block={block} onEdit={onEdit} onNavigate={onNavigate} collections={collections} /></EffectWrap>
    </div>
  );
}

function setPath(obj, path, value) {
  const keys = path.split("."); const out = Array.isArray(obj) ? [...obj] : { ...obj };
  let cur = out;
  keys.forEach((k, i) => { if (i === keys.length - 1) cur[k] = value; else { cur[k] = Array.isArray(cur[k]) ? [...cur[k]] : { ...cur[k] }; cur = cur[k]; } });
  return out;
}

export default function Builder({ appId, appDoc }) {
  const [pages, setPages] = useState([]);
  const [pageId, setPageId] = useState(null);
  const [blocks, setBlocks] = useState([]);
  const [theme, setTheme] = useState(DEFAULT_THEME);
  const [selected, setSelected] = useState(null);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [genOpen, setGenOpen] = useState(false);
  const [device, setDevice] = useState("desktop");
  const [dirty, setDirty] = useState(false);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }), useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }));

  useEffect(() => { load(); }, [appId]);
  useEffect(() => { loadFonts(theme); }, [theme]);

  async function load(keepPage) {
    setLoading(true);
    try {
      const [{ data: pgs }, { data: th }] = await Promise.all([api.get(`/apps/${appId}/pages`), api.get(`/apps/${appId}/theme`)]);
      setPages(pgs); setTheme(th);
      const pg = pgs.find(p => p.page_id === keepPage) || pgs[0];
      if (pg) { setPageId(pg.page_id); setBlocks(pg.blocks || []); setSelected(pg.blocks?.[0]?.id || null); }
    } catch { toast.error("Failed to load builder"); }
    finally { setLoading(false); }
  }
  function switchPage(id) {
    if (dirty && !confirm("Discard unsaved changes on this page?")) return;
    const pg = pages.find(p => p.page_id === id); setPageId(id); setBlocks(pg.blocks || []); setSelected(pg.blocks?.[0]?.id || null); setDirty(false);
  }
  const mutate = (next) => { setBlocks(next); setDirty(true); };
  function addBlock(tpl) {
    const id = `blk_${Math.random().toString(36).slice(2, 12)}`;
    const b = { id, type: tpl.type, props: JSON.parse(JSON.stringify(tpl.defaults)), style: { bg: "default", align: tpl.type === "hero" || tpl.type === "cta" ? "center" : "left", padding: "md" } };
    const next = tpl.type === "navbar" ? [b, ...blocks] : [...blocks, b];
    mutate(next); setSelected(id);
  }
  const removeBlock = (id) => { const next = blocks.filter(b => b.id !== id); mutate(next); if (selected === id) setSelected(next[0]?.id || null); };
  function onDragEnd({ active, over }) {
    if (!over || active.id === over.id) return;
    mutate(arrayMove(blocks, blocks.findIndex(b => b.id === active.id), blocks.findIndex(b => b.id === over.id))); setSelected(active.id);
  }
  const editProps = (id, path, value) => mutate(blocks.map(b => b.id === id ? { ...b, props: setPath(b.props, path, value) } : b));
  const editStyle = (id, style, propsPatch) => mutate(blocks.map(b => b.id === id ? { ...b, style, props: { ...b.props, ...(propsPatch || {}) } } : b));
  async function save() {
    setSaving(true);
    try {
      await Promise.all([api.patch(`/apps/${appId}/pages/${pageId}`, { blocks }), api.put(`/apps/${appId}/theme`, { theme })]);
      setPages(pages.map(p => p.page_id === pageId ? { ...p, blocks } : p)); setDirty(false); toast.success("Page & theme saved");
    } catch { toast.error("Save failed"); } finally { setSaving(false); }
  }
  async function createPage(name) {
    try { const { data } = await api.post(`/apps/${appId}/pages`, { name, slug: name }); setPages([...pages, data]); switchPage(data.page_id); setPages(p => p.some(x => x.page_id === data.page_id) ? p : [...p, data]); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not create page"); }
  }
  async function deletePage(pg) {
    if (!confirm(`Delete page "${pg.name}"?`)) return;
    await api.delete(`/apps/${appId}/pages/${pg.page_id}`); const rest = pages.filter(p => p.page_id !== pg.page_id); setPages(rest); if (pageId === pg.page_id) switchPage(rest[0].page_id);
  }
  async function runAI() {
    const block = blocks.find(b => b.id === selected); if (!prompt || !block) return;
    setAiBusy(true);
    try { const { data } = await api.post(`/apps/${appId}/ai/edit`, { prompt, block }); mutate(blocks.map(b => b.id === selected ? { ...data, style: data.style || b.style } : b)); setPrompt(""); toast.success("Claude updated the block"); }
    catch (e) { toast.error(e.response?.data?.detail || "AI edit failed"); } finally { setAiBusy(false); }
  }
  const navigateTo = (href) => { const pg = pages.find(p => p.slug === href); if (pg) switchPage(pg.page_id); };
  const [imgBusy, setImgBusy] = useState(false);
  const [collections, setCollections] = useState([]);
  useEffect(() => { api.get(`/apps/${appId}/cms`).then(r => setCollections(r.data)).catch(() => {}); }, [appId]);
  async function genImage(block, key) {
    const ctx = block.props.title || block.props.heading || appDoc?.name || "brand";
    const desc = window.prompt("Describe the image", `${ctx} — ${appDoc?.industry || ""} marketing visual, premium, natural light`);
    if (!desc) return;
    setImgBusy(true);
    try {
      const { data } = await api.post(`/apps/${appId}/media/image`, { prompt: desc, style: "website" }, { timeout: 180000 });
      if (key === "images") editProps(block.id, "images", [data.data_url, ...(block.props.images || [])]);
      else editProps(block.id, "image", data.data_url);
      toast.success("Image generated and placed in the block");
    } catch (e) { toast.error(e.response?.data?.detail || "Image generation failed"); } finally { setImgBusy(false); }
  }

  const sel = blocks.find(b => b.id === selected);
  if (loading) return <div className="overline text-center py-20">Loading builder…</div>;

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <PagesBar pages={pages} current={pageId} onSelect={switchPage} onCreate={createPage} onDelete={deletePage} />
        <div className="ml-auto flex items-center gap-2">
          <div className="flex card-surface !p-0.5 rounded-full">
            {[["desktop", Monitor], ["tablet", Tablet], ["mobile", Smartphone]].map(([d, I]) => <button key={d} data-testid={`device-${d}-btn`} onClick={() => setDevice(d)} className={`w-8 h-8 rounded-full flex items-center justify-center ${device === d ? "bg-white/10 text-white" : "text-[var(--mut)]"}`}><I size={14} /></button>)}
          </div>
          {appDoc?.preview_enabled && appDoc.preview_token && <a data-testid="builder-open-preview" href={`/p/${appDoc.preview_token}`} target="_blank" rel="noreferrer" className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2"><Eye size={13} /> Preview</a>}
          <button data-testid="generate-site-open-btn" onClick={() => setGenOpen(true)} className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2 !border-[var(--acc)]/50 text-[var(--acc)]"><Wand2 size={14} /> Generate site with AI</button>
          <button data-testid="builder-save-btn" onClick={save} disabled={saving} className={`btn-primary text-sm flex items-center gap-2 !py-2 !px-4 ${dirty ? "" : "opacity-80"}`}><Save size={14} /> {saving ? "Saving…" : dirty ? "Save changes" : "Saved"}</button>
        </div>
      </div>

      <div className="grid lg:grid-cols-[230px_1fr_300px] gap-4" data-testid="visual-builder">
        <aside className="space-y-4">
          <div className="card-surface p-3">
            <div className="overline mb-2 px-1">Blocks</div>
            <div className="grid grid-cols-2 gap-1">
              {BLOCK_TEMPLATES.map(t => <button key={t.type} data-testid={`builder-add-${t.type}-block-btn`} onClick={() => addBlock(t)} className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg hover:bg-white/5 text-[11px] text-left"><t.icon size={12} className="text-[var(--acc)] shrink-0" /> {t.label}</button>)}
            </div>
          </div>
          <div className="card-surface p-3">
            <div className="overline mb-2 px-1 flex justify-between">Outline <span className="text-[9px] normal-case tracking-normal text-[var(--dim)]">drag to reorder</span></div>
            <SortableContext items={blocks.map(b => b.id)} strategy={verticalListSortingStrategy}>
              <div className="space-y-1" data-testid="builder-outline-list">
                {blocks.map((b, i) => <OutlineItem key={b.id} block={b} index={i} selected={selected === b.id} onSelect={() => setSelected(b.id)} onRemove={() => removeBlock(b.id)} />)}
                {blocks.length === 0 && <div className="text-xs text-[var(--mut)] px-2 py-4 text-center">Add a block or generate a site →</div>}
              </div>
            </SortableContext>
          </div>
          <ThemePanel theme={theme} onChange={t => { setTheme(t); setDirty(true); }} />
        </aside>

        <div className="min-h-[600px]">
          <div className={`mx-auto transition-all duration-300 ${device === "mobile" ? "max-w-[400px]" : device === "tablet" ? "max-w-[820px]" : "max-w-full"}`}>
            <div className="rounded-2xl border border-[var(--line)] overflow-hidden shadow-2xl" style={{ ...themeVars(theme), background: "var(--tbg)", color: "var(--tfg)", fontFamily: "var(--tfb)" }} data-testid="builder-canvas">
              <div className="bg-[#0B0F17] px-3 py-2 flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-red-400/80" /><span className="w-2.5 h-2.5 rounded-full bg-amber-400/80" /><span className="w-2.5 h-2.5 rounded-full bg-emerald-400/80" /><span className="ml-3 text-[10px] font-mono text-white/40">{appDoc?.custom_domain || "tenant.luciostudio.app"}{pages.find(p => p.page_id === pageId)?.slug}</span></div>
              <div className="max-h-[72vh] overflow-y-auto scrollbar-thin">
                <SortableContext items={blocks.map(b => b.id)} strategy={verticalListSortingStrategy}>
                  {blocks.map(b => <CanvasItem key={b.id} block={b} selected={selected === b.id} onSelect={() => setSelected(b.id)} onEdit={(path, v) => editProps(b.id, path, v)} onNavigate={navigateTo} collections={collections} motionOn={theme.motion !== false} />)}
                </SortableContext>
                {blocks.length === 0 && <div className="p-24 text-center text-[var(--tmut)]">Empty page. Add blocks from the left, or let AI design the whole site.</div>}
              </div>
            </div>
          </div>
          <div className="text-center text-[10px] font-mono text-[var(--dim)] mt-2">Click any text on the canvas to edit it inline · drag handles to reorder</div>
        </div>

        <aside className="space-y-4">
          <div className="card-surface p-4">
            <div className="overline mb-3 flex items-center gap-2"><Sparkles size={12} className="text-[var(--acc)]" /> AI block editor</div>
            <textarea data-testid="builder-ai-prompt-input" value={prompt} onChange={e => setPrompt(e.target.value)} placeholder={sel ? `Edit "${sel.type}"… e.g. "Rewrite for a dental clinic, warmer tone"` : "Select a block first."} rows={3}
              className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--acc)] resize-none" />
            <button data-testid="builder-ai-run-btn" onClick={runAI} disabled={!prompt || !sel || aiBusy} className="mt-3 w-full btn-primary flex items-center justify-center gap-2 !py-2 text-sm disabled:opacity-50"><Sparkles size={13} /> {aiBusy ? "Claude is editing…" : "Ask Claude"}</button>
          </div>
          {sel && (
            <div className="card-surface p-4 space-y-4">
              <StylePanel block={sel} onChange={(style, propsPatch) => editStyle(sel.id, style, propsPatch)} />
              <div>
                <div className="overline mb-2">{sel.type} content</div>
                <div className="space-y-3 max-h-[36vh] overflow-y-auto scrollbar-thin pr-1">
                  {Object.entries(sel.props).map(([k, v]) => (
                    <div key={k}><div className="text-[10px] text-[var(--dim)] mb-1 uppercase flex items-center justify-between">{k}
                      {(k === "image" || k === "images") && <button data-testid={`ai-image-${k}-btn`} disabled={imgBusy} onClick={() => genImage(sel, k)} className="normal-case text-[var(--acc)] flex items-center gap-1 hover:underline disabled:opacity-50">{imgBusy ? <Loader2 size={10} className="animate-spin" /> : <Sparkles size={10} />} {imgBusy ? "Generating…" : "Generate with AI"}</button>}</div>
                      {typeof v === "string" ? <input value={v} onChange={e => editProps(sel.id, k, e.target.value)} data-testid={`prop-${k}-input`} className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-md px-2 py-1.5 text-xs outline-none focus:border-[var(--acc)]" />
                        : typeof v === "boolean" ? <input type="checkbox" checked={v} onChange={e => editProps(sel.id, k, e.target.checked)} />
                        : <textarea value={JSON.stringify(v, null, 2)} rows={4} onChange={e => { try { editProps(sel.id, k, JSON.parse(e.target.value)); } catch { } }} className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-md px-2 py-1.5 text-[11px] font-mono outline-none focus:border-[var(--acc)]" />}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </aside>
      </div>
      <GenerateSiteDialog open={genOpen} onOpenChange={setGenOpen} appId={appId} onDone={() => load()} />
    </DndContext>
  );
}
