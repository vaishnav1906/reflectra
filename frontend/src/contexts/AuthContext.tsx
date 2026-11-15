import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import { apiFetch } from "@/lib/api";

export interface AppUser {
  id: string;
  display_name: string;
  email: string;
}

interface AuthContextValue {
  session: Session | null;
  user: AppUser | null;
  /** True until the initial session (and app user) have been resolved. */
  loading: boolean;
  /** Set when the session exists but the backend refused it (e.g. unconfirmed email). */
  authError: string | null;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// Legacy keys still read by a few components for display purposes.
// Identity on the backend always comes from the access token, never from these.
const PROFILE_KEYS = ["user_id", "display_name", "email"] as const;

function storeProfile(user: AppUser | null) {
  if (user) {
    localStorage.setItem("user_id", user.id);
    localStorage.setItem("display_name", user.display_name);
    localStorage.setItem("email", user.email);
  } else {
    PROFILE_KEYS.forEach((key) => localStorage.removeItem(key));
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<AppUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);

  const loadAppUser = useCallback(async (nextSession: Session | null) => {
    if (!nextSession) {
      setUser(null);
      storeProfile(null);
      return;
    }
    try {
      const res = await apiFetch("/api/auth/me");
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setAuthError(typeof body?.detail === "string" ? body.detail : "Could not load your account.");
        setUser(null);
        storeProfile(null);
        return;
      }
      const appUser = (await res.json()) as AppUser;
      setAuthError(null);
      setUser(appUser);
      storeProfile(appUser);
    } catch {
      setAuthError("Could not reach the server.");
      setUser(null);
    }
  }, []);

  useEffect(() => {
    let active = true;

    supabase.auth.getSession().then(async ({ data }) => {
      if (!active) return;
      setSession(data.session);
      await loadAppUser(data.session);
      if (active) setLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((event, nextSession) => {
      if (!active) return;
      setSession(nextSession);
      // Token refreshes don't change who the user is; only reload on real changes.
      if (event === "SIGNED_IN" || event === "SIGNED_OUT" || event === "USER_UPDATED") {
        // Defer: calling Supabase from inside this callback can deadlock its auth lock.
        setTimeout(() => {
          void loadAppUser(nextSession);
        }, 0);
      }
    });

    return () => {
      active = false;
      listener.subscription.unsubscribe();
    };
  }, [loadAppUser]);

  const signOut = useCallback(async () => {
    await supabase.auth.signOut();
    setSession(null);
    setUser(null);
    storeProfile(null);
  }, []);

  const value = useMemo(
    () => ({ session, user, loading, authError, signOut }),
    [session, user, loading, authError, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
