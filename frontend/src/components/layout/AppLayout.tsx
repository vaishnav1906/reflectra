import { ReactNode, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { AppSidebar } from "./AppSidebar";
import { MirrorMark } from "@/components/MirrorMark";
import { EnterMirror, clearEntranceRequest, entranceRequested } from "@/components/transitions/EnterMirror";
import { useThemeSync } from "@/hooks/useThemeSync";
import { OfflineBanner } from "@/components/pwa/InstallApp";
import { Tutorial } from "@/components/tutorial/Tutorial";
import { useProfile } from "@/components/settings/AboutYou";
import { useAuth } from "@/contexts/AuthContext";
import { markTutorialDone, shouldAutoStartTutorial } from "@/lib/tutorial";
import { cn } from "@/lib/utils";

interface AppLayoutProps {
  children: ReactNode;
}

/**
 * App shell. From 768px up the sidebar sits beside the page. Below that it is a
 * drawer opened from a top bar, so pages get the full width of a phone.
 */
export function AppLayout({ children }: AppLayoutProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  useThemeSync();
  // The "step through the mirror" intro, when arriving from the landing page or sign-in.
  const [entering, setEntering] = useState(entranceRequested);
  useEffect(() => {
    if (entering) clearEntranceRequest();
  }, [entering]);

  // New here? The tour opens by itself once (after the entrance), and Skip is always there.
  const { user } = useAuth();
  const { data: profile } = useProfile();
  const navigate = useNavigate();
  const [touring, setTouring] = useState(false);
  useEffect(() => {
    if (!entering && profile && shouldAutoStartTutorial(user?.id, profile.member_since)) setTouring(true);
  }, [entering, profile, user?.id]);
  const endTour = (thenChat: boolean) => {
    markTutorialDone(user?.id);
    setTouring(false);
    if (thenChat) navigate("/app/chat?mode=reflection");
  };

  // Picking a destination closes the drawer.
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname, location.search]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  return (
    <div className="app-shell grain flex min-h-screen w-full gradient-mesh">
      <header className="app-topbar fixed inset-x-0 top-0 z-30 flex items-center gap-3 px-4 md:hidden">
        <button
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          aria-controls="app-sidebar"
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-foreground"
        >
          {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
        <MirrorMark className="h-7 w-7" />
        <span className="font-display text-xl leading-none text-foreground">Reflectra</span>
      </header>

      {/* Dim the page behind the open drawer; tapping it closes the drawer. */}
      <div
        aria-hidden="true"
        onClick={() => setMenuOpen(false)}
        className={cn(
          "fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity duration-300 md:hidden",
          menuOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />

      <div
        id="app-sidebar"
        className={cn(
          "fixed inset-y-0 left-0 z-50 transition-transform duration-300 ease-out md:static md:z-auto md:translate-x-0 md:transition-none",
          menuOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <AppSidebar />
      </div>

      <main className="app-main min-w-0 flex-1 overflow-hidden pt-[calc(3.5rem+env(safe-area-inset-top))] md:pt-0">
        {/* Keyed by page, so each page fades in when you arrive (not on every chat message). */}
        <div key={location.pathname} className="page-enter">
          {children}
        </div>
      </main>

      <OfflineBanner />
      {touring ? <Tutorial onClose={() => endTour(false)} onStart={() => endTour(true)} /> : null}
      {entering ? <EnterMirror onDone={() => setEntering(false)} /> : null}
    </div>
  );
}
