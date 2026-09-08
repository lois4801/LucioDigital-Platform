import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Layers, Mail, Lock, ChevronRight } from "lucide-react";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
function googleAuth() {
  const redirectUrl = window.location.origin + "/dashboard";
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
}

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("jaybernabe@luciodigital.com");
  const [password, setPassword] = useState("Lucio2026!");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      await login(email, password);
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

          <button data-testid="auth-google-login-btn" onClick={googleAuth}
            className="mt-8 w-full flex items-center justify-center gap-2 py-3 rounded-full border border-[var(--line)] hover:border-white/25 hover:bg-white/5 transition-all">
            <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
            Continue with Google
          </button>

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
                  required
                  className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl pl-9 pr-3 py-3 text-sm font-mono focus:border-[var(--acc)] outline-none" />
              </div>
            </label>
            <label className="block">
              <span className="overline block mb-2">Password</span>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--mut)]" />
                <input data-testid="login-password-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                  required
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
