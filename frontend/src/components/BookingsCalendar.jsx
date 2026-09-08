import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { CalendarDays, Plus, X, AlertTriangle, Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const HOURS = Array.from({ length: 24 }, (_, i) => i);
const pad = (n) => String(n).padStart(2, "0");
const iso = (d) => d.toISOString().slice(0, 10);
const startOfWeek = (d) => { const x = new Date(d); const g = (x.getDay() + 6) % 7; x.setDate(x.getDate() - g); x.setHours(0, 0, 0, 0); return x; };
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const slotHour = (slot) => {
  if (!slot) return 9;
  const m = /^(\d{1,2}):(\d{2})/.exec(slot);
  if (m) return Number(m[1]);
  return { Morning: 9, Afternoon: 13, Evening: 18 }[slot] ?? 9;
};

const BLANK = { name: "", email: "", phone: "", service: "", date: "", slot: "09:00", duration_min: 60, notes: "", notify: true };

/** Week / day / month calendar of every booking for a tenant, with admin create, edit and cancel. */
export default function BookingsCalendar({ appId, token }) {
  const [rows, setRows] = useState([]);
  const [view, setView] = useState("week");
  const [anchor, setAnchor] = useState(() => new Date());
  const [open, setOpen] = useState(null);      // existing booking
  const [draft, setDraft] = useState(null);    // new booking form
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = () => api.get(`/site/${token}/admin/bookings`).then(r => { setRows(r.data.bookings || []); setLoading(false); })
    .catch(() => setLoading(false));
  useEffect(() => { load(); const t = setInterval(load, 8000); return () => clearInterval(t); }, [token]);

  const days = useMemo(() => {
    if (view === "day") return [new Date(anchor)];
    if (view === "week") return Array.from({ length: 7 }, (_, i) => addDays(startOfWeek(anchor), i));
    const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    const start = startOfWeek(first);
    return Array.from({ length: 42 }, (_, i) => addDays(start, i));
  }, [view, anchor]);

  const byDay = useMemo(() => {
    const map = {};
    rows.filter(r => r.booking?.status !== "cancelled").forEach(r => {
      const d = r.booking?.date;
      if (!d) return;
      (map[d] = map[d] || []).push(r);
    });
    // flag clashes: same day + same hour
    Object.values(map).forEach(list => {
      const seen = {};
      list.forEach(r => { const h = slotHour(r.booking.slot); seen[h] = (seen[h] || 0) + 1; });
      list.forEach(r => { r.__clash = seen[slotHour(r.booking.slot)] > 1; });
    });
    return map;
  }, [rows]);

  const clashes = rows.filter(r => r.__clash).length;

  async function save() {
    setBusy(true);
    try {
      if (draft?.submission_id) await api.put(`/site/${token}/admin/bookings/${draft.submission_id}`, draft);
      else await api.post(`/site/${token}/admin/bookings`, draft);
      toast.success(draft.notify ? "Saved — the client has been emailed" : "Saved");
      setDraft(null); setOpen(null); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not save the booking"); }
    finally { setBusy(false); }
  }
  async function cancel(r, notifyClient) {
    if (!window.confirm(`Cancel the booking for ${r.name}?`)) return;
    try { await api.delete(`/site/${token}/admin/bookings/${r.submission_id}`, { params: { notify_client: notifyClient } }); setOpen(null); load(); toast.success("Booking cancelled"); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not cancel"); }
  }

  const Cell = ({ day, hour }) => {
    const list = (byDay[iso(day)] || []).filter(r => slotHour(r.booking.slot) === hour);
    return (
      <div data-testid={`cal-slot-${iso(day)}-${pad(hour)}`} onClick={() => setDraft({ ...BLANK, date: iso(day), slot: `${pad(hour)}:00` })}
        className="min-h-[34px] border-t border-l border-[var(--line)] px-1 py-0.5 cursor-pointer hover:bg-white/5">
        {list.map(r => (
          <button key={r.submission_id} data-testid={`booking-block-${r.submission_id}`} onClick={e => { e.stopPropagation(); setOpen(r); }}
            className={`w-full text-left rounded px-1.5 py-1 mb-0.5 text-[10px] leading-tight truncate ${r.__clash ? "bg-red-500/25 border border-red-400/70 text-red-200" : "bg-[var(--acc)]/20 border border-[var(--acc)]/40"}`}>
            {r.booking.slot || ""} {r.name}
          </button>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-3" data-testid="bookings-calendar">
      <div className="flex flex-wrap items-center gap-3">
        <CalendarDays size={15} className="text-[var(--acc)]" />
        <div className="text-xs flex-1 min-w-[180px]">
          <div className="font-semibold">Booking calendar</div>
          <div className="text-[var(--mut)]">{rows.length} booking(s){clashes ? " · " : ""}{clashes ? <span className="text-red-300">{clashes} overlapping</span> : ""} · live</div>
        </div>
        {clashes > 0 && <span data-testid="clash-warning" className="chip chip-maint flex items-center gap-1"><AlertTriangle size={11} /> double-booked</span>}
        <div className="flex rounded-full border border-[var(--line)] overflow-hidden text-[11px]">
          {["day", "week", "month"].map(v => <button key={v} data-testid={`cal-view-${v}`} onClick={() => setView(v)} className={`px-3 py-1.5 capitalize ${view === v ? "bg-[var(--acc)]/15 text-[var(--acc)]" : "text-[var(--mut)] hover:text-white"}`}>{v}</button>)}
        </div>
        <button data-testid="cal-prev" onClick={() => setAnchor(addDays(anchor, view === "month" ? -30 : view === "week" ? -7 : -1))} className="btn-ghost !py-1.5 !px-3 text-xs">←</button>
        <button data-testid="cal-today" onClick={() => setAnchor(new Date())} className="btn-ghost !py-1.5 !px-3 text-xs">Today</button>
        <button data-testid="cal-next" onClick={() => setAnchor(addDays(anchor, view === "month" ? 30 : view === "week" ? 7 : 1))} className="btn-ghost !py-1.5 !px-3 text-xs">→</button>
        <button data-testid="new-booking-btn" onClick={() => setDraft({ ...BLANK, date: iso(new Date()) })} className="btn-primary !py-2 !px-4 text-xs flex items-center gap-1.5"><Plus size={12} /> New booking</button>
      </div>

      {loading ? <div className="py-10 grid place-items-center"><Loader2 className="animate-spin text-[var(--acc)]" /></div> : view === "month" ? (
        <div className="grid grid-cols-7 rounded-xl border-r border-b border-[var(--line)] overflow-hidden">
          {days.map(d => (
            <div key={iso(d)} data-testid={`cal-day-${iso(d)}`} onClick={() => setDraft({ ...BLANK, date: iso(d) })}
              className={`min-h-[86px] border-t border-l border-[var(--line)] p-1.5 cursor-pointer hover:bg-white/5 ${d.getMonth() !== anchor.getMonth() ? "opacity-40" : ""}`}>
              <div className="text-[10px] text-[var(--dim)] mb-1">{d.getDate()}</div>
              {(byDay[iso(d)] || []).map(r => (
                <button key={r.submission_id} data-testid={`booking-block-${r.submission_id}`} onClick={e => { e.stopPropagation(); setOpen(r); }}
                  className={`w-full text-left rounded px-1 py-0.5 mb-0.5 text-[10px] truncate ${r.__clash ? "bg-red-500/25 border border-red-400/70 text-red-200" : "bg-[var(--acc)]/20 border border-[var(--acc)]/40"}`}>
                  {r.booking.slot || ""} {r.name}
                </button>
              ))}
            </div>
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border-r border-b border-[var(--line)]">
          <div className="min-w-[640px]" style={{ display: "grid", gridTemplateColumns: `60px repeat(${days.length}, minmax(90px, 1fr))` }}>
            <div className="border-t border-l border-[var(--line)] bg-[var(--bg-2)]" />
            {days.map(d => <div key={iso(d)} className="border-t border-l border-[var(--line)] bg-[var(--bg-2)] px-2 py-1.5 text-[11px] font-semibold">{d.toLocaleDateString(undefined, { weekday: "short", day: "numeric" })}</div>)}
            {HOURS.map(h => (
              <div key={h} style={{ display: "contents" }}>
                <div className="border-t border-l border-[var(--line)] px-2 py-1 text-[10px] font-mono text-[var(--dim)]">{pad(h)}:00</div>
                {days.map(d => <Cell key={iso(d) + h} day={d} hour={h} />)}
              </div>
            ))}
          </div>
        </div>
      )}

      <Dialog open={!!open} onOpenChange={o => !o && setOpen(null)}>
        <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)]">
          <DialogHeader><DialogTitle className="font-display">{open?.name}</DialogTitle></DialogHeader>
          {open && (
            <div className="space-y-2 text-sm" data-testid="booking-details">
              <div className="text-[var(--mut)] text-xs">{open.email} · {open.fields?.phone}</div>
              <div><span className="chip">{open.form_name}</span> <span className="chip">{open.booking.status}</span> {open.__clash && <span className="chip chip-maint">clashes</span>}</div>
              <div className="text-xs">{open.booking.date} {open.booking.slot || ""} · {open.booking.duration_min || 60} min</div>
              {open.fields?.notes && <div className="text-xs text-[var(--mut)]">{open.fields.notes}</div>}
              <div className="flex gap-2 pt-2">
                <button data-testid="booking-edit-btn" onClick={() => { setDraft({ ...BLANK, ...open.fields, submission_id: open.submission_id, name: open.name, email: open.email, service: open.form_name, date: open.booking.date, slot: open.booking.slot || "09:00", duration_min: open.booking.duration_min || 60, notify: true }); setOpen(null); }} className="btn-primary !py-2 !px-4 text-xs">Reschedule / edit</button>
                <button data-testid="booking-cancel-btn" onClick={() => cancel(open, true)} className="btn-ghost !py-2 !px-4 text-xs flex items-center gap-1.5"><X size={12} /> Cancel & notify</button>
                <button data-testid="booking-cancel-quiet-btn" onClick={() => cancel(open, false)} className="btn-ghost !py-2 !px-4 text-xs">Cancel quietly</button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={!!draft} onOpenChange={o => !o && setDraft(null)}>
        <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)]">
          <DialogHeader><DialogTitle className="font-display">{draft?.submission_id ? "Edit booking" : "New booking"}</DialogTitle></DialogHeader>
          {draft && (
            <div className="space-y-2" data-testid="booking-form">
              {[["name", "Client name"], ["email", "Client email"], ["phone", "Phone"], ["service", "Service or booking type"]].map(([k, label]) => (
                <label key={k} className="block"><span className="text-[10px] text-[var(--dim)]">{label}</span>
                  <input data-testid={`booking-field-${k}`} value={draft[k] || ""} onChange={e => setDraft({ ...draft, [k]: e.target.value })}
                    className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm outline-none focus:border-[var(--acc)]" /></label>
              ))}
              <div className="grid grid-cols-3 gap-2">
                <label className="block"><span className="text-[10px] text-[var(--dim)]">Date</span>
                  <input data-testid="booking-field-date" type="date" value={draft.date || ""} onChange={e => setDraft({ ...draft, date: e.target.value })} className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-2 py-2 text-sm" /></label>
                <label className="block"><span className="text-[10px] text-[var(--dim)]">Time</span>
                  <input data-testid="booking-field-slot" value={draft.slot || ""} onChange={e => setDraft({ ...draft, slot: e.target.value })} placeholder="09:00" className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-2 py-2 text-sm" /></label>
                <label className="block"><span className="text-[10px] text-[var(--dim)]">Minutes</span>
                  <input data-testid="booking-field-duration" type="number" min={15} step={15} value={draft.duration_min} onChange={e => setDraft({ ...draft, duration_min: Number(e.target.value) })} className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-2 py-2 text-sm" /></label>
              </div>
              <label className="block"><span className="text-[10px] text-[var(--dim)]">Notes</span>
                <textarea data-testid="booking-field-notes" rows={2} value={draft.notes || ""} onChange={e => setDraft({ ...draft, notes: e.target.value })} className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm outline-none focus:border-[var(--acc)] resize-none" /></label>
              <label className="flex items-center gap-2 text-xs cursor-pointer">
                <input type="checkbox" data-testid="booking-notify" checked={!!draft.notify} onChange={e => setDraft({ ...draft, notify: e.target.checked })} className="accent-[var(--acc)]" />
                Email the client about this
              </label>
              <button data-testid="booking-save-btn" onClick={save} disabled={busy || !draft.name || !draft.date} className="btn-primary w-full disabled:opacity-50">{busy ? "Saving…" : draft.submission_id ? "Save changes" : "Create booking"}</button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
