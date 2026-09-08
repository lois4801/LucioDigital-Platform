import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Lock, Unlock, LockKeyhole, Loader2, MessageSquarePlus } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import api from "@/lib/api";
import { toast } from "sonner";

const LockCtx = createContext(null);
export const useLocks = () => useContext(LockCtx) || { locks: {}, canManage: false, isLocked: () => false };

export function LocksProvider({ appId, children }) {
  const [data, setData] = useState({ locks: {}, state: "unlocked", locked: 0, total: 0, can_manage: false });
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => api.get(`/apps/${appId}/locks`).then(r => setData(r.data)).catch(() => { }), [appId]);
  useEffect(() => { refresh(); }, [refresh]);

  const isLocked = (kind, itemId) => !!data.locks?.[kind]?.[itemId];

  async function toggleItem(kind, itemId, name) {
    const next = !isLocked(kind, itemId);
    try {
      const { data: r } = await api.post(`/apps/${appId}/locks/item`, { kind, item_id: itemId, locked: next });
      setData(d => {
        const locks = { ...d.locks, [kind]: { ...(d.locks?.[kind] || {}) } };
        if (next) locks[kind][itemId] = true; else delete locks[kind][itemId];
        return { ...d, locks, state: r.state, locked: r.locked, total: r.total };
      });
      toast.success(`${name || "Item"} ${next ? "locked" : "unlocked"}`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not change the lock"); }
  }

  async function lockAll(locked) {
    setBusy(true);
    try {
      const { data: r } = await api.post(`/apps/${appId}/locks/all`, { locked });
      setData(d => ({ ...d, ...r }));
      toast.success(locked ? `Locked all ${r.items} item(s) across this tenant` : `Unlocked all ${r.items} item(s)`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not change the locks"); }
    finally { setBusy(false); }
  }

  return <LockCtx.Provider value={{ ...data, appId, canManage: data.can_manage, isLocked, toggleItem, lockAll, refresh, busy }}>{children}</LockCtx.Provider>;
}

export function MasterLockButton({ compact = false, testid = "master-lock-btn" }) {
  const { state, locked, total, canManage, lockAll, busy } = useLocks();
  if (!canManage) return <LockStateBadge testid="master-lock-badge" />;
  const allLocked = state === "locked";
  return (
    <button data-testid={testid} onClick={() => lockAll(!allLocked)} disabled={busy}
      title={allLocked ? "Unlock every page, section, form, workflow and CMS item" : "Lock every page, section, form, workflow and CMS item"}
      className={`flex items-center gap-2 rounded-full border px-4 py-2 text-xs font-semibold transition-colors disabled:opacity-50 ${allLocked
        ? "border-amber-400/50 bg-amber-400/10 text-amber-300 hover:bg-amber-400/20"
        : "border-[var(--line)] text-[var(--mut)] hover:text-white hover:border-white/40"}`}>
      {busy ? <Loader2 size={13} className="animate-spin" /> : allLocked ? <Lock size={13} /> : <Unlock size={13} />}
      {busy ? "Working…" : allLocked ? "Unlock all" : "Lock all"}
      {!compact && <span data-testid="master-lock-count" className="font-mono text-[10px] text-[var(--dim)]">{locked}/{total}</span>}
    </button>
  );
}

export function LockStateBadge({ state: forced, testid = "lock-state-badge" }) {
  const ctx = useLocks();
  const state = forced || ctx.state;
  const map = {
    locked: { label: "Fully locked", cls: "border-amber-400/50 text-amber-300 bg-amber-400/10", Icon: Lock },
    partial: { label: "Partially locked", cls: "border-cyan-400/40 text-cyan-300 bg-cyan-400/10", Icon: LockKeyhole },
    unlocked: { label: "Unlocked", cls: "border-[var(--line)] text-[var(--mut)]", Icon: Unlock },
  };
  const { label, cls, Icon } = map[state] || map.unlocked;
  return <span data-testid={testid} className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${cls}`}><Icon size={10} /> {label}</span>;
}

/** Padlock next to any item. Admins toggle it; clients see the lock + "Request a change". */
export function LockToggle({ kind, itemId, name, size = 11, alwaysVisible = false }) {
  const { canManage, isLocked, toggleItem } = useLocks();
  const [reqOpen, setReqOpen] = useState(false);
  const locked = isLocked(kind, itemId);
  const tid = `lock-${kind}-${itemId}`;
  if (!canManage) {
    if (!locked) return null;
    return (
      <>
        <button data-testid={`request-change-${kind}-${itemId}`} title={`${name || "This item"} is locked — request a change`}
          onClick={e => { e.stopPropagation(); setReqOpen(true); }}
          className="flex items-center gap-1 text-amber-300 hover:text-amber-200">
          <Lock size={size} /><MessageSquarePlus size={size} />
        </button>
        <ItemRequestDialog kind={kind} itemId={itemId} name={name} open={reqOpen} onOpenChange={setReqOpen} />
      </>
    );
  }
  return (
    <button data-testid={tid} title={locked ? `Unlock ${name || "item"}` : `Lock ${name || "item"} so clients cannot edit it`}
      onClick={e => { e.stopPropagation(); toggleItem(kind, itemId, name); }}
      className={`w-5 h-5 rounded-full flex items-center justify-center transition-opacity hover:text-amber-300 ${locked ? "text-amber-400 opacity-100" : `text-[var(--dim)] ${alwaysVisible ? "opacity-70" : "opacity-0 group-hover:opacity-100"}`}`}>
      {locked ? <Lock size={size} /> : <Unlock size={size} />}
    </button>
  );
}

export function ItemRequestDialog({ kind, itemId, name, open, onOpenChange }) {
  const { appId } = useLocks();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  async function send() {
    setBusy(true);
    try {
      await api.post(`/apps/${appId}/edit-request`, { kind, item_id: itemId, item_name: name, description: text });
      toast.success("Request sent — the agency will review it in their Inbox");
      setText(""); onOpenChange(false);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not send the request"); }
    finally { setBusy(false); }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[var(--card)] border-[var(--line)] text-[var(--fg)]">
        <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><Lock size={15} className="text-amber-400" /> Request a change</DialogTitle></DialogHeader>
        <p className="text-sm text-[var(--mut)]">“{name || kind}” is locked by the agency. Describe what you'd like changed and they can open it for one edit.</p>
        <textarea data-testid="item-request-input" rows={4} value={text} onChange={e => setText(e.target.value)}
          placeholder="e.g. Please update the phone number in this section to (555) 010-2030"
          className="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-xl px-3 py-2 text-sm outline-none focus:border-[var(--acc)] resize-none" />
        <button data-testid="item-request-send-btn" onClick={send} disabled={busy || text.trim().length < 5} className="btn-primary w-full disabled:opacity-50">
          {busy ? "Sending…" : "Send request"}
        </button>
      </DialogContent>
    </Dialog>
  );
}
