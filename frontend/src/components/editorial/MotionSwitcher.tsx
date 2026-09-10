import { useEffect, useState } from "react";
import api from "@/lib/api";
import { ChevronDown } from "lucide-react";

/** Live template switcher — permanently public, fixed at the top.
 *  Anyone (admin, client, visitor) can switch the page to any template's live motion system.
 *  Every selection renders immediately and in real time. */
export default function MotionSwitcher({ value = "", onPick, label = "LIVE — 44 Motion Systems", sticky = true }) {
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.get("/public/motion-reel").then(({ data }) => setRows(data.heroes || [])).catch(() => {});
  }, []);

  const options = rows.filter(r => r.template_key);
  const active = options.find(r => r.template_key === value);

  return (
    <div className={`${sticky ? "sticky top-0" : ""} z-[70] w-full bg-black/85 backdrop-blur-xl border-b border-white/10`}
      data-testid="motion-switcher">
      <div className="px-4 sm:px-6 py-2.5 flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="overline text-[10px] shrink-0" data-testid="motion-switcher-label">{label}</span>
        <span className="overline text-[10px] shrink-0 text-[#84FF00]">LIVE TEMPLATE</span>
        <div className="relative">
          <button data-testid="motion-switcher-toggle" onClick={() => setOpen(o => !o)}
            className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-sm text-white hover:border-white/35 cursor-pointer">
            <span className="w-2 h-2 rounded-full" style={{ background: active?.accent || "#84FF00" }} />
            <span className="font-mono text-[12px]">{active ? `${active.hero} · ${active.industry}` : "Tenant's own motion"}</span>
            <ChevronDown size={13} />
          </button>
          {open && (
            <div data-testid="motion-switcher-menu"
              className="absolute left-0 mt-2 w-[320px] max-h-[60vh] overflow-auto rounded-2xl border border-white/10 bg-[#0b0b0b] shadow-2xl p-1.5">
              <button data-testid="motion-switcher-reset" onClick={() => { onPick(""); setOpen(false); }}
                className={`w-full text-left px-3 py-2 rounded-xl text-sm cursor-pointer ${!value ? "bg-[#84FF00]/15 text-[#84FF00]" : "text-white/70 hover:bg-white/5"}`}>
                Tenant's own motion
              </button>
              {options.map(r => (
                <button key={r.template_key} data-testid={`motion-switcher-opt-${r.template_key}`}
                  onClick={() => { onPick(r.template_key); setOpen(false); }}
                  className={`w-full text-left px-3 py-2 rounded-xl cursor-pointer ${value === r.template_key ? "bg-[#84FF00]/15" : "hover:bg-white/5"}`}>
                  <div className={`text-sm ${value === r.template_key ? "text-[#84FF00]" : "text-white"}`}>{r.industry}</div>
                  <div className="font-mono text-[11px] text-white/40">{r.hero}</div>
                </button>
              ))}
            </div>
          )}
        </div>
        <a href="/motion" className="ml-auto chip cursor-pointer hover:!text-white" data-testid="motion-switcher-index-link">
          ALL 44 MOTION SYSTEMS
        </a>
      </div>
    </div>
  );
}
