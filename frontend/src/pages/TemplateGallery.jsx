import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { ArrowLeft, Check, Clock, Eye, FlaskConical, Layers, Link2, Loader2, Rocket, Share2, Sparkles, X } from "lucide-react";
import api from "@/lib/api";
import TemplateRolloutModal from "@/components/TemplateRolloutModal";
import TemplatePushModal from "@/components/TemplatePushModal";
import PushToOnePicker from "@/components/PushToOnePicker";
import BlockPreview, { DesignCtx } from "@/components/builder/BlockPreview";
import { themeVars, loadFonts, isV2, modeCls } from "@/lib/theme";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

/** Live, scaled render of a template's real pages — same renderer the tenant sites use. */
function TemplateFrame({ detail, scale = 0.3, maxBlocks = 3, height = 260 }) {
  const vars = themeVars(detail.theme);
  const blocks = (detail.pages?.[0]?.blocks || []).slice(0, maxBlocks);
  return (
    <div className="relative overflow-hidden" style={{ height }}>
      <div className={`absolute top-0 left-0 origin-top-left ${isV2(detail.theme) ? "dsv2" : ""} ${modeCls(detail.theme)}`}
        style={{ ...vars, width: `${100 / scale}%`, transform: `scale(${scale})`, background: "var(--tbg)", color: "var(--tbody)", fontFamily: "var(--tfb)" }}>
        <DesignCtx.Provider value={isV2(detail.theme)}>
          {blocks.map((b, i) => <BlockPreview key={b.block_id || i} block={b} collections={[]} />)}
        </DesignCtx.Provider>
      </div>
    </div>
  );
}

