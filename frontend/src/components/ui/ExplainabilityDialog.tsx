import { HelpCircle, Brain, MessageSquare, TrendingUp, Database } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ExplainabilitySource {
  type: "linguistic" | "behavioral" | "temporal" | "semantic";
  description: string;
  weight: number;
}

interface ExplainabilityDialogProps {
  title: string;
  explanation: string;
  sources: ExplainabilitySource[];
  children?: React.ReactNode;
}

const sourceIcons = {
  linguistic: MessageSquare,
  behavioral: TrendingUp,
  temporal: Brain,
  semantic: Database,
};

const sourceLabels = {
  linguistic: "Linguistic Analysis",
  behavioral: "Behavioral Patterns",
  temporal: "Temporal Correlation",
  semantic: "Semantic Extraction",
};

export function ExplainabilityDialog({ 
  title, 
  explanation, 
  sources,
  children 
}: ExplainabilityDialogProps) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        {children || (
          <Button 
            variant="ghost" 
            size="sm" 
            className="gap-1.5 text-xs text-muted-foreground hover:text-primary"
          >
            <HelpCircle className="w-3.5 h-3.5" />
            Why am I seeing this?
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg bg-card border-border">
        <DialogHeader>
          <DialogTitle className="text-foreground flex items-center gap-2">
            <Brain className="w-5 h-5 text-primary" />
            Inference Explanation
          </DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Understanding how this insight was derived
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-6 pt-4">
          <div>
            <h4 className="text-sm font-medium text-foreground mb-2">Subject</h4>
            <p className="text-sm text-muted-foreground bg-muted/30 rounded-lg p-3">
              {title}
            </p>
          </div>

          <div>
            <h4 className="text-sm font-medium text-foreground mb-2">Derivation Method</h4>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {explanation}
            </p>
          </div>

          <div>
            <h4 className="text-sm font-medium text-foreground mb-3">Contributing Sources</h4>
            <div className="space-y-2">
              {sources.map((source, index) => {
                const Icon = sourceIcons[source.type];
                return (
                  <div 
                    key={index}
                    className="flex items-start gap-3 p-3 bg-muted/20 rounded-lg border border-border/50"
                  >
                    <Icon className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-foreground">
                          {sourceLabels[source.type]}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          Weight: {source.weight}%
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {source.description}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="text-xs text-muted-foreground/60 pt-2 border-t border-border">
            <p>
              All inferences are derived from user-provided conversational data. 
              No external data sources are used in personality modeling.
            </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
