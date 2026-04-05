import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface RingProps {
  progress: number; // 0 to 100+
  size: number;
  strokeWidth: number;
  color: string;
  label: string;
}

const Ring: React.FC<RingProps> = ({ progress, size, strokeWidth, color, label }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  // Cap visual progress at 100 for one full rotation, or let it wrap around
  const displayProgress = progress > 100 ? 100 : progress; 
  const strokeDashoffset = circumference - (displayProgress / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div style={{ width: size, height: size }} className="relative flex items-center justify-center">
        <svg width={size} height={size} className="transform -rotate-90 origin-center absolute inset-0">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="currentColor"
            strokeWidth={strokeWidth}
            fill="transparent"
            className="text-muted/20"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={color}
            strokeWidth={strokeWidth}
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-1000 ease-out drop-shadow-[0_0_6px_rgba(255,255,255,0.2)]"
            style={{
              filter: `drop-shadow(0 0 6px ${color}80)`
            }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-bold">{Math.round(progress)}%</span>
        </div>
      </div>
      <span className="text-xs text-muted-foreground font-medium text-center">{label}</span>
    </div>
  );
};

export const ActivityRings = ({ metrics, view }: { metrics: any[], view: string }) => {
  // Compute aggregated scores against arbitrary goals for presentation
  const count = metrics.reduce((acc, m) => acc + m.message_count, 0);
  const totalTokens = metrics.reduce((acc, m) => acc + m.total_tokens, 0);
  
  // Baselines depend on the view (daily vs weekly vs monthly goals)
  const multiplier = view === 'day' ? 1 : view === 'week' ? 7 : 30;
  
  const engagementGoal = 20 * multiplier; 
  const verbosityGoal = 500 * multiplier;
  
  // Averages for intensity & reflection
  const validIntensity = metrics.filter(m => m.emotional_intensity !== null);
  const avgIntensity = validIntensity.length ? validIntensity.reduce((sum, m) => sum + m.emotional_intensity, 0) / validIntensity.length : 0.5;

  const validReflection = metrics.filter(m => m.reflection_depth !== null);
  const avgReflection = validReflection.length ? validReflection.reduce((sum, m) => sum + m.reflection_depth, 0) / validReflection.length : 0.5;


  const engagementPct = (count / engagementGoal) * 100;
  const depthPct = avgReflection * 100;
  const emotionPct = avgIntensity * 100;

  return (
    <Card className="col-span-full xl:col-span-3">
      <CardHeader>
        <CardTitle>Activity</CardTitle>
        <CardDescription>Your behavioral rings for this period</CardDescription>
      </CardHeader>
      <CardContent className="flex justify-around items-center py-4">
         <Ring progress={engagementPct} size={110} strokeWidth={12} color="#ec4899" label="Engagement" />
         <Ring progress={depthPct} size={110} strokeWidth={12} color="#3b82f6" label="Reflection" />
         <Ring progress={emotionPct} size={110} strokeWidth={12} color="#f59e0b" label="Emotion" />
      </CardContent>
    </Card>
  );
};