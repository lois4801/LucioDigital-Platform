export const DEFAULT_THEME = {
  mode: "dark", primary: "#F97316", secondary: "#14B8A6", bg: "#0A0A0F", surface: "#141420",
  fg: "#F8FAFC", muted: "#A1A7B8", border: "#262637", font_heading: "Plus Jakarta Sans", font_body: "Manrope", radius: 16, motion: true, cursor: true, cursor_effect: "none", cursor_density: 1, cursor_speed: 1, glass: true, grain: true, design_v2: false,
};

// Editorial default for every new tenant site: fluid type, glass depth, scroll reveals.
export const V2_THEME = { ...DEFAULT_THEME, font_heading: "Sora", font_body: "Inter", radius: 20, design_v2: true };

export const FONTS = ["Sora", "Inter", "Space Grotesk", "DM Sans", "Plus Jakarta Sans", "Manrope", "Outfit", "Playfair Display", "Poppins", "Nunito",
  "Archivo", "Oswald", "Syne", "Fraunces", "Lora", "Cormorant Garamond", "Barlow Condensed", "Chivo", "JetBrains Mono"];

// Per-template visual identities (mirrors backend site_content.LOOKS) — used for preset previews.
export const SITE_PRESETS = ["industrial", "clinical", "concrete", "energy", "editoriallux", "harbour", "ledger", "techno", "noir", "freight", "saas", "counsel", "campus", "realty", "ember", "cinematic"];

// Part 2 — one switch, complete design transformation. Every value stays admin-overridable after.
export const MODE_PRESETS = {
  light: {
    bg: "#FFFFFF", surface: "#F5F5F0", fg: "#111111", text_body: "#333333", muted: "#555555", border: "#E2E8F0",
    font_heading: "Playfair Display", font_body: "DM Sans", radius: 10, glass: false, grain: false, cursor: false, motion: true, glow: false,
  },
  dark: {
    bg: "#0A0A0F", surface: "#141420", fg: "#FFFFFF", text_body: "#E5E5E5", muted: "#A1A7B8", border: "#262637",
    font_heading: "Space Grotesk", font_body: "Inter", radius: 3, glass: true, grain: true, cursor: true, motion: true, glow: true,
  },
};

export function applyMode(theme, mode) {
  const p = MODE_PRESETS[mode] || MODE_PRESETS.dark;
  return { ...(theme || {}), ...p, mode };
}

const LIGHT = { bg: "#FFFFFF", surface: "#F5F5F0", fg: "#111111", muted: "#555555", border: "#E2E8F0" };
const isDarkHex = (h) => /^#[0-9a-f]{6}$/i.test(h || "") && parseInt(h.slice(1, 3), 16) * 0.299 + parseInt(h.slice(3, 5), 16) * 0.587 + parseInt(h.slice(5, 7), 16) * 0.114 < 128;

export const isV2 = (t) => !!(t && t.design_v2);
export const modeCls = (t) => `tmode-${(t?.mode === "light" ? "light" : "dark")}${t?.site_preset ? ` pr-site-${t.site_preset}` : ""}`;

export function themeVars(t) {
  const th = { ...DEFAULT_THEME, ...(t || {}) };
  const dark = th.mode === "dark";
  const pick = (k) => dark ? (isDarkHex(th[k]) || k === "fg" || k === "muted" ? th[k] : DEFAULT_THEME[k]) : (isDarkHex(th[k]) && k !== "fg" && k !== "muted" ? LIGHT[k] : th[k] || LIGHT[k]);
  // Headings and body copy are locked to legible values per mode so scroll reveals can never
  // animate white-on-white (or dark-on-dark).
  const head = dark ? (isDarkHex(th.fg) ? "#FFFFFF" : th.fg) : (isDarkHex(th.fg) ? th.fg : "#111111");
  const body = dark ? (th.text_body && !isDarkHex(th.text_body) ? th.text_body : "#E5E5E5") : (th.text_body && isDarkHex(th.text_body) ? th.text_body : "#333333");
  return {
    "--tp": th.primary, "--ts": th.secondary,
    "--tbg": pick("bg"), "--tsf": pick("surface"),
    "--tfg": head, "--thead": head, "--tbody": body,
    "--tmut": dark ? (isDarkHex(th.muted) ? "#A1A7B8" : th.muted) : (isDarkHex(th.muted) ? th.muted : LIGHT.muted), "--tbd": pick("border"),
    "--tglass": dark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.75)", "--tglow": `${th.primary}33`,
    "--tr": `${th.radius}px`, "--tfh": `'${th.font_heading}', sans-serif`, "--tfb": `'${th.font_body}', sans-serif`,
    // Fluid editorial type scale — resizes smoothly between 390px and 1600px, no breakpoint jumps.
    "--t-h1": "clamp(2.5rem, 1.6rem + 4.4vw, 5.25rem)",
    "--t-h2": "clamp(1.9rem, 1.35rem + 2.4vw, 3.25rem)",
    "--t-h3": "clamp(1.15rem, 1rem + 0.6vw, 1.5rem)",
    "--t-lead": "clamp(1.05rem, 0.98rem + 0.5vw, 1.4rem)",
    "--t-body": "clamp(0.95rem, 0.92rem + 0.18vw, 1.05rem)",
    "--t-small": "clamp(0.78rem, 0.76rem + 0.1vw, 0.85rem)",
    // Vertical rhythm
    "--rh-sm": "clamp(2.75rem, 2rem + 3vw, 4.5rem)",
    "--rh-md": "clamp(4rem, 2.75rem + 5vw, 7.5rem)",
    "--rh-lg": "clamp(5.5rem, 3.5rem + 7vw, 10rem)",
  };
}

const VARIABLE_AXIS = {
  Sora: "wght@100..800", Inter: "wght@100..900", "Space Grotesk": "wght@300..700", "DM Sans": "wght@100..1000", Outfit: "wght@100..900",
  Manrope: "wght@200..800", "Plus Jakarta Sans": "wght@200..800", Archivo: "wght@100..900", Oswald: "wght@200..700", Syne: "wght@400..800",
  Fraunces: "wght@100..900", Lora: "wght@400..700", "Cormorant Garamond": "wght@300;400;500;600;700", "Barlow Condensed": "wght@100;200;300;400;500;600;700;800;900",
  Chivo: "wght@100..900", "JetBrains Mono": "wght@100..800", "Playfair Display": "wght@400..900", Nunito: "wght@200..1000", Poppins: "wght@300;400;500;600;700;800",
};
const axis = (f) => VARIABLE_AXIS[f] || "wght@400;500;600;700";

export function loadFonts(t) {
  const th = { ...DEFAULT_THEME, ...(t || {}) };
  const id = "tenant-fonts";
  const fam = (f) => `family=${f.replace(/ /g, "+")}:${axis(f)}`;
  const href = `https://fonts.googleapis.com/css2?${fam(th.font_heading)}&${fam(th.font_body)}&display=swap`;
  let el = document.getElementById(id);
  if (!el) { el = document.createElement("link"); el.id = id; el.rel = "stylesheet"; document.head.appendChild(el); }
  if (el.href !== href) el.href = href;
}
