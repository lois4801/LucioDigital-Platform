import { useEffect, useRef, useState } from "react";

/** Reviews & testimonials: a fixed title and subtitle, with 5-star cards that auto-scroll slowly
 *  left to right. Arrows steer manually then hand back to the auto-scroll. Each quote types itself
 *  out the moment its card enters the viewport. Colour follows the template palette unless the
 *  tenant overrides it in Site Mode. */

const Stars = ({ colour }) => (
  <div className="flex gap-0.5 shrink-0" aria-label="5 out of 5 stars" data-testid="review-stars">
    {[0, 1, 2, 3, 4].map(i => (
      <svg key={i} width="12" height="12" viewBox="0 0 24 24" fill={colour} aria-hidden>
        <path d="M12 2.5l2.9 6.1 6.6.9-4.8 4.6 1.2 6.6L12 17.6 6.1 20.7l1.2-6.6L2.5 9.5l6.6-.9L12 2.5z" />
      </svg>
    ))}
  </div>
);

function TypedQuote({ text, active, colour }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!active) return;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { setN(text.length); return; }
    setN(0);
    let i = 0;
    const id = setInterval(() => {
      i += 3;                                   // types fast, as if spoken live
      setN(Math.min(text.length, i));
      if (i >= text.length) clearInterval(id);
    }, 16);
    return () => clearInterval(id);
  }, [text, active]);
  const shown = active ? text.slice(0, n) : text;
  const typing = active && n < text.length;
  return (
    <blockquote className="mt-3 text-sm leading-relaxed min-h-[92px]" data-testid="review-quote">
      <span className="opacity-90">{shown}</span>
      {typing && <span className="inline-block w-[2px] h-[1em] align-[-0.15em] ml-0.5 animate-pulse"
        style={{ background: colour }} data-testid="review-cursor" />}
    </blockquote>
  );
}

