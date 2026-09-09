import { useEffect, useState } from "react";
import { toast } from "sonner";
import api, { formatApiError } from "@/lib/api";
import { Mail, Loader2, Wand2 } from "lucide-react";

/** Google is Emergent-managed; Microsoft/Yahoo appear as soon as their credentials exist. */
function googleAuth() {
  const redirectUrl = window.location.origin + "/dashboard";
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
}

const API_ROOT = process.env.REACT_APP_BACKEND_URL;

const GoogleMark = () => (
  <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" /><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" /><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" /><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" /></svg>
);
const MicrosoftMark = () => (
  <svg width="16" height="16" viewBox="0 0 23 23"><path fill="#F25022" d="M0 0h11v11H0z" /><path fill="#7FBA00" d="M12 0h11v11H12z" /><path fill="#00A4EF" d="M0 12h11v11H0z" /><path fill="#FFB900" d="M12 12h11v11H12z" /></svg>
);
const YahooMark = () => (
  <svg width="16" height="16" viewBox="0 0 24 24"><path fill="#6001D2" d="M3 5h4.3l2.9 6.9L13.2 5H17l-6.4 14H6.8l1.8-4L3 5z" /><circle fill="#6001D2" cx="19" cy="16.5" r="2" /></svg>
);

export default function SocialSignIn({ mode = "signin" }) {
  const [providers, setProviders] = useState({ google: true });
  const [email, setEmail] = useState("");
  const [magicOpen, setMagicOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/auth/providers").then(({ data }) => setProviders(data)).catch(() => {});
  }, []);

  function oauth(provider) {
    if (!providers[provider]) {
      toast.info(`${provider === "microsoft" ? "Microsoft" : "Yahoo"} sign-in isn't connected yet — use your email and password below, or a sign-in link.`);
      return;
    }
    window.location.assign(`${API_ROOT}/api/auth/${provider}/start`);
  }

  async function sendMagic(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/auth/magic-link", { email: email.trim() });
      toast.success(data.new_account
        ? "Check your inbox — the link creates your account, no form needed."
        : "Check your inbox for your sign-in link.");
      setMagicOpen(false); setEmail("");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Could not send the link");
    } finally { setBusy(false); }
  }

  const btn = "w-full flex items-center justify-center gap-2 py-3 rounded-full border border-[var(--line)] hover:border-white/25 hover:bg-white/5 transition-all text-sm";

  return (
    <div className="mt-8 space-y-2" data-testid="social-signin">
      <button data-testid={mode === "signin" ? "auth-google-login-btn" : "auth-google-register-btn"} onClick={googleAuth} className={btn}>
        <GoogleMark /> Continue with Google
      </button>
      <div className="grid grid-cols-2 gap-2">
        <button data-testid="auth-microsoft-btn" onClick={() => oauth("microsoft")} className={btn}>
          <MicrosoftMark /> Microsoft
        </button>
        <button data-testid="auth-yahoo-btn" onClick={() => oauth("yahoo")} className={btn}>
          <YahooMark /> Yahoo
        </button>
      </div>
      <p className="text-[11px] text-[var(--dim)] text-center">Microsoft covers Outlook, Hotmail and Live addresses.</p>

      {magicOpen ? (
        <form onSubmit={sendMagic} className="flex gap-2 pt-1" data-testid="magic-link-form">
          <div className="relative flex-1">
            <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--mut)]" />
            <input data-testid="magic-link-email-input" type="email" required value={email} autoComplete="email"
              onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com"
              className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-full pl-9 pr-3 py-2.5 text-sm font-mono focus:border-[var(--acc)] outline-none" />
          </div>
          <button data-testid="magic-link-send-btn" disabled={busy} type="submit"
            className="btn-primary text-sm !py-2.5 !px-4 flex items-center gap-2 disabled:opacity-60">
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Wand2 size={14} />} Send link
          </button>
        </form>
      ) : (
        <button data-testid="magic-link-open-btn" onClick={() => setMagicOpen(true)} className={btn}>
          <Wand2 size={15} /> {mode === "signin" ? "Email me a sign-in link" : "Sign up with an email link (no form)"}
        </button>
      )}
    </div>
  );
}
