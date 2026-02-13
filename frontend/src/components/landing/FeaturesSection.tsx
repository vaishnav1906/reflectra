import { User, Clock, MessageCircle, Lightbulb, Shield } from "lucide-react";
import { cn } from "@/lib/utils";

const features = [
  {
    icon: User,
    title: "Personality Learning",
    description: "Continuously infers and refines a model of your traits, values, and communication preferences through natural conversation.",
    color: "text-primary",
    bgColor: "bg-primary/10",
    borderColor: "border-primary/20",
  },
  {
    icon: Clock,
    title: "Long-Term Memory",
    description: "Remembers significant moments, patterns, and context across sessions—building a continuous relationship rather than isolated interactions.",
    color: "text-trait-analytical",
    bgColor: "bg-trait-analytical/10",
    borderColor: "border-trait-analytical/20",
  },
  {
    icon: MessageCircle,
    title: "Adaptive Conversations",
    description: "Adjusts tone, depth, formality, and approach based on your unique personality profile and current emotional context.",
    color: "text-trait-empathetic",
    bgColor: "bg-trait-empathetic/10",
    borderColor: "border-trait-empathetic/20",
  },
  {
    icon: Lightbulb,
    title: "Reflection & Self-Insight",
    description: "Generates thoughtful observations about your behavioral patterns, emotional trends, and personal growth over time.",
    color: "text-accent",
    bgColor: "bg-accent/10",
    borderColor: "border-accent/20",
  },
  {
    icon: Shield,
    title: "Ethical Data Control",
    description: "You own your data completely. Edit traits, delete memories, export everything, or reset entirely at any time.",
    color: "text-trait-consistent",
    bgColor: "bg-trait-consistent/10",
    borderColor: "border-trait-consistent/20",
  },
];

export function FeaturesSection() {
  return (
    <section className="py-24 px-6 relative">
      {/* Background pattern */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_hsl(var(--primary)/0.03)_0%,_transparent_70%)]" />
      
      <div className="relative max-w-6xl mx-auto">
        {/* Section Header */}
        <div className="text-center mb-16">
          <span className="text-sm font-medium text-primary uppercase tracking-wider">Core Features</span>
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mt-3 mb-4">
            Designed for depth
          </h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Every feature serves the goal of genuine understanding and meaningful interaction
          </p>
        </div>

        {/* Feature Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => (
            <div
              key={feature.title}
              className={cn(
                "group bg-card border rounded-2xl p-6 transition-all duration-300 hover:shadow-lg",
                feature.borderColor,
                "hover:border-opacity-50"
              )}
            >
              <div className={cn(
                "w-12 h-12 rounded-xl flex items-center justify-center mb-5",
                feature.bgColor
              )}>
                <feature.icon className={cn("w-6 h-6", feature.color)} />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-3">{feature.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
