import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Layers, Mail, Lock, ChevronRight } from "lucide-react";
import SocialSignIn from "@/components/SocialSignIn";

const SAVED_EMAIL_KEY = "lt_saved_email";

export default function Login() {
  const { login } = useAuth();
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
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:block relative overflow-hidden border-r border-[var(--line)]">
        <video src="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoylikes.mp4"
          autoPlay muted loop playsInline className="absolute inset-0 w-full h-full object-cover opacity-70" />
        <div className="absolute inset-0 bg-gradient-to-br from-[var(--bg)]/80 via-transparent to-[var(--bg)]/60" />
        <div className="relative z-10 h-full flex flex-col justify-between p-12">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[var(--card)] border border-[var(--line)] flex items-center justify-center">
              <Layers size={18} className="text-[var(--acc)]" />
            </div>
            <div className="font-display font-semibold tracking-tight text-lg">Lois-<span className="text-[var(--acc)]">Tech</span></div>
          </div>
          <div>
            <div className="overline mb-3">Agency workspace · v2.4</div>
            <div className="font-display text-4xl leading-tight tracking-tighter">
              Ship, showcase and hand off every client app from one master workspace.
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-md fade-in">
          <div className="overline mb-3">Sign in</div>
          <h1 className="font-display text-3xl font-semibold tracking-tight">Welcome back.</h1>
          <p className="text-[var(--mut)] mt-2 text-sm">Access your agency control center.</p>

          <SocialSignIn mode="signin" />

          <div className="flex items-center gap-3 my-6">
            <div className="h-px flex-1 bg-[var(--line)]" />
            <span className="overline">or</span>
            <div className="h-px flex-1 bg-[var(--line)]" />
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
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
    </div>
  );
}
