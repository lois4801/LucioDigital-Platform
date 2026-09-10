import { useState } from "react";

/** Marquee text ribbon: oversized outline text looping seamlessly and slowing to 30% on hover.
 *  The band follows the template's own light/dark mode so it never breaks a light design. */
export default function MarqueeRibbon({ text = "", accent = "#10B981", speed = 1, strokeOpacity = 0.3, fontSize = 1, mode = "dark", testid = "marquee-ribbon" }) {
  const [slow, setSlow] = useState(false);
  const phrase = (text || "").trim();
  if (!phrase) return null;
  const light = mode === "light";
  // one copy is 50% of the track, so translating by -50% lands exactly on the next copy: no seam
  const base = 34;                                    // seconds for a full loop at 1x
  const dur = (base / Math.max(0.2, speed)) * (slow ? 1 / 0.3 : 1);
  const tiles = Array.from({ length: 8 }, () => `${phrase}\u00A0\u00A0·\u00A0\u00A0`);

  return (
    <section data-testid={testid} data-marquee-slow={slow ? "1" : "0"} data-marquee-mode={light ? "light" : "dark"}
      onMouseEnter={() => setSlow(true)} onMouseLeave={() => setSlow(false)}
      className="relative overflow-hidden select-none"
      style={{
        background: light ? "#F6F6F3" : "#080808",
        borderTop: `1px solid ${accent}${light ? "44" : "33"}`,
        borderBottom: `1px solid ${accent}${light ? "44" : "33"}`,
      }}>
      <div className="flex whitespace-nowrap will-change-transform marquee-track"
        data-testid={`${testid}-track`}
        style={{ animationDuration: `${dur}s`, width: "max-content" }}>
        {[0, 1].map(copy => (
          <div key={copy} className="flex whitespace-nowrap" aria-hidden={copy === 1}>
            {tiles.map((t, i) => (
              <span key={i} className="font-display font-black tracking-tight leading-none py-4"
                style={{
                  fontSize: `${5.5 * fontSize}rem`,
                  color: "transparent",
                  WebkitTextStroke: `${light ? 1.6 : 1.2}px ${accent}`,
                  opacity: light ? Math.min(1, strokeOpacity * 1.5) : strokeOpacity,
                }}>{t}</span>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

/** Where the two ribbons go in a page: after the hero, and before the closing CTA. */
export function ribbonPlan(blocks: any[] = []) {
  const type = (b: any) => (b?.type || "").toLowerCase();
  const rows = blocks.map(type);
  const top = rows.findIndex(t => t.includes("hero"));
  let bottom = rows.findIndex(t => t.includes("cta"));
  if (bottom < 0) {
    const foot = rows.findIndex(t => t.includes("footer") || t.includes("contact"));
    bottom = foot;
  }
  return { top, bottom: bottom > top ? bottom : -1 };
}
