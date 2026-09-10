import { useEffect } from "react";
import { animForTemplate, teamAnimFor, durFor, sectionOfBlock, sectionAnimFor } from "@/lib/boxAnims";

/** PowerPoint-style entrance animations for the CONTENT: every card, stat box, heading and
 *  paragraph group plays an entrance each time it scrolls into view. Per-section overrides win,
 *  then the tenant's site-wide choice, then the template's own per-section defaults.
 *  One shared IntersectionObserver, CSS animations only, so the cursor stays smooth. */
export default function ContentMotion({
  scopeSelector = "[data-content-motion]",
  templateKey = "",
  anim = "",              // tenant override; falls back to the template's own entrance
  teamAnim = "",
  speed = 1,              // 0.5x – 2x playback
  stagger = 90,           // ms between boxes
  sections = {} as Record<string, string>,
  deps = [] as any[],
}) {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const sp = Math.min(2, Math.max(0.5, Number(speed) || 1));
    const st = Math.min(200, Math.max(0, Number(stagger) ?? 90));
    const main = anim || animForTemplate(templateKey);
    const team = teamAnim || (anim ? anim : teamAnimFor(templateKey));
    if (main === "none" && team === "none") return;

    let io: IntersectionObserver | null = null;
    let counters: IntersectionObserver | null = null;

    /** Counts a stat up from zero every time it scrolls into view (either direction). */
    const runCount = (el: HTMLElement) => {
      const raw = el.dataset.cmRaw || el.textContent || "";
      const m = raw.match(/^(\D*?)([\d][\d.,]*)(.*)$/s);
      if (!m) return;
      el.dataset.cmRaw = raw;
      const [, pre, numStr, post] = m;
      const dec = (numStr.split(".")[1] || "").length;
      const target = parseFloat(numStr.replace(/,/g, ""));
      if (!isFinite(target)) return;
      const grouped = numStr.includes(",");
      const t0 = performance.now(), dur = 950;
      const tick = (now: number) => {
        const p = Math.min(1, (now - t0) / dur);
        const e = 1 - Math.pow(1 - p, 3);
        const v = target * e;
        const shown = dec ? v.toFixed(dec) : Math.round(v).toString();
        el.textContent = pre + (grouped ? Number(shown).toLocaleString() : shown) + post;
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };

    const tagCounters = (root: Element) => {
      counters = new IntersectionObserver((entries) => {
        entries.forEach(e => {
          const el = e.target as HTMLElement;
          if (!e.isIntersecting) { el.dataset.cmOut = "1"; return; }
          if (el.dataset.cmRan && !el.dataset.cmOut) return;
          delete el.dataset.cmOut;
          el.dataset.cmRan = "1";
          runCount(el);
        });
      }, { threshold: [0, 0.3] });
      const candidates = root.querySelectorAll<HTMLElement>("section div, section span, section strong, section dd, section p");
      Array.from(candidates).forEach(el => {
        if (el.dataset.cmNum || el.children.length) return;
        const txt = (el.textContent || "").trim();
        if (!/^\D{0,3}[\d][\d.,]*\s*\D{0,8}$/.test(txt) || txt.length > 12) return;
        if (parseFloat(getComputedStyle(el).fontSize) < 20) return;   // stats only, never body copy
        el.dataset.cmNum = "1";
        el.dataset.cmRaw = txt;
        counters!.observe(el);
      });
    };

    const register = (el: HTMLElement, i: number) => {
      if (el.dataset.cm) return;
      // never animate decorative layers (scrims, blur blobs, motion canvases) — text groups only
      const cs = getComputedStyle(el);
      if (cs.position === "absolute" || cs.position === "fixed") return;
      if (!(el.textContent || "").trim() && !el.querySelector("img, svg, canvas")) return;
      const inTeam = !!el.closest('[data-testid="block-team"]');
      const blockType = (el.closest("[data-block-type]") as HTMLElement | null)?.dataset.blockType || "";
      const section = inTeam ? "team" : sectionOfBlock(blockType);
      const key = sections[section]                              // per-section override wins
        || (inTeam && !anim ? team : "")                          // team keeps its own default
        || anim                                                   // then the site-wide choice
        || (section ? sectionAnimFor(templateKey, section) : main); // then template defaults
      if (key === "none") return;
      el.dataset.cm = "1";
      el.dataset.cmSection = section || "site";
      el.classList.add("cm-box", `cm-a-${key}`);
      el.style.setProperty("--cm-dur", `${Math.round(durFor(key) / sp)}ms`);
      el.style.setProperty("--cm-delay", `${(i % 6) * st}ms`);
      io!.observe(el);
    };

    const tag = () => {
      const root = document.querySelector(scopeSelector);
      if (!root) return;
      if (!io) {
        io = new IntersectionObserver((entries) => {
          entries.forEach(e => {
            const el = e.target as HTMLElement;
            // replays on every re-entry, in both scroll directions
            if (e.isIntersecting) el.classList.add("cm-in");
            else if (e.intersectionRatio === 0) el.classList.remove("cm-in");
          });
        }, { threshold: [0, 0.16], rootMargin: "0px 0px -6% 0px" });
      }

      // one group per box: the card animates as a whole, carrying its icon, heading and copy
      const boxes = Array.from(root.querySelectorAll<HTMLElement>(
        'section [class*="grid"] > *, section article, section figure',
      )).slice(0, 240);
      boxes.forEach(register);

      // headings and standalone copy get the same entrance, as their own group
      Array.from(root.querySelectorAll<HTMLElement>("section > h1, section > h2, section > h3, section > p, section > div, section > blockquote"))
        .slice(0, 160)
        .filter(el => !el.dataset.cm && !el.closest(".cm-box") && !el.querySelector(".cm-box"))
        .forEach(register);

      tagCounters(root);
    };

    const t1 = setTimeout(tag, 60);
    const t2 = setTimeout(tag, 700);       // blocks stream in, so tag once more
    // Safety net: anything already on screen must never stay hidden if the observer misses it.
    const t3 = setTimeout(() => {
      document.querySelectorAll<HTMLElement>(".cm-box:not(.cm-in)").forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.top < innerHeight * 1.1 && r.bottom > 0) el.classList.add("cm-in");
      });
    }, 1400);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); io?.disconnect(); counters?.disconnect(); };
  }, [scopeSelector, templateKey, anim, teamAnim, speed, stagger, JSON.stringify(sections), ...deps]);

  return null;
}
