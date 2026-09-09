import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function AuthCallback() {
  const location = useLocation();
  const nav = useNavigate();
  const { setUser } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = location.hash || "";
    const match = hash.match(/session_id=([^&]+)/);
    if (!match) {
      nav("/login", { replace: true });
      return;
    }
    const session_id = decodeURIComponent(match[1]);

    (async () => {
      try {
        const { data } = await api.post("/auth/session", { session_id });
        setUser(data);
        // Clean the hash from URL
        window.history.replaceState({}, "", "/dashboard");
        nav("/dashboard", { replace: true, state: { user: data } });
      } catch {
        nav("/login", { replace: true });
      }
    })();
  }, [location.hash, nav, setUser]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="pulse-dot inline-block" />
        <div className="overline mt-4">Establishing session…</div>
      </div>
    </div>
  );
}
