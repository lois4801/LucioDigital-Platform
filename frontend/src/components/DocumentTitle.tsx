import { useEffect } from "react";
import { useLocation } from "react-router-dom";

const BRAND = "LucioDigital";

const TITLES: [string, string][] = [
  ["/dashboard", "Dashboard"],
  ["/apps/", "Site Mode"],
  ["/templates", "Templates"],
  ["/choose/", "Choose a template"],
  ["/leads", "Lead inbox"],
  ["/deploy", "Deploy"],
  ["/rollout-history", "Rollout history"],
  ["/redesign-review", "Redesign review"],
  ["/hero-gallery", "Motion systems"],
  ["/motion", "Motion systems"],
  ["/accent-audit", "Accent audit"],
  ["/work", "Client work"],
  ["/portal", "Client Portal"],
  ["/p/", "Live site"],
  ["/paid", "Billing"],
  ["/site-admin/", "Site admin"],
  ["/compare/", "Before & after"],
  ["/login", "Sign in"],
  ["/register", "Create your account"],
  ["/classic-landing", "Agency platform"],
  ["/payment/success", "Payment complete"],
  ["/payment/cancel", "Payment cancelled"],
];

/** Keeps the browser tab title prefixed with the brand on every route. */
export default function DocumentTitle() {
  const { pathname } = useLocation();
  useEffect(() => {
    const hit = TITLES.find(([p]) => pathname === p || pathname.startsWith(p));
    document.title = hit ? `${BRAND} — ${hit[1]}` : `${BRAND} — Agency platform`;
  }, [pathname]);
  return null;
}
