import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Layers, ChevronRight, MailCheck } from "lucide-react";
import SocialSignIn from "@/components/SocialSignIn";
import { CursorFXBar, useCursorFX } from "@/components/CursorFX";
import { swatchOf } from "@/lib/cursorEffects";
import ScopedCursorFX from "@/components/ScopedCursorFX";

export default function Register() {
  const { register } = useAuth();
  const { effect } = useCursorFX();
  const [c1, c2] = swatchOf(effect);
  const panel = useRef(null);
  const fxBurst = useRef(null);
  const burstAt = (el, n = 6) => { fxBurst.current?.(el, n); };
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
      <div className="flex items-center justify-center p-6 lg:p-12 order-2 lg:order-1 min-w-0 overflow-hidden">
        <div className="w-full max-w-md fade-in" ref={panel}>
          <div className="flex items-center gap-3 mb-8">
            <div className="w-9 h-9 rounded-lg bg-[var(--card)] border border-[var(--line)] flex items-center justify-center">
              <Layers size={18} className="text-[var(--acc)]" />
            </div>
            <div className="font-display font-semibold tracking-tight text-lg">Lois-<span className="text-[var(--acc)]">Tech</span></div>
          </div>
          <div>
            <div className="overline mb-3">Create account</div>
            <h1 className="font-display text-3xl font-semibold tracking-tight">Start your agency workspace.</h1>
            <p className="text-[var(--mut)] mt-2 text-sm">14-day free trial. No credit card.</p>
          </div>
          <div className="mt-5" data-testid="register-cursor-picker" data-fx-skip>
            <CursorFXBar />
          </div>

          <ScopedCursorFX burstRef={fxBurst} className="mt-2 -mx-6 px-6 sm:-mx-12 sm:px-12 pb-2">
          <SocialSignIn mode="signup" />
      <div className="flex items-center gap-3 my-6">
            <div className="h-px flex-1 bg-[var(--line)]" />
            <span className="overline">or</span>
            <div className="h-px flex-1 bg-[var(--line)]" />
          </div>

          <form onSubmit={onSubmit} data-testid="register-form" className="space-y-4 rounded-2xl border p-5 transition-colors duration-500"
            style={{ borderColor: `${c1}55`, background: `linear-gradient(160deg, ${c1}0f, ${c2}0a)`, boxShadow: `0 0 40px -18px ${c1}80` }}>
            {["name", "email", "password"].map((k) => (
              <label key={k} className="block">
                <span className="overline block mb-2">{k}</span>
                <input data-testid={`register-${k}-input`} type={k === "password" ? "password" : k === "email" ? "email" : "text"}
                  value={form[k]} onChange={(e) => { setForm({ ...form, [k]: e.target.value }); burstAt(e.target, 3); }}
                  onFocus={(e) => burstAt(e.target, 8)} required
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
              onMouseEnter={(e) => burstAt(e.currentTarget, 10)}
              className="w-full btn-primary flex items-center justify-center gap-2 disabled:opacity-60">
              {busy ? "Creating…" : "Create workspace"} <ChevronRight size={16} />
            </button>
          </form>
          </ScopedCursorFX>

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
