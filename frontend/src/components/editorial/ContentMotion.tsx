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
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); io?.disconnect(); };
  }, [scopeSelector, ...deps]);

  return null;
}
