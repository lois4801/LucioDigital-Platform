import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { toast } from "sonner";
import { ArrowLeft, Rocket, Globe, Github, ExternalLink, Copy } from "lucide-react";

const Light = ({ on, warn, label }) => <span className="flex items-center gap-1.5 text-[11px] font-mono text-[var(--mut)]"><span className={`w-2 h-2 rounded-full ${on ? "bg-[var(--acc)] shadow-[0_0_8px_var(--acc)]" : warn ? "bg-amber-400" : "bg-[var(--line)]"}`} />{label}</span>;

export default function DeployHub() {
  const nav = useNavigate();
  const [rows, setRows] = useState([]);
  const origin = window.location.origin;
  useEffect(() => { load(); }, []);
  async function load() { try { const { data } = await api.get("/deployments"); setRows(data); } catch { toast.error("Failed to load"); } }
  async function publish(r) { await api.post(`/apps/${r.app_id}/preview/${r.preview_token ? "toggle" : "regenerate"}`); toast.success(r.published ? "Unpublished" : "Published — live URL ready"); load(); }
  async function push(r) { toast.info("Pushing to GitHub…"); try { const { data } = await api.post(`/apps/${r.app_id}/github/push`, {}, { timeout: 180000 }); toast[data.status === "pushed" ? "success" : "info"](data.status === "pushed" ? "Pushed" : "Push simulated (connect GitHub token in Handoff)"); load(); } catch { toast.error("Push failed"); } }

  return (
    <div className="min-h-screen" data-testid="deploy-hub">
      <header className="sticky top-0 z-30 backdrop-blur-xl bg-[var(--bg)]/85 border-b border-[var(--line)] px-6 lg:px-10 py-4 flex items-center gap-3">
        <button data-testid="deploy-back-btn" onClick={() => nav("/dashboard")} className="w-10 h-10 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-white/5"><ArrowLeft size={16} /></button>
        <div><div className="overline">Deployment Hub</div><div className="font-display text-xl font-semibold tracking-tight flex items-center gap-2"><Rocket size={16} className="text-[var(--acc)]" /> Publish & handoff, all projects</div></div>
      </header>
      <main className="px-6 lg:px-10 py-8 space-y-3">
        <div className="grid grid-cols-[1fr_200px_200px_200px_180px] gap-3 px-5 overline"><span>Project</span><span>Live URL</span><span>Custom domain</span><span>GitHub</span><span></span></div>
        {rows.map(r => (
          <div key={r.app_id} data-testid={`deploy-row-${r.app_id}`} className="card-surface px-5 py-4 grid grid-cols-[1fr_200px_200px_200px_180px] gap-3 items-center">
            <div className="flex items-center gap-3 min-w-0"><span className="w-2.5 h-2.5 rounded-full" style={{ background: r.color }} />
              <div className="min-w-0"><div className="font-display font-semibold truncate cursor-pointer hover:text-[var(--acc)]" onClick={() => nav(`/apps/${r.app_id}`)}>{r.name}</div><div className="text-[11px] font-mono text-[var(--mut)]">{r.kind} · {r.pages} pages · {r.plan || "no plan"}</div></div></div>
            <div className="space-y-1"><Light on={r.published} label={r.published ? "Live" : "Draft"} />
              {r.published && <div className="flex items-center gap-1 text-[11px] font-mono text-[var(--mut)]"><a data-testid="deploy-live-link" href={`${origin}/p/${r.preview_token}`} target="_blank" rel="noreferrer" className="truncate hover:text-white max-w-[150px]">/p/{r.preview_token.slice(0, 10)}…</a><button onClick={() => { navigator.clipboard.writeText(`${origin}/p/${r.preview_token}`); toast.success("Copied"); }}><Copy size={10} /></button></div>}</div>
            <div className="space-y-1"><Light on={r.domain_status === "verified"} warn={!!r.custom_domain} label={r.custom_domain ? (r.domain_status || "pending") : "none"} />{r.custom_domain && <div className="text-[11px] font-mono text-[var(--mut)] truncate flex items-center gap-1"><Globe size={10} />{r.custom_domain}</div>}</div>
            <div className="space-y-1"><Light on={r.github?.status === "pushed"} warn={r.github?.status === "mocked"} label={r.github ? r.github.status : "not synced"} />{r.github && <div className="text-[11px] font-mono text-[var(--mut)] truncate flex items-center gap-1"><Github size={10} />{r.github.repo?.replace("https://github.com/", "")}{r.github_autosync && " · auto"}</div>}</div>
            <div className="flex gap-2 justify-end">
              <button data-testid="deploy-publish-btn" onClick={() => publish(r)} className={`text-xs !py-1.5 !px-3 ${r.published ? "btn-ghost" : "btn-primary"}`}>{r.published ? "Unpublish" : "Publish"}</button>
              <button data-testid="deploy-push-btn" onClick={() => push(r)} className="btn-ghost text-xs !py-1.5 !px-3 flex items-center gap-1"><Github size={11} /> Push</button>
              {r.published && <a href={`${origin}/p/${r.preview_token}`} target="_blank" rel="noreferrer" className="w-8 h-8 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-white/5"><ExternalLink size={12} /></a>}
            </div>
          </div>
        ))}
      </main>
    </div>
  );
}
