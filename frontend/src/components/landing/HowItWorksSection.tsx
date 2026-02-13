import { MessageSquare, Brain, Layers, RefreshCw, Lightbulb, ArrowDown } from "lucide-react";
import { cn } from "@/lib/utils";

const steps = [
  {
    number: "01",
    icon: MessageSquare,
    title: "Natural Conversation",
    description: "You interact with Reflectra through natural dialogue—no special commands or structured inputs required.",
    color: "text-primary",
    bgColor: "bg-primary/10",
  },
  {
    number: "02",
    icon: Brain,
    title: "Trait Inference",
    description: "The system observes patterns in your communication style, emotional expressions, and preferences.",
    color: "text-trait-analytical",
    bgColor: "bg-trait-analytical/10",
  },
  {
    number: "03",
    icon: Layers,
    title: "Model Building",
    description: "A structured personality model is created and refined—representing who you are, not just what you say.",
    color: "text-trait-creative",
    bgColor: "bg-trait-creative/10",
  },
  {
    number: "04",
    icon: RefreshCw,
    title: "Adaptive Responses",
    description: "Future conversations are shaped by your unique model—more relevant, more personal, more aligned.",
    color: "text-trait-empathetic",
    bgColor: "bg-trait-empathetic/10",
  },
  {
    number: "05",
    icon: Lightbulb,
    title: "Reflective Insights",
    description: "Over time, Reflectra generates observations about your patterns, growth, and behavioral trends.",
    color: "text-accent",
    bgColor: "bg-accent/10",
  },
];

export function HowItWorksSection() {
  return (
    <section id="how-it-works" className="py-24 px-6 relative scroll-mt-20">
      <div className="max-w-5xl mx-auto">
        {/* Section Header */}
        <div className="text-center mb-20">
          <span className="text-sm font-medium text-primary uppercase tracking-wider">How It Works</span>
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mt-3 mb-4">
            From conversation to understanding
          </h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            A continuous learning loop that deepens over time
          </p>
        </div>

        {/* Steps with connecting line */}
        <div className="relative">
          {/* Vertical connector line */}
          <div className="absolute left-8 md:left-1/2 top-0 bottom-0 w-px bg-gradient-to-b from-primary/20 via-accent/20 to-primary/20 md:-translate-x-1/2" />

          <div className="space-y-12">
            {steps.map((step, index) => (
              <div
                key={step.number}
                className={cn(
                  "relative flex items-start gap-8 md:gap-16",
                  index % 2 === 0 ? "md:flex-row" : "md:flex-row-reverse"
                )}
              >
                {/* Step content */}
                <div className={cn(
                  "flex-1 ml-20 md:ml-0",
                  index % 2 === 0 ? "md:text-right" : "md:text-left"
                )}>
                  <div className={cn(
                    "bg-card border border-border rounded-xl p-6 transition-all duration-300 border-glow",
                    index % 2 === 0 ? "md:mr-8" : "md:ml-8"
                  )}>
                    <span className="text-xs font-mono text-muted-foreground/50 mb-2 block">
                      Step {step.number}
                    </span>
                    <h3 className="text-lg font-semibold text-foreground mb-2">{step.title}</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {step.description}
                    </p>
                  </div>
                </div>

                {/* Center icon */}
                <div className="absolute left-0 md:left-1/2 md:-translate-x-1/2 flex flex-col items-center">
                  <div className={cn(
                    "w-16 h-16 rounded-2xl flex items-center justify-center border-4 border-background z-10",
                    step.bgColor
                  )}>
                    <step.icon className={cn("w-7 h-7", step.color)} />
                  </div>
                  {index < steps.length - 1 && (
                    <ArrowDown className="w-4 h-4 text-muted-foreground/30 mt-4 hidden md:block" />
                  )}
                </div>

                {/* Empty space for alignment */}
                <div className="flex-1 hidden md:block" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
