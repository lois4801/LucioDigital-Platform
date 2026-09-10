import { useEffect, useState } from "react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Loader2, ShieldCheck } from "lucide-react";
import { previewUrl } from "@/components/SitePreviewOverlay";
import HeroMotionLayer from "@/components/editorial/HeroMotionLayer";
import MotionTuner from "@/components/editorial/MotionTuner";
import VitalsEditor from "@/components/VitalsEditor";
import LocationFields from "@/components/LocationFields";
import AnimationControls from "@/components/AnimationControls";
import ReviewsEditor from "@/components/ReviewsEditor";
import MarqueeEditor from "@/components/MarqueeEditor";
import EditLog from "@/components/EditLog";
import OnboardingChecklist from "@/components/OnboardingChecklist";

const STYLES = [["original", "Original template"], ["editorial", "Editorial motion"]];
const MODES = [["dark", "Dark"], ["light", "Light"]];
const ANIMS = [["full", "Full"], ["reduced", "Reduced"], ["none", "None"]];
const PUB = [["draft", "Draft"], ["preview", "Preview link only"], ["live", "Live"]];

function Row({ label, hint, value, options, onPick, testid, busy = false }) {
  return (
    <div className="py-4 border-b border-[var(--line)] last:border-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold">{label}</div>
          <div className="text-xs text-[var(--mut)] mt-0.5">{hint}</div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {options.map(([v, l]) => (
            <button key={v} data-testid={`${testid}-${v}`} disabled={busy} onClick={() => onPick(v)}
              className={`chip cursor-pointer transition-colors disabled:opacity-60 ${value === v ? "chip-active" : "hover:!text-white"}`}>{l}</button>
          ))}
        </div>
      </div>
    </div>
  );
}

