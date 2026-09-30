import { useEffect, useMemo, useRef, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import {
  Bot, BrainCircuit, Check, ChevronRight, CircleAlert, Code2, ExternalLink,
  FileCode2, GitBranch, Loader2, Play, RefreshCw, Save, ShieldCheck,
  Sparkles, TerminalSquare, TestTube2, X, Zap,
} from "lucide-react";

type AnyDoc = Record<string, any>;

const RUNNING = new Set(["preparing", "planning", "queued", "running"]);

function Badge({ children, tone = "default" }: { children: React.ReactNode; tone?: string }) {
  const cls = tone === "ok" ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
    : tone === "warn" ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
    : tone === "bad" ? "border-red-500/30 bg-red-500/10 text-red-300"
    : "border-[var(--line)] bg-white/[.035] text-[var(--mut)]";
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium ${cls}`}>{children}</span>;
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`rounded-2xl border border-[var(--line)] bg-[var(--bg-2)]/70 ${className}`}>{children}</section>;
}

function prettyStatus(status?: string) {
  return (status || "idle").replaceAll("_", " ");
}

function Verification({ value }: { value?: AnyDoc }) {
  if (!value) return null;
  const results = value.results || [];
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 font-semibold"><TestTube2 size={16} /> Verification</div>
        <Badge tone={value.ok ? "ok" : "bad"}>{value.ok ? "PASS" : "FAILED"}</Badge>
      </div>
      {!results.length && <div className="mt-3 text-sm text-[var(--mut)]">No project verification command was detected. Add commands in Dev Agent settings if this project needs them.</div>}
      <div className="mt-4 space-y-3">
        {results.map((r: AnyDoc, i: number) => (
          <div key={i} className="rounded-xl border border-[var(--line)] bg-black/20 p-3">
            <div className="flex items-center justify-between gap-3 text-xs">
              <code>{(r.argv || []).join(" ")}</code>
              <Badge tone={r.ok ? "ok" : "bad"}>{r.ok ? "pass" : `exit ${r.returncode}`}</Badge>
            </div>
            {r.output && <pre className="mt-2 max-h-44 overflow-auto whitespace-pre-wrap text-[11px] text-[var(--mut)]">{r.output}</pre>}
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function DevAgentPanel({ appId, appDoc }: { appId: string; appDoc?: AnyDoc }) {
  const [platform, setPlatform] = useState<AnyDoc | null>(null);
  const [config, setConfig] = useState<AnyDoc>({ repo_url: "", branch: "main" });
  const [sessions, setSessions] = useState<AnyDoc[]>([]);
  const [active, setActive] = useState<AnyDoc | null>(null);
  const [goal, setGoal] = useState("");
  const [instruction, setInstruction] = useState("");
  const [busy, setBusy] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const activeId = active?.session_id;
  const pollRef = useRef<number | null>(null);

  async function loadBase() {
    try {
      const [s, c, list] = await Promise.all([
        api.get("/dev-agent/status"),
        api.get(`/apps/${appId}/dev-agent/config`),
        api.get(`/apps/${appId}/dev-agent/sessions`),
      ]);
      setPlatform(s.data);
      setConfig(c.data || { repo_url: "", branch: "main" });
      setSessions(list.data || []);
      if (!activeId && list.data?.length) setActive(list.data[0]);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not load Lucio Dev Agent");
    }
  }

  async function refreshSession(id = activeId, quiet = false) {
    if (!id) return;
    try {
      const { data } = await api.get(`/apps/${appId}/dev-agent/sessions/${id}`);
      setActive(data);
      setSessions((xs) => [data, ...xs.filter((x) => x.session_id !== data.session_id)].slice(0, 30));
    } catch (e: any) {
      if (!quiet) toast.error(e.response?.data?.detail || "Could not refresh the agent run");
    }
  }

  useEffect(() => { loadBase(); }, [appId]);
  useEffect(() => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    if (activeId && RUNNING.has(active?.status)) {
      pollRef.current = window.setInterval(() => refreshSession(activeId, true), 1800);
    }
    return () => { if (pollRef.current) window.clearInterval(pollRef.current); };
  }, [activeId, active?.status]);

  async function saveConfig() {
    setBusy("config");
    try {
      const body: AnyDoc = { repo_url: config.repo_url?.trim() || null, branch: config.branch?.trim() || "main" };
      if (showAdvanced) {
        if (config.preview_text?.trim()) body.preview_argv = config.preview_text.trim().split(/\s+/);
        if (config.verify_text?.trim()) {
          body.verify_commands = config.verify_text.split("\n").map((x: string) => x.trim()).filter(Boolean).map((x: string) => x.split(/\s+/));
        }
      }
      const { data } = await api.patch(`/apps/${appId}/dev-agent/config`, body);
      setConfig((c: AnyDoc) => ({ ...c, ...data }));
      toast.success("Dev Agent project connection saved");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not save Dev Agent settings");
    } finally { setBusy(""); }
  }

  async function createRun(auto = false) {
    if (!goal.trim()) return toast.error("Tell Lucio what you want to build or improve first");
    if (!config.repo_url?.trim()) return toast.error("Connect this app to its GitHub repository first");
    setBusy("create");
    try {
      const { data } = await api.post(`/apps/${appId}/dev-agent/sessions`, {
        goal: goal.trim(), repo_url: config.repo_url.trim(), branch: config.branch || "main", auto_execute: auto,
      });
      setActive(data);
      setSessions((xs) => [data, ...xs.filter((x) => x.session_id !== data.session_id)]);
      if (data.status === "failed") toast.error(data.error || "Dev Agent could not start");
      else toast.success(auto ? "Lucio is building in an isolated workspace" : "Development plan is ready");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not start Dev Agent");
    } finally { setBusy(""); }
  }

  async function execute() {
    if (!activeId) return;
    setBusy("execute");
    try {
      await api.post(`/apps/${appId}/dev-agent/sessions/${activeId}/execute`, { max_steps: 16, start_preview: true });
      setActive((x: AnyDoc) => ({ ...x, status: "queued" }));
      toast.success("Agentic coding loop started");
    } catch (e: any) { toast.error(e.response?.data?.detail || "Could not run the coding agent"); }
    finally { setBusy(""); }
  }

  async function continueRun() {
    if (!activeId || !instruction.trim()) return;
    setBusy("continue");
    try {
      await api.post(`/apps/${appId}/dev-agent/sessions/${activeId}/continue`, { instruction: instruction.trim(), max_steps: 12, start_preview: true });
      setInstruction("");
      setActive((x: AnyDoc) => ({ ...x, status: "queued" }));
      toast.success("Follow-up sent to the coding agents");
    } catch (e: any) { toast.error(e.response?.data?.detail || "Could not continue the run"); }
    finally { setBusy(""); }
  }

  async function decide(state: "approve" | "reject") {
    if (!activeId) return;
    if (state === "reject" && !confirm("Reject this change set? The isolated workspace will be kept so you can still inspect it.")) return;
    setBusy(state);
    try {
      await api.post(`/apps/${appId}/dev-agent/sessions/${activeId}/${state}`, { note: "", cleanup_workspace: false });
      await refreshSession(activeId);
      toast.success(state === "approve" ? "Change set approved" : "Change set rejected");
    } catch (e: any) { toast.error(e.response?.data?.detail || `Could not ${state} this run`); }
    finally { setBusy(""); }
  }

  const runnerOk = !!platform?.runner?.reachable;
  const aiOk = !!platform?.llm_available;
  const events = active?.events || [];
  const planTasks = active?.plan?.tasks || [];
  const diff = active?.diff?.diff || "";
  const untracked = active?.diff?.untracked || [];
  const canExecute = active && ["planned", "failed", "completed", "approved", "rejected"].includes(active.status);
  const previewUrl = active?.preview?.url;

  return (
    <div className="space-y-6" data-testid="dev-agent-panel">
      <Card className="overflow-hidden">
        <div className="border-b border-[var(--line)] bg-gradient-to-r from-violet-500/10 via-cyan-500/5 to-transparent p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[.18em] text-violet-300"><Sparkles size={14} /> Goal → Working App</div>
              <h2 className="font-display text-2xl font-semibold">Lucio Dev Agent</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--mut)]">Plan, inspect, edit, test, repair and preview application code in an isolated Nexus Runner workspace. Production remains untouched until you review the change set.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge tone={aiOk ? "ok" : "bad"}><BrainCircuit size={12} className="mr-1" /> AI {aiOk ? "ready" : "not configured"}</Badge>
              <Badge tone={runnerOk ? "ok" : platform?.runner?.configured ? "warn" : "bad"}><TerminalSquare size={12} className="mr-1" /> Runner {runnerOk ? "online" : platform?.runner?.configured ? "offline" : "not configured"}</Badge>
              <Badge tone="ok"><ShieldCheck size={12} className="mr-1" /> isolated</Badge>
            </div>
          </div>
        </div>

        <div className="grid gap-5 p-6 lg:grid-cols-[1fr_220px]">
          <div>
            <label className="mb-2 block text-xs font-medium uppercase tracking-wider text-[var(--mut)]">GitHub repository</label>
            <div className="grid gap-3 md:grid-cols-[1fr_180px]">
              <div className="relative">
                <Code2 size={15} className="absolute left-3 top-3.5 text-[var(--mut)]" />
                <input value={config.repo_url || ""} onChange={(e) => setConfig((c: AnyDoc) => ({ ...c, repo_url: e.target.value }))}
                  placeholder="https://github.com/owner/project" className="input w-full pl-9" />
              </div>
              <div className="relative">
                <GitBranch size={14} className="absolute left-3 top-3.5 text-[var(--mut)]" />
                <input value={config.branch || "main"} onChange={(e) => setConfig((c: AnyDoc) => ({ ...c, branch: e.target.value }))}
                  placeholder="main" className="input w-full pl-9" />
              </div>
            </div>
            <button onClick={() => setShowAdvanced((x) => !x)} className="mt-3 text-xs text-[var(--mut)] hover:text-white">{showAdvanced ? "Hide" : "Show"} advanced commands</button>
            {showAdvanced && (
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div><label className="mb-1 block text-xs text-[var(--mut)]">Preview command</label><input value={config.preview_text ?? (config.preview_argv || []).join(" ")} onChange={(e) => setConfig((c: AnyDoc) => ({ ...c, preview_text: e.target.value }))} placeholder="npm run dev" className="input w-full font-mono text-xs" /></div>
                <div><label className="mb-1 block text-xs text-[var(--mut)]">Verification commands — one per line</label><textarea value={config.verify_text ?? (config.verify_commands || []).map((x: string[]) => x.join(" ")).join("\n")} onChange={(e) => setConfig((c: AnyDoc) => ({ ...c, verify_text: e.target.value }))} placeholder={"npm run lint\nnpm run build"} className="input min-h-20 w-full font-mono text-xs" /></div>
              </div>
            )}
          </div>
          <div className="flex items-end">
            <button onClick={saveConfig} disabled={!!busy} className="btn-ghost flex w-full items-center justify-center gap-2"><Save size={14} /> {busy === "config" ? "Saving…" : "Save connection"}</button>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Card className="p-6">
            <div className="flex items-center gap-2 font-semibold"><Bot size={17} /> What should Lucio build or improve?</div>
            <textarea value={goal} onChange={(e) => setGoal(e.target.value)} className="input mt-4 min-h-36 w-full resize-y text-sm leading-6"
              placeholder={`Example: Inspect ${appDoc?.name || "this app"}. Add a production-ready client analytics dashboard with API endpoints, responsive UI, tests and error handling. Preserve existing behavior.`} />
            <div className="mt-4 flex flex-wrap gap-3">
              <button onClick={() => createRun(false)} disabled={!!busy || !runnerOk || !aiOk} className="btn-ghost flex items-center gap-2"><BrainCircuit size={15} /> {busy === "create" ? "Planning…" : "Create plan"}</button>
              <button onClick={() => createRun(true)} disabled={!!busy || !runnerOk || !aiOk} className="btn-primary flex items-center gap-2"><Zap size={15} /> Plan & build</button>
            </div>
            {(!runnerOk || !aiOk) && <div className="mt-4 flex gap-2 rounded-xl border border-amber-500/20 bg-amber-500/[.06] p-3 text-xs text-amber-200"><CircleAlert size={15} className="mt-0.5 shrink-0" /> {!runnerOk ? "Deploy/configure Nexus Runner before code execution." : "Configure an LLM provider before starting Dev Agent."}</div>}
          </Card>

          {active && (
            <>
              <Card className="p-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-xs uppercase tracking-wider text-[var(--mut)]">Current run</div>
                    <div className="mt-1 font-semibold">{active.plan?.summary || active.goal}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone={RUNNING.has(active.status) ? "warn" : active.status === "failed" ? "bad" : active.status === "approved" ? "ok" : "default"}>{prettyStatus(active.status)}</Badge>
                    <button onClick={() => refreshSession()} className="rounded-lg border border-[var(--line)] p-2 text-[var(--mut)] hover:text-white"><RefreshCw size={14} /></button>
                  </div>
                </div>

                {!!planTasks.length && (
                  <div className="mt-5 grid gap-3 md:grid-cols-2">
                    {planTasks.map((t: AnyDoc, i: number) => (
                      <div key={t.id || i} className="rounded-xl border border-[var(--line)] bg-black/15 p-4">
                        <div className="flex items-center justify-between gap-2"><span className="text-sm font-semibold">{t.id || `T${i+1}`} · {t.title}</span><Badge>{t.agent || "agent"}</Badge></div>
                        <div className="mt-2 text-xs leading-5 text-[var(--mut)]">{t.description}</div>
                        {!!t.acceptance?.length && <div className="mt-3 space-y-1">{t.acceptance.slice(0, 4).map((a: string, j: number) => <div key={j} className="flex gap-2 text-[11px] text-[var(--mut)]"><Check size={12} className="mt-0.5 shrink-0 text-emerald-400" /> {a}</div>)}</div>}
                      </div>
                    ))}
                  </div>
                )}

                <div className="mt-5 flex flex-wrap gap-3">
                  {canExecute && <button onClick={execute} disabled={!!busy || RUNNING.has(active.status)} className="btn-primary flex items-center gap-2"><Play size={14} /> {busy === "execute" ? "Starting…" : "Run coding agents"}</button>}
                  {RUNNING.has(active.status) && <div className="flex items-center gap-2 text-sm text-[var(--mut)]"><Loader2 size={15} className="animate-spin" /> Lucio is working… this panel refreshes automatically.</div>}
                </div>
              </Card>

              {!!events.length && (
                <Card className="p-6">
                  <div className="flex items-center gap-2 font-semibold"><TerminalSquare size={16} /> Agent timeline</div>
                  <div className="mt-4 max-h-[420px] space-y-2 overflow-auto pr-1">
                    {[...events].reverse().map((e: AnyDoc) => (
                      <div key={e.event_id} className="flex gap-3 rounded-xl border border-[var(--line)] bg-black/10 p-3">
                        <div className={`mt-1 h-2 w-2 shrink-0 rounded-full ${e.kind === "error" ? "bg-red-400" : e.kind.includes("repair") ? "bg-amber-400" : e.kind === "complete" ? "bg-emerald-400" : "bg-violet-400"}`} />
                        <div className="min-w-0 flex-1"><div className="text-xs font-medium">{e.message}</div><div className="mt-1 text-[10px] text-[var(--mut)]">{e.kind} · {e.at ? new Date(e.at).toLocaleString() : ""}</div>{e.data?.detail && <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap text-[10px] text-red-300/80">{e.data.detail}</pre>}</div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              <Verification value={active.verification} />

              {(diff || untracked.length > 0) && (
                <Card className="p-6">
                  <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-2 font-semibold"><FileCode2 size={16} /> Change set</div><Badge>{untracked.length} new file{untracked.length === 1 ? "" : "s"}</Badge></div>
                  {!!active.review && <div className="mt-4 rounded-xl border border-violet-500/20 bg-violet-500/[.05] p-4"><div className="text-xs font-semibold text-violet-200">Reviewer</div><div className="mt-1 text-sm leading-6 text-[var(--mut)]">{active.review.summary}</div>{!!active.review.risks?.length && <div className="mt-2 text-xs text-amber-200">Risks: {active.review.risks.join(" · ")}</div>}</div>}
                  {untracked.length > 0 && <div className="mt-4 flex flex-wrap gap-2">{untracked.map((f: string) => <Badge key={f}>{f}</Badge>)}</div>}
                  {diff && <pre className="mt-4 max-h-[520px] overflow-auto rounded-xl border border-[var(--line)] bg-black/30 p-4 text-[11px] leading-5 text-zinc-300">{diff}</pre>}
                  {active.status === "awaiting_approval" && <div className="mt-5 flex flex-wrap gap-3"><button onClick={() => decide("approve")} disabled={!!busy} className="btn-primary flex items-center gap-2"><Check size={14} /> Approve change set</button><button onClick={() => decide("reject")} disabled={!!busy} className="btn-ghost flex items-center gap-2 text-red-300"><X size={14} /> Reject</button></div>}
                </Card>
              )}

              {previewUrl && (
                <Card className="overflow-hidden">
                  <div className="flex items-center justify-between gap-3 border-b border-[var(--line)] p-4"><div className="font-semibold">Live sandbox preview</div><a href={previewUrl} target="_blank" rel="noreferrer" className="btn-ghost flex items-center gap-2 text-xs">Open <ExternalLink size={12} /></a></div>
                  <iframe src={previewUrl} title="Lucio Dev Agent preview" className="h-[640px] w-full bg-white" sandbox="allow-forms allow-modals allow-popups allow-same-origin allow-scripts" />
                </Card>
              )}

              {!RUNNING.has(active.status) && active.status !== "preparing" && (
                <Card className="p-6">
                  <div className="font-semibold">Continue this build</div>
                  <p className="mt-1 text-xs text-[var(--mut)]">Give the agents another instruction. They will keep the same isolated workspace and current changes.</p>
                  <div className="mt-4 flex flex-col gap-3 md:flex-row"><textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="Example: The mobile navigation still overlaps the hero. Fix it and rerun the build." className="input min-h-20 flex-1" /><button onClick={continueRun} disabled={!!busy || !instruction.trim()} className="btn-ghost self-stretch px-5"><ChevronRight size={16} /></button></div>
                </Card>
              )}
            </>
          )}
        </div>

        <aside className="space-y-4">
          <Card className="p-5">
            <div className="text-sm font-semibold">Development runs</div>
            <div className="mt-3 space-y-2">
              {!sessions.length && <div className="text-xs text-[var(--mut)]">No runs yet.</div>}
              {sessions.map((s) => (
                <button key={s.session_id} onClick={() => { setActive(s); refreshSession(s.session_id, true); }} className={`w-full rounded-xl border p-3 text-left transition ${activeId === s.session_id ? "border-violet-500/40 bg-violet-500/[.07]" : "border-[var(--line)] hover:bg-white/[.03]"}`}>
                  <div className="line-clamp-2 text-xs font-medium leading-5">{s.plan?.summary || s.goal}</div>
                  <div className="mt-2 flex items-center justify-between gap-2"><span className="text-[10px] text-[var(--mut)]">{s.created_at ? new Date(s.created_at).toLocaleDateString() : ""}</span><Badge tone={s.status === "failed" ? "bad" : s.status === "approved" ? "ok" : RUNNING.has(s.status) ? "warn" : "default"}>{prettyStatus(s.status)}</Badge></div>
                </button>
              ))}
            </div>
          </Card>

          <Card className="p-5">
            <div className="text-sm font-semibold">Agent team</div>
            <div className="mt-3 space-y-2 text-xs text-[var(--mut)]">
              {["Orchestrator / planner", "Frontend engineer", "Backend engineer", "Database engineer", "QA + self-healing", "Final reviewer"].map((x) => <div key={x} className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-violet-400" /> {x}</div>)}
            </div>
          </Card>
        </aside>
      </div>
    </div>
  );
}
