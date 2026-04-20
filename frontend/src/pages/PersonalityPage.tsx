import { useState, useEffect } from "react";
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

function getConfidenceLevel(confidence: number): "high" | "medium" | "low" {
  if (confidence >= 0.7) return "high";
  if (confidence >= 0.3) return "medium";
  return "low";
}

function mapTraitsToUI(profile: PersonaProfile | null): PersonaTrait[] {
  const defaultTraits: PersonaTrait[] = [
    { name: "Communication Style", leftLabel: "Concise", rightLabel: "Verbose", value: 50, confidence: "low", color: "#FA114F" },
    { name: "Emotional Expressiveness", leftLabel: "Reserved", rightLabel: "Expressive", value: 50, confidence: "low", color: "#00F0FF" },
    { name: "Decision Framing", leftLabel: "Hesitant", rightLabel: "Decisive", value: 50, confidence: "low", color: "#A4FF00" },
    { name: "Reflection Depth", leftLabel: "Surface", rightLabel: "Deep", value: 50, confidence: "low", color: "#FF00D6" },
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

  addTrait('communication_style', "Communication Style", "Concise", "Verbose", "#FA114F");
  addTrait('emotional_expressiveness', "Emotional Expressiveness", "Reserved", "Expressive", "#00F0FF");
  addTrait('decision_framing', "Decision Framing", "Hesitant", "Decisive", "#A4FF00");
  addTrait('reflection_depth', "Reflection Depth", "Surface", "Deep", "#FF00D6");

  return traits;
}

export function PersonalityPage() {
  const [profile, setProfile] = useState<PersonaProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ringValues, setRingValues] = useState<Record<string, number>>({});
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

  // Add a slight delay for the ring animation on mount
  useEffect(() => {
    if (!loading) {
      const timer = setTimeout(() => {
        const nextValues: Record<string, number> = {};
        personaTraits.forEach(t => {
          nextValues[t.name] = t.value <= 50 ? 100 - t.value : t.value;
        });
        setRingValues(nextValues);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [loading, profile]);

  // Timeline variables
  const timelineData = metricsData?.timeline || [];
  
  // To handle timezone safely mapping days
  const charData = timelineData.map(d => {
    const date = new Date(d.timestamp);
    const dayInitial = date.toLocaleDateString('en-US', { weekday: 'short' }).charAt(0);
    return { name: dayInitial, count: d.message_count };
  });

  const fullTimeline = charData.length > 0 ? charData : [{ name: "-", count: 0 }];
  const totalMessages = timelineData.reduce((sum, d) => sum + d.message_count, 0);
  const averageMessagesPerPeriod = totalMessages > 0 ? (totalMessages / timelineData.length).toFixed(1) : "0.0";

  return (
    <div className="h-screen flex flex-col bg-background text-foreground">
      <header className="px-8 py-6 border-b border-border">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold text-foreground">Persona Profile</h1>
              <TooltipProvider delayDuration={200}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button className="p-1 flex items-center justify-center rounded-full hover:bg-accent hover:text-accent-foreground transition-colors">
                      <Info className="w-5 h-5 text-muted-foreground" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-xs bg-popover border border-border text-popover-foreground text-xs">
                    <p>Observable communication patterns based on interactions over time.</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
          <PersonaMirrorInfo />
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="p-8">
          <div className="max-w-4xl mx-auto">
            
            <Tabs defaultValue="traits" className="w-full">
              <TabsList className="bg-muted/50 border border-border p-1 mb-10 inline-flex w-full md:w-auto h-auto rounded-full mt-2">
                <TabsTrigger 
                  value="traits" 
                  className="px-8 py-3 rounded-full text-sm font-black uppercase tracking-widest text-muted-foreground data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm transition-all"
                >
                  Traits
                </TabsTrigger>
                <TabsTrigger 
                  value="timeline" 
                  className="px-8 py-3 rounded-full text-sm font-black uppercase tracking-widest text-muted-foreground data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm transition-all"
                >
                  Timeline
                </TabsTrigger>
              </TabsList>

              <TabsContent value="traits" className="space-y-8 outline-none animate-in fade-in slide-in-from-bottom-4 duration-700">
                {loading ? (
                  <div className="flex justify-center items-center h-64">
                    <Loader2 className="w-12 h-12 text-primary animate-spin" />
                  </div>
                ) : error ? (
                   <div className="text-center p-12 border border-border rounded-3xl bg-card">
                    <p className="text-muted-foreground font-medium">{error}</p>
                   </div>
                ) : (
                  <>
                     <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {personaTraits.map((trait) => (
                        <div key={trait.name} className="relative bg-card border border-border rounded-[2rem] p-10 flex flex-col items-center text-center group transition-colors overflow-hidden">
                          
                          {/* Faint background beam */}
                          <div 
                            className="absolute inset-0 opacity-0 group-hover:opacity-10 transition-opacity duration-700 pointer-events-none"
                            style={{ backgroundImage: `radial-gradient(circle at center, ${trait.color} 0%, transparent 60%)` }}
                          />

                          <FitnessRing 
                            value={ringValues[trait.name] || 0} 
                            color={trait.color} 
                            size={180} 
                            strokeWidth={18} 
                            className="mb-8" 
                          >
                             <div className="flex flex-col items-center">
                                <span className="text-3xl font-black tabular-nums tracking-tighter" style={{ color: trait.color, filter: `drop-shadow(0 0 8px ${trait.color}66)` }}>
                                  {ringValues[trait.name] || 0}%
                                </span>
                                <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">MATCH</span>
                             </div>
                          </FitnessRing>
                          
                          <h3 className="font-bold text-xl mb-1 text-foreground tracking-tight">{trait.name}</h3>
                          <div className="flex items-center justify-between w-full mt-4 text-xs font-black uppercase tracking-widest">
                             <span className={`transition-colors ${trait.value <= 50 ? 'text-foreground drop-shadow-md' : 'text-muted-foreground'}`} style={trait.value <= 50 ? { color: trait.color } : {}}>
                                {trait.leftLabel}
                             </span>
                             <span className={`transition-colors ${trait.value > 50 ? 'text-foreground drop-shadow-md' : 'text-muted-foreground'}`} style={trait.value > 50 ? { color: trait.color } : {}}>
                                {trait.rightLabel}
                             </span>
                          </div>
                        </div>
                      ))}
                    </div>
                    
                    <div className="bg-card border border-border rounded-[2rem] p-8 flex items-center justify-between">
                      <div className="max-w-2xl">
                        <p className="text-xs uppercase font-black tracking-widest text-muted-foreground mb-3">Diagnostic Summary</p>
                        <h2 className="text-xl font-medium leading-relaxed text-foreground">
                          {profile?.summary || "Based on your recent interactions, you show balanced communication patterns."}
                        </h2>
                      </div>
                      {profile && profile.stability !== undefined && (
                        <div className="text-right pl-6 border-l border-border">
                          <p className="text-5xl font-black tabular-nums tracking-tighter text-foreground">
                            {Math.round(profile.stability * 100)}<span className="text-2xl text-muted-foreground">%</span>
                          </p>
                          <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground mt-2">Stability</p>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </TabsContent>

              <TabsContent value="timeline" className="space-y-8 outline-none animate-in fade-in slide-in-from-bottom-4 duration-700">
                 {isLoadingMetrics ? (
                   <div className="flex justify-center items-center h-64">
                    <Loader2 className="w-12 h-12 text-primary animate-spin" />
                   </div>
                ) : (
                  <div className="bg-card border border-border rounded-[2.5rem] p-10 relative overflow-hidden">
                    <div className="flex justify-end mb-6">
                      <div className="flex bg-muted rounded-lg p-1 border border-border">
                        {([
                          { label: "Last 7 days", value: "week" as const },
                          { label: "Last 30 days", value: "month" as const },
                          { label: "All time", value: "all" as const },
                        ]).map((option) => (
                          <button
                            key={option.value}
                            onClick={() => setTimelineView(option.value)}
                            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                              timelineView === option.value
                                ? "bg-background text-foreground shadow-sm"
                                : "text-muted-foreground hover:text-foreground"
                            }`}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Ring Tracker */}
                    <div className="mb-10 w-full overflow-x-auto">
                      <div className="flex gap-4 min-w-max pb-2">
                      {fullTimeline.map((d, i) => (
                        <div key={i} className="flex flex-col items-center gap-3">
                           <FitnessRing
                             value={Math.min(((d.count || 0.1) / Math.max(parseFloat(averageMessagesPerPeriod), 1)) * 50, 100)} 
                             size={36}
                             strokeWidth={6}
                             color="#A4FF00"
                             backgroundColor="#18181b"
                           />
                           <span className="text-[10px] font-black text-muted-foreground uppercase">{d.name}</span>
                        </div>
                      ))}
                      </div>
                    </div>

                    <div className="mb-16">
                      <h3 className="text-xs font-black uppercase tracking-widest text-muted-foreground mb-4">Daily Average</h3>
                      <div className="flex items-baseline gap-2">
                        <span className="text-[5rem] font-black tracking-tighter leading-none text-[#A4FF00] drop-shadow-[0_0_12px_rgba(164,255,0,0.3)]">
                          {averageMessagesPerPeriod}
                        </span>
                        <span className="text-2xl font-black tracking-widest text-[#A4FF00]/60">
                          MSG
                        </span>
                      </div>
                    </div>

                    {/* Chart Container */}
                    <div className="w-full relative z-10" style={{ marginLeft: '-15px' }}>
                      <CapsuleBarChart 
                        data={fullTimeline}
                        dataKey="count"
                        color="#A4FF00"
                        height={400}
                      />
                    </div>
                  </div>
                )}
              </TabsContent>

            </Tabs>

            <div className="mt-8 mb-16">
              <TimetableSection />
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
