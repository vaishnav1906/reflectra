import { useState } from "react";
import { Brain, MessageSquare, Microscope, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { InfoTooltip } from "@/components/ui/InfoTooltip";

type ResearchMode = "normal" | "reflective" | "analytical";

interface ModeConfig {
  id: ResearchMode;
  name: string;
  icon: typeof Brain;
  description: string;
  responseStyle: string;
}

const modes: ModeConfig[] = [
  {
    id: "normal",
    name: "Standard",
    icon: MessageSquare,
    description: "Balanced conversational interaction with personality adaptation",
    responseStyle: "Conversational, adaptive tone matching",
  },
  {
    id: "reflective",
    name: "Reflective",
    icon: Sparkles,
    description: "Deep introspective dialogue with enhanced self-insight prompts",
    responseStyle: "Thoughtful, question-rich, insight-oriented",
  },
  {
    id: "analytical",
    name: "Analytical",
    icon: Microscope,
    description: "Detailed behavioral analysis with explicit inference explanations",
    responseStyle: "Technical, data-rich, explainable",
  },
];

interface ResearchModeToggleProps {
  compact?: boolean;
}

export function ResearchModeToggle({ compact = false }: ResearchModeToggleProps) {
  const [activeMode, setActiveMode] = useState<ResearchMode>("normal");

  if (compact) {
    return (
      <div className="flex items-center gap-1 p-1 bg-muted/50 rounded-lg border border-border">
        {modes.map((mode) => {
          const Icon = mode.icon;
          return (
            <button
              key={mode.id}
              onClick={() => setActiveMode(mode.id)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                activeMode === mode.id
                  ? "bg-card text-primary shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
              title={mode.description}
            >
              <Icon className="w-3.5 h-3.5" />
              {mode.name}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <Brain className="w-4 h-4 text-primary" />
        <h3 className="font-semibold text-foreground">Research Mode</h3>
        <InfoTooltip 
          content="Switch between interaction modes to adjust response depth, analytical detail, and reflective prompting behavior" 
        />
      </div>

      <div className="space-y-3">
        {modes.map((mode) => {
          const Icon = mode.icon;
          const isActive = activeMode === mode.id;
          
          return (
            <button
              key={mode.id}
              onClick={() => setActiveMode(mode.id)}
              className={cn(
                "w-full p-4 rounded-lg border transition-all text-left",
                isActive 
                  ? "bg-primary/5 border-primary/30 ring-1 ring-primary/20" 
                  : "bg-muted/30 border-border/50 hover:border-border"
              )}
            >
              <div className="flex items-start gap-3">
                <div className={cn(
                  "w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0",
                  isActive ? "bg-primary/10" : "bg-muted"
                )}>
                  <Icon className={cn("w-4 h-4", isActive ? "text-primary" : "text-muted-foreground")} />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "text-sm font-medium",
                      isActive ? "text-foreground" : "text-muted-foreground"
                    )}>
                      {mode.name} Mode
                    </span>
                    {isActive && (
                      <span className="text-xs px-1.5 py-0.5 bg-primary/20 text-primary rounded">
                        Active
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{mode.description}</p>
                  <p className="text-xs text-muted-foreground/60 mt-2">
                    Response style: {mode.responseStyle}
                  </p>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <div className="mt-4 pt-4 border-t border-border">
        <p className="text-xs text-muted-foreground/60">
          Mode selection affects response generation parameters. All modes maintain personality model accuracy.
        </p>
      </div>
    </div>
  );
}
