// Two infinite ribbons scrolling in opposite directions at ~40px/s. Pause on hover.
const DOT = () => <span className="mx-5 inline-block w-1.5 h-1.5 rounded-full bg-[var(--ed-lime)] align-middle" />;

function Row({ items, reverse = false, testid }) {
  // Duration = content width / 40px per second. Approximated from character count for a stable loop.
  const chars = items.join("").length + items.length * 8;
  const seconds = Math.max(18, Math.round((chars * 11) / 40));
  const line = [...items, ...items];
  return (
    <div className="ed-ribbon group overflow-hidden py-4" data-testid={testid}>
      <div className={`ed-ribbon-track flex w-max items-center whitespace-nowrap ${reverse ? "ed-ribbon-rev" : ""}`}
        style={{ animationDuration: `${seconds}s`, willChange: "transform" }}>
        {line.map((t, i) => (
          <span key={`${t}-${i}`} className="flex items-center">
            <span className="text-sm sm:text-base uppercase tracking-[0.14em] text-white/45">{t}</span>
            <DOT />
          </span>
        ))}
      </div>
    </div>
  );
}

export default function Ribbon({ top = [], bottom = [] }) {
  return (
    <section className="relative z-10 border-y border-white/[0.07] bg-white/[0.015]" data-testid="ribbon-section">
      <Row items={top} testid="ribbon-row-top" />
      <div className="h-px bg-white/[0.05]" />
      <Row items={bottom} reverse testid="ribbon-row-bottom" />
    </section>
  );
}
