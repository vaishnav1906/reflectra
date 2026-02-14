import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const API_BASE = "/api";

// Email validation regex
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [emailError, setEmailError] = useState("");
  const [displayNameError, setDisplayNameError] = useState("");

  // Validate email on change
  const handleEmailChange = (value: string) => {
    setEmail(value);
    setEmailError("");
    setError("");
    
    if (value && !EMAIL_REGEX.test(value)) {
      setEmailError("Please enter a valid email address");
    }
  };

  // Validate display name on change
  const handleDisplayNameChange = (value: string) => {
    setDisplayName(value);
    setDisplayNameError("");
    setError("");
    
    if (value && value.trim().length === 0) {
      setDisplayNameError("Display name cannot be empty");
    }
  };

  // Check if form is valid
  const isFormValid = () => {
    const trimmedEmail = email.trim();
    const trimmedName = displayName.trim();
    
    return (
      trimmedEmail.length > 0 &&
      trimmedName.length > 0 &&
      EMAIL_REGEX.test(trimmedEmail) &&
      !emailError &&
      !displayNameError
    );
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setEmailError("");
    setDisplayNameError("");

    // Trim inputs
    const trimmedEmail = email.trim();
    const trimmedName = displayName.trim();

    // Final validation
    if (!trimmedEmail) {
      setEmailError("Email is required");
      return;
    }

    if (!EMAIL_REGEX.test(trimmedEmail)) {
      setEmailError("Please enter a valid email address");
      return;
    }

    if (!trimmedName) {
      setDisplayNameError("Display name is required");
      return;
    }

    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: trimmedEmail.toLowerCase(),
          display_name: trimmedName,
        }),
      });

      if (!res.ok) {
        // Handle validation errors (422)
        if (res.status === 422) {
          const errorData = await res.json();
          const detail = errorData?.detail;
          
          if (Array.isArray(detail) && detail.length > 0) {
            const firstError = detail[0];
            if (firstError.loc?.includes("email")) {
              setEmailError(firstError.msg || "Invalid email format");
            } else if (firstError.loc?.includes("display_name")) {
              setDisplayNameError(firstError.msg || "Invalid display name");
            } else {
              setError(firstError.msg || "Validation failed");
            }
          } else {
            setError("Invalid input. Please check your email and name.");
          }
          return;
        }
        
        throw new Error("Login failed");
      }

      const data = await res.json();
      
      // Save to localStorage
      localStorage.setItem("user_id", data.id);
      localStorage.setItem("display_name", data.display_name);
      localStorage.setItem("email", data.email);

      // Navigate to main app
      navigate("/app/chat");
    } catch (err) {
      setError("Failed to login. Please try again.");
      console.error("Login error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background gradient-mesh">
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="flex items-center gap-3 mb-4">
            <img
              src="/favicon.ico"
              alt="Reflectra Logo"
              className="w-10 h-10 rounded-xl"
            />
            <div>
              <CardTitle>Welcome to Reflectra</CardTitle>
              <CardDescription>Enter your details to continue</CardDescription>
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
                placeholder="your@email.com"
                value={email}
                onChange={(e) => handleEmailChange(e.target.value)}
                required
                disabled={isLoading}
                className={emailError ? "border-destructive" : ""}
              />
              {emailError && (
                <p className="text-sm text-destructive">{emailError}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="displayName">Display Name</Label>
              <Input
                id="displayName"
                type="text"
                placeholder="Your Name"
                value={displayName}
                onChange={(e) => handleDisplayNameChange(e.target.value)}
                required
                disabled={isLoading}
                className={displayNameError ? "border-destructive" : ""}
              />
              {displayNameError && (
                <p className="text-sm text-destructive">{displayNameError}</p>
              )}
            </div>
            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}
            <Button 
              type="submit" 
              className="w-full" 
              disabled={isLoading || !isFormValid()}
            >
              {isLoading ? "Logging in..." : "Continue"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
