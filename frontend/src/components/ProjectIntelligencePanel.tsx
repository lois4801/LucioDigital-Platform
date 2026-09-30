import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import {
  BrainCircuit, CheckCircle2, CircleAlert, FileCode2, Plus, RefreshCw,
  ShieldCheck, Sparkles, Trash2,
} from "lucide-react";

type AnyDoc = Record<string, any>;

function Pill({ children, tone = "default" }: { children: React.ReactNode; tone?: string }) {
  const cls = tone === "ok"
    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
    : tone === "warn"
      ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
      : "border-[var(--line)] bg-white/[.035] text-[var(--mut)]";
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium ${cls}`}>{children}</span>;
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-[var(--line)] bg-black/15 p-3">
      <div className="text-xl font-semibold">{value}</div>
      <div className="mt-1 text-[11px] uppercase tracking-wider text-[var(--mut)]">{label}</div>
    </div>
  );
}

export default function ProjectIntelligencePanel({ appId }: { appId: string }) {
  const [memory, setMemory] = useState<AnyDoc | null>(null);
  const [busy, setBusy] = useState("");
  const [title, setTitle] = useState("");
  const [detail, setDetail] = useState("");
  const [category, setCategory] = useState("architecture");

  async function load(quiet = false) {
    try {
      const { data } = await api.get(`/apps/${appId}/dev-agent/intelligence`);
      setMemory(data);
    } catch (e: any) {
      if (!quiet) toast.error(e.response?.data?.detail || "Could not load project intelligence");
    }
  }

  async function refresh() {
    setBusy("refresh");
    try {
      const { data } = await api.post(`/apps/${appId}/dev-agent/intelligence/refresh`);
      setMemory(data);
      toast.success("Project intelligence refreshed");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not refresh project intelligence");
    } finally { setBusy(""); }
  }

  async function addDecision() {
    if (!title.trim() || !detail.trim()) return toast.error("Add a short title and decision detail first");
    setBusy("decision");
    try {
      await api.post(`/apps/${appId}/dev-agent/intelligence/decisions`, {
        title: title.trim(), detail: detail.trim(), category,
      });
      setTitle("");
      setDetail("");
      await load(true);
      toast.success("Project decision saved to Lucio memory");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not save project decision");
    } finally { setBusy(""); }
  }

  async function removeDecision(id: string) {
    if (!confirm("Remove this project decision from Lucio memory?")) return;
    setBusy(id);
    try {
      await api.delete(`/apps/${appId}/dev-agent/intelligence/decisions/${id}`);
      await load(true);
      toast.success("Project decision removed");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not remove project decision");
    } finally { setBusy(""); }
  }

  useEffect(() => { load(); }, [appId]);

  const stats = memory?.stats || {};
  const architecture = memory?.architecture || {};
  const decisions = memory?.decisions || [];
  const runs = memory?.recent_runs || [];
  const failures = memory?.known_failures || [];
  const capabilities = memory?.verified_capabilities || [];
  const files = architecture?.files || [];
  const latestRuns = useMemo(() => runs.slice(0, 6), [runs]);

  return (
    <section className="overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--bg-2)]/70" data-testid="project-intelligence-panel">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--line)] bg-gradient-to-r from-cyan-500/10 via-violet-500/5 to-transparent p-6">
        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[.18em] text-cyan-300">
            <BrainCircuit size={14} /> Phase 12 · Persistent Project Intelligence
          </div>
          <h3 className="font-display text-xl font-semibold">What Lucio remembers about this project</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--mut)]">
            Architecture, verified capabilities, prior agent runs, known failures and human decisions are carried into future Dev Agent planning and coding sessions.
          </p>
        </div>
        <button onClick={refresh} disabled={busy === "refresh"} className="btn-ghost inline-flex items-center gap-2 text-sm">
          <RefreshCw size={14} className={busy === "refresh" ? "animate-spin" : ""} /> Refresh memory
        </button>
      </div>

      {!memory ? (
        <div className="p-6 text-sm text-[var(--mut)]">Loading project intelligence…</div>
      ) : (
        <div className="space-y-6 p-6">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
            <Stat label="Agent runs" value={stats.runs || 0} />
            <Stat label="Verified" value={stats.verified_runs || 0} />
            <Stat label="Browser QA" value={stats.browser_verified_runs || 0} />
            <Stat label="Approved" value={stats.approved_runs || 0} />
            <Stat label="Published" value={stats.published_runs || 0} />
            <Stat label="Decisions" value={stats.decision_count || 0} />
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <div className="rounded-xl border border-[var(--line)] bg-black/15 p-4">
              <div className="flex items-center gap-2 font-semibold"><FileCode2 size={15} /> Architecture snapshot</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {architecture.stack && <Pill tone="ok">stack: {String(architecture.stack)}</Pill>}
                {architecture.scaffold && <Pill>scaffold: {String(architecture.scaffold)}</Pill>}
                {architecture.package_manager && <Pill>package: {String(architecture.package_manager)}</Pill>}
                <Pill>{files.length} remembered files</Pill>
              </div>
              {files.length ? (
                <div className="mt-3 max-h-40 overflow-auto rounded-lg border border-[var(--line)] bg-black/20 p-3">
                  {files.slice(0, 60).map((f: string) => <code key={f} className="block truncate py-0.5 text-[11px] text-[var(--mut)]">{f}</code>)}
                </div>
              ) : <p className="mt-3 text-sm text-[var(--mut)]">Architecture will populate after the first repository/scaffold inspection.</p>}
            </div>

            <div className="rounded-xl border border-[var(--line)] bg-black/15 p-4">
              <div className="flex items-center gap-2 font-semibold"><ShieldCheck size={15} /> Verified capabilities</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {capabilities.length ? capabilities.map((c: string) => <Pill key={c} tone="ok"><CheckCircle2 size={11} className="mr-1" />{c.replaceAll("_", " ")}</Pill>)
                  : <span className="text-sm text-[var(--mut)]">Capabilities become verified only after successful evidence-backed runs.</span>}
              </div>
              {!!failures.length && (
                <div className="mt-5">
                  <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-300"><CircleAlert size={13} /> Known failures</div>
                  <div className="space-y-2">
                    {failures.slice(0, 4).map((f: AnyDoc) => (
                      <div key={f.session_id} className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-xs">
                        <div className="font-medium">{f.goal || f.session_id}</div>
                        <div className="mt-1 text-[var(--mut)]">{f.error || "Failed run"}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="grid gap-5 xl:grid-cols-[1.15fr_.85fr]">
            <div className="rounded-xl border border-[var(--line)] bg-black/15 p-4">
              <div className="flex items-center gap-2 font-semibold"><Sparkles size={15} /> Human project decisions</div>
              <p className="mt-1 text-xs text-[var(--mut)]">Save architecture or product decisions you want future coding sessions to respect.</p>
              <div className="mt-4 grid gap-2 md:grid-cols-[160px_1fr]">
                <select value={category} onChange={(e) => setCategory(e.target.value)} className="input">
                  <option value="architecture">Architecture</option>
                  <option value="product">Product</option>
                  <option value="ui">UI / UX</option>
                  <option value="security">Security</option>
                  <option value="deployment">Deployment</option>
                  <option value="constraint">Constraint</option>
                </select>
                <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Decision title" className="input" />
              </div>
              <textarea value={detail} onChange={(e) => setDetail(e.target.value)} placeholder="Example: Keep MongoDB private inside Railway and never expose database credentials to generated apps." className="input mt-2 min-h-24 w-full resize-y" />
              <button onClick={addDecision} disabled={busy === "decision"} className="btn-primary mt-3 inline-flex items-center gap-2 text-sm">
                <Plus size={14} /> Save decision
              </button>

              <div className="mt-5 space-y-2">
                {decisions.length ? decisions.slice(0, 12).map((d: AnyDoc) => (
                  <div key={d.decision_id} className="flex items-start justify-between gap-3 rounded-lg border border-[var(--line)] bg-black/20 p-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2"><span className="font-medium text-sm">{d.title}</span><Pill>{d.category}</Pill></div>
                      <p className="mt-1 whitespace-pre-wrap text-xs leading-5 text-[var(--mut)]">{d.detail}</p>
                    </div>
                    <button onClick={() => removeDecision(d.decision_id)} disabled={busy === d.decision_id} className="rounded-lg p-2 text-[var(--mut)] hover:bg-red-500/10 hover:text-red-300" title="Remove decision"><Trash2 size={14} /></button>
                  </div>
                )) : <p className="text-sm text-[var(--mut)]">No explicit project decisions saved yet.</p>}
              </div>
            </div>

            <div className="rounded-xl border border-[var(--line)] bg-black/15 p-4">
              <div className="font-semibold">Recent remembered runs</div>
              <div className="mt-3 space-y-2">
                {latestRuns.length ? latestRuns.map((r: AnyDoc) => (
                  <div key={r.session_id} className="rounded-lg border border-[var(--line)] bg-black/20 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="truncate text-sm font-medium">{r.goal || r.session_id}</div>
                      <Pill tone={r.verification_ok ? "ok" : r.error ? "warn" : "default"}>{r.status || "unknown"}</Pill>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {r.verification_ok && <Pill tone="ok">build verified</Pill>}
                      {r.browser_qa_ok && <Pill tone="ok">browser QA</Pill>}
                      {r.decision && <Pill>{r.decision}</Pill>}
                      {r.published_branch && <Pill>{r.published_branch}</Pill>}
                    </div>
                  </div>
                )) : <p className="text-sm text-[var(--mut)]">No Dev Agent history yet.</p>}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
