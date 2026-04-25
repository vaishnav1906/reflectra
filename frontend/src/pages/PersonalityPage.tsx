import { useState, useEffect, useMemo } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PersonaMirrorInfo } from "@/components/persona/PersonaMirrorInfo";
import { Info, Loader2 } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { FitnessRing } from "@/components/ui/FitnessRing";
import { CapsuleBarChart } from "@/components/ui/CapsuleBarChart";
import { useBehavioralMetrics } from "@/hooks/useAnalytics";
import { TimetableSection } from "@/components/timetable/TimetableSection";

const API_BASE = "/api";

interface PersonaTrait {
  name: string;
  leftLabel: string;
  rightLabel: string;
  value: number;
  confidence: "high" | "medium" | "low";
  color: string;
}

interface PersonaProfile {
  traits?: Record<string, { score: number; confidence: number }>;
  stability: number;
  summary: string;
}

const traitThemes: Record<string, string> = {
  "Communication Style": "hsl(var(--trait-analytical))",
  "Emotional Expressiveness": "hsl(var(--trait-empathetic))",
  "Decision Framing": "hsl(var(--trait-consistent))",
  "Reflection Depth": "hsl(var(--trait-introspective))",
};

const confidenceThemes = {
  high: "border-white/10 bg-primary/10 text-primary",
  medium: "border-white/10 bg-muted text-foreground",
  low: "border-white/10 bg-muted/80 text-muted-foreground",
} as const;

const confidenceDotThemes = {
  high: "bg-primary",
  medium: "bg-foreground/70",
  low: "bg-muted-foreground",
} as const;

function getConfidenceLevel(confidence: number): "high" | "medium" | "low" {
  if (confidence >= 0.7) return "high";
  if (confidence >= 0.3) return "medium";
  return "low";
}

function mapTraitsToUI(profile: PersonaProfile | null): PersonaTrait[] {
  const defaultTraits: PersonaTrait[] = [
    { name: "Communication Style", leftLabel: "Concise", rightLabel: "Verbose", value: 50, confidence: "low", color: "#ff6f97" },
    { name: "Emotional Expressiveness", leftLabel: "Reserved", rightLabel: "Expressive", value: 50, confidence: "low", color: "#76d6e8" },
    { name: "Decision Framing", leftLabel: "Hesitant", rightLabel: "Decisive", value: 50, confidence: "low", color: "#bfdc7a" },
    { name: "Reflection Depth", leftLabel: "Surface", rightLabel: "Deep", value: 50, confidence: "low", color: "#d696f2" },
  ];

  if (!profile || !profile.traits) return defaultTraits;

  const { traits: behavioral_profile } = profile;
  const traits: PersonaTrait[] = [];

  const addTrait = (key: string, name: string, leftLabel: string, rightLabel: string, color: string) => {
    const data = behavioral_profile[key];
    if (data) {
      traits.push({
        name,
        leftLabel,
        rightLabel,
        value: Math.round(data.score * 100),
        confidence: getConfidenceLevel(data.confidence),
        color
      });
    } else {
      traits.push(defaultTraits.find(t => t.name === name)!);
    }
  };

  addTrait('communication_style', "Communication Style", "Concise", "Verbose", "#ff6f97");
  addTrait('emotional_expressiveness', "Emotional Expressiveness", "Reserved", "Expressive", "#76d6e8");
  addTrait('decision_framing', "Decision Framing", "Hesitant", "Decisive", "#bfdc7a");
  addTrait('reflection_depth', "Reflection Depth", "Surface", "Deep", "#d696f2");

  return traits;
}

