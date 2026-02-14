import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";

interface LandingHeaderProps {
  onShowLogin: () => void;
}

export function LandingHeader({ onShowLogin }: LandingHeaderProps) {
  const navigate = useNavigate();
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [displayName, setDisplayName] = useState("");

  useEffect(() => {
    const checkLoginStatus = () => {
      const userId = localStorage.getItem("user_id");
      const name = localStorage.getItem("display_name");
      setIsLoggedIn(!!userId);
      setDisplayName(name || "");
    };

    // Check on mount
    checkLoginStatus();

    // Check when window regains focus (user comes back from app)
    window.addEventListener("focus", checkLoginStatus);

    // Check when storage changes (works across tabs)
    window.addEventListener("storage", checkLoginStatus);

    return () => {
      window.removeEventListener("focus", checkLoginStatus);
      window.removeEventListener("storage", checkLoginStatus);
    };
  }, []);

  const handleCTA = () => {
    if (isLoggedIn) {
      navigate("/app");
    } else {
      onShowLogin();
    }
  };

  const handleFeatures = () => {
    const userId = localStorage.getItem("user_id");
    if (userId) {
      navigate("/app/personality");
    } else {
      onShowLogin();
    }
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-xl border-b border-border/50">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-3">
          <img
            src="/favicon.ico"
            alt="Reflectra Logo"
            className="h-8 w-8"
          />
          <span className="font-semibold text-foreground">Reflectra</span>
        </Link>

        {/* Navigation */}
        <nav className="hidden md:flex items-center gap-8">
          <a href="#how-it-works" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            How It Works
          </a>
          <button onClick={handleFeatures} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            Features
          </button>
        </nav>

        {/* CTA */}
        <button 
          onClick={handleCTA}
          className="px-5 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          {isLoggedIn ? `Logged in as ${displayName}` : "Try Reflectra"}
        </button>
      </div>
    </header>
  );
}
