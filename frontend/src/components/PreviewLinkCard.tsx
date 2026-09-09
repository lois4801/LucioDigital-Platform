import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Link2, RefreshCw, Copy, ExternalLink } from "lucide-react";
import { Switch } from "@/components/ui/switch";

export default function PreviewLinkCard({ appDoc, setAppDoc }) {
  const [busy, setBusy] = useState(false);
  const url = appDoc.preview_token ? `${window.location.origin}/p/${appDoc.preview_token}` : null;

  async function regen() {
    setBusy(true);
    try { const { data } = await api.post(`/apps/${appDoc.app_id}/preview/regenerate`); setAppDoc(data); toast.success("New preview link issued — old link revoked"); }
    catch { toast.error("Failed"); } finally { setBusy(false); }
  }
  async function toggle() {
    const { data } = await api.post(`/apps/${appDoc.app_id}/preview/toggle`); setAppDoc(data);
  }

  return (
    <div data-testid="preview-link-card" className="card-surface p-6">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-[var(--acc)]/10 border border-[var(--acc)]/30 flex items-center justify-center"><Link2 size={18} className="text-[var(--acc)]" /></div>
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <div className="overline">Live preview link</div>
            <Switch data-testid="preview-enabled-toggle" checked={!!appDoc.preview_enabled} onCheckedChange={toggle} />
          </div>
          <h3 className="font-display text-xl font-semibold tracking-tight mt-1">Share a public, read-only preview</h3>
          <p className="text-sm text-[var(--mut)] mt-2">Partners and clients can open the current page without signing in. Regenerate to revoke the old link instantly.</p>
          {appDoc.preview_enabled && url ? (
            <div className="mt-4 flex items-center gap-2 p-2 pl-4 rounded-full bg-[var(--bg-2)] border border-[var(--line)]">
              <span data-testid="preview-url" className="font-mono text-xs flex-1 truncate">{url}</span>
              <button data-testid="preview-copy-btn" onClick={() => { navigator.clipboard.writeText(url); toast.success("Link copied"); }} className="w-8 h-8 rounded-full hover:bg-white/10 flex items-center justify-center"><Copy size={13} /></button>
              <a data-testid="preview-open-link" href={url} target="_blank" rel="noreferrer" className="w-8 h-8 rounded-full hover:bg-white/10 flex items-center justify-center"><ExternalLink size={13} /></a>
            </div>
          ) : <div className="mt-4 text-xs font-mono text-[var(--dim)]">Preview disabled.</div>}
          <button data-testid="preview-regenerate-btn" onClick={regen} disabled={busy} className="mt-3 btn-ghost text-sm !py-2 !px-4 flex items-center gap-2">
            <RefreshCw size={13} className={busy ? "animate-spin" : ""} /> {appDoc.preview_token ? "Regenerate link" : "Create link"}
          </button>
        </div>
      </div>
    </div>
  );
}
