import { useEffect, useState } from "react";
import axios from "axios";
import { User, Loader2, KeyRound, CalendarCheck, Trash2 } from "lucide-react";

const BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;
const err = (e) => {
  const d = e.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map(x => x?.msg || JSON.stringify(x)).join(" ");
  return e.message || "Something went wrong";
};

export default function MemberAccount({ token, jwt, onSignedOut, onClose }) {
  const [profile, setProfile] = useState(null);
  const [subs, setSubs] = useState([]);
  const [form, setForm] = useState({ name: "", phone: "", notes: "" });
  const [pw, setPw] = useState({ current_password: "", password: "" });
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const http = axios.create({ baseURL: `${BASE}/site/${token}`, headers: { Authorization: `Bearer ${jwt}` } });

  useEffect(() => {
    http.get("/me").then(r => { setProfile(r.data); setForm({ name: r.data.user.name || "", phone: r.data.user.phone || "", notes: r.data.user.notes || "" }); }).catch(e => setMsg(err(e)));
    http.get("/me/submissions").then(r => setSubs(r.data.submissions)).catch(() => { });
  }, [token, jwt]);

  async function save() {
    setBusy(true); setMsg("");
    try { const { data } = await http.patch("/me", form); setProfile({ ...profile, user: data.user }); setMsg("Details saved."); }
    catch (e) { setMsg(err(e)); } finally { setBusy(false); }
  }
  async function changePw() {
    setBusy(true); setMsg("");
    try { await http.post("/me/password", pw); setPw({ current_password: "", password: "" }); setMsg("Password updated."); }
    catch (e) { setMsg(err(e)); } finally { setBusy(false); }
  }
  async function removeAccount() {
    if (!window.confirm("Delete your account for good? Your submissions stay with the business but are no longer linked to you.")) return;
    try { await http.delete("/me"); onSignedOut(); } catch (e) { setMsg(err(e)); }
  }

  if (!profile) return <section className="min-h-[60svh] grid place-items-center"><Loader2 className="animate-spin text-[var(--tp)]" /></section>;

  const Field = ({ label, ...p }) => (
    <label className="block"><span className="text-xs text-[var(--tmut)]">{label}</span>
      <input {...p} className="mt-1 w-full rounded-[calc(var(--tr)/1.6)] border border-[var(--tbd)] bg-[var(--tsf)] px-3.5 py-2.5 text-sm outline-none focus:border-[var(--tp)]" /></label>
  );

  return (
    <section data-testid="member-account" className="px-6 sm:px-8 lg:px-12 py-16 max-w-4xl mx-auto space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <User size={18} className="text-[var(--tp)]" />
        <h1 className="font-[var(--tfh)] t-h2 font-bold flex-1">My account</h1>
        <button data-testid="member-account-close" onClick={onClose} className="tbtn rounded-full border border-[var(--tbd)] px-4 py-2 text-xs font-semibold">Back to the site</button>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="tcard rounded-[var(--tr)] border border-[var(--tbd)] p-5 space-y-3">
          <div className="text-xs uppercase tracking-wide text-[var(--tmut)]">Your details</div>
          <div className="text-sm">{profile.user.email}</div>
          <Field label="Name" data-testid="account-name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
          <Field label="Phone" data-testid="account-phone" value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} />
          <label className="block"><span className="text-xs text-[var(--tmut)]">Notes for the team</span>
            <textarea data-testid="account-notes" rows={3} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })}
              className="mt-1 w-full rounded-[calc(var(--tr)/1.6)] border border-[var(--tbd)] bg-[var(--tsf)] px-3.5 py-2.5 text-sm outline-none focus:border-[var(--tp)] resize-none" /></label>
          <button data-testid="account-save" onClick={save} disabled={busy} className="tbtn tbtn-solid w-full rounded-full bg-[var(--tp)] px-6 py-2.5 text-sm font-semibold text-white disabled:opacity-50">Save details</button>
        </div>

        <div className="tcard rounded-[var(--tr)] border border-[var(--tbd)] p-5 space-y-3">
          <div className="text-xs uppercase tracking-wide text-[var(--tmut)] flex items-center gap-2"><KeyRound size={12} /> Password</div>
          <Field label="Current password" data-testid="account-current-pw" type="password" value={pw.current_password} onChange={e => setPw({ ...pw, current_password: e.target.value })} />
          <Field label="New password" data-testid="account-new-pw" type="password" value={pw.password} onChange={e => setPw({ ...pw, password: e.target.value })} />
          <button data-testid="account-change-pw" onClick={changePw} disabled={busy} className="tbtn w-full rounded-full border border-[var(--tbd)] px-6 py-2.5 text-sm font-semibold disabled:opacity-50">Change password</button>
          {profile.allow_self_delete && (
            <button data-testid="account-delete" onClick={removeAccount} className="w-full text-xs text-red-400 hover:text-red-300 flex items-center justify-center gap-1.5 pt-1"><Trash2 size={12} /> Delete my account</button>
          )}
        </div>
      </div>

      {msg && <div data-testid="account-msg" className="text-sm text-[var(--tp)]">{msg}</div>}

      <div className="space-y-2">
        <div className="text-xs uppercase tracking-wide text-[var(--tmut)]">Your submissions</div>
        {subs.length === 0 && <div className="text-sm text-[var(--tmut)]">Nothing submitted yet.</div>}
        {subs.map(s => (
          <div key={s.submission_id} data-testid="account-submission-row" className="tcard rounded-[var(--tr)] border border-[var(--tbd)] p-4 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">{s.form_name}</span>
              <span className="rounded-full border border-[var(--tbd)] px-2 py-0.5 text-[10px] uppercase tracking-wide">{s.status}</span>
              {s.booking && <span data-testid="account-booking-chip" className="flex items-center gap-1.5 rounded-full border border-[var(--tp)]/50 text-[var(--tp)] px-2 py-0.5 text-[10px]"><CalendarCheck size={10} /> {s.booking.date} {s.booking.slot || ""} · {s.booking.status}</span>}
              <span className="ml-auto text-[10px] text-[var(--tmut)]">{new Date(s.created_at).toLocaleString()}</span>
            </div>
            <div className="mt-1.5 text-xs text-[var(--tmut)] space-y-0.5">
              {Object.entries(s.fields || {}).map(([k, v]) => <div key={k}>{k}: {v}</div>)}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
