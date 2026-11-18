/**
 * When the tutorial shows by itself: once, for someone new, on each device.
 *
 * "New" means the account is less than NEW_ACCOUNT_DAYS old, so people who've used
 * Reflectra for a while aren't interrupted (they can open it from the homepage).
 * Finishing it or pressing Skip both count as done.
 */

export const NEW_ACCOUNT_DAYS = 3;
const key = (userId: string) => `reflectra:tutorial-done:${userId}`;

export function tutorialDone(userId: string): boolean {
  try {
    return localStorage.getItem(key(userId)) === "1";
  } catch {
    return true; // can't remember it, so don't keep forcing it
  }
}

export function markTutorialDone(userId: string | null | undefined): void {
  if (!userId) return;
  try {
    localStorage.setItem(key(userId), "1");
  } catch {
    /* private mode: it may show once more, which is fine */
  }
}

export function isNewAccount(memberSince: string | null | undefined, now = Date.now()): boolean {
  if (!memberSince) return false;
  const started = new Date(memberSince).getTime();
  if (Number.isNaN(started)) return false;
  return now - started < NEW_ACCOUNT_DAYS * 86_400_000;
}

export function shouldAutoStartTutorial(userId: string | null | undefined, memberSince: string | null | undefined, now = Date.now()): boolean {
  return Boolean(userId) && isNewAccount(memberSince, now) && !tutorialDone(userId as string);
}
