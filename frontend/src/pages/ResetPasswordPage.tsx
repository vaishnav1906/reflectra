import { useState, useEffect, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle2, AlertCircle } from "lucide-react";

export function ResetPasswordPage() {
  const navigate = useNavigate();

  const [newPassword, setNewPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [hasRecoverySession, setHasRecoverySession] = useState(false);

  useEffect(() => {
    // supabase-js reads the recovery token from the email link (detectSessionInUrl)
    // and emits PASSWORD_RECOVERY once the temporary session is established.
    const { data: listener } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "PASSWORD_RECOVERY" || (session && event === "SIGNED_IN")) {
        setHasRecoverySession(true);
        setError("");
      }
    });

    supabase.auth.getSession().then(({ data }) => {
      if (data.session) {
        setHasRecoverySession(true);
      } else if (!window.location.hash.includes("access_token") && !window.location.search.includes("code=")) {
        setError("No reset token found. Please use the link from your email.");
      }
    });

    return () => listener.subscription.unsubscribe();
  }, []);

  const handleUpdatePassword = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!hasRecoverySession) {
      setError("This reset link is invalid or has expired. Request a new one.");
      return;
    }

    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    setIsLoading(true);
    const { error: updateError } = await supabase.auth.updateUser({ password: newPassword });
    setIsLoading(false);

    if (updateError) {
      setError(updateError.message || "Failed to update password.");
      return;
    }

    setSuccess("Password updated successfully.");
    setTimeout(() => navigate("/app/chat"), 1500);
  };

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4">
      <div className="absolute top-8 left-8 flex items-center gap-3">
        <img src="/favicon.ico" alt="Reflectra Logo" className="w-8 h-8 rounded-lg" />
        <span className="font-bold text-xl tracking-tight">Reflectra</span>
      </div>

      <Card className="w-full max-w-md shadow-xl border-border/50">
        <CardHeader>
          <CardTitle>Reset Password</CardTitle>
          <CardDescription>Enter your new password below.</CardDescription>
        </CardHeader>
        <CardContent>
          {success && (
            <div className="mb-4 bg-green-500/10 border border-green-500/20 text-green-400 p-3 flex items-start gap-2 rounded-md text-sm">
                <CheckCircle2 className="w-4 h-4 mt-0.5" />
                <span>{success} Redirecting…</span>
            </div>
          )}
          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 text-red-500 flex items-start gap-2 rounded-md text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleUpdatePassword} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="new-password">New Password</Label>
              <Input
                id="new-password"
                type="password"
                placeholder="••••••••"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                disabled={isLoading || !hasRecoverySession || !!success}
              />
            </div>
            
            <Button 
              type="submit" 
              className="w-full" 
              disabled={isLoading || !hasRecoverySession || !!success}
            >
              {isLoading ? 'Updating...' : 'Update Password'}
            </Button>
          </form>
          
          <div className="mt-6 text-center">
            <button
              onClick={() => navigate("/")}
              className="text-sm text-muted-foreground hover:text-foreground hover:underline"
            >
              Back to Home
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
