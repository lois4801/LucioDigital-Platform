import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Mail, Loader2, Link2 } from "lucide-react";

export default function PortalInvite({ appId }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("viewer");
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState(null);
  async function send() {
    setBusy(true);
    try { const { data } = await api.post(`/apps/${appId}/portal/invite`, { email, role }); setLast(data); setEmail(""); toast.success(data.delivery === "sent" ? `Invite emailed to ${data.email}` : "Invite created — copy the magic link below"); }
    catch (e) { toast.error(e.response?.data?.detail || "Invite failed"); } finally { setBusy(false); }
  }
  return (
    <div data-testid="portal-invite-card" className="card-surface p-5 mb-5">
      <div className="overline flex items-center gap-2 mb-1"><Mail size={11} className="text-[var(--acc)]" /> Invite a client to their portal</div>
      <p className="text-xs text-[var(--mut)]">Sends a one-time magic link (valid 7 days) that signs them straight into <span className="font-mono">/portal</span>. Clients can view and request changes but cannot spend your AI credits.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <input data-testid="portal-invite-email-input" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="client@company.com" className="flex-1 min-w-[200px] bg-[var(--bg-2)] border border-[var(--line)] rounded-full px-4 py-2 text-sm outline-none focus:border-[var(--acc)]" />
        <select data-testid="portal-invite-role-select" value={role} onChange={e => setRole(e.target.value)} className="bg-[var(--bg-2)] border border-[var(--line)] rounded-full px-3 py-2 text-xs font-mono outline-none"><option value="viewer">viewer</option><option value="editor">editor</option></select>
        <button data-testid="portal-invite-send-btn" onClick={send} disabled={busy || !email.includes("@")} className="btn-primary text-sm !py-2 !px-4 flex items-center gap-2 disabled:opacity-50">{busy ? <Loader2 size={13} className="animate-spin" /> : <Mail size={13} />} Send invite</button>
      </div>
      {last && <div data-testid="portal-invite-result" className="mt-3 text-[11px] font-mono text-[var(--mut)] flex items-center gap-2 flex-wrap">✓ {last.email} · email {last.delivery}{last.delivery_detail && <span className="text-amber-300">({String(last.delivery_detail).slice(0, 80)})</span>}{last.magic_link && <><Link2 size={11} /><button onClick={() => { navigator.clipboard.writeText(last.magic_link); toast.success("Magic link copied"); }} className="text-[var(--acc)] underline">copy magic link</button></>}</div>}
    </div>
  );
}
