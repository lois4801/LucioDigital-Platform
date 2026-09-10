import { useEffect, useState } from "react";
import { Monitor, Tablet, Smartphone, X, Play, Loader2, ExternalLink } from "lucide-react";
import api from "@/lib/api";

const SIZES = { desktop: [1440, 900], tablet: [820, 1100], mobile: [390, 844] };
const ICONS = { desktop: Monitor, tablet: Tablet, mobile: Smartphone };

/** Absolute preview URL so it also works when opened in a new tab or copied out. */
export const previewUrl = (token) =>
  `${typeof window !== "undefined" ? window.location.origin : ""}/p/${token}?motion=full`;

// Full-screen live preview of a tenant's site: no editor chrome, all motion active.
export default function SitePreviewOverlay({ appId, previewToken, open, onClose }) {
  const [vp, setVp] = useState("desktop");
  const [token, setToken] = useState(previewToken || "");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!open) return;
    setErr("");
    if (previewToken) { setToken(previewToken); return; }
    // No link yet (or preview disabled) — mint one so Preview always shows the real public site.
    api.post(`/apps/${appId}/preview/regenerate`)
      .then(({ data }) => setToken(data.preview_token || data.token || ""))
      .catch(() => setErr("Could not create a preview link for this tenant."));
  }, [open, appId, previewToken]);

  if (!open) return null;
  const [w, h] = SIZES[vp];

  return (
    <div className="fixed inset-0 z-[110] bg-[#050505] flex flex-col" data-testid="site-preview-overlay">
      <div className="flex items-center justify-between gap-3 px-4 sm:px-6 py-3 border-b border-white/10 bg-black/80 backdrop-blur-xl">
        <div className="overline">Live preview · motion active</div>
        <div className="flex items-center gap-1.5">
          {Object.keys(SIZES).map(k => {
            const I = ICONS[k];
            return (
              <button key={k} data-testid={`site-preview-vp-${k}`} onClick={() => setVp(k)}
                className={`chip cursor-pointer inline-flex items-center gap-1 ${vp === k ? "chip-active" : "hover:!text-white"}`}>
                <I size={11} /> <span className="hidden sm:inline">{k}</span>
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-2">
          {token && (
            <a data-testid="site-preview-newtab" href={previewUrl(token)} target="_blank" rel="noreferrer"
              className="chip cursor-pointer inline-flex items-center gap-1 hover:!text-white">
              <ExternalLink size={11} /> <span className="hidden sm:inline">New tab</span>
            </a>
          )}
          <button data-testid="site-preview-close" onClick={onClose} aria-label="Close preview"
            className="w-9 h-9 rounded-full border border-white/15 flex items-center justify-center text-white/70 hover:text-white hover:bg-white/5">
            <X size={15} />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-auto grid place-items-center p-4">
        {token ? (
          <iframe key={`${vp}-${token}`} data-testid="site-preview-frame" title="Tenant live preview"
            src={previewUrl(token)} className="border border-white/10 rounded-xl bg-black"
            style={{ width: w, height: h, maxWidth: "100%" }} />
        ) : (
          <div className="text-sm text-white/50 flex items-center gap-2" data-testid="site-preview-loading">
            {err ? <span data-testid="site-preview-error">{err}</span>
              : <><Loader2 size={14} className="animate-spin" /> Opening the live site…</>}
          </div>
        )}
      </div>
    </div>
  );
}

export function PreviewSiteButton({ onClick, token = "" }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <button data-testid="site-mode-preview-btn" onClick={onClick}
        className="btn-primary text-sm !py-2 !px-4 inline-flex items-center gap-2">
        <Play size={14} /> Preview Site
      </button>
      {token && (
        <a data-testid="site-mode-preview-newtab" href={previewUrl(token)} target="_blank" rel="noreferrer"
          title="Open the live public site in a new tab"
          className="chip cursor-pointer inline-flex items-center gap-1 hover:!text-white">
          <ExternalLink size={11} /> New tab
        </a>
      )}
    </span>
  );
}
