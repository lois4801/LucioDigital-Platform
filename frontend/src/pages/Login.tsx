import Logo, { LogoMark } from "@/components/Logo";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Layers, Mail, Lock, ChevronRight } from "lucide-react";
import SocialSignIn from "@/components/SocialSignIn";
import { CursorFXBar, useCursorFX } from "@/components/CursorFX";
import { swatchOf } from "@/lib/cursorEffects";
import PageCursorFX from "@/components/PageCursorFX";

const SAVED_EMAIL_KEY = "lt_saved_email";

export default function Login() {
  const { login } = useAuth();
  const { effect } = useCursorFX();
  const [c1, c2] = swatchOf(effect);
  const panel = useRef(null);
  const nav = useNavigate();
  const [params] = useSearchParams();
  // Nothing is pre-filled for a new visitor. A saved address only ever lives in this browser.
  const [email, setEmail] = useState(() => localStorage.getItem(SAVED_EMAIL_KEY) || "");
  const [remember, setRemember] = useState(() => !!localStorage.getItem(SAVED_EMAIL_KEY));
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (params.get("verified")) toast.success("Email confirmed — you're all set.");
    const unavailable = params.get("provider_unavailable");
    if (unavailable) toast.info(`${unavailable} sign-in isn't connected yet — use your email or a sign-in link.`);
  }, [params]);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      await login(email, password);
      if (remember) localStorage.setItem(SAVED_EMAIL_KEY, email.trim());
      else localStorage.removeItem(SAVED_EMAIL_KEY);
      toast.success("Welcome back.");
      nav("/dashboard");
    } catch (e) {
      const msg = formatApiError(e.response?.data?.detail) || e.message;
      setErr(msg); toast.error(msg);
    } finally { setBusy(false); }
  }

  return (
    <div className="min-h-screen relative overflow-hidden flex flex-col">
      {/* Background layer: one unified workspace, no split panels. */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <video src="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoylikes.mp4"
          autoPlay muted loop playsInline className="absolute inset-0 w-full h-full object-cover opacity-25" />
        <div className="absolute inset-0 bg-gradient-to-br from-[var(--bg)]/92 via-[var(--bg)]/85 to-[var(--bg)]/95" />
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[900px] h-[520px] rounded-full bg-[var(--acc)]/10 blur-[150px]" />
      </div>
      <PageCursorFX />

      {/* Brand, top-left of the whole page */}
      <header className="relative z-10 px-6 sm:px-10 pt-7">
        <Link to="/" data-testid="brand-home-link" title="Back to the LucioDigital home page"
          className="inline-flex items-center gap-3 cursor-pointer group w-fit">
          <Logo variant="white" size={19} />
        </Link>
      </header>

      {/* Centered form card floating over the full-page background */}
      <main className="relative z-10 flex-1 flex items-center justify-center px-6 py-10">
        <div className="w-full max-w-md fade-in relative z-10" ref={panel} data-fx-content>
          <div className="rounded-3xl border border-white/10 bg-[#080b10]/80 backdrop-blur-xl shadow-[0_40px_120px_-40px_rgba(0,0,0,0.9)] p-6 sm:p-8">
            <div className="flex justify-center mb-5" data-testid="login-card-logo"><Logo variant="white" size={20} /></div>
            <div className="overline mb-2">Sign in</div>
            <h1 className="font-display text-3xl font-semibold tracking-tight">Welcome back.</h1>
            <p className="text-[var(--mut)] mt-2 text-sm">Access your agency control center.</p>

            <div className="mt-5" data-testid="login-cursor-picker" data-fx-skip>
              <CursorFXBar />
            </div>

            <SocialSignIn mode="signin" />
            <div className="flex items-center gap-3 my-6">
              <div className="h-px flex-1 bg-[var(--line)]" />
              <span className="overline">or</span>
              <div className="h-px flex-1 bg-[var(--line)]" />
            </div>

            <form onSubmit={onSubmit} data-testid="login-form" className="space-y-4 rounded-2xl border p-5 transition-colors duration-500"
              style={{ borderColor: `${c1}55`, background: `linear-gradient(160deg, ${c1}0f, ${c2}0a)`, boxShadow: `0 0 40px -18px ${c1}80` }}>
              <label className="block">
                <span className="overline block mb-2">Email</span>
                <div className="relative">
                  <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--mut)]" />
                  <input data-testid="login-email-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                    required autoComplete="off" placeholder="you@company.com"
                    className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl pl-9 pr-3 py-3 text-sm font-mono focus:border-[var(--acc)] outline-none" />
                </div>
              </label>
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input data-testid="login-remember-email" type="checkbox" checked={remember}
                  onChange={(e) => {
                    setRemember(e.target.checked);
                    if (!e.target.checked) localStorage.removeItem(SAVED_EMAIL_KEY);
                  }}
                  className="accent-[var(--acc)]" />
                <span className="text-xs text-[var(--mut)]">Save my email on this device only</span>
              </label>
              <label className="block">
                <span className="overline block mb-2">Password</span>
                <div className="relative">
                  <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--mut)]" />
                  <input data-testid="login-password-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                    required autoComplete="current-password"
                    className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl pl-9 pr-3 py-3 text-sm font-mono focus:border-[var(--acc)] outline-none" />
                </div>
              </label>
              {err && <div className="text-sm text-red-400 font-mono">{err}</div>}
              <button data-testid="auth-jwt-submit-btn" disabled={busy} type="submit"
                className="w-full btn-primary flex items-center justify-center gap-2 disabled:opacity-60">
                {busy ? "Signing in…" : "Sign in"} <ChevronRight size={16} />
              </button>
            </form>

            <p className="mt-6 text-sm text-[var(--mut)]">
              No account yet? <Link to="/register" className="text-[var(--acc)] hover:underline">Create one</Link>
            </p>
          </div>
        </div>
      </main>

      {/* Subtle brand statement, bottom-left of the page */}
      <footer className="relative z-10 px-6 sm:px-10 pb-8 max-w-xl">
        <div className="overline">Agency workspace · v2.4</div>
        <p className="font-display text-lg md:text-lg text-white/45 mt-1 leading-snug" data-testid="login-tagline">
          Ship, showcase and hand off every client app from one master workspace.
        </p>
      </footer>
    </div>
  );
}
