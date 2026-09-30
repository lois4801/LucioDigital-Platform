import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { toast } from "sonner";
import {
  Bot, BrainCircuit, CheckCircle2, ChevronRight, CircleAlert, Cpu, GitBranch,
  Loader2, Play, RefreshCw, Rocket, ShieldCheck, Sparkles, TerminalSquare,
  WandSparkles,
} from "lucide-react";

type Doc = Record<string, any>;

type Props = {
  apps: Doc[];
  onCreateProject: () => void;
};

function StatusPill({ ok, label, warn = false }: { ok: boolean; label: string; warn?: boolean }) {
  const cls = ok
    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
    : warn
      ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
      : "border-red-500/30 bg-red-500/10 text-red-300";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-emerald-400" : warn ? "bg-amber-400" : "bg-red-400"}`} />
      {label}
    </span>
  );
}

const AGENTS = [
  { name: "Planner", detail: "Goal → architecture → task plan", icon: BrainCircuit },
  { name: "Coding Agent", detail: "Reads, edits and repairs code", icon: Bot },
  { name: "QA Agent", detail: "Builds, tests and verification", icon: CheckCircle2 },
  { name: "Browser QA", detail: "Chromium runtime validation", icon: Cpu },
  { name: "Reviewer", detail: "Diff + evidence review", icon: ShieldCheck },
  { name: "Deployment", detail: "Preview and production gates", icon: Rocket },
];

