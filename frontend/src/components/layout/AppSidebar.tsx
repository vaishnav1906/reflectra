import { NavLink, useLocation } from "react-router-dom";
import {
  MessageSquare,
  User,
  Calendar,
  TrendingUp,
  Settings,
  Home,
  Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ModelStatePanel } from "./ModelStatePanel";

const navItems = [
  { title: "Home", path: "/", icon: Home },
  { title: "Architecture", path: "/architecture", icon: Layers },
  { title: "Conversation", path: "/chat", icon: MessageSquare },
  { title: "Persona Profile", path: "/personality", icon: User },
  { title: "Timeline", path: "/memory", icon: Calendar },
  { title: "Reflections", path: "/reflections", icon: TrendingUp },
  { title: "Settings", path: "/settings", icon: Settings },
];

export function AppSidebar() {
  const location = useLocation();

  return (
    <aside className="w-64 h-screen bg-sidebar border-r border-sidebar-border flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-sidebar-border">
        <div className="flex items-center gap-3">
          <img
            src="/favicon.ico"
            alt="Reflectra Logo"
            className="w-10 h-10 rounded-xl glow-subtle"
          />
          <div>
            <h1 className="font-semibold text-foreground tracking-tight">Reflectra</h1>
            <p className="text-xs text-muted-foreground">Persona Reflection</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={cn(
                "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-sidebar-accent text-primary glow-subtle"
                  : "text-sidebar-foreground hover:bg-sidebar-accent/50 hover:text-foreground"
              )}
            >
              <item.icon className={cn("w-4 h-4", isActive && "text-primary")} />
              <span>{item.title}</span>
              {item.path === "/chat" && (
                <span className="ml-auto w-2 h-2 rounded-full bg-primary pulse-indicator" />
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Model State Panel */}
      <div className="p-4 border-t border-sidebar-border">
        <ModelStatePanel />
      </div>
    </aside>
  );
}
