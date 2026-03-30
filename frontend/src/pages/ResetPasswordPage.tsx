import { useState, useEffect, FormEvent } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle2, AlertCircle } from "lucide-react";

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const location = useLocation();
  
  const [newPassword, setNewPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  
  const [accessToken, setAccessToken] = useState("");
  const [refreshToken, setRefreshToken] = useState("");

  useEffect(() => {
    // Supabase redirects to /reset-password#access_token=...&refresh_token=...
    const hash = window.location.hash;
    if (hash) {
      const hashParams = new URLSearchParams(hash.substring(1));
      const access_token = hashParams.get("access_token");
      const refresh_token = hashParams.get("refresh_token");
      const type = hashParams.get("type");

      if (access_token) {
        setAccessToken(access_token);
      }
      if (refresh_token) {
        setRefreshToken(refresh_token);
      }
      
      if (type === "recovery" && access_token) {
        // Clear the hash from the URL for security
        window.history.replaceState(null, "", window.location.pathname);
      } else if (!access_token) {
        setError("Invalid or expired reset link. Please try again.");
      }
    } else {
      setError("No reset token found in URL. Please use the link from your email.");
    }
  }, [location]);

  const handleUpdatePassword = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    
    if (!accessToken) {
      setError("Missing authorization token. Try requesting a new reset link.");
      return;
    }
    
    if (newPassword.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }

    setIsLoading(true);

    try {
      const res = await fetch(`/api/auth/update-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          access_token: accessToken,
          refresh_token: refreshToken || accessToken,
          new_password: newPassword 
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Failed to update password");
      }

      setSuccess("Password updated successfully.");
      setTimeout(() => {
        navigate("/"); // Redirect to landing/login
      }, 2000);
      
    } catch (err: any) {
      setError(err.message || "Something went wrong.");
    } finally {
      setIsLoading(false);
    }
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
                <span>{success} Redirecting to login...</span>
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
                disabled={isLoading || !accessToken || !!success}
              />
            </div>
            
            <Button 
              type="submit" 
              className="w-full" 
              disabled={isLoading || !accessToken || !!success}
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
