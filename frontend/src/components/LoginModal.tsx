import { useState, FormEvent, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { X } from "lucide-react";
import { MirrorMark } from "@/components/MirrorMark";
import { supabase, isSupabaseConfigured } from "@/lib/supabase";
import { useAuth } from "@/contexts/AuthContext";
import { requestEntrance } from "@/components/transitions/EnterMirror";

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type AuthMode = "signin" | "signup" | "forgot";

const MODE_COPY: Record<AuthMode, { description: string; submit: string; busy: string }> = {
  signin: { description: "Sign in to continue", submit: "Sign in", busy: "Signing in..." },
  signup: { description: "Create your account", submit: "Create account", busy: "Creating account..." },
  forgot: { description: "We'll email you a reset link", submit: "Send reset link", busy: "Sending..." },
};

function GoogleMark() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.06l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z" />
    </svg>
  );
}

export function LoginModal({ isOpen, onClose }: LoginModalProps) {
  const navigate = useNavigate();
  const { authError } = useAuth();
  const [mode, setMode] = useState<AuthMode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isOpen]);

  // Handle ESC key
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [isOpen, onClose]);

  // Surface backend refusals (e.g. unconfirmed email) when the modal opens.
  useEffect(() => {
    if (isOpen && authError) {
      setError(authError);
    }
  }, [isOpen, authError]);

  const switchMode = (next: AuthMode) => {
    setMode(next);
    setError("");
    setNotice("");
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setNotice("");

    if (!isSupabaseConfigured) {
      setError("Sign-in is not configured for this deployment.");
      return;
    }

    const normalizedEmail = email.trim().toLowerCase();
    setIsLoading(true);
    try {
      if (mode === "forgot") {
        const { error: resetError } = await supabase.auth.resetPasswordForEmail(normalizedEmail, {
          redirectTo: `${window.location.origin}/reset-password`,
        });
        if (resetError) throw resetError;
        setNotice("If an account exists for that email, a reset link is on its way.");
        return;
      }

      if (mode === "signup") {
        if (password.length < 8) {
          setError("Password must be at least 8 characters long.");
          return;
        }
        const { data, error: signUpError } = await supabase.auth.signUp({
          email: normalizedEmail,
          password,
          options: {
            data: { display_name: displayName.trim() },
            emailRedirectTo: `${window.location.origin}/app/chat`,
          },
        });
        if (signUpError) throw signUpError;
        if (!data.session) {
          // Email confirmation is required before the first sign-in.
          setMode("signin");
          setNotice("Check your email to confirm your account, then sign in.");
          return;
        }
        requestEntrance();
        navigate("/app/chat");
        return;
      }

      const { error: signInError } = await supabase.auth.signInWithPassword({
        email: normalizedEmail,
        password,
      });
      if (signInError) throw signInError;
      requestEntrance();
      navigate("/app/chat");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogle = async () => {
    setError("");
    setNotice("");
    if (!isSupabaseConfigured) {
      setError("Sign-in is not configured for this deployment.");
      return;
    }
    setIsLoading(true);
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/app/chat` },
    });
    // On success the browser leaves for Google, so only a failure comes back here.
    if (oauthError) {
      setError(oauthError.message);
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  const copy = MODE_COPY[mode];

  return (
    <div
      className="safe-overlay fixed inset-0 z-50 flex items-center justify-center p-4 animate-in fade-in duration-200"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-background/70 backdrop-blur-xl" />

      {/* Modal Card */}
      <Card
        role="dialog"
        aria-modal="true"
        aria-label="Sign in to Reflectra"
        data-lenis-prevent
        className="glass-panel iris-border fog-card w-full max-w-md relative z-10 rounded-3xl border-0 bg-transparent"
        onClick={(e) => e.stopPropagation()}
      >
        {/* The card condenses out of a mist that clears as it settles. */}
        <div className="fog-mist" aria-hidden="true" />
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1 rounded-lg hover:bg-muted transition-colors"
          aria-label="Close"
        >
          <X className="w-5 h-5 text-muted-foreground hover:text-foreground" />
        </button>

        <CardHeader>
          <div className="flex items-center gap-3 mb-4">
            <MirrorMark className="h-11 w-11" />
            <div>
              <CardTitle className="font-display text-3xl font-normal">Welcome to Reflectra</CardTitle>
              <CardDescription>{copy.description}</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {mode !== "forgot" && (
            <>
              <Button
                type="button"
                variant="outline"
                className="w-full gap-2"
                onClick={handleGoogle}
                disabled={isLoading}
              >
                <GoogleMark />
                Continue with Google
              </Button>
              <div className="my-4 flex items-center gap-3 text-xs text-muted-foreground" aria-hidden="true">
                <span className="h-px flex-1 bg-border" />
                or use your email
                <span className="h-px flex-1 bg-border" />
              </div>
            </>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>
            {mode === "signup" && (
              <div className="space-y-2">
                <Label htmlFor="displayName">Display Name</Label>
                <Input
                  id="displayName"
                  type="text"
                  autoComplete="nickname"
                  placeholder="Your Name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  required
                  disabled={isLoading}
                />
              </div>
            )}
            {mode !== "forgot" && (
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <PasswordInput
                  id="password"
                  autoComplete={mode === "signup" ? "new-password" : "current-password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={mode === "signup" ? 8 : undefined}
                  disabled={isLoading}
                />
              </div>
            )}
            {error && <p className="text-sm text-destructive">{error}</p>}
            {notice && <p className="text-sm text-muted-foreground">{notice}</p>}
            <Button type="submit" className="btn-mirror w-full border-0" disabled={isLoading}>
              {isLoading ? copy.busy : copy.submit}
            </Button>
          </form>
          <div className="mt-4 flex flex-col items-center gap-2 text-sm text-muted-foreground">
            {mode === "signin" ? (
              <>
                <button type="button" className="hover:text-foreground hover:underline" onClick={() => switchMode("forgot")}>
                  Forgot password?
                </button>
                <button type="button" className="hover:text-foreground hover:underline" onClick={() => switchMode("signup")}>
                  New here? Create an account
                </button>
              </>
            ) : (
              <button type="button" className="hover:text-foreground hover:underline" onClick={() => switchMode("signin")}>
                Back to sign in
              </button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
