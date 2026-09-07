export default function BlockPreview({ block }) {
  const p = block.props || {};
  if (block.type === "hero") {
    return (
      <section className="px-10 py-16 border-b border-[var(--line)]" style={{ textAlign: p.align || "left" }}>
        <h1 className="font-display text-4xl lg:text-5xl font-bold tracking-tighter">{p.title}</h1>
        <p className="text-[var(--mut)] mt-3 max-w-xl">{p.subtitle}</p>
        <button className="mt-6 px-6 py-3 rounded-full font-semibold text-sm text-black"
          style={{ background: p.accent || "var(--acc)" }}>{p.cta}</button>
      </section>
    );
  }
  if (block.type === "features") {
    return (
      <section className="px-10 py-14 border-b border-[var(--line)]">
        <h2 className="font-display text-2xl font-semibold tracking-tight mb-6">{p.heading}</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {(p.items || []).map((it, i) => (
            <div key={i} className="p-5 rounded-xl border border-[var(--line)] bg-[var(--bg-2)]">
              <div className="font-display text-lg">{it.title}</div>
              <div className="text-sm text-[var(--mut)] mt-1">{it.desc}</div>
            </div>
          ))}
        </div>
      </section>
    );
  }
  if (block.type === "pricing") {
    return (
      <section className="px-10 py-14 border-b border-[var(--line)]">
        <h2 className="font-display text-2xl font-semibold tracking-tight mb-6">{p.heading}</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {(p.plans || []).map((pl, i) => (
            <div key={i} className="p-5 rounded-xl border border-[var(--line)] bg-[var(--bg-2)]">
              <div className="overline">{pl.name}</div>
              <div className="font-display text-3xl font-bold mt-2">{pl.price}</div>
              <ul className="mt-3 space-y-1 text-sm text-[var(--mut)]">
                {(pl.features || []).map((f, k) => <li key={k}>• {f}</li>)}
              </ul>
            </div>
          ))}
        </div>
      </section>
    );
  }
  if (block.type === "chart") {
    const max = Math.max(1, ...(p.series || []).map(s => s.v || 0));
    return (
      <section className="px-10 py-14 border-b border-[var(--line)]">
        <h2 className="font-display text-2xl font-semibold tracking-tight mb-6">{p.heading}</h2>
        <div className="h-40 flex items-end gap-3 border-b border-[var(--line)] pb-2">
          {(p.series || []).map((s, i) => (
            <div key={i} className="flex-1 flex flex-col items-center gap-2">
              <div style={{ height: `${(s.v / max) * 100}%`, background: "var(--acc)" }}
                className="w-full rounded-t-md min-h-[6px]" />
              <div className="text-[10px] text-[var(--mut)] font-mono">{s.m}</div>
            </div>
          ))}
        </div>
      </section>
    );
  }
  if (block.type === "contact") {
    return (
      <section className="px-10 py-14 border-b border-[var(--line)]">
        <h2 className="font-display text-2xl font-semibold tracking-tight">{p.heading}</h2>
        <p className="text-[var(--mut)] mt-2">{p.subtitle}</p>
        <div className="mt-4 flex gap-2 max-w-md">
          <input placeholder="you@company.com" className="flex-1 bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm outline-none" />
          <button className="px-4 py-2 rounded-lg bg-[var(--acc)] text-black font-semibold text-sm">Send</button>
        </div>
        <div className="text-xs text-[var(--mut)] mt-3 font-mono">{p.email}</div>
      </section>
    );
  }
  return <div className="p-6 text-sm text-[var(--mut)]">Unknown block: {block.type}</div>;
}
