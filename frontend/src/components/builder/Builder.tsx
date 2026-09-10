import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, GripVertical, Sparkles, Save, Type, LayoutGrid, DollarSign, Mail, BarChart3, Navigation, Quote, Images, Film, HelpCircle, Megaphone, PanelBottom, Award, Wand2, Monitor, Smartphone, Tablet, Eye, Loader2, Database, Palette, Undo2, Redo2, MousePointer2, History, Globe, Lock, Sun, Moon } from "lucide-react";
import { DndContext, closestCenter, PointerSensor, KeyboardSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import BlockPreview, { DesignCtx } from "@/components/builder/BlockPreview";
import EffectWrap from "@/components/builder/EffectWrap";
import CursorTrail from "@/components/CursorTrail";
import { PagesBar, GenerateSiteDialog } from "@/components/builder/PagesBar";
import PageManager from "@/components/builder/PageManager";
import SiteModeToolbar from "@/components/builder/SiteModeToolbar";
import { ThemePanel, StylePanel } from "@/components/builder/Panels";
import { NicheSwitcher, NichePreviewBar, ClientVoteBanner } from "@/components/builder/NicheSwitcher";
import { LogoUpload } from "@/components/builder/LogoUpload";
import { ImageSwapDialog } from "@/components/builder/ImageSwap";
import { WebImportDialog } from "@/components/builder/WebImport";
import { HistoryDialog } from "@/components/builder/PageHistory";
import { DiffDialog } from "@/components/builder/VersionDiff";
import { EditRequestDialog } from "@/components/builder/EditRequest";
import { DEFAULT_THEME, themeVars, loadFonts, isV2, modeCls } from "@/lib/theme";
import { LockToggle, MasterLockButton, useLocks } from "@/components/locks/LockContext";
import { CtaCtx, ctaKey } from "@/components/CtaFormModal";
import CtaFormEditor from "@/components/CtaFormEditor";

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
  { type: "stats", icon: BarChart3, label: "Stats", defaults: { heading: "By the numbers", items: [{ value: "12K+", label: "Customers served" }, { value: "98%", label: "Satisfaction" }, { value: "15 yrs", label: "In business" }, { value: "4.9★", label: "Average rating" }] } },
  { type: "team", icon: Award, label: "Team", defaults: { heading: "Meet the team", members: [{ name: "Alex Morgan", role: "Founder & CEO", photo: "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=600&q=80" }, { name: "Priya Shah", role: "Head of Operations", photo: "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=600&q=80" }, { name: "Daniel Kim", role: "Lead Engineer", photo: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=600&q=80" }] } },
  { type: "cta", icon: Megaphone, label: "Call to action", defaults: { title: "Ready to get started?", subtitle: "Join thousands of happy customers.", cta: "Start free" } },
  { type: "form", icon: Mail, label: "Form", defaults: { heading: "Request a quote", subtitle: "Tell us what you need and we'll reply within a day.", submit_label: "Send request", success_message: "Thanks — we'll be in touch shortly.", fields: [{ name: "name", label: "Full name", type: "text", placeholder: "Jane Doe", required: true }, { name: "email", label: "Email", type: "email", placeholder: "jane@company.com", required: true }, { name: "service", label: "Service needed", type: "select", options: ["General enquiry", "New project", "Support"], required: false }, { name: "message", label: "How can we help?", type: "textarea", placeholder: "A few details…", required: true }] } },
  { type: "contact", icon: Mail, label: "Contact", defaults: { heading: "Contact us", subtitle: "We reply within a day.", email: "hello@example.com", phone: "+1 (555) 010-2030", address: "100 King St W, Toronto" } },
  { type: "collection_list", icon: Database, label: "Collection list", defaults: { heading: "Latest from the blog", collection: "blog", limit: 6 } },
  { type: "footer", icon: PanelBottom, label: "Footer", defaults: { brand: "Brand", tagline: "Made with care.", columns: [{ title: "Product", links: ["Features", "Pricing"] }, { title: "Company", links: ["About", "Contact"] }, { title: "Legal", links: ["Privacy", "Terms"] }] } },
];

function OutlineItem({ block, index, selected, onSelect, onRemove }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: block.id });
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.6 : 1 }} onClick={onSelect} data-testid={`builder-outline-${block.type}-${index}`}
      className={`flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer select-none group ${selected ? "bg-[var(--acc)]/10 border border-[var(--acc)]/30" : "hover:bg-white/5 border border-transparent"}`}>
      <button {...attributes} {...listeners} data-testid={`builder-drag-handle-${index}`} onClick={e => e.stopPropagation()} className="text-[var(--dim)] hover:text-white cursor-grab active:cursor-grabbing p-0.5 touch-none"><GripVertical size={14} /></button>
      <span className="text-sm capitalize flex-1 truncate">{block.type}</span>
      <LockToggle kind={block.type === "form" ? "form" : "block"} itemId={block.id} name={block.type} />
      <button onClick={e => { e.stopPropagation(); onRemove(); }} className="text-[var(--mut)] hover:text-red-400 p-0.5"><Trash2 size={12} /></button>
    </div>
  );
}

