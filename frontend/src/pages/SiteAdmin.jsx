import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Inbox, Users, Layers, BarChart3, LogOut, Loader2, Check, Trash2, Plus, Shield } from "lucide-react";

const BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;
const KEY = (t) => `site_admin_token_${t}`;

const err = (e) => {
  const d = e.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map(x => x?.msg || JSON.stringify(x)).join(" ");
  return e.message || "Something went wrong";
};

export default function SiteAdmin() {
  const { token } = useParams();
  const [params] = useSearchParams();
  const resetToken = params.get("reset");
  const [jwtToken, setJwtToken] = useState(() => localStorage.getItem(KEY(token)) || "");
  const [summary, setSummary] = useState(null);
  const [tab, setTab] = useState("submissions");
  const [loading, setLoading] = useState(true);

  const http = useMemo(() => axios.create({
    baseURL: `${BASE}/site/${token}`,
    withCredentials: true,
    headers: jwtToken ? { Authorization: `Bearer ${jwtToken}` } : {},
  }), [token, jwtToken]);

  const loadSummary = () => http.get("/admin/summary").then(r => { setSummary(r.data); setLoading(false); }).catch(() => { setSummary(null); setLoading(false); });
  useEffect(() => { loadSummary(); }, [http]);

  function signOut() { localStorage.removeItem(KEY(token)); setJwtToken(""); setSummary(null); }

  if (loading) return <div className="min-h-screen grid place-items-center bg-[var(--bg)] text-[var(--fg)]"><Loader2 className="animate-spin" /></div>;
  if (!summary) return <SignIn token={token} resetToken={resetToken} onToken={(t) => { localStorage.setItem(KEY(token), t); setJwtToken(t); setLoading(true); }} />;

  const TABS = [["submissions", "Submissions", Inbox], ["users", "Users", Users], ["content", "Content", Layers], ["analytics", "Analytics", BarChart3]];
  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--fg)]" data-testid="site-admin-page">
      <header className="sticky top-0 z-30 backdrop-blur-xl bg-[var(--bg)]/85 border-b border-[var(--line)] px-5 py-3 flex flex-wrap items-center gap-3">
        <Shield size={16} className="text-[var(--acc)]" />
        <div className="min-w-0">
          <div className="font-display font-bold truncate" data-testid="site-admin-title">{summary.site.name} — admin</div>
          <div className="text-[11px] text-[var(--mut)] truncate">{summary.me.email} · {summary.me.role}{summary.me.agency ? " (agency)" : ""}</div>
        </div>
        <div className="ml-auto flex items-center gap-3 text-xs">
          <span className="chip chip-active">{summary.totals.new_submissions} new</span>
          <button data-testid="site-admin-signout" onClick={signOut} className="btn-ghost !py-1.5 !px-3 flex items-center gap-1.5"><LogOut size={12} /> Sign out</button>
        </div>
      </header>

      <div className="px-5 pt-5 grid grid-cols-2 lg:grid-cols-5 gap-3">
        <Stat label="Submissions" value={summary.totals.submissions} />
        <Stat label="New" value={summary.totals.new_submissions} />
        <Stat label="Accounts" value={summary.totals.users} />
        <Stat label="Awaiting approval" value={summary.totals.pending_users} />
        <Stat label="Visits (30d)" value={summary.totals.visits_30d} />
      </div>

      <nav className="px-5 mt-6 flex gap-1 border-b border-[var(--line)] overflow-x-auto">
        {TABS.map(([k, label, Icon]) => (
          <button key={k} data-testid={`site-admin-tab-${k}`} onClick={() => setTab(k)}
            className={`px-4 py-2.5 text-sm flex items-center gap-2 border-b-2 whitespace-nowrap ${tab === k ? "border-[var(--acc)] text-white" : "border-transparent text-[var(--mut)] hover:text-white"}`}>
            <Icon size={13} /> {label}
          </button>
        ))}
      </nav>

      <main className="p-5 max-w-6xl">
        {tab === "submissions" && <Submissions http={http} onChange={loadSummary} />}
        {tab === "users" && <SiteUsers http={http} onChange={loadSummary} />}
        {tab === "content" && <Content http={http} />}
        {tab === "analytics" && <Analytics summary={summary} />}
      </main>
    </div>
  );
}

