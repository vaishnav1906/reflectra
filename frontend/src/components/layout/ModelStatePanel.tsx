import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { toast } from "@/components/ui/sonner";
import { CountUp } from "@/components/motion/CountUp";

import { apiFetch } from "@/lib/api";
const API_BASE = "/api";

interface SystemState {
  last_inference: string | null;
  memory_count: number;
  confidence: number;
  learning_active: boolean;
  cycle_days: number;
  messages?: number;
  confidence_range?: [number, number];
  learning_enabled?: boolean;
  confidence_tier?: string;
}

/** How well Reflectra knows you, lowest first. Moving up a step is a small moment. */
const TIERS = ["very_low", "partial", "moderate", "high"];
const TIER_NEWS: Record<string, string> = {
  partial: "Reflectra is starting to know you.",
  moderate: "Reflectra knows you fairly well now.",
  high: "Reflectra knows you well now.",
};
export const MILESTONE_EVENT = "reflectra:milestone";

/** Celebrate once when the tier goes up (never on the first visit, never twice). */
function noticeMilestone(userId: string, tier: string | undefined) {
  if (!tier || !TIERS.includes(tier)) return;
  const key = `reflectra-tier:${userId}`;
  let before: string | null = null;
  try {
    before = localStorage.getItem(key);
    localStorage.setItem(key, tier);
  } catch {
    return;
  }
  if (before && TIERS.indexOf(tier) > TIERS.indexOf(before) && TIER_NEWS[tier]) {
    window.dispatchEvent(new CustomEvent(MILESTONE_EVENT, { detail: TIER_NEWS[tier] }));
    toast.success(TIER_NEWS[tier]);
  }
}

function formatTimeAgo(isoTimestamp: string | null): string {
  if (!isoTimestamp) return "--";
  
  const now = new Date();
  const past = new Date(isoTimestamp);
  const diffMs = now.getTime() - past.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

export function ModelStatePanel() {
  const [systemState, setSystemState] = useState<SystemState | null>(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    let isMounted = true;

    const fetchSystemState = async () => {
      const userId = localStorage.getItem("user_id");
      if (!userId) {
        if (isMounted) {
          setSystemState(null);
          setLoading(false);
        }
        return;
      }
      
      try {
        const response = await apiFetch(`${API_BASE}/user/system-state?user_id=${userId}`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data: SystemState = await response.json();
        if (isMounted) {
          setSystemState(data);
          noticeMilestone(userId, data.confidence_tier);

          const warningKey = `mirror-low-confidence-warning:${userId}`;
          const alreadyWarned = sessionStorage.getItem(warningKey) === "1";
          if (data.confidence <= 10 && !alreadyWarned) {
            toast.warning(
              "Reflectra barely knows you yet, so Mirror mode won't sound much like you. A few Reflection chats will fix that.",
            );
            sessionStorage.setItem(warningKey, "1");
          }
        }
      } catch (error) {
        console.error("❌ Failed to fetch system state:", error);
        if (isMounted) {
          setSystemState(null);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchSystemState();

    const intervalId = window.setInterval(fetchSystemState, 30_000);

    return () => {
      isMounted = false;
      window.clearInterval(intervalId);
    };
  }, []);
  
  const paused = systemState ? systemState.learning_enabled === false : false;
  const messages = systemState?.messages;
  const rows: { label: string; value: React.ReactNode; hint: string }[] = [
    {
      label: "Messages read",
      value: loading ? "…" : messages != null ? <CountUp value={messages} /> : "–",
      hint: "How many of your messages Reflectra has learned from.",
    },
    {
      label: "How sure it is",
      value: loading ? "…" : systemState ? <CountUp value={Math.round(systemState.confidence)} suffix="%" /> : "–",
      hint: systemState?.confidence_range
        ? `Overall confidence, likely between ${systemState.confidence_range[0]} and ${systemState.confidence_range[1]}. It combines how settled your traits are, how much you've talked and over how many days, how much of your writing it has, and your reflections. "How it works" shows the breakdown.`
        : "Overall confidence that Reflectra knows you.",
    },
    {
      label: "Last learned",
      value: loading ? "…" : formatTimeAgo(systemState?.last_inference || null),
      hint: "The last time a message of yours changed a trait.",
    },
  ];

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">What it knows</h3>
        <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <span className={cn("h-1.5 w-1.5 rounded-full", paused ? "bg-iris-peach" : "bg-iris-cyan")} />
          {loading ? "…" : paused ? "Learning paused" : "Learning"}
        </span>
      </div>

      <dl className="mt-3 space-y-2.5">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between gap-2">
            <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
              {row.label}
              <InfoTooltip content={row.hint} side="right" />
            </dt>
            <dd className="font-mono text-xs text-foreground">{row.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
