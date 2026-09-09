import { useRef, useState } from "react";
import { toast } from "sonner";
import { ImagePlus, Loader2, Trash2 } from "lucide-react";
import api from "@/lib/api";

const abs = (u) => (u?.startsWith("/api/") ? `${process.env.REACT_APP_BACKEND_URL}${u}` : u);

export function LogoUpload({ appId, logo, onChange }) {
  const ref = useRef(null);
  const [busy, setBusy] = useState(false);
  async function upload(file) {
    if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    setBusy(true);
    try { const { data } = await api.post(`/apps/${appId}/brand/logo`, fd, { headers: { "Content-Type": "multipart/form-data" } }); onChange(data.logo); toast.success(`Logo applied to ${data.pages_updated} page${data.pages_updated === 1 ? "" : "s"} — navbar, footer and exports`); }
    catch (e) { toast.error(e.response?.data?.detail || "Upload failed"); } finally { setBusy(false); if (ref.current) ref.current.value = ""; }
  }
  async function remove() {
    setBusy(true);
    try { await api.delete(`/apps/${appId}/brand/logo`); onChange(null); toast.success("Logo removed"); } catch { toast.error("Remove failed"); } finally { setBusy(false); }
  }
  return (
    <div className="flex items-center gap-2" data-testid="logo-upload">
      <input ref={ref} type="file" accept=".png,.jpg,.jpeg,.svg,.webp,.gif" className="hidden" data-testid="logo-file-input" onChange={e => upload(e.target.files?.[0])} />
      {logo ? <img data-testid="logo-current" src={abs(logo)} alt="logo" className="h-7 w-auto max-w-[96px] object-contain rounded bg-white/5 px-1" /> : null}
      <button data-testid="logo-upload-btn" onClick={() => ref.current?.click()} disabled={busy} className="btn-ghost text-sm !py-2 !px-4 flex items-center gap-2">{busy ? <Loader2 size={14} className="animate-spin" /> : <ImagePlus size={14} />} {logo ? "Replace logo" : "Upload logo"}</button>
      {logo && <button data-testid="logo-remove-btn" onClick={remove} disabled={busy} className="p-2 rounded-lg text-[var(--dim)] hover:text-red-400 hover:bg-red-400/10" title="Remove logo"><Trash2 size={14} /></button>}
    </div>
  );
}
