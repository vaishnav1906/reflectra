import { NavLink, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  MessageSquare,
  User,
  Calendar,
  TrendingUp,
  Settings,
  Layers,
  Home,
  Users,
  BookOpen,
  Sun,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { MILESTONE_EVENT, ModelStatePanel } from "./ModelStatePanel";
import { ProfileMenu } from "./ProfileMenu";
import { MirrorMark } from "@/components/MirrorMark";
import { ConversationHistoryModal } from "@/components/chat/ConversationHistoryModal";
import type { InteractionMode } from "@/contexts/ChatContext";

const navItems = [
  { title: "Home", path: "/", icon: Home },
  { title: "How it works", path: "/app/architecture", icon: Layers },
  { title: "Conversation", path: "/app/chat", icon: MessageSquare, hasModal: true },
  { title: "Persona", path: "/app/personality", icon: User },
  { title: "People", path: "/app/people", icon: Users },
  { title: "Your life", path: "/app/life", icon: BookOpen },
  { title: "Timeline", path: "/app/memory", icon: Calendar },
  { title: "Your week", path: "/app/week", icon: Sun },
  { title: "Reflections", path: "/app/reflections", icon: TrendingUp },
  { title: "Settings", path: "/app/settings", icon: Settings },
];

export function AppSidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [showConversationModal, setShowConversationModal] = useState(false);
  const [animatedNavPath, setAnimatedNavPath] = useState<string | null>(null);
  // The highlight slides from the old page's item to the new one.
  const navRef = useRef<HTMLElement>(null);
  const [indicator, setIndicator] = useState<{ top: number; height: number } | null>(null);
  useLayoutEffect(() => {
    const active = navRef.current?.querySelector<HTMLElement>("[data-active='true']");
    setIndicator(active ? { top: active.offsetTop, height: active.offsetHeight } : null);
  }, [location.pathname]);

  // A one-time glint on the mirror when Reflectra gets to know you better.
  const [glint, setGlint] = useState(false);
  useEffect(() => {
    let timer = 0;
    const onMilestone = () => {
      setGlint(true);
      window.clearTimeout(timer);
      timer = window.setTimeout(() => setGlint(false), 2600);
    };
    window.addEventListener(MILESTONE_EVENT, onMilestone);
    return () => {
      window.removeEventListener(MILESTONE_EVENT, onMilestone);
      window.clearTimeout(timer);
    };
  }, []);

  // Get userId dynamically each time - it might change after login
  const userId = localStorage.getItem("user_id") || "";
  const currentMode: InteractionMode = searchParams.get("mode") === "mirror" ? "mirror" : "reflection";

  const handleNavContextMenu = (e: React.MouseEvent, item: typeof navItems[0]) => {
    if (item.hasModal && item.path === "/app/chat") {
      e.preventDefault(); // Prevent browser context menu
      setShowConversationModal(true);
    }
  };

  const handleNavClick = (e: React.MouseEvent, item: typeof navItems[0]) => {
    // On the chat route, clicking Conversation should open history directly.
    if (item.hasModal && item.path === "/app/chat" && location.pathname === "/app/chat") {
      e.preventDefault();
      setShowConversationModal(true);
    }

    setAnimatedNavPath(item.path);
  };

  useEffect(() => {
    if (!animatedNavPath) return;

    const timeout = window.setTimeout(() => {
      setAnimatedNavPath(null);
    }, 360);

    return () => window.clearTimeout(timeout);
  }, [animatedNavPath]);

  const handleSelectConversation = (conversationId: string) => {
    navigate(`/app/chat?conversation_id=${conversationId}&mode=${currentMode}`);
  };

  const handleNewChat = () => {
    navigate(`/app/chat?mode=${currentMode}`);
  };

  return (
    <aside className="app-sidebar w-64 h-screen flex flex-col">
      {/* Logo */}
      <div className="px-6 pb-5 pt-7">
        <div className="flex items-center gap-3">
          <span className={cn("mirror-glint-wrap", glint && "is-glinting")}>
            <MirrorMark className="h-9 w-9" />
          </span>
          <div>
            <p className="font-display text-2xl leading-none text-foreground">Reflectra</p>
            <p className="eyebrow mt-1.5 !text-[0.6rem]">A mirror for your mind</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav ref={navRef} className="app-nav flex-1 px-3 py-2 space-y-0.5 overflow-y-auto" aria-label="App">
        <span
          className="app-nav-indicator"
          aria-hidden="true"
          style={indicator ? { top: indicator.top, height: indicator.height, opacity: 1 } : { opacity: 0 }}
        />
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          
          // For chat page, preserve mode in URL
          const itemPath = item.path === "/app/chat" 
            ? `${item.path}?mode=${currentMode}`
            : item.path;
          
          return (
            <NavLink
              key={item.path}
              to={itemPath}
              onClick={(e) => handleNavClick(e, item)}
              onContextMenu={(e) => handleNavContextMenu(e, item)}
              data-active={isActive ? "true" : undefined}
              className={cn(
                "app-nav-item flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm transition-all duration-200",
                isActive || animatedNavPath === item.path
                  ? "is-active text-foreground sidebar-nav-pop"
                  : "text-sidebar-foreground/70 hover:bg-white/[0.04] hover:text-foreground"
              )}
            >
              <item.icon className={cn("w-4 h-4 transition-transform duration-200", isActive && "text-primary", animatedNavPath === item.path && "scale-110")} />
              <span>{item.title}</span>
              {item.path === "/app/chat" && (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-iris-cyan pulse-indicator" />
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Model State Panel */}
      <div className="p-4 border-t border-white/5">
        <ModelStatePanel />
      </div>

      {/* Profile Menu */}
      <div className="p-3 border-t border-white/5">
        <ProfileMenu />
      </div>

      {/* Conversation History Modal */}
      <ConversationHistoryModal
        isOpen={showConversationModal}
        onClose={() => setShowConversationModal(false)}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        userId={userId}
        mode={currentMode}
      />
    </aside>
  );
}
