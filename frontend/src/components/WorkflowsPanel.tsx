import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Zap, Plus, Trash2, Play, Mail, Database, Webhook, Bell, Filter, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { LockToggle } from "@/components/locks/LockContext";

const ACTION_META = { email: [Mail, "Send email"], db_write: [Database, "Write to database"], webhook: [Webhook, "Call webhook"], notify: [Bell, "Notify team"] };
const EMPTY = { name: "", trigger: "form_submitted", conditions: [], actions: [{ type: "notify", message: "New {{name}} event" }], enabled: true };

export default function WorkflowsPanel({ appId }) {
  const [wfs, setWfs] = useState([]);
  const [triggers, setTriggers] = useState([]);
  const [samples, setSamples] = useState({});
  const [draft, setDraft] = useState(null);
  const [running, setRunning] = useState(null);
  const [emailCfg, setEmailCfg] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [tplOpen, setTplOpen] = useState(false);
  async function installTemplate(key) { try { const { data } = await api.post(`/apps/${appId}/workflows/templates/${key}`); setWfs([data, ...wfs]); setTplOpen(false); toast.success(`Added “${data.name}”`); } catch { toast.error("Failed"); } }

  useEffect(() => { load(); api.get("/settings/email").then(r => setEmailCfg(r.data)).catch(() => {}); api.get("/workflows/templates").then(r => setTemplates(r.data)).catch(() => {}); }, [appId]);
  async function load() { const { data } = await api.get(`/apps/${appId}/workflows`); setWfs(data.workflows); setTriggers(data.triggers); setSamples(data.samples); }
  async function save() {
    if (!draft.name.trim()) return toast.error("Name required");
    try {
      if (draft.workflow_id) { const { data } = await api.put(`/apps/${appId}/workflows/${draft.workflow_id}`, draft); setWfs(wfs.map(w => w.workflow_id === data.workflow_id ? data : w)); }
      else { const { data } = await api.post(`/apps/${appId}/workflows`, draft); setWfs([data, ...wfs]); }
      setDraft(null); toast.success("Workflow saved");
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
  }
  async function test(w) {
    setRunning(w.workflow_id);
    try { const { data } = await api.post(`/apps/${appId}/workflows/${w.workflow_id}/test`, {}); setWfs(wfs.map(x => x.workflow_id === w.workflow_id ? { ...x, last_run: { ...data, test: true, at: new Date().toISOString() } } : x)); toast[data.status === "completed" ? "success" : "info"](`Test run ${data.status}`); }
    catch { toast.error("Test failed"); } finally { setRunning(null); }
  }
  async function toggle(w) { const { data } = await api.put(`/apps/${appId}/workflows/${w.workflow_id}`, { ...w, enabled: !w.enabled }); setWfs(wfs.map(x => x.workflow_id === w.workflow_id ? data : x)); }
  async function del(w) { if (!confirm("Delete workflow?")) return; await api.delete(`/apps/${appId}/workflows/${w.workflow_id}`); setWfs(wfs.filter(x => x.workflow_id !== w.workflow_id)); }
  const setAction = (i, patch) => setDraft({ ...draft, actions: draft.actions.map((a, k) => k === i ? { ...a, ...patch } : a) });
  const setCond = (i, patch) => setDraft({ ...draft, conditions: draft.conditions.map((c, k) => k === i ? { ...c, ...patch } : c) });
  const inp = "bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2 py-1.5 text-xs outline-none focus:border-[var(--acc)]";

  return (
    <div data-testid="workflows-panel" className="grid lg:grid-cols-[1fr_420px] gap-6">
      <div className="space-y-4">
        <div className="flex items-end justify-between">
          <div><div className="overline mb-1 flex items-center gap-2"><Zap size={12} className="text-[var(--acc)]" /> Workflow engine</div>
            <h3 className="font-display text-2xl font-semibold tracking-tight">Trigger → conditions → actions</h3>
            <p className="text-sm text-[var(--mut)] mt-1">Automations run when leads arrive, chats start, payments succeed or members join. Emails send via LucioDigital mail{emailCfg && !emailCfg.configured && " (not configured — queued)"}.</p></div>
          <div className="flex gap-2">
            <button data-testid="workflow-templates-btn" onClick={() => setTplOpen(!tplOpen)} className="btn-ghost text-sm !py-2 !px-4">Projects</button>
            <button data-testid="workflow-new-btn" onClick={() => setDraft({ ...EMPTY })} className="btn-primary text-sm !py-2 !px-4 flex items-center gap-2"><Plus size={14} /> New workflow</button>
          </div>
        </div>
        {tplOpen && <div data-testid="workflow-templates-list" className="card-surface p-4 grid md:grid-cols-2 gap-2">
          {templates.map(t => <button key={t.key} data-testid={`workflow-template-${t.key}`} onClick={() => installTemplate(t.key)} className="text-left p-3 rounded-xl border border-[var(--line)] hover:border-[var(--acc)]/50 hover:bg-white/3">
            <div className="text-sm font-semibold flex items-center gap-2"><Zap size={12} className="text-[var(--acc)]" /> {t.name}</div>
            <div className="text-[11px] font-mono text-[var(--mut)] mt-1">on {t.trigger} → {t.actions.map(a => a.type).join(" + ")}</div></button>)}
        </div>}
        {wfs.length === 0 && <div className="card-surface p-10 text-center text-sm text-[var(--mut)]">No workflows yet. Try “When a form is submitted → email the lead + notify team”.</div>}
        {wfs.map(w => (
          <div key={w.workflow_id} data-testid="workflow-card" className="group card-surface p-5">
            <div className="flex items-center gap-3">
              <LockToggle kind="workflow" itemId={w.workflow_id} name={w.name} alwaysVisible />
              <Switch data-testid="workflow-enabled-toggle" checked={w.enabled} onCheckedChange={() => toggle(w)} />
              <div className="flex-1 min-w-0"><div className="font-semibold">{w.name}</div><div className="text-[11px] font-mono text-[var(--mut)]">on {w.trigger} · {w.conditions.length} condition{w.conditions.length !== 1 && "s"} · {w.actions.length} action{w.actions.length !== 1 && "s"} · {w.runs || 0} runs</div></div>
              <button data-testid="workflow-test-btn" onClick={() => test(w)} disabled={running === w.workflow_id} className="btn-ghost text-xs !py-1.5 !px-3 flex items-center gap-1">{running === w.workflow_id ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />} Test run</button>
              <button data-testid="workflow-edit-btn" onClick={() => setDraft(w)} className="btn-ghost text-xs !py-1.5 !px-3">Edit</button>
              <button onClick={() => del(w)} className="w-8 h-8 rounded-full border border-[var(--line)] flex items-center justify-center hover:text-red-400"><Trash2 size={12} /></button>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-2 text-[11px] font-mono">
              <span className="chip chip-active"><Zap size={10} /> {w.trigger}</span>
              {w.conditions.map((c, i) => <span key={i} className="chip chip-maint"><Filter size={10} /> {c.field} {c.op} {c.value}</span>)}
              {w.actions.map((a, i) => { const [I, l] = ACTION_META[a.type] || [Bell, a.type]; return <span key={i} className="chip chip-handover"><I size={10} /> {l}</span>; })}
            </div>
            {w.last_run && <div data-testid="workflow-last-run" className="mt-3 p-3 rounded-lg bg-[var(--bg-2)] border border-[var(--line)] text-[11px] font-mono space-y-1">
              <div className="text-[var(--dim)]">Last run {w.last_run.test ? "(test)" : ""} · {new Date(w.last_run.at).toLocaleString()} · {w.last_run.status}</div>
              {w.last_run.steps?.map((s, i) => <div key={i} className="flex items-center gap-2">{["pass", "sent", "written", "logged"].includes(s.result) || String(s.result).startsWith("HTTP 2") ? <CheckCircle2 size={11} className="text-[var(--acc)]" /> : <XCircle size={11} className="text-amber-400" />}<span className="text-[var(--mut)]">{s.kind}</span> {s.detail} <span className="ml-auto">{s.result}{s.info && ` · ${s.info}`}</span></div>)}
            </div>}
          </div>
        ))}
      </div>

      <aside>
        {draft ? (
          <div className="card-surface p-5 space-y-4 sticky top-28" data-testid="workflow-editor">
            <div className="overline">{draft.workflow_id ? "Edit workflow" : "New workflow"}</div>
            <input data-testid="workflow-name-input" value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} placeholder="Workflow name" className={`w-full ${inp} !py-2`} />
            <div><div className="text-[10px] text-[var(--dim)] uppercase mb-1">1 · Trigger</div>
              <select data-testid="workflow-trigger-select" value={draft.trigger} onChange={e => setDraft({ ...draft, trigger: e.target.value })} className={`w-full ${inp}`}>{triggers.map(t => <option key={t} value={t}>{t.replace("_", " ")}</option>)}</select>
              <div className="text-[10px] text-[var(--dim)] mt-1 font-mono">fields: {Object.keys(samples[draft.trigger] || {}).join(", ")}</div></div>
            <div><div className="text-[10px] text-[var(--dim)] uppercase mb-1 flex justify-between">2 · Conditions <button data-testid="workflow-add-condition-btn" onClick={() => setDraft({ ...draft, conditions: [...draft.conditions, { field: "email", op: "contains", value: "" }] })} className="text-[var(--acc)] normal-case">+ add</button></div>
              {draft.conditions.map((c, i) => <div key={i} className="grid grid-cols-[1fr_70px_1fr_20px] gap-1 mb-1">
                <input value={c.field} onChange={e => setCond(i, { field: e.target.value })} placeholder="field" className={inp} />
                <select value={c.op} onChange={e => setCond(i, { op: e.target.value })} className={inp}>{["==", "!=", "contains", ">", "<"].map(o => <option key={o}>{o}</option>)}</select>
                <input value={c.value} onChange={e => setCond(i, { value: e.target.value })} placeholder="value" className={inp} />
                <button onClick={() => setDraft({ ...draft, conditions: draft.conditions.filter((_, k) => k !== i) })} className="text-[var(--dim)] hover:text-red-400"><Trash2 size={11} /></button></div>)}
              {draft.conditions.length === 0 && <div className="text-[11px] text-[var(--dim)]">Always runs.</div>}</div>
            <div><div className="text-[10px] text-[var(--dim)] uppercase mb-1 flex justify-between">3 · Actions <span className="flex gap-2">{Object.keys(ACTION_META).map(t => <button key={t} data-testid={`workflow-add-action-${t}`} onClick={() => setDraft({ ...draft, actions: [...draft.actions, { type: t }] })} className="text-[var(--acc)] normal-case">+{t.split("_")[0]}</button>)}</span></div>
              {draft.actions.map((a, i) => { const [I, l] = ACTION_META[a.type]; return <div key={i} className="p-2 rounded-lg border border-[var(--line)] mb-2 space-y-1">
                <div className="flex items-center gap-2 text-xs font-semibold"><I size={12} className="text-[var(--acc)]" /> {l}<button onClick={() => setDraft({ ...draft, actions: draft.actions.filter((_, k) => k !== i) })} className="ml-auto text-[var(--dim)] hover:text-red-400"><Trash2 size={11} /></button></div>
                {a.type === "email" && <><div className="text-[10px] text-[var(--dim)]">To: the event's email address</div><input value={a.subject || ""} onChange={e => setAction(i, { subject: e.target.value })} placeholder="Subject — use {{name}}" className={`w-full ${inp}`} /><textarea value={a.body || ""} onChange={e => setAction(i, { body: e.target.value })} rows={2} placeholder="Body" className={`w-full ${inp}`} /></>}
                {a.type === "db_write" && <input value={a.collection || ""} onChange={e => setAction(i, { collection: e.target.value })} placeholder="collection name" className={`w-full ${inp}`} />}
                {a.type === "webhook" && <input value={a.url || ""} onChange={e => setAction(i, { url: e.target.value })} placeholder="https://hooks.example.com/…" className={`w-full ${inp}`} />}
                {a.type === "notify" && <input value={a.message || ""} onChange={e => setAction(i, { message: e.target.value })} placeholder="Message — use {{name}}" className={`w-full ${inp}`} />}
              </div>; })}</div>
            <div className="flex gap-2"><button data-testid="workflow-save-btn" onClick={save} className="btn-primary text-sm !py-2 flex-1">Save workflow</button><button onClick={() => setDraft(null)} className="btn-ghost text-sm !py-2 !px-4">Cancel</button></div>
          </div>
        ) : <div className="card-surface p-5 text-sm text-[var(--mut)]"><div className="overline mb-2">Ideas</div><ul className="space-y-2">{["Form submitted → email lead + notify team", "Payment succeeded → if tier == pro → webhook to Slack", "Chat lead → write to database", "Member invited → welcome email"].map(x => <li key={x} className="flex gap-2"><Zap size={12} className="text-[var(--acc)] mt-0.5" />{x}</li>)}</ul></div>}
      </aside>
    </div>
  );
}
