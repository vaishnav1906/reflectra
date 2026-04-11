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
        <div className="flex items-center bg-muted/50 rounded-lg p-1 border border-border">
          <button
            onClick={() => onModeChange("reflection")}
            className={cn(
              "flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
              mode === "reflection"
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Eye className="w-3.5 h-3.5" />
            Reflection
          </button>
          <button
            onClick={() => onModeChange("mirror")}
            className={cn(
              "flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
              mode === "mirror"
                ? "bg-primary/10 text-primary shadow-sm border border-primary/20"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Users className="w-3.5 h-3.5" />
            Persona Mirror
          </button>
        </div>
        
        <Tooltip>
          <TooltipTrigger asChild>
            <button className="p-1.5 rounded-md hover:bg-muted/50 transition-colors">
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
