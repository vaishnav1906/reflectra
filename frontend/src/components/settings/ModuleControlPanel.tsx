import { useState } from "react";
import { 
  Brain, 
  Database, 
  Lightbulb, 
  Activity, 
  Settings2,
  AlertCircle
} from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { cn } from "@/lib/utils";

interface Module {
  id: string;
  name: string;
  icon: typeof Brain;
  enabled: boolean;
  description: string;
  internalFunction: string;
  critical: boolean;
}

const initialModules: Module[] = [
  {
    id: "personality-learning",
    name: "Personality Learning Engine",
    icon: Brain,
    enabled: true,
    description: "Bayesian inference module for continuous personality trait updates",
    internalFunction: "Processes interaction features to update trait posterior distributions with configurable learning rate",
    critical: false,
  },
  {
    id: "memory-persistence",
    name: "Memory Persistence Module",
    icon: Database,
    enabled: true,
    description: "Long-term storage and retrieval of significant interaction memories",
    internalFunction: "Manages episodic, semantic, behavioral, and preference memory consolidation with decay functions",
    critical: false,
  },
  {
    id: "reflection-generation",
    name: "Reflection Generation Engine",
    icon: Lightbulb,
    enabled: true,
    description: "Automated synthesis of behavioral insights and pattern reflections",
    internalFunction: "Aggregates longitudinal data, detects trends, and generates natural language reflective summaries",
    critical: false,
  },
  {
    id: "behavior-tracking",
    name: "Behavior Tracking Module",
    icon: Activity,
    enabled: true,
    description: "Real-time monitoring and classification of interaction patterns",
    internalFunction: "Extracts behavioral features, tracks temporal patterns, and updates behavioral coefficient matrices",
    critical: false,
  },
];

export function ModuleControlPanel() {
  const [modules, setModules] = useState<Module[]>(initialModules);

  const toggleModule = (id: string) => {
    setModules(modules.map(module => 
      module.id === id 
        ? { ...module, enabled: !module.enabled }
        : module
    ));
  };

  const activeCount = modules.filter(m => m.enabled).length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings2 className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold text-foreground">Module Control Panel</h2>
        </div>
        <span className="text-xs px-2 py-1 bg-muted rounded-full text-muted-foreground">
          {activeCount}/{modules.length} active
        </span>
      </div>

      <div className="bg-card border border-border rounded-xl divide-y divide-border">
        {modules.map((module) => {
          const Icon = module.icon;
          return (
            <div 
              key={module.id}
              className={cn(
                "p-5 transition-colors",
                !module.enabled && "opacity-60"
              )}
            >
              <div className="flex items-start gap-4">
                <div className={cn(
                  "w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0",
                  module.enabled ? "bg-primary/10" : "bg-muted"
                )}>
                  <Icon className={cn(
                    "w-5 h-5",
                    module.enabled ? "text-primary" : "text-muted-foreground"
                  )} />
                </div>
                
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-foreground">{module.name}</span>
                      <InfoTooltip content={module.internalFunction} />
                    </div>
                    <Switch
                      checked={module.enabled}
                      onCheckedChange={() => toggleModule(module.id)}
                    />
                  </div>
                  
                  <p className="text-sm text-muted-foreground mb-2">{module.description}</p>
                  
                  <div className="p-2 bg-muted/30 rounded-lg border border-border/50">
                    <p className="text-xs text-muted-foreground font-mono">
                      {module.internalFunction}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex items-start gap-2 p-4 bg-muted/30 rounded-lg border border-border">
        <AlertCircle className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-0.5" />
        <p className="text-xs text-muted-foreground">
          Disabling modules affects system behavior. Personality Learning and Memory Persistence 
          are core to adaptive personalization. Changes take effect immediately and persist across sessions.
        </p>
      </div>
    </div>
  );
}
