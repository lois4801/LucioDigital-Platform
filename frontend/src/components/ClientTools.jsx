import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { UserPlus, ArrowLeftRight, Copy, Trash2, RefreshCw, ExternalLink } from "lucide-react";

/** Client panel invites + the public before/after share link, for one tenant. */
export default function ClientTools({ appId, appName, converted }) {
  const [invites, setInvites] = useState([]);
  const [email, setEmail] = useState("");
  const [link, setLink] = useState(null);
  const [beforeUrl, setBeforeUrl] = useState("");
  const [busy, setBusy] = useState("");

  const loadInvites = () => api.get(`/apps/${appId}/webapp/invites`).then(r => setInvites(r.data.invites)).catch(() => { });
  const loadLink = () => api.get(`/apps/${appId}/compare-link`).then(r => { setLink(r.data.link); setBeforeUrl(r.data.link?.before_url || r.data.suggested_before_url || ""); }).catch(() => { });
  useEffect(() => { if (converted) loadInvites(); loadLink(); }, [appId, converted]);

  async function invite() {
    setBusy("invite");
    try { const { data } = await api.post(`/apps/${appId}/webapp/invite-client`, { email }); setEmail(""); loadInvites(); toast.success(`Invite emailed to ${data.invite.email}`); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not send the invite"); } finally { setBusy(""); }
  }
  async function revoke(inv) {
    try { await api.delete(`/apps/${appId}/webapp/invites/${inv.invite_id}`); loadInvites(); } catch (e) { toast.error("Could not revoke"); }
  }
  async function makeLink() {
    setBusy("link");
    try { const { data } = await api.post(`/apps/${appId}/compare-link`, { before_url: beforeUrl }); setLink(data); toast.success("Before/after link ready"); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not create the link"); } finally { setBusy(""); }
  }
  async function removeLink() {
    try { await api.delete(`/apps/${appId}/compare-link`); setLink(null); } catch { toast.error("Could not remove"); }
  }
  const copy = (path) => { navigator.clipboard.writeText(`${window.location.origin}${path}`); toast.success("Link copied"); };

  return (
    <div className="space-y-3">
      {converted && (
        <div data-testid="client-invite-card" className="rounded-xl border border-[var(--line)] p-4 space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            <UserPlus size={15} className="text-[var(--acc)]" />
            <div className="text-xs flex-1 min-w-[220px]">
              <div className="font-semibold">Invite your client to their panel</div>
              <div className="text-[var(--mut)]">They get one link, set a password and manage their own submissions, bookings and content.</div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <input data-testid="client-invite-email" value={email} onChange={e => setEmail(e.target.value)} placeholder="client@company.com"
              className="flex-1 min-w-[200px] bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm outline-none focus:border-[var(--acc)]" />
            <button data-testid="client-invite-btn" onClick={invite} disabled={!email || busy === "invite"} className="btn-primary text-sm !py-2 !px-4 disabled:opacity-50">{busy === "invite" ? "Sending…" : "Send invite"}</button>
          </div>
          {invites.map(i => (
            <div key={i.invite_id} data-testid="client-invite-row" className="flex flex-wrap items-center gap-2 text-xs border-t border-[var(--line)] pt-2">
              <span className="font-mono">{i.email}</span>
              <span className={`chip ${i.state === "accepted" ? "chip-active" : i.state === "sent" ? "" : "chip-maint"}`}>{i.state}</span>
              <span className="text-[10px] text-[var(--dim)]">{new Date(i.created_at).toLocaleDateString()}</span>
              <div className="ml-auto flex gap-2">
                {i.state !== "accepted" && <button data-testid={`invite-resend-${i.invite_id}`} onClick={() => { setEmail(i.email); invite(); }} className="btn-ghost !py-1 !px-2.5 text-[10px] flex items-center gap-1"><RefreshCw size={10} /> Resend</button>}
                {i.state === "sent" && <button data-testid={`invite-revoke-${i.invite_id}`} onClick={() => revoke(i)} className="btn-ghost !py-1 !px-2.5 text-[10px]">Revoke</button>}
              </div>
            </div>
          ))}
        </div>
      )}

      <div data-testid="compare-link-card" className="rounded-xl border border-[var(--line)] p-4 space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <ArrowLeftRight size={15} className="text-[var(--acc)]" />
          <div className="text-xs flex-1 min-w-[220px]">
            <div className="font-semibold">Before / after share link</div>
            <div className="text-[var(--mut)]">Shows the prospect's current site beside this rebuild, with a “start with this rebuild” form that lands in your Inbox.</div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <input data-testid="compare-before-url" value={beforeUrl} onChange={e => setBeforeUrl(e.target.value)} placeholder="their-current-site.com"
            className="flex-1 min-w-[200px] bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm font-mono outline-none focus:border-[var(--acc)]" />
          <button data-testid="compare-create-btn" onClick={makeLink} disabled={busy === "link"} className="btn-primary text-sm !py-2 !px-4 disabled:opacity-50">{busy === "link" ? "Capturing…" : link ? "Update link" : "Create link"}</button>
        </div>
        {link && (
          <div className="flex flex-wrap items-center gap-2 text-xs border-t border-[var(--line)] pt-2">
            <span data-testid="compare-link-url" className="font-mono truncate max-w-[240px]">/compare/{link.code}</span>
            <span className="chip">{link.views || 0} view(s)</span>
            <div className="ml-auto flex gap-2">
              <button data-testid="compare-copy-btn" onClick={() => copy(`/compare/${link.code}`)} className="btn-ghost !py-1 !px-2.5 text-[10px] flex items-center gap-1"><Copy size={10} /> Copy</button>
              <a data-testid="compare-open-btn" href={`/compare/${link.code}`} target="_blank" rel="noreferrer" className="btn-ghost !py-1 !px-2.5 text-[10px] flex items-center gap-1"><ExternalLink size={10} /> Open</a>
              <button data-testid="compare-delete-btn" onClick={removeLink} className="btn-ghost !py-1 !px-2.5 text-[10px] flex items-center gap-1"><Trash2 size={10} /> Remove</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
