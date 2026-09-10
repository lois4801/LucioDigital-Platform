/** PowerPoint-style entrance animations for content boxes.
 *  Every one of the 33 templates gets its OWN animation, the team section always uses a
 *  different one, and a tenant can override the whole site from Site Mode. */

export type BoxAnim = { key: string; label: string; dur: number };

export const BOX_ANIMS: BoxAnim[] = [
  { key: "appear", label: "Appear", dur: 260 },
  { key: "fade", label: "Fade", dur: 820 },
  { key: "fly-in", label: "Fly In", dur: 780 },
  { key: "float-in", label: "Float In", dur: 800 },
  { key: "split", label: "Split", dur: 760 },
  { key: "wipe", label: "Wipe", dur: 740 },
  { key: "shape", label: "Shape", dur: 820 },
  { key: "wheel", label: "Wheel", dur: 860 },
  { key: "random-bars", label: "Random Bars", dur: 780 },
  { key: "grow-turn", label: "Grow & Turn", dur: 800 },
  { key: "zoom", label: "Zoom", dur: 720 },
  { key: "swivel", label: "Swivel", dur: 840 },
  { key: "bounce", label: "Bounce", dur: 900 },
  { key: "pulse", label: "Pulse", dur: 820 },
  { key: "spin", label: "Spin", dur: 880 },
  { key: "grow-shrink", label: "Grow / Shrink", dur: 780 },
  { key: "teeter", label: "Teeter", dur: 860 },
  { key: "dissolve", label: "Dissolve", dur: 860 },
  { key: "blinds", label: "Blinds", dur: 800 },
  { key: "checkerboard", label: "Checkerboard", dur: 820 },
  { key: "box-in", label: "Box In", dur: 780 },
  { key: "plus-in", label: "Plus", dur: 800 },
  { key: "diamond", label: "Diamond", dur: 820 },
  { key: "peek-in", label: "Peek In", dur: 760 },
  { key: "rise-up", label: "Rise Up", dur: 840 },
  { key: "stretch", label: "Stretch", dur: 760 },
  { key: "compress", label: "Compress", dur: 740 },
  { key: "whip", label: "Whip", dur: 800 },
  { key: "spiral-in", label: "Spiral In", dur: 900 },
  { key: "darken", label: "Darken", dur: 800 },
  { key: "lighten", label: "Lighten", dur: 800 },
  { key: "desaturate", label: "Desaturate", dur: 840 },
  { key: "transparency", label: "Transparency", dur: 820 },
  { key: "wave", label: "Wave", dur: 880 },
  { key: "bold-flash", label: "Bold Flash", dur: 780 },
  { key: "bold-reveal", label: "Bold Reveal", dur: 820 },
  { key: "color-pulse", label: "Colour Pulse", dur: 840 },
  { key: "credits", label: "Credits", dur: 900 },
  { key: "none", label: "None", dur: 0 },
];

export const ANIM_KEYS = BOX_ANIMS.map(a => a.key);
const PLAYABLE = ANIM_KEYS.filter(k => k !== "none");

/** One unique animation per template — all 33 differ. */
export const TEMPLATE_ANIM: Record<string, string> = {
  hvac: "fly-in",
  healthcare: "float-in",
  construction: "wipe",
  fitness: "bounce",
  retail: "zoom",
  hospitality: "fade",
  finance: "split",
  it_services: "random-bars",
  creative_studio: "shape",
  logistics: "wheel",
  saas: "grow-turn",
  legal: "appear",
  education: "swivel",
  real_estate: "grow-shrink",
  restaurant: "pulse",
  events: "spin",
  veterinary: "teeter",
  dental: "dissolve",
  accounting: "blinds",
  landscaping: "checkerboard",
  photography: "box-in",
  automotive: "whip",
  beauty: "color-pulse",
  insurance: "plus-in",
  pet_grooming: "peek-in",
  hvac_plumbing: "diamond",
  coworking: "rise-up",
  wellness: "desaturate",
  cleaning: "lighten",
  music_school: "wave",
  nonprofit: "bold-reveal",
  architecture: "compress",
  test_template: "spiral-in",
};

const hash = (s: string, seed: number) => Math.abs([...(s || "x")].reduce((a, c) => a * 31 + c.charCodeAt(0), seed));

export const animForTemplate = (key: string) =>
  TEMPLATE_ANIM[key] || PLAYABLE[hash(key, 7) % PLAYABLE.length];

/** The team section always uses a different entrance from the rest of the template. */
export const teamAnimFor = (key: string) => {
  const main = animForTemplate(key);
  const pool = PLAYABLE.filter(k => k !== main && k !== "appear");
  return pool[hash(key, 11) % pool.length];
};

export const durFor = (key: string) => BOX_ANIMS.find(a => a.key === key)?.dur || 780;

/** Sections that can carry their own entrance. */
export const SECTIONS: [string, string][] = [
  ["hero", "Hero"], ["services", "Services / Features"], ["testimonials", "Testimonials"],
  ["team", "Team"], ["pricing", "Pricing"], ["stats", "Stats"], ["gallery", "Gallery"],
  ["faq", "FAQ"], ["contact", "Contact"],
];
const SECTION_KEYS = SECTIONS.map(s => s[0]);

const BLOCK_SECTION: Record<string, string> = {
  hero: "hero", "hero-cover": "hero", cover: "hero",
  features: "services", services: "services", cards: "services", steps: "services",
  testimonials: "testimonials", quotes: "testimonials", logos: "testimonials",
  team: "team", pricing: "pricing", plans: "pricing",
  stats: "stats", metrics: "stats",
  gallery: "gallery", media: "gallery",
  faq: "faq", accordion: "faq",
  contact: "contact", form: "contact", cta: "contact",
};
export const sectionOfBlock = (type: string) => BLOCK_SECTION[type || ""] || "";

const TEMPLATE_ORDER = Object.keys(TEMPLATE_ANIM);

/** Each template ships a distinct combination of per-section entrances. */
export const sectionAnimFor = (templateKey: string, section: string) => {
  if (!section) return animForTemplate(templateKey);
  const ti = TEMPLATE_ORDER.indexOf(templateKey);
  const base = ti >= 0 ? ti : hash(templateKey, 5) % PLAYABLE.length;
  const si = Math.max(0, SECTION_KEYS.indexOf(section));
  return PLAYABLE[(base * 7 + si * 3) % PLAYABLE.length];
};
