/** LucioDigital brand marks. Hand-drawn SVG so they stay sharp at any size and recolour instantly. */

type Variant = "white" | "lime" | "dark";

const LIME = "#84FF00";

function colours(variant: Variant) {
  if (variant === "lime") return { word: LIME, mark: "#FFFFFF" };
  if (variant === "dark") return { word: "#000000", mark: "#000000" };
  return { word: "#FFFFFF", mark: "#FFFFFF" };
}

/** Standalone icon mark: three forward-leaning blades — digital layers in motion. */
export function LogoMark({ size = 28, color = "currentColor", className = "", testid = "logo-mark" }) {
  return (
    <svg data-testid={testid} className={className} width={size} height={size} viewBox="0 0 32 32"
      fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M4 24.5 12.5 5h6.2L10.2 24.5H4Z" fill={color} />
      <path d="M14.2 24.5 22.7 5h3.5l-8.5 19.5h-3.5Z" fill={color} opacity="0.62" />
      <path d="M22 24.5 28.6 9.5H30l-6.6 15H22Z" fill={color} opacity="0.34" />
    </svg>
  );
}

/** Full lockup: icon mark + "LucioDigital" wordmark. */
export default function Logo({ variant = "white" as Variant, size = 20, className = "", markSize = 0, testid = "logo" }) {
  const c = colours(variant);
  return (
    <span data-testid={testid} className={`inline-flex items-center gap-2.5 ${className}`}>
      <LogoMark size={markSize || Math.round(size * 1.45)} color={c.mark} />
      <span className="font-display font-bold tracking-[-0.035em] leading-none whitespace-nowrap"
        style={{ fontSize: size, color: c.word }}>
        Lucio<span style={{ color: variant === "lime" ? "#FFFFFF" : c.word, opacity: variant === "lime" ? 1 : 0.72 }}>Digital</span>
      </span>
    </span>
  );
}

/** Splash / loading mark, centred on the platform near-black. */
export function LogoSplash({ testid = "logo-splash" }) {
  return (
    <div data-testid={testid} className="flex items-center justify-center py-16" style={{ background: "#080808" }}>
      <LogoMark size={44} color="#FFFFFF" className="animate-pulse" />
    </div>
  );
}
