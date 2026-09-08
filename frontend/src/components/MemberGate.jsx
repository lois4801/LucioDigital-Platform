import { useEffect, useState } from "react";
import axios from "axios";
import { Lock, Loader2 } from "lucide-react";

const BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const memberKey = (t) => `site_member_token_${t}`;

const err = (e) => {
  const d = e.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map(x => x?.msg || JSON.stringify(x)).join(" ");
  return e.message || "Something went wrong";
};

export function useMember(token) {
  const [state, setState] = useState({ loading: true, user: null, jwt: localStorage.getItem(memberKey(token)) || "" });
  useEffect(() => {
    const jwt = localStorage.getItem(memberKey(token)) || "";
    if (!jwt) { setState({ loading: false, user: null, jwt: "" }); return; }
    axios.get(`${BASE}/site/${token}/auth/me`, { headers: { Authorization: `Bearer ${jwt}` } })
      .then(r => setState({ loading: false, user: r.data.user, jwt }))
      .catch(() => { localStorage.removeItem(memberKey(token)); setState({ loading: false, user: null, jwt: "" }); });
  }, [token]);
  const signIn = (jwt, user) => { localStorage.setItem(memberKey(token), jwt); setState({ loading: false, user, jwt }); };
  const signOut = () => { localStorage.removeItem(memberKey(token)); setState({ loading: false, user: null, jwt: "" }); };
  return { ...state, signIn, signOut };
}

/** Sign-in / register / reset wall shown in place of a members-only page. Uses tenant theme vars. */
export default function MemberGate({ token, pageName, signupMode = "open", onSignedIn }) {
  const [view, setView] = useState("login");
  const [f, setF] = useState({ email: "", password: "", name: "" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function go() {
    setBusy(true); setMsg("");
    try {
      if (view === "login") {
        const { data } = await axios.post(`${BASE}/site/${token}/auth/login`, { email: f.email, password: f.password });
        onSignedIn(data.token, data.user);
      } else if (view === "register") {
        const { data } = await axios.post(`${BASE}/site/${token}/auth/register`, f);
        if (data.pending) setMsg(data.message);
        else onSignedIn(data.token, data.user);
      } else {
        await axios.post(`${BASE}/site/${token}/auth/forgot`, { email: f.email });
        setMsg("If that email has an account here, a reset link is on its way.");
      }
    } catch (e) { setMsg(err(e)); }
    finally { setBusy(false); }
  }

  const Input = (props) => (
    <input {...props} className="w-full rounded-[calc(var(--tr)/1.6)] border border-[var(--tbd)] bg-[var(--tsf)] px-3.5 py-3 text-sm outline-none focus:border-[var(--tp)]" />
  );

  return (
    <section data-testid="member-gate" className="min-h-[70svh] flex items-center justify-center px-6 py-20">
      <div className="w-full max-w-sm rounded-[var(--tr)] border border-[var(--tbd)] tcard p-7 space-y-3">
        <div className="flex items-center gap-2 text-[var(--tp)]"><Lock size={15} /><span className="font-[var(--tfh)] font-bold text-[var(--tfg)]">Members only</span></div>
        <p className="text-sm text-[var(--tmut)]">
          {view === "register" ? "Create your account to continue." : view === "forgot" ? "We'll email you a reset link." : `Sign in to view ${pageName || "this page"}.`}
        </p>
        {view === "register" && <Input data-testid="member-name" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} placeholder="Your name" />}
        <Input data-testid="member-email" type="email" value={f.email} onChange={e => setF({ ...f, email: e.target.value })} placeholder="you@email.com" />
        {view !== "forgot" && <Input data-testid="member-password" type="password" value={f.password} onChange={e => setF({ ...f, password: e.target.value })} placeholder="Password" />}
        {msg && <div data-testid="member-msg" className="text-xs text-[var(--tp)]">{msg}</div>}
        <button data-testid="member-submit" onClick={go} disabled={busy}
          className="tbtn tbtn-solid w-full rounded-full bg-[var(--tp)] px-6 py-3 text-sm font-semibold text-white disabled:opacity-50">
          {busy ? <Loader2 size={14} className="animate-spin mx-auto" /> : view === "login" ? "Sign in" : view === "register" ? "Create account" : "Send reset link"}
        </button>
        <div className="flex justify-between text-[11px] text-[var(--tmut)]">
          {view === "login" ? (
            <>
              {signupMode !== "invite" ? <button data-testid="member-to-register" onClick={() => { setView("register"); setMsg(""); }} className="tlink">Create an account</button> : <span>Invite only</span>}
              <button data-testid="member-to-forgot" onClick={() => { setView("forgot"); setMsg(""); }} className="tlink">Forgot password?</button>
            </>
          ) : <button data-testid="member-to-login" onClick={() => { setView("login"); setMsg(""); }} className="tlink">Back to sign in</button>}
        </div>
      </div>
    </section>
  );
}
