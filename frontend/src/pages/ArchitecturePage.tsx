import { ScrollArea } from "@/components/ui/scroll-area";
import { 
  ArrowRight, 
  MessageSquare, 
  Scan, 
  Brain, 
  Box, 
  Database, 
  Wand2, 
  Lightbulb, 
  Eye,
  Activity,
  Layers
} from "lucide-react";
import { cn } from "@/lib/utils";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { useState } from "react";

interface PipelineBlock {
  id: string;
  name: string;
  icon: typeof Brain;
  description: string;
  dataProcessed: string;
  outputType: string;
  color: string;
}

const pipelineBlocks: PipelineBlock[] = [
  {
    id: "input",
    name: "User Input Layer",
    icon: MessageSquare,
    description: "Natural language interface capturing user utterances, including textual content, temporal metadata, and session context markers.",
    dataProcessed: "Raw text, timestamps, session IDs, interaction sequence",
    outputType: "Structured interaction objects with metadata",
    color: "text-muted-foreground",
  },
  {
    id: "extraction",
    name: "Feature Extraction Engine",
    icon: Scan,
    description: "Multi-modal feature extraction pipeline processing linguistic, semantic, and affective signals from raw input.",
    dataProcessed: "Tokenized text, syntactic parse trees, sentiment vectors",
    outputType: "Feature tensors for downstream inference",
    color: "text-trait-analytical",
  },
  {
    id: "inference",
    name: "Personality Inference Engine",
    icon: Brain,
    description: "Bayesian inference module updating personality trait distributions based on extracted features and prior beliefs.",
    dataProcessed: "Feature tensors, prior trait distributions, confidence intervals",
    outputType: "Updated trait posteriors with uncertainty estimates",
    color: "text-primary",
  },
  {
    id: "representation",
    name: "Structured Representation",
    icon: Box,
    description: "Formal personality model storing trait vectors, behavioral coefficients, and temporal dynamics.",
    dataProcessed: "Trait posteriors, decay functions, temporal weights",
    outputType: "Structured PersonalityModel object",
    color: "text-trait-creative",
  },
  {
    id: "memory",
    name: "Memory Update Engine",
    icon: Database,
    description: "Episodic and semantic memory consolidation with significance scoring and cognitive type classification.",
    dataProcessed: "Interaction content, significance scores, temporal context",
    outputType: "Classified memory objects with retrieval indices",
    color: "text-trait-consistent",
  },
  {
    id: "response",
    name: "Adaptive Response Generator",
    icon: Wand2,
    description: "Context-aware response synthesis adapting tone, depth, and content based on personality model and memory retrieval.",
    dataProcessed: "Query context, personality model, retrieved memories",
    outputType: "Personalized response with adaptation markers",
    color: "text-trait-empathetic",
  },
  {
    id: "reflection",
    name: "Reflection Engine",
    icon: Lightbulb,
    description: "Longitudinal pattern detection and natural language synthesis for generating reflective insights.",
    dataProcessed: "Aggregated behavioral data, trend vectors, pattern graphs",
    outputType: "Natural language reflections with source attribution",
    color: "text-accent",
  },
  {
    id: "explainability",
    name: "Explainability Layer",
    icon: Eye,
    description: "Transparent reasoning module providing inference justifications and source attribution for all system outputs.",
    dataProcessed: "Inference traces, feature contributions, source weights",
    outputType: "Human-readable explanations with confidence scores",
    color: "text-trait-introspective",
  },
];

const learningLoopSteps = [
  { label: "User Interaction", description: "Natural conversation input" },
  { label: "Feature Extraction", description: "Signal processing" },
  { label: "Model Update", description: "Bayesian inference" },
  { label: "Response Adaptation", description: "Personalized output" },
  { label: "User Feedback", description: "Implicit/explicit signals" },
  { label: "Re-Learning", description: "Model refinement" },
];

