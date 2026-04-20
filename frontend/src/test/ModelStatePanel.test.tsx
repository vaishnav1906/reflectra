import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ModelStatePanel } from "@/components/layout/ModelStatePanel";
import { toast } from "@/components/ui/sonner";

vi.mock("@/components/ui/sonner", () => ({
  toast: {
    warning: vi.fn(),
  },
}));

describe("ModelStatePanel low-confidence warning", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it("shows warning once when confidence is <= 10", async () => {
    localStorage.setItem("user_id", "test-user");
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        last_inference: null,
        memory_count: 0,
        confidence: 0,
        learning_active: false,
        cycle_days: 7,
      }),
    } as Response);

    render(<ModelStatePanel />);

    await waitFor(() => {
      expect(toast.warning).toHaveBeenCalledTimes(1);
    });

    const warningKey = "mirror-low-confidence-warning:test-user";
    expect(sessionStorage.getItem(warningKey)).toBe("1");
  });

  it("does not show warning when confidence is above 10", async () => {
    localStorage.setItem("user_id", "test-user");
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        last_inference: null,
        memory_count: 3,
        confidence: 10.1,
        learning_active: true,
        cycle_days: 7,
      }),
    } as Response);

    render(<ModelStatePanel />);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    expect(toast.warning).not.toHaveBeenCalled();
  });

  it("does not repeat warning when already shown in session", async () => {
    localStorage.setItem("user_id", "test-user");
    sessionStorage.setItem("mirror-low-confidence-warning:test-user", "1");

    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        last_inference: null,
        memory_count: 1,
        confidence: 5,
        learning_active: true,
        cycle_days: 7,
      }),
    } as Response);

    render(<ModelStatePanel />);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    expect(toast.warning).not.toHaveBeenCalled();
  });
});
