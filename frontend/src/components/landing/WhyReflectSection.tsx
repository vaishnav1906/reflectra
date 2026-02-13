import { Check } from "lucide-react";

const differentiators = [
  {
    title: "Long-Term Understanding",
    description: "Unlike stateless AI, Reflectra builds a persistent model of who you are that deepens with every interaction.",
  },
  {
    title: "Cognitive Alignment",
    description: "The system adapts to match your thinking style, emotional patterns, and communication preferences.",
  },
  {
    title: "Reflective Intelligence",
    description: "Goes beyond answering questions to offer genuine insights about your patterns and growth.",
  },
  {
    title: "Ethical by Design",
    description: "Built with privacy, transparency, and user control as foundational principles—not afterthoughts.",
  },
];

export function WhyReflectSection() {
  return (
    <section className="py-24 px-6 relative">
      <div className="max-w-6xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          {/* Left: Visual */}
          <div className="relative">
            <div className="aspect-square max-w-md mx-auto relative">
              {/* Orbital rings */}
              <div className="absolute inset-0 rounded-full border border-border/30 animate-[spin_30s_linear_infinite]" />
              <div className="absolute inset-8 rounded-full border border-primary/20 animate-[spin_25s_linear_infinite_reverse]" />
              <div className="absolute inset-16 rounded-full border border-accent/20 animate-[spin_20s_linear_infinite]" />
              
              {/* Center core */}
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center glow-subtle">
                  <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-primary/30 to-accent/30 flex items-center justify-center">
                    <div className="w-8 h-8 rounded-lg bg-primary/50" />
                  </div>
                </div>
              </div>

              {/* Floating elements */}
              <div className="absolute top-10 right-16 w-3 h-3 rounded-full bg-trait-analytical/50 animate-pulse-soft" />
              <div className="absolute bottom-20 left-12 w-2 h-2 rounded-full bg-trait-empathetic/50 animate-pulse-soft" style={{ animationDelay: "0.5s" }} />
              <div className="absolute top-1/3 left-8 w-2.5 h-2.5 rounded-full bg-accent/50 animate-pulse-soft" style={{ animationDelay: "1s" }} />
            </div>
          </div>

          <div>
            <span className="text-sm font-medium text-primary uppercase tracking-wider">Why Reflectra</span>
            <h2 className="text-3xl md:text-4xl font-bold text-foreground mt-3 mb-6">
              What makes it different
            </h2>
            <p className="text-muted-foreground mb-10 leading-relaxed">
              Reflectra isn't another chatbot or productivity tool. It's a new kind of AI 
              designed around the idea that technology should understand and adapt to humans—not 
              the other way around.
            </p>

            <div className="space-y-6">
              {differentiators.map((item) => (
                <div key={item.title} className="flex gap-4">
                  <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Check className="w-3.5 h-3.5 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground mb-1">{item.title}</h3>
                    <p className="text-sm text-muted-foreground">{item.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
