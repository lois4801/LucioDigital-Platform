import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Layers, ChevronRight, MailCheck } from "lucide-react";
import SocialSignIn from "@/components/SocialSignIn";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [sent, setSent] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      await register(form.email, form.password, form.name);
      setSent(true);
      toast.success("Workspace created — check your inbox to confirm your email.");
      setTimeout(() => nav("/dashboard"), 1600);
    } catch (e) {
      const msg = formatApiError(e.response?.data?.detail) || e.message;
      setErr(msg); toast.error(msg);
    } finally { setBusy(false); }
  }

  async function resend() {
    try {
      await api.post("/auth/verify/request", { email: form.email });
      toast.success("Confirmation email sent again.");
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Could not resend");
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="flex items-center justify-center p-6 lg:p-12 order-2 lg:order-1">
        <div className="w-full max-w-md fade-in">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-9 h-9 rounded-lg bg-[var(--card)] border border-[var(--line)] flex items-center justify-center">
              <Layers size={18} className="text-[var(--acc)]" />
            </div>
            <div className="font-display font-semibold tracking-tight text-lg">Lois-<span className="text-[var(--acc)]">Tech</span></div>
          </div>
          <div className="overline mb-3">Create account</div>
          <h1 className="font-display text-3xl font-semibold tracking-tight">Start your agency workspace.</h1>
          <p className="text-[var(--mut)] mt-2 text-sm">14-day free trial. No credit card.</p>

          <SocialSignIn mode="signup" />

          <div className="flex items-center gap-3 my-6">
            <div className="h-px flex-1 bg-[var(--line)]" />
            <span className="overline">or</span>
            <div className="h-px flex-1 bg-[var(--line)]" />
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            {["name", "email", "password"].map((k) => (
              <label key={k} className="block">
                <span className="overline block mb-2">{k}</span>
                <input data-testid={`register-${k}-input`} type={k === "password" ? "password" : k === "email" ? "email" : "text"}
                  value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} required
                  className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-3 text-sm font-mono focus:border-[var(--acc)] outline-none" />
              </label>
            ))}
            {err && <div className="text-sm text-red-400 font-mono">{err}</div>}
            {sent && (
              <div data-testid="register-verify-notice" className="flex items-start gap-2 p-3 rounded-xl bg-[var(--acc)]/10 border border-[var(--acc)]/30 text-sm">
                <MailCheck size={15} className="text-[var(--acc)] mt-0.5 shrink-0" />
                <span>
                  We sent a confirmation link to <b className="font-mono">{form.email}</b>. Confirm it to prove the
                  address is real.{" "}
                  <button type="button" data-testid="register-resend-btn" onClick={resend} className="text-[var(--acc)] hover:underline">Resend</button>
                </span>
              </div>
            )}
            <button data-testid="register-submit-btn" disabled={busy} type="submit"
              className="w-full btn-primary flex items-center justify-center gap-2 disabled:opacity-60">
              {busy ? "Creating…" : "Create workspace"} <ChevronRight size={16} />
            </button>
          </form>

          <p className="mt-6 text-sm text-[var(--mut)]">
            Have an account? <Link to="/login" className="text-[var(--acc)] hover:underline">Sign in</Link>
          </p>
        </div>
      </div>

      <div className="hidden lg:block relative overflow-hidden border-l border-[var(--line)] order-1 lg:order-2">
        <video src="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"
          autoPlay muted loop playsInline className="absolute inset-0 w-full h-full object-cover opacity-70" />
        <div className="absolute inset-0 bg-gradient-to-tl from-[var(--bg)]/80 via-transparent to-[var(--bg)]/60" />
      </div>
    </div>
  );
}
