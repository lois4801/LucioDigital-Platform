import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Upload, Loader2, Trash2, Pencil, Copy, Download, HardDrive, FileText, FileSpreadsheet, FileArchive, File as FileIcon, Film, Music, Search, DatabaseBackup, Lock, Globe2 } from "lucide-react";
import api from "@/lib/api";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const IMG = /^image\//;
const fmt = (b) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);
const iconFor = (ct = "") => ct.startsWith("video/") ? Film : ct.startsWith("audio/") ? Music
  : ct.includes("sheet") || ct.includes("excel") || ct.includes("csv") ? FileSpreadsheet
  : ct.includes("zip") ? FileArchive : ct.includes("pdf") || ct.startsWith("text/") || ct.includes("word") ? FileText : FileIcon;

export function StorageUsageBar({ usage, compact }) {
  if (!usage) return null;
  const hot = usage.percent > 85;
  return (
    <div data-testid="storage-usage" className={compact ? "" : "card-surface p-4"}>
      <div className="flex justify-between text-xs">
        <span className="text-[var(--mut)] flex items-center gap-1.5"><HardDrive size={12} className="text-[var(--acc)]" /> Storage · {usage.files} file{usage.files === 1 ? "" : "s"}</span>
        <span data-testid="storage-usage-text" className="font-mono">{fmt(usage.used_bytes)} / {fmt(usage.quota_bytes)}</span>
      </div>
      <div className="h-2 rounded-full bg-[var(--bg-2)] mt-2 overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${Math.max(1.5, usage.percent)}%`, background: hot ? "#F97316" : "var(--acc)" }} />
      </div>
      {hot && <div className="text-[11px] text-amber-300 mt-1.5">Nearly full — delete files to free space.</div>}
    </div>
  );
}