export function PersonalityPage() {
  const [profile, setProfile] = useState<PersonaProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timelineView, setTimelineView] = useState<"week" | "month" | "all">("all");
  
  const userId = localStorage.getItem("user_id") || "anonymous";
  const { data: metricsData, isLoading: isLoadingMetrics } = useBehavioralMetrics(userId, timelineView);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        setLoading(true);
        setError(null);
        
        let targetId = userId;
        // Try fallback if user_id is not set. 
        if (targetId === "anonymous") {
           targetId = localStorage.getItem("user_id") || "anonymous";
        }
        
        if (targetId === "anonymous") {
          throw new Error("No user ID found. Please log in.");
        }

        const response = await fetch(`${API_BASE}/persona/profile/${targetId}`);
        if (!response.ok) {
          if (response.status === 404) {
            throw new Error("Building personality model... Start reflecting to build your profile!");
          }
          throw new Error(`Failed to fetch profile: ${response.statusText}`);
        }

        const data = await response.json();
        setProfile(data);
      } catch (err) {
        console.error("Error fetching persona profile:", err);
        setError(err instanceof Error ? err.message : "Failed to load profile");
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  }, [userId]);

  const personaTraits = mapTraitsToUI(profile);
  const heroStats = [
    {
      label: "Traits",
      value: personaTraits.length.toString(),
    },
    {
      label: "Stability",
      value: profile ? `${Math.round(profile.stability * 100)}%` : "—",
    },
    {
      label: "View",
      value: timelineView === "all" ? "All time" : timelineView === "month" ? "30 days" : "7 days",
    },
  ];

  // Timeline variables
  const timelineData = metricsData?.timeline || [];

  const normalizedTimelineData = useMemo(() => {
    if (timelineView !== "all") {
      return timelineData;
    }

    const monthlyBuckets = new Map<string, { timestamp: string; message_count: number }>();

    for (const point of timelineData) {
      const date = new Date(point.timestamp);
      const monthKey = `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
      const monthTimestamp = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1)).toISOString();
      const existing = monthlyBuckets.get(monthKey);

      if (existing) {
        existing.message_count += point.message_count;
      } else {
        monthlyBuckets.set(monthKey, {
          timestamp: monthTimestamp,
          message_count: point.message_count,
        });
      }
    }

    return Array.from(monthlyBuckets.values()).sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
  }, [timelineData, timelineView]);

  const chartData = normalizedTimelineData.map((d) => {
    const date = new Date(d.timestamp);
    const label =
      timelineView === "all"
        ? date.toLocaleDateString("en-US", { month: "short", year: "2-digit" })
        : date.toLocaleDateString("en-US", { weekday: "short" }).charAt(0);

    return { name: label, count: d.message_count };
  });

  const fullTimeline = chartData.length > 0 ? chartData : [{ name: "-", count: 0 }];
  const totalMessages = normalizedTimelineData.reduce((sum, d) => sum + d.message_count, 0);
  const averageMessagesPerPeriod = totalMessages > 0 ? (totalMessages / normalizedTimelineData.length).toFixed(1) : "0.0";

  return (
    <div className="relative h-screen flex flex-col overflow-hidden bg-background text-foreground">
      <div className="pointer-events-none absolute -left-28 top-8 h-72 w-72 rounded-full bg-primary/12 blur-3xl" />
      <div className="pointer-events-none absolute -right-24 top-12 h-72 w-72 rounded-full bg-accent/10 blur-3xl" />
      <div className="pointer-events-none absolute bottom-14 left-1/3 h-64 w-64 rounded-full bg-primary/6 blur-3xl" />
      <ScrollArea className="h-screen">
        <div className="relative z-10 mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-6 lg:px-8 lg:py-8">
          <header className="gradient-card rounded-[1.75rem] border border-border/70 px-7 py-7 shadow-[0_18px_44px_rgba(0,0,0,0.2)] backdrop-blur-sm">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl space-y-3">
                <p className="text-[10px] uppercase tracking-[0.38em] text-muted-foreground">Behavioral portrait</p>
                <div className="flex items-center gap-2">
                  <h1 className="text-2xl font-semibold tracking-tight text-foreground md:text-3xl">Persona Profile</h1>
                  <TooltipProvider delayDuration={200}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button className="flex h-8 w-8 items-center justify-center rounded-full border border-border/80 bg-background/70 text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground">
                          <Info className="h-4 w-4" />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="max-w-xs border border-border bg-popover text-xs text-popover-foreground">
                        <p>Observable communication patterns based on interactions over time.</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
                  A composed snapshot of how you communicate over time, presented with clarity and calm visual hierarchy.
                </p>
              </div>

              <div className="flex flex-col gap-4 lg:items-end">
                <PersonaMirrorInfo />
                <div className="grid grid-cols-3 gap-3">
                  {heroStats.map((stat) => (
                    <div key={stat.label} className="rounded-xl border border-border/80 bg-background/55 px-4 py-3 shadow-sm backdrop-blur-sm transition-all duration-300 hover:border-primary/35 hover:shadow-md">
                      <p className="text-[10px] uppercase tracking-[0.32em] text-muted-foreground">{stat.label}</p>
                      <p className="mt-1 text-base font-semibold text-foreground">{stat.value}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </header>

          <Tabs defaultValue="traits" className="w-full">
            <TabsList className="mb-8 inline-flex h-auto w-full rounded-xl border border-border/70 bg-card/75 p-1 shadow-sm backdrop-blur-sm md:w-auto">
                <TabsTrigger
                  value="traits"
                  className="rounded-lg px-6 py-3 text-xs font-medium uppercase tracking-[0.28em] text-muted-foreground transition-all data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-md"
                >
                  Traits
                </TabsTrigger>
                <TabsTrigger
                  value="timeline"
                  className="rounded-lg px-6 py-3 text-xs font-medium uppercase tracking-[0.28em] text-muted-foreground transition-all data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-md"
                >
                  Timeline
                </TabsTrigger>
            </TabsList>

            <TabsContent value="traits" className="space-y-8 outline-none animate-in fade-in slide-in-from-bottom-4 duration-700">
              {loading ? (
                <div className="flex h-72 items-center justify-center rounded-xl border border-border bg-card">
                    <Loader2 className="h-11 w-11 animate-spin text-primary" />
                </div>
              ) : error ? (
                <div className="rounded-xl border border-border bg-card p-10 text-center">
                    <p className="text-muted-foreground">{error}</p>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                    {personaTraits.map((trait) => {
                      const accent = traitThemes[trait.name] ?? "hsl(var(--primary))";

                      return (
                        <article
                          key={trait.name}
                          className="group relative overflow-hidden rounded-2xl border border-border/75 gradient-card p-6 shadow-[0_12px_30px_rgba(0,0,0,0.2)] transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/35 hover:shadow-[0_20px_38px_rgba(0,0,0,0.24)]"
                        >
                          <div
                            className="pointer-events-none absolute inset-x-0 top-0 h-16 opacity-60"
                            style={{ background: `linear-gradient(180deg, ${accent}22 0%, transparent 100%)` }}
                          />

                          <div className="relative flex items-start justify-between gap-4">
                            <div>
                              <p className="text-[10px] uppercase tracking-[0.32em] text-muted-foreground">Trait profile</p>
                              <h3 className="mt-2 text-[1.95rem] font-medium tracking-tight leading-none text-foreground">{trait.name}</h3>
                            </div>

                            <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[10px] font-medium uppercase tracking-[0.24em] ${confidenceThemes[trait.confidence]}`}>
                              <span className={`h-1.5 w-1.5 rounded-full ${confidenceDotThemes[trait.confidence]}`} />
                              {trait.confidence} confidence
                            </span>
                          </div>

                          <div className="relative mt-6">
                            <div className="mb-2 flex items-center justify-between text-[10px] uppercase tracking-[0.28em] text-muted-foreground">
                              <span>{trait.leftLabel}</span>
                              <span>{trait.rightLabel}</span>
                            </div>

                            <div className="relative">
                              <div className="h-2 rounded-full bg-muted/90" />
                              <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border" />
                              <div
                                className="absolute top-0 h-2 rounded-full opacity-70"
                                style={{
                                  width: `${Math.abs(trait.value - 50)}%`,
                                  left: trait.value >= 50 ? "50%" : undefined,
                                  right: trait.value < 50 ? "50%" : undefined,
                                  background: trait.value >= 50
                                    ? `linear-gradient(90deg, transparent 0%, ${accent} 100%)`
                                    : `linear-gradient(90deg, ${accent} 0%, transparent 100%)`,
                                }}
                              />
                              <div
                                className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background shadow-sm transition-transform duration-300 group-hover:scale-110"
                                style={{
                                  left: `${trait.value}%`,
                                  backgroundColor: accent,
                                  boxShadow: `0 0 0 7px ${accent}22`,
                                }}
                              />
                            </div>
                          </div>

                          <div className="mt-5 flex items-end justify-between gap-4">
                            <p className="text-sm text-muted-foreground">
                              Position: <span className="font-medium text-foreground">{trait.value}%</span> from {trait.leftLabel} to {trait.rightLabel}
                            </p>
                            <p className="text-sm font-medium uppercase tracking-[0.24em]" style={{ color: accent }}>
                              {trait.value === 50 ? "Balanced" : `Leans ${trait.value > 50 ? trait.rightLabel : trait.leftLabel}`}
                            </p>
                          </div>
                        </article>
                      );
                    })}
                  </div>

                  <div className="rounded-2xl border border-border/75 gradient-card p-7 shadow-[0_12px_30px_rgba(0,0,0,0.18)]">
                    <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
                      <div className="max-w-3xl space-y-3">
                        <p className="text-[10px] uppercase tracking-[0.32em] text-muted-foreground">Diagnostic summary</p>
                        <h2 className="text-2xl font-medium leading-relaxed text-foreground text-balance">
                          {profile?.summary || "Based on your recent interactions, you show balanced communication patterns."}
                        </h2>
                      </div>

                      {profile && profile.stability !== undefined && (
                        <div className="rounded-2xl border border-border/70 bg-background/45 px-7 py-6 shadow-inner lg:min-w-[190px] lg:text-right">
                          <p className="text-5xl font-semibold tabular-nums tracking-tight text-foreground">
                            {Math.round(profile.stability * 100)}<span className="text-xl text-muted-foreground">%</span>
                          </p>
                          <p className="mt-2 text-[10px] uppercase tracking-[0.32em] text-muted-foreground">Stability</p>
                        </div>
                      )}
                    </div>
                  </div>
                </>
              )}
            </TabsContent>

            <TabsContent value="timeline" className="space-y-8 outline-none animate-in fade-in slide-in-from-bottom-4 duration-700">
              {isLoadingMetrics ? (
                <div className="flex h-72 items-center justify-center rounded-xl border border-border bg-card">
                  <Loader2 className="h-11 w-11 animate-spin text-primary" />
                </div>
              ) : (
                <div className="rounded-2xl border border-border/75 gradient-card p-6 shadow-[0_12px_30px_rgba(0,0,0,0.18)]">
                  <div className="mb-6 flex justify-end">
                    <div className="flex rounded-lg border border-border/70 bg-background/45 p-1">
                      {[
                        { label: "Last 7 days", value: "week" as const },
                        { label: "Last 30 days", value: "month" as const },
                        { label: "All time", value: "all" as const },
                      ].map((option) => (
                        <button
                          key={option.value}
                          onClick={() => setTimelineView(option.value)}
                          className={`rounded-md px-4 py-2 text-xs font-medium uppercase tracking-[0.24em] transition-all ${
                            timelineView === option.value
                              ? "bg-background text-foreground shadow-md"
                              : "text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="mb-8 w-full overflow-x-auto">
                    <div className="flex min-w-max gap-4 pb-2">
                      {fullTimeline.map((d, i) => (
                        <div key={i} className="flex flex-col items-center gap-3">
                          <FitnessRing
                            value={Math.min(((d.count || 0.1) / Math.max(parseFloat(averageMessagesPerPeriod), 1)) * 50, 100)}
                            size={36}
                            strokeWidth={6}
                            color="hsl(var(--primary))"
                            backgroundColor="hsl(var(--muted))"
                          />
                          <span className="text-[10px] font-medium uppercase tracking-[0.28em] text-muted-foreground">{d.name}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mb-10">
                    <h3 className="mb-3 text-[10px] font-medium uppercase tracking-[0.32em] text-muted-foreground">Daily average</h3>
                    <div className="flex items-baseline gap-3">
                      <span className="text-5xl font-semibold tracking-tight leading-none text-primary drop-shadow-[0_0_14px_hsl(var(--primary)/0.22)]">
                        {averageMessagesPerPeriod}
                      </span>
                      <span className="text-sm font-medium uppercase tracking-[0.28em] text-muted-foreground">msg</span>
                    </div>
                  </div>

                  <div className="relative z-10 w-full" style={{ marginLeft: "-15px" }}>
                    <CapsuleBarChart
                      data={fullTimeline}
                      dataKey="count"
                      color="hsl(var(--primary))"
                      height={400}
                    />
                  </div>
                </div>
              )}
            </TabsContent>
          </Tabs>

          <div className="pb-16">
            <TimetableSection />
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
