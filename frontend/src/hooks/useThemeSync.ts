import { useEffect } from "react";
import { useProfile } from "@/components/settings/AboutYou";
import { applyTheme, cleanTheme, forgetTheme, rememberTheme, storedTheme } from "@/lib/theme";
import { saveThemeToAccount, themePending } from "@/lib/themeAccount";

/**
 * Keep this device's colour and the account's in step.
 *
 * - A choice made here that hasn't reached the account yet wins: it's sent now.
 * - Otherwise the account wins (you picked a colour on another device).
 * Only fresh data from the server is trusted, never a cached copy from earlier.
 */
export function useThemeSync() {
  const { data, isFetchedAfterMount } = useProfile();
  useEffect(() => {
    if (!data || !isFetchedAfterMount) return;
    const local = storedTheme();

    if (themePending()) {
      void saveThemeToAccount(local).catch(() => undefined); // retried on the next visit if it fails
      return;
    }
    if (!data.theme) {
      if (local) forgetTheme();
      return;
    }
    const account = cleanTheme(data.theme);
    if (!local || local.hue !== account.hue || local.saturation !== account.saturation) {
      applyTheme(account);
      rememberTheme(account);
    }
  }, [data, isFetchedAfterMount]);
}
