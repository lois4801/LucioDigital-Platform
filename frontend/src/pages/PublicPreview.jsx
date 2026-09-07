import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "@/lib/api";
import BlockPreview from "@/components/builder/BlockPreview";
import ChatWidget from "@/components/ChatWidget";
import { themeVars, loadFonts } from "@/lib/theme";
import { Layers, Eye } from "lucide-react";

export default function PublicPreview() {
  const { token } = useParams();
  const [site, setSite] = useState(null);
  const [slug, setSlug] = useState("/");
  const [err, setErr] = useState(null);

  useEffect(() => {
    api.get(`/public/site/${token}`).then(r => { setSite(r.data); loadFonts(r.data.theme); }).catch(e => setErr(e.response?.data?.detail || "Preview unavailable"));
  }, [token]);

  if (err) return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 text-center px-6">
      <Eye size={28} className="text-[var(--mut)]" /><div className="font-display text-2xl">{err}</div>
      <Link to="/" className="btn-ghost text-sm">Back to OmniStack AI</Link>
    </div>
  );
  if (!site) return <div className="min-h-screen flex items-center justify-center"><div className="overline">Loading preview…</div></div>;

  const page = site.pages.find(p => p.slug === slug) || site.pages[0];
  const navigate = (href) => { if (href?.startsWith("/")) { setSlug(href); window.scrollTo(0, 0); } };

  return (
    <div className="min-h-screen" data-testid="public-preview-page" style={{ ...themeVars(site.theme), background: "var(--tbg)", color: "var(--tfg)", fontFamily: "var(--tfb)" }}>
      <div className="sticky top-0 z-40 backdrop-blur-xl bg-[#0B0F17]/90 text-white border-b border-white/10 px-5 py-2 flex items-center justify-between text-xs">
        <div className="flex items-center gap-3">
          <span className="w-2 h-2 rounded-full" style={{ background: site.app.color }} />
          <span className="font-semibold">{site.app.name}</span>
          <div className="flex gap-1 ml-3">
            {site.pages.map(p => <button key={p.page_id} data-testid={`preview-page-${p.slug.replace("/", "") || "home"}`} onClick={() => navigate(p.slug)} className={`px-2.5 py-1 rounded-full ${page?.slug === p.slug ? "bg-white/15" : "text-white/60 hover:text-white"}`}>{p.name}</button>)}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="chip chip-handover"><Eye size={11} /> Preview</span>
          <Link to="/" className="flex items-center gap-1.5 text-white/60 hover:text-white"><Layers size={12} className="text-[var(--acc)]" /> OmniStack AI</Link>
        </div>
      </div>
      {page?.blocks.map(b => <BlockPreview key={b.id} block={b} onNavigate={navigate} collections={site.collections || []} onLead={async (l) => { await api.post(`/public/contact/${token}`, l); }} />)}
      <ChatWidget token={token} brand={site.app.name} accent={site.theme.primary} light={site.theme.mode !== "dark"} />
    </div>
  );
}
