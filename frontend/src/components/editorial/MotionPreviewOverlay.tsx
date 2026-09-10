import { useEffect, useState } from "react";
import api from "@/lib/api";
import { X } from "lucide-react";
import MotionStage from "./MotionStage";
import MotionSwitcher from "./MotionSwitcher";
import MotionTuner from "./MotionTuner";

/** Full LIVE render of one motion system, with the industry template name on top and the
 *  live switcher so a visitor can move between all 44 systems. Always on, always live. */
export default function MotionPreviewOverlay({ templateKey, onClose, onSwitch }) {
  const [data, setData] = useState(null);
  const [speed, setSpeed] = useState(1);
  const [intensity, setIntensity] = useState(1);

  useEffect(() => {
    if (!templateKey) return;
    api.get(`/public/motion-preview/${templateKey}`).then(r => setData(r.data)).catch(() => setData(null));
  }, [templateKey]);

  if (!templateKey) return null;
  const live = data && data.template_key === templateKey ? data : null;

  return (
    <div className="fixed inset-0 z-[130] bg-[#080808] overflow-auto" data-testid="motion-live-overlay">
      <MotionSwitcher value={templateKey} onPick={k => (k ? onSwitch(k) : onClose())} />
      <div className="px-4 sm:px-6 py-3 flex flex-wrap items-center gap-3 border-b border-white/10 bg-black/60 backdrop-blur-xl sticky top-[49px] z-[65]">
        <div className="min-w-0">
          <div className="overline text-[#84FF00]">LIVE</div>
          <div className="font-display text-lg font-semibold" data-testid="motion-live-title">
            {live?.industry || templateKey} <span className="text-white/35 font-mono text-xs">{live?.profile?.hero || ""}</span>
          </div>
        </div>
        <span data-testid="motion-live-status"
          className={`chip ${live?.status === "active" ? "!text-black" : ""}`}
          style={live?.status === "active" ? { background: "#84FF00", borderColor: "#84FF00" } : undefined}>
          {live?.status === "active" ? "ACTIVE" : "RESERVED"}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <MotionTuner prefix="live" compact speed={speed} intensity={intensity}
            onChange={v => { if (v.speed !== undefined) setSpeed(v.speed); if (v.intensity !== undefined) setIntensity(v.intensity); }} />
          <button data-testid="motion-live-close" onClick={onClose} aria-label="Close"
            className="w-9 h-9 rounded-full border border-white/15 flex items-center justify-center text-white/70 hover:text-white hover:bg-white/5 cursor-pointer">
            <X size={15} />
          </button>
        </div>
      </div>
      {live?.profile && (
        <MotionStage key={templateKey} profile={live.profile} industry={live.industry} speed={speed} intensity={intensity} />
      )}
    </div>
  );
}
