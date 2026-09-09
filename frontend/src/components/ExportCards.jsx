import { useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Download, Globe, Layers, Package2, PackageCheck, Loader2, CheckCircle2, AlertTriangle } from "lucide-react";

const KINDS = [
  {
    kind: "website",
    label: "Export as Website",
    icon: Globe,
    title: "Complete static website package",
    blurb: "Every page and CMS item as HTML, all images, video and fonts embedded locally, styles.css, a small form server for submissions, plus WordPress and Webflow import files and a setup readme.",
  },
  {
    kind: "fullstack",
    label: "Export as Full-Stack App",
    icon: Layers,
    title: "Deployable full-stack application",
    blurb: "React frontend with the exact design, FastAPI backend, MongoDB seed preloaded with all your content, data, bookings and members, email/password auth with admin & user roles, admin dashboard, schema.sql, docker-compose and a step-by-step deploy readme.",
  },
  {
    kind: "plugin",
    label: "Export as Plugin Package",
    icon: Package2,
    title: "Plug-and-play platform bundle",
    blurb: "plugin.json with every page, block, design token, CMS record, form, workflow, setting and member, plus an assets folder. Re-import it here to clone or restore the whole project instantly.",
  },
  {
    kind: "handoff",
    label: "Build Handoff Bundle",
    icon: PackageCheck,
    title: "One-click client handoff bundle",
    blurb: "Everything in one archive: the static site, the full-stack app code, every record as JSON, every uploaded file, a ready Supabase migration, .env.example and a written self-host guide. Hand it over and they own it.",
  },
];

const STAGES = ["collecting", "pages", "data", "assets", "fonts", "code", "cms", "supabase", "zipping", "done"];

export default function ExportCards({ appDoc }) {
  const [jobs, setJobs] = useState({});         // kind -> job
  const timers = useRef({});

  useEffect(() => {
    api.get(`/apps/${appDoc.app_id}/export/jobs`).then(({ data }) => {
      const latest = {};
      (data.jobs || []).forEach((j) => { if (!latest[j.kind]) latest[j.kind] = j; });
      setJobs(latest);
      Object.values(latest).filter((j) => j.status === "running").forEach((j) => poll(j));
    }).catch(() => {});
    return () => Object.values(timers.current).forEach(clearInterval);
  }, [appDoc.app_id]);

  function poll(job) {
    clearInterval(timers.current[job.kind]);
    timers.current[job.kind] = setInterval(async () => {
      try {
        const { data } = await api.get(`/apps/${appDoc.app_id}/export/jobs/${job.job_id}`);
        setJobs((j) => ({ ...j, [data.kind]: data }));
        if (data.status !== "running") {
          clearInterval(timers.current[data.kind]);
          if (data.status === "done") toast.success(`${KINDS.find((k) => k.kind === data.kind)?.label} is ready — emailed you the confirmation too`);
          else toast.error(data.error || "Export failed");
        }
      } catch { clearInterval(timers.current[job.kind]); }
    }, 1500);
  }

  async function start(kind) {
    try {
      const { data } = await api.post(`/apps/${appDoc.app_id}/export/start?kind=${kind}`);
      setJobs((j) => ({ ...j, [kind]: data }));
      poll(data);
      toast.info("Export started — you'll get a toast and an email when it's ready");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not start the export"); }
  }

  async function download(job) {
    try {
      const res = await api.get(`/apps/${appDoc.app_id}/export/jobs/${job.job_id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = job.filename || "export.zip";
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch { toast.error("Download failed"); }
  }

  return (
    <div className="lg:col-span-2 card-surface p-6" data-testid="export-system">
      <div className="overline">Handoff &amp; Export</div>
      <h3 className="font-display text-xl font-semibold tracking-tight mt-1">Four ways to hand this project over</h3>
      <p className="text-sm text-[var(--mut)] mt-2 max-w-3xl">
        Every package bundles all images, media and fonts locally, so nothing is missing on the receiving end.
        Exports run in the background — the progress bar updates live and we email you when the download is ready.
      </p>

      <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4 mt-6">
        {KINDS.map(({ kind, label, icon: Icon, title, blurb }) => {
          const job = jobs[kind];
          const running = job?.status === "running";
          const done = job?.status === "done";
          return (
            <div key={kind} data-testid={`export-card-${kind}`}
              className="rounded-2xl border border-[var(--line)] p-5 flex flex-col gap-3 hover:border-[var(--acc)]/50 transition-colors">
              <div className="w-10 h-10 rounded-xl bg-[var(--acc)]/10 border border-[var(--acc)]/30 flex items-center justify-center">
                <Icon size={17} className="text-[var(--acc)]" />
              </div>
              <div>
                <div className="font-semibold text-sm">{title}</div>
                <p className="text-[11px] leading-relaxed text-[var(--mut)] mt-1.5">{blurb}</p>
              </div>

              <button data-testid={`export-${kind}-btn`} onClick={() => start(kind)} disabled={running}
                className="mt-auto btn-primary text-xs !py-2.5 !px-4 flex items-center justify-center gap-2 disabled:opacity-50">
                {running ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
                {running ? "Preparing…" : label}
              </button>

              {job && (
                <div data-testid={`export-progress-${kind}`} className="rounded-xl bg-[var(--bg-2)] border border-[var(--line)] p-3">
                  <div className="flex items-center justify-between text-[10px] font-mono">
                    <span className="text-[var(--mut)] truncate">{job.detail || job.stage}</span>
                    <span>{job.status === "done" ? "100%" : `${job.pct || 0}%`}</span>
                  </div>
                  <div className="h-1.5 mt-2 rounded-full bg-[var(--line)] overflow-hidden">
                    <div style={{ width: `${job.status === "done" ? 100 : job.pct || 0}%` }}
                      className={`h-full transition-all duration-500 ${job.status === "error" ? "bg-red-500" : "bg-[var(--acc)]"}`} />
                  </div>
                  {done && (
                    <>
                      <div className="mt-2 flex items-center gap-1.5 text-[10px] text-[var(--acc)]">
                        <CheckCircle2 size={11} /> {job.file_count} files · {Math.max(1, Math.round((job.size || 0) / 1024))} KB
                      </div>
                      <button data-testid={`export-download-${kind}`} onClick={() => download(job)}
                        className="mt-2 w-full btn-ghost text-[11px] !py-2 flex items-center justify-center gap-1.5">
                        <Download size={11} /> Download {job.filename?.length > 26 ? ".zip" : job.filename}
                      </button>
                      {!!job.skipped?.length && (
                        <div className="mt-2 text-[10px] text-amber-300 flex items-start gap-1.5">
                          <AlertTriangle size={11} className="mt-0.5 shrink-0" /> {job.skipped.length} asset(s) couldn't be fetched — listed in the readme
                        </div>
                      )}
                    </>
                  )}
                  {job.status === "error" && <div className="mt-2 text-[10px] text-red-300">{job.error}</div>}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-4 text-[10px] text-[var(--dim)]">
        Stages: {STAGES.join(" → ")}. Media is capped at this tenant's storage quota; anything skipped is listed in the package readme.
      </div>
    </div>
  );
}
