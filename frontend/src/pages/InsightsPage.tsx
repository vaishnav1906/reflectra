import { ScrollArea } from "@/components/ui/scroll-area";
import { TrendingUp, TrendingDown, Minus, Calendar, Activity } from "lucide-react";
import { cn } from "@/lib/utils";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { ExplainabilityDialog } from "@/components/ui/ExplainabilityDialog";
import { PipelineIndicator } from "@/components/insights/PipelineIndicator";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar } from "recharts";

const moodData = [
  { day: "Mon", positive: 72, neutral: 20, challenging: 8 },
  { day: "Tue", positive: 65, neutral: 25, challenging: 10 },
  { day: "Wed", positive: 80, neutral: 15, challenging: 5 },
  { day: "Thu", positive: 55, neutral: 30, challenging: 15 },
  { day: "Fri", positive: 78, neutral: 18, challenging: 4 },
  { day: "Sat", positive: 85, neutral: 12, challenging: 3 },
  { day: "Sun", positive: 90, neutral: 8, challenging: 2 },
];

const topicData = [
  { topic: "Vocational", sessions: 18 },
  { topic: "Interpersonal", sessions: 14 },
  { topic: "Development", sessions: 22 },
  { topic: "Creative", sessions: 9 },
  { topic: "Wellbeing", sessions: 6 },
];

const weeklyStats = [
  { label: "Interactions", value: "23", change: 12, trend: "up" as const },
  { label: "Avg. Depth Score", value: "8.4", change: 5, trend: "up" as const },
  { label: "Reflective Episodes", value: "47", change: -3, trend: "down" as const },
  { label: "Insights Generated", value: "12", change: 0, trend: "neutral" as const },
];

const observations = [
  {
    title: "Peak engagement: Sunday evening temporal window",
    description: "Highest introspective depth and disclosure metrics occur consistently in Sunday 19:00-21:00 window across 12-week sample.",
    significance: "high",
    explanation: "Derived from temporal analysis of session depth scores and emotional disclosure metrics.",
    sources: [
      { type: "temporal" as const, description: "Time-of-day correlation with depth metrics", weight: 60 },
      { type: "behavioral" as const, description: "Topic complexity and session duration patterns", weight: 40 },
    ],
  },
  {
    title: "Vocational uncertainty correlates with creative ideation",
    description: "Career-related anxiety discussions show 78% co-occurrence with creative project exploration. Potential adaptive coping mechanism.",
    significance: "medium",
    explanation: "Computed from topic co-occurrence analysis and sentiment trajectory patterns.",
    sources: [
      { type: "semantic" as const, description: "Topic clustering and transition analysis", weight: 50 },
      { type: "behavioral" as const, description: "Affect state before/after creative topic engagement", weight: 50 },
    ],
  },
];

export function InsightsPage() {
  return (
    <div className="h-screen flex flex-col">
      <header className="px-8 py-6 border-b border-border">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold text-foreground">Behavioral Analytics</h1>
              <InfoTooltip content="Quantitative analysis of interaction patterns and behavioral metrics" side="right" />
            </div>
            <p className="text-sm text-muted-foreground">Temporal patterns, topic distributions, and behavioral observations</p>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 bg-card border border-border rounded-lg text-sm hover:bg-muted transition-colors">
            <Calendar className="w-4 h-4" />
            Current Cycle
          </button>
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="p-8">
          <div className="max-w-6xl mx-auto space-y-8">
            {/* Analytics Engine Info */}
            <div className="bg-gradient-to-br from-primary/5 via-card to-transparent border border-border rounded-2xl p-6">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <Activity className="w-5 h-5 text-primary" />
                </div>
                <div className="flex-1">
                  <h2 className="font-semibold text-foreground mb-2">Analytics Engine</h2>
                  <p className="text-sm text-muted-foreground mb-3">
                    Behavioral metrics are computed through automated pattern detection and statistical aggregation pipelines.
                  </p>
                  <PipelineIndicator variant="insight" />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {weeklyStats.map((stat) => (
                <div key={stat.label} className="bg-card border border-border rounded-xl p-5">
                  <p className="text-sm text-muted-foreground mb-1">{stat.label}</p>
                  <div className="flex items-end justify-between">
                    <p className="text-3xl font-bold text-foreground">{stat.value}</p>
                    <div className={cn("flex items-center gap-1 text-xs font-medium",
                      stat.trend === "up" ? "text-green-500" : stat.trend === "down" ? "text-red-400" : "text-muted-foreground"
                    )}>
                      {stat.trend === "up" ? <TrendingUp className="w-3 h-3" /> : stat.trend === "down" ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
                      {stat.change !== 0 && `${stat.change > 0 ? '+' : ''}${stat.change}%`}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-card border border-border rounded-xl p-6">
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="font-semibold text-foreground">Affective State Distribution</h3>
                  <InfoTooltip content="Sentiment classification across daily interaction windows" />
                </div>
                <p className="text-sm text-muted-foreground mb-6">Weekly affect patterns</p>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={moodData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                      <XAxis dataKey="day" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                      <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                      <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px" }} />
                      <Area type="monotone" dataKey="positive" stackId="1" stroke="hsl(var(--trait-consistent))" fill="hsl(var(--trait-consistent) / 0.3)" />
                      <Area type="monotone" dataKey="neutral" stackId="1" stroke="hsl(var(--muted-foreground))" fill="hsl(var(--muted) / 0.5)" />
                      <Area type="monotone" dataKey="challenging" stackId="1" stroke="hsl(var(--trait-empathetic))" fill="hsl(var(--trait-empathetic) / 0.3)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="bg-card border border-border rounded-xl p-6">
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="font-semibold text-foreground">Topic Domain Distribution</h3>
                  <InfoTooltip content="Semantic categorization of discussion themes" />
                </div>
                <p className="text-sm text-muted-foreground mb-6">Current analysis period</p>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={topicData} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                      <XAxis type="number" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                      <YAxis dataKey="topic" type="category" stroke="hsl(var(--muted-foreground))" fontSize={12} width={80} />
                      <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px" }} />
                      <Bar dataKey="sessions" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            <div className="bg-card border border-border rounded-xl p-6">
              <div className="flex items-center gap-2 mb-4">
                <h3 className="font-semibold text-foreground">Derived Observations</h3>
                <InfoTooltip content="Pattern-based insights with explainability metadata" />
              </div>
              <div className="space-y-4">
                {observations.map((obs, index) => (
                  <div key={index} className="flex items-start gap-4 p-4 rounded-lg bg-muted/30 border border-border/50">
                    <div className={cn("w-2 h-2 rounded-full mt-2 flex-shrink-0", obs.significance === "high" ? "bg-accent" : "bg-primary")} />
                    <div className="flex-1">
                      <h4 className="font-medium text-foreground mb-1">{obs.title}</h4>
                      <p className="text-sm text-muted-foreground mb-2">{obs.description}</p>
                      <ExplainabilityDialog title={obs.title} explanation={obs.explanation} sources={obs.sources} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="text-center py-4">
              <p className="text-xs text-muted-foreground/60">Analysis based on 156 interactions over 90-day window • Pipeline latency: 180ms</p>
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
