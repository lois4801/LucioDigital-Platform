import { useState, useEffect, createContext, useContext } from "react";
import ReviewsSection from "@/components/editorial/ReviewsSection";
import * as Icons from "lucide-react";
import { SwapOverlay } from "@/components/builder/ImageSwap";
import { EditableText } from "@/components/InlineTextTools";

// design_v2 flag for the current tenant site — set by the canvas / public preview root.
export const DesignCtx = createContext(false);
import { useCta } from "@/components/CtaFormModal";

export const useV2 = () => useContext(DesignCtx);

const styleKey = (path) => `_styles.${String(path).replace(/\./g, "__")}`;

// Inline-editable text. `path` is dotted path into block.props
function T({ as: Tag = "span", value, path, onEdit, className, style, styles }) {
  const editable = !!onEdit;
  const st = styles?.[String(path).replace(/\./g, "__")] || {};
  const safe = value && typeof value === "object" ? (value.label ?? value.text ?? value.title ?? "") : value;
  return (
    <EditableText
      as={Tag}
      value={safe}
      className={className}
      style={style}
      editable={editable}
      font={st.font}
      color={st.color}
      singleLine={Tag !== "p"}
      testid={editable ? `inline-edit-${path}` : undefined}
      onCommit={(v) => onEdit(path, v)}
      onStyleChange={(s) => onEdit(styleKey(path), { font: s.font || "", color: s.color || "" })}
    />
  );
}

const PAD = { sm: "py-10", md: "py-16", lg: "py-24" };
const V2PAD = { sm: "tsec-sm", md: "tsec", lg: "tsec-lg" };
function sectionCls(style, v2) {
  const bg = style?.bg === "muted" ? "bg-[var(--tsf)] tsec-muted" : style?.bg === "accent" ? "bg-[var(--tp)] text-white tsec-accent" : style?.bg === "dark" ? "bg-[#0F172A] text-white" : "";
  const pad = v2 ? V2PAD[style?.padding] || V2PAD.md : PAD[style?.padding] || PAD.md;
  const preset = ["editorial", "bold", "minimal", "luxe"].includes(style?.preset) ? `pr-${style.preset}` : "";
  return `relative ${pad} ${bg} ${preset} ${style?.align === "center" ? "text-center" : ""} px-6 sm:px-8 lg:px-12 ${v2 ? "[&>*]:mx-auto [&>*]:max-w-[1240px]" : ""}`;
}
const mut = (style) => (style?.bg === "accent" || style?.bg === "dark") ? "text-white/80" : "text-[var(--tmut)]";
const cardCls = (v2) => v2
  ? "tcard rounded-[var(--tr)] border border-[var(--tbd)] p-6"
  : "tglass rounded-[var(--tr)] border border-[var(--tbd)] p-6 transition-[transform,box-shadow,border-color] duration-300 hover:-translate-y-1";
const CtaBandBtn = ({ label, v2, children }) => {
  const cta = useCta();
  const form = cta?.formFor?.(label);
  const cls = `inline-block px-7 py-3.5 rounded-full font-semibold bg-white text-[var(--tp)] ${v2 ? "tbtn" : ""}`;
  if (form && cta?.onCta) return <button type="button" data-testid={`cta-btn-${form.key}`} onClick={(e) => { e.stopPropagation(); cta.onCta(form); }} className={`${cls} cursor-pointer`}>{children}</button>;
  return <span className={cls}>{children}</span>;
};

