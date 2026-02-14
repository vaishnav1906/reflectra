import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { LandingPage } from "./pages/LandingPage";
import { ChatPage } from "./pages/ChatPage";
import { PersonalityPage } from "./pages/PersonalityPage";
import { MemoryPage } from "./pages/MemoryPage";
import { ReflectionsPage } from "./pages/ReflectionsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { ArchitecturePage } from "./pages/ArchitecturePage";
import NotFound from "./pages/NotFound";

const App = () => {
  // Create QueryClient once and memoize it to prevent recreation on every render
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
            refetchOnReconnect: false,
            retry: 1,
            staleTime: 5 * 60 * 1000, // 5 minutes
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            {/* Landing Page */}
            <Route path="/" element={<LandingPage />} />
            
            {/* Main App Routes - Protected */}
            <Route path="/app" element={<ProtectedRoute><AppLayout><Navigate to="/app/chat" replace /></AppLayout></ProtectedRoute>} />
            <Route path="/app/chat" element={<ProtectedRoute><AppLayout><ChatPage /></AppLayout></ProtectedRoute>} />
            <Route path="/app/architecture" element={<ProtectedRoute><AppLayout><ArchitecturePage /></AppLayout></ProtectedRoute>} />
            <Route path="/app/personality" element={<ProtectedRoute><AppLayout><PersonalityPage /></AppLayout></ProtectedRoute>} />
            <Route path="/app/memory" element={<ProtectedRoute><AppLayout><MemoryPage /></AppLayout></ProtectedRoute>} />
            <Route path="/app/reflections" element={<ProtectedRoute><AppLayout><ReflectionsPage /></AppLayout></ProtectedRoute>} />
            <Route path="/app/settings" element={<ProtectedRoute><AppLayout><SettingsPage /></AppLayout></ProtectedRoute>} />
            
            {/* 404 */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
};

export default App;