/** Full-page, scrollable preview of every page in the template. */
function FullPreview({ detail, onClose, onUse, useLabel }) {
  const [slug, setSlug] = useState(detail.pages?.[0]?.slug || "/");
  const page = detail.pages?.find(p => p.slug === slug) || detail.pages?.[0];
  useEffect(() => { loadFonts(detail.theme); }, [detail]);
  return (
    <div className="fixed inset-0 z-[70] bg-[var(--bg)] flex flex-col" data-testid="template-full-preview">
      <div className="flex items-center gap-3 px-5 py-3 border-b border-[var(--line)] shrink-0 flex-wrap">
        <button data-testid="template-preview-close" onClick={onClose} className="btn-ghost text-sm !py-1.5 !px-3 flex items-center gap-1"><X size={14} /> Close</button>
        <div>
          <div className="font-display text-lg font-semibold leading-tight">{detail.brand}</div>
          <div className="overline">{detail.category} · {detail.theme.mode} mode · {detail.theme.font_heading}</div>
        </div>
        <div className="flex items-center gap-1.5 ml-2 flex-wrap">
          {detail.pages.map(p => (
            <button key={p.slug} data-testid={`template-preview-page-${p.slug.replace("/", "") || "home"}`} onClick={() => setSlug(p.slug)}
              className={`chip cursor-pointer ${slug === p.slug ? "chip-active" : ""}`}>{p.name}</button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2">
          {[detail.theme.primary, detail.theme.secondary, detail.theme.bg].map(c => (
            <span key={c} className="w-5 h-5 rounded-full border border-white/15" style={{ background: c }} />
          ))}
          <button data-testid="template-preview-use-btn" onClick={() => onUse(detail)} className="btn-primary text-sm !py-2 !px-4 flex items-center gap-2"><Check size={14} /> {useLabel}</button>
        </div>
      </div>
      <div className={`flex-1 overflow-y-auto ${isV2(detail.theme) ? "dsv2" : ""} ${modeCls(detail.theme)}`}
        style={{ ...themeVars(detail.theme), background: "var(--tbg)", color: "var(--tbody)", fontFamily: "var(--tfb)" }}>
        <DesignCtx.Provider value={isV2(detail.theme)}>
          {(page?.blocks || []).map((b, i) => <BlockPreview key={b.block_id || i} block={b} collections={[]} />)}
        </DesignCtx.Provider>
      </div>
    </div>
  );
}

function Card({ t, detail, onOpen, onUse, useLabel, selected, state, onPush, onTemplatePush, allKeys }) {
  const isTest = t.key === "test_template";
  const ref = useRef(null);
  return (
    <motion.div ref={ref} initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-40px" }}
      data-testid={`template-card-${t.key}`} className={`card-surface overflow-hidden group cursor-pointer ${selected ? "!border-[var(--acc)]" : ""}`}
      onClick={() => onOpen(t)}>
      <div className="relative bg-[var(--bg-2)] border-b border-[var(--line)]">
        {detail ? <TemplateFrame detail={detail} /> : (
          <div className="h-[260px] flex items-center justify-center"><Loader2 size={18} className="animate-spin text-[var(--mut)]" /></div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-[var(--card)] via-transparent to-transparent pointer-events-none" />
        <div className="absolute top-3 left-3 flex gap-1.5">
          {isTest && (
            <span data-testid="template-test-badge" className="chip inline-flex items-center gap-1"
              style={{ background: "rgba(250,204,21,0.18)", color: "#FACC15", borderColor: "rgba(250,204,21,0.45)" }}>
              <FlaskConical size={10} /> TEST
            </span>
          )}
          {state?.status === "pending" && (
            <span data-testid={`template-pending-badge-${t.key}`} className="chip inline-flex items-center gap-1"
              style={{ background: "rgba(249,115,22,0.16)", color: "#FB923C", borderColor: "rgba(249,115,22,0.4)" }}>
              <Clock size={10} /> Pending Update
            </span>
          )}
          {t.studio && <span data-testid={`template-studio-badge-${t.key}`} className="chip chip-active inline-flex items-center gap-1"><Sparkles size={10} /> New design</span>}
          <span className="chip">{t.category}</span>
          <span className="chip">{t.mode === "light" ? "Light" : "Dark"}</span>
        </div>
        <div className="absolute bottom-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity">
          <span className="chip chip-active flex items-center gap-1"><Eye size={11} /> Full preview</span>
        </div>
      </div>
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="font-display text-lg font-semibold truncate">{t.brand}</div>
            <div className="text-xs text-[var(--mut)] mt-0.5 line-clamp-2">{t.summary}</div>
          </div>
          <div className="flex gap-1 shrink-0 pt-1">
            {[t.primary, t.secondary, t.bg].map(c => <span key={c} className="w-4 h-4 rounded-full border border-white/15" style={{ background: c }} />)}
          </div>
        </div>
        <div className="mt-3 flex items-center justify-between gap-2">
          <div className="font-mono text-[10px] text-[var(--dim)] truncate">{t.font_heading} · {t.font_body} · r{t.radius}</div>
          <button data-testid={`template-use-${t.key}`} onClick={(e) => { e.stopPropagation(); onUse(t); }}
            className="btn-primary text-xs !py-1.5 !px-3 whitespace-nowrap">{useLabel}</button>
        </div>
        {isTest && onTemplatePush ? (
          <div className="mt-2 space-y-2">
            <button data-testid="push-to-all-templates-btn"
              onClick={(e) => { e.stopPropagation(); onTemplatePush({ scope: "all" }); }}
              className="w-full btn-primary text-[11px] !py-2 flex items-center justify-center gap-1.5">
              <Rocket size={11} /> Push to All Templates
            </button>
            <PushToOnePicker testid="push-to-one-template" label="Push to One Template"
              options={(allKeys || []).map((k) => ({ value: k, label: k.replace(/_/g, " ") }))}
              onPick={(k) => onTemplatePush({ targetKey: k })} />
          </div>
        ) : onPush && (
          <button data-testid={`template-push-${t.key}`} onClick={(e) => { e.stopPropagation(); onPush(t, state); }}
            className={`mt-2 w-full text-[11px] !py-2 flex items-center justify-center gap-1.5 ${state?.status === "pending" ? "btn-primary" : "btn-ghost"}`}>
            <Rocket size={11} /> Push to All Tenants Using This Template
            <span className="font-mono text-[10px] opacity-70">({state?.tenants_using ?? 0})</span>
          </button>
        )}
      </div>
    </motion.div>
  );
}

export default function TemplateGallery({ clientMode = false }) {
  const nav = useNavigate();
  const { token } = useParams();
  const [list, setList] = useState([]);  const [cats, setCats] = useState([]);
  const [cat, setCat] = useState("All");
  const [details, setDetails] = useState({});
  const [full, setFull] = useState(null);
  const [loading, setLoading] = useState(true);
  const [share, setShare] = useState(null);
  const [shareOpen, setShareOpen] = useState(false);
  const [clientName, setClientName] = useState("");
  const [useOpen, setUseOpen] = useState(null);
  const [form, setForm] = useState({ name: "", description: "" });
  const [busy, setBusy] = useState(false);
  const [chosen, setChosen] = useState(null);
  const [clientNote, setClientNote] = useState("");
  const [shareInfo, setShareInfo] = useState(null);
  const [states, setStates] = useState({});
  const [pushing, setPushing] = useState(null);
  const [tplPush, setTplPush] = useState(null);   // { scope } | { targetKey }

  const loadStates = () => {
    if (clientMode) return;
    api.get("/templates/rollout-status")
      .then(({ data }) => setStates(Object.fromEntries(data.templates.map((t) => [t.key, t]))))
      .catch(() => { /* non-blocking */ });
  };
  useEffect(loadStates, [clientMode]);

  useEffect(() => {
    api.get("/public/templates").then(r => {
      // the sandbox template is never offered to clients
      setList(clientMode ? r.data.templates.filter(t => t.key !== "test_template") : r.data.templates);
      setCats(r.data.categories);
    })
      .catch(() => toast.error("Could not load the template gallery")).finally(() => setLoading(false));
    if (clientMode && token) {
      api.get(`/public/template-shares/${token}`).then(r => { setShareInfo(r.data); setChosen(r.data.selected_key || null); })
        .catch(e => setShareInfo({ error: e.response?.data?.detail || "This preview link is not valid" }));
    }
  }, [clientMode, token]);

  // Load real page data for every template so each card renders its true design.
  // Batched (4 at a time) with one retry so a slow/failed request never leaves a card spinning.
  useEffect(() => {
    if (!list.length) return;
    let stop = false;
    (async () => {
      const keys = list.map(t => t.key);
      for (let i = 0; i < keys.length; i += 4) {
        if (stop) return;
        await Promise.all(keys.slice(i, i + 4).map(async k => {
          for (let attempt = 0; attempt < 2; attempt++) {
            try {
              const r = await api.get(`/public/templates/${k}`);
              if (!stop) setDetails(d => ({ ...d, [k]: r.data }));
              return;
            } catch { /* retry once */ }
          }
        }));
      }
    })();
    return () => { stop = true; };
  }, [list]);

  const shown = useMemo(() => {
    const base = cat === "All" ? list : cat === "New design" ? list.filter(t => t.studio) : list.filter(t => t.category === cat);
    // Test Template always sits first so it is never confused with a client-facing design.
    return [...base].sort((a, b) => (b.key === "test_template" ? 1 : 0) - (a.key === "test_template" ? 1 : 0));
  }, [list, cat]);

  function openFull(t) {
    const d = details[t.key];
    if (!d) return toast.message("Still rendering that design — one moment");
    loadFonts(d.theme);
    setFull(d);
  }

  async function useTemplate(t) {
    if (clientMode) {
      try {
        await api.post(`/public/template-shares/${token}/select`, { key: t.key, client_note: clientNote });
        setChosen(t.key); setFull(null);
        toast.success(`${t.brand} sent to your agency as your chosen design`);
      } catch (e) { toast.error(e.response?.data?.detail || "Could not send your choice"); }
      return;
    }
    setFull(null);
    setUseOpen(t);
    setForm({ name: "", description: t.summary });
  }

  async function createFromTemplate() {
    if (!form.name.trim()) return toast.error("Give the tenant a name");
    setBusy(true);
    try {
      const { data } = await api.post("/apps", {
        name: form.name.trim(), industry: useOpen.industry, description: form.description,
        kind: "website", status: "active", template_key: useOpen.key,
      });
      toast.success(`${data.name} created with the ${useOpen.brand} design`);
      nav(`/apps/${data.app_id}`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not create that tenant"); }
    finally { setBusy(false); }
  }

  async function makeShareLink() {
    setBusy(true);
    try {
      const { data } = await api.post("/template-shares", { client_name: clientName || "Client", note: "" });
      const url = `${window.location.origin}/choose/${data.token}`;
      setShare({ ...data, url });
      try { await navigator.clipboard.writeText(url); toast.success("Link copied — valid for 7 days"); }
      catch { toast.success("Preview link ready — valid for 7 days"); }
    } catch (e) { toast.error(e.response?.data?.detail || "Could not create a preview link"); }
    finally { setBusy(false); }
  }

  if (clientMode && shareInfo?.error) return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-center px-6" data-testid="share-invalid">
      <Layers size={26} className="text-[var(--mut)]" />
      <div className="font-display text-2xl">{shareInfo.error}</div>
      <p className="text-sm text-[var(--mut)]">Preview links stay open for 7 days. Ask your agency to send a new one.</p>
    </div>
  );

  return (
    <div className="min-h-screen px-6 lg:px-10 py-8" data-testid={clientMode ? "client-template-gallery" : "template-gallery"}>
      <div className="flex flex-wrap items-end justify-between gap-4 mb-7">
        <div>
          {!clientMode && <button data-testid="gallery-back-btn" onClick={() => nav("/dashboard")} className="text-sm text-[var(--mut)] hover:text-white inline-flex items-center gap-1 mb-3"><ArrowLeft size={14} /> Dashboard</button>}
          <div className="overline mb-1 flex items-center gap-2"><Sparkles size={12} className="text-[var(--acc)]" /> {clientMode ? `Choose a design${shareInfo?.client_name ? ` · ${shareInfo.client_name}` : ""}` : `Template gallery · ${list.length} designs`}
            {!clientMode && Object.values(states).some((s) => s.status === "pending") && (
              <span data-testid="gallery-pending-count" className="chip chip-maint inline-flex items-center gap-1">
                <Clock size={10} /> {Object.values(states).filter((s) => s.status === "pending").length} pending update
              </span>
            )}
          </div>
          <h1 className="font-display text-3xl lg:text-4xl font-semibold tracking-tight">{clientMode ? "Pick the look you love." : "Start from a finished design."}</h1>
          <p className="text-[var(--mut)] mt-2 max-w-2xl text-sm">{clientMode
            ? "Browse every design side by side, open any one full screen to scroll the whole site, then send your pick to the team."
            : "Every template is a complete, distinct build — its own palette, typography, hero and section style. Pick one and the tenant is created with that design applied instantly."}</p>
        </div>
        {!clientMode && (
          <button data-testid="preview-for-client-btn" onClick={() => setShareOpen(true)} className="btn-ghost text-sm flex items-center gap-2"><Share2 size={14} /> Preview for client</button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-6 border-b border-[var(--line)] pb-4">
        {["All", "New design", ...cats].map(c => (
          <button key={c} data-testid={`gallery-cat-${c.toLowerCase().replace(/\s+/g, "-")}`} onClick={() => setCat(c)}
            className={`chip cursor-pointer ${cat === c ? "chip-active" : ""}`}>{c}</button>
        ))}
        <span className="ml-auto text-xs text-[var(--mut)] font-mono">{shown.length} design{shown.length === 1 ? "" : "s"}</span>
      </div>

      {loading ? (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5">
          {[...Array(6)].map((_, i) => <div key={i} className="card-surface h-[400px]"><div className="skeleton h-[260px] rounded-none" /></div>)}
        </div>
      ) : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5">
          {shown.map(t => (
            <Card key={t.key} t={t} detail={details[t.key]} onOpen={openFull} onUse={useTemplate}
              state={states[t.key]} onPush={clientMode ? null : (tpl, st) => setPushing({ ...tpl, ...(st || {}) })}
              onTemplatePush={clientMode ? null : setTplPush}
              allKeys={list.filter((x) => x.key !== "test_template").map((x) => x.key)}
              selected={chosen === t.key} useLabel={clientMode ? (chosen === t.key ? "Your pick" : "Choose this") : "Use this template"} />
          ))}
        </div>
      )}

      {clientMode && (
        <div className="card-surface p-5 mt-6 max-w-2xl" data-testid="client-note-box">
          <div className="overline mb-2">Anything you want the team to know?</div>
          <textarea data-testid="client-note-input" rows={3} value={clientNote} onChange={e => setClientNote(e.target.value)}
            placeholder="e.g. we love the type but would prefer our green as the accent"
            className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--acc)]" />
          {chosen && <div className="text-xs text-[var(--acc)] mt-2" data-testid="client-choice-confirm">Your pick — {list.find(t => t.key === chosen)?.brand} — has been sent to your agency.</div>}
        </div>
      )}

      {full && <FullPreview detail={full} onClose={() => setFull(null)} onUse={useTemplate}
        useLabel={clientMode ? "Choose this design" : "Use this template"} />}

      {pushing && <TemplateRolloutModal template={pushing} onClose={() => setPushing(null)} onDone={loadStates} />}

      {tplPush && (
        <TemplatePushModal open initialScope={tplPush.scope || "all"} targetKey={tplPush.targetKey || null}
          onClose={() => setTplPush(null)} onDone={() => { loadStates(); load(); }} />
      )}

      <Dialog open={shareOpen} onOpenChange={setShareOpen}>
        <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)]">
          <DialogHeader><DialogTitle className="font-display">Share the gallery with your client</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-[var(--mut)]">They browse all 16 designs, scroll any one full screen and send back their pick. No login needed, and the link expires after 7 days.</p>
            <label className="block"><span className="overline block mb-1">Client name</span>
              <input data-testid="share-client-name-input" value={clientName} onChange={e => setClientName(e.target.value)} placeholder="Northwind Roofing"
                className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--acc)]" /></label>
            {share ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2 bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2">
                  <Link2 size={14} className="text-[var(--acc)] shrink-0" />
                  <span data-testid="share-link-value" className="text-xs font-mono truncate">{share.url}</span>
                </div>
                <button data-testid="share-copy-btn" onClick={() => { navigator.clipboard.writeText(share.url); toast.success("Copied"); }} className="btn-ghost text-xs !py-1.5 !px-3">Copy link again</button>
                <div className="text-[11px] text-[var(--mut)]">Expires {new Date(share.expires_at).toLocaleDateString()} · their choice appears on your dashboard</div>
              </div>
            ) : (
              <button data-testid="share-create-btn" onClick={makeShareLink} disabled={busy} className="btn-primary w-full disabled:opacity-60">{busy ? "Creating…" : "Create preview link"}</button>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!useOpen} onOpenChange={(o) => !o && setUseOpen(null)}>
        <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)]">
          <DialogHeader><DialogTitle className="font-display">New tenant · {useOpen?.brand} design</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <label className="block"><span className="overline block mb-1">Tenant name</span>
              <input data-testid="template-tenant-name-input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Client business name"
                className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--acc)]" /></label>
            <label className="block"><span className="overline block mb-1">Description</span>
              <textarea data-testid="template-tenant-desc-input" rows={3} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
                className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--acc)]" /></label>
            <div className="text-[11px] text-[var(--mut)]">Creates a 4-page site (Home, About, Services, Contact) with the {useOpen?.brand} palette, typography and section style applied.</div>
            <button data-testid="template-create-btn" onClick={createFromTemplate} disabled={busy} className="btn-primary w-full disabled:opacity-60">{busy ? "Creating…" : "Create tenant with this design"}</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
