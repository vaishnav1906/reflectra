import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LoginModal } from "@/components/LoginModal";
import { requestEntrance } from "@/components/transitions/EnterMirror";
import { useAuth } from "@/contexts/AuthContext";
import { SmoothScroll } from "@/components/immersive/SmoothScroll";
import { ImmersiveNav } from "@/components/immersive/ImmersiveNav";
import { HeroMirror } from "@/components/immersive/HeroMirror";
import { ConversationScene } from "@/components/immersive/ConversationScene";
import { TraitsScene } from "@/components/immersive/TraitsScene";
import { TwoMirrorsScene } from "@/components/immersive/TwoMirrorsScene";
import { ManifestoScene } from "@/components/immersive/ManifestoScene";
import { FinalCTA, ImmersiveFooter, PrivacySection } from "@/components/immersive/ClosingSections";
import "@/components/immersive/immersive.css";

/**
 * Immersive, scroll-driven landing page:
 * thoughts become a mirror -> it listens -> it learns you -> two modes ->
 * manifesto -> privacy -> "Meet yourself."
 */
export function LandingPage() {
  const [showLogin, setShowLogin] = useState(false);
  const { user } = useAuth();
  const navigate = useNavigate();

  const start = () => {
    if (user) {
      requestEntrance();
      navigate("/app/chat");
    } else {
      setShowLogin(true);
    }
  };

  return (
    <div className="grain min-h-screen bg-background">
      <SmoothScroll />
      <ImmersiveNav signedIn={Boolean(user)} onPrimary={start} />
      <main>
        <HeroMirror onStart={start} />
        <ConversationScene />
        <TraitsScene />
        <TwoMirrorsScene />
        <ManifestoScene />
        <PrivacySection />
        <FinalCTA onStart={start} />
      </main>
      <ImmersiveFooter />
      <LoginModal isOpen={showLogin} onClose={() => setShowLogin(false)} />
    </div>
  );
}
