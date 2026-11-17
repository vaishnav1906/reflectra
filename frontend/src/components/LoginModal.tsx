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

  if (!isOpen) return null;

  const copy = MODE_COPY[mode];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-in fade-in duration-200"
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