function Card({ r, colour, cardBg, index }) {
  const ref = useRef(null);
  const [active, setActive] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setActive(e.isIntersecting), { threshold: 0.55 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  const initials = (r.company || r.name || "?").split(" ").filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();
  return (
    <article ref={ref} data-testid={`review-card-${index}`}
      className="shrink-0 w-[310px] sm:w-[352px] rounded-[var(--tr,16px)] p-5 flex flex-col"
      style={{ background: cardBg, border: `1px solid ${colour}44` }}>
      <div className="flex items-start gap-3">
        {r.photo
          ? <img src={r.photo} alt={r.name} loading="lazy" decoding="async"
            className="w-11 h-11 rounded-xl object-cover shrink-0" style={{ border: `1px solid ${colour}55` }} />
          : <div className="w-11 h-11 rounded-xl shrink-0 grid place-items-center text-xs font-bold"
            style={{ background: `${colour}22`, color: colour }}>{initials}</div>}
        <div className="min-w-0">
          <div className="text-sm font-bold truncate" data-testid="review-company">{r.company}</div>
          <div className="text-xs opacity-75 truncate">{r.name}{r.title ? ` · ${r.title}` : ""}</div>
        </div>
        <div className="ml-auto"><Stars colour={colour} /></div>
      </div>

      <div className="mt-2 flex items-center gap-1.5 text-[11px] opacity-60">
        {r.flag && <img src={`https://flagcdn.com/w20/${r.flag}.png`} alt={r.country || ""} loading="lazy"
          className="w-4 h-auto rounded-[2px]" data-testid="review-flag" />}
        <span className="truncate" data-testid="review-place">{[r.city, r.country].filter(Boolean).join(", ")}</span>
        {r.company_desc && <span className="truncate opacity-80">· {r.company_desc}</span>}
      </div>

      <div className="mt-1 pl-3" style={{ borderLeft: `2px solid ${colour}` }}>
        <TypedQuote text={r.quote || ""} active={active} colour={colour} />
      </div>

      <div className="mt-auto pt-4 flex flex-wrap gap-2">
        {(r.tags || []).map((t, i) => (
          <span key={i} data-testid={`review-tag-${i}`}
            className="text-[10px] font-semibold uppercase tracking-[0.1em] px-2.5 py-1 rounded-full"
            style={{ background: `${colour}1f`, color: colour, border: `1px solid ${colour}55` }}>{t}</span>
        ))}
      </div>
    </article>
  );
}

export default function ReviewsSection({ reviews = [], style = {} as any, accent = "#10B981", limeLock = false }) {
  const track = useRef(null);
  const dir = useRef(1);
  const hover = useRef(false);
  const target = useRef<number | null>(null);
  const colour = style.accent || (limeLock ? "#BEF264" : accent) || "#10B981";
  const cardBg = style.card_bg || "color-mix(in srgb, var(--tfg, #ffffff) 5%, transparent)";

  useEffect(() => {
    const el = track.current;
    if (!el || !reviews.length) return;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    el.style.scrollBehavior = "auto";      // one engine only — CSS smooth scrolling would fight it
    let raf = 0, last = 0;
    const step = (now) => {
      if (!last) last = now;
      const dt = Math.min(40, now - last); last = now;
      const max = el.scrollWidth - el.clientWidth;
      if (target.current !== null) {
        // arrow click: ease to the target, then hand back to the drift
        const gap = target.current - el.scrollLeft;
        const move = Math.sign(gap) * Math.min(Math.abs(gap), Math.max(2.4, Math.abs(gap) * 0.12));
        el.scrollLeft = Math.max(0, Math.min(max, el.scrollLeft + move));
        el.dataset.autoscroll = "steering";
        if (Math.abs(gap) < 2.5 || el.scrollLeft <= 0 || el.scrollLeft >= max) target.current = null;
      } else if (!hover.current && !document.hidden) {
        let next = el.scrollLeft + dir.current * dt * 0.028;   // slow, comfortable drift
        if (next >= max) { next = max; dir.current = -1; }
        if (next <= 0) { next = 0; dir.current = 1; }
        el.scrollLeft = next;
        el.dataset.autoscroll = "on";
      } else {
        el.dataset.autoscroll = "paused";
      }
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [reviews.length]);

  const nudge = (d) => {
    const el = track.current;
    if (!el) return;
    dir.current = d;                                  // manual click steers, then auto-scroll resumes
    target.current = Math.max(0, Math.min(el.scrollWidth - el.clientWidth, el.scrollLeft + d * 372));
  };

  if (!reviews.length) return null;

  return (
    <section className="px-6 sm:px-10 py-14 border-t" data-testid="reviews-section"
      style={{ background: "var(--tbg)", color: "var(--tbody)", borderColor: `${colour}33` }}>
      {/* Title and subtitle are fixed — only the track below moves. */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight"
            data-testid="reviews-title" style={{ color: style.title_color || undefined, fontFamily: "var(--tfh)" }}>
            {style.title || "Reviews & testimonials"}
          </h2>
          <p className="text-sm md:text-base opacity-70 mt-1.5" data-testid="reviews-subtitle"
            style={{ color: style.title_color || undefined }}>
            {style.subtitle || "Real results, in our clients' own words."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs opacity-60 mr-1" data-testid="reviews-count">{reviews.length} five-star reviews</span>
          <button data-testid="reviews-prev" aria-label="Previous reviews" onClick={() => nudge(-1)}
            className="w-9 h-9 rounded-full grid place-items-center transition-transform hover:-translate-x-0.5"
            style={{ border: `1px solid ${colour}66`, color: colour }}>‹</button>
          <button data-testid="reviews-next" aria-label="Next reviews" onClick={() => nudge(1)}
            className="w-9 h-9 rounded-full grid place-items-center transition-transform hover:translate-x-0.5"
            style={{ border: `1px solid ${colour}66`, color: colour }}>›</button>
        </div>
      </div>

      <div ref={track} data-testid="reviews-track"
        onMouseEnter={() => { hover.current = true; }} onMouseLeave={() => { hover.current = false; }}
        className="mt-7 flex gap-4 overflow-x-auto pb-3 tenant-scroll"
        style={{ scrollbarWidth: "none" }}>
        {reviews.map((r, i) => <Card key={r.id || i} r={r} index={i} colour={colour} cardBg={cardBg} />)}
      </div>
    </section>
  );
}
