import { useState } from "react";
import { ThumbsUp, ThumbsDown, Edit3, Check, X, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { cn } from "@/lib/utils";

interface TraitFeedback {
  id: string;
  name: string;
  currentValue: number;
  userAgreement: "agree" | "disagree" | null;
  userOverride: number | null;
}

const initialTraits: TraitFeedback[] = [
  { id: "analytical", name: "Analytical Processing", currentValue: 78, userAgreement: null, userOverride: null },
  { id: "affective", name: "Affective Depth", currentValue: 85, userAgreement: null, userOverride: null },
  { id: "creative", name: "Divergent Ideation", currentValue: 72, userAgreement: null, userOverride: null },
  { id: "consistent", name: "Behavioral Consistency", currentValue: 68, userAgreement: null, userOverride: null },
  { id: "introspective", name: "Introspective Orientation", currentValue: 91, userAgreement: null, userOverride: null },
];

export function FeedbackLoop() {
  const [traits, setTraits] = useState<TraitFeedback[]>(initialTraits);
  const [editingTrait, setEditingTrait] = useState<string | null>(null);
  const [tempValue, setTempValue] = useState<number>(0);

  const handleAgreement = (id: string, agreement: "agree" | "disagree") => {
    setTraits(traits.map(trait => 
      trait.id === id 
        ? { ...trait, userAgreement: trait.userAgreement === agreement ? null : agreement }
        : trait
    ));
  };

  const startEditing = (trait: TraitFeedback) => {
    setEditingTrait(trait.id);
    setTempValue(trait.userOverride ?? trait.currentValue);
  };

  const saveOverride = (id: string) => {
    setTraits(traits.map(trait => 
      trait.id === id 
        ? { ...trait, userOverride: tempValue, userAgreement: null }
        : trait
    ));
    setEditingTrait(null);
  };

  const resetTrait = (id: string) => {
    setTraits(traits.map(trait => 
      trait.id === id 
        ? { ...trait, userOverride: null, userAgreement: null }
        : trait
    ));
  };

  const feedbackCount = traits.filter(t => t.userAgreement || t.userOverride !== null).length;

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Edit3 className="w-4 h-4 text-primary" />
          <h3 className="font-semibold text-foreground">Feedback & Correction Loop</h3>
          <InfoTooltip 
            content="Supervised learning interface allowing you to validate, correct, or override system inferences to improve model accuracy" 
          />
        </div>
        {feedbackCount > 0 && (
          <span className="text-xs px-2 py-1 bg-primary/10 text-primary rounded-full">
            {feedbackCount} correction{feedbackCount > 1 ? "s" : ""} pending
          </span>
        )}
      </div>

      <div className="space-y-3">
        {traits.map((trait) => (
          <div 
            key={trait.id}
            className={cn(
              "p-4 rounded-lg border transition-all",
              trait.userOverride !== null 
                ? "bg-primary/5 border-primary/30" 
                : trait.userAgreement 
                  ? trait.userAgreement === "agree" 
                    ? "bg-green-500/5 border-green-500/30" 
                    : "bg-red-400/5 border-red-400/30"
                  : "bg-muted/30 border-border/50"
            )}
          >
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium text-foreground">{trait.name}</span>
                  {trait.userOverride !== null && (
                    <span className="text-xs px-1.5 py-0.5 bg-primary/20 text-primary rounded">
                      Overridden
                    </span>
                  )}
                </div>
                
                {editingTrait === trait.id ? (
                  <div className="flex items-center gap-4 mt-3">
                    <Slider
                      value={[tempValue]}
                      onValueChange={(v) => setTempValue(v[0])}
                      max={100}
                      min={0}
                      step={1}
                      className="flex-1"
                    />
                    <span className="text-sm font-medium text-primary w-12 text-right">
                      {tempValue}%
                    </span>
                    <div className="flex gap-1">
                      <Button 
                        size="sm" 
                        variant="ghost" 
                        className="h-7 w-7 p-0"
                        onClick={() => saveOverride(trait.id)}
                      >
                        <Check className="w-3.5 h-3.5 text-green-500" />
                      </Button>
                      <Button 
                        size="sm" 
                        variant="ghost" 
                        className="h-7 w-7 p-0"
                        onClick={() => setEditingTrait(null)}
                      >
                        <X className="w-3.5 h-3.5 text-muted-foreground" />
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      System inference: {trait.currentValue}%
                    </span>
                    {trait.userOverride !== null && (
                      <>
                        <span className="text-xs text-muted-foreground">→</span>
                        <span className="text-xs text-primary font-medium">
                          User correction: {trait.userOverride}%
                        </span>
                      </>
                    )}
                  </div>
                )}
              </div>

              {editingTrait !== trait.id && (
                <div className="flex items-center gap-1 ml-4">
                  <Button
                    size="sm"
                    variant="ghost"
                    className={cn(
                      "h-8 w-8 p-0",
                      trait.userAgreement === "agree" && "bg-green-500/10 text-green-500"
                    )}
                    onClick={() => handleAgreement(trait.id, "agree")}
                    title="Agree with inference"
                  >
                    <ThumbsUp className="w-3.5 h-3.5" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className={cn(
                      "h-8 w-8 p-0",
                      trait.userAgreement === "disagree" && "bg-red-400/10 text-red-400"
                    )}
                    onClick={() => handleAgreement(trait.id, "disagree")}
                    title="Disagree with inference"
                  >
                    <ThumbsDown className="w-3.5 h-3.5" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-8 w-8 p-0"
                    onClick={() => startEditing(trait)}
                    title="Override value"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                  </Button>
                  {(trait.userOverride !== null || trait.userAgreement !== null) && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8 w-8 p-0"
                      onClick={() => resetTrait(trait.id)}
                      title="Reset to system inference"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                    </Button>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-border">
        <p className="text-xs text-muted-foreground/60">
          Your feedback is used to refine the personality model through supervised learning. 
          Corrections influence future inferences with weighted temporal decay.
        </p>
      </div>
    </div>
  );
}
