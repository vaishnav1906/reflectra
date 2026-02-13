import { ScrollArea } from "@/components/ui/scroll-area";
import { PersonaTraitCard } from "@/components/persona/PersonaTraitCard";
import { PersonaMirrorInfo } from "@/components/persona/PersonaMirrorInfo";
import { TimetableSection } from "@/components/timetable/TimetableSection";
import { User, Info } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const personaTraits = [
  {
    name: "Communication Style",
    leftLabel: "Concise",
    rightLabel: "Verbose",
    value: 65,
    confidence: "high" as const,
  },
  {
    name: "Emotional Expressiveness",
    leftLabel: "Reserved",
    rightLabel: "Expressive",
    value: 72,
    confidence: "medium" as const,
  },
  {
    name: "Decision Framing",
    leftLabel: "Hesitant",
    rightLabel: "Decisive",
    value: 35,
    confidence: "medium" as const,
  },
  {
    name: "Reflection Depth",
    leftLabel: "Surface",
    rightLabel: "Deep",
    value: 80,
    confidence: "high" as const,
  },
];

export function PersonalityPage() {
  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
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
            {/* Summary Card */}
            <div className="bg-gradient-to-br from-primary/5 via-card to-transparent border border-border rounded-2xl p-6">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                  <User className="w-6 h-6 text-primary" />
                </div>
                <div className="flex-1">
                  <h2 className="font-medium text-foreground mb-2">Your Communication Patterns</h2>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    Based on recent interactions, you tend toward thoughtful, moderately detailed responses. 
                    You show some hesitation when discussing decisions, and engage more deeply during evening sessions. 
                    These patterns may shift over time.
                  </p>
                </div>
              </div>
            </div>

            {/* Observable Traits */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-medium text-foreground">Observable Traits</h2>
                <span className="text-xs text-muted-foreground">
                  Based on {personaTraits.length} dimensions
                </span>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {personaTraits.map((trait) => (
                  <PersonaTraitCard key={trait.name} {...trait} />
                ))}
              </div>
            </div>

            {/* Timetable Section */}
            <div>
              <h2 className="text-lg font-medium text-foreground mb-4">Schedule Context</h2>
              <TimetableSection />
            </div>

            {/* Disclaimer */}
            <div className="bg-muted/20 border border-border rounded-xl p-5">
              <p className="text-xs text-muted-foreground/70 leading-relaxed">
                These observations reflect how you've been communicating, not who you are. 
                Patterns are based on multiple interactions and may evolve over time. 
                You can provide feedback on any trait or reset your profile in Settings.
              </p>
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
