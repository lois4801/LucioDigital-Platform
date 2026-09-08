import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "@/lib/api";
import BlockPreview, { DesignCtx } from "@/components/builder/BlockPreview";
import EffectWrap from "@/components/builder/EffectWrap";
import CursorTrail from "@/components/CursorTrail";
import { useTenantCursorFX } from "@/components/CursorFX";
import ChatWidget from "@/components/ChatWidget";
import { themeVars, loadFonts, isV2 } from "@/lib/theme";
import { AnimatePresence, motion } from "framer-motion";
import MemberGate, { useMember } from "@/components/MemberGate";
import MemberAccount from "@/components/MemberAccount";
import Paywall from "@/components/Paywall";
import { LogOut } from "lucide-react";
import { Layers, Eye } from "lucide-react";

export default function PublicPreview() {
  const { token } = useParams();
  const embed = new URLSearchParams(window.location.search).get("embed") === "1";
  const [site, setSite] = useState(null);
  const [slug, setSlug] = useState("/");
  const [err, setErr] = useState(null);
  const [account, setAccount] = useState(false);
  const [hasPaid, setHasPaid] = useState(false);
  const member = useMember(token);
  useTenantCursorFX(site?.theme?.cursor === false ? "none" : site?.theme?.cursor_effect, site?.theme?.cursor_density ?? 1, site?.theme?.cursor_speed ?? 1);

  useEffect(() => {
    api.get(`/public/site/${token}`).then(r => { setSite(r.data); loadFonts(r.data.theme); }).catch(e => setErr(e.response?.data?.detail || "Preview unavailable"));
  }, [token]);
  useEffect(() => {
    if (!site) return;
    const k = "os_visitor"; let s = localStorage.getItem(k); if (!s) { s = "v_" + Math.random().toString(36).slice(2, 12); localStorage.setItem(k, s); }
    api.post(`/public/track/${token}`, { path: slug, event: "view", session: s, referrer: document.referrer }).catch(() => {});
  }, [site, slug, token]);

  if (err) return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 text-center px-6">
      <Eye size={28} className="text-[var(--mut)]" /><div className="font-display text-2xl">{err}</div>
      <Link to="/" className="btn-ghost text-sm">Back to OmniStack AI</Link>
    </div>
  );
  if (!site) return <div className="min-h-screen flex items-center justify-center"><div className="overline">Loading preview…</div></div>;

  const page = site.pages.find(p => p.slug === slug) || site.pages[0];
  const navbar = (page?.blocks || []).find(b => b.type === "navbar");
  const navigate = (href) => { if (href?.startsWith("/")) { setSlug(href); window.scrollTo(0, 0); } };

  const v2 = isV2(site.theme);
  const gated = !!(site.webapp?.converted && page?.protected && !member.user && !member.loading);
  const paywalled = !!(site.webapp?.paid?.enabled && page?.paid && !hasPaid);
  const submitLead = async (l) => {
    await api.post(`/public/contact/${token}`, l);
    if (site.webapp?.converted) {
      await api.post(`/site/${token}/submit`, {
        form_id: l.form_id, form_name: l.form_name, name: l.name, email: l.email || null,
        fields: { message: l.message, page: page?.slug || "/" },
      }, member.jwt ? { headers: { Authorization: `Bearer ${member.jwt}` } } : undefined).catch(() => { });
    }
  };
  return (
    <DesignCtx.Provider value={v2}>
    <div className={`min-h-screen ${v2 ? "dsv2" : ""} ${site.theme?.grain !== false ? "tgrain" : ""}`} data-testid="public-preview-page" style={{ ...themeVars(site.theme), background: "var(--tbg)", color: "var(--tfg)", fontFamily: "var(--tfb)" }}>
      {!embed && <div className="relative z-50 backdrop-blur-xl bg-[#0B0F17]/90 text-white border-b border-white/10 px-4 sm:px-5 py-2 flex flex-wrap items-center gap-y-2 justify-between text-xs">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: site.app.color }} />
          <span className="font-semibold truncate max-w-[120px] sm:max-w-none">{site.app.name}</span>
          <div className="flex gap-1 sm:ml-3 overflow-x-auto scrollbar-thin">
            {site.pages.map(p => <button key={p.page_id} data-testid={`preview-page-${p.slug.replace("/", "") || "home"}`} onClick={() => navigate(p.slug)} className={`px-2.5 py-1 rounded-full whitespace-nowrap ${page?.slug === p.slug ? "bg-white/15" : "text-white/60 hover:text-white"}`}>{p.name}</button>)}
          </div>
        </div>
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          {site.webapp?.converted && (member.user
            ? <>
              <button data-testid="member-account-link" onClick={() => setAccount(a => !a)} className="flex items-center gap-1.5 text-white/60 hover:text-white">{account ? "Site" : "My account"}</button>
              <button data-testid="member-signout" onClick={member.signOut} className="flex items-center gap-1.5 text-white/60 hover:text-white"><LogOut size={11} /> {member.user.name || "Sign out"}</button>
            </>
            : <span data-testid="member-status" className="chip">Members area</span>)}
          <span className="chip chip-handover"><Eye size={11} /> Preview</span>
          <Link to="/" className="flex items-center gap-1.5 text-white/60 hover:text-white"><Layers size={12} className="text-[var(--acc)]" /> <span className="hidden sm:inline">OmniStack AI</span></Link>
        </div>
      </div>}
      {navbar && <BlockPreview block={navbar} onNavigate={navigate} collections={site.collections || []} />}
      <AnimatePresence mode="wait">
        <motion.div key={page?.slug || "home"} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}>
          {account && member.user
            ? <MemberAccount token={token} jwt={member.jwt} onSignedOut={() => { member.signOut(); setAccount(false); }} onClose={() => setAccount(false)} />
            : gated
              ? <MemberGate token={token} pageName={page?.name} signupMode={site.webapp?.signup_mode} onSignedIn={member.signIn} />
              : paywalled
                ? <Paywall token={token} jwt={member.jwt} user={member.user} paid={site.webapp.paid} pageName={page?.name}
                    signupMode={site.webapp?.signup_mode} onSignedIn={member.signIn} onPaid={() => setHasPaid(true)} />
                : (page?.blocks || []).filter(b => b.type !== "navbar").map(b => (
                <EffectWrap key={b.id} v2={v2} effects={b.style?.effects} motionOn={site.theme.motion !== false}>
                  <BlockPreview block={b} onNavigate={navigate} collections={site.collections || []} onLead={submitLead} bookingMode={site.webapp?.booking_mode} siteToken={site.webapp?.converted ? token : null} />
                </EffectWrap>
              ))}
        </motion.div>
      </AnimatePresence>
      {site.theme.cursor !== false && <CursorTrail color={site.theme.primary} />}
      <ChatWidget token={token} brand={site.app.name} accent={site.theme.primary} light={site.theme.mode !== "dark"} />
    </div>
    </DesignCtx.Provider>
  );
}
