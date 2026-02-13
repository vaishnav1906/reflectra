import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import Index from "./pages/Index";
import { ChatPage } from "./pages/ChatPage";
import { PersonalityPage } from "./pages/PersonalityPage";
import { MemoryPage } from "./pages/MemoryPage";
import { ReflectionsPage } from "./pages/ReflectionsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { ArchitecturePage } from "./pages/ArchitecturePage";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
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

export default App;
