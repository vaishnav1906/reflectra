import { supabase } from "@/lib/supabase";

/**
 * fetch() for backend calls: attaches the current Supabase access token.
 *
 * Supabase refreshes tokens automatically; getSession() returns the current
 * (refreshed) session from local storage without a network round trip.
 * A 401 from the backend means the session is no longer valid, so we sign out.
 */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);

  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(input, { ...init, headers });

  if (response.status === 401 && token) {
    await supabase.auth.signOut();
  }

  return response;
}
