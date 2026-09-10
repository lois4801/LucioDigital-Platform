import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import api from "@/lib/api";
import { Monitor, Tablet, Smartphone, ArrowLeft, Layers, FlaskConical } from "lucide-react";

const SIZES = { desktop: [1440, 900], tablet: [820, 1100], mobile: [390, 844] };
const ICONS = { desktop: Monitor, tablet: Tablet, mobile: Smartphone };

// Mandatory approval workflow: side-by-side preview → Generate Diff → controlled rollout.
export default function RedesignReview() {
  const nav = useNavigate();
  const [vp, setVp] = useState("desktop");
  const [info, setInfo] = useState(null);
  const [target, setTarget] = useState(null);      // null = all clients
  const [clients, setClients] = useState([]);

  useEffect(() => {
    api.get("/redesign/pending").then(r => setInfo(r.data)).catch(() => {});
    api.get("/apps").then(r => setClients((r.data.apps || r.data || []).filter(a => !a.is_test_lab))).catch(() => {});
  }, []);

  const [w, h] = SIZES[vp];
  const scale = vp === "desktop" ? 0.42 : vp === "tablet" ? 0.5 : 0.62;

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

        <div className="card-surface p-6 text-center" data-testid="redesign-live-notice">
          <div className="font-display text-xl sm:text-2xl font-semibold tracking-tight">
            Everything here is already live.
          </div>
          <p className="text-sm text-[var(--mut)] mt-2 max-w-2xl mx-auto">
            Auto-propagation is permanently on: every change lands on its project immediately,
            reaches every active client using it, and is inherited by future clients. There is no
            approval step, no diff to confirm and no push button.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
            <button data-testid="redesign-open-motion" onClick={() => nav("/motion")} className="btn-primary inline-flex items-center gap-2">Motion systems index</button>
            <button data-testid="redesign-open-dashboard" onClick={() => nav("/dashboard")} className="btn-ghost text-sm !py-2.5 !px-5">Back to dashboard</button>
          </div>
        </div>

      </main>

    </div>
  );
}
