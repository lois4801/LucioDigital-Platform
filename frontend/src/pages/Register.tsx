import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Layers, ChevronRight, MailCheck } from "lucide-react";
import SocialSignIn from "@/components/SocialSignIn";
import { CursorFXBar, useCursorFX } from "@/components/CursorFX";
import { swatchOf } from "@/lib/cursorEffects";
import PageCursorFX from "@/components/PageCursorFX";

export default function Register() {
  const { register } = useAuth();
  const { effect } = useCursorFX();
  const [c1, c2] = swatchOf(effect);
  const panel = useRef(null);
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
    <div className="min-h-screen relative overflow-hidden flex flex-col">
      {/* Background layer: one unified workspace, no split panels. */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <video src="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"
          autoPlay muted loop playsInline className="absolute inset-0 w-full h-full object-cover opacity-25" />
        <div className="absolute inset-0 bg-gradient-to-br from-[var(--bg)]/92 via-[var(--bg)]/85 to-[var(--bg)]/95" />
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[900px] h-[520px] rounded-full bg-[var(--acc)]/10 blur-[150px]" />
      </div>
      <PageCursorFX />

      <header className="relative z-10 px-6 sm:px-10 pt-7">
        <Link to="/" data-testid="brand-home-link" title="Back to the Lois-Tech home page"
          className="inline-flex items-center gap-3 cursor-pointer group w-fit">
          <div className="w-9 h-9 rounded-lg bg-[var(--card)]/80 border border-[var(--line)] flex items-center justify-center group-hover:border-[var(--acc)]/50 transition-colors">
            <Layers size={18} className="text-[var(--acc)]" />
          </div>
          <div className="font-display font-semibold tracking-tight text-lg">Lois-<span className="text-[var(--acc)]">Tech</span></div>
        </Link>
      </header>

      <main className="relative z-10 flex-1 flex items-center justify-center px-6 py-10">
        <div className="w-full max-w-md fade-in relative z-10" ref={panel} data-fx-content>
          <div className="rounded-3xl border border-white/10 bg-[#080b10]/80 backdrop-blur-xl shadow-[0_40px_120px_-40px_rgba(0,0,0,0.9)] p-6 sm:p-8">
            <div className="overline mb-2">Create account</div>
            <h1 className="font-display text-3xl font-semibold tracking-tight">Start your agency workspace.</h1>
            <p className="text-[var(--mut)] mt-2 text-sm">14-day free trial. No credit card.</p>

            <div className="mt-5" data-testid="register-cursor-picker" data-fx-skip>
              <CursorFXBar />
            </div>

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
      </main>

      <footer className="relative z-10 px-6 sm:px-10 pb-8 max-w-xl">
        <div className="overline">Agency workspace · v2.4</div>
        <p className="font-display text-lg text-white/45 mt-1 leading-snug" data-testid="register-tagline">
          Ship, showcase and hand off every client app from one master workspace.
        </p>
      </footer>
    </div>
  );
}
