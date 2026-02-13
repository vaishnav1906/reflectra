import { ScrollArea } from "@/components/ui/scroll-area";
import { Lightbulb, TrendingUp, Heart, Target, Calendar, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const reflections = [
  {
    id: 1,
    title: "Emotional Expression Patterns",
    summary: "You tend to articulate emotions more openly during evening sessions. When facing uncertainty, you often explore multiple perspectives before settling on an interpretation.",
    date: "This week",
    category: "emotional",
    icon: Heart,
    color: "text-trait-empathetic",
  },
  {
    id: 2,
    title: "Decision-Making Approach",
    summary: "There's a noticeable balance between high expectations and self-compassion in how you discuss goals. You seem to prioritize meaningful outcomes over quick resolutions.",
    date: "This week",
    category: "behavioral",
    icon: Target,
    color: "text-trait-consistent",
  },
  {
    id: 3,
    title: "Reflection Depth Over Time",
    summary: "Your reflections have become more detailed over the past month. Earlier conversations tended to focus on events, while recent ones explore underlying beliefs and values more often.",
    date: "Last week",
    category: "growth",
    icon: TrendingUp,
    color: "text-primary",
  },
];

export function ReflectionsPage() {
  return (
    <div className="h-screen flex flex-col">
      <header className="px-8 py-6 border-b border-border">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold text-foreground">Reflections</h1>
              <TooltipProvider delayDuration={200}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button className="p-1 rounded hover:bg-muted/50 transition-colors">
                      <Info className="w-4 h-4 text-muted-foreground" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-xs bg-card border border-border">
                    <p className="text-xs text-muted-foreground">
                      Observations about your communication patterns over time. These are not assessments or advice.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <p className="text-sm text-muted-foreground">Observed patterns from recent conversations</p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted border border-border">
            <Calendar className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Past 30 days</span>
          </div>
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="p-8">
          <div className="max-w-3xl mx-auto">
            <div className="bg-gradient-to-br from-primary/5 via-card to-transparent border border-border rounded-2xl p-6 mb-8">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <Lightbulb className="w-6 h-6 text-primary" />
                </div>
                <div className="flex-1">
                  <h2 className="font-medium text-foreground mb-2">About Reflections</h2>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    These observations are based on patterns in your conversations. They describe how you've been 
                    communicating, not who you are. Patterns may shift over time as your context changes.
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-6">
              {reflections.map((reflection, index) => {
                const Icon = reflection.icon;
                return (
                  <div key={reflection.id} className="bg-card border border-border rounded-xl p-6 fade-in" style={{ animationDelay: `${index * 100}ms` }}>
                    <div className="flex items-start gap-4">
                      <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0", 
                        reflection.color === "text-trait-empathetic" ? "bg-trait-empathetic/10" :
                        reflection.color === "text-trait-consistent" ? "bg-trait-consistent/10" : "bg-primary/10"
                      )}>
                        <Icon className={cn("w-5 h-5", reflection.color)} />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-2">
                          <h3 className="font-medium text-foreground">{reflection.title}</h3>
                          <span className="text-xs text-muted-foreground">{reflection.date}</span>
                        </div>
                        <p className="text-sm text-muted-foreground leading-relaxed">{reflection.summary}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-8 text-center">
              <p className="text-xs text-muted-foreground/60">
                Based on patterns across multiple conversations
              </p>
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
