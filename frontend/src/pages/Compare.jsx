import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { ArrowLeftRight, Loader2, Sparkles, Send, Monitor } from "lucide-react";

const BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;

/** The capture service renders on first request, so retry a few times until the shot lands. */
function BeforeShot({ src }) {
  const [tries, setTries] = useState(0);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (tries >= 4 || failed) return;
    const t = setTimeout(() => setTries(n => n + 1), 5000);
    return () => clearTimeout(t);
  }, [tries, failed]);
  if (failed) return (
    <div data-testid="compare-before-failed" className="h-full grid place-items-center p-8 text-center text-sm text-[var(--mut)]">
      We couldn't capture that address automatically. Check the URL, or upload a screenshot of the current site instead.
    </div>
  );
  return (
    <div className="relative">
      <img data-testid="compare-before-img" key={tries} src={tries ? `${src}&r=${tries}` : src} alt="Current website" onError={() => setFailed(true)} className="w-full block" />
      {tries < 4 && <span className="absolute bottom-2 left-2 rounded-full bg-black/60 px-2 py-1 text-[10px] text-white/70">capturing the current site…</span>}
    </div>
  );
}

export default function Compare() {
  const { code } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [lead, setLead] = useState({ name: "", email: "", message: "" });
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    axios.get(`${BASE}/public/compare/${code}`).then(r => setData(r.data))
      .catch(e => setErr(e.response?.data?.detail || "This comparison link is no longer available"));
  }, [code]);

  async function send() {
    setBusy(true);
    try { await axios.post(`${BASE}/public/compare/${code}/lead`, lead); setSent(true); }
    catch (e) { setErr(e.response?.data?.detail || "Could not send that"); }
    finally { setBusy(false); }
  }

  if (err) return <div className="min-h-screen grid place-items-center text-center px-6"><div><div className="font-display text-2xl">{err}</div></div></div>;
  if (!data) return <div className="min-h-screen grid place-items-center"><Loader2 className="animate-spin text-[var(--acc)]" /></div>;

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--fg)]" data-testid="compare-page">
      <header className="px-6 lg:px-10 pt-14 pb-8 max-w-6xl mx-auto">
        <div className="flex items-center gap-2 text-[var(--acc)] text-xs font-semibold uppercase tracking-[0.2em]"><ArrowLeftRight size={13} /> Before and after</div>
        <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.03] mt-4" data-testid="compare-headline">{data.headline}</h1>
        <p className="text-[var(--mut)] mt-4 max-w-2xl text-base">On the left, {data.before_url ? <a href={data.before_url} target="_blank" rel="noreferrer" className="underline">the site as it is today</a> : "the site as it is today"}. On the right, the live rebuild — scroll it, click through it, it is real.</p>
      </header>

      <div className="px-6 lg:px-10 max-w-6xl mx-auto grid lg:grid-cols-2 gap-5 pb-12">
        <figure className="space-y-2">
          <figcaption className="flex items-center gap-2 text-[11px] uppercase tracking-widest text-[var(--dim)]"><Monitor size={12} /> Before</figcaption>
          <div className="rounded-2xl border border-[var(--line)] overflow-hidden bg-[var(--bg-2)] h-[520px] lg:h-[640px]">
            <div className="h-full overflow-y-auto">
              {data.before_image
                ? <BeforeShot src={data.before_image} />
                : <div className="h-full grid place-items-center text-sm text-[var(--mut)]">Screenshot unavailable</div>}
            </div>
          </div>
        </figure>

        <figure className="space-y-2">
          <figcaption className="flex items-center gap-2 text-[11px] uppercase tracking-widest text-[var(--acc)]"><Sparkles size={12} /> After — the rebuild</figcaption>
          <div className="rounded-2xl border border-[var(--acc)]/40 overflow-hidden h-[520px] lg:h-[640px] shadow-[0_40px_120px_-60px_var(--acc)]">
            <iframe data-testid="compare-after-frame" title="Rebuilt site" src={`/p/${data.preview_token}?embed=1`} className="w-full h-full border-0" />
          </div>
          <a data-testid="compare-open-live" href={`/p/${data.preview_token}`} target="_blank" rel="noreferrer" className="text-xs text-[var(--acc)] hover:underline">Open the rebuild full screen →</a>
        </figure>
      </div>

      <section className="px-6 lg:px-10 pb-24 max-w-2xl mx-auto">
        <div className="card-surface p-6 space-y-3">
          <h2 className="font-display text-2xl font-bold">Start with this rebuild</h2>
          <p className="text-sm text-[var(--mut)]">Leave your details and we'll get it live on your domain.</p>
          {sent ? <div data-testid="compare-lead-sent" className="text-sm text-[var(--acc)]">Thank you — we'll be in touch shortly.</div> : (
            <>
              <input data-testid="compare-lead-name" value={lead.name} onChange={e => setLead({ ...lead, name: e.target.value })} placeholder="Your name" className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3.5 py-2.5 text-sm outline-none focus:border-[var(--acc)]" />
              <input data-testid="compare-lead-email" type="email" value={lead.email} onChange={e => setLead({ ...lead, email: e.target.value })} placeholder="you@company.com" className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3.5 py-2.5 text-sm outline-none focus:border-[var(--acc)]" />
              <textarea data-testid="compare-lead-message" rows={3} value={lead.message} onChange={e => setLead({ ...lead, message: e.target.value })} placeholder="Anything you'd like changed?" className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3.5 py-2.5 text-sm outline-none focus:border-[var(--acc)] resize-none" />
              <button data-testid="compare-lead-send" onClick={send} disabled={busy || !lead.name || !lead.email} className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50"><Send size={13} /> {busy ? "Sending…" : "I want this rebuild"}</button>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