function CanvasItem({ block, selected, onSelect, onEdit, onImage, onNavigate, collections, motionOn, v2 }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: block.id });
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 }} onClick={onSelect} className={`relative group ${selected ? "outline outline-2 outline-[var(--tp)]" : "hover:outline hover:outline-1 hover:outline-[var(--tp)]/40"}`}>
      <button {...attributes} {...listeners} onClick={e => e.stopPropagation()} className="absolute left-2 top-2 z-10 w-8 h-8 rounded-lg bg-black/70 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 cursor-grab active:cursor-grabbing touch-none transition-opacity"><GripVertical size={14} /></button>
      <span className="absolute right-2 top-2 z-10 text-[10px] font-mono uppercase bg-black/70 text-white px-2 py-0.5 rounded opacity-0 group-hover:opacity-100">{block.type}</span>
      <DesignCtx.Provider value={!!v2}>
        <EffectWrap effects={block.style?.effects} motionOn={motionOn} v2={!!v2}><BlockPreview block={block} onEdit={onEdit} onImage={onImage} onNavigate={onNavigate} collections={collections} /></EffectWrap>
      </DesignCtx.Provider>    </div>
  );
}

function setPath(obj, path, value) {
  const keys = path.split("."); const out = Array.isArray(obj) ? [...obj] : { ...obj };
  let cur = out;
  keys.forEach((k, i) => { if (i === keys.length - 1) cur[k] = value; else { cur[k] = Array.isArray(cur[k]) ? [...cur[k]] : { ...cur[k] }; cur = cur[k]; } });
  return out;
}

