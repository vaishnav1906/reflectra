import { Bot, RefreshCw, Repeat, HelpCircle } from "lucide-react";

const problems = [
  {
    icon: Repeat,
    title: "Stateless Interactions",
    description: "Every conversation starts from zero. No memory of past discussions, preferences, or growth.",
  },
  {
    icon: Bot,
    title: "Generic Responses",
    description: "One-size-fits-all answers that don't consider your unique personality or communication style.",
  },
  {
    icon: RefreshCw,
    title: "Repetitive Patterns",
    description: "You explain the same context repeatedly. The AI never learns who you really are.",
  },
  {
    icon: HelpCircle,
    title: "No Self-Insight",
    description: "Current AI provides answers but never helps you understand yourself better.",
  },
];

export function ProblemSection() {
  return (
    <section className="py-24 px-6 relative">
      <div className="max-w-6xl mx-auto">
        {/* Section Header */}
        <div className="text-center mb-16">
          <span className="text-sm font-medium text-muted-foreground/70 uppercase tracking-wider">The Problem</span>
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mt-3 mb-4">
            Current AI systems are fundamentally{" "}
            <span className="text-muted-foreground/60">impersonal</span>
          </h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            They answer questions without understanding who's asking. 
            Every interaction is isolated, generic, and forgotten.
          </p>
        </div>

        {/* Problem Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {problems.map((problem, index) => (
            <div
              key={problem.title}
              className="group bg-muted/20 border border-border/50 rounded-xl p-6 transition-all duration-300 hover:border-border opacity-70 hover:opacity-100"
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-lg bg-muted/50 flex items-center justify-center flex-shrink-0">
                  <problem.icon className="w-6 h-6 text-muted-foreground/60" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground/80 mb-2">{problem.title}</h3>
                  <p className="text-sm text-muted-foreground/60 leading-relaxed">
                    {problem.description}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Visual Separator */}
        <div className="mt-20 flex items-center justify-center">
          <div className="flex items-center gap-4">
            <div className="h-px w-24 bg-gradient-to-r from-transparent to-border" />
            <span className="text-sm text-muted-foreground/50">There's a better way</span>
            <div className="h-px w-24 bg-gradient-to-l from-transparent to-border" />
          </div>
        </div>
      </div>
    </section>
  );
}
