import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Download, Github, Smartphone, ShieldAlert, Package } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import PreviewLinkCard from "@/components/PreviewLinkCard";
import { EmbedCard, GithubCard } from "@/components/HandoffExtras";

export default function HandoffPanel({ appDoc, patch, apiRoot, setAppDoc }) {
  const [job, setJob] = useState(null);
  const [progress, setProgress] = useState(0);
  const [platform, setPlatform] = useState("ios");

  async function downloadSource() {
    try {
      const res = await fetch(`${apiRoot}/apps/${appDoc.app_id}/export/source`, { credentials: "include" });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `${appDoc.name.toLowerCase().replace(/\s+/g, "-")}-source.zip`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast.success("Source bundle downloaded");
    } catch { toast.error("Export failed"); }
  }

  async function startMobileBuild(p) {
    setPlatform(p);
    try {
      const { data } = await api.post(`/apps/${appDoc.app_id}/export/mobile?platform=${p}`);
      setJob(data); setProgress(0);
      const steps = data.steps || [];
      let i = 0;
      const timer = setInterval(() => {
        i += 1;
        setProgress(Math.min(100, Math.round((i / (steps.length + 1)) * 100)));
        if (i >= steps.length + 1) {
          clearInterval(timer);
          setJob({ ...data, status: "ready" });
          toast.success(`${p.toUpperCase()} artifact ready (mocked)`);
        }
      }, 800);
    } catch { toast.error("Build failed"); }
  }

  return (
    <div className="grid lg:grid-cols-2 gap-6">
      {/* Source */}
      <div className="card-surface p-6">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-[var(--acc)]/10 border border-[var(--acc)]/30 flex items-center justify-center">
            <Github size={18} className="text-[var(--acc)]" />
          </div>
          <div className="flex-1">
            <div className="overline">Web Export</div>
            <h3 className="font-display text-xl font-semibold tracking-tight mt-1">Production-ready source bundle</h3>
            <p className="text-sm text-[var(--mut)] mt-2">Downloads a .zip with <code>site/</code> (multi-page HTML + chat embed), <code>app/</code> (React + FastAPI starter, Postgres/Supabase <code>schema.sql</code>) and <code>mobile/</code> (Capacitor wrapper with App Store &amp; Google Play publishing steps).</p>
            <button data-testid="export-source-zip-btn" onClick={downloadSource}
              className="mt-5 btn-primary flex items-center gap-2 text-sm !py-2 !px-4">
              <Download size={14} /> Download .zip bundle
            </button>
          </div>
        </div>
      </div>

      {/* Native builds */}
      <div className="card-surface p-6">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-[var(--acc)]/10 border border-[var(--acc)]/30 flex items-center justify-center">
            <Smartphone size={18} className="text-[var(--acc)]" />
          </div>
          <div className="flex-1">
            <div className="overline flex items-center gap-2">Native builds <span className="chip chip-maint" style={{ padding: "2px 6px" }}>MOCKED</span></div>
            <h3 className="font-display text-xl font-semibold tracking-tight mt-1">iOS & Android packages</h3>
            <p className="text-sm text-[var(--mut)] mt-2">Simulated CI pipeline. Wire this to your Xcode Cloud / Gradle runner to deliver real .ipa/.aab.</p>
            <div className="flex gap-2 mt-4">
              <button data-testid="export-ios-build-btn" onClick={() => startMobileBuild("ios")}
                className="btn-ghost flex items-center gap-2 text-sm !py-2 !px-4">
                <Package size={14} /> Build .ipa
              </button>
              <button data-testid="export-android-build-btn" onClick={() => startMobileBuild("android")}
                className="btn-ghost flex items-center gap-2 text-sm !py-2 !px-4">
                <Package size={14} /> Build .aab
              </button>
            </div>
            {job && (
              <div className="mt-5 p-4 rounded-xl bg-[var(--bg-2)] border border-[var(--line)]">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-mono">{job.job_id} · {platform.toUpperCase()}</div>
                  <div className="text-xs font-mono text-[var(--mut)]">{progress}%</div>
                </div>
                <div className="h-1.5 mt-2 rounded-full bg-[var(--line)] overflow-hidden">
                  <div style={{ width: `${progress}%` }} className="h-full bg-[var(--acc)] transition-all duration-500" />
                </div>
                {job.status === "ready" && (
                  <div className="mt-3 text-xs font-mono text-[var(--acc)]">✓ Artifact: {job.artifact} (mocked)</div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="lg:col-span-2"><PreviewLinkCard appDoc={appDoc} setAppDoc={setAppDoc} /></div>
      <EmbedCard appDoc={appDoc} />
      <GithubCard appDoc={appDoc} setAppDoc={setAppDoc} />

      {/* Transfer mode */}
      <div className="card-surface p-6 lg:col-span-2">
        <div className="flex items-start gap-3">
          <div className={`w-10 h-10 rounded-xl border flex items-center justify-center ${appDoc.transfer_mode ? "bg-amber-500/10 border-amber-500/40" : "bg-[var(--bg-2)] border-[var(--line)]"}`}>
            <ShieldAlert size={18} className={appDoc.transfer_mode ? "text-amber-400" : "text-[var(--mut)]"} />
          </div>
          <div className="flex-1">
            <div className="overline">Ownership</div>
            <div className="flex items-center justify-between mt-1">
              <div>
                <h3 className="font-display text-xl font-semibold tracking-tight">Client Transfer Mode</h3>
                <p className="text-sm text-[var(--mut)] mt-1 max-w-xl">
                  Rotates API keys, locks agency edits, and hands DB + domain ownership to the client's workspace.
                  Toggle this when the retainer ends.
                </p>
              </div>
              <Switch data-testid="client-transfer-toggle"
                checked={!!appDoc.transfer_mode}
                onCheckedChange={(v) => patch({ transfer_mode: v })} />
            </div>
            {appDoc.transfer_mode && (
              <div className="mt-4 p-3 rounded-lg bg-amber-500/8 border border-amber-500/30 text-sm text-amber-200 font-mono">
                ⚠︎ Transfer mode enabled. Agency users are read-only. New API tokens have been rotated for the client owner.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
