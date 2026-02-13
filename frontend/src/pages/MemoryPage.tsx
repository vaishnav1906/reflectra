import { ScrollArea } from "@/components/ui/scroll-area";
import { PatternHighlight } from "@/components/timeline/PatternHighlight";
import { Search, Calendar, Info } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const patternHighlights = [
  {
    period: "This week",
    observation: "More hesitation than usual in decision-related topics",
    trend: "up" as const,
    context: "Coincides with upcoming project deadline",
  },
  {
    period: "This week",
    observation: "Shorter reflection entries on high-class days",
    trend: "down" as const,
    context: "4+ classes correlated with briefer responses",
  },
  {
    period: "Last week",
    observation: "Higher emotional expressiveness during evening sessions",
    trend: "up" as const,
  },
  {
    period: "Last week",
    observation: "Deeper reflection depth when discussing career topics",
    trend: "up" as const,
    context: "Topic persisted across 3 sessions",
  },
  {
    period: "2 weeks ago",
    observation: "Communication style shifted toward more concise expressions",
    trend: "stable" as const,
  },
  {
    period: "2 weeks ago",
    observation: "Lower engagement during exam preparation period",
    trend: "down" as const,
    context: "Returned to baseline after exams ended",
  },
  {
    period: "3 weeks ago",
    observation: "Increased introspection following weekend break",
    trend: "up" as const,
  },
];

export function MemoryPage() {
  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <header className="px-8 py-6 border-b border-border">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold text-foreground">Timeline</h1>
              <TooltipProvider delayDuration={200}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button className="p-1 rounded hover:bg-muted/50 transition-colors">
                      <Info className="w-4 h-4 text-muted-foreground" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-xs bg-card border border-border">
                    <p className="text-xs text-muted-foreground">
                      Pattern highlights from your recent interactions. Not analytics—just observations.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <p className="text-sm text-muted-foreground">
              Recent patterns and observations
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search patterns..."
                className="bg-card border border-border rounded-lg pl-9 pr-4 py-2 text-sm focus:outline-none focus:border-primary/50 w-56"
              />
            </div>
            <button className="p-2 bg-card border border-border rounded-lg hover:bg-muted transition-colors">
              <Calendar className="w-4 h-4 text-muted-foreground" />
            </button>
          </div>
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="p-8">
          <div className="max-w-2xl mx-auto">
            {/* Summary */}
            <div className="bg-gradient-to-br from-primary/5 via-card to-transparent border border-border rounded-xl p-5 mb-8">
              <h2 className="font-medium text-foreground mb-2">Recent Overview</h2>
              <p className="text-sm text-muted-foreground">
                Over the past few weeks, your communication has shown some variation tied to workload. 
                Hesitation increases near deadlines, while reflection depth tends to be higher during calmer periods.
              </p>
            </div>

            {/* Pattern Highlights */}
            <div className="space-y-4">
              {patternHighlights.map((highlight, index) => (
                <PatternHighlight key={index} {...highlight} />
              ))}
            </div>

            {/* Footer note */}
            <div className="mt-8 text-center">
              <p className="text-xs text-muted-foreground/60">
                Patterns are observed across interactions, not individual sessions
              </p>
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
