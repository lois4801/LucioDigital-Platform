import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import api from "@/lib/api";
import { Monitor, Tablet, Smartphone, ArrowLeft, GitCompare, Rocket, Layers, FlaskConical } from "lucide-react";
import RolloutModal from "@/components/RolloutModal";

const SIZES = { desktop: [1440, 900], tablet: [820, 1100], mobile: [390, 844] };
const ICONS = { desktop: Monitor, tablet: Tablet, mobile: Smartphone };

// Mandatory approval workflow: side-by-side preview → Generate Diff → controlled rollout.
export default function RedesignReview() {
  const nav = useNavigate();
  const [vp, setVp] = useState("desktop");
  const [info, setInfo] = useState(null);
  const [showDiff, setShowDiff] = useState(false);
  const [target, setTarget] = useState(null);      // null = all tenants
  const [tenants, setTenants] = useState([]);

  useEffect(() => {
    api.get("/redesign/pending").then(r => setInfo(r.data)).catch(() => {});
    api.get("/apps").then(r => setTenants((r.data.apps || r.data || []).filter(a => !a.is_test_lab))).catch(() => {});
  }, []);

  const [w, h] = SIZES[vp];
  const scale = vp === "desktop" ? 0.42 : vp === "tablet" ? 0.5 : 0.62;

  async function generateDiff() {
    try { await api.post("/redesign/reviewed"); } catch { /* non-blocking */ }
    setTarget(null);
    setShowDiff(true);
  }

  async function dismiss() {
    try {
      await api.post("/redesign/dismiss");
      toast.success("Redesign review dismissed — nothing was pushed");
      nav("/dashboard");
    } catch { toast.error("Could not dismiss"); }
  }

  const Frame = ({ src, label, badge }) => (
    <div className="flex-1 min-w-0">
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="text-sm font-semibold flex items-center gap-2">{badge}{label}</div>
        <span className="text-[10px] font-mono text-[var(--dim)]">{w}×{h}</span>
      </div>
      <div className="rounded-2xl border border-[var(--line)] bg-black/40 overflow-hidden mx-auto"
        style={{ width: Math.round(w * scale), height: Math.round(h * scale) }}>
        <iframe src={src} title={label} data-testid={`redesign-frame-${label.includes("live") ? "live" : "new"}`}
          className="origin-top-left border-0 bg-black" loading="eager"
          style={{ width: w, height: h, transform: `scale(${scale})` }} />
      </div>
    </div>
  );

  return (
    <div className="min-h-screen" data-testid="redesign-review-page">
      <header className="sticky top-0 z-30 backdrop-blur-xl bg-[var(--bg)]/90 border-b border-[var(--line)] px-6 lg:px-10 py-4 flex flex-wrap items-center justify-between gap-3">
        <button data-testid="redesign-back" onClick={() => nav("/dashboard")} className="btn-ghost text-sm !py-2 !px-4 inline-flex items-center gap-2"><ArrowLeft size={14} /> Dashboard</button>
        <div className="min-w-0">
          <div className="overline">Redesign review</div>
          <div className="font-display text-lg font-semibold truncate" data-testid="redesign-version">{info?.version || "No pending redesign"}</div>
        </div>
        <div className="flex items-center gap-1.5">
          {Object.keys(SIZES).map(k => {
            const I = ICONS[k];
            return (
              <button key={k} data-testid={`redesign-vp-${k}`} onClick={() => setVp(k)} title={k}
                className={`chip cursor-pointer inline-flex items-center gap-1 ${vp === k ? "chip-active" : "hover:!text-white"}`}>
                <I size={11} /> {k}
              </button>
            );
          })}
        </div>
      </header>

      <main className="px-6 lg:px-10 py-8 space-y-8">
        {info?.note && <div className="card-surface p-4 text-sm text-[var(--mut)]" data-testid="redesign-note">{info.note}</div>}

        <div className="flex flex-col lg:flex-row gap-6" data-testid="redesign-compare">
          <Frame src="/" label="Current live version" badge={<Layers size={13} className="text-[var(--mut)]" />} />
          <Frame src={info?.preview_url || "/test-lab/landing"} label="New Test Lab version" badge={<FlaskConical size={13} className="text-[var(--acc)]" />} />
        </div>

        <div className="card-surface p-6 text-center" data-testid="redesign-approval-prompt">
          <div className="font-display text-xl sm:text-2xl font-semibold tracking-tight">
            Are you happy with this redesign?
          </div>
          <p className="text-sm text-[var(--mut)] mt-2 max-w-2xl mx-auto">
            When you are ready, click Generate Diff to see a detailed breakdown of every change before deciding where to push it.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
            <button data-testid="redesign-generate-diff" onClick={generateDiff} className="btn-primary inline-flex items-center gap-2"><GitCompare size={15} /> Generate Diff</button>
            <button data-testid="redesign-dismiss" onClick={dismiss} className="btn-ghost text-sm !py-2.5 !px-5">Not yet — keep it in Test Lab</button>
          </div>
        </div>

        {info?.reviewed_at && (
          <div className="card-surface p-6" data-testid="redesign-rollout-options">
            <div className="overline">Controlled rollout</div>
            <div className="text-sm text-[var(--mut)] mt-1">Each option opens the confirmation modal before anything is applied.</div>
            <div className="mt-4 grid sm:grid-cols-3 gap-3">
              <div>
                <select data-testid="redesign-target-tenant" onChange={e => setTarget(e.target.value || null)} defaultValue=""
                  className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm mb-2 outline-none focus:border-[var(--acc)]">
                  <option value="">Choose a tenant…</option>
                  {tenants.map(t => <option key={t.app_id} value={t.app_id}>{t.name}</option>)}
                </select>
                <button data-testid="redesign-push-one" disabled={!target} onClick={() => setShowDiff(true)}
                  className="btn-ghost w-full text-sm !py-2.5 disabled:opacity-40">Push to One Tenant</button>
              </div>
              <button data-testid="redesign-push-template" onClick={() => nav("/templates")}
                className="btn-ghost text-sm !py-2.5 self-start">Push to One Template</button>
              <button data-testid="redesign-push-all" onClick={() => { setTarget(null); setShowDiff(true); }}
                className="btn-primary text-sm !py-2.5 inline-flex items-center justify-center gap-2 self-start"><Rocket size={14} /> Push to All</button>
            </div>
          </div>
        )}
      </main>

      <RolloutModal open={showDiff} onClose={() => setShowDiff(false)} targetAppId={target}
        targetName={tenants.find(t => t.app_id === target)?.name || ""} />
    </div>
  );
}
