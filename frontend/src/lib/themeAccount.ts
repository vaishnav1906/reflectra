import type { QueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { Theme, cleanTheme } from "@/lib/theme";

/**
 * Keeping your colour in step between this device and your account.
 *
 * A choice is made here first (instant), then saved to the account. Until the save
 * is confirmed the choice is marked "pending", so the sign-in sync never mistakes an
 * older account value for the truth and undoes what you just picked.
 */

const PENDING_KEY = "reflectra:theme-pending";

export function markThemePending(pending: boolean) {
  try {
    if (pending) localStorage.setItem(PENDING_KEY, "1");
    else localStorage.removeItem(PENDING_KEY);
  } catch {
    /* storage blocked */
  }
}

export function themePending(): boolean {
  try {
    return localStorage.getItem(PENDING_KEY) === "1";
  } catch {
    return false;
  }
}

/** Update the cached profile straight away, so nothing reads the old colour from it. */
export function cacheTheme(queryClient: QueryClient, theme: Theme | null) {
  queryClient.setQueriesData({ queryKey: ["profile"] }, (old: unknown) =>
    old && typeof old === "object" ? { ...(old as object), theme: theme ? cleanTheme(theme) : null } : old,
  );
}

/** Save to the account (null = back to the default). Clears "pending" once it's stored. */
export async function saveThemeToAccount(theme: Theme | null): Promise<void> {
  const res = await apiFetch("/api/user/profile", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ theme: theme ? cleanTheme(theme) : {} }),
  });
  if (!res.ok) throw new Error("Couldn't save your colour.");
  markThemePending(false);
}
