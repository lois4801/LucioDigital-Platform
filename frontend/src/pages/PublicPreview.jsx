import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "@/lib/api";
import BlockPreview from "@/components/builder/BlockPreview";
import { Layers, Eye } from "lucide-react";

export default function PublicPreview() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api.get(`/public/preview/${token}`).then(r => setData(r.data)).catch(e => setErr(e.response?.data?.detail || "Preview unavailable"));
  }, [token]);

  if (err) return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 text-center px-6">
      <Eye size={28} className="text-[var(--mut)]" />
      <div className="font-display text-2xl">{err}</div>
      <Link to="/" className="btn-ghost text-sm">Back to Lucio/Studio</Link>
    </div>
  );
  if (!data) return <div className="min-h-screen flex items-center justify-center"><div className="overline">Loading preview…</div></div>;

  return (
    <div className="min-h-screen" data-testid="public-preview-page">
      <div className="sticky top-0 z-30 backdrop-blur-xl bg-[var(--bg)]/85 border-b border-[var(--line)] px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: data.app.color }} />
          <div className="font-display font-semibold">{data.app.name}</div>
          <span className="chip">{data.app.industry}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="chip chip-handover"><Eye size={11} /> Read-only preview</span>
          <Link to="/" className="flex items-center gap-2 text-xs text-[var(--mut)] hover:text-white"><Layers size={13} className="text-[var(--acc)]" /> Built with Lucio/Studio</Link>
        </div>
      </div>
      <div className="max-w-6xl mx-auto my-8 card-surface !p-0 overflow-hidden">
        {data.blocks.map(b => <BlockPreview key={b.id} block={b} />)}
      </div>
    </div>
  );
}
