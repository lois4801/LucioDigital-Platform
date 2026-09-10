import { useEffect, useState } from "react";
import { toast } from "sonner";
import { MapPin, Navigation } from "lucide-react";
import api from "@/lib/api";

/** Business address + optional custom "Get directions" link for one client.
 *  Used by the agency Site Mode panel and by the client portal. */
export default function LocationFields({ appId, onSaved = () => {}, compact = false }) {
  const [sm, setSm] = useState<any>(null);
  const [addr, setAddr] = useState("");
  const [mapUrl, setMapUrl] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!appId) return;
    api.get(`/apps/${appId}/site-mode`).then(({ data }) => {
      setSm(data); setAddr(data.address || ""); setMapUrl(data.map_url || "");
    }).catch(() => {});
  }, [appId]);

  const dirty = !!sm && (addr !== (sm.address || "") || mapUrl !== (sm.map_url || ""));

  async function save() {
    setBusy(true);
    try {
      const { data } = await api.put(`/apps/${appId}/site-mode`, { address: addr, map_url: mapUrl });
      setSm((s: any) => ({ ...s, ...data }));
      toast.success("Location saved — the map and contact details are updated");
      onSaved();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Could not save the location");
    } finally { setBusy(false); }
  }

  if (!sm) return null;
  const inp = "w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm outline-none focus:border-[var(--acc)]";

  return (
    <div className={compact ? "" : "py-4 border-b border-[var(--line)]"} data-testid="location-fields">
      <div className="text-sm font-semibold flex items-center gap-2"><MapPin size={13} className="text-[var(--acc)]" /> Business address</div>
      <div className="text-xs text-[var(--mut)] mt-0.5">
        Drives the map, the “Get directions” button and your contact + footer details.
        {sm.template_address && !sm.address ? ` Showing the template sample for now: ${sm.template_address}` : ""}
      </div>
      <div className="mt-3 grid sm:grid-cols-2 gap-2">
        <input data-testid="sm-address-input" value={addr} onChange={e => setAddr(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && dirty) save(); }}
          placeholder={sm.template_address || "215 Industrial Pkwy N, Toronto, ON"} className={inp} />
        <input data-testid="sm-mapurl-input" value={mapUrl} onChange={e => setMapUrl(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && dirty) save(); }}
          placeholder="Directions link — blank uses Google Maps automatically" className={inp} />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button data-testid="sm-address-save" onClick={save} disabled={busy || !dirty}
          className="btn-primary text-xs !py-1.5 !px-3 disabled:opacity-50">{busy ? "Saving…" : "Save location"}</button>
        {addr && (
          <a data-testid="sm-directions-test" target="_blank" rel="noreferrer"
            href={mapUrl || `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(addr)}`}
            className="chip cursor-pointer hover:!text-white inline-flex items-center gap-1"><Navigation size={11} /> Test the link</a>
        )}
      </div>
    </div>
  );
}
