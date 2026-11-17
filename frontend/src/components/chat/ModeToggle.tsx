import { Eye, Users, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import type { InteractionMode } from "@/contexts/ChatContext";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ModeToggleProps {
  mode: InteractionMode;
  onModeChange: (mode: InteractionMode) => void;
}

export function ModeToggle({ mode, onModeChange }: ModeToggleProps) {
  const modeDescriptions: Record<InteractionMode, string> = {
    reflection: "Reflection mode helps you unpack thoughts, feelings, and patterns.",
    mirror: "Persona Mirror mode reflects how you usually communicate and handles explicit tasks in your style.",
  };

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex items-center gap-2">
        <div className="flex items-center rounded-full border border-white/10 bg-white/[0.03] p-1" role="group" aria-label="Conversation mode">
          <button
            onClick={() => onModeChange("reflection")}
            className={cn(
              "flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-medium transition-all",
              mode === "reflection"
                ? "mode-pill-active text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Eye className="w-3.5 h-3.5" />
            Reflection
          </button>
          <button
            onClick={() => onModeChange("mirror")}
            className={cn(
              "flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-medium transition-all",
              mode === "mirror"
                ? "mode-pill-active text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Users className="w-3.5 h-3.5" />
            Mirror
          </button>
        </div>
        
        <Tooltip>
          <TooltipTrigger asChild>
            <button className="p-1.5 rounded-full hover:bg-white/5 transition-colors" aria-label="About this mode">
              <Info className="w-4 h-4 text-muted-foreground" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="max-w-xs bg-card border border-border">
            <p className="text-xs text-muted-foreground leading-relaxed">
              <span className="font-medium text-foreground">
                {mode === "reflection" ? "Reflection Mode" : "Persona Mirror Mode"}
              </span>{" "}
              {modeDescriptions[mode]}
            </p>
          </TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  );
}
