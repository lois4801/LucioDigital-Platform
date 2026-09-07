import { useRef, useState } from "react";
import * as Icons from "lucide-react";

// Inline-editable text. `path` is dotted path into block.props
function T({ as: Tag = "span", value, path, onEdit, className, style }) {
  const ref = useRef();
  const editable = !!onEdit;
  return (
    <Tag ref={ref} className={`${className || ""} ${editable ? "outline-none hover:ring-1 hover:ring-[var(--tp)]/40 focus:ring-2 focus:ring-[var(--tp)] rounded-sm cursor-text" : ""}`} style={style}
      contentEditable={editable} suppressContentEditableWarning
      data-testid={editable ? `inline-edit-${path}` : undefined}
      onBlur={editable ? () => { const v = ref.current.innerText; if (v !== value) onEdit(path, v); } : undefined}
      onKeyDown={editable ? (e) => { if (e.key === "Enter" && Tag !== "p") { e.preventDefault(); ref.current.blur(); } } : undefined}
      onClick={editable ? (e) => e.stopPropagation() : undefined}>
      {value}
    </Tag>
  );
}

const PAD = { sm: "py-10", md: "py-16", lg: "py-24" };
function sectionCls(style) {
  const bg = style?.bg === "muted" ? "bg-[var(--tsf)] tsec-muted" : style?.bg === "accent" ? "bg-[var(--tp)] text-white tsec-accent" : style?.bg === "dark" ? "bg-[#0F172A] text-white" : "";
  return `relative ${PAD[style?.padding] || PAD.md} ${bg} ${style?.align === "center" ? "text-center" : ""} px-8 lg:px-12`;
}
const mut = (style) => (style?.bg === "accent" || style?.bg === "dark") ? "text-white/80" : "text-[var(--tmut)]";
const card = "tglass rounded-[var(--tr)] border border-[var(--tbd)] p-6 transition-[transform,box-shadow,border-color] duration-300 hover:-translate-y-1";
const Btn = ({ children, ghost }) => <span className={`inline-block px-6 py-3 rounded-full font-semibold text-sm transition-transform hover:-translate-y-0.5 ${ghost ? "border border-[var(--tbd)] tglass" : "bg-[var(--tp)] text-white shadow-[0_10px_30px_-12px_var(--tp)]"}`}>{children}</span>;
const H2 = (props) => <T as="h2" {...props} className={`font-[var(--tfh)] text-3xl lg:text-4xl font-bold tracking-tight ${props.className || ""}`} />;
const Icon = ({ name, size = 18 }) => { const I = Icons[name] || Icons.Sparkles; return <I size={size} />; };
const Kicker = ({ children }) => <div className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--tp)] mb-3">{children}</div>;
const isYouTube = (u = "") => /youtube\.com|youtu\.be/.test(u);

