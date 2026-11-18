import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const signInWithOAuth = vi.fn();

vi.mock("@/lib/supabase", () => ({
  isSupabaseConfigured: true,
  supabase: { auth: { signInWithOAuth: (args: unknown) => signInWithOAuth(args) } },
}));
vi.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ authError: null }) }));

import { LoginModal } from "@/components/LoginModal";

const open = () =>
  render(
    <MemoryRouter>
      <LoginModal isOpen onClose={vi.fn()} />
    </MemoryRouter>,
  );

beforeEach(() => signInWithOAuth.mockReset());

describe("Continue with Google", () => {
  it("starts Google sign-in and comes back to the chat", async () => {
    signInWithOAuth.mockResolvedValue({ error: null });
    open();
    fireEvent.click(screen.getByRole("button", { name: /continue with google/i }));
    await waitFor(() => expect(signInWithOAuth).toHaveBeenCalledTimes(1));
    expect(signInWithOAuth).toHaveBeenCalledWith({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/app/chat` },
    });
  });

  it("shows the reason when Google sign-in can't start", async () => {
    signInWithOAuth.mockResolvedValue({ error: { message: "Unsupported provider: provider is not enabled" } });
    open();
    fireEvent.click(screen.getByRole("button", { name: /continue with google/i }));
    expect(await screen.findByText(/provider is not enabled/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /continue with google/i })).toBeEnabled();
  });

  it("is on sign in and create account, but not on the reset-password form", () => {
    open();
    expect(screen.getByRole("button", { name: /continue with google/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /create an account/i }));
    expect(screen.getByRole("button", { name: /continue with google/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /back to sign in/i }));
    fireEvent.click(screen.getByRole("button", { name: /forgot password/i }));
    expect(screen.queryByRole("button", { name: /continue with google/i })).not.toBeInTheDocument();
  });
});
