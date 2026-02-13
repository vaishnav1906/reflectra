import { Link } from "react-router-dom";
import { ArrowRight, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

export function CTASection() {
  return (
    <section className="py-32 px-6 relative">
      {/* Background effects */}
      <div className="absolute inset-0 bg-gradient-to-t from-primary/5 via-transparent to-transparent" />
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-primary/10 rounded-full blur-[100px]" />
      
      <div className="relative max-w-3xl mx-auto text-center">
        <h2 className="text-4xl md:text-5xl font-bold text-foreground mb-6">
          Ready to meet an AI that{" "}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent">
            remembers
          </span>
          ?
        </h2>
        <p className="text-lg text-muted-foreground mb-10 max-w-xl mx-auto">
          Start a conversation with Reflectra and experience what personalized, 
          reflective AI interaction feels like.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link to="/chat">
            <Button size="lg" className="gap-2 px-10 py-6 text-lg bg-primary hover:bg-primary/90 glow-primary">
              <Sparkles className="w-5 h-5" />
              Start Your Journey
            </Button>
          </Link>
          <Link to="/personality">
            <Button variant="outline" size="lg" className="gap-2 px-8 py-6 text-base">
              Explore Features
              <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
        </div>

        <p className="mt-8 text-sm text-muted-foreground/60">
          No account required to explore • Your data stays private
        </p>
      </div>
    </section>
  );
}
