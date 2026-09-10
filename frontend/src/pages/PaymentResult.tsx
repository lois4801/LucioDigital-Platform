import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

export function PaymentSuccess() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const sessionId = params.get("session_id");
  const [state, setState] = useState({ status: "checking" });

  useEffect(() => {
    if (!sessionId) return;
    let tries = 0;
    const t = setInterval(async () => {
      tries += 1;
      try {
        const { data } = await api.get(`/billing/status/${sessionId}`);
        if (data.payment_status === "paid") { setState({ status: "paid", ...data }); clearInterval(t); }
        else if (["expired", "failed"].includes(data.payment_status) || tries > 10) { setState({ status: "failed", ...data }); clearInterval(t); }
      } catch { if (tries > 10) { setState({ status: "failed" }); clearInterval(t); } }
    }, 2000);
    return () => clearInterval(t);
  }, [sessionId]);

  return (
    <div className="min-h-screen flex items-center justify-center px-6" data-testid="payment-success-page">
      <div className="card-surface p-10 max-w-md w-full text-center">
        {state.status === "checking" && <><Loader2 size={32} className="animate-spin text-[var(--acc)] mx-auto" /><div className="font-display text-2xl mt-4">Confirming payment…</div><p className="text-sm text-[var(--mut)] mt-2">Waiting for Stripe to confirm.</p></>}
        {state.status === "paid" && <><CheckCircle2 size={36} className="text-[var(--acc)] mx-auto" /><div className="font-display text-2xl mt-4">Subscribed to {state.plan_name}</div><p className="text-sm text-[var(--mut)] mt-2">Billing is active for this client.</p>
          <button data-testid="payment-back-btn" onClick={() => nav(state.app_id ? `/apps/${state.app_id}` : "/dashboard")} className="btn-primary mt-6">Back to client</button></>}
        {state.status === "failed" && <><XCircle size={36} className="text-red-400 mx-auto" /><div className="font-display text-2xl mt-4">Payment not confirmed</div><p className="text-sm text-[var(--mut)] mt-2">If you were charged, it will sync shortly via webhook.</p>
          <button onClick={() => nav("/dashboard")} className="btn-ghost mt-6">Dashboard</button></>}
      </div>
    </div>
  );
}

export function PaymentCancel() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const appId = params.get("app_id");
  return (
    <div className="min-h-screen flex items-center justify-center px-6" data-testid="payment-cancel-page">
      <div className="card-surface p-10 max-w-md w-full text-center">
        <XCircle size={36} className="text-amber-400 mx-auto" />
        <div className="font-display text-2xl mt-4">Checkout cancelled</div>
        <p className="text-sm text-[var(--mut)] mt-2">No charge was made.</p>
        <button data-testid="payment-cancel-back-btn" onClick={() => nav(appId ? `/apps/${appId}` : "/dashboard")} className="btn-ghost mt-6">Back</button>
      </div>
    </div>
  );
}
