/** Registry of every signature hero motion engine (44 heroes, one bespoke engine each). */
import { CORE_ENGINES } from "./heroEnginesCore";
import { STUDIO_ENGINES } from "./heroEnginesStudio";
import { RESERVED_ENGINES } from "./heroEnginesReserved";
import type { Engine } from "./heroUtils";

export const HERO_ENGINES: Record<string, Engine> = {
  ...CORE_ENGINES,
  ...STUDIO_ENGINES,
  ...RESERVED_ENGINES,
};

export const HERO_NAMES = Object.keys(HERO_ENGINES);
export const FALLBACK_HERO = "particle-network";

export const engineFor = (hero: string): Engine =>
  HERO_ENGINES[hero] || HERO_ENGINES[FALLBACK_HERO];

export type { Engine };
