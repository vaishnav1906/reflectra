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
  view: 'day' | 'week' | 'month';
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

export function useBehavioralMetrics(userId: string, view: 'day' | 'week' | 'month') {
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
