import { ArrowRight, Scan, TrendingUp, Layers, FileText } from "lucide-react";
import { cn } from "@/lib/utils";

interface PipelineStep {
  name: string;
  icon: typeof Scan;
  active: boolean;
}

const reflectionPipeline: PipelineStep[] = [
  { name: "Pattern Detection", icon: Scan, active: true },
  { name: "Trend Analysis", icon: TrendingUp, active: true },
  { name: "Abstraction", icon: Layers, active: true },
  { name: "NL Synthesis", icon: FileText, active: true },
];

interface PipelineIndicatorProps {
  variant?: "reflection" | "insight";
  className?: string;
}

export function PipelineIndicator({ variant = "reflection", className }: PipelineIndicatorProps) {
  const steps = reflectionPipeline;
  
  return (
    <div className={cn("flex items-center gap-1", className)}>
      <span className="text-xs text-muted-foreground/60 mr-2">Pipeline:</span>
      {steps.map((step, index) => {
        const Icon = step.icon;
        return (
          <div key={step.name} className="flex items-center">
            <div 
              className={cn(
                "flex items-center gap-1 px-2 py-1 rounded text-xs",
                step.active 
                  ? "bg-muted/50 text-muted-foreground" 
                  : "text-muted-foreground/40"
              )}
              title={step.name}
            >
              <Icon className="w-3 h-3" />
              <span className="hidden sm:inline">{step.name}</span>
            </div>
            {index < steps.length - 1 && (
              <ArrowRight className="w-3 h-3 text-muted-foreground/30 mx-0.5" />
            )}
          </div>
        );
      })}
    </div>
  );
}
