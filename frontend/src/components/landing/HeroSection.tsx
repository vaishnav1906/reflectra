import { Brain, ArrowRight, Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";

interface HeroSectionProps {
  onShowLogin: () => void;
}

export function HeroSection({ onShowLogin }: HeroSectionProps) {
  const navigate = useNavigate();

  const handleStartConversation = () => {
    const userId = localStorage.getItem("user_id");
    if (userId) {
      navigate("/app/chat");
    } else {
      onShowLogin();
    }
  };

  return (
    <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0 gradient-mesh" />
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/5 rounded-full blur-3xl" />
      <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-accent/5 rounded-full blur-3xl" />
      
      {/* Floating orbs */}
      <div className="absolute top-20 right-[20%] w-2 h-2 rounded-full bg-primary/40 animate-pulse-soft" />
      <div className="absolute top-40 left-[15%] w-1.5 h-1.5 rounded-full bg-accent/40 animate-pulse-soft" style={{ animationDelay: "1s" }} />
      <div className="absolute bottom-32 right-[30%] w-2.5 h-2.5 rounded-full bg-primary/30 animate-pulse-soft" style={{ animationDelay: "0.5s" }} />

      <div className="relative z-10 max-w-5xl mx-auto px-6 text-center">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-8 fade-in">
          <Brain className="w-4 h-4 text-primary" />
          <span className="text-sm text-primary font-medium">Cognitive AI Research</span>
        </div>

        {/* Main Headline */}
        <h1 className="text-5xl md:text-7xl font-bold text-foreground mb-6 leading-tight fade-in" style={{ animationDelay: "0.1s" }}>
          An AI that{" "}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-primary to-accent">
            understands you
          </span>
          <br />over time
        </h1>

        {/* Subheadline */}
        <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10 leading-relaxed fade-in" style={{ animationDelay: "0.2s" }}>
          Reflectra learns your personality, adapts to your communication style, 
          and provides reflective insights—not just answers. A cognitive companion 
          built for long-term personalization and self-understanding.
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 fade-in" style={{ animationDelay: "0.3s" }}>
          <Button 
            size="lg" 
            className="gap-2 px-8 py-6 text-base bg-primary hover:bg-primary/90 glow-primary"
            onClick={handleStartConversation}
          >
            <Sparkles className="w-5 h-5" />
            Start a Conversation
          </Button>
          <a href="#how-it-works">
            <Button variant="outline" size="lg" className="gap-2 px-8 py-6 text-base border-border hover:bg-muted">
              Explore How It Works
              <ArrowRight className="w-4 h-4" />
            </Button>
          </a>
        </div>

        {/* Trust indicators */}
        <div className="mt-16 pt-8 border-t border-border/50 fade-in" style={{ animationDelay: "0.4s" }}>
          <p className="text-xs text-muted-foreground/60 mb-4">Built on principles of</p>
          <div className="flex flex-wrap justify-center gap-8 text-sm text-muted-foreground">
            <span className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-primary" />
              Cognitive Science
            </span>
            <span className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-trait-empathetic" />
              Ethical AI Design
            </span>
            <span className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-accent" />
              Privacy-First Architecture
            </span>
          </div>
        </div>
      </div>

      {/* Scroll indicator */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-muted-foreground/40">
        <span className="text-xs">Scroll to explore</span>
        <div className="w-5 h-8 rounded-full border border-muted-foreground/20 flex items-start justify-center p-1">
          <div className="w-1 h-2 rounded-full bg-muted-foreground/40 animate-bounce" />
        </div>
      </div>
    </section>
  );
}
