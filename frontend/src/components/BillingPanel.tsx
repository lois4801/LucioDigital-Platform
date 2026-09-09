import { useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { CreditCard, FileSpreadsheet, Upload, CheckCircle2, Loader2, Receipt } from "lucide-react";
import { StorageUsageBar } from "@/components/FilesPanel";

export default function BillingPanel({ appDoc }) {
  const [plans, setPlans] = useState([]);
  const [meta, setMeta] = useState({});
  const [tx, setTx] = useState([]);
  const [busy, setBusy] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [usage, setUsage] = useState(null);
  const fileRef = useRef();

  useEffect(() => { load(); }, [appDoc.app_id]);
  async function load() {
    try {
      const [{ data: p }, { data: t }] = await Promise.all([api.get("/billing/plans"), api.get(`/billing/transactions?app_id=${appDoc.app_id}`)]);
      setPlans(p.plans); setMeta(p); setTx(t);
      api.get(`/apps/${appDoc.app_id}/files/usage`).then(r => setUsage(r.data)).catch(() => {});
    } catch { toast.error("Failed to load billing"); }
  }

  async function subscribe(lookup_key) {
    setBusy(lookup_key);
    try {
      const { data } = await api.post("/billing/checkout", { lookup_key, app_id: appDoc.app_id, origin_url: window.location.origin });
      window.location.href = data.checkout_url;
    } catch (e) { toast.error(e.response?.data?.detail || "Checkout failed"); setBusy(null); }
  }

  async function onFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    const fd = new FormData(); fd.append("file", f);
    try {
      const { data } = await api.post("/billing/plans/import", fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 120000 });
      toast.success(`Imported ${data.count} plans from ${data.source_file} and synced to Stripe`);
      load();
    } catch (err) { toast.error(err.response?.data?.detail || "Import failed"); }
    finally { setUploading(false); e.target.value = ""; }
  }

  return (
    <div data-testid="billing-panel" className="space-y-6">
      <div className="grid lg:grid-cols-[1fr_360px] gap-6">
        <div>
          <div className="flex items-end justify-between mb-4">
            <div>
              <div className="overline mb-1">Plan tiers · Stripe</div>
              <h3 className="font-display text-2xl font-semibold tracking-tight">Charge this client monthly</h3>
              <p className="text-sm text-[var(--mut)] mt-1">Pick the tier for <span className="text-[var(--fg)]">{appDoc.name}</span>. Checkout is powered by Stripe; test card 4242 4242 4242 4242.</p>
            </div>
            {appDoc.plan && <span data-testid="current-plan-chip" className="chip chip-active"><CheckCircle2 size={11} /> {appDoc.plan} active</span>}
          </div>
          {usage && <div className="mb-4"><StorageUsageBar usage={usage} /></div>}
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
            {plans.map((p) => {
              const current = appDoc.plan_lookup_key === p.lookup_key;
              return (
                <div key={p.lookup_key} data-testid={`plan-card-${p.lookup_key}`}
                  className={`card-surface p-5 flex flex-col ${current ? "!border-[var(--acc)]/60" : ""}`}>
                  <div className="overline">{p.name}</div>
                  <div className="font-display text-3xl font-bold mt-2">${Number(p.price).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                    <span className="text-sm text-[var(--mut)] font-normal">/{p.interval === "one_time" ? "once" : p.interval === "year" ? "yr" : "mo"}</span></div>
                  {p.description && <div className="text-xs text-[var(--mut)] mt-1">{p.description}</div>}
                  <ul className="mt-3 space-y-1 text-sm text-[var(--mut)] flex-1">
                    {(p.features || []).slice(0, 6).map((f, i) => <li key={i} className="flex gap-2"><span className="text-[var(--acc)]">•</span>{f}</li>)}
                  </ul>
                  <button data-testid={`plan-subscribe-${p.lookup_key}-btn`} onClick={() => subscribe(p.lookup_key)} disabled={!!busy || current}
                    className={`mt-4 w-full rounded-full py-2.5 text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-60 ${current ? "border border-[var(--acc)]/40 text-[var(--acc)]" : "btn-primary !py-2.5"}`}>
                    {busy === p.lookup_key ? <Loader2 size={14} className="animate-spin" /> : <CreditCard size={14} />}
                    {current ? "Current plan" : "Subscribe"}
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        <aside className="space-y-4">
          <div className="card-surface p-5">
            <div className="overline mb-2 flex items-center gap-2"><FileSpreadsheet size={12} className="text-[var(--acc)]" /> Import pricing</div>
            <p className="text-xs text-[var(--mut)]">Upload an Excel (.xlsx), CSV or Word (.docx) table with columns <span className="font-mono text-[var(--fg)]">Plan · Price · Interval · Features · Description</span>. Plans sync to Stripe automatically.</p>
            <input ref={fileRef} data-testid="pricing-file-input" type="file" accept=".xlsx,.xlsm,.csv,.docx" className="hidden" onChange={onFile} />
            <button data-testid="pricing-upload-btn" onClick={() => fileRef.current.click()} disabled={uploading}
              className="mt-4 w-full border border-dashed border-[var(--line)] hover:border-[var(--acc)]/60 rounded-xl py-6 flex flex-col items-center gap-2 text-sm transition-colors">
              {uploading ? <Loader2 size={18} className="animate-spin text-[var(--acc)]" /> : <Upload size={18} className="text-[var(--acc)]" />}
              {uploading ? "Parsing & syncing to Stripe…" : "Choose .xlsx / .csv / .docx"}
            </button>
            <div className="text-[11px] text-[var(--mut)] mt-3 font-mono">
              Source: {meta.source === "import" ? `${meta.source_file}` : meta.source === "manual" ? "manual" : "default tiers"} · {plans.length} plans
            </div>
          </div>

          <div className="card-surface p-5">
            <div className="overline mb-3 flex items-center gap-2"><Receipt size={12} className="text-[var(--acc)]" /> Transactions</div>
            {tx.length === 0 ? <div className="text-xs text-[var(--mut)]">No charges yet for this tenant.</div> : (
              <div className="space-y-2">
                {tx.map(t => (
                  <div key={t.session_id} data-testid="billing-transaction-row" className="flex items-center justify-between text-xs">
                    <div><div className="font-semibold">{t.plan_name}</div><div className="font-mono text-[var(--dim)]">{new Date(t.created_at).toLocaleDateString()}</div></div>
                    <div className="text-right"><div className="font-mono">${t.amount}</div>
                      <span className={`chip ${t.payment_status === "paid" ? "chip-active" : t.payment_status === "pending" ? "chip-maint" : ""}`} style={{ padding: "1px 6px" }}>{t.payment_status}</span></div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
