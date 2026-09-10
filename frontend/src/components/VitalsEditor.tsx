import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Loader2, RotateCcw, Upload, Download, Plus, Trash2 } from "lucide-react";
import api from "@/lib/api";
import { LiveChart } from "@/components/editorial/IndustryVitals";

/** Live figures editor — the numbers, labels and charts shown in the site's "at a glance" section.
 *  Scoped to one client. Clients can drop in a two-column Excel/CSV sheet to replace the figures. */
export default function VitalsEditor({ appId, accent = "#10B981" }) {
  const [v, setV] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [drop, setDrop] = useState("");
  const fileRef = useRef<any>(null);
  const targetRef = useRef("series");

  useEffect(() => {
    if (!appId) return;
    api.get(`/apps/${appId}/vitals`).then(r => setV(r.data)).catch(() => toast.error("Could not load the figures"));
  }, [appId]);

  const set = (patch: any) => setV((s: any) => ({ ...s, ...patch }));

  async function save() {
    setBusy(true);
    try {
      const { data } = await api.put(`/apps/${appId}/vitals`, {
        title: v.title, metrics: v.metrics,
        series_label: v.series_label, labels: v.labels, series: v.series.map(Number),
        series2_label: v.series2_label, labels2: v.labels2, series2: v.series2.map(Number),
        source_label: v.source_label || "", source_label2: v.source_label2 || "",
      });
      setV((s: any) => ({ ...s, ...data }));
      toast.success("Figures saved — the live site is already showing them");
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not save the figures");
    } finally { setBusy(false); }
  }

  async function reset() {
    setBusy(true);
    try {
      const { data } = await api.post(`/apps/${appId}/vitals/reset`);
      setV((s: any) => ({ ...s, ...data }));
      toast.success("Demo figures restored");
    } catch { toast.error("Could not restore the demo figures"); }
    finally { setBusy(false); }
  }

  async function upload(file: any, target = "series") {
    if (!file) return;
    setBusy(true);
    const fd = new FormData(); fd.append("file", file);
    try {
      const { data } = await api.post(`/apps/${appId}/vitals/import?target=${target}`, fd,
        { headers: { "Content-Type": "multipart/form-data" } });
      setV((s: any) => ({ ...s, ...data }));
      toast.success(`Imported ${data.points} figures from ${file.name}${data.charts > 1 ? " — both charts built" : ""}`);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not read that spreadsheet");
    } finally { setBusy(false); setDrop(""); }
  }

  function sample() {
    const csv = "Label,Chart 1,Chart 2\nJan,280,42\nFeb,305,48\nMar,340,55\nApr,372,61\nMay,410,68\nJun,468,74\n";
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a"); a.href = url; a.download = "figures-template.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  function rowSet(which: "1" | "2", i: number, key: "label" | "value", val: string) {
    const lk = which === "1" ? "labels" : "labels2", sk = which === "1" ? "series" : "series2";
    setV((s: any) => {
      const labels = [...(s[lk] || [])], series = [...(s[sk] || [])];
      if (key === "label") labels[i] = val; else series[i] = val === "" ? 0 : Number(val);
      return { ...s, [lk]: labels, [sk]: series };
    });
  }
  function rowAdd(which: "1" | "2") {
    const lk = which === "1" ? "labels" : "labels2", sk = which === "1" ? "series" : "series2";
    setV((s: any) => ({ ...s, [lk]: [...(s[lk] || []), "New"], [sk]: [...(s[sk] || []), 0] }));
  }
  function rowDel(which: "1" | "2", i: number) {
    const lk = which === "1" ? "labels" : "labels2", sk = which === "1" ? "series" : "series2";
    setV((s: any) => ({ ...s, [lk]: (s[lk] || []).filter((_: any, j: number) => j !== i), [sk]: (s[sk] || []).filter((_: any, j: number) => j !== i) }));
  }

  if (!v) return (
    <div className="py-4 text-sm text-[var(--mut)] flex items-center gap-2" data-testid="vitals-editor-loading">
      <Loader2 size={14} className="animate-spin" /> Loading the live figures…
    </div>
  );

  const Series = ({ which, label, labels, series, variant, lkKey, srcKey, source }: any) => (
    <div className="rounded-xl border border-[var(--line)] p-4" data-testid={`vitals-series-${which}`}>
      <input data-testid={`vitals-series-label-${which}`} value={label || ""}
        onChange={e => set({ [lkKey]: e.target.value })}
        className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2 text-sm font-semibold outline-none focus:border-[var(--acc)]" />
      <div className="mt-3 rounded-lg overflow-hidden border border-[var(--line)] bg-[#080808]">
        <LiveChart variant={variant} accent={accent} label={label} values={series} labels={labels}
          testid={`vitals-chart-${which}`} source={source} updated={v.imported_at || v.updated_at || ""} />
      </div>
      <input data-testid={`vitals-source-${which}`} value={source || ""}
        onChange={e => set({ [srcKey]: e.target.value })}
        placeholder="Source — e.g. Internal CRM (leave blank to hide)"
        className="mt-3 w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2.5 py-1.5 text-xs outline-none focus:border-[var(--acc)]" />
      <div className="mt-3 max-h-[220px] overflow-y-auto tenant-scroll pr-1 space-y-1.5">
        {(labels || []).map((l: string, i: number) => (
          <div key={i} className="flex items-center gap-2">
            <input data-testid={`vitals-row-label-${which}-${i}`} value={l}
              onChange={e => rowSet(which, i, "label", e.target.value)}
              className="flex-1 min-w-0 bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2.5 py-1.5 text-xs outline-none focus:border-[var(--acc)]" />
            <input data-testid={`vitals-row-value-${which}-${i}`} type="number" value={series?.[i] ?? 0}
              onChange={e => rowSet(which, i, "value", e.target.value)}
              className="w-24 bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2.5 py-1.5 text-xs font-mono outline-none focus:border-[var(--acc)]" />
            <button data-testid={`vitals-row-del-${which}-${i}`} onClick={() => rowDel(which, i)}
              className="chip cursor-pointer hover:!text-red-400 !px-2"><Trash2 size={11} /></button>
          </div>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button data-testid={`vitals-row-add-${which}`} onClick={() => rowAdd(which)}
          className="chip cursor-pointer hover:!text-white inline-flex items-center gap-1"><Plus size={11} /> Add row</button>
        <button data-testid={`vitals-import-${which}`}
          onClick={() => { targetRef.current = which === "1" ? "series" : "series2"; fileRef.current?.click(); }}
          className="chip cursor-pointer hover:!text-white inline-flex items-center gap-1"><Upload size={11} /> Import into this chart</button>
      </div>
    </div>
  );

  return (
    <div className="py-4 border-b border-[var(--line)]" data-testid="vitals-editor">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold">Live figures &amp; charts</div>
          <div className="text-xs text-[var(--mut)] mt-0.5">
            The numbers in this client's “at a glance” section. {v.source === "imported" ? "Currently showing imported client data." : "Currently showing demo figures."}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button data-testid="vitals-sample-btn" onClick={sample} className="chip cursor-pointer hover:!text-white inline-flex items-center gap-1"><Download size={11} /> Sample sheet</button>
          <button data-testid="vitals-reset-btn" onClick={reset} disabled={busy} className="chip cursor-pointer hover:!text-white inline-flex items-center gap-1 disabled:opacity-50"><RotateCcw size={11} /> Reset to demo</button>
          <button data-testid="vitals-save-btn" onClick={save} disabled={busy} className="btn-primary text-xs !py-1.5 !px-3 disabled:opacity-60">{busy ? "Saving…" : "Save figures"}</button>
        </div>
      </div>

      <input ref={fileRef} type="file" accept=".csv,.xlsx,.xlsm" className="hidden" data-testid="vitals-file-input"
        onChange={e => { upload(e.target.files?.[0], targetRef.current); e.target.value = ""; }} />

      <div
        data-testid="vitals-dropzone"
        onDragOver={e => { e.preventDefault(); setDrop("on"); }}
        onDragLeave={() => setDrop("")}
        onDrop={e => { e.preventDefault(); targetRef.current = "series"; upload(e.dataTransfer.files?.[0]); }}
        onClick={() => { targetRef.current = "series"; fileRef.current?.click(); }}
        className={`mt-4 rounded-xl border border-dashed px-4 py-5 text-center cursor-pointer transition-colors ${drop ? "border-[var(--acc)] bg-[var(--acc)]/5" : "border-[var(--line)] hover:border-[var(--acc)]"}`}>
        <div className="text-sm font-semibold inline-flex items-center gap-2"><Upload size={13} /> Drop an Excel or CSV sheet here</div>
        <div className="text-xs text-[var(--mut)] mt-1">Label in the first column, figures in the next. A third column automatically fills the second chart. .xlsx, .xlsm or .csv, up to 12 rows.</div>
        {v.imported_file && <div className="text-[11px] text-[var(--acc)] mt-2" data-testid="vitals-imported-file">Last import: {v.imported_file}</div>}
      </div>

      <div className="mt-4">
        <span className="overline block mb-1">Section title</span>
        <input data-testid="vitals-title-input" value={v.title || ""} onChange={e => set({ title: e.target.value })}
          className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2.5 text-sm outline-none focus:border-[var(--acc)]" />
      </div>

      <div className="mt-4 grid sm:grid-cols-3 gap-3">
        {(v.metrics || []).map((m: any, i: number) => (
          <div key={i} className="rounded-xl border border-[var(--line)] p-3" data-testid={`vitals-metric-${i}`}>
            <input data-testid={`vitals-metric-label-${i}`} value={m.label || ""}
              onChange={e => set({ metrics: v.metrics.map((x: any, j: number) => j === i ? { ...x, label: e.target.value } : x) })}
              className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2.5 py-1.5 text-xs outline-none focus:border-[var(--acc)]" />
            <div className="mt-2 flex items-center gap-1.5">
              <input data-testid={`vitals-metric-prefix-${i}`} value={m.prefix || ""} placeholder="$"
                onChange={e => set({ metrics: v.metrics.map((x: any, j: number) => j === i ? { ...x, prefix: e.target.value } : x) })}
                className="w-12 bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2 py-1.5 text-xs text-center outline-none focus:border-[var(--acc)]" />
              <input data-testid={`vitals-metric-value-${i}`} value={m.value ?? ""}
                onChange={e => set({ metrics: v.metrics.map((x: any, j: number) => j === i ? { ...x, value: e.target.value === "" ? 0 : Number(e.target.value) } : x) })}
                type="number" step="any"
                className="flex-1 min-w-0 bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2.5 py-1.5 text-sm font-mono outline-none focus:border-[var(--acc)]" />
              <input data-testid={`vitals-metric-suffix-${i}`} value={m.suffix || ""} placeholder="%"
                onChange={e => set({ metrics: v.metrics.map((x: any, j: number) => j === i ? { ...x, suffix: e.target.value } : x) })}
                className="w-14 bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-2 py-1.5 text-xs text-center outline-none focus:border-[var(--acc)]" />
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 grid md:grid-cols-2 gap-3">
        <Series which="1" label={v.series_label} lkKey="series_label" srcKey="source_label" source={v.source_label}
          labels={v.labels} series={v.series} variant={(v.variants || [])[0] || "area"} />
        <Series which="2" label={v.series2_label} lkKey="series2_label" srcKey="source_label2" source={v.source_label2}
          labels={v.labels2} series={v.series2} variant={(v.variants || [])[1] || "donut"} />
      </div>
    </div>
  );
}
