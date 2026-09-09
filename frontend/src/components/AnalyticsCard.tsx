import { useEffect, useState } from "react";
import api from "@/lib/api";
import { BarChart3, Users, Eye, MessageSquare, Inbox, TrendingUp } from "lucide-react";
import { L } from "@/components/UiLabels";

export default function AnalyticsCard({ appId }) {
  const [a, setA] = useState(null);
  useEffect(() => { api.get(`/apps/${appId}/analytics?days=30`).then(r => setA(r.data)).catch(() => {}); }, [appId]);
  if (!a) return null;
  const max = Math.max(1, ...a.daily.map(d => d.views));
  const Stat = ({ icon: I, lk, label, value, testid }) => <div className="p-3 rounded-xl bg-[var(--bg-2)] border border-[var(--line)]"><div className="overline flex items-center gap-1.5"><I size={11} className="text-[var(--acc)]" /> <L k={lk} d={label} /></div><div data-testid={testid} className="font-display text-2xl font-bold mt-1">{value}</div></div>;
  return (
    <div data-testid="analytics-card" className="card-surface p-6 lg:col-span-2">
      <div className="flex items-center justify-between mb-4"><div><div className="overline flex items-center gap-2"><BarChart3 size={12} className="text-[var(--acc)]" /> <L k="analytics_heading" d="Site analytics · last 30 days" testid="label-analytics-heading" /></div><L k="analytics_subheading" d="Tracked from the live site, chat widget and contact forms." as="div" className="text-xs text-[var(--mut)] mt-1" /></div><span className="chip chip-active"><TrendingUp size={11} /> {a.conversion}% visitor → lead</span></div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Stat icon={Eye} lk="stat_page_views" label="Page views" value={a.views} testid="analytics-views" /><Stat icon={Users} lk="stat_visitors" label="Visitors" value={a.visitors} testid="analytics-visitors" />
        <Stat icon={MessageSquare} lk="stat_chat_convos" label="Chat convos" value={a.chat_conversations} testid="analytics-chats" /><Stat icon={MessageSquare} lk="stat_chat_messages" label="Chat messages" value={a.chat_messages} /><Stat icon={Inbox} lk="stat_leads" label="Leads" value={a.leads} testid="analytics-leads" />
      </div>
      <div className="grid md:grid-cols-[1fr_260px] gap-5 mt-5">
        <div><L k="analytics_daily_views" d="Daily views" as="div" className="overline mb-2" testid="label-daily-views" /><div className="h-24 flex items-end gap-1">{a.daily.length === 0 ? <div className="text-xs text-[var(--mut)]">No visits yet — share the live preview link.</div> : a.daily.map(d => <div key={d.day} title={`${d.day}: ${d.views}`} className="flex-1 rounded-t bg-gradient-to-t from-[var(--acc)]/40 to-[var(--acc)] min-h-[3px]" style={{ height: `${(d.views / max) * 100}%` }} />)}</div></div>
        <div><L k="analytics_top_pages" d="Top pages" as="div" className="overline mb-2" testid="label-top-pages" />{a.top_pages.length === 0 ? <div className="text-xs text-[var(--mut)]">—</div> : a.top_pages.map(t => <div key={t.path} data-testid="analytics-top-page" className="flex justify-between text-xs py-1 border-b border-[var(--line)] last:border-0"><span className="font-mono">{t.path}</span><span className="text-[var(--mut)]">{t.views}</span></div>)}</div>
      </div>
    </div>
  );
}
