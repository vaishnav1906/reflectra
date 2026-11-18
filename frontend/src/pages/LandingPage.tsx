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
import { Tutorial } from "@/components/tutorial/Tutorial";
import { markTutorialDone } from "@/lib/tutorial";

/**
 * Immersive, scroll-driven landing page:
 * thoughts become a mirror -> it listens -> it learns you -> two modes ->
 * manifesto -> privacy -> "Meet yourself."
 */
export function LandingPage() {
  const [showLogin, setShowLogin] = useState(false);
  const [touring, setTouring] = useState(false);
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
      <ImmersiveNav signedIn={Boolean(user)} onPrimary={start} onTutorial={() => setTouring(true)} />
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
      {touring ? (
        <Tutorial
          onClose={() => {
            markTutorialDone(user?.id);
            setTouring(false);
          }}
          onStart={() => {
            markTutorialDone(user?.id);
            setTouring(false);
            start();
          }}
        />
      ) : null}
    </div>
  );
}