export default function AICommandCenter({ apps, onCreateProject }: Props) {
  const nav = useNavigate();
  const [status, setStatus] = useState<Doc>({});
  const [models, setModels] = useState<Doc>({ models: [], platform: {} });
  const [intelligence, setIntelligence] = useState<Doc>({});
  const [browserQa, setBrowserQa] = useState<Doc>({});
  const [publishing, setPublishing] = useState<Doc>({});
  const [deployment, setDeployment] = useState<Doc>({});
  const [selectedProject, setSelectedProject] = useState("");
  const [goal, setGoal] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [busy, setBusy] = useState("");
  const [expanded, setExpanded] = useState(true);

  const activeApps = useMemo(() => apps.filter((a) => !a.archived && !a.trashed), [apps]);

  useEffect(() => {
    if (!selectedProject && activeApps.length) setSelectedProject(activeApps[0].app_id);
  }, [activeApps, selectedProject]);

  async function load() {
    setBusy((b) => b || "refresh");
    const requests = [
      api.get("/dev-agent/status"),
      api.get("/ai/models"),
      api.get("/dev-agent/intelligence/status"),
      api.get("/dev-agent/browser-qa"),
      api.get("/dev-agent/publishing"),
      api.get("/dev-agent/deployment-control"),
    ];
    const settled = await Promise.allSettled(requests);
    const value = (i: number) => settled[i].status === "fulfilled" ? (settled[i] as PromiseFulfilledResult<any>).value.data : {};
    setStatus(value(0));
    const modelData = value(1);
    setModels(modelData);
    setSelectedModel((current) => current || modelData?.platform?.model || modelData?.feature_defaults?.site_generation || "");
    setIntelligence(value(2));
    setBrowserQa(value(3));
    setPublishing(value(4));
    setDeployment(value(5));
    setBusy("");
  }

  useEffect(() => { load(); }, []);

  async function saveDefaultModel(model: string) {
    setSelectedModel(model);
    setBusy("model");
    try {
      await api.patch("/ai/models", { model });
      setModels((m: Doc) => ({ ...m, platform: { ...(m.platform || {}), model } }));
      toast.success("Lucio default LLM updated");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not update the default model");
    } finally {
      setBusy("");
    }
  }

  async function launch() {
    if (!goal.trim()) return toast.error("Tell Lucio what you want to build or improve");
    if (!selectedProject) return onCreateProject();
    setBusy("launch");
    try {
      const { data } = await api.post(`/apps/${selectedProject}/dev-agent/sessions`, {
        goal: goal.trim(),
        auto_execute: true,
      });
      if (data?.status === "failed") throw new Error(data?.error || "Dev Agent could not start");
      toast.success("Lucio Dev Agent started in an isolated Nexus workspace");
      nav(`/apps/${selectedProject}?tab=dev-agent&session=${encodeURIComponent(data.session_id || "")}`);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || e.message || "Could not start Lucio Dev Agent");
    } finally {
      setBusy("");
    }
  }

  const runnerOnline = !!status?.runner?.reachable;
  const llmReady = !!status?.llm_available;
  const memoryReady = intelligence?.enabled === true;
  const browserReady = browserQa?.available === true;
  const githubReady = publishing?.configured === true;
  const previewReady = deployment?.configured === true;

  return (
    <section data-testid="ai-command-center" className="mb-8 overflow-hidden rounded-2xl border border-violet-500/20 bg-[var(--card)] shadow-[0_0_60px_rgba(124,58,237,0.06)]">
      <div className="border-b border-[var(--line)] bg-gradient-to-r from-violet-500/12 via-cyan-500/5 to-transparent px-5 py-5 lg:px-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[.2em] text-violet-300">
              <Sparkles size={14} /> Lucio AI Command Center
            </div>
            <h2 className="font-display text-2xl font-semibold tracking-tight">Build and improve apps with your agent team.</h2>
            <p className="mt-1 max-w-3xl text-sm text-[var(--mut)]">Describe the outcome. Lucio plans the work, edits in an isolated Nexus Runner workspace, verifies the build, runs Chromium QA, self-heals failures and hands the change set back for your approval.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill ok={llmReady} label={llmReady ? `LLM ${status?.llm_mode || "ready"}` : "LLM not configured"} />
            <StatusPill ok={runnerOnline} label={runnerOnline ? "Nexus Runner online" : "Runner offline"} />
            <StatusPill ok={memoryReady} label={memoryReady ? "Project Memory on" : "Memory unavailable"} />
            <button onClick={load} disabled={busy === "refresh"} className="chip cursor-pointer inline-flex items-center gap-1.5 disabled:opacity-50">
              <RefreshCw size={12} className={busy === "refresh" ? "animate-spin" : ""} /> Refresh
            </button>
          </div>
        </div>
      </div>

      <div className="p-5 lg:p-6">
        <div className="grid gap-5 xl:grid-cols-[1.45fr_.75fr]">
          <div className="rounded-2xl border border-[var(--line)] bg-black/15 p-4 lg:p-5">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <div className="font-display text-lg font-semibold">What should Lucio build?</div>
                <div className="text-xs text-[var(--mut)]">New feature, bug fix, redesign, integration, test repair, or architecture change.</div>
              </div>
              <WandSparkles size={20} className="text-violet-300" />
            </div>
            <textarea
              data-testid="ai-command-goal"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              rows={5}
              placeholder="Example: Add a premium booking dashboard with calendar views, automated reminders, mobile support and Browser QA. Preserve everything already working."
              className="w-full resize-y rounded-xl border border-[var(--line)] bg-[var(--bg-2)] px-4 py-3 text-sm leading-6 outline-none focus:border-violet-400/50"
            />
            <div className="mt-3 grid gap-3 md:grid-cols-[1fr_220px_auto]">
              <select
                data-testid="ai-command-project"
                value={selectedProject}
                onChange={(e) => setSelectedProject(e.target.value)}
                className="rounded-xl border border-[var(--line)] bg-[var(--bg-2)] px-3 py-2.5 text-sm outline-none"
              >
                {!activeApps.length && <option value="">Create a project first</option>}
                {activeApps.map((a) => <option key={a.app_id} value={a.app_id}>{a.name}</option>)}
              </select>
              <select
                data-testid="ai-command-model"
                value={selectedModel}
                onChange={(e) => saveDefaultModel(e.target.value)}
                disabled={busy === "model"}
                className="rounded-xl border border-[var(--line)] bg-[var(--bg-2)] px-3 py-2.5 text-sm outline-none disabled:opacity-60"
              >
                {(models.models || []).map((m: Doc) => <option key={m.id} value={m.id}>{m.label || m.id}</option>)}
              </select>
              {activeApps.length ? (
                <button data-testid="ai-command-launch" onClick={launch} disabled={!!busy || !llmReady || !runnerOnline}
                  className="btn-primary inline-flex items-center justify-center gap-2 disabled:opacity-50">
                  {busy === "launch" ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
                  Build with Lucio AI
                </button>
              ) : (
                <button onClick={onCreateProject} className="btn-primary inline-flex items-center justify-center gap-2"><Sparkles size={15} /> Create first project</button>
              )}
            </div>
            {(!llmReady || !runnerOnline) && (
              <div className="mt-3 flex items-start gap-2 rounded-xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-200/90">
                <CircleAlert size={14} className="mt-0.5 shrink-0" />
                <span>{!llmReady ? "An LLM provider still needs to be connected on the backend. " : ""}{!runnerOnline ? "Nexus Runner must be online before agentic coding can start." : ""}</span>
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-[var(--line)] bg-black/15 p-4 lg:p-5">
            <div className="mb-3 flex items-center justify-between">
              <div className="font-display text-lg font-semibold">Runtime readiness</div>
              <TerminalSquare size={18} className="text-cyan-300" />
            </div>
            <div className="space-y-2 text-xs">
              {[
                ["LLM routing", llmReady, status?.llm_mode || "none"],
                ["Nexus Runner", runnerOnline, runnerOnline ? "reachable" : "offline"],
                ["Persistent memory", memoryReady, memoryReady ? `schema v${intelligence?.schema_version || 1}` : "unavailable"],
                ["Chromium QA", browserReady, browserReady ? "available" : "not ready"],
                ["GitHub publishing", githubReady, githubReady ? "connected" : "artifact-only"],
                ["Railway previews", previewReady, previewReady ? "enabled" : "gated"],
              ].map(([label, ok, detail]: any) => (
                <div key={label} className="flex items-center justify-between gap-3 rounded-lg border border-[var(--line)] px-3 py-2">
                  <span>{label}</span>
                  <span className={ok ? "text-emerald-300" : "text-[var(--mut)]"}>{detail}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <button onClick={() => setExpanded((v) => !v)} className="mt-5 flex w-full items-center justify-between border-t border-[var(--line)] pt-4 text-left">
          <span className="text-xs font-semibold uppercase tracking-[.16em] text-[var(--mut)]">Agent team & capabilities</span>
          <ChevronRight size={15} className={`transition-transform ${expanded ? "rotate-90" : ""}`} />
        </button>

        {expanded && (
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {AGENTS.map((agent) => {
              const Icon = agent.icon;
              const available = agent.name === "Browser QA" ? browserReady : agent.name === "Deployment" ? previewReady : (llmReady && runnerOnline);
              return (
                <div key={agent.name} className="rounded-xl border border-[var(--line)] bg-white/[.025] p-3.5">
                  <div className="flex items-start gap-3">
                    <div className="rounded-lg border border-violet-500/20 bg-violet-500/10 p-2 text-violet-300"><Icon size={15} /></div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2"><span className="font-medium text-sm">{agent.name}</span><span className={`text-[10px] uppercase tracking-wider ${available ? "text-emerald-300" : "text-[var(--dim)]"}`}>{available ? "ready" : "gated"}</span></div>
                      <div className="mt-1 text-xs text-[var(--mut)]">{agent.detail}</div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-2 text-[11px] text-[var(--mut)]">
          {(status?.capabilities || []).slice(0, 10).map((cap: string) => <span key={cap} className="chip">{cap.replaceAll("_", " ")}</span>)}
          <span className="ml-auto inline-flex items-center gap-1.5"><GitBranch size={12} /> GitHub branch review remains approval-gated</span>
        </div>
      </div>
    </section>
  );
}
