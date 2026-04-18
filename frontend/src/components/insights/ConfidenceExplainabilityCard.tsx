import { Activity, Gauge, GitBranch, Info, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useConfidenceExplainability } from "@/hooks/useAnalytics";

interface ConfidenceExplainabilityCardProps {
  userId: string;
}

const SOURCE_LABELS: Record<string, string> = {
  conversations: "Raw Conversations",
  traits: "Extraction Traits",
  timeline_reflections: "Timeline Insights",
  reflection_summaries: "Reflection Summaries",
  external_inputs: "External Inputs",
};

export function ConfidenceExplainabilityCard({ userId }: ConfidenceExplainabilityCardProps) {
  const { data, isLoading, error, refetch, isFetching } = useConfidenceExplainability(userId);

  const contributionRows = Object.entries(data?.source_contributions || {})
    .sort((a, b) => b[1] - a[1])
    .map(([key, value]) => ({
      key,
      label: SOURCE_LABELS[key] || key,
      contributionPct: Math.round(value * 100),
      score: data?.source_scores?.[key] ?? 0,
      weight: data?.source_weights?.[key] ?? 0,
    }));

  return (
    <div className="bg-card border border-border rounded-xl p-6 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-1 h-full bg-accent" />

      <div className="flex items-center justify-between mb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-foreground flex items-center gap-2">
              <Gauge className="w-4 h-4 text-accent" />
              Confidence Explainability
            </h3>
          </div>
          <p className="text-sm text-muted-foreground">Per-source contribution to active mirror confidence interval</p>
        </div>
        <button
          onClick={() => void refetch()}
          disabled={isFetching}
          className="p-2 hover:bg-muted rounded-full transition-colors"
          aria-label="Refresh confidence explainability"
        >
          <RefreshCw className={cn("w-4 h-4 text-muted-foreground", isFetching && "animate-spin")} />
        </button>
      </div>

      {isLoading ? (
        <div className="h-36 animate-pulse bg-muted/40 rounded-lg border border-border" />
      ) : error ? (
        <div className="py-6 text-center text-sm text-red-500 bg-red-500/10 rounded-lg">Failed to load confidence explainability</div>
      ) : data ? (
        <div className="space-y-5">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-background border border-border rounded-lg p-3">
              <p className="text-xs text-muted-foreground uppercase tracking-wider">Tier</p>
              <p className="text-lg font-semibold text-foreground">{data.tier.replace("_", " ")}</p>
            </div>
            <div className="bg-background border border-border rounded-lg p-3">
              <p className="text-xs text-muted-foreground uppercase tracking-wider">Center</p>
              <p className="text-lg font-semibold text-foreground">{Math.round(data.center * 100)}%</p>
            </div>
            <div className="bg-background border border-border rounded-lg p-3">
              <p className="text-xs text-muted-foreground uppercase tracking-wider">Lower</p>
              <p className="text-lg font-semibold text-foreground">{Math.round(data.interval.lower * 100)}%</p>
            </div>
            <div className="bg-background border border-border rounded-lg p-3">
              <p className="text-xs text-muted-foreground uppercase tracking-wider">Upper</p>
              <p className="text-lg font-semibold text-foreground">{Math.round(data.interval.upper * 100)}%</p>
            </div>
          </div>

          <div className="space-y-3">
            {contributionRows.map((row) => (
              <div key={row.key} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-foreground font-medium">{row.label}</span>
                  <span className="text-muted-foreground">{row.contributionPct}% contribution</span>
                </div>
                <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full bg-primary"
                    style={{ width: `${Math.max(2, row.contributionPct)}%` }}
                  />
                </div>
                <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>score: {row.score.toFixed(2)}</span>
                  <span>weight: {row.weight.toFixed(2)}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="bg-background border border-border rounded-lg p-3">
              <p className="text-xs text-muted-foreground flex items-center gap-1 mb-1">
                <GitBranch className="w-3 h-3" /> Timeline Override
              </p>
              <p className="text-sm text-foreground">
                {data.timeline_recency_override.applied ? "Applied" : "Not applied"}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                recent {Math.round(data.timeline_recency_override.recent_avg * 100)}% vs older {Math.round(data.timeline_recency_override.older_avg * 100)}%
              </p>
              <p className="text-xs text-muted-foreground">
                strength {Math.round(data.timeline_recency_override.override_strength * 100)}%
              </p>
            </div>
            <div className="bg-background border border-border rounded-lg p-3">
              <p className="text-xs text-muted-foreground flex items-center gap-1 mb-1">
                <Activity className="w-3 h-3" /> Active Controls
              </p>
              <p className="text-xs text-muted-foreground">phrase freq: {(data.controls.phrase_usage_frequency * 100).toFixed(0)}%</p>
              <p className="text-xs text-muted-foreground">tone strength: {(data.controls.tone_strength * 100).toFixed(0)}%</p>
              <p className="text-xs text-muted-foreground">style intensity: {(data.controls.style_enforcement_intensity * 100).toFixed(0)}%</p>
              <p className="text-xs text-muted-foreground">uncertainty note: {data.controls.include_uncertainty_note ? "on" : "off"}</p>
            </div>
          </div>

          {data.message_used ? (
            <div className="bg-muted/30 border border-border rounded-lg p-3">
              <p className="text-xs text-muted-foreground flex items-center gap-1 mb-1">
                <Info className="w-3 h-3" /> Message Used
              </p>
              <p className="text-xs text-foreground line-clamp-2">{data.message_used}</p>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
