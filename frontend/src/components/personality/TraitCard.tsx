import { cn } from "@/lib/utils";
import { LucideIcon } from "lucide-react";
import { InfoTooltip } from "@/components/ui/InfoTooltip";

interface TraitCardProps {
  title: string;
  value: number;
  description: string;
  icon: LucideIcon;
  color: "analytical" | "empathetic" | "creative" | "consistent" | "introspective";
  inference?: string;
}

const colorClasses = {
  analytical: {
    bg: "bg-trait-analytical/10",
    border: "border-trait-analytical/20",
    text: "text-trait-analytical",
    bar: "bg-trait-analytical",
  },
  empathetic: {
    bg: "bg-trait-empathetic/10",
    border: "border-trait-empathetic/20",
    text: "text-trait-empathetic",
    bar: "bg-trait-empathetic",
  },
  creative: {
    bg: "bg-trait-creative/10",
    border: "border-trait-creative/20",
    text: "text-trait-creative",
    bar: "bg-trait-creative",
  },
  consistent: {
    bg: "bg-trait-consistent/10",
    border: "border-trait-consistent/20",
    text: "text-trait-consistent",
    bar: "bg-trait-consistent",
  },
  introspective: {
    bg: "bg-trait-introspective/10",
    border: "border-trait-introspective/20",
    text: "text-trait-introspective",
    bar: "bg-trait-introspective",
  },
};

export function TraitCard({ title, value, description, icon: Icon, color, inference }: TraitCardProps) {
  const colors = colorClasses[color];

  return (
    <div className={cn(
      "rounded-xl border p-5 transition-all duration-300 border-glow",
      colors.bg,
      colors.border
    )}>
      <div className="flex items-start justify-between mb-4">
        <div className={cn("p-2.5 rounded-lg", colors.bg)}>
          <Icon className={cn("w-5 h-5", colors.text)} />
        </div>
        <div className="flex items-center gap-1.5">
          <span className={cn("text-2xl font-bold", colors.text)}>{value}%</span>
          {inference && (
            <InfoTooltip 
              content={inference} 
              side="left"
              className="w-4 h-4"
            />
          )}
        </div>
      </div>

      <h3 className="font-semibold text-foreground mb-1">{title}</h3>
      <p className="text-sm text-muted-foreground mb-4">{description}</p>

      {/* Progress bar */}
      <div className="h-1.5 bg-background/50 rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-500", colors.bar)}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}
