import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Mail, CreditCard, Eye, Send } from "lucide-react";

/** Per-tenant weekly digest settings + the paid members area. */
export default function ProSettings({ appId }) {
  const [digest, setDigest] = useState({ enabled: false, hour: 8, recipients: [] });
  const [preview, setPreview] = useState(null);
  const [paid, setPaid] = useState({ enabled: false, mode: "one_time", price: 19, currency: "usd", interval: "month", page_ids: [] });
  const [pages, setPages] = useState([]);
  const [members, setMembers] = useState({ members: [], payments: [] });
  const [busy, setBusy] = useState("");

  const load = () => {
    api.get(`/apps/${appId}/digest/preview`).then(r => { setDigest({ ...r.data.settings }); setPreview(r.data); }).catch(() => { });
    api.get(`/apps/${appId}/webapp`).then(r => { setPages(r.data.pages || []); if (r.data.paid) setPaid(p => ({ ...p, ...r.data.paid })); }).catch(() => { });
    api.get(`/apps/${appId}/paid-members`).then(r => { setMembers(r.data); if (r.data.paid?.enabled !== undefined) setPaid(p => ({ ...p, ...r.data.paid })); }).catch(() => { });
  };
  useEffect(() => { load(); }, [appId]);

  async function saveDigest(next) {
    setDigest(next); setBusy("digest");
    try { await api.patch(`/apps/${appId}/webapp/digest`, next); toast.success("Digest settings saved"); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not save"); } finally { setBusy(""); }
  }
  async function sendTest() {
    setBusy("test");
    try { const { data } = await api.post(`/apps/${appId}/digest/test`); toast.success(`Test digest sent to ${data.sent_to}`); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not send"); } finally { setBusy(""); }
  }
  async function savePaid(next) {
    setPaid(next); setBusy("paid");
    try { const { data } = await api.patch(`/apps/${appId}/webapp/paid`, next); setPaid(p => ({ ...p, ...data })); toast.success(next.enabled ? "Paid members area is live" : "Paid members area off — those pages are open again"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not save"); } finally { setBusy(""); }
  }
  const togglePage = (id) => savePaid({ ...paid, page_ids: paid.page_ids.includes(id) ? paid.page_ids.filter(x => x !== id) : [...paid.page_ids, id] });

  return (
    <div className="space-y-3">
      <div data-testid="digest-card" className="rounded-xl border border-[var(--line)] p-4 space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <Mail size={15} className="text-[var(--acc)]" />
          <div className="text-xs flex-1 min-w-[220px]">
            <div className="font-semibold">Monday client digest</div>
            <div className="text-[var(--mut)]">New submissions, next week's bookings and pending edit requests — emailed to the client panel admins and you.{digest.last_sent ? ` Last sent ${new Date(digest.last_sent).toLocaleString()}.` : ""}</div>
          </div>
          <label className="flex items-center gap-2 text-xs cursor-pointer">
            <input type="checkbox" data-testid="digest-enabled" checked={!!digest.enabled} onChange={e => saveDigest({ ...digest, enabled: e.target.checked })} className="accent-[var(--acc)]" /> On
          </label>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <label className="text-xs text-[var(--mut)]">Send at
            <select data-testid="digest-hour" value={digest.hour} onChange={e => saveDigest({ ...digest, hour: Number(e.target.value) })} className="ml-2 bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2 py-1.5 text-xs">
              {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{`${String(h).padStart(2, "0")}:00 UTC`}</option>)}
            </select>
          </label>
          <input data-testid="digest-recipients" defaultValue={(digest.recipients || []).join(", ")} onBlur={e => saveDigest({ ...digest, recipients: e.target.value.split(",").map(s => s.trim()).filter(Boolean) })}
            placeholder="extra recipients, comma separated (optional)" className="flex-1 min-w-[220px] bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-xs outline-none focus:border-[var(--acc)]" />
          <button data-testid="digest-test-btn" onClick={sendTest} disabled={busy === "test"} className="btn-ghost !py-2 !px-4 text-xs flex items-center gap-1.5"><Send size={12} /> Send me a test</button>
        </div>
        {preview && (
          <details data-testid="digest-preview">
            <summary className="text-xs text-[var(--acc)] cursor-pointer flex items-center gap-1.5"><Eye size={12} /> Preview this week's digest ({preview.counts.submissions} submissions · {preview.counts.bookings} bookings · {preview.counts.edit_requests} edit requests)</summary>
            <pre className="mt-2 whitespace-pre-wrap text-[11px] text-[var(--mut)] bg-[var(--bg-2)] rounded-xl p-3 max-h-64 overflow-y-auto">{preview.text}</pre>
          </details>
        )}
      </div>

      <div data-testid="paid-area-card" className="rounded-xl border border-[var(--line)] p-4 space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <CreditCard size={15} className="text-[var(--acc)]" />
          <div className="text-xs flex-1 min-w-[220px]">
            <div className="font-semibold">Paid members area</div>
            <div className="text-[var(--mut)]">Charge for access to chosen pages. Visitors sign in, pay, then unlock everything paid on this site. Switch it off and those pages open up again instantly.</div>
          </div>
          <label className="flex items-center gap-2 text-xs cursor-pointer">
            <input type="checkbox" data-testid="paid-enabled" checked={!!paid.enabled} onChange={e => savePaid({ ...paid, enabled: e.target.checked })} className="accent-[var(--acc)]" /> On
          </label>
        </div>
        {paid.enabled && (
          <>
            <div className="flex flex-wrap gap-2 items-center">
              <div className="flex rounded-lg border border-[var(--line)] overflow-hidden text-[11px]">
                {[["one_time", "One-time fee"], ["subscription", "Subscription"]].map(([k, l]) => (
                  <button key={k} data-testid={`paid-mode-${k}`} onClick={() => savePaid({ ...paid, mode: k })} className={`px-3 py-1.5 ${paid.mode === k ? "bg-[var(--acc)]/15 text-[var(--acc)]" : "text-[var(--mut)]"}`}>{l}</button>
                ))}
              </div>
              <input data-testid="paid-price" type="number" min={1} step={1} value={paid.price} onChange={e => setPaid({ ...paid, price: Number(e.target.value) })} onBlur={() => savePaid(paid)}
                className="w-24 bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm" />
              <select data-testid="paid-currency" value={paid.currency} onChange={e => savePaid({ ...paid, currency: e.target.value })} className="bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-2 py-2 text-xs">
                {["usd", "cad", "eur", "gbp", "aud"].map(c => <option key={c} value={c}>{c.toUpperCase()}</option>)}
              </select>
              {paid.mode === "subscription" && (
                <select data-testid="paid-interval" value={paid.interval} onChange={e => savePaid({ ...paid, interval: e.target.value })} className="bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-2 py-2 text-xs">
                  <option value="month">per month</option><option value="year">per year</option>
                </select>
              )}
            </div>
            <div className="space-y-1">
              <div className="text-[10px] uppercase tracking-wide text-[var(--dim)]">Paid pages</div>
              {pages.map(p => (
                <label key={p.page_id} data-testid={`paid-page-${p.slug.replace("/", "") || "home"}`} className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg border border-[var(--line)] cursor-pointer">
                  <input type="checkbox" checked={paid.page_ids.includes(p.page_id)} onChange={() => togglePage(p.page_id)} className="accent-[var(--acc)]" />
                  {p.name} <span className="font-mono text-[10px] text-[var(--dim)]">{p.slug}</span>
                </label>
              ))}
            </div>
          </>
        )}
        <div className="border-t border-[var(--line)] pt-2">
          <div className="text-[10px] uppercase tracking-wide text-[var(--dim)] mb-1">Paying members ({members.members.length})</div>
          {members.members.length === 0 && <div className="text-xs text-[var(--mut)]">Nobody has paid yet.</div>}
          {members.members.map(m => (
            <div key={m.site_user_id} data-testid="paid-member-row" className="flex flex-wrap items-center gap-2 text-xs py-1">
              <span className="font-semibold">{m.name || m.email}</span><span className="text-[var(--mut)]">{m.email}</span>
              <span className="chip">{m.level}</span><span className={`chip ${m.status === "active" ? "chip-active" : "chip-maint"}`}>{m.status}</span>
              <span className="ml-auto font-mono text-[10px]">{m.amount} {String(m.currency || "").toUpperCase()}</span>
            </div>
          ))}
          {members.payments.length > 0 && (
            <details className="mt-1"><summary data-testid="payment-history" className="text-[11px] text-[var(--acc)] cursor-pointer">Payment history ({members.payments.length})</summary>
              <div className="mt-1 space-y-0.5">
                {members.payments.map(p => <div key={p.session_id} className="text-[10px] font-mono text-[var(--mut)]">{p.created_at?.slice(0, 19)} · {p.amount} {String(p.currency || "").toUpperCase()} · {p.status}</div>)}
              </div>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}
