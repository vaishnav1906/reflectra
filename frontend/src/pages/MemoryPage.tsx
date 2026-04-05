import { useEffect, useMemo, useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PatternHighlight } from "@/components/timeline/PatternHighlight";
import { Search, Calendar, Info } from "lucide-react";
import { useTimelineEvents, type TimelineEvent, type TimelineRange } from "@/hooks/useAnalytics";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

function includesSearch(event: TimelineEvent, query: string) {
  if (!query.trim()) {
    return true;
  }

  const normalized = query.trim().toLowerCase();
  const haystack = [
    event.observation,
    event.context || "",
    event.source,
    ...event.tags,
  ]
    .join(" ")
    .toLowerCase();

  return haystack.includes(normalized);
}

export function MemoryPage() {
  const [userId, setUserId] = useState<string>("anonymous");
  const [timeRange, setTimeRange] = useState<TimelineRange>("7d");
  const [searchQuery, setSearchQuery] = useState<string>("");

  useEffect(() => {
    const id = localStorage.getItem("user_id");
    if (id) {
      setUserId(id);
    }
  }, []);

  const { data, isLoading, isError } = useTimelineEvents(userId, timeRange);

  const filteredEvents = useMemo(() => {
    const events = data?.events || [];
    return events.filter((event) => includesSearch(event, searchQuery));
  }, [data?.events, searchQuery]);

  const overviewText =
    data?.overview ||
    "Patterns are generated from conversation context and persona traits as activity accumulates.";

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
                      Pattern highlights generated from conversations, persona traits, and context signals.
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
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                className="bg-card border border-border rounded-lg pl-9 pr-4 py-2 text-sm focus:outline-none focus:border-primary/50 w-56"
              />
            </div>
            <div className="relative p-2 bg-card border border-border rounded-lg hover:bg-muted transition-colors">
              <Calendar className="w-4 h-4 text-muted-foreground" />
              <select
                aria-label="Timeline range"
                value={timeRange}
                onChange={(event) => setTimeRange(event.target.value as TimelineRange)}
                className="absolute inset-0 opacity-0 cursor-pointer"
              >
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
                <option value="90d">Last 90 days</option>
              </select>
            </div>
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
                {overviewText}
              </p>
            </div>

            {/* Pattern Highlights */}
            {userId === "anonymous" ? (
              <div className="bg-card border border-border rounded-xl p-6 text-sm text-muted-foreground">
                Please log in to generate your timeline automatically.
              </div>
            ) : isLoading ? (
              <div className="space-y-4">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div key={index} className="h-24 rounded-xl border border-border bg-card animate-pulse" />
                ))}
              </div>
            ) : isError ? (
              <div className="bg-card border border-border rounded-xl p-6 text-sm text-muted-foreground">
                Unable to load timeline right now. Try refreshing in a moment.
              </div>
            ) : filteredEvents.length > 0 ? (
              <div className="space-y-4">
                {filteredEvents.map((event) => (
                  <PatternHighlight
                    key={event.id}
                    period={event.period}
                    observation={event.observation}
                    trend={event.trend}
                    context={event.context}
                  />
                ))}
              </div>
            ) : (
              <div className="bg-card border border-border rounded-xl p-6 text-sm text-muted-foreground">
                No timeline entries match your current filter.
              </div>
            )}

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
