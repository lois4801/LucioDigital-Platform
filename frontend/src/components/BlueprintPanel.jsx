import { useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sparkles, Loader2, Database, Route, Layout, Shield, Plug, Download, Table, FormInput, BarChart3, LayoutGrid, MessageSquare, Settings, KanbanSquare, Calendar, LogIn, FileUp, RefreshCw } from "lucide-react";

const COMP_ICON = { table: Table, list: Table, form: FormInput, stats: BarChart3, chart: BarChart3, cards: LayoutGrid, chat: MessageSquare, settings: Settings, kanban: KanbanSquare, calendar: Calendar, auth: LogIn, detail: Layout, hero: Layout, navbar: Layout };
const EXAMPLES = ["Patient booking app for a dental clinic: appointments, patients, treatments, invoices, SMS reminders", "Field-service CRM for HVAC technicians with jobs, dispatch board, quotes and customer portal", "Internal tool for tracking influencer campaigns, budgets and content approvals"];

function Mock({ c, accent = "#F97316" }) {
  const fields = c.fields?.length ? c.fields : ["Name", "Status", "Updated"];
  const t = c.type;
  if (t === "stats") return <div className="grid grid-cols-3 gap-3">{fields.slice(0, 3).map(f => <div key={f} className="rounded-xl border border-slate-200 p-4"><div className="text-[10px] uppercase text-slate-500">{f}</div><div className="text-2xl font-bold mt-1 text-slate-900">{Math.floor(Math.random() * 900 + 100)}</div></div>)}</div>;
  if (t === "table" || t === "list") return <table className="w-full text-xs"><thead><tr className="text-left text-slate-500 border-b border-slate-200">{fields.slice(0, 5).map(f => <th key={f} className="py-2 font-medium">{f}</th>)}</tr></thead><tbody>{[1, 2, 3].map(r => <tr key={r} className="border-b border-slate-100">{fields.slice(0, 5).map((f, i) => <td key={f} className="py-2.5 text-slate-700">{i === 0 ? `Sample ${r}` : i === 1 ? <span className="px-2 py-0.5 rounded-full text-[10px]" style={{ background: `${accent}1A`, color: accent }}>Active</span> : "—"}</td>)}</tr>)}</tbody></table>;
  if (t === "form" || t === "settings" || t === "auth") return <div className="grid sm:grid-cols-2 gap-3">{fields.slice(0, 6).map(f => <div key={f}><div className="text-[10px] text-slate-500 mb-1">{f}</div><div className="h-9 rounded-lg border border-slate-200 bg-white" /></div>)}<div className="sm:col-span-2"><span data-testid="proto-save-btn" className="inline-block px-5 py-2 rounded-full text-white text-xs font-semibold" style={{ background: accent }}>Save</span></div></div>;
  if (t === "chart") return <div className="h-28 flex items-end gap-2">{[40, 70, 55, 90, 65, 100, 80].map((h, i) => <div key={i} className="flex-1 rounded-t-md" style={{ height: `${h}%`, background: `linear-gradient(180deg,${accent},${accent}66)` }} />)}</div>;
  if (t === "kanban") { const cols = c.fields?.length >= 2 ? c.fields.slice(0, 5) : ["Todo", "In progress", "Done"]; return <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${cols.length},1fr)` }}>{cols.map(col => <div key={col} className="rounded-xl bg-slate-50 p-3"><div className="text-[10px] uppercase text-slate-500 mb-2 flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full" style={{ background: accent }} />{col}</div>{[1, 2].map(i => <div key={i} className="rounded-lg bg-white border border-slate-200 p-2 text-xs mb-2 text-slate-700">Card {i}</div>)}</div>)}</div>; }
  if (t === "calendar") return <div className="grid grid-cols-7 gap-1 text-[10px]">{["M", "T", "W", "T", "F", "S", "S"].map((d, i) => <div key={i} className="text-center text-slate-400 py-1">{d}</div>)}{Array.from({ length: 28 }).map((_, i) => <div key={i} className="h-8 rounded-md border border-slate-100 p-1 text-slate-500 relative">{i + 1}{[3, 9, 14, 22].includes(i) && <span className="absolute bottom-1 left-1 right-1 h-1 rounded-full" style={{ background: accent }} />}</div>)}</div>;
  if (t === "chat") return <div className="space-y-2 text-xs"><div className="bg-slate-100 rounded-2xl px-3 py-2 w-2/3 text-slate-700">Hi, how can I help?</div><div className="text-white rounded-2xl px-3 py-2 w-1/2 ml-auto" style={{ background: accent }}>Book an appointment</div></div>;
  return <div className="grid sm:grid-cols-3 gap-3">{[1, 2, 3].map(i => <div key={i} className="rounded-xl border border-slate-200 p-4"><div className="h-16 rounded-lg bg-slate-100 mb-3" /><div className="text-sm font-semibold text-slate-900">{fields[0]} {i}</div><div className="text-xs text-slate-500 mt-1">{fields[1] || "Detail"}</div></div>)}</div>;
}

export default function BlueprintPanel({ appId, apiRoot }) {
  const [spec, setSpec] = useState(null);
  const [brief, setBrief] = useState("");
  const [busy, setBusy] = useState(false);
  const [screen, setScreen] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => { api.get(`/apps/${appId}/blueprint`).then(r => setSpec(r.data)).catch(() => {}).finally(() => setLoading(false)); }, [appId]);

  async function generate() {
    setBusy(true);
    try { const { data } = await api.post(`/apps/${appId}/ai/generate-app`, { brief }, { timeout: 300000 }); setSpec(data); setScreen(0); toast.success(`Blueprint ready: ${data.screens?.length} screens`); }
    catch (e) { toast.error(e.response?.data?.detail || "Generation failed"); } finally { setBusy(false); }
  }

  const [chat, setChat] = useState([]);
  const [msg, setMsg] = useState("");
  const [target, setTarget] = useState(null);
  const [refining, setRefining] = useState(false);
  const [briefOpen, setBriefOpen] = useState(false);
  const [longBrief, setLongBrief] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef();
  async function uploadBrief(e) {
    const f = e.target.files?.[0]; if (!f) return; setUploading(true);
    const fd = new FormData(); fd.append("file", f);
    try { const { data } = await api.post(`/apps/${appId}/ai/brief-upload`, fd, { headers: { "Content-Type": "multipart/form-data" } }); setLongBrief(data.text); toast.success(`Extracted ${data.chars.toLocaleString()} characters from ${data.filename}`); }
    catch (err) { toast.error(err.response?.data?.detail || "Upload failed"); } finally { setUploading(false); e.target.value = ""; }
  }
  async function applyLongBrief() {
    setBriefOpen(false);
    if (spec) { setMsg(longBrief); await refineWith(longBrief); } else { setBrief(longBrief); }
    setLongBrief("");
  }
  async function refineWith(text) {
    setRefining(true); setChat(c => [...c, { role: "user", content: text.slice(0, 400) + (text.length > 400 ? "…" : ""), target }]);
    try { const { data } = await api.post(`/apps/${appId}/ai/refine-app`, { message: text, target }, { timeout: 300000 }); setSpec(data.spec); setChat(c => [...c, { role: "assistant", content: data.summary }]); setTarget(null); toast.success("Blueprint updated"); }
    catch (e) { toast.error(e.response?.data?.detail || "Refinement failed"); } finally { setRefining(false); setMsg(""); }
  }
  useEffect(() => { api.get(`/apps/${appId}/ai/app-chat`).then(r => setChat(r.data)).catch(() => {}); }, [appId]);
  async function refine() {
    if (!msg.trim() || refining) return;
    const text = msg; setMsg(""); setRefining(true);
    setChat(c => [...c, { role: "user", content: text, target }]);
    try { const { data } = await api.post(`/apps/${appId}/ai/refine-app`, { message: text, target }, { timeout: 300000 }); setSpec(data.spec); setChat(c => [...c, { role: "assistant", content: data.summary }]); setTarget(null); toast.success("Blueprint updated"); }
    catch (e) { toast.error(e.response?.data?.detail || "Refinement failed"); } finally { setRefining(false); }
  }
  const [sync, setSync] = useState({ enabled: false, last_sync: null, last_summary: null });
  const [syncing, setSyncing] = useState(false);
  useEffect(() => { api.get(`/apps/${appId}/site-sync`).then(r => setSync(r.data)).catch(() => {}); }, [appId]);
  async function toggleSync(enabled) {
    setSync(s => ({ ...s, enabled }));
    try { await api.post(`/apps/${appId}/site-sync`, { enabled }); toast.success(enabled ? "Auto-sync on — saving a page will rebuild this app" : "Auto-sync off"); }
    catch (e) { setSync(s => ({ ...s, enabled: !enabled })); toast.error(e.response?.data?.detail || "Failed"); }
  }
  async function syncFromSite() {
    setSyncing(true);
    try {
      const { data: job } = await api.post(`/apps/${appId}/ai/app-from-site`, { mode: spec ? "merge" : "overwrite" });
      let data = null;
      for (let i = 0; i < 100 && !data; i++) {
        await new Promise(r => setTimeout(r, 4000));
        const { data: st } = await api.get(`/apps/${appId}/ai/app-sync-job/${job.job_id}`);
        if (st.status === "done") data = st.result;
        else if (st.status === "error") throw new Error(st.error || "Sync failed");
      }
      if (!data) throw new Error("Sync timed out — try again");
      setSpec(data.spec); setScreen(0); setSync(s => ({ ...s, ...data.sync }));
      setChat(c => [...c, { role: "assistant", content: `Synced from Site Mode — ${data.summary}` }]);
      toast.success(`App built from your site · ${data.spec.screens?.length} screens`);
    } catch (e) { toast.error(e.response?.data?.detail || e.message || "Sync failed"); } finally { setSyncing(false); }
  }
  const [templates, setTemplates] = useState([]);
  const [tplOpen, setTplOpen] = useState(false);
  const [dark, setDark] = useState(false);
  useEffect(() => { api.get("/templates").then(r => setTemplates(r.data)).catch(() => {}); }, []);
  async function applyTemplate(key) {
    try { const { data } = await api.post(`/apps/${appId}/templates/${key}/apply`); setSpec(data.spec); setScreen(0); setTplOpen(false); toast.success(`Template applied: ${data.spec.name}`); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  }
  const accent = spec?.palette ? ({ amber: "#F59E0B", orange: "#F97316", teal: "#0D9488", navy: "#1E3A8A", violet: "#7C3AED", terracotta: "#C2410C", red: "#DC2626", blue: "#2563EB", indigo: "#4F46E5", emerald: "#059669", rose: "#E11D48", slate: "#334155", green: "#16A34A", cyan: "#0891B2", purple: "#9333EA", sky: "#0284C7", lime: "#65A30D", brown: "#92400E" }[spec.palette] || "#F97316") : "#F97316";
  const s = spec?.screens?.[screen];
  return (
    <div data-testid="blueprint-panel" className="space-y-6">
      <Dialog open={briefOpen} onOpenChange={setBriefOpen}>
        <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)] max-w-2xl">
          <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><FileUp size={16} className="text-[var(--acc)]" /> Long brief or requirements document</DialogTitle></DialogHeader>
          <p className="text-sm text-[var(--mut)]">Upload a .docx / .pdf / .txt / .md, or paste a long narrative. {spec ? "It will be applied as a change request to the current blueprint." : "It becomes the brief for a new blueprint."}</p>
          <input ref={fileRef} data-testid="brief-file-input" type="file" accept=".docx,.pdf,.txt,.md" className="hidden" onChange={uploadBrief} />
          <button data-testid="brief-upload-btn" onClick={() => fileRef.current.click()} disabled={uploading} className="w-full border border-dashed border-[var(--line)] hover:border-[var(--acc)]/60 rounded-xl py-5 flex items-center justify-center gap-2 text-sm">{uploading ? <Loader2 size={16} className="animate-spin text-[var(--acc)]" /> : <FileUp size={16} className="text-[var(--acc)]" />} {uploading ? "Extracting text…" : "Choose document"}</button>
          <textarea data-testid="brief-long-input" value={longBrief} onChange={e => setLongBrief(e.target.value)} rows={12} placeholder="Or paste your narrative here…" className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-4 py-3 text-sm outline-none focus:border-[var(--acc)] resize-none" />
          <div className="flex justify-between items-center text-[11px] font-mono text-[var(--dim)]"><span>{longBrief.length.toLocaleString()} chars</span><button data-testid="brief-apply-btn" onClick={applyLongBrief} disabled={longBrief.trim().length < 20} className="btn-primary text-sm !py-2 !px-5 disabled:opacity-50">{spec ? "Apply to blueprint" : "Use as brief"}</button></div>
        </DialogContent>
      </Dialog>
      <div className="card-surface p-5">
        <div className="flex flex-col lg:flex-row lg:items-end gap-4">
          <div className="flex-1">
            <div className="overline mb-1 flex items-center gap-2"><Sparkles size={12} className="text-[var(--acc)]" /> Lovable-style app blueprint</div>
            <h3 className="font-display text-2xl font-semibold tracking-tight">Describe the app — get screens, data models, API and starter code</h3>
            <textarea data-testid="app-brief-input" value={brief} onChange={e => setBrief(e.target.value)} rows={2} placeholder="e.g. Patient booking app for a dental clinic…" className="mt-3 w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-4 py-3 text-sm outline-none focus:border-[var(--acc)] resize-none" />
            <div className="flex flex-wrap gap-2 mt-2">{EXAMPLES.map((x, i) => <button key={i} data-testid={`app-example-${i}`} onClick={() => setBrief(x)} className="chip normal-case tracking-normal cursor-pointer hover:!text-white">{x.slice(0, 44)}…</button>)}</div>
          </div>
          <div className="flex flex-col gap-2 shrink-0">
            <button data-testid="app-generate-btn" onClick={generate} disabled={busy || brief.trim().length < 10} className="btn-primary flex items-center gap-2 disabled:opacity-50">{busy ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} {busy ? "Architecting (30–60s)…" : spec ? "Regenerate blueprint" : "Generate blueprint"}</button>
            <button data-testid="app-long-brief-btn" onClick={() => setBriefOpen(true)} className="btn-ghost flex items-center gap-2 text-sm"><FileUp size={14} /> Upload doc / long brief</button>
            <button data-testid="app-sync-btn" onClick={syncFromSite} disabled={syncing} className="btn-ghost flex items-center gap-2 text-sm !border-[var(--cyan,#14B8A6)]/50 text-[var(--acc)] disabled:opacity-50">{syncing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} {syncing ? "Reading your site…" : spec ? "Re-sync app from my site" : "Build app from my site"}</button>
            <button data-testid="app-templates-btn" onClick={() => setTplOpen(!tplOpen)} className="btn-ghost flex items-center gap-2 text-sm !border-[var(--acc)]/50 text-[var(--acc)]"><LayoutGrid size={14} /> Industry templates ({templates.length})</button>
          </div>
        </div>
        <div data-testid="app-sync-bar" className="mt-4 flex flex-wrap items-center gap-3 border-t border-[var(--line)] pt-3">
          <label className="flex items-center gap-2 text-xs cursor-pointer">
            <input data-testid="app-sync-toggle" type="checkbox" checked={sync.enabled} onChange={e => toggleSync(e.target.checked)} className="accent-[var(--acc)]" />
            <span className="text-[var(--mut)]">Keep this app in sync with Site Mode — rebuild it automatically whenever the website changes</span>
          </label>
          {sync.last_sync && <span data-testid="app-sync-status" className="font-mono text-[10px] text-[var(--dim)] ml-auto">Last synced {new Date(sync.last_sync).toLocaleString()}</span>}
        </div>
        {sync.last_summary && <div data-testid="app-sync-summary" className="mt-2 text-xs text-[var(--mut)] bg-white/5 rounded-xl px-3 py-2">{sync.last_summary}</div>}
        {tplOpen && <div data-testid="template-library" className="mt-5 grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {templates.map(t => <button key={t.key} data-testid={`template-${t.key}`} onClick={() => applyTemplate(t.key)} className="card-lift text-left p-4 rounded-2xl border border-[var(--line)] bg-[var(--bg-2)] relative overflow-hidden">
            <span className="absolute inset-x-0 top-0 h-1" style={{ background: `linear-gradient(90deg, ${t.primary}, ${t.secondary})` }} />
            <div className="flex items-center gap-2 mt-1"><span className="w-3 h-3 rounded-full" style={{ background: t.primary }} /><div className="font-display font-semibold text-sm">{t.name}</div></div>
            <div className="text-[10px] font-mono text-[var(--mut)] mt-1">{t.suite} suite · {t.screens} screens · {t.models} models</div></button>)}
        </div>}
        <div className="hidden">
        </div>
      </div>

      {loading ? null : !spec ? (
        <div className="card-surface p-12 text-center text-[var(--mut)] text-sm">No blueprint yet. Pick an <button onClick={() => setTplOpen(true)} className="text-[var(--acc)] underline">industry template</button> or describe your app above — the result becomes a navigable prototype here and React + FastAPI starter code in the .zip export.</div>
      ) : (
        <div className="grid lg:grid-cols-[300px_1fr_280px] gap-5">
          <aside className="space-y-4">
            <div className="card-surface p-3 flex flex-col h-[560px]" data-testid="app-chat-panel">
              <div className="overline px-1 mb-2 flex items-center gap-2"><Sparkles size={11} className="text-[var(--acc)]" /> Ask AI to build or modify</div>
              <div className="flex-1 overflow-y-auto scrollbar-thin space-y-2 px-1 text-xs">
                {chat.length === 0 && <div className="text-[var(--mut)] p-2">Click any element in the preview to target it, then describe the change — e.g. “add a status filter dropdown to this table”.</div>}
                {chat.map((m, i) => <div key={i} data-testid={`app-chat-${m.role}`} className={`px-3 py-2 rounded-xl ${m.role === "user" ? "bg-[var(--acc)]/15 ml-4" : "bg-white/5 mr-4"}`}>{m.target && <div className="text-[9px] font-mono text-[var(--acc)] mb-0.5">@ {m.target.screen} › {m.target.component}</div>}{m.content}</div>)}
                {refining && <div className="px-3 py-2 rounded-xl bg-white/5 mr-4 flex items-center gap-2 text-[var(--mut)]"><Loader2 size={11} className="animate-spin" /> Updating blueprint…</div>}
              </div>
              {target && <div data-testid="app-chat-target" className="mt-2 mx-1 px-2 py-1 rounded-lg bg-orange-500/15 border border-orange-500/40 text-[10px] font-mono text-orange-300 flex justify-between">Target: {target.screen} › {target.component}<button onClick={() => setTarget(null)}>✕</button></div>}
              <div className="mt-2 flex gap-1"><input data-testid="app-chat-input" value={msg} onChange={e => setMsg(e.target.value)} onKeyDown={e => e.key === "Enter" && refine()} placeholder="Describe a change…" className="flex-1 bg-[var(--bg-2)] border border-[var(--line)] rounded-full px-3 py-2 text-xs outline-none focus:border-[var(--acc)]" /><button data-testid="app-chat-send-btn" onClick={refine} disabled={refining || !msg.trim()} className="btn-primary !py-2 !px-3 text-xs disabled:opacity-50">Send</button></div>
            </div>
            <div className="card-surface p-3">
              <div className="overline mb-2 px-1 flex items-center gap-2"><Route size={11} /> Screens · {spec.screens?.length}</div>
              {spec.screens?.map((sc, i) => <button key={i} data-testid={`blueprint-screen-${i}`} onClick={() => setScreen(i)} className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center justify-between ${screen === i ? "bg-[var(--acc)]/10 border border-[var(--acc)]/30" : "hover:bg-white/5 border border-transparent"}`}><span className="truncate">{sc.name}</span><span className="font-mono text-[10px] text-[var(--dim)]">{sc.route}</span></button>)}
            </div>
            <div className="card-surface p-3">
              <div className="overline mb-2 px-1 flex items-center gap-2"><Shield size={11} /> Roles</div>
              <div className="flex flex-wrap gap-1 px-1">{(spec.roles || []).map(r => <span key={r} className="chip">{r}</span>)}</div>
              {spec.integrations?.length > 0 && <><div className="overline mb-2 mt-3 px-1 flex items-center gap-2"><Plug size={11} /> Integrations</div><div className="flex flex-wrap gap-1 px-1">{spec.integrations.map(r => <span key={r} className="chip chip-handover">{r}</span>)}</div></>}
            </div>
          </aside>

          <div>
            <div className={`rounded-2xl border border-[var(--line)] overflow-hidden shadow-2xl ${dark ? "bg-slate-900 text-slate-100" : "bg-white text-slate-900"}`} data-testid="blueprint-prototype" style={{ "--tp": accent }}>
              <div className="bg-[#0B0F17] px-3 py-2 flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-red-400/80" /><span className="w-2.5 h-2.5 rounded-full bg-amber-400/80" /><span className="w-2.5 h-2.5 rounded-full bg-emerald-400/80" /><span className="ml-3 text-[10px] font-mono text-white/40">{spec.name?.toLowerCase().replace(/\s+/g, "")}.app{s?.route}</span>
                <button data-testid="proto-theme-toggle" onClick={() => setDark(!dark)} className="ml-auto text-[10px] font-mono text-white/60 hover:text-white px-2 py-0.5 rounded border border-white/10">{dark ? "☾ dark" : "☀ light"}</button></div>
              <div className={`px-4 py-2 text-[11px] font-mono border-b flex items-center gap-2 ${dark ? "border-slate-800 text-slate-400" : "border-slate-200 text-slate-500"}`} data-testid="proto-breadcrumbs"><span>{spec.name}</span><span>›</span><span style={{ color: accent }}>{s?.name}</span><span className="ml-auto flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> live · {spec.roles?.[0] || "admin"}</span></div>
              <div className="flex">
                <div className={`w-44 border-r p-3 space-y-1 min-h-[520px] ${dark ? "border-slate-800 bg-slate-950" : "border-slate-200 bg-slate-50"}`}>
                  <div className="font-bold text-sm px-2 py-2 flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: accent }} />{spec.name}</div>
                  {spec.screens?.filter(x => x.nav !== false).map((sc, i) => { const idx = spec.screens.indexOf(sc); return <button key={i} data-testid={`proto-nav-${idx}`} onClick={() => setScreen(idx)} className={`w-full text-left text-xs px-2 py-1.5 rounded-lg transition-colors ${idx === screen ? "text-white" : dark ? "text-slate-400 hover:bg-slate-800" : "text-slate-600 hover:bg-slate-200"}`} style={idx === screen ? { background: accent } : {}}>{sc.name}</button>; })}
                </div>
                <div className="flex-1 p-6 space-y-5 max-h-[560px] overflow-y-auto" style={{ background: dark ? "#0F172A" : `radial-gradient(1200px 400px at 80% -10%, ${accent}14, transparent), #F8FAFC` }}>
                  <div><h2 className="text-xl font-bold">{s?.name}</h2><p className="text-xs text-slate-500 mt-1">{s?.description}</p></div>
                  {s?.components?.map((c, i) => { const I = COMP_ICON[c.type] || Layout; const hit = target?.screen === s.name && target?.component === (c.label || c.type); return <div key={i} data-testid={`proto-component-${i}`} onClick={() => setTarget({ screen: s.name, component: c.label || c.type })} style={hit ? { borderColor: accent, boxShadow: `0 0 0 3px ${accent}33` } : {}} className={`card-lift rounded-2xl border p-4 cursor-pointer ${dark ? "bg-slate-900 border-slate-800" : "bg-white border-slate-200"}`}><div className="flex items-center gap-2 text-xs font-semibold text-slate-700 mb-3"><I size={13} style={{ color: accent }} /> {c.label || c.type}{c.model && <span className="ml-auto font-mono text-[10px] text-teal-600">{c.model}</span>}</div><Mock c={c} accent={accent} /></div>; })}
                </div>
              </div>
            </div>
            <div className="text-center text-[10px] font-mono text-[var(--dim)] mt-2">Live prototype · click any element to target it, then describe the change in chat</div>
          </div>

          <aside className="space-y-4">
            <div className="card-surface p-4">
              <div className="overline mb-3 flex items-center gap-2"><Database size={11} /> Data models · {spec.models?.length}</div>
              <div className="space-y-3 max-h-[40vh] overflow-y-auto scrollbar-thin">
                {spec.models?.map((m, i) => <div key={i} data-testid={`blueprint-model-${i}`}><div className="text-sm font-semibold">{m.name}</div><div className="mt-1 space-y-0.5">{m.fields?.map((f, k) => <div key={k} className="flex justify-between text-[11px] font-mono"><span className="text-[var(--mut)]">{f.name}{f.required && <span className="text-[var(--acc)]">*</span>}</span><span className="text-[var(--dim)]">{f.type}</span></div>)}</div></div>)}
              </div>
            </div>
            <div className="card-surface p-4">
              <div className="overline mb-3">API · {spec.api?.length}</div>
              <div className="space-y-1 max-h-[24vh] overflow-y-auto scrollbar-thin">{spec.api?.map((a, i) => <div key={i} className="flex gap-2 text-[11px] font-mono"><span className={`w-12 ${a.method === "GET" ? "text-teal-400" : a.method === "DELETE" ? "text-red-400" : "text-amber-300"}`}>{a.method}</span><span className="text-[var(--mut)] truncate">{a.path}</span></div>)}</div>
            </div>
            <a data-testid="blueprint-export-link" href={`${apiRoot}/apps/${appId}/export/source`} className="btn-primary w-full flex items-center justify-center gap-2 text-sm"><Download size={14} /> Download starter code (.zip)</a>
            <p className="text-[11px] text-[var(--mut)]">React (Vite-free CRA) + FastAPI + Mongo scaffold with CRUD per model, pages per screen, and this blueprint.json.</p>
          </aside>
        </div>
      )}
    </div>
  );
}
