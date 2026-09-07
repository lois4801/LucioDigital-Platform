import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Sparkles, Loader2, Database, Route, Layout, Shield, Plug, Download, Table, FormInput, BarChart3, LayoutGrid, MessageSquare, Settings, KanbanSquare, Calendar, LogIn } from "lucide-react";

const COMP_ICON = { table: Table, list: Table, form: FormInput, stats: BarChart3, chart: BarChart3, cards: LayoutGrid, chat: MessageSquare, settings: Settings, kanban: KanbanSquare, calendar: Calendar, auth: LogIn, detail: Layout, hero: Layout, navbar: Layout };
const EXAMPLES = ["Patient booking app for a dental clinic: appointments, patients, treatments, invoices, SMS reminders", "Field-service CRM for HVAC technicians with jobs, dispatch board, quotes and customer portal", "Internal tool for tracking influencer campaigns, budgets and content approvals"];

function Mock({ c }) {
  const fields = c.fields?.length ? c.fields : ["Name", "Status", "Updated"];
  const t = c.type;
  if (t === "stats") return <div className="grid grid-cols-3 gap-3">{fields.slice(0, 3).map(f => <div key={f} className="rounded-xl border border-slate-200 p-4"><div className="text-[10px] uppercase text-slate-500">{f}</div><div className="text-2xl font-bold mt-1 text-slate-900">{Math.floor(Math.random() * 900 + 100)}</div></div>)}</div>;
  if (t === "table" || t === "list") return <table className="w-full text-xs"><thead><tr className="text-left text-slate-500 border-b border-slate-200">{fields.slice(0, 5).map(f => <th key={f} className="py-2 font-medium">{f}</th>)}</tr></thead><tbody>{[1, 2, 3].map(r => <tr key={r} className="border-b border-slate-100">{fields.slice(0, 5).map((f, i) => <td key={f} className="py-2.5 text-slate-700">{i === 0 ? `Sample ${r}` : i === 1 ? <span className="px-2 py-0.5 rounded-full bg-teal-50 text-teal-700 text-[10px]">Active</span> : "—"}</td>)}</tr>)}</tbody></table>;
  if (t === "form" || t === "settings" || t === "auth") return <div className="grid sm:grid-cols-2 gap-3">{fields.slice(0, 6).map(f => <div key={f}><div className="text-[10px] text-slate-500 mb-1">{f}</div><div className="h-9 rounded-lg border border-slate-200 bg-white" /></div>)}<div className="sm:col-span-2"><span className="inline-block px-5 py-2 rounded-full bg-orange-500 text-white text-xs font-semibold">Save</span></div></div>;
  if (t === "chart") return <div className="h-28 flex items-end gap-2">{[40, 70, 55, 90, 65, 100, 80].map((h, i) => <div key={i} className="flex-1 rounded-t-md" style={{ height: `${h}%`, background: "linear-gradient(180deg,#F97316,#14B8A6)" }} />)}</div>;
  if (t === "kanban") return <div className="grid grid-cols-3 gap-3">{["Todo", "In progress", "Done"].map(col => <div key={col} className="rounded-xl bg-slate-50 p-3"><div className="text-[10px] uppercase text-slate-500 mb-2">{col}</div>{[1, 2].map(i => <div key={i} className="rounded-lg bg-white border border-slate-200 p-2 text-xs mb-2 text-slate-700">Card {i}</div>)}</div>)}</div>;
  if (t === "chat") return <div className="space-y-2 text-xs"><div className="bg-slate-100 rounded-2xl px-3 py-2 w-2/3 text-slate-700">Hi, how can I help?</div><div className="bg-orange-500 text-white rounded-2xl px-3 py-2 w-1/2 ml-auto">Book an appointment</div></div>;
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
  useEffect(() => { api.get(`/apps/${appId}/ai/app-chat`).then(r => setChat(r.data)).catch(() => {}); }, [appId]);
  async function refine() {
    if (!msg.trim() || refining) return;
    const text = msg; setMsg(""); setRefining(true);
    setChat(c => [...c, { role: "user", content: text, target }]);
    try { const { data } = await api.post(`/apps/${appId}/ai/refine-app`, { message: text, target }, { timeout: 300000 }); setSpec(data.spec); setChat(c => [...c, { role: "assistant", content: data.summary }]); setTarget(null); toast.success("Blueprint updated"); }
    catch (e) { toast.error(e.response?.data?.detail || "Refinement failed"); } finally { setRefining(false); }
  }
  const s = spec?.screens?.[screen];
  return (
    <div data-testid="blueprint-panel" className="space-y-6">
      <div className="card-surface p-5">
        <div className="flex flex-col lg:flex-row lg:items-end gap-4">
          <div className="flex-1">
            <div className="overline mb-1 flex items-center gap-2"><Sparkles size={12} className="text-[var(--acc)]" /> Lovable-style app blueprint</div>
            <h3 className="font-display text-2xl font-semibold tracking-tight">Describe the app — get screens, data models, API and starter code</h3>
            <textarea data-testid="app-brief-input" value={brief} onChange={e => setBrief(e.target.value)} rows={2} placeholder="e.g. Patient booking app for a dental clinic…" className="mt-3 w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-4 py-3 text-sm outline-none focus:border-[var(--acc)] resize-none" />
            <div className="flex flex-wrap gap-2 mt-2">{EXAMPLES.map((x, i) => <button key={i} data-testid={`app-example-${i}`} onClick={() => setBrief(x)} className="chip normal-case tracking-normal cursor-pointer hover:!text-white">{x.slice(0, 44)}…</button>)}</div>
          </div>
          <button data-testid="app-generate-btn" onClick={generate} disabled={busy || brief.trim().length < 10} className="btn-primary flex items-center gap-2 disabled:opacity-50 shrink-0">{busy ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} {busy ? "Architecting (30–60s)…" : spec ? "Regenerate blueprint" : "Generate blueprint"}</button>
        </div>
      </div>

      {loading ? null : !spec ? (
        <div className="card-surface p-12 text-center text-[var(--mut)] text-sm">No blueprint yet. Describe your app above — the result becomes a navigable prototype here and React + FastAPI starter code in the .zip export.</div>
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
            <div className="rounded-2xl border border-[var(--line)] overflow-hidden shadow-2xl bg-white text-slate-900" data-testid="blueprint-prototype">
              <div className="bg-[#0B0F17] px-3 py-2 flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-red-400/80" /><span className="w-2.5 h-2.5 rounded-full bg-amber-400/80" /><span className="w-2.5 h-2.5 rounded-full bg-emerald-400/80" /><span className="ml-3 text-[10px] font-mono text-white/40">{spec.name?.toLowerCase().replace(/\s+/g, "")}.app{s?.route}</span></div>
              <div className="flex">
                <div className="w-44 border-r border-slate-200 p-3 space-y-1 bg-slate-50 min-h-[520px]">
                  <div className="font-bold text-sm px-2 py-2 text-slate-900">{spec.name}</div>
                  {spec.screens?.filter(x => x.nav !== false).map((sc, i) => { const idx = spec.screens.indexOf(sc); return <button key={i} onClick={() => setScreen(idx)} className={`w-full text-left text-xs px-2 py-1.5 rounded-lg ${idx === screen ? "bg-orange-500 text-white" : "text-slate-600 hover:bg-slate-200"}`}>{sc.name}</button>; })}
                </div>
                <div className="flex-1 p-6 space-y-5 max-h-[560px] overflow-y-auto">
                  <div><h2 className="text-xl font-bold">{s?.name}</h2><p className="text-xs text-slate-500 mt-1">{s?.description}</p></div>
                  {s?.components?.map((c, i) => { const I = COMP_ICON[c.type] || Layout; const hit = target?.screen === s.name && target?.component === (c.label || c.type); return <div key={i} data-testid={`proto-component-${i}`} onClick={() => setTarget({ screen: s.name, component: c.label || c.type })} className={`rounded-2xl border p-4 cursor-pointer transition-colors ${hit ? "border-orange-500 ring-2 ring-orange-500/30 bg-orange-50" : "border-slate-200 hover:border-orange-300"}`}><div className="flex items-center gap-2 text-xs font-semibold text-slate-700 mb-3"><I size={13} className="text-orange-500" /> {c.label || c.type}{c.model && <span className="ml-auto font-mono text-[10px] text-teal-600">{c.model}</span>}</div><Mock c={c} /></div>; })}
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
