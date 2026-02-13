import { cn } from "@/lib/utils";
import { Calendar, MessageSquare, Star, Repeat, BookOpen, Activity, Heart } from "lucide-react";
import { InfoTooltip } from "@/components/ui/InfoTooltip";

type MemoryType = "event" | "habit" | "pattern" | "milestone";
type CognitiveType = "episodic" | "semantic" | "behavioral" | "preference";

interface MemoryCardProps {
  type: MemoryType;
  cognitiveType?: CognitiveType;
  title: string;
  description: string;
  date: string;
  significance: number;
  tags: string[];
  inference?: string;
}

const typeConfig = {
  event: { icon: Calendar, label: "Event", color: "text-trait-analytical" },
  habit: { icon: Repeat, label: "Habit", color: "text-trait-consistent" },
  pattern: { icon: MessageSquare, label: "Pattern", color: "text-trait-creative" },
  milestone: { icon: Star, label: "Milestone", color: "text-accent" },
};

const cognitiveConfig = {
  episodic: { icon: Calendar, label: "Episodic", color: "bg-trait-analytical/20 text-trait-analytical" },
  semantic: { icon: BookOpen, label: "Semantic", color: "bg-trait-creative/20 text-trait-creative" },
  behavioral: { icon: Activity, label: "Behavioral", color: "bg-trait-consistent/20 text-trait-consistent" },
  preference: { icon: Heart, label: "Preference", color: "bg-trait-empathetic/20 text-trait-empathetic" },
};

export function MemoryCard({ 
  type, 
  cognitiveType, 
  title, 
  description, 
  date, 
  significance, 
  tags,
  inference 
}: MemoryCardProps) {
  const config = typeConfig[type];
  const Icon = config.icon;
  const cognitive = cognitiveType ? cognitiveConfig[cognitiveType] : null;

  return (
    <div className="relative pl-10 pb-8 last:pb-0">
      {/* Timeline connector */}
      <div className="timeline-connector" />

      {/* Timeline dot */}
      <div className={cn(
        "absolute left-2.5 w-3 h-3 rounded-full border-2 border-background",
        significance > 80 ? "bg-accent" : significance > 50 ? "bg-primary" : "bg-muted-foreground"
      )} />

      {/* Card */}
      <div className="bg-card border border-border rounded-xl p-5 ml-4 transition-all duration-200 border-glow fade-in">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <Icon className={cn("w-4 h-4", config.color)} />
            <span className="text-xs font-medium text-muted-foreground">{config.label}</span>
            {cognitive && (
              <span className={cn("text-xs px-2 py-0.5 rounded-full", cognitive.color)}>
                {cognitive.label}
              </span>
            )}
          </div>
          <span className="text-xs text-muted-foreground">{date}</span>
        </div>

        <div className="flex items-start gap-2 mb-2">
          <h3 className="font-medium text-foreground flex-1">{title}</h3>
          {inference && (
            <InfoTooltip 
              content={inference} 
              side="left"
              className="flex-shrink-0"
            />
          )}
        </div>
        <p className="text-sm text-muted-foreground mb-4">{description}</p>

        <div className="flex items-center justify-between">
          <div className="flex flex-wrap gap-2">
            {tags.map((tag) => (
              <span
                key={tag}
                className="text-xs px-2 py-1 rounded-full bg-muted text-muted-foreground"
              >
                {tag}
              </span>
            ))}
          </div>

          <div className="flex items-center gap-1">
            <span className="text-xs text-muted-foreground">Significance:</span>
            <span className={cn(
              "text-xs font-medium",
              significance > 80 ? "text-accent" : significance > 50 ? "text-primary" : "text-muted-foreground"
            )}>
              {significance}%
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
