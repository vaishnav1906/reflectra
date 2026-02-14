import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import Index from "./pages/Index";
import { ChatPage } from "./pages/ChatPage";
import { PersonalityPage } from "./pages/PersonalityPage";
import { MemoryPage } from "./pages/MemoryPage";
import { ReflectionsPage } from "./pages/ReflectionsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { ArchitecturePage } from "./pages/ArchitecturePage";
import { Login } from "./pages/Login";
import NotFound from "./pages/NotFound";

const App = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(() => {
    return !!localStorage.getItem("user_id");
  });

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

  const handleLoginSuccess = () => {
    setIsLoggedIn(true);
  };

  if (!isLoggedIn) {
    return (
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <Login onLoginSuccess={handleLoginSuccess} />
        </TooltipProvider>
      </QueryClientProvider>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <AppLayout>
            <Routes>
              <Route path="/" element={<Index />} />
              <Route path="/architecture" element={<ArchitecturePage />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/personality" element={<PersonalityPage />} />
              <Route path="/memory" element={<MemoryPage />} />
              <Route path="/reflections" element={<ReflectionsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </AppLayout>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
};

export default App;
