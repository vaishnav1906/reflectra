import { useLayoutEffect, useRef, useState } from "react";
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

  // The coloured pill slides under whichever mode is on.
  const group = useRef<HTMLDivElement>(null);
  const [pill, setPill] = useState<{ left: number; width: number } | null>(null);
  useLayoutEffect(() => {
    const active = group.current?.querySelector<HTMLElement>(`[data-mode='${mode}']`);
    if (active) setPill({ left: active.offsetLeft, width: active.offsetWidth });
  }, [mode]);

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex items-center gap-2">
        <div ref={group} className="relative flex items-center rounded-full border border-white/10 bg-white/[0.03] p-1" role="group" aria-label="Conversation mode">
          <span
            className="mode-pill-active mode-pill-slider"
            aria-hidden="true"
            style={pill ? { left: pill.left, width: pill.width } : { opacity: 0 }}
          />
          <button
            data-mode="reflection"
            aria-pressed={mode === "reflection"}
            onClick={() => onModeChange("reflection")}
            className={cn(
              "relative z-[1] flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-medium transition-colors",
              mode === "reflection"
                ? "text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Eye className="w-3.5 h-3.5" />
            Reflection
          </button>
          <button
            data-mode="mirror"
            aria-pressed={mode === "mirror"}
            onClick={() => onModeChange("mirror")}
            className={cn(
              "relative z-[1] flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-medium transition-colors",
              mode === "mirror"
                ? "text-primary-foreground"
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
