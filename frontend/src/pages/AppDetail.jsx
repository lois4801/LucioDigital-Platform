import { PageSkeleton } from "@/components/PageTransition";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api, { API } from "@/lib/api";
import { toast } from "sonner";
import { ArrowLeft, ExternalLink, Trash2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import Builder from "@/components/builder/Builder";
import HandoffPanel from "@/components/HandoffPanel";
import ActivityLog from "@/components/ActivityLog";
import MembersPanel from "@/components/MembersPanel";
import OverviewPanel from "@/components/OverviewPanel";
import MediaStudio from "@/components/MediaStudio";
import BillingPanel from "@/components/BillingPanel";
import DomainPanel from "@/components/DomainPanel";
import BlueprintPanel from "@/components/BlueprintPanel";
import InboxPanel from "@/components/InboxPanel";
import WorkflowsPanel from "@/components/WorkflowsPanel";
import CmsPanel from "@/components/CmsPanel";

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "builder", label: "Site Mode" },
  { key: "cms", label: "CMS" },
  { key: "blueprint", label: "App Mode" },
  { key: "workflows", label: "Workflows" },
  { key: "inbox", label: "Inbox" },
  { key: "media", label: "AI Media" },
  { key: "billing", label: "Billing" },
  { key: "domain", label: "Domain" },
  { key: "handoff", label: "Handoff & Export" },
  { key: "activity", label: "Activity" },
  { key: "members", label: "Members" },
];

export default function AppDetail() {
  const { appId } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [appDoc, setAppDoc] = useState(null);
  const [tab, setTab] = useState("overview");
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, [appId]);

  async function load() {
    setLoading(true);
    try { const { data } = await api.get(`/apps/${appId}`); setAppDoc(data); }
    catch { toast.error("Failed to load app"); nav("/dashboard"); }
    finally { setLoading(false); }
  }

  async function patch(fields) {
    try {
      const { data } = await api.patch(`/apps/${appId}`, fields);
      setAppDoc(data);
      toast.success("Saved");
    } catch { toast.error("Save failed"); }
  }

  async function del() {
    if (!confirm(`Delete ${appDoc.name}? This is permanent.`)) return;
    try {
      await api.delete(`/apps/${appId}`);
      toast.success("Deleted");
      nav("/dashboard");
    } catch { toast.error("Delete failed"); }
  }

  if (loading || !appDoc) {
    return <PageSkeleton testid="app-skeleton" />;
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 backdrop-blur-xl bg-[var(--bg)]/85 border-b border-[var(--line)]">
        <div className="px-6 lg:px-10 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button data-testid="back-to-dashboard-btn" onClick={() => nav("/dashboard")}
              className="w-10 h-10 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-white/5">
              <ArrowLeft size={16} />
            </button>
            <div>
              <div className="overline">Tenant</div>
              <div className="font-display text-xl font-semibold tracking-tight flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: appDoc.color }} />
                {appDoc.name}
                <span data-testid="header-kind-chip" className={`chip ${appDoc.kind === "app" ? "chip-handover" : ""}`} style={{ padding: "2px 8px" }}>{appDoc.kind === "app" ? "App" : "Website"}</span>
                {appDoc.plan && <span data-testid="header-plan-chip" className="chip chip-active" style={{ padding: "2px 8px" }}>{appDoc.plan}</span>}
                {appDoc.custom_domain && <span data-testid="header-domain-chip" className={`chip ${appDoc.domain_status === "verified" ? "chip-active" : "chip-maint"}`} style={{ padding: "2px 8px" }}>{appDoc.custom_domain}</span>}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {appDoc.live_url && (
              <a data-testid="app-live-link" href={appDoc.live_url} target="_blank" rel="noopener noreferrer"
                className="btn-ghost flex items-center gap-2 text-sm">
                Live <ExternalLink size={13} />
              </a>
            )}
            <button data-testid="app-delete-btn" onClick={del}
              className="w-10 h-10 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-red-500/10 hover:border-red-500/40 hover:text-red-400">
              <Trash2 size={15} />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="px-6 lg:px-10 flex overflow-x-auto scrollbar-thin">
          {TABS.map((t) => (
            <button key={t.key} data-testid={`tab-${t.key}-btn`} onClick={() => setTab(t.key)}
              data-active={tab === t.key} className="tab-underline">
              {t.label}
            </button>
          ))}
        </div>
      </header>

      <main className="px-6 lg:px-10 py-8 fade-in">
        {tab === "overview" && <OverviewPanel appDoc={appDoc} patch={patch} />}
        {tab === "builder" && <Builder appId={appId} appDoc={appDoc} />}
        {tab === "blueprint" && <BlueprintPanel appId={appId} apiRoot={API} />}
        {tab === "cms" && <CmsPanel appId={appId} />}
        {tab === "workflows" && <WorkflowsPanel appId={appId} />}
        {tab === "inbox" && <InboxPanel appId={appId} />}
        {tab === "media" && <MediaStudio appId={appId} />}
        {tab === "billing" && <BillingPanel appDoc={appDoc} />}
        {tab === "domain" && <DomainPanel appDoc={appDoc} setAppDoc={setAppDoc} />}
        {tab === "handoff" && <HandoffPanel appDoc={appDoc} patch={patch} apiRoot={API} setAppDoc={setAppDoc} />}
        {tab === "activity" && <ActivityLog appId={appId} />}
        {tab === "members" && <MembersPanel appId={appId} currentUser={user} />}
      </main>
    </div>
  );
}