// Per-client Site Mode. Every write is scoped to this one app_id — no other client is touched.
export default function SiteModePanel({ appId, appName, appDoc = null, templates = [] }) {
  const [sm, setSm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [heroes, setHeroes] = useState([]);
  const [renderV, setRenderV] = useState(0);   // bumps the live site render after every save
  const [liveToken, setLiveToken] = useState(appDoc?.preview_token || "");

  useEffect(() => {
    if (!appId) return;
    api.get(`/apps/${appId}/site-mode`).then(r => {
      setSm(r.data);
      // Never rotate an existing link — only mint one when the client has none at all.
      if (r.data.preview_token) setLiveToken(r.data.preview_token);
      else api.post(`/apps/${appId}/preview/regenerate`)
        .then(({ data }) => setLiveToken(data.preview_token || data.token || "")).catch(() => {});
    }).catch(() => {});
    api.get("/editorial/heroes").then(r => setHeroes(r.data.heroes || [])).catch(() => {});
  }, [appId]);

  async function patch(next) {
    setSm(s => ({ ...s, ...next }));
    setBusy(true);
    try {
      const { data } = await api.put(`/apps/${appId}/site-mode`, next);
      setSm(s => ({ ...s, ...data }));
      setRenderV(v => v + 1);
      toast.success("Site Mode updated for this client only");
    } catch (e) {
      if (e.response?.status === 429) {       // the live-site refetch is rate limited; retry once
        await new Promise(r => setTimeout(r, 1300));
        try {
          const { data } = await api.put(`/apps/${appId}/site-mode`, next);
          setSm(s => ({ ...s, ...data }));
          setRenderV(v => v + 1);
          toast.success("Site Mode updated for this client only");
          return;
        } catch { /* fall through to the error toast */ }
      }
      toast.error(e.response?.data?.detail || "Could not save Site Mode");
    } finally { setBusy(false); }
  }

  if (!sm) return <div className="card-surface p-6 text-sm text-[var(--mut)] flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Loading Site Mode…</div>;

  return (
    <div className="card-surface p-6" data-testid="site-mode-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="overline">Site Mode</div>
          <div className="font-display text-xl font-semibold mt-1">{appName}</div>
          <div className="text-xs text-[var(--mut)] mt-0.5">Public site · {sm.publish}</div>
        </div>
        <div className="flex items-center gap-2">
          <span className="chip inline-flex items-center gap-1" data-testid="site-mode-live-badge"><ShieldCheck size={11} /> Live · isolated to this client</span>
        </div>
      </div>

      <div className="mt-4">
        <Row busy={busy} testid="sm-style" label="Design style" hint="Original template look, or the new editorial motion system."
          value={sm.style} options={STYLES} onPick={v => patch({ style: v })} />
        <Row busy={busy} testid="sm-mode" label="Light / dark default" hint="What visitors see first on this client's public site."
          value={sm.mode} options={MODES} onPick={v => patch({ mode: v })} />
        <Row busy={busy} testid="sm-anim" label="Animation intensity" hint="Full motion, subtle transitions only, or completely static."
          value={sm.animation} options={ANIMS} onPick={v => patch({ animation: v })} />
        <Row busy={busy} testid="sm-publish" label="Publishing status" hint="Draft is private, Preview is link-only, Live is public."
          value={sm.publish} options={PUB} onPick={v => patch({ publish: v })} />
        <div className="py-4 border-b border-[var(--line)]">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-sm font-semibold">Signature hero motion</div>
              <div className="text-xs text-[var(--mut)] mt-0.5">Swap this client's hero animation. Applies to Preview, Live and Demo.</div>
            </div>
            <div className="flex items-center gap-2">
              <select data-testid="sm-hero-select" value={sm.hero || ""} onChange={e => patch({ hero: e.target.value })}
                className="bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm outline-none focus:border-[var(--acc)] max-w-[240px]">
                <option value="">— inherit from template —</option>
                {heroes.map(h => <option key={h.hero} value={h.hero}>{h.hero}</option>)}
              </select>
              <a href="/hero-gallery" data-testid="sm-hero-gallery-link" className="chip cursor-pointer hover:!text-white">See all {heroes.length}</a>
            </div>
          </div>
          {sm.hero && (
            <div className="mt-3">
              <div className="relative h-[46vh] min-h-[280px] rounded-xl overflow-hidden bg-[#080808] border border-[var(--line)]"
                data-testid="sm-hero-live-render" data-hero={sm.hero}
                data-speed={sm.motion_speed ?? 1} data-intensity={sm.motion_intensity ?? 1}>
                <HeroMotionLayer hero={sm.hero} accent={sm.accent || "#10B981"}
                  speed={sm.motion_speed ?? 1} intensity={sm.motion_intensity ?? 1} />
                <div className="absolute top-3 left-3 chip !text-black" style={{ background: sm.accent || "#10B981", borderColor: sm.accent || "#10B981" }}>LIVE</div>
                <div className="absolute bottom-3 left-3 font-mono text-[11px] text-white/45">{sm.hero}</div>
              </div>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <div className="text-xs text-[var(--mut)]">Speed and intensity update this live render as you drag.</div>
                <MotionTuner prefix="sm" compact
                  speed={sm.motion_speed ?? 1} intensity={sm.motion_intensity ?? 1}
                  onChange={v => setSm(s => ({
                    ...s,
                    ...(v.speed !== undefined ? { motion_speed: v.speed } : {}),
                    ...(v.intensity !== undefined ? { motion_intensity: v.intensity } : {}),
                  }))}
                  onCommit={() => patch({ motion_speed: sm.motion_speed ?? 1, motion_intensity: sm.motion_intensity ?? 1 })} />
              </div>
            </div>
          )}
        </div>

        <div className="py-4 border-b border-[var(--line)]">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-sm font-semibold">Accent colour</div>
              <div className="text-xs text-[var(--mut)] mt-0.5">Drives every motion layer on this client. Lime is reserved for luciodigital.ca.</div>
            </div>
            <div className="flex items-center gap-2">
              <input type="color" data-testid="sm-accent-picker" value={sm.accent || "#10B981"}
                onChange={e => patch({ accent: e.target.value.toUpperCase() })}
                className="w-10 h-10 rounded-xl bg-transparent border border-[var(--line)] p-0 cursor-pointer" />
              <span className="font-mono text-xs" style={{ color: sm.accent }}>{sm.accent}</span>
              <a href="/accent-audit" data-testid="sm-accent-audit-link" className="chip cursor-pointer hover:!text-white">Audit all</a>
            </div>
          </div>
        </div>

        <AnimationControls appId={appId} accent={sm.accent || "#10B981"} onSaved={() => setRenderV(v => v + 1)} />

        <OnboardingChecklist appId={appId} />

        <ReviewsEditor appId={appId} accent={sm.accent || "#10B981"} />

        <MarqueeEditor appId={appId} accent={sm.accent || "#10B981"}
          mode={sm.mode === "light" ? "light" : "dark"} onSaved={() => setRenderV(v => v + 1)} />

        <EditLog appId={appId} />

        <LocationFields appId={appId} onSaved={() => setRenderV(v => v + 1)} />

        <VitalsEditor appId={appId} accent={sm.accent || "#10B981"} />

        {templates.length > 0 && (
          <div className="py-4">
            <div className="text-sm font-semibold">Active template</div>
            <div className="text-xs text-[var(--mut)] mt-0.5 mb-2">Which industry layout drives this client's site.</div>
            <select data-testid="sm-template" value={sm.template_key || ""} onChange={e => patch({ template_key: e.target.value })}
              className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]">
              <option value="">— none selected —</option>
              {templates.map(t => <option key={t.key} value={t.key}>{t.title || t.key}</option>)}
            </select>
          </div>
        )}
      </div>
      {busy && <div className="mt-3 text-xs text-[var(--mut)] flex items-center gap-2"><Loader2 size={12} className="animate-spin" /> Saving…</div>}

      {/* Live site render — exactly what a public visitor sees, all motion running. */}
      <div className="mt-6 pt-5 border-t border-[var(--line)]" data-testid="sm-live-site-section">
        <div className="flex flex-wrap items-center gap-2">
          <span className="chip !text-black" style={{ background: sm.accent || "#10B981", borderColor: sm.accent || "#10B981" }}>LIVE SITE</span>
          <div className="text-xs text-[var(--mut)]">Every change above lands here immediately — no preview step.</div>
          {liveToken && (
            <a data-testid="sm-live-newtab" href={previewUrl(liveToken)} target="_blank" rel="noreferrer"
              className="ml-auto chip cursor-pointer hover:!text-white">Open full screen</a>
          )}
        </div>
        {liveToken ? (
          <iframe key={`${liveToken}-${renderV}`} data-testid="sm-live-site-frame" title="Live site"
            src={previewUrl(liveToken)}
            className="mt-3 w-full h-[56vh] min-h-[420px] rounded-xl border border-[var(--line)] bg-black" />
        ) : (
          <div className="mt-3 text-sm text-[var(--mut)]" data-testid="sm-live-site-missing">
            This client has no public link yet — set Publishing status to Preview or Live.
          </div>
        )}
      </div>
    </div>
  );
}