export function ArchitecturePage() {
  const [selectedBlock, setSelectedBlock] = useState<PipelineBlock | null>(null);

  return (
    <div className="h-screen flex flex-col">
      <header className="px-8 py-6 border-b border-border">
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-primary" />
          <h1 className="text-xl font-semibold text-foreground">System Architecture</h1>
          <InfoTooltip 
            content="Interactive visualization of the cognitive pipeline and data flow architecture" 
            side="right"
          />
        </div>
        <p className="text-sm text-muted-foreground">
          Modular inference pipeline and learning loop visualization
        </p>
      </header>

      <ScrollArea className="flex-1">
        <div className="p-8">
          <div className="max-w-6xl mx-auto space-y-12">
            {/* Pipeline Header */}
            <div className="bg-gradient-to-br from-primary/5 via-card to-transparent border border-border rounded-2xl p-8">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <Activity className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <h2 className="font-semibold text-foreground mb-2">Cognitive Processing Pipeline</h2>
                  <p className="text-muted-foreground text-sm leading-relaxed">
                    The Reflectra framework processes user interactions through a modular pipeline of specialized engines. 
                    Each component performs a distinct cognitive function, transforming raw input into personalized, 
                    explainable outputs. Click on any block to view detailed specifications.
                  </p>
                </div>
              </div>
            </div>

            {/* Pipeline Visualization */}
            <div className="relative">
              <h3 className="text-sm font-medium text-foreground mb-6 flex items-center gap-2">
                <span>Data Flow Pipeline</span>
                <InfoTooltip content="Sequential processing stages from input to explainable output" />
              </h3>
              
              <div className="grid grid-cols-4 gap-4">
                {pipelineBlocks.map((block, index) => (
                  <div key={block.id} className="relative">
                    <button
                      onClick={() => setSelectedBlock(selectedBlock?.id === block.id ? null : block)}
                      className={cn(
                        "w-full p-4 bg-card border rounded-xl transition-all duration-200 text-left",
                        selectedBlock?.id === block.id 
                          ? "border-primary ring-1 ring-primary/20" 
                          : "border-border hover:border-primary/50"
                      )}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <block.icon className={cn("w-4 h-4", block.color)} />
                        <span className="text-xs font-medium text-muted-foreground">
                          {String(index + 1).padStart(2, '0')}
                        </span>
                      </div>
                      <h4 className="text-sm font-medium text-foreground mb-1">{block.name}</h4>
                      <p className="text-xs text-muted-foreground line-clamp-2">{block.description}</p>
                    </button>
                    
                    {/* Arrow connector */}
                    {index < pipelineBlocks.length - 1 && (index + 1) % 4 !== 0 && (
                      <ArrowRight className="absolute -right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/30 z-10" />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Selected Block Details */}
            {selectedBlock && (
              <div className="bg-card border border-primary/30 rounded-xl p-6 fade-in">
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <selectedBlock.icon className={cn("w-5 h-5", selectedBlock.color)} />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-foreground mb-2">{selectedBlock.name}</h3>
                    <p className="text-sm text-muted-foreground mb-4">{selectedBlock.description}</p>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-3 bg-muted/30 rounded-lg border border-border/50">
                        <p className="text-xs font-medium text-foreground mb-1">Input Data</p>
                        <p className="text-xs text-muted-foreground">{selectedBlock.dataProcessed}</p>
                      </div>
                      <div className="p-3 bg-muted/30 rounded-lg border border-border/50">
                        <p className="text-xs font-medium text-foreground mb-1">Output Type</p>
                        <p className="text-xs text-muted-foreground">{selectedBlock.outputType}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Learning Loop */}
            <div>
              <h3 className="text-sm font-medium text-foreground mb-6 flex items-center gap-2">
                <span>Continuous Learning Loop</span>
                <InfoTooltip content="Recursive adaptation cycle demonstrating how feedback influences model evolution" />
              </h3>
              
              <div className="relative p-8 bg-card border border-border rounded-2xl">
                <div className="flex items-center justify-center">
                  <div className="relative">
                    {/* Circular layout */}
                    <div className="w-80 h-80 relative">
                      {learningLoopSteps.map((step, index) => {
                        const angle = (index * 60 - 90) * (Math.PI / 180);
                        const radius = 130;
                        const x = Math.cos(angle) * radius;
                        const y = Math.sin(angle) * radius;
                        
                        return (
                          <div
                            key={step.label}
                            className="absolute w-24 text-center"
                            style={{
                              left: `calc(50% + ${x}px - 48px)`,
                              top: `calc(50% + ${y}px - 32px)`,
                            }}
                          >
                            <div className="p-3 bg-muted/50 border border-border rounded-lg">
                              <p className="text-xs font-medium text-foreground">{step.label}</p>
                              <p className="text-xs text-muted-foreground mt-0.5">{step.description}</p>
                            </div>
                          </div>
                        );
                      })}
                      
                      {/* Center */}
                      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-20 h-20 rounded-full bg-primary/10 border border-primary/30 flex items-center justify-center">
                        <Brain className="w-8 h-8 text-primary" />
                      </div>
                      
                      {/* Circular arrows SVG */}
                      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 320 320">
                        <circle
                          cx="160"
                          cy="160"
                          r="100"
                          fill="none"
                          stroke="hsl(var(--border))"
                          strokeWidth="1"
                          strokeDasharray="8 4"
                        />
                      </svg>
                    </div>
                  </div>
                </div>
                
                <div className="text-center mt-4">
                  <p className="text-xs text-muted-foreground">
                    Continuous adaptation cycle • Model refinement occurs with each interaction
                  </p>
                </div>
              </div>
            </div>

            {/* Data Model Specification */}
            <div>
              <h3 className="text-sm font-medium text-foreground mb-6 flex items-center gap-2">
                <span>Internal Data Models</span>
                <InfoTooltip content="Structured representations used by the cognitive framework" />
              </h3>
              
              <div className="grid grid-cols-2 gap-6">
                {/* PersonalityModel */}
                <div className="bg-card border border-border rounded-xl p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <Box className="w-4 h-4 text-primary" />
                    <span className="text-sm font-medium text-foreground">PersonalityModel</span>
                    <span className="text-xs px-2 py-0.5 bg-primary/10 text-primary rounded">object</span>
                  </div>
                  <div className="space-y-2 font-mono text-xs">
                    <div className="p-2 bg-muted/30 rounded">
                      <span className="text-trait-analytical">traits</span>: TraitVector[]
                    </div>
                    <div className="p-2 bg-muted/30 rounded">
                      <span className="text-trait-analytical">confidence</span>: Float [0,1]
                    </div>
                    <div className="p-2 bg-muted/30 rounded">
                      <span className="text-trait-analytical">timestamp</span>: DateTime
                    </div>
                    <div className="p-2 bg-muted/30 rounded">
                      <span className="text-trait-analytical">decayFunction</span>: Exponential
                    </div>
                    <div className="p-2 bg-muted/30 rounded">
                      <span className="text-trait-analytical">version</span>: String
                    </div>
                  </div>
                </div>

                {/* MemoryObject */}
                <div className="bg-card border border-border rounded-xl p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <Database className="w-4 h-4 text-trait-consistent" />
                    <span className="text-sm font-medium text-foreground">MemoryObject</span>
                    <span className="text-xs px-2 py-0.5 bg-trait-consistent/10 text-trait-consistent rounded">object</span>
                  </div>
                  <div className="space-y-2 font-mono text-xs">
                    <div className="p-2 bg-muted/30 rounded">
                      <span className="text-trait-consistent">category</span>: CognitiveType
                    </div>
                    <div className="p-2 bg-muted/30 rounded">
                      <span className="text-trait-consistent">content</span>: String
                    </div>
                    <div className="p-2 bg-muted/30 rounded">
                      <span className="text-trait-consistent">emotionalWeight</span>: Float
                    </div>
                    <div className="p-2 bg-muted/30 rounded">
                      <span className="text-trait-consistent">temporalRelevance</span>: Float
                    </div>
                    <div className="p-2 bg-muted/30 rounded">
                      <span className="text-trait-consistent">sourceInteraction</span>: UUID
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Module Status */}
            <div className="bg-muted/30 border border-border rounded-xl p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-foreground">Architecture Version 2.4.1</p>
                  <p className="text-xs text-muted-foreground">
                    8 active modules • Pipeline latency: 45ms avg • Memory efficiency: 94%
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-green-500" />
                  <span className="text-xs text-muted-foreground">All Systems Operational</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