export default function Builder({ appId, appDoc, user }) {
  const canLock = !user || !appDoc || appDoc.owner_id === user.user_id || appDoc.my_role === "admin" || user.is_admin;
  const [historyOpen, setHistoryOpen] = useState(false);
  const [diffVersion, setDiffVersion] = useState(null);
  const [requestOpen, setRequestOpen] = useState(false);
  const [access, setAccess] = useState({ can_edit: true, can_request: false, locked: false });
  const [pages, setPages] = useState([]);
  const [pageId, setPageId] = useState(null);
  const [lockBusy, setLockBusy] = useState(false);
  const { refresh: refreshLocks, state: lockState, isLocked } = useLocks();
  const refreshAccess = () => pageId && api.get(`/apps/${appId}/pages/${pageId}/edit-access`).then(r => setAccess(r.data)).catch(() => { });
  useEffect(() => { refreshAccess(); }, [appId, pageId, pages.length]);
  const allLocked = lockState === "locked";
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
  const [nicheOpen, setNicheOpen] = useState(false);
  const [nichePreview, setNichePreview] = useState(null);
  const [previewPage, setPreviewPage] = useState(0);
  const [applyingNiche, setApplyingNiche] = useState(false);
  const [lookVote, setLookVote] = useState(appDoc?.look_vote || null);
  const [swapTarget, setSwapTarget] = useState(null);
  const [ctaForms, setCtaForms] = useState({});
  const [formOpen, setFormOpen] = useState(null);
  const [history, setHistory] = useState({ past: [], future: [] });
  const [cursorVote, setCursorVote] = useState(null);
  const [draft, setDraft] = useState(null);
  const [logo, setLogo] = useState(appDoc?.logo || null);
  const [importOpen, setImportOpen] = useState(false);
  const [siteMode, setSiteMode] = useState(null);
  useEffect(() => { api.get(`/apps/${appId}/site-mode`).then(r => setSiteMode(r.data)).catch(() => {}); }, [appId]);
  async function patchSiteMode(next) {
    setSiteMode(s => ({ ...s, ...next }));
    try {
      const { data } = await api.put(`/apps/${appId}/site-mode`, next);
      setSiteMode(s => ({ ...s, ...data }));
      toast.success("Site Mode updated");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not save that setting"); }
  }
  useEffect(() => { setLogo(appDoc?.logo || null); }, [appDoc?.logo]);
  useEffect(() => { setLookVote(appDoc?.look_vote || null); }, [appDoc?.look_vote]);
  async function applyNiche() {
    if (!nichePreview) return;
    setApplyingNiche(true);
    try { const { data } = await api.post(`/apps/${appId}/site/premium-rebuild`, { niche: nichePreview.niche }); toast.success(`Applied ${nichePreview.niche.replace(/_/g, " ")} look · kept ${Object.keys(data.preserved || {}).join(", ") || "pack defaults"}`); if (lookVote?.niche === nichePreview.niche) setLookVote(v => ({ ...v, applied: true })); setNichePreview(null); await load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Apply failed"); } finally { setApplyingNiche(false); }
  }
  async function previewNiche(niche) {
    setApplyingNiche(true);
    try { const { data } = await api.post(`/apps/${appId}/site/niche-preview`, { niche }); setNichePreview(data); setPreviewPage(0); }
    catch (e) { toast.error(e.response?.data?.detail || "Preview failed"); } finally { setApplyingNiche(false); }
  }
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }), useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }));

  useEffect(() => { load(); }, [appId]);
  useEffect(() => { loadFonts(theme); }, [theme]);

  const draftKey = (pid) => `os_builder_draft_${appId}_${pid}`;

  // Draft recovery: keep unsaved canvas changes in localStorage until the page is saved.
  useEffect(() => {
    if (!pageId || !dirty) return;
    const t = setTimeout(() => {
      try { localStorage.setItem(draftKey(pageId), JSON.stringify({ blocks, at: Date.now() })); } catch {}
    }, 800);
    return () => clearTimeout(t);
  }, [blocks, dirty, pageId, appId]);

  const restoreDraft = () => {
    if (!draft) return;
    setBlocks(draft.blocks); setDirty(true); setSelected(draft.blocks?.[0]?.id || null); setDraft(null);
    toast.success("Unsaved changes restored — press Save to keep them");
  };
  const discardDraft = () => {
    try { localStorage.removeItem(draftKey(pageId)); } catch {}
    setDraft(null);
  };

  async function load(keepPage) {
    setLoading(true);
    try {
      const [{ data: pgs }, { data: th }] = await Promise.all([api.get(`/apps/${appId}/pages`), api.get(`/apps/${appId}/theme`)]);
      setPages(pgs); setTheme(th);
      api.get(`/apps/${appId}/cta-forms`).then(r => setCtaForms(Object.fromEntries((r.data.forms || []).map(f => [f.key, f])))).catch(() => {});
      const pg = pgs.find(p => p.page_id === keepPage) || pgs[0];
      if (pg) { setPageId(pg.page_id); setBlocks(pg.blocks || []); setSelected(pg.blocks?.[0]?.id || null); checkDraft(pg); }
    } catch { toast.error("Failed to load builder"); }
    finally { setLoading(false); }
  }
  function checkDraft(pg) {
    try {
      const raw = localStorage.getItem(draftKey(pg.page_id));
      if (!raw) { setDraft(null); return; }
      const d = JSON.parse(raw);
      if (!d?.blocks || JSON.stringify(d.blocks) === JSON.stringify(pg.blocks || [])) { localStorage.removeItem(draftKey(pg.page_id)); setDraft(null); return; }
      setDraft(d);
    } catch { setDraft(null); }
  }

  function switchPage(id) {
    if (dirty && !confirm("Discard unsaved changes on this page?")) return;
    const pg = pages.find(p => p.page_id === id); setPageId(id); setBlocks(pg.blocks || []); setSelected(pg.blocks?.[0]?.id || null); setDirty(false); setHistory({ past: [], future: [] }); checkDraft(pg);
  }
  const mutate = (next) => { setHistory(h => ({ past: [...h.past.slice(-49), blocks], future: [] })); setBlocks(next); setDirty(true); };
  const undo = () => setHistory(h => {
    if (!h.past.length) return h;
    const prev = h.past[h.past.length - 1];
    setBlocks(prev); setDirty(true);
    return { past: h.past.slice(0, -1), future: [blocks, ...h.future].slice(0, 50) };
  });
  const redo = () => setHistory(h => {
    if (!h.future.length) return h;
    const next = h.future[0];
    setBlocks(next); setDirty(true);
    return { past: [...h.past, blocks], future: h.future.slice(1) };
  });
  useEffect(() => {
    const onKey = (e) => {
      if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "z") return;
      const t = e.target;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      e.preventDefault();
      if (e.shiftKey) redo(); else undo();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
  function addBlock(tpl) {
    const id = `blk_${Math.random().toString(36).slice(2, 12)}`;
    const b = { id, type: tpl.type, props: JSON.parse(JSON.stringify(tpl.defaults)), style: { bg: "default", align: tpl.type === "hero" || tpl.type === "cta" ? "center" : "left", padding: tpl.type === "hero" || tpl.type === "cta" ? "lg" : "md", effects: { reveal: true, hover: ["features", "gallery", "testimonials", "pricing", "collection_list", "logos", "stats", "team"].includes(tpl.type) } } };
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
  async function toggleLock(p) {
    try {
      const { data } = await api.post(`/apps/${appId}/locks/item`, { kind: "page", item_id: p.page_id, locked: !p.locked });
      setPages(pages.map(x => x.page_id === p.page_id ? { ...x, locked: data.locked } : x));
      refreshLocks(); refreshAccess();
      toast.success(data.locked ? `"${p.name}" locked — clients can no longer edit it` : `"${p.name}" unlocked`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not change the page lock"); }
  }
  async function save() {
    setSaving(true);
    try {
      await Promise.all([api.patch(`/apps/${appId}/pages/${pageId}`, { blocks }), api.put(`/apps/${appId}/theme`, { theme })]);
      setPages(pages.map(p => p.page_id === pageId ? { ...p, blocks } : p)); setDirty(false); setDraft(null);
      try { localStorage.removeItem(draftKey(pageId)); } catch {}
      toast.success("Page & theme saved");
    } catch { toast.error("Save failed"); } finally { setSaving(false); }
  }
  async function createPage(name, nav = "end") {
    try { const { data } = await api.post(`/apps/${appId}/pages`, { name, slug: name, nav }); setPages([...pages, data]); switchPage(data.page_id); setPages(p => p.some(x => x.page_id === data.page_id) ? p : [...p, data]); toast.success(nav === "hidden" ? `${name} created` : `${name} created and added to the menu`); }
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
  useEffect(() => { api.get(`/apps/${appId}/cursor-vote`).then(r => setCursorVote(r.data.vote || null)).catch(() => {}); }, [appId]);
  async function applyCursorVote() {
    try {
      const { data } = await api.post(`/apps/${appId}/cursor-vote/apply`);
      setCursorVote(data.vote); setTheme(data.theme);
      toast.success(`${data.vote.label} cursor applied to this site`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not apply the vote"); }
  }
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
      {/* Row 2 — tenant/page selector cards · Row 3 — toolbar. Fully separated, never overlapping. */}
      <div className="-mx-6 lg:-mx-10 -mt-8 mb-6" data-testid="builder-header">
        <div className="px-6 lg:px-10 py-4 border-b border-[var(--line)]" data-testid="header-row-pages">
          <PageManager pages={pages} current={pageId} onSelect={switchPage} onCreate={createPage} onDelete={deletePage}
            canLock={canLock} onToggleLock={toggleLock} theme={theme} />
        </div>
        <div className="px-6 lg:px-10 py-4 border-b border-[var(--line)]" data-testid="header-row-toolbar">
          <div className="flex items-center gap-2 mb-4">
            <div className="flex card-surface !p-0.5 rounded-full">
              <button data-testid="builder-undo-btn" title="Undo (Ctrl+Z)" onClick={undo} disabled={!history.past.length}
                className="w-8 h-8 rounded-full flex items-center justify-center text-[var(--mut)] hover:text-white disabled:opacity-30"><Undo2 size={14} /></button>
              <button data-testid="builder-redo-btn" title="Redo (Ctrl+Shift+Z)" onClick={redo} disabled={!history.future.length}
                className="w-8 h-8 rounded-full flex items-center justify-center text-[var(--mut)] hover:text-white disabled:opacity-30"><Redo2 size={14} /></button>
            </div>
            <div className="flex card-surface !p-0.5 rounded-full">
              {[["desktop", Monitor], ["tablet", Tablet], ["mobile", Smartphone]].map(([d, I]) => <button key={d} data-testid={`device-${d}-btn`} onClick={() => setDevice(d)} className={`w-8 h-8 rounded-full flex items-center justify-center ${device === d ? "bg-white/10 text-white" : "text-[var(--mut)]"}`}><I size={14} /></button>)}
            </div>
            <button data-testid="builder-save-btn" onClick={save} disabled={saving} className={`ml-auto btn-primary text-sm flex items-center gap-2 !py-2 !px-4 ${dirty ? "" : "opacity-80"}`}><Save size={14} /> {saving ? "Saving…" : dirty ? "Save changes" : "Saved"}</button>
          </div>
          {/* Controls are grouped automatically by function — see lib/siteModeGroups.ts */}
          <SiteModeToolbar items={[
            { id: "design-mode-toggle", node: (
              <button data-testid="sm-quick-mode" onClick={() => patchSiteMode({ mode: siteMode?.mode === "light" ? "dark" : "light" })}
                className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2">
                {siteMode?.mode === "light" ? <Sun size={14} /> : <Moon size={14} />} {siteMode?.mode === "light" ? "Light" : "Dark"} mode
              </button>) },
            { id: "design-style", node: (
              <button data-testid="sm-quick-style" onClick={() => patchSiteMode({ style: siteMode?.style === "editorial" ? "original" : "editorial" })}
                className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2"><LayoutGrid size={14} /> {siteMode?.style === "editorial" ? "Editorial" : "Original"} style</button>) },
            { id: "design-animation", node: (
              <button data-testid="sm-quick-anim" onClick={() => patchSiteMode({ animation: siteMode?.animation === "full" ? "reduced" : siteMode?.animation === "reduced" ? "none" : "full" })}
                className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2"><Sparkles size={14} /> Animation · {siteMode?.animation || "full"}</button>) },
            { id: "design-accent-colour", node: (
              <label data-testid="sm-quick-accent-wrap" className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2 cursor-pointer">
                <Palette size={14} /> Accent
                <input data-testid="sm-quick-accent" type="color" value={siteMode?.accent || theme?.primary || "#10B981"}
                  onChange={e => patchSiteMode({ accent: e.target.value.toUpperCase() })}
                  className="w-6 h-6 rounded bg-transparent border-0 p-0 cursor-pointer" />
              </label>) },
            { id: "design-hero-motion", node: (
              <a data-testid="sm-quick-hero" href="/hero-gallery" className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2"><MousePointer2 size={14} /> Hero motion{siteMode?.hero ? ` · ${siteMode.hero}` : ""}</a>) },
            { id: "publish-status", node: (
              <div data-testid="sm-publish-group" className="flex card-surface !p-0.5 rounded-full">
                {[["draft", "Draft"], ["preview", "Preview link only"], ["live", "Live"]].map(([v, l]) => (
                  <button key={v} data-testid={`sm-publish-${v}`} onClick={() => patchSiteMode({ publish: v })}
                    className={`text-xs px-3 py-1.5 rounded-full ${siteMode?.publish === v ? "bg-white/10 text-white" : "text-[var(--mut)] hover:text-white"}`}>{l}</button>
                ))}
              </div>) },
            appDoc?.preview_enabled && appDoc.preview_token
              ? { id: "publish-preview-link", node: (
                <a data-testid="builder-open-preview" href={`/p/${appDoc.preview_token}`} target="_blank" rel="noreferrer"
                  className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2"><Eye size={13} /> Open live site</a>) } : null,
            { id: "tools-generate-ai", node: (
              <button data-testid="generate-site-open-btn" onClick={() => setGenOpen(true)} className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2 !border-[var(--acc)]/50 text-[var(--acc)]"><Wand2 size={14} /> Generate site with AI</button>) },
            { id: "tools-import-url", node: (
              <button data-testid="web-import-btn" onClick={() => setImportOpen(true)} className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2"><Globe size={14} /> Import from URL</button>) },
            { id: "tools-upload-logo", group: "tools", node: <LogoUpload appId={appId} logo={logo} onChange={(u) => { setLogo(u); load(); }} /> },
            { id: "tools-another-look", group: "tools", node: (
              <button data-testid="niche-switcher-btn" onClick={() => setNicheOpen(true)} className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2"><Palette size={14} /> Try another look</button>) },
            { id: "tools-history", node: (
              <button data-testid="page-history-btn" onClick={() => setHistoryOpen(true)} className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2"><History size={14} /> History</button>) },
            canLock ? { id: "tools-lock-all", node: <MasterLockButton compact /> } : null,
            access.can_request ? { id: "tools-request-change", node: (
              <button data-testid="request-change-btn" onClick={() => setRequestOpen(true)} className="btn-primary text-sm !py-2 !px-4 flex items-center gap-2"><Lock size={14} /> Request a change</button>) } : null,
          ].filter(Boolean)} />
        </div>
      </div>
      <WebImportDialog appId={appId} open={importOpen} onOpenChange={setImportOpen} onDone={() => load()} />
      <HistoryDialog appId={appId} pageId={pageId} pageName={pages.find(p => p.page_id === pageId)?.name || "page"}
        open={historyOpen} onOpenChange={setHistoryOpen}
        onPreview={(v) => { setBlocks(v.blocks); setSelected(v.blocks?.[0]?.id || null); setDirty(true); }}
        onRestored={(pg) => { setBlocks(pg.blocks || []); setPages(pages.map(p => p.page_id === pg.page_id ? pg : p)); setDirty(false); }}
        onCompare={(v) => { setHistoryOpen(false); setDiffVersion(v); }}
        onSiteRestored={() => load()} />
      {diffVersion && <DiffDialog appId={appId} pageId={pageId} version={diffVersion} open={!!diffVersion}
        onOpenChange={(o) => !o && setDiffVersion(null)}
        onRestored={(pg) => { setBlocks(pg.blocks || []); setDirty(false); setDiffVersion(null); }} />}
      {access.can_request && <EditRequestDialog appId={appId} pageId={pageId} pageName={pages.find(p => p.page_id === pageId)?.name || "page"}
        open={requestOpen} onOpenChange={setRequestOpen} onSent={() => refreshAccess()} />}
      <NicheSwitcher appId={appId} current={appDoc?.site_niche} open={nicheOpen} onOpenChange={setNicheOpen} onPreview={(d) => { setNichePreview(d); setPreviewPage(0); }} />
      <ClientVoteBanner vote={lookVote} onPreview={previewNiche} busy={applyingNiche} />
      {draft && (
        <div data-testid="builder-draft-banner" className="mb-4 card-surface p-4 flex flex-wrap items-center gap-3 !border-amber-400/40">
          <History size={15} className="text-amber-300" />
          <div className="flex-1 text-sm">Unsaved changes from {new Date(draft.at).toLocaleString()} were recovered for this page
            <div className="text-[11px] text-[var(--mut)] mt-0.5">Restore them onto the canvas, or discard to keep the last saved version.</div></div>
          <button data-testid="builder-draft-restore-btn" onClick={restoreDraft} className="btn-primary text-sm !py-2 !px-4">Restore changes</button>
          <button data-testid="builder-draft-discard-btn" onClick={discardDraft} className="btn-ghost text-sm !py-2 !px-4">Discard</button>
        </div>
      )}
      {cursorVote && !cursorVote.applied && (
        <div data-testid="cursor-vote-banner" className="mb-4 card-surface p-4 flex flex-wrap items-center gap-3 !border-[var(--acc)]/40">
          <MousePointer2 size={15} className="text-[var(--acc)]" />
          <div className="flex-1 text-sm">Your client voted for the <span className="font-semibold text-[var(--acc)]">{cursorVote.label}</span> cursor effect
            <div className="text-[11px] text-[var(--mut)] mt-0.5">{cursorVote.by} · {new Date(cursorVote.at).toLocaleString()}</div></div>
          <button data-testid="cursor-vote-apply-btn" onClick={applyCursorVote} className="btn-primary text-sm !py-2 !px-4">Apply to this site</button>
        </div>
      )}
      <ImageSwapDialog appId={appId} target={swapTarget} context={swapTarget?.ctx} onClose={() => setSwapTarget(null)} onApply={(url) => { editProps(swapTarget.blockId, swapTarget.path, url); setSwapTarget(null); }} />
      {formOpen && (
        <div data-testid="builder-form-editor-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) setFormOpen(null); }}
          className="fixed inset-0 z-[80] bg-black/70 backdrop-blur-sm overflow-y-auto p-4 sm:p-8 flex items-start justify-center">
          <div className="card-surface p-5 w-full max-w-3xl my-auto">
            <CtaFormEditor appId={appId} form={formOpen}
              onSaved={(next) => { setCtaForms(m => ({ ...m, [next.key]: next })); setFormOpen(next); }}
              onClose={() => setFormOpen(null)} />
          </div>
        </div>
      )}
      <NichePreviewBar preview={nichePreview} onApply={applyNiche} onExit={() => setNichePreview(null)} applying={applyingNiche} />
      {nichePreview && (
        <div className="min-h-[600px]" data-testid="niche-preview-canvas">
          <div className="flex gap-1 mb-3">{nichePreview.pages.map((p, i) => <button key={p.slug} data-testid={`niche-preview-page-${i}`} onClick={() => setPreviewPage(i)} className={`px-3 py-1.5 rounded-full text-xs ${previewPage === i ? "bg-[var(--acc)] text-black font-semibold" : "text-[var(--mut)] hover:text-white"}`}>{p.name}</button>)}</div>
          <div className={`rounded-2xl border border-[var(--acc)]/40 overflow-hidden shadow-2xl ${modeCls(nichePreview.theme)} ${nichePreview.theme?.grain !== false ? "tgrain" : ""}`} style={{ ...themeVars(nichePreview.theme), background: "var(--tbg)", color: "var(--tbody)", fontFamily: "var(--tfb)" }}>
            <div className="bg-[#0B0F17] px-3 py-2 flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-red-400/80" /><span className="w-2.5 h-2.5 rounded-full bg-amber-400/80" /><span className="w-2.5 h-2.5 rounded-full bg-emerald-400/80" /><span className="ml-3 text-[10px] font-mono text-white/40">preview · {nichePreview.brand.toLowerCase().replace(/[^a-z0-9]+/g, "")}.com{nichePreview.pages[previewPage]?.slug}</span></div>
            <div className="max-h-[72vh] overflow-y-auto scrollbar-thin">{(nichePreview.pages[previewPage]?.blocks || []).map(b => <EffectWrap key={b.id} effects={b.style?.effects} motionOn={true}><BlockPreview block={b} onNavigate={(href) => { const i = nichePreview.pages.findIndex(p => p.slug === href); if (i >= 0) setPreviewPage(i); }} /></EffectWrap>)}</div>
          </div>
        </div>
      )}

      <div className={`grid lg:grid-cols-[230px_1fr_300px] gap-4 ${nichePreview ? "hidden" : ""}`} data-testid="visual-builder">
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
            <div className={`rounded-2xl border border-[var(--line)] overflow-hidden shadow-2xl ${isV2(theme) ? "dsv2" : ""} ${modeCls(theme)} ${theme?.grain !== false ? "tgrain" : ""}`} style={{ ...themeVars(theme), background: "var(--tbg)", color: "var(--tbody)", fontFamily: "var(--tfb)" }} data-testid="builder-canvas">
              <div className="bg-[#0B0F17] px-3 py-2 flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-red-400/80" /><span className="w-2.5 h-2.5 rounded-full bg-amber-400/80" /><span className="w-2.5 h-2.5 rounded-full bg-emerald-400/80" /><span className="ml-3 text-[10px] font-mono text-white/40">{appDoc?.custom_domain || "tenant.luciostudio.app"}{pages.find(p => p.page_id === pageId)?.slug}</span><span data-testid="inline-edit-hint" className="ml-auto text-[10px] text-white/40 hidden sm:inline">Click any text to edit · Enter to commit</span></div>
              <div className="max-h-[72vh] overflow-y-auto scrollbar-thin">
                <CtaCtx.Provider value={{ formFor: (label) => ctaForms[ctaKey(label)] || null, onCta: (f) => setFormOpen(f), editMode: true }}>
                <SortableContext items={blocks.map(b => b.id)} strategy={verticalListSortingStrategy}>
                  {blocks.map(b => <CanvasItem key={b.id} block={b} v2={isV2(theme)} selected={selected === b.id} onSelect={() => setSelected(b.id)} onEdit={(path, v) => editProps(b.id, path, v)} onImage={(path, current) => setSwapTarget({ blockId: b.id, path, current, ctx: b.props.title || b.props.heading || appDoc?.name })} onNavigate={navigateTo} collections={collections} motionOn={theme.motion !== false} />)}
                </SortableContext>
                </CtaCtx.Provider>
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
              <StylePanel block={sel} appId={appId} locked={!access.can_edit || isLocked("block", sel.id) || isLocked("form", sel.id)}
                onChange={(style, propsPatch) => editStyle(sel.id, style, propsPatch)}
                onApplyPresetToPage={(preset) => { mutate(blocks.map(b => ({ ...b, style: { ...(b.style || {}), preset } }))); toast.success(preset ? `“${preset}” applied to every section — press Save to keep it` : "Preset cleared on every section"); }} />
              <div>
                <div className="overline mb-2">{sel.type} content</div>
                <div className="space-y-3 max-h-[36vh] overflow-y-auto scrollbar-thin pr-1">
                  {Object.entries(sel.props).filter(([k]) => k !== "_styles").map(([k, v]) => (
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