const Stat = ({ label, value }) => (
  <div className="card-surface p-4"><div className="text-[10px] uppercase tracking-wide text-[var(--dim)]">{label}</div><div className="font-display text-2xl font-bold mt-1">{value}</div></div>
);

function SignIn({ token, resetToken, onToken }) {
  const [view, setView] = useState(resetToken ? "reset" : "login");
  const [f, setF] = useState({ email: "", password: "", name: "" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const post = (path, body) => axios.post(`${BASE}/site/${token}${path}`, body);

  async function go() {
    setBusy(true); setMsg("");
    try {
      if (view === "login") { const { data } = await post("/auth/login", { email: f.email, password: f.password }); onToken(data.token); }
      else if (view === "reset") { const { data } = await post("/auth/reset", { token: resetToken, password: f.password }); onToken(data.token); }
      else if (view === "forgot") { await post("/auth/forgot", { email: f.email }); setMsg("If that email has an account here, a reset link is on its way."); }
    } catch (e) { setMsg(err(e)); }
    finally { setBusy(false); }
  }

  return (
    <div className="min-h-screen grid place-items-center bg-[var(--bg)] text-[var(--fg)] px-5" data-testid="site-admin-signin">
      <div className="card-surface p-7 w-full max-w-sm space-y-3">
        <div className="flex items-center gap-2"><Shield size={16} className="text-[var(--acc)]" /><span className="font-display font-bold">Site admin</span></div>
        <p className="text-xs text-[var(--mut)]">{view === "reset" ? "Choose a new password to finish." : view === "forgot" ? "We'll email you a reset link." : "Sign in with your site admin account, or open this panel while signed in to your agency dashboard."}</p>
        {view !== "reset" && <input data-testid="site-admin-email" type="email" value={f.email} onChange={e => setF({ ...f, email: e.target.value })} placeholder="you@company.com" className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]" />}
        {view !== "forgot" && <input data-testid="site-admin-password" type="password" value={f.password} onChange={e => setF({ ...f, password: e.target.value })} placeholder="Password" className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]" />}
        {msg && <div data-testid="site-admin-msg" className="text-xs text-amber-300">{msg}</div>}
        <button data-testid="site-admin-submit" onClick={go} disabled={busy} className="btn-primary w-full disabled:opacity-50">{busy ? "Working…" : view === "login" ? "Sign in" : view === "reset" ? "Set password" : "Send reset link"}</button>
        <div className="flex justify-between text-[11px] text-[var(--mut)]">
          {view !== "login" ? <button onClick={() => setView("login")}>Back to sign in</button> : <button data-testid="site-admin-forgot" onClick={() => setView("forgot")}>Forgot password?</button>}
        </div>
      </div>
    </div>
  );
}

function Submissions({ http, onChange }) {
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState("");
  const load = () => http.get("/admin/submissions", { params: { q } }).then(r => setRows(r.data.submissions)).catch(e => toast.error(err(e)));
  useEffect(() => { load(); }, [q]);
  async function setStatus(s, status) {
    try { await http.patch(`/admin/submissions/${s.submission_id}`, { status }); load(); onChange(); } catch (e) { toast.error(err(e)); }
  }
  return (
    <div className="space-y-3" data-testid="site-admin-submissions">
      <input data-testid="submissions-search" value={q} onChange={e => setQ(e.target.value)} placeholder="Search name, email or form…" className="w-full max-w-sm bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm outline-none focus:border-[var(--acc)]" />
      {rows.length === 0 && <div className="text-sm text-[var(--mut)]">No submissions yet.</div>}
      {rows.map(s => (
        <div key={s.submission_id} data-testid="submission-row" className="card-surface p-4">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-semibold">{s.name || "Anonymous"}</span>
            <span className="text-[var(--mut)] text-xs">{s.email}</span>
            <span className="chip">{s.form_name}</span>
            {s.page && <span className="font-mono text-[10px] text-[var(--dim)]">{s.page}</span>}
            <span className={`chip ${s.status === "new" ? "chip-active" : ""}`}>{s.status}</span>
            <span className="ml-auto text-[10px] text-[var(--dim)]">{new Date(s.created_at).toLocaleString()}</span>
          </div>
          <div className="mt-2 text-xs text-[var(--mut)] space-y-0.5">
            {Object.entries(s.fields || {}).map(([k, v]) => <div key={k}><span className="text-[var(--dim)]">{k}:</span> {v}</div>)}
          </div>
          <div className="mt-3 flex gap-2">
            <button data-testid={`submission-handled-${s.submission_id}`} onClick={() => setStatus(s, "handled")} className="btn-ghost !py-1.5 !px-3 text-[11px] flex items-center gap-1.5"><Check size={11} /> Mark handled</button>
            <button onClick={() => setStatus(s, "archived")} className="btn-ghost !py-1.5 !px-3 text-[11px]">Archive</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function SiteUsers({ http, onChange }) {
  const [rows, setRows] = useState([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("user");
  const load = () => http.get("/admin/users").then(r => setRows(r.data.users)).catch(e => toast.error(err(e)));
  useEffect(() => { load(); }, []);
  async function patch(u, body) { try { await http.patch(`/admin/users/${u.site_user_id}`, body); load(); onChange(); } catch (e) { toast.error(err(e)); } }
  async function invite() {
    try { await http.post("/admin/users/invite", { email, role }); setEmail(""); toast.success("Invitation sent"); load(); onChange(); }
    catch (e) { toast.error(err(e)); }
  }
  return (
    <div className="space-y-3" data-testid="site-admin-users">
      <div className="card-surface p-4 flex flex-wrap gap-2 items-center">
        <input data-testid="invite-email" value={email} onChange={e => setEmail(e.target.value)} placeholder="invite@client.com" className="flex-1 min-w-[200px] bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm outline-none focus:border-[var(--acc)]" />
        <select data-testid="invite-role" value={role} onChange={e => setRole(e.target.value)} className="bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm"><option value="user">Standard user</option><option value="admin">Admin</option></select>
        <button data-testid="invite-btn" onClick={invite} className="btn-primary text-sm !py-2 !px-4 flex items-center gap-1.5"><Plus size={13} /> Invite</button>
      </div>
      {rows.map(u => (
        <div key={u.site_user_id} data-testid="site-user-row" className="card-surface p-4 flex flex-wrap items-center gap-2 text-sm">
          <span className="font-semibold">{u.name}</span>
          <span className="text-xs text-[var(--mut)]">{u.email}</span>
          <span className={`chip ${u.role === "admin" ? "chip-active" : ""}`}>{u.role}</span>
          <span className={`chip ${u.status === "active" ? "" : "chip-maint"}`}>{u.status}</span>
          <div className="ml-auto flex gap-2">
            {u.status !== "active" && <button data-testid={`approve-${u.site_user_id}`} onClick={() => patch(u, { status: "active" })} className="btn-ghost !py-1.5 !px-3 text-[11px]">Approve</button>}
            {u.status === "active" && <button data-testid={`suspend-${u.site_user_id}`} onClick={() => patch(u, { status: "suspended" })} className="btn-ghost !py-1.5 !px-3 text-[11px]">Suspend</button>}
            <button data-testid={`role-${u.site_user_id}`} onClick={() => patch(u, { role: u.role === "admin" ? "user" : "admin" })} className="btn-ghost !py-1.5 !px-3 text-[11px]">{u.role === "admin" ? "Make user" : "Make admin"}</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function Content({ http }) {
  const [cols, setCols] = useState([]);
  const [draft, setDraft] = useState({});
  const load = () => http.get("/admin/collections").then(r => setCols(r.data.collections)).catch(e => toast.error(err(e)));
  useEffect(() => { load(); }, []);
  async function save(it) {
    try { await http.put(`/admin/items/${it.item_id}`, { title: it.title, excerpt: it.excerpt, body: it.body || "", cover: it.cover || "", published: it.published !== false, fields: it.fields || {} }); toast.success("Saved — the site updates instantly"); load(); }
    catch (e) { toast.error(err(e)); }
  }
  async function add(c) {
    const title = draft[c.slug];
    if (!title) return;
    try { await http.post(`/admin/collections/${c.slug}/items`, { title, excerpt: "", published: true, fields: {} }); setDraft({ ...draft, [c.slug]: "" }); load(); }
    catch (e) { toast.error(err(e)); }
  }
  async function del(it) {
    if (!window.confirm(`Delete “${it.title}”?`)) return;
    try { await http.delete(`/admin/items/${it.item_id}`); load(); } catch (e) { toast.error(err(e)); }
  }
  return (
    <div className="space-y-5" data-testid="site-admin-content">
      {cols.length === 0 && <div className="text-sm text-[var(--mut)]">No collections yet.</div>}
      {cols.map(c => (
        <div key={c.collection_id} className="card-surface p-4 space-y-2">
          <div className="flex items-center gap-2"><span className="font-display font-bold">{c.name}</span><span className="font-mono text-[10px] text-[var(--dim)]">/{c.slug}</span><span className="chip ml-auto">{c.items.length}</span></div>
          {c.items.map(it => (
            <div key={it.item_id} data-testid="content-item-row" className="flex flex-wrap gap-2 items-center border-t border-[var(--line)] pt-2">
              <input data-testid={`content-title-${it.item_id}`} defaultValue={it.title} onBlur={e => { if (e.target.value !== it.title) save({ ...it, title: e.target.value }); }} className="flex-1 min-w-[160px] bg-transparent border border-transparent hover:border-[var(--line)] focus:border-[var(--acc)] rounded-lg px-2 py-1.5 text-sm outline-none" />
              <input defaultValue={it.excerpt} placeholder="Description" onBlur={e => { if (e.target.value !== it.excerpt) save({ ...it, excerpt: e.target.value }); }} className="flex-[2] min-w-[200px] bg-transparent border border-transparent hover:border-[var(--line)] focus:border-[var(--acc)] rounded-lg px-2 py-1.5 text-xs text-[var(--mut)] outline-none" />
              <button onClick={() => save({ ...it, published: !(it.published !== false) })} className={`chip ${it.published !== false ? "chip-active" : ""}`}>{it.published !== false ? "live" : "hidden"}</button>
              <button data-testid={`content-delete-${it.item_id}`} onClick={() => del(it)} className="text-[var(--mut)] hover:text-red-400"><Trash2 size={13} /></button>
            </div>
          ))}
          <div className="flex gap-2 pt-2 border-t border-[var(--line)]">
            <input data-testid={`content-new-${c.slug}`} value={draft[c.slug] || ""} onChange={e => setDraft({ ...draft, [c.slug]: e.target.value })} placeholder={`New ${c.name.toLowerCase()} item`} className="flex-1 bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm outline-none focus:border-[var(--acc)]" />
            <button data-testid={`content-add-${c.slug}`} onClick={() => add(c)} className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-1.5"><Plus size={13} /> Add</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function Analytics({ summary }) {
  const Bars = ({ data, label }) => {
    const max = Math.max(1, ...data.map(d => d.count));
    return (
      <div className="card-surface p-4">
        <div className="text-[10px] uppercase tracking-wide text-[var(--dim)] mb-3">{label}</div>
        {data.length === 0 ? <div className="text-sm text-[var(--mut)]">Nothing in the last 30 days yet.</div> : (
          <div className="flex items-end gap-1.5 h-32">
            {data.map(d => <div key={d.day} title={`${d.day}: ${d.count}`} data-testid={`bar-${d.day}`} className="flex-1 min-h-[6px] bg-[var(--acc)] hover:brightness-125 rounded-t transition-all" style={{ height: `${Math.max(8, (d.count / max) * 100)}%` }} />)}
          </div>
        )}
        {data.length > 0 && <div className="mt-2 text-[10px] text-[var(--dim)]">{data.reduce((a, d) => a + d.count, 0)} total · peak {max} in a day</div>}
      </div>
    );
  };
  return (
    <div className="space-y-4" data-testid="site-admin-analytics">
      <Bars data={summary.submissions_daily} label="Form submissions · last 30 days" />
      <Bars data={summary.signups_daily} label="New accounts · last 30 days" />
    </div>
  );
}
