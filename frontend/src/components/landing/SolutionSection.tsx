import { Brain, Database, Sparkles, Heart } from "lucide-react";

const solutions = [
  {
    icon: Brain,
    title: "Long-Term Personality Model",
    description: "Reflectra builds a nuanced understanding of your traits, preferences, and communication patterns that evolves with every interaction.",
    color: "text-primary",
    bgColor: "bg-primary/10",
  },
  {
    icon: Database,
    title: "Persistent Memory",
    description: "Important moments, habits, and insights are remembered across sessions—creating continuity in your relationship with AI.",
    color: "text-trait-analytical",
    bgColor: "bg-trait-analytical/10",
  },
  {
    icon: Heart,
    title: "Adaptive Communication",
    description: "The system naturally adjusts its tone, depth, and style to match your preferences—becoming more aligned with you over time.",
    color: "text-trait-empathetic",
    bgColor: "bg-trait-empathetic/10",
  },
  {
    icon: Sparkles,
    title: "Reflective Intelligence",
    description: "Beyond answers, Reflectra generates insights about your patterns, growth, and behaviors—supporting genuine self-understanding.",
    color: "text-accent",
    bgColor: "bg-accent/10",
  },
];

export function SolutionSection() {
  return (
    <section className="py-24 px-6 relative">
      {/* Subtle background accent */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-primary/[0.02] to-transparent" />
      
      <div className="relative max-w-6xl mx-auto">
        {/* Section Header */}
        <div className="text-center mb-16">
          <span className="text-sm font-medium text-primary uppercase tracking-wider">The Solution</span>
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mt-3 mb-4">
            AI that truly{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent">
              knows you
            </span>
          </h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Reflectra is built differently—designed for depth, continuity, 
            and genuine understanding rather than surface-level assistance.
          </p>
        </div>

        {/* Solution Cards - Cleaner, more harmonious layout */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {solutions.map((solution, index) => (
            <div
              key={solution.title}
              className="group bg-card border border-border rounded-2xl p-8 transition-all duration-300 border-glow"
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              <div className={`w-14 h-14 rounded-xl ${solution.bgColor} flex items-center justify-center mb-6`}>
                <solution.icon className={`w-7 h-7 ${solution.color}`} />
              </div>
              <h3 className="text-xl font-semibold text-foreground mb-3">{solution.title}</h3>
              <p className="text-muted-foreground leading-relaxed">
                {solution.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
