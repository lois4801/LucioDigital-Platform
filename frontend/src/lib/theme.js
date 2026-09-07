export const DEFAULT_THEME = {
  mode: "light", primary: "#F97316", secondary: "#14B8A6", bg: "#FFFFFF", surface: "#F8FAFC",
  fg: "#0F172A", muted: "#64748B", border: "#E2E8F0", font_heading: "Plus Jakarta Sans", font_body: "Manrope", radius: 16, motion: true, cursor: true,
};

export const FONTS = ["Plus Jakarta Sans", "Manrope", "Space Grotesk", "DM Sans", "Sora", "Outfit", "Playfair Display", "Poppins", "Nunito"];

export function themeVars(t) {
  const th = { ...DEFAULT_THEME, ...(t || {}) };
  const dark = th.mode === "dark";
  return {
    "--tp": th.primary, "--ts": th.secondary,
    "--tbg": dark ? "#0B0F17" : th.bg, "--tsf": dark ? "#111827" : th.surface,
    "--tfg": dark ? "#F8FAFC" : th.fg, "--tmut": dark ? "#94A3B8" : th.muted, "--tbd": dark ? "#1F2937" : th.border,
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
