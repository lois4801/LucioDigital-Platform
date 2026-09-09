import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Github, Code2, Copy, Loader2, ExternalLink, Unplug } from "lucide-react";
import { Switch } from "@/components/ui/switch";

export function EmbedCard({ appDoc }) {
  const origin = process.env.REACT_APP_BACKEND_URL;
  const snippet = appDoc.preview_token ? `<script src="${origin}/api/public/embed.js" data-token="${appDoc.preview_token}" data-origin="${origin}"></script>` : null;
  return (
    <div data-testid="embed-card" className="card-surface p-6">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-[var(--acc)]/10 border border-[var(--acc)]/30 flex items-center justify-center"><Code2 size={18} className="text-[var(--acc)]" /></div>
        <div className="flex-1 min-w-0">
          <div className="overline">Chat widget embed</div>
          <h3 className="font-display text-xl font-semibold tracking-tight mt-1">One line adds the AI assistant to any site</h3>
          <p className="text-sm text-[var(--mut)] mt-2">Paste before <code>&lt;/body&gt;</code> on the client's exported or custom-domain site. Voice + text chat answers from this tenant's content; conversations land in the Inbox.</p>
          {snippet ? (
            <div className="mt-4 flex items-start gap-2 p-3 rounded-xl bg-[var(--bg-2)] border border-[var(--line)]">
              <code data-testid="embed-snippet" className="font-mono text-[11px] text-[var(--mut)] break-all flex-1">{snippet}</code>
              <button data-testid="embed-copy-btn" onClick={() => { navigator.clipboard.writeText(snippet); toast.success("Snippet copied"); }} className="w-8 h-8 rounded-full hover:bg-white/10 flex items-center justify-center shrink-0"><Copy size={13} /></button>
            </div>
          ) : <div className="mt-4 text-xs font-mono text-amber-300">Create a preview link first (below) — the embed uses the same token.</div>}
        </div>
      </div>
    </div>
  );
}

export function GithubCard({ appDoc, setAppDoc }) {
  const [gh, setGh] = useState(null);
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [repo, setRepo] = useState("");
  useEffect(() => { api.get("/settings/github").then(r => setGh(r.data)).catch(() => {}); }, []);

  async function connect() {
    setBusy(true);
    try { const { data } = await api.post("/settings/github", { token }); setGh(data); setToken(""); toast.success(`Connected as ${data.login}`); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not connect"); } finally { setBusy(false); }
  }
  async function disconnect() { await api.delete("/settings/github"); setGh({ connected: false }); }
  async function push() {
    setBusy(true);
    try { const { data } = await api.post(`/apps/${appDoc.app_id}/github/push`, { repo_name: repo || undefined, private: true }, { timeout: 180000 }); setAppDoc({ ...appDoc, github: data }); toast[data.status === "pushed" ? "success" : "info"](data.status === "pushed" ? `Pushed ${data.files} files` : "Push simulated (MOCKED) — connect a token to push for real"); }
    catch (e) { toast.error(e.response?.data?.detail || "Push failed"); } finally { setBusy(false); }
  }
  async function toggleAuto(v) { const { data } = await api.post(`/apps/${appDoc.app_id}/github/autosync`, { enabled: v }); setAppDoc(data); toast.success(v ? "Auto-sync on: every save pushes to GitHub" : "Auto-sync off"); }
  const g = appDoc.github;

  return (
    <div data-testid="github-card" className="card-surface p-6">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-[var(--acc)]/10 border border-[var(--acc)]/30 flex items-center justify-center"><Github size={18} className="text-[var(--acc)]" /></div>
        <div className="flex-1 min-w-0">
          <div className="overline flex items-center gap-2">GitHub Sync {gh && !gh.connected && <span className="chip chip-maint" style={{ padding: "2px 6px" }}>MOCKED until connected</span>}</div>
          <h3 className="font-display text-xl font-semibold tracking-tight mt-1">Push site + app source to a repo</h3>
          <p className="text-sm text-[var(--mut)] mt-2">Exports the full bundle (site/, app/ with schema.sql, mobile/) into a private repository. Turn on auto-sync to push on every save.</p>
          {gh?.connected ? (
            <div className="mt-3 flex items-center gap-2 text-xs font-mono">{gh.avatar && <img src={gh.avatar} alt="" className="w-5 h-5 rounded-full" />}<span className="text-[var(--acc)]">Connected as {gh.login}</span>
              <button data-testid="github-disconnect-btn" onClick={disconnect} className="ml-2 text-[var(--mut)] hover:text-white flex items-center gap-1"><Unplug size={11} /> disconnect</button></div>
          ) : (
            <div className="mt-4 flex gap-2">
              <input data-testid="github-token-input" type="password" value={token} onChange={e => setToken(e.target.value)} placeholder="GitHub Personal Access Token (repo scope)" className="flex-1 bg-[var(--bg-2)] border border-[var(--line)] rounded-full px-4 py-2 text-xs font-mono outline-none focus:border-[var(--acc)]" />
              <button data-testid="github-connect-btn" onClick={connect} disabled={busy || token.length < 20} className="btn-ghost text-sm !py-2 !px-4 disabled:opacity-50">Connect</button>
            </div>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <input data-testid="github-repo-input" value={repo} onChange={e => setRepo(e.target.value)} placeholder={appDoc.name.toLowerCase().replace(/\s+/g, "-")} className="bg-[var(--bg-2)] border border-[var(--line)] rounded-full px-4 py-2 text-xs font-mono outline-none w-56" />
            <button data-testid="github-push-btn" onClick={push} disabled={busy} className="btn-primary text-sm !py-2 !px-4 flex items-center gap-2">{busy ? <Loader2 size={13} className="animate-spin" /> : <Github size={13} />} Push to GitHub</button>
            <label className="ml-auto flex items-center gap-2 text-xs text-[var(--mut)]">Auto-sync on save <Switch data-testid="github-autosync-toggle" checked={!!appDoc.github_autosync} onCheckedChange={toggleAuto} /></label>
          </div>
          {g && <div data-testid="github-last-push" className={`mt-3 text-xs font-mono p-3 rounded-lg border ${g.status === "pushed" ? "border-[var(--acc)]/30 text-[var(--acc)] bg-[var(--acc)]/5" : "border-amber-500/30 text-amber-200 bg-amber-500/5"}`}>
            {g.status === "pushed" ? "✓" : "⚠︎"} {g.status.toUpperCase()} · {g.files} files · {g.repo} {g.commit && `@ ${g.commit}`} {g.status === "pushed" && <a href={g.repo} target="_blank" rel="noreferrer" className="inline-flex ml-1"><ExternalLink size={11} /></a>}
            {g.message && <div className="mt-1 opacity-80">{g.message}</div>}
          </div>}
        </div>
      </div>
    </div>
  );
}
