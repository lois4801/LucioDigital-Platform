import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, FileText } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import api from "@/lib/api";

/** Thumbnail sketch of a section set — bars stand in for the sections, in order. */
const SHAPE: Record<string, string> = {
  hero: "h-4", text: "h-2", features: "h-3", pricing: "h-3", stats: "h-1.5",
  testimonials: "h-2.5", team: "h-3", gallery: "h-3.5", faq: "h-2", contact: "h-2.5", cta: "h-2",
};

function Thumb({ blocks, accent }) {
  return (
    <div className="rounded-lg bg-[var(--bg-2)] border border-[var(--line)] p-2 flex flex-col gap-1" aria-hidden>
      {blocks.map((b: string, i: number) => (
        <div key={i} className={`${SHAPE[b] || "h-2"} rounded-sm`}
          style={{ background: i === 0 ? accent : `${accent}33` }} />
      ))}
    </div>
  );
}

/** Section Template picker — shown when a page is created or is still empty, and available at any
 *  time from the Page Manager to apply a set over the current content. */
export default function SectionPicker({ appId, pageId, accent = "#10B981", open, onClose, onApplied }) {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    if (!open || !pageId) return;
    setData(null);
    api.get(`/apps/${appId}/pages/${pageId}/section-sets`)
      .then(r => setData(r.data))
      .catch(() => toast.error("Could not load the section projects"));
  }, [open, pageId, appId]);

  async function apply(setId: string) {
    setBusy(setId);
    try {
      const { data: got } = await api.post(`/apps/${appId}/pages/${pageId}/apply-set`, { set_id: setId });
      toast.success(setId === "blank" ? "Started a blank page" : `${got.count} sections added, ready to edit`);
      onApplied?.(got);
      onClose();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not apply that section project");
    } finally { setBusy(""); }
  }

  return (
    <Dialog open={open} onOpenChange={v => !v && onClose()}>
      <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)] max-w-3xl max-h-[86vh] overflow-y-auto tenant-scroll"
        data-testid="section-picker">
        <DialogHeader>
          <DialogTitle className="font-display">Pick a section project</DialogTitle>
        </DialogHeader>
        {!data ? (
          <div className="py-8 text-sm text-[var(--mut)] flex items-center gap-2 justify-center">
            <Loader2 size={14} className="animate-spin" /> Loading projects…
          </div>
        ) : (
          <>
            <p className="text-xs text-[var(--mut)] -mt-2">
              Sets made for a <span className="text-[var(--acc)] font-semibold">{data.page_type}</span> page. Everything arrives in your own colours, accent and motion — nothing to style afterwards.
            </p>
            <div className="grid sm:grid-cols-2 gap-3 mt-1">
              {data.sets.map((s: any) => (
                <button key={s.id} data-testid={`section-set-${s.id}`} disabled={!!busy} onClick={() => apply(s.id)}
                  className="text-left rounded-xl border border-[var(--line)] p-3 hover:border-[var(--acc)] transition-colors disabled:opacity-50 relative">
                  {s.saved && (
                    <span className="absolute right-2 top-2 flex items-center gap-1.5">
                      <span className="chip !px-1.5 text-[9px]">Saved</span>
                      <span role="button" data-testid={`section-set-delete-${s.id}`}
                        onClick={async e => {
                          e.stopPropagation();
                          try { await api.delete(`/section-sets/${s.id}`); toast.success("Section set removed"); setData(d => ({ ...d, sets: d.sets.filter(x => x.id !== s.id) })); }
                          catch { toast.error("Could not remove that set"); }
                        }}
                        className="text-[var(--mut)] hover:text-red-400 text-[10px]">remove</span>
                    </span>
                  )}
                  <div className="flex gap-3">
                    <div className="w-16 shrink-0"><Thumb blocks={s.blocks} accent={accent} /></div>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold">{s.label}</div>
                      <div className="text-xs text-[var(--mut)] mt-1 leading-snug">{s.hint}</div>
                      <div className="text-[10px] font-mono text-[var(--dim)] mt-1.5 truncate">{s.blocks.join(" · ")}</div>
                    </div>
                  </div>
                  {busy === s.id && <div className="text-[11px] text-[var(--acc)] mt-2 flex items-center gap-1"><Loader2 size={10} className="animate-spin" /> Building the page…</div>}
                </button>
              ))}
            </div>
            <button data-testid="section-set-blank" disabled={!!busy} onClick={() => apply("blank")}
              className="mt-2 btn-ghost text-sm !py-2 flex items-center gap-2 justify-center disabled:opacity-50">
              <FileText size={13} /> Start blank instead
            </button>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
