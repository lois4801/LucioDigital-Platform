import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Rocket, Check, ExternalLink, Loader2, Lock, Users, Database, Bell, Code2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const MODES = [
  ["open", "Open registration", "Anyone can create an account and sign in right away"],
  ["approval", "Admin approval", "New accounts wait until an admin approves them"],
  ["invite", "Invite only", "Only the admin can create accounts, by email invite"],
];

export default function ConvertToWebApp({ appId, appName, inline }) {
  const [state, setState] = useState(null);
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState("open");
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState(null);

  const load = () => api.get(`/apps/${appId}/webapp`).then(r => setState(r.data)).catch(() => { });
  useEffect(() => { load(); }, [appId]);

  async function convert() {
    setBusy(true);
    try {
      const { data } = await api.post(`/apps/${appId}/convert-to-webapp`, { signup_mode: mode });
      setSummary({ ...data.summary, url: data.admin_panel_url, already: data.already });
      toast.success(data.already ? "This site is already a web app" : "Conversion complete — your design and content are unchanged");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Conversion failed"); }
    finally { setBusy(false); }
  }

  async function setPageAccess(p) {
    try {
      await api.post(`/apps/${appId}/webapp/pages/${p.page_id}/access`, { protected: !p.protected });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not change page access"); }
  }

  async function saveMode(m, extra = {}) {
    setMode(m);
    try { await api.patch(`/apps/${appId}/webapp/settings`, { signup_mode: m, ...extra }); toast.success("Web app settings updated"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not update"); }
  }

  const converted = state?.converted;
  const panel = state?.admin_panel_url;

  if (inline) {
    return (
      <>
        <button data-testid="convert-webapp-header-btn" onClick={() => setOpen(true)}
          className={`flex items-center gap-2 rounded-full border px-4 py-2 text-xs font-semibold transition-colors ${converted
            ? "border-emerald-400/50 bg-emerald-400/10 text-emerald-300 hover:bg-emerald-400/20"
            : "border-[var(--line)] text-[var(--mut)] hover:text-white hover:border-white/40"}`}>
          {converted ? <Check size={13} /> : <Rocket size={13} />} {converted ? "Web app" : "Convert to Web App"}
        </button>
        <Panel {...{ open, setOpen, state, converted, panel, mode: state?.signup_mode || mode, saveMode, convert, busy, summary, setPageAccess, appName }} />
      </>
    );
  }

  return (
    <div data-testid="convert-webapp-card" className={`rounded-xl border p-4 ${converted ? "border-emerald-400/30 bg-emerald-400/5" : "border-[var(--acc)]/40 bg-[var(--acc)]/5"}`}>
      <div className="flex flex-wrap items-center gap-3">
        {converted ? <Check size={15} className="text-emerald-400" /> : <Rocket size={15} className="text-[var(--acc)]" />}
        <div className="flex-1 min-w-[240px] text-xs">
          <div className="font-semibold">{converted ? "This site is a full web app" : "Convert to Web App"}</div>
          <div className="text-[var(--mut)]">
            {converted
              ? `${state?.counts?.users || 0} account(s), ${state?.counts?.submissions || 0} submission(s). Sign-ups: ${state?.signup_mode}.`
              : "Add visitor accounts, a live database, an admin panel and a real-time API in one pass. Your design, copy and branding stay exactly as they are."}
          </div>
        </div>
        {converted && panel && <a data-testid="open-admin-panel-link" href={panel} target="_blank" rel="noreferrer" className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-1.5"><ExternalLink size={13} /> Admin panel</a>}
        <button data-testid="convert-webapp-btn" onClick={() => setOpen(true)} className="btn-primary text-sm !py-2 !px-4">{converted ? "Manage web app" : "Convert to Web App"}</button>
      </div>
      <Panel {...{ open, setOpen, state, converted, panel, mode: state?.signup_mode || mode, saveMode, convert, busy, summary, setPageAccess, appName }} />
    </div>
  );
}

function Panel({ open, setOpen, state, converted, panel, mode, saveMode, convert, busy, summary, setPageAccess, appName }) {  const s = summary || state?.summary;
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)] max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><Rocket size={16} className="text-[var(--acc)]" /> {converted ? `${appName} — web app` : `Convert ${appName} to a web app`}</DialogTitle></DialogHeader>

        {!converted && (
          <>
            <p className="text-sm text-[var(--mut)]">One automated pass adds everything below. Nothing about the current design, copy or branding changes.</p>
            <ul className="text-xs space-y-1.5 text-[var(--mut)]">
              <li className="flex gap-2"><Users size={13} className="text-[var(--acc)] mt-0.5" /> Visitor sign-in, registration and password reset</li>
              <li className="flex gap-2"><Lock size={13} className="text-[var(--acc)] mt-0.5" /> Members-only pages (Home, About, Services and Contact stay public)</li>
              <li className="flex gap-2"><Database size={13} className="text-[var(--acc)] mt-0.5" /> Forms saved to the database and repeated sections turned into editable content</li>
              <li className="flex gap-2"><Code2 size={13} className="text-[var(--acc)] mt-0.5" /> Real-time API + a private admin panel with two roles</li>
              <li className="flex gap-2"><Bell size={13} className="text-[var(--acc)] mt-0.5" /> Confirmation email to everyone who submits a form</li>
            </ul>
          </>
        )}

        <div>
          <div className="overline mb-2">Who can sign up</div>
          <div className="space-y-1.5">
            {MODES.map(([k, label, hint]) => (
              <button key={k} data-testid={`signup-mode-${k}`} onClick={() => saveMode(k)}
                className={`w-full text-left px-3 py-2 rounded-xl border text-xs ${mode === k ? "border-[var(--acc)]/50 bg-[var(--acc)]/10" : "border-[var(--line)] hover:border-white/30"}`}>
                <div className="font-semibold">{label}</div><div className="text-[var(--mut)]">{hint}</div>
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="overline mb-2">Booking requests</div>
          <div className="flex gap-1.5">
            {[["period", "Morning / Afternoon / Evening"], ["slots", "Fixed time slots"]].map(([k, label]) => (
              <button key={k} data-testid={`booking-mode-${k}`} onClick={() => saveMode(mode, { booking_mode: k })}
                className={`flex-1 px-3 py-2 rounded-xl border text-xs ${(state?.booking_mode || "period") === k ? "border-[var(--acc)]/50 bg-[var(--acc)]/10" : "border-[var(--line)] hover:border-white/30"}`}>{label}</button>
            ))}
          </div>
          <label data-testid="self-delete-toggle" className="flex items-center gap-2 text-xs mt-2.5 cursor-pointer">
            <input type="checkbox" data-testid="self-delete-checkbox" checked={!!state?.allow_self_delete} onChange={e => saveMode(mode, { allow_self_delete: e.target.checked })} className="accent-[var(--acc)]" />
            Let members delete their own account
          </label>
        </div>

        {!converted && <button data-testid="run-conversion-btn" onClick={convert} disabled={busy} className="btn-primary w-full disabled:opacity-50">{busy ? <span className="flex items-center justify-center gap-2"><Loader2 size={14} className="animate-spin" /> Converting…</span> : "Run the conversion"}</button>}

        {s && (
          <div data-testid="conversion-summary" className="space-y-2 text-xs">
            <div className="overline">What was added</div>
            <Row label="Authentication" value={s.auth} />
            <Row label="Roles" value={(s.roles || []).join(" · ")} />
            <Row label="Members-only pages" value={(s.protected_pages || []).join(", ") || "none yet"} />
            <Row label="Database-driven sections" value={`${s.sections_bound || 0} section(s) → ${(s.collections || []).join(", ") || "no repeated sections found"}`} />
            <Row label="Forms connected" value={`${(s.forms_connected || []).length} form(s)`} />
            <Row label="API base" value={s.api_base} mono />
            <Row label="Emails" value={s.emails} />
            {panel && <a data-testid="summary-admin-panel-link" href={panel} target="_blank" rel="noreferrer" className="btn-primary w-full mt-1 flex items-center justify-center gap-2"><ExternalLink size={13} /> Open the admin panel</a>}
          </div>
        )}

        {converted && (
          <div>
            <div className="overline mb-2">Page access</div>
            <div className="space-y-1">
              {(state?.pages || []).map(p => (
                <div key={p.page_id} className="flex items-center gap-2 text-xs px-3 py-2 rounded-lg border border-[var(--line)]">
                  <span className="flex-1 truncate">{p.name} <span className="font-mono text-[10px] text-[var(--dim)]">{p.slug}</span></span>
                  <button data-testid={`page-access-${p.slug.replace("/", "") || "home"}`} onClick={() => setPageAccess(p)}
                    className={`px-2.5 py-1 rounded-full border text-[10px] font-semibold ${p.protected ? "border-amber-400/50 text-amber-300" : "border-[var(--line)] text-[var(--mut)]"}`}>
                    {p.protected ? "Members only" : "Public"}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

const Row = ({ label, value, mono }) => (
  <div className="flex gap-3 py-1.5 border-b border-[var(--line)] last:border-0">
    <span className="w-40 shrink-0 text-[var(--dim)]">{label}</span>
    <span className={`flex-1 ${mono ? "font-mono text-[11px]" : ""}`}>{value}</span>
  </div>
);