export default function BlockPreview({ block, onEdit, onNavigate, onLead, collections = [] }) {
  const p = block.props || {}, s = block.style || {};
  const cls = sectionCls(s), m = mut(s);
  const E = (path, extra = {}) => ({ path, onEdit, ...extra });
  const [lead, setLead] = useState({ name: "", email: "", message: "", sent: false });
  const [openItem, setOpenItem] = useState(null);
  async function submitLead(e) { e.preventDefault(); if (!onLead) return; try { await onLead(lead); setLead({ name: "", email: "", message: "", sent: true }); } catch { } }

  if (block.type === "collection_list") {
    const col = collections.find(c => c.slug === p.collection) || collections[0];
    const items = (col?.items || []).filter(i => i.published !== false).slice(0, Number(p.limit) || 6);
    if (openItem) return (
      <section className={`${cls} text-left`} data-testid="collection-detail-view"><div className="max-w-3xl mx-auto">
        <button onClick={() => setOpenItem(null)} className="text-sm text-[var(--tp)] font-semibold">← Back to {col?.name}</button>
        <div className="text-xs font-bold uppercase tracking-[0.12em] text-[var(--ts)] mt-6">{col?.name}</div>
        <h1 className="font-[var(--tfh)] text-4xl lg:text-5xl font-extrabold tracking-tight mt-3">{openItem.title}</h1>
        <div className={`text-sm mt-3 ${m}`}>{openItem.date}{openItem.tags?.length ? " · " + openItem.tags.join(", ") : ""}</div>
        {openItem.cover && <img src={openItem.cover} alt="" className="w-full aspect-video object-cover rounded-[var(--tr)] mt-8" />}
        <p className={`text-xl mt-8 ${m}`}>{openItem.excerpt}</p>
        {(openItem.body || "").split("\n").filter(Boolean).map((x, i) => <p key={i} className="text-lg leading-relaxed mt-5">{x}</p>)}
      </div></section>
    );
    return (
      <section className={cls}><H2 value={p.heading} {...E("heading")} />
        <div className="grid md:grid-cols-3 gap-5 mt-8 text-left">
          {items.map(it => <button key={it.item_id} data-testid="collection-item-card" onClick={(e) => { e.stopPropagation(); setOpenItem(it); }} className={`${card} text-left hover:-translate-y-1 transition-transform`}>
            {it.cover && <img src={it.cover} alt="" className="w-full aspect-video object-cover rounded-xl mb-4" />}
            <div className={`text-xs ${m}`}>{it.date}</div><div className="font-[var(--tfh)] text-lg font-bold mt-1">{it.title}</div><p className="text-sm text-[var(--tmut)] mt-2">{it.excerpt}</p></button>)}
          {items.length === 0 && <div className={`text-sm ${m}`}>No published items in “{col?.name || p.collection}” yet — add some in the CMS tab.</div>}
        </div>
      </section>
    );
  }

  if (block.type === "navbar") return (
    <nav className="px-8 lg:px-12 py-5 flex items-center justify-between border-b border-[var(--tbd)]">
      <T value={p.brand} {...E("brand")} className="font-[var(--tfh)] font-extrabold text-xl" />
      <div className="hidden md:flex gap-6 text-sm font-medium text-[var(--tmut)]">
        {(p.links || []).map((l, i) => <button key={i} onClick={(e) => { e.stopPropagation(); onNavigate?.(l.href); }} className="hover:text-[var(--tfg)]">{l.label}</button>)}
      </div>
      <Btn>{p.cta || "Get started"}</Btn>
    </nav>
  );
  if (block.type === "hero") {
    const centered = p.variant === "centered" || s.align === "center";
    const split = p.variant === "split" && p.image;
    const cover = p.variant === "cover" && p.image;
    const inner = (
      <div className={centered ? "mx-auto max-w-3xl" : "max-w-2xl"}>
        {p.badge && <T value={p.badge} {...E("badge")} className="inline-block text-xs font-bold uppercase tracking-[0.12em] text-[var(--ts)] bg-[var(--ts)]/10 border border-[var(--ts)]/30 px-3 py-1.5 rounded-full mb-6" />}
        <T as="h1" value={p.title} {...E("title")} className="block font-[var(--tfh)] text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.05]" />
        <T as="p" value={p.subtitle} {...E("subtitle")} className={`block mt-6 text-lg lg:text-xl ${cover ? "text-white/80" : m}`} />
        <div className="mt-8 flex flex-wrap gap-3" style={{ justifyContent: centered ? "center" : "flex-start" }}>
          <Btn><T value={p.cta || "Get started"} {...E("cta")} /></Btn>
          {p.cta2 && <Btn ghost><T value={p.cta2} {...E("cta2")} /></Btn>}
        </div>
      </div>
    );
    if (cover) return (
      <section data-testid="hero-cover" className={`relative overflow-hidden px-8 lg:px-12 py-28 lg:py-36 text-white ${centered ? "text-center" : ""}`}>
        <img src={p.image} alt="" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0" style={{ background: "linear-gradient(105deg, var(--tbg) 0%, color-mix(in srgb, var(--tbg) 82%, transparent) 45%, color-mix(in srgb, var(--tbg) 30%, transparent) 100%)" }} />
        <div className="absolute inset-0" style={{ background: "linear-gradient(180deg, transparent 40%, var(--tbg) 100%)" }} />
        <div className="absolute -top-32 -right-24 w-[520px] h-[520px] rounded-full blur-3xl opacity-30 pointer-events-none" style={{ background: "var(--tp)" }} />
        <div className="relative">{inner}</div>
      </section>
    );
    return (
      <section className={`${sectionCls({ ...s, padding: s.padding || "lg" })} ${centered ? "text-center" : ""}`}>
        {split ? <div className="grid lg:grid-cols-2 gap-10 items-center">{inner}<img src={p.image} alt="" className="w-full aspect-[4/3] object-cover rounded-[var(--tr)] border border-[var(--tbd)] shadow-[0_30px_80px_-40px_var(--tp)]" /></div> : inner}
      </section>
    );
  }
  if (block.type === "stats") return (
    <section className={cls} data-testid="block-stats"><Kicker>{p.heading}</Kicker>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-6">{(p.items || []).map((it, i) => <div key={i} className={`${card} text-left`}><div className="font-[var(--tfh)] text-3xl lg:text-4xl font-extrabold text-[var(--tp)]"><T value={it.value} {...E(`items.${i}.value`)} /></div><div className="text-sm text-[var(--tmut)] mt-2"><T value={it.label} {...E(`items.${i}.label`)} /></div></div>)}</div>
    </section>
  );
  if (block.type === "team") return (
    <section className={cls} data-testid="block-team"><H2 value={p.heading} {...E("heading")} />
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5 mt-10 text-left">{(p.members || []).map((mb, i) => <div key={i} className={`${card} !p-4`}>{mb.photo && <img src={mb.photo} alt="" className="w-full aspect-square object-cover rounded-[calc(var(--tr)-6px)] mb-4" />}<div className="font-[var(--tfh)] font-bold"><T value={mb.name} {...E(`members.${i}.name`)} /></div><div className="text-xs text-[var(--tp)] mt-1 font-semibold uppercase tracking-wider"><T value={mb.role} {...E(`members.${i}.role`)} /></div></div>)}</div>
    </section>
  );
  if (block.type === "logos") return (
    <section className={`${cls} text-center`}>
      <T as="p" value={p.heading} {...E("heading")} className={`block text-xs uppercase tracking-[0.15em] font-semibold ${m}`} />
      <div className="mt-6 flex flex-wrap justify-center gap-10 text-xl font-bold text-[var(--tmut)]/70 font-[var(--tfh)]">{(p.names || []).map((n, i) => <span key={i}>{n}</span>)}</div>
    </section>
  );
  if (block.type === "features") return (
    <section className={cls}>
      <H2 value={p.heading} {...E("heading")} />
      {p.subheading !== undefined && <T as="p" value={p.subheading} {...E("subheading")} className={`block mt-3 text-lg max-w-xl ${m} ${s.align === "center" ? "mx-auto" : ""}`} />}
      <div className="grid md:grid-cols-3 gap-5 mt-10 text-left">
        {(p.items || []).map((it, i) => (
          <div key={i} className={card}>
            <div className="w-11 h-11 rounded-xl bg-[var(--tp)]/15 text-[var(--tp)] flex items-center justify-center mb-4 shadow-[0_0_24px_-6px_var(--tp)]"><Icon name={it.icon} /></div>
            <T as="h3" value={it.title} {...E(`items.${i}.title`)} className="block font-[var(--tfh)] text-lg font-bold" />
            <T as="p" value={it.desc} {...E(`items.${i}.desc`)} className="block text-sm text-[var(--tmut)] mt-2" />
          </div>
        ))}
      </div>
    </section>
  );
  if (block.type === "gallery") return (
    <section className={cls}><H2 value={p.heading} {...E("heading")} />
      <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4 mt-8">{(p.images || []).map((u, i) => <img key={i} src={u} alt="" className="w-full aspect-[4/3] object-cover rounded-[var(--tr)] border border-[var(--tbd)] transition-transform duration-500 hover:scale-[1.02]" />)}</div>
    </section>
  );
  if (block.type === "video") return (
    <section className={`${cls} text-center`}><H2 value={p.heading} {...E("heading")} />
      {p.url ? (isYouTube(p.url) ? <iframe data-testid="video-youtube" src={p.url} title="video" allow="autoplay; encrypted-media; picture-in-picture" allowFullScreen className="w-full max-w-4xl mx-auto mt-8 aspect-video rounded-[var(--tr)] border border-[var(--tbd)] bg-black" /> : <video src={p.url} controls className="w-full max-w-4xl mx-auto mt-8 rounded-[var(--tr)] border border-[var(--tbd)] bg-black" />) : <div className="mt-8 aspect-video max-w-4xl mx-auto rounded-[var(--tr)] bg-[var(--tsf)] border border-dashed border-[var(--tbd)] flex items-center justify-center text-sm text-[var(--tmut)]">Add a video URL (or generate one in AI Media)</div>}
      <T as="p" value={p.caption} {...E("caption")} className={`block mt-3 text-sm ${m}`} />
    </section>
  );
  if (block.type === "testimonials") return (
    <section className={cls}><H2 value={p.heading} {...E("heading")} />
      <div className="grid md:grid-cols-3 gap-5 mt-10 text-left">
        {(p.items || []).map((it, i) => (
          <div key={i} className={card}>
            <div className="flex gap-0.5 text-[var(--tp)] mb-3">{[...Array(5)].map((_, k) => <Icons.Star key={k} size={14} fill="currentColor" />)}</div>
            <T as="p" value={`“${it.quote}”`} {...E(`items.${i}.quote`)} className="block text-base leading-relaxed" />
            <div className="mt-4"><T value={it.name} {...E(`items.${i}.name`)} className="font-semibold text-sm" /><div className="text-xs text-[var(--tmut)]"><T value={it.role} {...E(`items.${i}.role`)} /></div></div>
          </div>
        ))}
      </div>
    </section>
  );
  if (block.type === "pricing") return (
    <section className={cls}><H2 value={p.heading} {...E("heading")} className="text-center block" />
      <div className="grid md:grid-cols-3 gap-5 mt-10 text-left">
        {(p.plans || []).map((pl, i) => (
          <div key={i} className={`${card} ${pl.highlight ? "!border-[var(--tp)] shadow-[0_24px_60px_-30px_var(--tp)]" : ""}`}>
            <T value={pl.name} {...E(`plans.${i}.name`)} className="text-sm font-semibold text-[var(--tmut)]" />
            <div className="font-[var(--tfh)] text-4xl font-extrabold mt-2"><T value={pl.price} {...E(`plans.${i}.price`)} /><span className="text-sm text-[var(--tmut)] font-medium">/{pl.period || "mo"}</span></div>
            <ul className="mt-4 space-y-2 text-sm text-[var(--tmut)]">{(pl.features || []).map((f, k) => <li key={k} className="flex gap-2"><Icons.Check size={14} className="text-[var(--ts)] mt-0.5" />{f}</li>)}</ul>
            <div className="mt-6"><Btn ghost={!pl.highlight}>Choose {pl.name}</Btn></div>
          </div>
        ))}
      </div>
    </section>
  );
  if (block.type === "faq") return (
    <section className={cls}><div className="max-w-3xl mx-auto text-left"><H2 value={p.heading} {...E("heading")} />
      <div className="mt-6 divide-y divide-[var(--tbd)]">
        {(p.items || []).map((it, i) => (
          <details key={i} className="py-4 group"><summary className="font-semibold cursor-pointer list-none flex justify-between items-center"><T value={it.q} {...E(`items.${i}.q`)} /><Icons.ChevronDown size={16} className="group-open:rotate-180 transition-transform" /></summary>
            <T as="p" value={it.a} {...E(`items.${i}.a`)} className="block text-[var(--tmut)] mt-2 text-sm leading-relaxed" /></details>
        ))}
      </div></div>
    </section>
  );
  if (block.type === "chart") {
    const max = Math.max(1, ...(p.series || []).map(x => x.v || 0));
    return (
      <section className={cls}><H2 value={p.heading} {...E("heading")} />
        <div className="h-44 mt-8 flex items-end gap-3">{(p.series || []).map((x, i) => (
          <div key={i} className="flex-1 flex flex-col items-center gap-2"><div style={{ height: `${(x.v / max) * 100}%`, background: "linear-gradient(180deg,var(--tp),var(--ts))" }} className="w-full rounded-t-lg min-h-[6px]" /><div className="text-[10px] text-[var(--tmut)]">{x.m}</div></div>))}</div>
        {p.caption && <T as="p" value={p.caption} {...E("caption")} className={`block mt-4 text-sm ${m}`} />}
      </section>
    );
  }
  if (block.type === "cta") return (
    <section className={`${sectionCls({ ...s, bg: s.bg || "accent" })} text-center`}>
      <T as="h2" value={p.title} {...E("title")} className="block font-[var(--tfh)] text-3xl lg:text-5xl font-extrabold tracking-tight" />
      <T as="p" value={p.subtitle} {...E("subtitle")} className="block mt-4 text-lg text-white/80" />
      <div className="mt-8"><span className="inline-block px-7 py-3.5 rounded-full font-semibold bg-white text-[var(--tp)]"><T value={p.cta || "Get started"} {...E("cta")} /></span></div>
    </section>
  );
  if (block.type === "contact") return (
    <section className={cls}><div className="grid lg:grid-cols-2 gap-10 text-left">
      <div><H2 value={p.heading} {...E("heading")} /><T as="p" value={p.subtitle} {...E("subtitle")} className={`block mt-3 ${m}`} />
        <div className="mt-6 space-y-1 text-sm"><div><T value={p.email} {...E("email")} /></div>{p.phone !== undefined && <div><T value={p.phone} {...E("phone")} /></div>}{p.address !== undefined && <div className="text-[var(--tmut)]"><T value={p.address} {...E("address")} /></div>}</div></div>
      <form onSubmit={submitLead} className={`${card} space-y-3`} data-testid="contact-form">
        {lead.sent ? <div className="text-center py-8 text-[var(--ts)] font-semibold" data-testid="contact-form-sent">Thanks — we'll be in touch shortly.</div> : <>
          <input data-testid="contact-name-input" required value={lead.name} onChange={e => setLead({ ...lead, name: e.target.value })} placeholder="Name" className="w-full border border-[var(--tbd)] rounded-xl px-4 py-3 text-sm bg-[var(--tbg)] outline-none" />
          <input data-testid="contact-email-input" required type="email" value={lead.email} onChange={e => setLead({ ...lead, email: e.target.value })} placeholder="Email" className="w-full border border-[var(--tbd)] rounded-xl px-4 py-3 text-sm bg-[var(--tbg)] outline-none" />
          <textarea data-testid="contact-message-input" required value={lead.message} onChange={e => setLead({ ...lead, message: e.target.value })} placeholder="Message" rows={4} className="w-full border border-[var(--tbd)] rounded-xl px-4 py-3 text-sm bg-[var(--tbg)] outline-none" />
          <button type="submit" data-testid="contact-submit-btn" disabled={!onLead} className="inline-block px-6 py-3 rounded-full font-semibold text-sm bg-[var(--tp)] text-white disabled:opacity-70">Send message</button></>}
      </form>
    </div></section>
  );
  if (block.type === "footer") return (
    <footer className="px-8 lg:px-12 py-14 border-t border-[var(--tbd)] grid md:grid-cols-4 gap-8 text-left">
      <div><T value={p.brand} {...E("brand")} className="font-[var(--tfh)] font-extrabold text-lg" /><T as="p" value={p.tagline} {...E("tagline")} className="block text-sm text-[var(--tmut)] mt-2" /></div>
      {(p.columns || []).map((c, i) => <div key={i}><T value={c.title} {...E(`columns.${i}.title`)} className="text-sm font-semibold" /><ul className="mt-3 space-y-2 text-sm text-[var(--tmut)]">{(c.links || []).map((l, k) => <li key={k}>{l}</li>)}</ul></div>)}
    </footer>
  );
  return <div className="p-6 text-sm text-[var(--tmut)]">Unknown block: {block.type}</div>;
}
