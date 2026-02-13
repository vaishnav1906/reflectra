import { HeroSection } from "@/components/landing/HeroSection";
import { ProblemSection } from "@/components/landing/ProblemSection";
import { SolutionSection } from "@/components/landing/SolutionSection";
import { HowItWorksSection } from "@/components/landing/HowItWorksSection";
import { FeaturesSection } from "@/components/landing/FeaturesSection";
import { WhyReflectSection } from "@/components/landing/WhyReflectSection";
import { UseCasesSection } from "@/components/landing/UseCasesSection";
import { PrivacySection } from "@/components/landing/PrivacySection";
import { CTASection } from "@/components/landing/CTASection";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { LandingFooter } from "@/components/landing/LandingFooter";

export function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      <LandingHeader />
      <main>
        <HeroSection />
        <ProblemSection />
        <SolutionSection />
        <HowItWorksSection />
        <FeaturesSection />
        <WhyReflectSection />
        <UseCasesSection />
        <PrivacySection />
        <CTASection />
      </main>
      <LandingFooter />
    </div>
  );
}
