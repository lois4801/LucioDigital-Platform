import { useState } from "react";
import { Monitor, Smartphone, ExternalLink, RefreshCw } from "lucide-react";

/** Sticky live preview of the client's own site, refreshed whenever they save an edit. */
export default function PortalPreview({ token, v = 0 }) {
  const [device, setDevice] = useState<"desktop" | "mobile">("desktop");
  const [bump, setBump] = useState(0);
  if (!token) return null;
  const src = `/p/${token}?embed=1&v=${v}-${bump}`;
  const mobile = device === "mobile";

  return (
    <div className="card-surface p-4 lg:sticky lg:top-24" data-testid="portal-preview">
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="overline">Your live site</div>
        <div className="flex items-center gap-1">
          <button data-testid="portal-preview-desktop" onClick={() => setDevice("desktop")}
            title="Desktop" className={`chip cursor-pointer ${!mobile ? "chip-active" : ""}`}><Monitor size={11} /></button>
          <button data-testid="portal-preview-mobile" onClick={() => setDevice("mobile")}
            title="Mobile" className={`chip cursor-pointer ${mobile ? "chip-active" : ""}`}><Smartphone size={11} /></button>
          <button data-testid="portal-preview-refresh" onClick={() => setBump(b => b + 1)}
            title="Refresh" className="chip cursor-pointer"><RefreshCw size={11} /></button>
          <a data-testid="portal-preview-open" href={`/p/${token}`} target="_blank" rel="noreferrer"
            title="Open full site" className="chip cursor-pointer"><ExternalLink size={11} /></a>
        </div>
      </div>
      <div className="rounded-xl overflow-hidden border border-[var(--line)] bg-black flex justify-center">
        <iframe key={src} data-testid="portal-preview-frame" src={src} title="Live site preview"
          className="border-0 origin-top"
          style={mobile
            ? { width: 390, height: 780, transform: "scale(0.72)", marginBottom: -218 }
            : { width: 1280, height: 1000, transform: "scale(0.22)", marginBottom: -780 }}
          scrolling="yes" />
      </div>
      <div className="text-[10px] text-[var(--mut)] mt-2">Updates every time you save a change.</div>
    </div>
  );
}
