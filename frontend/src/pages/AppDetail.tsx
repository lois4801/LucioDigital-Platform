import Logo from "@/components/Logo";
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
import VideoStudio from "@/components/VideoStudio";
import OverviewPanel from "@/components/OverviewPanel";
import MediaStudio from "@/components/MediaStudio";
import BillingPanel from "@/components/BillingPanel";
import DomainPanel from "@/components/DomainPanel";
import BlueprintPanel from "@/components/BlueprintPanel";
import InboxPanel from "@/components/InboxPanel";
import WorkflowsPanel from "@/components/WorkflowsPanel";
import CmsPanel from "@/components/CmsPanel";
import { UiLabelsProvider, L } from "@/components/UiLabels";
import { CursorFXPicker } from "@/components/CursorFX";
import FilesPanel from "@/components/FilesPanel";
import DataDestinationPanel from "@/components/DataDestinationPanel";
import { LocksProvider, MasterLockButton, LockStateBadge } from "@/components/locks/LockContext";
import ConvertToWebApp from "@/components/ConvertToWebApp";
import SubmissionsPanel from "@/components/SubmissionsPanel";
import BookingsCalendar from "@/components/BookingsCalendar";
import ProSettings from "@/components/ProSettings";
import CtaFormsPanel from "@/components/CtaFormsPanel";
import RolloutModal from "@/components/RolloutModal";
import SiteModePanel from "@/components/SiteModePanel";
import DevAgentPanel from "@/components/DevAgentPanel";
import DevAgentRuntimePanel from "@/components/DevAgentRuntimePanel";

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "dev-agent", label: "Dev Agent" },
  { key: "builder", label: "Site Mode" },
  { key: "cms", label: "CMS" },
  { key: "blueprint", label: "App Mode" },
  { key: "workflows", label: "Workflows" },
  { key: "inbox", label: "Inbox" },
  { key: "forms", label: "Forms" },
  { key: "bookings", label: "Bookings" },
  { key: "media", label: "AI Media" },
  { key: "videos", label: "Videos" },
  { key: "files", label: "Files" },
  { key: "data", label: "Data & Storage" },
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
  const [appDoc, setAppDoc] = useState<any>(null);
  const [tab, setTab] = useState("overview");
  const [loading, setLoading] = useState(true);
  const [rolloutOpen, setRolloutOpen] = useState(false);

  useEffect(() => { load(); }, [appId]);

  useEffect(() => {
    const quiet = async () => {
      try { const { data } = await api.get(`/apps/${appId}`); setAppDoc(data); } catch { /* transient */ }
    };
    const timer = setInterval(quiet, 8000);
    window.addEventListener("focus", quiet);
    return () => { clearInterval(timer); window.removeEventListener("focus", quiet); };
  }, [appId]);

  useEffect(() => { if (tab === "overview") api.get(`/apps/${appId}`).then(r => setAppDoc(r.data)).catch(() => {}); }, [tab, appId]);

  async function load() {
    setLoading(true);
    try { const { data } = await api.get(`/apps/${appId}`); setAppDoc(data); }
    catch { toast.error("Failed to load app"); nav("/dashboard"); }
    finally { setLoading(false); }
  }

  async function patch(fields: any) {
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
    <UiLabelsProvider appId={appId!}>
    <LocksProvider appId={appId!}>
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 backdrop-blur-xl bg-[var(--bg)]/85 border-b border-[var(--line)] w-full max-w-full" data-testid="builder-page-header">
        <div className="px-6 lg:px-10 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button data-testid="builder-logo-home-btn" onClick={() => nav("/dashboard")} title="Back to your dashboard"
              className="hidden sm:flex items-center cursor-pointer pr-3 mr-1 border-r border-[var(--line)]">
              <Logo variant="white" size={16} />
            </button>
            <button data-testid="back-to-dashboard-btn" onClick={() => nav("/dashboard")}
              className="w-10 h-10 rounded-full border border-[var(--line)] flex items-center justify-center hover:bg-white/5">
              <ArrowLeft size={16} />
            </button>
            <div>
              <L k="header_tenant_overline" d="Client" as="div" className="overline" testid="label-header-overline" />
              <div className="font-display text-xl font-semibold tracking-tight flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: appDoc.color }} />
                <span data-testid="label-client-name">{appDoc.name}</span>
                {appDoc.is_test_lab && <span data-testid="header-master-badge" className="chip chip-active inline-flex items-center gap-1" style={{ padding: "2px 8px" }}>INTERNAL TOOLS</span>}
                <span data-testid="header-kind-chip" className={`chip ${appDoc.kind === "app" ? "chip-handover" : ""}`} style={{ padding: "2px 8px" }}>{appDoc.kind === "app" ? "App" : "Website"}</span>
                {appDoc.plan && <span data-testid="header-plan-chip" className="chip chip-active" style={{ padding: "2px 8px" }}>{appDoc.plan}</span>}
                {appDoc.custom_domain && <span data-testid="header-domain-chip" className={`chip ${appDoc.domain_status === "verified" ? "chip-active" : "chip-maint"}`} style={{ padding: "2px 8px" }}>{appDoc.custom_domain}</span>}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ConvertToWebApp appId={appId!} appName={appDoc?.name} inline />
            <LockStateBadge />
            <MasterLockButton />
            <CursorFXPicker />
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
            <RolloutModal open={rolloutOpen} onClose={() => setRolloutOpen(false)} />
          </div>
        </div>

        <div className="px-6 lg:px-10 pr-6 lg:pr-10 flex tenant-scroll border-b border-[var(--line)]" data-testid="header-row-tabs">
          {TABS.map((t) => (
            <button key={t.key} data-testid={`tab-${t.key}-btn`} onClick={() => setTab(t.key)}
              data-active={tab === t.key} className="tab-underline shrink-0">
              <L k={`tab_${t.key}`} d={t.label} testid={`label-tab-${t.key}`} />
            </button>
          ))}
        </div>
      </header>

      <main className="px-6 lg:px-10 pr-6 lg:pr-10 py-8 fade-in w-full max-w-full" data-testid="app-main">
        {tab === "overview" && <OverviewPanel appDoc={appDoc} patch={patch} />}
        {tab === "dev-agent" && (
          <div className="space-y-10">
            <DevAgentPanel appId={appId!} appDoc={appDoc} />
            <DevAgentRuntimePanel appId={appId!} />
          </div>
        )}
        {tab === "builder" && (
          <div className="space-y-6">
            <SiteModePanel appId={appId!} appName={appDoc?.name || ""} appDoc={appDoc} />
            <Builder appId={appId!} appDoc={appDoc} user={user} />
          </div>
        )}
        {tab === "blueprint" && <BlueprintPanel appId={appId!} apiRoot={API} />}
        {tab === "cms" && <CmsPanel appId={appId!} />}
        {tab === "workflows" && <WorkflowsPanel appId={appId!} />}
        {tab === "inbox" && <InboxPanel appId={appId!} />}
        {tab === "forms" && <CtaFormsPanel appId={appId!} />}
        {tab === "media" && <MediaStudio appId={appId!} />}
        {tab === "videos" && <VideoStudio appId={appId!} appDoc={appDoc} />}
        {tab === "files" && <FilesPanel appId={appId!} />}
        {tab === "bookings" && (appDoc?.webapp?.converted
          ? <div className="space-y-8"><BookingsCalendar appId={appId!} token={appDoc.preview_token} /><ProSettings appId={appId!} /></div>
          : <div className="text-sm text-[var(--mut)]">Convert this site to a web app from Overview and bookings, the weekly digest and the paid members area appear here.</div>)}
        {tab === "data" && <div className="space-y-8"><SubmissionsPanel appId={appId!} /><DataDestinationPanel appId={appId!} /></div>}
        {tab === "billing" && <BillingPanel appDoc={appDoc} />}
        {tab === "domain" && <DomainPanel appDoc={appDoc} setAppDoc={setAppDoc} />}
        {tab === "handoff" && <HandoffPanel appDoc={appDoc} patch={patch} apiRoot={API} setAppDoc={setAppDoc} />}
        {tab === "activity" && <ActivityLog appId={appId!} />}
        {tab === "members" && <MembersPanel appId={appId!} currentUser={user} />}
      </main>
    </div>
    </LocksProvider>
    </UiLabelsProvider>
  );
}