const Btn = ({ children, ghost }) => {
  const v2 = useV2();
  const cta = useCta();
  const label = typeof children === "object" ? (children?.props?.value || "") : String(children || "");
  const form = cta?.formFor?.(label);
  const cls = `inline-block px-6 py-3 rounded-full font-semibold text-sm ${v2 ? `tbtn ${ghost ? "tbtn-ghost" : "tbtn-solid"}` : "transition-transform hover:-translate-y-0.5"} ${ghost ? "tbtn-ghost border-2 border-[var(--thead)] text-[var(--thead)] bg-transparent" : "bg-[var(--tp)] text-white shadow-[0_10px_30px_-12px_var(--tp)]"}`;
  if (form && cta?.onCta) {
    return <button type="button" data-testid={`cta-btn-${form.key}`} onClick={(e) => { e.stopPropagation(); e.preventDefault(); cta.onCta(form); }}
      className={`${cls} cursor-pointer text-left`}>{children}{cta.editMode && <span className="ml-2 text-[10px] uppercase tracking-wider opacity-70">Edit form</span>}</button>;
  }
  return <span className={cls}>{children}</span>;
};
function BookingPicker({ token, mode = "period", value, onChange, inputCls }) {
  const [slots, setSlots] = useState(mode === "period" ? ["Morning", "Afternoon", "Evening"] : []);
  const today = new Date().toISOString().slice(0, 10);
  useEffect(() => {
    if (!token || !value.__date) return;
    fetch(`${process.env.REACT_APP_BACKEND_URL}/api/site/${token}/slots?date=${value.__date}`)
      .then(r => r.json()).then(d => setSlots(d.slots || [])).catch(() => { });
  }, [token, value.__date]);
  return (
    <div data-testid="booking-picker" className="grid sm:grid-cols-2 gap-4">
      <label className="block"><span className="block text-xs font-semibold mb-1.5">Preferred date <span className="text-[var(--tp)]">*</span></span>
        <input data-testid="booking-date" type="date" required min={today} value={value.__date || ""} onChange={e => onChange({ __date: e.target.value, __slot: "" })} className={inputCls} /></label>
      <label className="block"><span className="block text-xs font-semibold mb-1.5">{mode === "period" ? "Time of day" : "Time"}</span>
        <select data-testid="booking-slot" value={value.__slot || ""} onChange={e => onChange({ __slot: e.target.value })} className={inputCls}>
          <option value="">{slots.length ? "Select…" : "Pick a date first"}</option>
          {slots.map(s => <option key={s} value={s}>{s}</option>)}
        </select></label>
    </div>
  );
}

const H2 = (props) => {  const v2 = useV2();
  return <T as="h2" {...props} className={`font-[var(--tfh)] ${v2 ? "t-h2" : "text-3xl lg:text-4xl"} font-bold tracking-tight ${props.className || ""}`} />;
};
const Icon = ({ name, size = 18 }) => { const I = Icons[name] || Icons.Sparkles; return <I size={size} />; };
const Kicker = ({ children }) => <div className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--tp)] mb-3">{children}</div>;
const isYouTube = (u = "") => /youtube\.com|youtu\.be/.test(u);
const absUrl = (u = "") => u.startsWith("/api/") ? `${process.env.REACT_APP_BACKEND_URL}${u}` : u;

