import { useQuery } from '@tanstack/react-query';

export interface BehavioralMetric {
  timestamp: string;
  message_count: number;
  total_tokens: number;
  emotional_intensity: number | null;
  reflection_depth: number | null;
  response_delay_ms: number | null;
}

export interface MetricTotals {
  message_count: number;
}

export interface BehavioralMetricsResponse {
  view: 'day' | 'week' | 'month' | 'all';
  start_date: string;
  totals: MetricTotals;
  timeline: BehavioralMetric[];
}

export interface BehavioralInsight {
  id: string;
  text: string;
  tags: string[];
  confidence: number | null;
  created_at: string;
}

export interface HeatmapResponse {
  range_days: number;
  heatmap: number[][]; // 7 days (0=Sunday), 24 hours
}

export type TimelineRange = '7d' | '30d' | '90d';
export type TimelineTrend = 'up' | 'down' | 'stable';

export interface TimelineEvent {
  id: string;
  period: string;
  observation: string;
  trend: TimelineTrend;
  context?: string;
  created_at: string;
  source: 'insight' | 'persona' | 'schedule' | 'mirror' | 'unknown';
  confidence: number | null;
  tags: string[];
  severity: number;
}

export interface TimelineResponse {
  range: TimelineRange;
  start_date: string;
  end_date: string;
  overview: string;
  events: TimelineEvent[];
}

export interface ConfidenceExplainabilityControls {
  phrase_usage_frequency: number;
  tone_strength: number;
  reaction_accuracy_threshold: number;
  style_enforcement_intensity: number;
  include_uncertainty_note: boolean;
}

export interface ConfidenceExplainabilityResponse {
  center: number;
  interval: {
    lower: number;
    upper: number;
  };
  tier: 'very_low' | 'partial' | 'moderate' | 'high';
  source_scores: Record<string, number>;
  source_weights: Record<string, number>;
  source_contributions: Record<string, number>;
  timeline_recency_override: {
    applied: boolean;
    recent_avg: number;
    older_avg: number;
    override_strength: number;
  };
  controls: ConfidenceExplainabilityControls;
  message_used: string;
}

export function useBehavioralMetrics(userId: string, view: 'day' | 'week' | 'month' | 'all') {
  return useQuery({
    queryKey: ['analytics', 'metrics', userId, view],
    queryFn: async (): Promise<BehavioralMetricsResponse> => {
      const response = await fetch(`/api/analytics/metrics/${userId}?view=${view}`);
      if (!response.ok) throw new Error('Failed to fetch metrics');
      return response.json();
    },
    enabled: !!userId && userId !== "anonymous",
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useActivityHeatmap(userId: string, days: number = 30) {
  return useQuery({
    queryKey: ['analytics', 'heatmap', userId, days],
    queryFn: async (): Promise<HeatmapResponse> => {
      const response = await fetch(`/api/analytics/heatmap/${userId}?days=${days}`);
      if (!response.ok) throw new Error('Failed to fetch heatmap');
      return response.json();
    },
    enabled: !!userId && userId !== "anonymous",
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

export function useReflections(userId: string, range: '1d' | '2d' | '3d' | '7d' | '30d' | '90d' = '30d') {
  return useQuery({
    queryKey: ['analytics', 'reflections', userId, range],
    queryFn: async (): Promise<BehavioralInsight[]> => {
      const response = await fetch(`/api/analytics/reflections/${userId}?range=${range}`);
      if (!response.ok) throw new Error('Failed to fetch reflections');
      return response.json();
    },
    enabled: !!userId && userId !== "anonymous",
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useTimelineEvents(userId: string, range: TimelineRange = '7d') {
  return useQuery({
    queryKey: ['analytics', 'timeline', userId, range],
    queryFn: async (): Promise<TimelineResponse> => {
      const response = await fetch(`/api/analytics/timeline/${userId}?range=${range}`);
      if (!response.ok) throw new Error('Failed to fetch timeline events');
      return response.json();
    },
    enabled: !!userId && userId !== 'anonymous',
    staleTime: 5 * 60 * 1000,
  });
}

export function useConfidenceExplainability(userId: string, message?: string) {
  return useQuery({
    queryKey: ['analytics', 'confidence-explainability', userId, message || 'latest'],
    queryFn: async (): Promise<ConfidenceExplainabilityResponse> => {
      const params = new URLSearchParams();
      if (message && message.trim()) {
        params.set('message', message.trim());
      }
      const query = params.toString();
      const endpoint = query
        ? `/api/analytics/confidence-explainability/${userId}?${query}`
        : `/api/analytics/confidence-explainability/${userId}`;

      const response = await fetch(endpoint);
      if (!response.ok) throw new Error('Failed to fetch confidence explainability');
      return response.json();
    },
    enabled: !!userId && userId !== 'anonymous',
    staleTime: 15 * 1000,
    refetchInterval: 15 * 1000,
  });
}
