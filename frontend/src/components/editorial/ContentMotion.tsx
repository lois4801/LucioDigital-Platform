import { useEffect } from "react";

/** Animates the CONTENT instead of the background: every card, stat and service box in the
 *  rendered site rises into place on scroll with a staggered rhythm. One shared
 *  IntersectionObserver, CSS transforms/opacity only — no per-frame work, so the cursor stays smooth.
 */
export default function ContentMotion({ scopeSelector = "[data-content-motion]", deps = [] as any[] }) {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;

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
          // re-count on EVERY re-entry: only fire once the element has actually left the viewport
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
    const tag = () => {
      const root = document.querySelector(scopeSelector);
      if (!root) return;
      io = new IntersectionObserver((entries) => {
        entries.forEach(e => {
          if (e.isIntersecting) { e.target.classList.add("cm-in"); io?.unobserve(e.target); }
        });
      }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });

      const boxes = root.querySelectorAll<HTMLElement>(
        'section [class*="grid"] > *, section article, section figure',
      );
      Array.from(boxes).slice(0, 240).forEach((el, i) => {
        if (el.dataset.cm) return;
        el.dataset.cm = "1";
        el.classList.add("cm-box");
        el.style.transitionDelay = `${(i % 6) * 70}ms`;
        io!.observe(el);
      });
      tagCounters(root);
    };

    const t1 = setTimeout(tag, 60);
    const t2 = setTimeout(tag, 700);       // blocks stream in, so tag once more
    // Safety net: anything already on screen must never stay hidden if the observer misses it.
    const t3 = setTimeout(() => {
      document.querySelectorAll<HTMLElement>(".cm-box:not(.cm-in)").forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.top < innerHeight * 1.1) el.classList.add("cm-in");
      });
    }, 1400);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); io?.disconnect(); counters?.disconnect(); };
  }, [scopeSelector, ...deps]);

  return null;
}