export default function BlockPreview({ block, onEdit, onNavigate, onLead, onImage, collections = [], bookingMode = "period", siteToken = null, reviews = null }) {
  const v2 = useV2();
  const p = block.props || {}, s = block.style || {};
  // Database-driven sections: after "Convert to Web App" the items live in a collection.
  const dyn = (key) => {
    if (!p.dynamic || !p.collection) return p[key];
    const col = collections.find(c => c.slug === p.collection);
    const items = (col?.items || []).filter(i => i.published !== false);
    if (!items.length) return p[key];
    if (key === "images") return items.map(i => i.fields?.image || i.cover).filter(Boolean);
    return items.map(i => ({ ...(i.fields || {}), title: i.title, name: i.fields?.name || i.title, desc: i.excerpt, quote: i.fields?.quote || i.excerpt, photo: i.cover || i.fields?.photo, image: i.cover || i.fields?.image }));
  };
  const cls = sectionCls(s, v2), m = mut(s);
  const card = cardCls(v2);
  const stag = v2 ? "tstagger" : "";
  const E = (path, extra = {}) => ({ path, onEdit, styles: p._styles, ...extra });
  const Swap = ({ path, current }) => onImage ? <SwapOverlay testid={`image-swap-${path}`} onSwap={() => onImage(path, current)} /> : null;
  const [lead, setLead] = useState({ name: "", email: "", message: "", sent: false });
  const [form, setForm] = useState({});
  const [sent, setSent] = useState(false);
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
        {openItem.cover && <img src={openItem.cover} alt="" loading="lazy" decoding="async" className="w-full aspect-video object-cover rounded-[var(--tr)] mt-8" />}
        <p className={`text-xl mt-8 ${m}`}>{openItem.excerpt}</p>
        {(openItem.body || "").split("\n").filter(Boolean).map((x, i) => <p key={`${x.slice(0, 24)}-${i}`} className="text-lg leading-relaxed mt-5">{x}</p>)}
      </div></section>
    );
    return (
      <section className={cls}><H2 value={p.heading} {...E("heading")} />
        <div className={`grid md:grid-cols-3 gap-5 mt-8 text-left ${stag}`}>
          {items.map(it => <button key={it.item_id} data-testid="collection-item-card" onClick={(e) => { e.stopPropagation(); setOpenItem(it); }} className={`${card} text-left`}>
            {it.cover && <img src={it.cover} alt="" loading="lazy" decoding="async" className="w-full aspect-video object-cover rounded-xl mb-4" />}
            <div className={`text-xs ${m}`}>{it.date}</div><div className="font-[var(--tfh)] text-lg font-bold mt-1">{it.title}</div><p className="text-sm text-[var(--tmut)] mt-2">{it.excerpt}</p></button>)}
          {items.length === 0 && <div className={`text-sm ${m}`}>No published items in “{col?.name || p.collection}” yet — add some in the CMS tab.</div>}
        </div>
      </section>
    );
  }

  if (block.type === "navbar") return (
    <nav className={`px-6 sm:px-8 lg:px-12 py-5 flex items-center justify-between border-b border-[var(--tbd)] ${v2 ? "tglassnav" : ""}`}>
      <T value={p.brand} {...E("brand")} className="font-[var(--tfh)] font-extrabold text-xl flex items-center gap-2" />
      {p.logo && <img data-testid="navbar-logo" src={absUrl(p.logo)} alt="" className="h-8 w-auto object-contain order-first" />}
      <div className="hidden md:flex gap-6 text-sm font-medium text-[var(--tmut)]">
        {(p.links || []).map((l, i) => (
          <span key={`${(typeof l === "string" ? l : l?.label) || "nav"}-${i}`} className="relative group">
            <button data-testid={`nav-link-${i}`} onClick={(e) => { e.stopPropagation(); if (!onEdit) onNavigate?.(l.href); }} className={`hover:text-[var(--tfg)] flex items-center gap-1 ${v2 ? "tlink" : ""}`}>
              <T value={l.label} {...E(`links.${i}.label`)} />
              {l.children?.length > 0 && <Icons.ChevronDown size={12} />}
            </button>
            {l.children?.length > 0 && (
              <span data-testid={`nav-dropdown-${i}`} className="absolute left-0 top-full pt-3 hidden group-hover:block z-30">
                <span className="block min-w-[190px] rounded-xl border border-[var(--tbd)] bg-[var(--tsf)] shadow-xl p-2">
                  {l.children.map((c, k) => (
                    <button key={k} data-testid={`nav-dropdown-item-${i}-${k}`} onClick={(e) => { e.stopPropagation(); if (!onEdit) onNavigate?.(c.href); }} className="block w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-[var(--tp)]/10 hover:text-[var(--tfg)]">
                      <T value={c.label} {...E(`links.${i}.children.${k}.label`)} />
                    </button>
                  ))}
                </span>
              </span>
            )}
          </span>
        ))}
      </div>
      <Btn><T value={p.cta || "Get started"} {...E("cta")} /></Btn>
    </nav>
  );
  if (block.type === "hero") {
    const centered = p.variant === "centered" || s.align === "center";
    const split = p.variant === "split" && p.image;
    const cover = p.variant === "cover" && p.image;
    const inner = (
      <div className={centered ? "mx-auto max-w-3xl" : "max-w-2xl"}>
        {p.badge && <T value={p.badge} {...E("badge")} className="inline-block text-xs font-bold uppercase tracking-[0.12em] text-[var(--ts)] bg-[var(--ts)]/10 border border-[var(--ts)]/30 px-3 py-1.5 rounded-full mb-6" />}
        <T as="h1" value={p.title} {...E("title")} className={`block font-[var(--tfh)] ${v2 ? "t-h1" : "text-4xl sm:text-5xl lg:text-6xl"} font-extrabold tracking-tight leading-[1.05]`} />
        <T as="p" value={p.subtitle} {...E("subtitle")} className={`block mt-6 ${v2 ? "t-lead" : "text-lg lg:text-xl"} ${cover ? "text-[var(--tbody)]" : m}`} />
        <div className="mt-8 flex flex-wrap gap-3" style={{ justifyContent: centered ? "center" : "flex-start" }}>
          <Btn><T value={p.cta || "Get started"} {...E("cta")} /></Btn>
          {String(p.cta2 || "").trim() && <Btn ghost><T value={p.cta2} {...E("cta2")} /></Btn>}
        </div>
      </div>
    );
    if (cover) return (
      <section data-testid="hero-cover" className={`relative overflow-hidden px-6 sm:px-8 lg:px-12 ${v2 ? "thero py-24" : "py-28 lg:py-36"} text-[var(--thead)] ${centered ? "text-center" : ""}`}>
        <img src={p.image} alt="" decoding="async" fetchPriority="high" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0 hero-scrim" />
        <div className="absolute inset-0 hero-scrim-b" />
        <div className="absolute -top-32 -right-24 w-[520px] h-[520px] rounded-full blur-3xl opacity-30 pointer-events-none" style={{ background: "var(--tp)" }} />
        <div className="relative w-full">{inner}</div>
        {onImage && <div className="absolute top-4 right-4 z-20"><button type="button" data-testid="image-swap-image" onClick={(e) => { e.stopPropagation(); onImage("image", p.image); }} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold text-white border border-white/30 bg-black/60 backdrop-blur hover:bg-black/80"><Icons.ImagePlus size={12} /> Replace background</button></div>}
      </section>
    );
    return (
      <section data-testid={centered && p.image ? "hero-centered" : undefined}
        className={`relative overflow-hidden ${sectionCls({ ...s, padding: s.padding || "lg" }, v2)} ${v2 && centered ? "thero" : ""} ${centered ? "text-center" : ""}`}>
        {/* Centred heroes keep their photograph as the backdrop so no template loses its imagery. */}
        {!split && p.image && (
          <>
            <img src={p.image} alt="" decoding="async" className="absolute inset-0 w-full h-full object-cover" />
            <div className="absolute inset-0 hero-scrim-c" />
            <Swap path="image" current={p.image} />
          </>
        )}
        {split
          ? <div className="grid lg:grid-cols-2 gap-10 items-center">{inner}<div className="relative"><img src={p.image} alt="" loading="lazy" decoding="async" className="w-full aspect-[4/3] object-cover rounded-[var(--tr)] border border-[var(--tbd)] shadow-[0_30px_80px_-40px_var(--tp)]" /><Swap path="image" current={p.image} /></div></div>
          : <div className="relative">{inner}</div>}
      </section>
    );
  }
  if (block.type === "stats") return (
    <section className={cls} data-testid="block-stats"><Kicker><T value={p.heading} {...E("heading")} /></Kicker>
      <div className={`grid grid-cols-2 lg:grid-cols-4 gap-4 mt-6 ${stag}`}>{(p.items || []).map((it, i) => <div key={`${it.label || it.value || "it"}-${i}`} className={`${card} text-left`}><div className="font-[var(--tfh)] text-3xl lg:text-4xl font-extrabold text-[var(--tp)]"><T value={it.value} {...E(`items.${i}.value`)} /></div><div className="text-sm text-[var(--tmut)] mt-2"><T value={it.label} {...E(`items.${i}.label`)} /></div></div>)}</div>
    </section>
  );
  if (block.type === "team") return (
    <section className={cls} data-testid="block-team"><H2 value={p.heading} {...E("heading")} />
      <div className={`grid sm:grid-cols-2 lg:grid-cols-4 gap-5 mt-10 text-left ${stag}`}>{(dyn("members") || []).map((mb, i) => <div key={`${mb.name || "mb"}-${i}`} className={`${card} !p-4`}>{mb.photo && <div className="relative mb-4"><img src={mb.photo} alt="" loading="lazy" decoding="async" className="w-full aspect-square object-cover rounded-[calc(var(--tr)-6px)]" /><Swap path={`members.${i}.photo`} current={mb.photo} /></div>}<div className="font-[var(--tfh)] font-bold"><T value={mb.name} {...E(`members.${i}.name`)} /></div><div className="text-xs text-[var(--tp)] mt-1 font-semibold uppercase tracking-wider"><T value={mb.role} {...E(`members.${i}.role`)} /></div></div>)}</div>
    </section>
  );
  if (block.type === "logos") return (
    <section className={`${cls} text-center`}>
      <T as="p" value={p.heading} {...E("heading")} className={`block text-xs uppercase tracking-[0.15em] font-semibold ${m}`} />
      <div className="mt-6 flex flex-wrap justify-center gap-10 text-xl font-bold text-[var(--tmut)]/70 font-[var(--tfh)]">{(p.names || []).map((n, i) => <T key={`${n}-${i}`} value={n} {...E(`names.${i}`)} />)}</div>
    </section>
  );
  if (block.type === "features") return (
    <section className={cls}>
      <H2 value={p.heading} {...E("heading")} />
      {p.subheading !== undefined && <T as="p" value={p.subheading} {...E("subheading")} className={`block mt-3 text-lg max-w-xl ${m} ${s.align === "center" ? "mx-auto" : ""}`} />}
      <div className={`grid md:grid-cols-3 gap-5 mt-10 text-left ${stag}`}>
        {(dyn("items") || []).map((it, i) => (
          <div key={`${it.title || it.name || "card"}-${i}`} className={card}>
            <div className="w-11 h-11 rounded-xl bg-[var(--tp)]/15 text-[var(--tp)] flex items-center justify-center mb-4 shadow-[0_0_24px_-6px_var(--tp)]"><Icon name={it.icon} /></div>
            <T as="h3" value={it.title} {...E(`items.${i}.title`)} className={`block font-[var(--tfh)] ${v2 ? "t-h3" : "text-lg"} font-bold`} />
            <T as="p" value={it.desc} {...E(`items.${i}.desc`)} className="block text-sm text-[var(--tmut)] mt-2" />
          </div>
        ))}
      </div>
    </section>
  );
  if (block.type === "gallery") return (
    <section className={cls}><H2 value={p.heading} {...E("heading")} />
      <div className={`grid sm:grid-cols-2 md:grid-cols-3 gap-4 mt-8 ${stag}`}>{(dyn("images") || []).map((u, i) => <div key={`${u}-${i}`} className="relative overflow-hidden rounded-[var(--tr)]"><img src={u} alt="" loading="lazy" decoding="async" className="w-full aspect-[4/3] object-cover rounded-[var(--tr)] border border-[var(--tbd)] transition-transform duration-500 hover:scale-[1.02]" /><Swap path={`images.${i}`} current={u} /></div>)}</div>
    </section>
  );
  if (block.type === "video") return (
    <section className={`${cls} text-center`}><H2 value={p.heading} {...E("heading")} />
      {p.url ? (isYouTube(p.url) ? <iframe data-testid="video-youtube" src={p.url} title="video" allow="autoplay; encrypted-media; picture-in-picture" allowFullScreen className="w-full max-w-4xl mx-auto mt-8 aspect-video rounded-[var(--tr)] border border-[var(--tbd)] bg-black" /> : <video src={p.url} controls className="w-full max-w-4xl mx-auto mt-8 rounded-[var(--tr)] border border-[var(--tbd)] bg-black" />) : <div className="mt-8 aspect-video max-w-4xl mx-auto rounded-[var(--tr)] bg-[var(--tsf)] border border-dashed border-[var(--tbd)] flex items-center justify-center text-sm text-[var(--tmut)]">Add a video URL (or generate one in AI Media)</div>}
      <T as="p" value={p.caption} {...E("caption")} className={`block mt-3 text-sm ${m}`} />
    </section>
  );
  if (block.type === "testimonials") {
    // The 3-quote block is replaced in place by the full reviews section when a set exists.
    if (reviews?.reviews?.length) return (
      <ReviewsSection reviews={reviews.reviews} style={reviews.style || {}}
        accent={reviews.accent || "var(--tp)"} limeLock={reviews.limeLock} />
    );
    return (
    <section className={cls}><H2 value={p.heading} {...E("heading")} />
      <div className={`grid md:grid-cols-3 gap-5 mt-10 text-left ${stag}`}>
        {(dyn("items") || []).map((it, i) => (
          <div key={`${it.title || it.name || "card"}-${i}`} className={card}>
            <div className="flex gap-0.5 text-[var(--tp)] mb-3">{[...Array(5)].map((_, k) => <Icons.Star key={k} size={14} fill="currentColor" />)}</div>
            <T as="p" value={`“${it.quote}”`} {...E(`items.${i}.quote`)} className="block text-base leading-relaxed" />
            <div className="mt-4"><T value={it.name} {...E(`items.${i}.name`)} className="font-semibold text-sm" /><div className="text-xs text-[var(--tmut)]"><T value={it.role} {...E(`items.${i}.role`)} /></div></div>
          </div>
        ))}
      </div>
    </section>
    );
  }
  if (block.type === "pricing") return (
    <section className={cls}><H2 value={p.heading} {...E("heading")} className="text-center block" />
      <div className={`grid md:grid-cols-3 gap-5 mt-10 text-left ${stag}`}>
        {(dyn("plans") || []).map((pl, i) => (
          <div key={`${pl.name || "plan"}-${i}`} className={`${card} ${pl.highlight ? "!border-[var(--tp)] shadow-[0_24px_60px_-30px_var(--tp)]" : ""}`}>
            <T value={pl.name} {...E(`plans.${i}.name`)} className="text-sm font-semibold text-[var(--tmut)]" />
            <div className="font-[var(--tfh)] text-4xl font-extrabold mt-2"><T value={pl.price} {...E(`plans.${i}.price`)} /><span className="text-sm text-[var(--tmut)] font-medium">/{pl.period || "mo"}</span></div>
            <ul className="mt-4 space-y-2 text-sm text-[var(--tmut)]">{(pl.features || []).map((f, k) => <li key={k} className="flex gap-2"><Icons.Check size={14} className="text-[var(--ts)] mt-0.5" /><T value={f} {...E(`plans.${i}.features.${k}`)} /></li>)}</ul>
            <div className="mt-6"><Btn ghost={!pl.highlight}>Choose {pl.name}</Btn></div>
          </div>
        ))}
      </div>
    </section>
  );
  if (block.type === "faq") return (
    <section className={cls}><div className="max-w-3xl mx-auto text-left"><H2 value={p.heading} {...E("heading")} />
      <div className="mt-6 divide-y divide-[var(--tbd)]">
        {(dyn("items") || []).map((it, i) => (
          <details key={`${it.q || "faq"}-${i}`} className="py-4 group"><summary className="font-semibold cursor-pointer list-none flex justify-between items-center"><T value={it.q} {...E(`items.${i}.q`)} /><Icons.ChevronDown size={16} className="group-open:rotate-180 transition-transform" /></summary>
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
          <div key={`${x.m || "bar"}-${i}`} className="flex-1 flex flex-col items-center gap-2"><div style={{ height: `${(x.v / max) * 100}%`, background: "linear-gradient(180deg,var(--tp),var(--ts))" }} className="w-full rounded-t-lg min-h-[6px]" /><div className="text-[10px] text-[var(--tmut)]"><T value={x.m} {...E(`series.${i}.m`)} /></div></div>))}</div>
        {p.caption && <T as="p" value={p.caption} {...E("caption")} className={`block mt-4 text-sm ${m}`} />}
      </section>
    );
  }
  if (block.type === "cta") return (
    <section className={`${sectionCls({ ...s, bg: s.bg || "accent" }, v2)} text-center`}>
      <T as="h2" value={p.title} {...E("title")} className={`block font-[var(--tfh)] ${v2 ? "t-h2" : "text-3xl lg:text-5xl"} font-extrabold tracking-tight`} />
      <T as="p" value={p.subtitle} {...E("subtitle")} className={`block mt-4 ${v2 ? "t-lead" : "text-lg"} text-white/80`} />
      <div className="mt-8"><CtaBandBtn label={p.cta || "Get started"} v2={v2}><T value={p.cta || "Get started"} {...E("cta")} /></CtaBandBtn></div>
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
  if (block.type === "form") {
    const fields = p.fields || [];
    const inputCls = "w-full border border-[var(--tbd)] rounded-xl px-4 py-3 text-sm bg-[var(--tbg)] outline-none";
    async function submitForm(e) {
      e.preventDefault();
      if (!onLead) return;
      const emailF = fields.find(f => f.type === "email");
      const nameF = fields.find(f => /name/i.test(f.name) || /name/i.test(f.label));
      const lines = fields.map(f => `${f.label}: ${form[f.name] ?? ""}`).join("\n");
      try {
        await onLead({ name: (nameF && form[nameF.name]) || "Website visitor", email: (emailF && form[emailF.name]) || "", message: `${p.heading || "Form submission"}\n\n${lines}`, form_id: block.id,
                       booking_date: p.booking ? form.__date : undefined, booking_slot: p.booking ? form.__slot : undefined });
        setForm({}); setSent(true);
      } catch { }
    }
    return (
      <section className={cls} data-testid="form-block">
        <div className="max-w-2xl mx-auto text-left">
          <H2 value={p.heading} {...E("heading")} />
          {p.subtitle && <T as="p" value={p.subtitle} {...E("subtitle")} className={`block mt-3 ${m}`} />}
          <form onSubmit={submitForm} className={`${card} mt-8 space-y-4`} data-testid="custom-form">
            {sent ? <div data-testid="custom-form-sent" className="text-center py-8 text-[var(--ts)] font-semibold">{p.success_message || "Thanks — we'll be in touch shortly."}</div> : <>
              {p.booking && <BookingPicker token={siteToken} mode={bookingMode} value={form} onChange={v => setForm({ ...form, ...v })} inputCls={inputCls} />}
              {fields.map((f, i) => (
                <label key={f.name || i} className="block">
                  <span className="block text-xs font-semibold mb-1.5"><T value={f.label} {...E(`fields.${i}.label`)} />{f.required && <span className="text-[var(--tp)]"> *</span>}</span>
                  {f.type === "textarea" ? (
                    <textarea data-testid={`form-field-${f.name}`} required={!!f.required} rows={4} placeholder={f.placeholder || ""} value={form[f.name] || ""} onChange={e => setForm({ ...form, [f.name]: e.target.value })} className={inputCls} />
                  ) : f.type === "select" ? (
                    <select data-testid={`form-field-${f.name}`} required={!!f.required} value={form[f.name] || ""} onChange={e => setForm({ ...form, [f.name]: e.target.value })} className={inputCls}>
                      <option value="">{f.placeholder || "Select…"}</option>
                      {(f.options || []).map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  ) : f.type === "radio" ? (
                    <span className="flex flex-wrap gap-4 pt-1">{(f.options || []).map(o => (
                      <span key={o} className="flex items-center gap-1.5 text-sm"><input type="radio" name={f.name} value={o} checked={form[f.name] === o} onChange={() => setForm({ ...form, [f.name]: o })} className="accent-[var(--tp)]" />{o}</span>))}</span>
                  ) : f.type === "checkbox" ? (
                    <span className="flex items-center gap-2 text-sm"><input data-testid={`form-field-${f.name}`} type="checkbox" checked={!!form[f.name]} onChange={e => setForm({ ...form, [f.name]: e.target.checked ? "Yes" : "" })} className="accent-[var(--tp)]" />{f.placeholder || "Yes"}</span>
                  ) : (
                    <input data-testid={`form-field-${f.name}`} type={f.type || "text"} required={!!f.required} placeholder={f.placeholder || ""} value={form[f.name] || ""} onChange={e => setForm({ ...form, [f.name]: e.target.value })} className={inputCls} />
                  )}
                </label>
              ))}
              <button type="submit" data-testid="custom-form-submit" disabled={!onLead} className="inline-block px-6 py-3 rounded-full font-semibold text-sm bg-[var(--tp)] text-white disabled:opacity-70"><T value={p.submit_label || "Send"} {...E("submit_label")} /></button>
            </>}
          </form>
        </div>
      </section>
    );
  }
  if (block.type === "footer") return (
    <footer className="px-6 sm:px-8 lg:px-12 py-14 border-t border-[var(--tbd)] grid md:grid-cols-4 gap-8 text-left">
      <div>{p.logo && <img data-testid="footer-logo" src={absUrl(p.logo)} alt="" loading="lazy" decoding="async" className="h-8 w-auto object-contain mb-3" />}<T value={p.brand} {...E("brand")} className="font-[var(--tfh)] font-extrabold text-lg" /><T as="p" value={p.tagline} {...E("tagline")} className="block text-sm text-[var(--tmut)] mt-2" /></div>
      {(p.columns || []).map((c, i) => <div key={`${c.title || "col"}-${i}`}><T value={c.title} {...E(`columns.${i}.title`)} className="text-sm font-semibold" /><ul className="mt-3 space-y-2 text-sm text-[var(--tmut)]">{(c.links || []).map((l, k) => <li key={k}><T value={typeof l === "string" ? l : (l?.label || "")} {...E(`columns.${i}.links.${k}`)} /></li>)}</ul></div>)}
    </footer>
  );
  return <div className="p-6 text-sm text-[var(--tmut)]">Unknown block: {block.type}</div>;
}
