import { Shield, Eye, Edit, Download, Lock } from "lucide-react";

const principles = [
  {
    icon: Eye,
    title: "Full Transparency",
    description: "See exactly what the AI understands about you at any time",
  },
  {
    icon: Edit,
    title: "Memory Control",
    description: "Edit or delete any trait, memory, or insight with one click",
  },
  {
    icon: Download,
    title: "Data Portability",
    description: "Export all your data in standard formats whenever you want",
  },
  {
    icon: Lock,
    title: "End-to-End Encryption",
    description: "Your data is encrypted at rest and in transit—always",
  },
];

export function PrivacySection() {
  return (
    <section className="py-24 px-6 relative">
      <div className="max-w-6xl mx-auto">
        <div className="bg-gradient-to-br from-card via-card to-primary/5 border border-border rounded-3xl p-8 md:p-12">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            {/* Left: Content */}
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-trait-consistent/10 border border-trait-consistent/20 mb-6">
                <Shield className="w-4 h-4 text-trait-consistent" />
                <span className="text-sm text-trait-consistent font-medium">Privacy & Ethics First</span>
              </div>
              
              <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
                Your data, your control
              </h2>
              <p className="text-muted-foreground leading-relaxed mb-8">
                We believe AI personalization shouldn't come at the cost of privacy. 
                Reflectra is designed from the ground up to give you complete ownership 
                and control over your data—with no exceptions.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {principles.map((principle) => (
                  <div key={principle.title} className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
                      <principle.icon className="w-4 h-4 text-foreground" />
                    </div>
                    <div>
                      <h3 className="font-medium text-foreground text-sm">{principle.title}</h3>
                      <p className="text-xs text-muted-foreground">{principle.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Right: Visual */}
            <div className="flex justify-center">
              <div className="relative">
                {/* Shield visualization */}
                <div className="w-48 h-56 relative">
                  <div className="absolute inset-0 bg-gradient-to-b from-trait-consistent/20 to-trait-consistent/5 rounded-t-full rounded-b-[40%] border border-trait-consistent/30" />
                  <div className="absolute inset-4 bg-gradient-to-b from-trait-consistent/10 to-transparent rounded-t-full rounded-b-[40%]" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Shield className="w-16 h-16 text-trait-consistent/60" />
                  </div>
                </div>
                
                {/* Floating locks */}
                <div className="absolute -top-4 -left-8 w-8 h-8 rounded-lg bg-card border border-border flex items-center justify-center">
                  <Lock className="w-4 h-4 text-muted-foreground" />
                </div>
                <div className="absolute -bottom-4 -right-8 w-8 h-8 rounded-lg bg-card border border-border flex items-center justify-center">
                  <Lock className="w-4 h-4 text-muted-foreground" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
