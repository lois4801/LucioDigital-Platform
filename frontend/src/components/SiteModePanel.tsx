import { useEffect, useState } from "react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Loader2, ShieldCheck } from "lucide-react";
import SitePreviewOverlay, { PreviewSiteButton } from "@/components/SitePreviewOverlay";

const STYLES = [["original", "Original template"], ["editorial", "Editorial motion"]];
const MODES = [["dark", "Dark"], ["light", "Light"]];
const ANIMS = [["full", "Full"], ["reduced", "Reduced"], ["none", "None"]];
const PUB = [["draft", "Draft"], ["preview", "Preview link only"], ["live", "Live"]];

function Row({ label, hint, value, options, onPick, testid }) {
  return (
    <div className="py-4 border-b border-[var(--line)] last:border-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold">{label}</div>
          <div className="text-xs text-[var(--mut)] mt-0.5">{hint}</div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {options.map(([v, l]) => (
            <button key={v} data-testid={`${testid}-${v}`} onClick={() => onPick(v)}
              className={`chip cursor-pointer transition-colors ${value === v ? "chip-active" : "hover:!text-white"}`}>{l}</button>
          ))}
        </div>
      </div>
    </div>
  );
}

// Per-tenant Site Mode. Every write is scoped to this one app_id — no other tenant is touched.
export default function SiteModePanel({ appId, appName, appDoc = null, templates = [] }) {
  const [sm, setSm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(false);

  useEffect(() => {
    if (!appId) return;
    api.get(`/apps/${appId}/site-mode`).then(r => setSm(r.data)).catch(() => {});
  }, [appId]);

  async function patch(next) {
    setSm(s => ({ ...s, ...next }));
    setBusy(true);
    try {
      const { data } = await api.put(`/apps/${appId}/site-mode`, next);
      setSm(s => ({ ...s, ...data }));
      toast.success("Site Mode updated for this tenant only");
    } catch (e) {
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
          <PreviewSiteButton onClick={() => setPreview(true)} />
          <span className="chip inline-flex items-center gap-1"><ShieldCheck size={11} /> Isolated to this tenant</span>
        </div>
      </div>

      <div className="mt-4">
        <Row testid="sm-style" label="Design style" hint="Original template look, or the new editorial motion system."
          value={sm.style} options={STYLES} onPick={v => patch({ style: v })} />
        <Row testid="sm-mode" label="Light / dark default" hint="What visitors see first on this tenant's public site."
          value={sm.mode} options={MODES} onPick={v => patch({ mode: v })} />
        <Row testid="sm-anim" label="Animation intensity" hint="Full motion, subtle transitions only, or completely static."
          value={sm.animation} options={ANIMS} onPick={v => patch({ animation: v })} />
        <Row testid="sm-publish" label="Publishing status" hint="Draft is private, Preview is link-only, Live is public."
          value={sm.publish} options={PUB} onPick={v => patch({ publish: v })} />
        {templates.length > 0 && (
          <div className="py-4">
            <div className="text-sm font-semibold">Active template</div>
            <div className="text-xs text-[var(--mut)] mt-0.5 mb-2">Which industry layout drives this tenant's site.</div>
            <select data-testid="sm-template" value={sm.template_key || ""} onChange={e => patch({ template_key: e.target.value })}
              className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]">
              <option value="">— none selected —</option>
              {templates.map(t => <option key={t.key} value={t.key}>{t.title || t.key}</option>)}
            </select>
          </div>
        )}
      </div>
      {busy && <div className="mt-3 text-xs text-[var(--mut)] flex items-center gap-2"><Loader2 size={12} className="animate-spin" /> Saving…</div>}
      <SitePreviewOverlay open={preview} appId={appId} previewToken={appDoc?.preview_token}
        onClose={() => setPreview(false)} />
    </div>
  );
}
