import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import {
  Activity, CheckCircle2, ExternalLink, FlaskConical, Globe2, Loader2,
  RefreshCw, Rocket, ShieldCheck, Sparkles, Wrench,
} from "lucide-react";

type Doc = Record<string, any>;

function Badge({ children, tone = "default" }: { children: React.ReactNode; tone?: string }) {
  const cls = tone === "ok" ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
    : tone === "warn" ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
    : tone === "bad" ? "border-red-500/30 bg-red-500/10 text-red-300"
    : "border-[var(--line)] bg-white/[.035] text-[var(--mut)]";
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium ${cls}`}>{children}</span>;
}

function Card({ children }: { children: React.ReactNode }) {
  return <section className="rounded-2xl border border-[var(--line)] bg-[var(--bg-2)]/70 p-6">{children}</section>;
}

export default function DevAgentRuntimePanel({ appId }: { appId: string }) {
  const [sessions, setSessions] = useState<Doc[]>([]);
  const [sessionId, setSessionId] = useState("");
  const [session, setSession] = useState<Doc | null>(null);
  const [browserStatus, setBrowserStatus] = useState<Doc | null>(null);
  const [deployControl, setDeployControl] = useState<Doc | null>(null);
  const [previewReadiness, setPreviewReadiness] = useState<Doc | null>(null);
  const [path, setPath] = useState("/");
  const [expectedText, setExpectedText] = useState("");
  const [busy, setBusy] = useState("");

  async function loadBase() {
    try {
      const [list, browser, deploy] = await Promise.all([
        api.get(`/apps/${appId}/dev-agent/sessions`),
        api.get("/dev-agent/browser-qa"),
        api.get("/dev-agent/deployment-control"),
      ]);
      const rows = list.data || [];
      setSessions(rows);
      setBrowserStatus(browser.data || {});
      setDeployControl(deploy.data || {});
      if (!sessionId && rows.length) setSessionId(rows[0].session_id);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not load Dev Agent runtime controls");
    }
  }

  async function loadSession(id = sessionId) {
    if (!id) return;
    try {
      const [s, readiness] = await Promise.all([
        api.get(`/apps/${appId}/dev-agent/sessions/${id}`),
        api.get(`/apps/${appId}/dev-agent/sessions/${id}/preview-readiness`).catch(() => ({ data: null })),
      ]);
      setSession(s.data || null);
      setPreviewReadiness(readiness.data || null);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not load Dev Agent session runtime state");
    }
  }

  useEffect(() => { loadBase(); }, [appId]);
  useEffect(() => { if (sessionId) loadSession(sessionId); }, [sessionId]);

  const expected = useMemo(() => expectedText.split("\n").map(x => x.trim()).filter(Boolean).slice(0, 20), [expectedText]);
  const qa = session?.browser_qa || {};
  const preview = session?.preview_deployment || previewReadiness?.preview || {};
  const productionRequest = session?.production_request || {};
  const sandboxRunning = !!session?.preview?.running;

  async function runBrowserQA(selfHeal = false) {
    if (!sessionId) return;
    setBusy(selfHeal ? "heal" : "qa");
    try {
      const endpoint = selfHeal
        ? `/apps/${appId}/dev-agent/sessions/${sessionId}/browser-self-heal`
        : `/apps/${appId}/dev-agent/sessions/${sessionId}/browser-qa`;
      const body = {
        path: path || "/",
        expected_text: expected,
        viewport_width: 1440,
        viewport_height: 900,
        fail_on_console_errors: true,
        ...(selfHeal ? { max_repair_steps: 5 } : { screenshot: true }),
      };
      const { data } = await api.post(endpoint, body);
      toast.success(selfHeal
        ? (data.ok ? "Browser QA passed after self-healing" : "Repair pass completed; runtime issues remain")
        : (data.ok ? "Chromium Browser QA passed" : "Chromium Browser QA found runtime issues"));
      await loadSession();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Browser QA operation failed");
    } finally { setBusy(""); }
  }

  async function deployPreview() {
    if (!sessionId) return;
    if (!confirm("Create an isolated Railway preview service from the reviewed GitHub branch? This may consume Railway resources. It will NOT change production.")) return;
    setBusy("deploy");
    try {
      await api.post(`/apps/${appId}/dev-agent/sessions/${sessionId}/preview-deploy`, {});
      toast.success("Railway preview deployment requested");
      await loadSession();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Could not create Railway preview"); }
    finally { setBusy(""); }
  }

  async function refreshPreview() {
    if (!sessionId) return;
    setBusy("refresh-preview");
    try {
      const { data } = await api.post(`/apps/${appId}/dev-agent/sessions/${sessionId}/preview-refresh`, {});
      toast.success(data.ready ? "Railway preview is live" : `Preview status: ${data.status || "checking"}`);
      await loadSession();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Could not refresh Railway preview"); }
    finally { setBusy(""); }
  }

  async function requestProduction() {
    if (!sessionId) return;
    if (!confirm("Request production promotion review? This records an approval request only — it does NOT deploy anything to production.")) return;
    setBusy("production");
    try {
      await api.post(`/apps/${appId}/dev-agent/sessions/${sessionId}/production-request`, {});
      toast.success("Production promotion review requested; no production change was made");
      await loadSession();
    } catch (e: any) { toast.error(e.response?.data?.detail || "Could not request production review"); }
    finally { setBusy(""); }
  }

  return (
    <div className="space-y-6" data-testid="dev-agent-runtime-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[.18em] text-cyan-300"><Activity size={14} /> Runtime QA & promotion</div>
          <h3 className="mt-1 font-display text-xl font-semibold">From working code to verified preview</h3>
          <p className="mt-1 max-w-3xl text-sm text-[var(--mut)]">Use real Chromium QA, bounded self-healing and a separate preview-deployment gate. Production is never changed by these controls.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={browserStatus?.available ? "ok" : "warn"}><Globe2 size={12} className="mr-1" /> Browser QA {browserStatus?.available ? "online" : "unavailable"}</Badge>
          <Badge tone={deployControl?.configured ? "ok" : "warn"}><Rocket size={12} className="mr-1" /> Railway preview {deployControl?.configured ? "enabled" : "disabled"}</Badge>
          <Badge tone="ok"><ShieldCheck size={12} className="mr-1" /> production gated</Badge>
        </div>
      </div>

      <Card>
        <div className="grid gap-4 lg:grid-cols-[1fr_220px]">
          <div>
            <label className="mb-2 block text-xs uppercase tracking-wider text-[var(--mut)]">Development run</label>
            <select value={sessionId} onChange={e => setSessionId(e.target.value)} className="input w-full">
              {!sessions.length && <option value="">No Dev Agent runs yet</option>}
              {sessions.map(s => <option key={s.session_id} value={s.session_id}>{(s.plan?.summary || s.goal || s.session_id).slice(0, 100)} · {s.status}</option>)}
            </select>
          </div>
          <div className="flex items-end">
            <button onClick={() => { loadBase(); loadSession(); }} disabled={!!busy} className="btn-ghost flex w-full items-center justify-center gap-2"><RefreshCw size={14} /> Refresh runtime</button>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 font-semibold"><FlaskConical size={16} /> Chromium Browser QA</div>
            {qa.checked_at && <Badge tone={qa.ok ? "ok" : "bad"}>{qa.ok ? "PASS" : "ISSUES FOUND"}</Badge>}
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-[180px_1fr]">
            <div><label className="mb-1 block text-xs text-[var(--mut)]">Preview path</label><input value={path} onChange={e => setPath(e.target.value)} className="input w-full font-mono text-xs" placeholder="/" /></div>
            <div><label className="mb-1 block text-xs text-[var(--mut)]">Expected visible text — optional, one per line</label><textarea value={expectedText} onChange={e => setExpectedText(e.target.value)} className="input min-h-20 w-full text-xs" placeholder={"Dashboard\nWelcome"} /></div>
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <button onClick={() => runBrowserQA(false)} disabled={!!busy || !browserStatus?.available || !sandboxRunning} className="btn-ghost flex items-center gap-2">{busy === "qa" ? <Loader2 size={14} className="animate-spin" /> : <Globe2 size={14} />} Run Browser QA</button>
            <button onClick={() => runBrowserQA(true)} disabled={!!busy || !browserStatus?.available || !sandboxRunning} className="btn-primary flex items-center gap-2">{busy === "heal" ? <Loader2 size={14} className="animate-spin" /> : <Wrench size={14} />} QA + self-heal</button>
          </div>
          {!sandboxRunning && <p className="mt-3 text-xs text-amber-200">This run needs a live Nexus sandbox preview before Browser QA can execute.</p>}
          {qa.checked_at && (
            <div className="mt-5 rounded-xl border border-[var(--line)] bg-black/15 p-4">
              <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
                <div><div className="text-[var(--mut)]">HTTP</div><div className="mt-1 font-semibold">{qa.status ?? "—"}</div></div>
                <div><div className="text-[var(--mut)]">Console errors</div><div className="mt-1 font-semibold">{(qa.console_errors || []).length}</div></div>
                <div><div className="text-[var(--mut)]">Page errors</div><div className="mt-1 font-semibold">{(qa.page_errors || []).length}</div></div>
                <div><div className="text-[var(--mut)]">Failed requests</div><div className="mt-1 font-semibold">{(qa.failed_requests || []).length}</div></div>
              </div>
              {!!qa.missing_text?.length && <div className="mt-3 text-xs text-amber-200">Missing text: {qa.missing_text.join(" · ")}</div>}
              {!!qa.page_errors?.length && <pre className="mt-3 max-h-36 overflow-auto whitespace-pre-wrap text-[11px] text-red-300">{qa.page_errors.join("\n\n")}</pre>}
              {!!qa.console_errors?.length && <pre className="mt-3 max-h-36 overflow-auto whitespace-pre-wrap text-[11px] text-red-300/80">{qa.console_errors.join("\n\n")}</pre>}
              {qa.screenshot?.url && <a href={qa.screenshot.url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs text-cyan-300">Open screenshot evidence <ExternalLink size={11} /></a>}
            </div>
          )}
        </Card>

        <Card>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 font-semibold"><Rocket size={16} /> Railway preview gate</div>
            <Badge tone={preview.ready ? "ok" : preview.service_id ? "warn" : "default"}>{preview.ready ? "LIVE" : preview.service_id ? (preview.status || "DEPLOYING") : "NOT CREATED"}</Badge>
          </div>
          {!deployControl?.configured && <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/[.05] p-4 text-xs leading-5 text-amber-100">Preview deployment is intentionally disabled until a backend-only Railway project token, target project/environment IDs and the explicit enable flag are configured. No token belongs in the browser or Nexus Runner.</div>}
          {!!previewReadiness?.reasons?.length && <div className="mt-4 space-y-1 text-xs text-[var(--mut)]">{previewReadiness.reasons.map((r: string) => <div key={r}>• {r}</div>)}</div>}
          <div className="mt-5 flex flex-wrap gap-3">
            {!preview.service_id && <button onClick={deployPreview} disabled={!!busy || !previewReadiness?.ready} className="btn-primary flex items-center gap-2">{busy === "deploy" ? <Loader2 size={14} className="animate-spin" /> : <Rocket size={14} />} Deploy isolated preview</button>}
            {preview.service_id && <button onClick={refreshPreview} disabled={!!busy} className="btn-ghost flex items-center gap-2">{busy === "refresh-preview" ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} Refresh deployment</button>}
            {preview.url && <a href={preview.url} target="_blank" rel="noreferrer" className="btn-ghost flex items-center gap-2">Open preview <ExternalLink size={12} /></a>}
          </div>
          {preview.ready && (
            <div className="mt-5 rounded-xl border border-emerald-500/20 bg-emerald-500/[.05] p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-emerald-200"><CheckCircle2 size={15} /> Preview is live</div>
              <p className="mt-2 text-xs leading-5 text-[var(--mut)]">Production promotion is still a separate gate. Requesting production review below only records intent; it does not deploy.</p>
              <button onClick={requestProduction} disabled={!!busy || !!productionRequest.status} className="btn-ghost mt-3 flex items-center gap-2">{busy === "production" ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} {productionRequest.status ? "Production review requested" : "Request production review"}</button>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
