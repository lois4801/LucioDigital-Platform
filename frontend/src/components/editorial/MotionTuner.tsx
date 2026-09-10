import { useState } from "react";

/** Shared speed / intensity tuner for any hero motion engine. */
export const SPEEDS = { min: 0.25, max: 2, step: 0.05 };
export const INTENSITIES = { min: 0.2, max: 1.5, step: 0.05 };

export default function MotionTuner({
  speed, intensity, onChange, onCommit, compact = false, prefix = "tuner",
}: {
  speed: number; intensity: number;
  onChange: (v: { speed?: number; intensity?: number }) => void;
  onCommit?: () => void;
  compact?: boolean;
  prefix?: string;
}) {
  const [dirty, setDirty] = useState(false);
  const commit = () => { if (dirty && onCommit) { onCommit(); setDirty(false); } };
  const label = compact ? "text-[10px]" : "text-xs";

  return (
    <div className={`flex min-w-0 ${compact ? "flex-wrap items-center gap-x-4 gap-y-2" : "flex-col gap-3"}`} data-testid={`${prefix}-motion-tuner`}>
      <label className="flex items-center gap-2 min-w-0">
        <span className={`overline ${label} shrink-0`}>Speed</span>
        <input type="range" data-testid={`${prefix}-speed`} min={SPEEDS.min} max={SPEEDS.max} step={SPEEDS.step}
          value={speed} onChange={e => { setDirty(true); onChange({ speed: Number(e.target.value) }); }}
          onMouseUp={commit} onTouchEnd={commit} onKeyUp={commit}
          className="w-24 sm:w-36 accent-[var(--acc)] cursor-pointer" />
        <span data-testid={`${prefix}-speed-value`} className="font-mono text-[11px] text-[var(--mut)] w-10">{speed.toFixed(2)}x</span>
      </label>
      <label className="flex items-center gap-2 min-w-0">
        <span className={`overline ${label} shrink-0`}>Intensity</span>
        <input type="range" data-testid={`${prefix}-intensity`} min={INTENSITIES.min} max={INTENSITIES.max} step={INTENSITIES.step}
          value={intensity} onChange={e => { setDirty(true); onChange({ intensity: Number(e.target.value) }); }}
          onMouseUp={commit} onTouchEnd={commit} onKeyUp={commit}
          className="w-24 sm:w-36 accent-[var(--acc)] cursor-pointer" />
        <span data-testid={`${prefix}-intensity-value`} className="font-mono text-[11px] text-[var(--mut)] w-8">{intensity.toFixed(2)}</span>
      </label>
    </div>
  );
}
