import { useState, FormEvent, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { X } from "lucide-react";

const API_BASE = "/api";

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function LoginModal({ isOpen, onClose }: LoginModalProps) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

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

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          display_name: displayName,
        }),
      });

      if (!res.ok) {
        throw new Error("Login failed");
      }

      const data = await res.json();
      
      console.log("🔐 Login successful!");
      console.log("👤 User ID:", data.id);
      console.log("📧 Email:", data.email);
      console.log("✨ Display Name:", data.display_name);
      
      // Save to localStorage
      localStorage.setItem("user_id", data.id);
      localStorage.setItem("display_name", data.display_name);
      localStorage.setItem("email", data.email);
      
      console.log("💾 Saved to localStorage");
      console.log("  - user_id:", localStorage.getItem("user_id"));
      console.log("  - display_name:", localStorage.getItem("display_name"));
      console.log("  - email:", localStorage.getItem("email"));

      // Navigate to main app
      navigate("/app/chat");
    } catch (err) {
      setError("Failed to login. Please try again.");
      console.error("Login error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-in fade-in duration-200"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-background/80 backdrop-blur-md" />
      
      {/* Modal Card */}
      <Card 
        className="w-full max-w-md relative z-10 animate-in zoom-in-95 duration-200 shadow-2xl border-border/50"
        onClick={(e) => e.stopPropagation()}
      >
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
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="displayName">Display Name</Label>
              <Input
                id="displayName"
                type="text"
                placeholder="Your Name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>
            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? "Logging in..." : "Continue"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
