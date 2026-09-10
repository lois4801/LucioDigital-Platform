import { createContext, useCallback, useContext, useEffect, useState } from "react";
import api from "@/lib/api";

const Ctx = createContext<any>({ loading: true, member: null, refresh: () => {} });

export function MembershipProvider({ children }) {
  const [member, setMember] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/membership/me");
      setMember(data);
    } catch {
      setMember(null);                       // signed out or not authenticated
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return <Ctx.Provider value={{ loading, member, refresh, setMember }}>{children}</Ctx.Provider>;
}

export function useMembership() {
  return useContext(Ctx);
}
