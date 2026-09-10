import { Navigate } from "react-router-dom";
import { PageSkeleton } from "@/components/PageTransition";
import { useMembership } from "@/lib/membership";

/** Gated route: signed out -> login, free/suspended -> upgrade, paid & clients -> through. */
export default function PaidRoute({ children, admin = false }) {
  const { loading, member } = useMembership();
  if (loading) return <PageSkeleton testid="gate-skeleton" />;
  if (!member) return <Navigate to="/login" replace />;
  if (admin && !member.is_admin) return <Navigate to="/dashboard" replace />;
  if (!member.full_access) return <Navigate to="/upgrade" replace />;
  return children;
}
