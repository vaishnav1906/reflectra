import { TrendingUp, Heart, GraduationCap, Users, Activity } from "lucide-react";
import { cn } from "@/lib/utils";

const useCases = [
  {
    icon: TrendingUp,
    title: "Personal Growth",
    description: "Track your emotional patterns, identify recurring themes, and receive insights that support intentional self-development over time.",
    color: "text-primary",
  },
  {
    icon: Heart,
    title: "Mental Well-being Support",
    description: "A consistent, judgment-free space for processing thoughts and emotions, with an AI that remembers your journey and context.",
    color: "text-trait-empathetic",
  },
  {
    icon: GraduationCap,
    title: "Personalized Learning",
    description: "An AI tutor that understands how you learn best, adapts explanations to your style, and builds on what you already know.",
    color: "text-trait-analytical",
  },
  {
    icon: Users,
    title: "Long-Term Digital Companion",
    description: "A continuous relationship with an AI that knows your story, celebrates your progress, and grows alongside you.",
    color: "text-trait-creative",
  },
  {
    icon: Activity,
    title: "Self-Awareness & Habit Tracking",
    description: "Observe your behavioral patterns, understand your triggers, and build better habits with AI-generated awareness.",
    color: "text-trait-consistent",
  },
];

export function UseCasesSection() {
  return (
    <section className="py-24 px-6 relative">
      {/* Background accent */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-muted/20 to-transparent" />
      
      <div className="relative max-w-6xl mx-auto">
        {/* Section Header */}
        <div className="text-center mb-16">
          <span className="text-sm font-medium text-primary uppercase tracking-wider">Use Cases</span>
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mt-3 mb-4">
            Built for meaningful applications
          </h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Reflectra shines in contexts where understanding, continuity, and depth matter most
          </p>
        </div>

        {/* Use Case Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {useCases.map((useCase, index) => (
            <div
              key={useCase.title}
              className={cn(
                "group bg-card/50 backdrop-blur-sm border border-border rounded-xl p-6 transition-all duration-300 hover:bg-card hover:border-border/80",
                index === 0 && "lg:col-span-2"
              )}
            >
              <useCase.icon className={cn("w-8 h-8 mb-4", useCase.color)} />
              <h3 className="text-lg font-semibold text-foreground mb-2">{useCase.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {useCase.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
