export const DEFAULT_THEME = {
  mode: "dark", primary: "#F97316", secondary: "#14B8A6", bg: "#0A0A0F", surface: "#141420",
  fg: "#F8FAFC", muted: "#A1A7B8", border: "#262637", font_heading: "Plus Jakarta Sans", font_body: "Manrope", radius: 16, motion: true, cursor: true, glass: true, grain: true,
};

export const FONTS = ["Plus Jakarta Sans", "Manrope", "Space Grotesk", "DM Sans", "Sora", "Outfit", "Playfair Display", "Poppins", "Nunito"];

const LIGHT = { bg: "#FFFFFF", surface: "#F8FAFC", fg: "#0F172A", muted: "#64748B", border: "#E2E8F0" };
const isDarkHex = (h) => /^#[0-9a-f]{6}$/i.test(h || "") && parseInt(h.slice(1, 3), 16) * 0.299 + parseInt(h.slice(3, 5), 16) * 0.587 + parseInt(h.slice(5, 7), 16) * 0.114 < 128;

export function themeVars(t) {
  const th = { ...DEFAULT_THEME, ...(t || {}) };
  const dark = th.mode === "dark";
  const pick = (k) => dark ? (isDarkHex(th[k]) || k === "fg" || k === "muted" ? th[k] : DEFAULT_THEME[k]) : (isDarkHex(th[k]) && k !== "fg" && k !== "muted" ? LIGHT[k] : th[k] || LIGHT[k]);
  return {
    "--tp": th.primary, "--ts": th.secondary,
    "--tbg": pick("bg"), "--tsf": pick("surface"),
    "--tfg": dark ? (isDarkHex(th.fg) ? "#F8FAFC" : th.fg) : (isDarkHex(th.fg) ? th.fg : LIGHT.fg), "--tmut": dark ? (isDarkHex(th.muted) ? "#A1A7B8" : th.muted) : (isDarkHex(th.muted) ? th.muted : LIGHT.muted), "--tbd": pick("border"),
    "--tglass": dark ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.6)", "--tglow": `${th.primary}33`,
    "--tr": `${th.radius}px`, "--tfh": `'${th.font_heading}', sans-serif`, "--tfb": `'${th.font_body}', sans-serif`,
  };
}

export function loadFonts(t) {
  const th = { ...DEFAULT_THEME, ...(t || {}) };
  const id = "tenant-fonts";
  const href = `https://fonts.googleapis.com/css2?family=${th.font_heading.replace(/ /g, "+")}:wght@500;600;700;800&family=${th.font_body.replace(/ /g, "+")}:wght@400;500;600&display=swap`;
  let el = document.getElementById(id);
  if (!el) { el = document.createElement("link"); el.id = id; el.rel = "stylesheet"; document.head.appendChild(el); }
  if (el.href !== href) el.href = href;
}
