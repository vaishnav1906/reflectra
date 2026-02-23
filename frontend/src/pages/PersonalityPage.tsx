import { useState, useEffect } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PersonaTraitCard } from "@/components/persona/PersonaTraitCard";
import { PersonaMirrorInfo } from "@/components/persona/PersonaMirrorInfo";
import { TimetableSection } from "@/components/timetable/TimetableSection";
import { User, Info, Loader2 } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const API_BASE = "/api";

interface PersonaTrait {
  name: string;
  leftLabel: string;
  rightLabel: string;
  value: number;
  confidence: "high" | "medium" | "low";
}

interface PersonaProfile {
  persona_vector: {
    behavioral_profile?: Record<string, { score: number; confidence: number }>;
  };
  stability_index: number;
  summary: string;
}

function getConfidenceLevel(confidence: number): "high" | "medium" | "low" {
  if (confidence >= 0.7) return "high";
  if (confidence >= 0.3) return "medium";
  return "low";
}

function mapTraitsToUI(profile: PersonaProfile | null): PersonaTrait[] {
  // Default traits if no profile exists
  const defaultTraits: PersonaTrait[] = [
    {
      name: "Communication Style",
      leftLabel: "Concise",
      rightLabel: "Verbose",
      value: 50,
      confidence: "low",
    },
    {
      name: "Emotional Expressiveness",
      leftLabel: "Reserved",
      rightLabel: "Expressive",
      value: 50,
      confidence: "low",
    },
    {
      name: "Decision Framing",
      leftLabel: "Hesitant",
      rightLabel: "Decisive",
      value: 50,
      confidence: "low",
    },
    {
      name: "Reflection Depth",
      leftLabel: "Surface",
      rightLabel: "Deep",
      value: 50,
      confidence: "low",
    },
  ];

  if (!profile || !profile.persona_vector || !profile.persona_vector.behavioral_profile) {
    return defaultTraits;
  }

  const { behavioral_profile } = profile.persona_vector;
  const traits: PersonaTrait[] = [];

  // Communication Style (0 = concise, 1 = verbose)
  const communicationStyle = behavioral_profile.communication_style;
  if (communicationStyle) {
    traits.push({
      name: "Communication Style",
      leftLabel: "Concise",
      rightLabel: "Verbose",
      value: Math.round(communicationStyle.score * 100),
      confidence: getConfidenceLevel(communicationStyle.confidence),
    });
  } else {
    traits.push(defaultTraits[0]);
  }

  // Emotional Expressiveness (0 = reserved, 1 = expressive)
  const emotionalExpressiveness = behavioral_profile.emotional_expressiveness;
  if (emotionalExpressiveness) {
    traits.push({
      name: "Emotional Expressiveness",
      leftLabel: "Reserved",
      rightLabel: "Expressive",
      value: Math.round(emotionalExpressiveness.score * 100),
      confidence: getConfidenceLevel(emotionalExpressiveness.confidence),
    });
  } else {
    traits.push(defaultTraits[1]);
  }

  // Decision Framing (0 = hesitant, 1 = decisive)
  const decisionFraming = behavioral_profile.decision_framing;
  if (decisionFraming) {
    traits.push({
      name: "Decision Framing",
      leftLabel: "Hesitant",
      rightLabel: "Decisive",
      value: Math.round(decisionFraming.score * 100),
      confidence: getConfidenceLevel(decisionFraming.confidence),
    });
  } else {
    traits.push(defaultTraits[2]);
  }

  // Reflection Depth (0 = surface, 1 = deep)
  const reflectionDepth = behavioral_profile.reflection_depth;
  if (reflectionDepth) {
    traits.push({
      name: "Reflection Depth",
      leftLabel: "Surface",
      rightLabel: "Deep",
      value: Math.round(reflectionDepth.score * 100),
      confidence: getConfidenceLevel(reflectionDepth.confidence),
    });
  } else {
    traits.push(defaultTraits[3]);
  }

  return traits;
}

export function PersonalityPage() {
  const [profile, setProfile] = useState<PersonaProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        setLoading(true);
        setError(null);

        const userId = localStorage.getItem("user_id");
        if (!userId) {
          throw new Error("No user ID found. Please log in.");
        }

        const response = await fetch(`${API_BASE}/persona/profile/${userId}`);
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
  }, []);

  const personaTraits = mapTraitsToUI(profile);

  return (
    <div className="h-screen flex flex-col">
      <header className="px-8 py-6 border-b border-border">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold text-foreground">Persona Profile</h1>
              <TooltipProvider delayDuration={200}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button className="p-1 rounded hover:bg-muted/50 transition-colors">
                      <Info className="w-4 h-4 text-muted-foreground" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-xs bg-card border border-border">
                    <p className="text-xs text-muted-foreground">
                      Observable communication patterns based on your interactions over time.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <p className="text-sm text-muted-foreground">
              How you've been expressing yourself recently
            </p>
          </div>
          <PersonaMirrorInfo />
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="p-8">
          <div className="max-w-4xl mx-auto space-y-8">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
                <span className="ml-3 text-muted-foreground">Loading profile...</span>
              </div>
            ) : error ? (
              <div className="bg-primary/5 border border-primary/20 rounded-xl p-6 text-center">
                <p className="text-sm text-muted-foreground">{error}</p>
              </div>
            ) : (
              <>
                <div className="bg-gradient-to-br from-primary/5 via-card to-transparent border border-border rounded-2xl p-6">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                      <User className="w-6 h-6 text-primary" />
                    </div>
                    <div className="flex-1">
                      <h2 className="font-medium text-foreground mb-2">Your Communication Patterns</h2>
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {profile?.summary || 
                          "Based on recent interactions, you tend toward thoughtful, moderately detailed responses."}
                      </p>
                    </div>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-medium text-foreground">Observable Traits</h2>
                    <span className="text-xs text-muted-foreground">
                      Based on {personaTraits.length} dimensions
                      {profile && ` • Stability: ${Math.round(profile.stability_index * 100)}%`}
                    </span>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {personaTraits.map((trait) => (
                      <PersonaTraitCard key={trait.name} {...trait} />
                    ))}
                  </div>
                </div>

                <div>
                  <h2 className="text-lg font-medium text-foreground mb-4">Schedule Context</h2>
                  <TimetableSection />
                </div>

                <div className="bg-muted/20 border border-border rounded-xl p-5">
                  <p className="text-xs text-muted-foreground/70 leading-relaxed">
                    These observations reflect how you've been communicating, not who you are. 
                    Patterns are based on multiple interactions and may evolve over time. 
                    You can provide feedback on any trait or reset your profile in Settings.
                  </p>
                </div>
              </>
            )}
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
