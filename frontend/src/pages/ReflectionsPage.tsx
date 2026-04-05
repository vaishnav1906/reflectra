import { useState, useEffect } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Lightbulb, TrendingUp, Heart, Target, Calendar, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { TimeRangeToggle } from "@/components/ui/TimeRangeToggle";
import { useReflections } from "@/hooks/useAnalytics";
import { formatDistanceToNow } from "date-fns";

export function ReflectionsPage() {
  const [userId, setUserId] = useState<string>("anonymous");
  const [timeRange, setTimeRange] = useState<'1d' | '2d' | '3d' | '7d' | '30d' | '90d'>('30d');

  useEffect(() => {
    const id = localStorage.getItem("user_id");
    if (id) setUserId(id);
  }, []);

  const { data: insightsData, isLoading } = useReflections(userId, timeRange);

  const getRangeLabel = (range: string) => {
    switch (range) {
      case '1d': return "Past 24 hours";
      case '2d': return "Past 48 hours";
      case '3d': return "Past 3 days";
      case '7d': return "This week";
      case '30d': return "This month";
      case '90d': return "Past 3 months";
      default: return "Selected period";
    }
  };

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
          <TimeRangeToggle value={timeRange} onChange={setTimeRange} />
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
                  <h2 className="font-medium text-foreground mb-2">About {getRangeLabel(timeRange)} Reflections</h2>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    These observations are based on patterns in your conversations over {timeRange === '1d' ? 'the past 24 hours' : timeRange === '2d' ? 'the past 48 hours' : timeRange === '3d' ? 'the past 3 days' : timeRange === '7d' ? 'the past 7 days' : timeRange === '30d' ? 'the past 30 days' : 'the past 90 days'}. They describe how you've been 
                    communicating, not who you are. Patterns may shift over time as your context changes.
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-6 min-h-[300px]">
              {userId === "anonymous" ? (
                <div className="p-8 text-center text-muted-foreground bg-card border border-border rounded-xl">
                  Please log in to view your personalized reflections.
                </div>
              ) : isLoading ? (
                <div className="space-y-4">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-32 animate-pulse bg-card border border-border rounded-xl w-full" />
                  ))}
                </div>
              ) : !insightsData || insightsData.length === 0 ? (
                 <div className="p-8 text-center text-muted-foreground bg-card border border-border rounded-xl">
                  No reflections found for {getRangeLabel(timeRange).toLowerCase()}. Keep chatting to generate insights!
                 </div>
              ) : (
                <div className="transition-opacity duration-300 space-y-4">
                  {insightsData.map((insight, index) => (
                    <div key={insight.id} className="bg-card border border-border rounded-xl p-6 transition-all hover:bg-muted/30 fade-in" style={{ animationDelay: `${index * 50}ms` }}>
                      <div className="flex items-start gap-4">
                        <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0", "bg-primary/10")}>
                          <Target className={cn("w-5 h-5", "text-primary")} />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center justify-between mb-2">
                            <h3 className="font-medium text-foreground">Behavioral Insight</h3>
                            <span className="text-xs text-muted-foreground">{formatDistanceToNow(new Date(insight.created_at), { addSuffix: true })}</span>
                          </div>
                          
                          {insight.tags && insight.tags.length > 0 && (
                            <div className="flex flex-wrap gap-2 mb-3">
                               {insight.tags.map((tag) => (
                                 <span key={tag} className={cn("px-2.5 py-1 rounded-full text-xs font-medium text-muted-foreground bg-muted/50 border border-border/50")}>
                                   {tag}
                                 </span>
                               ))}
                            </div>
                          )}

                          <p className="text-sm text-foreground leading-relaxed">{insight.text}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
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
