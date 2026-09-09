import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Globe, RefreshCw, Trash2, CheckCircle2, Circle, AlertTriangle, Copy } from "lucide-react";

const STATUS = {
  verified: { label: "Verified", cls: "chip-active" },
  partial: { label: "Partially configured", cls: "chip-maint" },
  pending: { label: "Pending DNS", cls: "chip-maint" },
};

function Row({ ok, label, name, expected, found }) {
  return (
    <div className="p-4 rounded-xl bg-[var(--bg-2)] border border-[var(--line)] flex gap-3">
      {ok ? <CheckCircle2 size={18} className="text-[var(--acc)] shrink-0" /> : <Circle size={18} className="text-[var(--dim)] shrink-0" />}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold">{label}</div>
        <div className="grid sm:grid-cols-[80px_1fr] gap-x-3 gap-y-1 mt-2 text-xs font-mono">
          <span className="text-[var(--dim)]">Name</span><span className="truncate">{name}</span>
          <span className="text-[var(--dim)]">Value</span>
          <span className="flex items-center gap-2 truncate">{expected}
            <button onClick={() => { navigator.clipboard.writeText(expected); toast.success("Copied"); }} className="text-[var(--mut)] hover:text-white"><Copy size={11} /></button></span>
          <span className="text-[var(--dim)]">Found</span>
          <span className={found?.length ? "text-[var(--fg)]" : "text-[var(--dim)]"}>{found?.length ? found.join(", ") : "— nothing yet"}</span>
        </div>
      </div>
    </div>
  );
}

export default function DomainPanel({ appDoc, setAppDoc }) {
  const [domain, setDomain] = useState("");
  const [busy, setBusy] = useState(false);
  const dns = appDoc.domain_dns;
  const st = STATUS[appDoc.domain_status] || STATUS.pending;

  async function save() {
    setBusy(true);
    try { const { data } = await api.post(`/apps/${appDoc.app_id}/domain`, { domain }); setAppDoc(data); setDomain(""); toast.success("Domain saved — add the DNS records below"); }
    catch (e) { toast.error(e.response?.data?.detail || "Invalid domain"); }
    finally { setBusy(false); }
  }
  async function verify() {
    setBusy(true);
    try { const { data } = await api.post(`/apps/${appDoc.app_id}/domain/verify`); setAppDoc(data);
      data.domain_status === "verified" ? toast.success("Domain verified") : toast.info("DNS not fully propagated yet"); }
    catch { toast.error("DNS check failed"); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!confirm("Remove custom domain?")) return;
    const { data } = await api.delete(`/apps/${appDoc.app_id}/domain`); setAppDoc(data);
  }

  return (
    <div data-testid="domain-panel" className="grid lg:grid-cols-[1fr_380px] gap-6">
      <div className="card-surface p-6">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-[var(--acc)]/10 border border-[var(--acc)]/30 flex items-center justify-center"><Globe size={18} className="text-[var(--acc)]" /></div>
          <div className="flex-1">
            <div className="overline">Custom domain</div>
            <h3 className="font-display text-xl font-semibold tracking-tight mt-1">Point the client's domain at this tenant</h3>
            {!appDoc.custom_domain ? (
              <div className="mt-4 flex gap-2 max-w-lg">
                <input data-testid="domain-input" value={domain} onChange={e => setDomain(e.target.value)} placeholder="app.clientbrand.com"
                  className="flex-1 bg-[var(--bg-2)] border border-[var(--line)] rounded-full px-4 py-2.5 text-sm font-mono outline-none focus:border-[var(--acc)]" />
                <button data-testid="domain-save-btn" onClick={save} disabled={busy || !domain} className="btn-primary text-sm !py-2 !px-5 disabled:opacity-50">Add domain</button>
              </div>
            ) : (
              <>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <span data-testid="domain-name" className="font-mono text-lg">{appDoc.custom_domain}</span>
                  <span data-testid="domain-status-badge" className={`chip ${st.cls}`}><span className={`pulse-dot ${appDoc.domain_status === "verified" ? "" : "amber"}`} />{st.label}</span>
                  <button data-testid="domain-verify-btn" onClick={verify} disabled={busy} className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2 ml-auto">
                    <RefreshCw size={13} className={busy ? "animate-spin" : ""} /> Check DNS</button>
                  <button data-testid="domain-remove-btn" onClick={remove} className="w-9 h-9 rounded-full border border-[var(--line)] flex items-center justify-center hover:text-red-400 hover:border-red-500/40"><Trash2 size={14} /></button>
                </div>
                {appDoc.domain_checked_at && <div className="text-[11px] font-mono text-[var(--dim)] mt-2">Last checked {new Date(appDoc.domain_checked_at).toLocaleString()} · live DNS lookup</div>}
                <div className="mt-5 space-y-3">
                  <Row ok={dns?.cname?.ok} label="1 · CNAME record" name={appDoc.custom_domain} expected="tenants.luciostudio.app" found={dns?.cname?.found} />
                  <Row ok={dns?.txt?.ok} label="2 · TXT ownership record" name={`_lucio-verify.${appDoc.custom_domain}`} expected={appDoc.domain_token} found={dns?.txt?.found} />
                  <div className="p-4 rounded-xl bg-[var(--bg-2)] border border-[var(--line)] flex gap-3">
                    {appDoc.domain_status === "verified" ? <CheckCircle2 size={18} className="text-[var(--acc)] shrink-0" /> : <Circle size={18} className="text-[var(--dim)] shrink-0" />}
                    <div><div className="text-sm font-semibold">3 · SSL certificate</div><div className="text-xs text-[var(--mut)] mt-1">Issued automatically once both records verify. Propagation can take up to 48h.</div></div>
                  </div>
                </div>
                {dns && !dns.resolves && <div className="mt-3 text-xs text-amber-300 flex items-center gap-2 font-mono"><AlertTriangle size={12} /> Domain doesn't resolve yet — check the registrar.</div>}
              </>
            )}
          </div>
        </div>
      </div>

      <aside className="card-surface p-5 text-sm">
        <div className="overline mb-3">How it works</div>
        <ol className="space-y-3 text-[var(--mut)]">
          <li><span className="text-[var(--fg)] font-semibold">Add the domain</span> the client owns (subdomains recommended).</li>
          <li><span className="text-[var(--fg)] font-semibold">Create two DNS records</span> at their registrar using the values shown.</li>
          <li><span className="text-[var(--fg)] font-semibold">Click Check DNS.</span> We perform a real-time lookup and flip the badge to Verified.</li>
        </ol>
        <div className="mt-5 p-3 rounded-lg bg-[var(--bg-2)] border border-[var(--line)] text-xs font-mono text-[var(--mut)]">
          Tip: Cloudflare users — set the CNAME to “DNS only” (grey cloud) during verification.
        </div>
      </aside>
    </div>
  );
}
