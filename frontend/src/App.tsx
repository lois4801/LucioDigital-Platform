import { useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Toaster } from "sonner";

import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import AuthCallback from "@/pages/AuthCallback";
import Dashboard from "@/pages/Dashboard";
import AppDetail from "@/pages/AppDetail";
import PublicPreview from "@/pages/PublicPreview";
import SiteAdmin from "@/pages/SiteAdmin";
import Compare from "@/pages/Compare";
import { PaymentSuccess, PaymentCancel } from "@/pages/PaymentResult";
import ChatEmbed from "@/pages/ChatEmbed";
import { CursorFXProvider, CursorTrailThemed } from "@/components/CursorFX";
import { AnimatePresence } from "framer-motion";
import { PageTransition } from "@/components/PageTransition";
import DeployHub from "@/pages/DeployHub";
import Portal from "@/pages/Portal";
import Leads from "@/pages/Leads";
import { applySkin, getSkin } from "@/components/SkinToggle";
import TemplateGallery from "@/pages/TemplateGallery";
import RolloutHistory from "@/pages/RolloutHistory";
import TestLabLanding from "@/pages/TestLabLanding";
import CaseStudy from "@/pages/CaseStudy";
import Showcase from "@/pages/Showcase";
import RedesignReview from "@/pages/RedesignReview";
import HeroGallery from "@/pages/HeroGallery";
import AccentAudit from "@/pages/AccentAudit";
function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="overline">Loading workspace…</div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
}
function AppRouter() {
  useEffect(() => { applySkin(getSkin()); }, []);
  const location = useLocation();
  // Detect session_id synchronously (reactive) to prevent race
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <AnimatePresence mode="wait" initial={false}>
    <Routes location={location} key={location.pathname}>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/dashboard" element={<ProtectedRoute><PageTransition testid="page-dashboard"><Dashboard /></PageTransition></ProtectedRoute>} />
      <Route path="/apps/:appId" element={<ProtectedRoute><PageTransition testid="page-app"><AppDetail /></PageTransition></ProtectedRoute>} />
      <Route path="/deploy" element={<ProtectedRoute><PageTransition testid="page-deploy"><DeployHub /></PageTransition></ProtectedRoute>} />
      <Route path="/leads" element={<ProtectedRoute><PageTransition testid="page-leads"><Leads /></PageTransition></ProtectedRoute>} />
      <Route path="/templates" element={<ProtectedRoute><PageTransition testid="page-templates"><TemplateGallery /></PageTransition></ProtectedRoute>} />
      <Route path="/rollout-history" element={<ProtectedRoute><PageTransition testid="page-history"><RolloutHistory /></PageTransition></ProtectedRoute>} />
      <Route path="/test-lab/landing" element={<ProtectedRoute><TestLabLanding /></ProtectedRoute>} />
      <Route path="/redesign-review" element={<ProtectedRoute><RedesignReview /></ProtectedRoute>} />
      <Route path="/hero-gallery" element={<ProtectedRoute><HeroGallery /></ProtectedRoute>} />
      <Route path="/accent-audit" element={<ProtectedRoute><AccentAudit /></ProtectedRoute>} />
      <Route path="/work" element={<Showcase />} />
      <Route path="/work/:slug" element={<CaseStudy />} />
      <Route path="/choose/:token" element={<TemplateGallery clientMode />} />
      <Route path="/portal" element={<ProtectedRoute><PageTransition testid="page-portal"><Portal /></PageTransition></ProtectedRoute>} />
      <Route path="/p/:token" element={<PublicPreview />} />
      <Route path="/site-admin/:token" element={<SiteAdmin />} />
      <Route path="/compare/:code" element={<Compare />} />
      <Route path="/embed/chat/:token" element={<ChatEmbed />} />
      <Route path="/payment/success" element={<ProtectedRoute><PaymentSuccess /></ProtectedRoute>} />
      <Route path="/payment/cancel" element={<ProtectedRoute><PaymentCancel /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <CursorFXProvider>
            <AppRouter />
            <Toaster theme="dark" position="top-right" richColors closeButton />
            <CursorTrailThemed />
          </CursorFXProvider>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}
