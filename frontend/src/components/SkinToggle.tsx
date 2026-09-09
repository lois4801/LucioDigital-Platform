import { useEffect, useState } from "react";
import { Palette, Sparkles } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";

const KEY = "ui_skin";
export const getSkin = () => localStorage.getItem(KEY) || "classic";
export function applySkin(skin) {
  document.documentElement.setAttribute("data-skin", skin === "studio" ? "studio" : "classic");
  localStorage.setItem(KEY, skin);
}

/** Instant Classic ⇄ Studio 2026 switch for the whole agency app. */
export default function SkinToggle() {
  const [skin, setSkin] = useState(getSkin);
  useEffect(() => { applySkin(skin); }, [skin]);

  const flip = async () => {
    const next = skin === "studio" ? "classic" : "studio";
    setSkin(next);
    applySkin(next);
    toast.success(next === "studio" ? "Studio 2026 design on" : "Back to the classic design");
    try { await api.put("/me/ui-skin", { skin: next }); } catch { /* local preference still applies */ }
  };

  const studio = skin === "studio";
  return (
    <button data-testid="ui-skin-toggle" onClick={flip} title={studio ? "Switch back to the classic design" : "Try the Studio 2026 design"}
      className={`chip cursor-pointer inline-flex items-center gap-1.5 ${studio ? "chip-active" : ""}`}>
      {studio ? <Sparkles size={12} /> : <Palette size={12} />}
      <span data-testid="ui-skin-label">{studio ? "Studio 2026" : "Classic"}</span>
    </button>
  );
}