export default function FilesPanel({ appId }) {
  const [files, setFiles] = useState([]);
  const [usage, setUsage] = useState(null);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const inputRef = useRef(null);

  const load = () => api.get(`/apps/${appId}/files`).then(r => { setFiles(r.data.files); setUsage(r.data.usage); }).catch(() => {});
  useEffect(() => { load(); }, [appId]);

  async function upload(e) {
    const list = Array.from(e.target.files || []);
    e.target.value = "";
    if (!list.length) return;
    setBusy(true);
    for (const f of list) {
      try {
        const fd = new FormData(); fd.append("file", f);
        await api.post(`/apps/${appId}/files`, fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 180000 });
      } catch (err) { toast.error(`${f.name}: ${err.response?.data?.detail || "upload failed"}`); }
    }
    await load(); setBusy(false);
    toast.success(list.length === 1 ? "File uploaded" : `${list.length} files uploaded`);
  }

  async function rename(f) {
    const name = prompt("Rename file", f.original_filename);
    if (!name || name === f.original_filename) return;
    try { await api.patch(`/apps/${appId}/files/${f.file_id}`, { name }); load(); toast.success("Renamed"); }
    catch { toast.error("Rename failed"); }
  }

  async function togglePrivacy(f) {
    try {
      await api.patch(`/apps/${appId}/files/${f.file_id}/privacy`, { private: !f.private });
      load();
      toast.success(f.private ? "Public link enabled" : "File is private again");
    } catch { toast.error("Could not change sharing"); }
  }

  async function remove(f) {
    if (!confirm(`Delete “${f.original_filename}”? Links to it will stop working.`)) return;
    try { await api.delete(`/apps/${appId}/files/${f.file_id}`); load(); toast.success("Deleted"); }
    catch { toast.error("Delete failed"); }
  }

  async function dataExport() {
    setExporting(true);
    try {
      const res = await api.get(`/apps/${appId}/data-export`, { responseType: "blob", timeout: 300000 });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = `${appId}-data-export.zip`; a.click();
      URL.revokeObjectURL(url);
      toast.success("Data & media archive downloaded");
    } catch { toast.error("Export failed"); } finally { setExporting(false); }
  }

  const shown = files.filter(f => f.original_filename.toLowerCase().includes(q.toLowerCase()));

  return (
    <div data-testid="files-panel" className="space-y-5">
      <div className="grid lg:grid-cols-[1fr_320px] gap-5">
        <div className="card-surface p-5">
          <div className="overline">Media & file library</div>
          <p className="text-xs text-[var(--mut)] mt-1.5">Upload images, documents, sheets, audio or video for this client. New files are <span className="text-[var(--fg)]">private</span> — flip a file to Shared when you want a public link for pages, replies or the client.</p>
          <div className="flex flex-wrap items-center gap-2 mt-4">
            <input ref={inputRef} data-testid="files-input" type="file" multiple onChange={upload} className="hidden"
              accept=".png,.jpg,.jpeg,.webp,.gif,.svg,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.zip,.json,.mp4,.webm,.mp3,.wav" />
            <button data-testid="files-upload-btn" onClick={() => inputRef.current?.click()} disabled={busy}
              className="btn-primary text-sm flex items-center gap-2 disabled:opacity-50">{busy ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />} Upload files</button>
            <button data-testid="data-export-btn" onClick={dataExport} disabled={exporting}
              className="btn-ghost text-sm flex items-center gap-2 disabled:opacity-50">{exporting ? <Loader2 size={14} className="animate-spin" /> : <DatabaseBackup size={14} />} Download all data & media</button>
            <label className="relative ml-auto">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--dim)]" />
              <input data-testid="files-search" value={q} onChange={e => setQ(e.target.value)} placeholder="Search files…"
                className="bg-[var(--bg-2)] border border-[var(--line)] rounded-full pl-8 pr-3 py-2 text-xs outline-none focus:border-[var(--acc)] w-44" />
            </label>
          </div>
        </div>
        <StorageUsageBar usage={usage} />
      </div>

      {shown.length === 0 ? (
        <div data-testid="files-empty" className="card-surface p-10 text-center text-sm text-[var(--mut)]">
          {files.length === 0 ? "No files yet — upload logos, brand assets, quotes or contracts to keep them with this client." : "No files match that search."}
        </div>
      ) : (
        <div data-testid="files-grid" className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {shown.map(f => {
            const Icon = iconFor(f.content_type);
            const url = `${BACKEND}${f.url}`;
            const openUrl = f.private ? `${BACKEND}/api/apps/${appId}/files/${f.file_id}/download` : url;
            return (
              <div key={f.file_id} data-testid={`file-card-${f.file_id}`} className="card-surface overflow-hidden group">
                <a href={openUrl} target="_blank" rel="noreferrer" className="block h-32 bg-black/30 flex items-center justify-center overflow-hidden relative">
                  {IMG.test(f.content_type) && !f.private
                    ? <img src={url} alt={f.original_filename} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                    : <Icon size={30} className="text-[var(--acc)]" />}
                  <span data-testid={`file-privacy-badge-${f.file_id}`} className="absolute top-2 right-2 chip flex items-center gap-1" style={{ padding: "2px 7px" }}>
                    {f.private ? <><Lock size={9} /> Private</> : <><Globe2 size={9} /> Shared</>}
                  </span>
                </a>
                <div className="p-3">
                  <div className="text-xs font-medium truncate" title={f.original_filename}>{f.original_filename}</div>
                  <div className="text-[10px] font-mono text-[var(--dim)] mt-0.5">{fmt(f.size)} · {new Date(f.created_at).toLocaleDateString()}</div>
                  <div className="flex items-center gap-1 mt-2">
                    <button data-testid={`file-privacy-${f.file_id}`} title={f.private ? "Enable a public link" : "Make private again"} onClick={() => togglePrivacy(f)} className="w-7 h-7 rounded-lg hover:bg-white/8 flex items-center justify-center">{f.private ? <Lock size={12} /> : <Globe2 size={12} className="text-[var(--acc)]" />}</button>
                    <button data-testid={`file-copy-${f.file_id}`} title={f.private ? "Make it shared to get a public link" : "Copy link"} disabled={f.private} onClick={async () => { try { await navigator.clipboard.writeText(url); toast.success("Link copied"); } catch { toast.error("Copy failed — open the file to grab its link"); } }} className="w-7 h-7 rounded-lg hover:bg-white/8 flex items-center justify-center disabled:opacity-30"><Copy size={12} /></button>
                    <a data-testid={`file-download-${f.file_id}`} title="Download" href={openUrl} target="_blank" rel="noreferrer" className="w-7 h-7 rounded-lg hover:bg-white/8 flex items-center justify-center"><Download size={12} /></a>
                    <button data-testid={`file-rename-${f.file_id}`} title="Rename" onClick={() => rename(f)} className="w-7 h-7 rounded-lg hover:bg-white/8 flex items-center justify-center"><Pencil size={12} /></button>
                    <button data-testid={`file-delete-${f.file_id}`} title="Delete" onClick={() => remove(f)} className="w-7 h-7 rounded-lg hover:bg-white/8 flex items-center justify-center text-red-300 ml-auto"><Trash2 size={12} /></button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
