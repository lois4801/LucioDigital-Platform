import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { UserPlus, X, Crown } from "lucide-react";
import PortalInvite from "@/components/PortalInvite";

const ROLES = ["viewer", "editor", "admin"];

export default function MembersPanel({ appId, currentUser }) {
  const [members, setMembers] = useState([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("editor");
  const [busy, setBusy] = useState(false);

  useEffect(() => { load(); }, [appId]);

  async function load() {
    try { const { data } = await api.get(`/apps/${appId}/members`); setMembers(data); } catch {}
  }
  async function invite() {
    if (!email) return;
    setBusy(true);
    try {
      await api.post(`/apps/${appId}/members`, { email, role });
      setEmail("");
      toast.success(`Invited ${email}`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Invite failed"); }
    finally { setBusy(false); }
  }
  async function remove(membership_id) {
    if (membership_id === "owner") return;
    try { await api.delete(`/apps/${appId}/members/${membership_id}`); load(); toast.success("Removed"); } catch {}
  }

  return (
    <div className="max-w-3xl space-y-6">
      <PortalInvite appId={appId} />
      <div className="card-surface p-5">
        <div className="overline mb-3 flex items-center gap-2"><UserPlus size={12} /> Invite member</div>
        <div className="flex flex-col md:flex-row gap-3">
          <input data-testid="member-invite-email-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="teammate@company.com"
            className="flex-1 bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm font-mono outline-none focus:border-[var(--acc)]" />
          <select data-testid="member-invite-role-select" value={role} onChange={(e) => setRole(e.target.value)}
            className="bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm font-mono outline-none">
            {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
          <button data-testid="member-invite-submit-btn" onClick={invite} disabled={busy} className="btn-primary text-sm !py-2 !px-4 disabled:opacity-50">
            {busy ? "Inviting…" : "Invite"}
          </button>
        </div>
      </div>

      <div className="card-surface divide-y divide-[var(--line)]">
        {members.map((m) => (
          <div key={m.membership_id} data-testid={`member-row-${m.email}`} className="flex items-center gap-3 px-4 py-3">
            <div className="w-9 h-9 rounded-full bg-[var(--acc)]/15 text-[var(--acc)] text-sm font-bold flex items-center justify-center">
              {(m.name || m.email).charAt(0).toUpperCase()}
            </div>
            <div className="flex-1">
              <div className="text-sm font-display">{m.name || m.email}</div>
              <div className="text-xs text-[var(--mut)] font-mono">{m.email}</div>
            </div>
            <span className={`chip ${m.role === "owner" ? "chip-handover" : ""}`}>
              {m.role === "owner" && <Crown size={11} className="mr-1" />}
              {m.role}
            </span>
            {m.role !== "owner" && (
              <button data-testid={`member-remove-${m.membership_id}`} onClick={() => remove(m.membership_id)}
                className="w-8 h-8 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-red-500/10 hover:border-red-500/40 hover:text-red-400">
                <X size={13} />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
