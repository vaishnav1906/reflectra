import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { TrendingUp, Calendar } from "lucide-react";
import { cn } from "@/lib/utils";

interface TraitDataPoint {
  date: string;
  value: number;
}

interface TraitEvolution {
  name: string;
  color: string;
  data: TraitDataPoint[];
  trend: "increasing" | "decreasing" | "stable";
  changePercent: number;
}

const traitEvolutions: TraitEvolution[] = [
  {
    name: "Analytical Processing",
    color: "hsl(var(--trait-analytical))",
    data: [
      { date: "Oct", value: 72 },
      { date: "Nov", value: 74 },
      { date: "Dec", value: 76 },
      { date: "Jan", value: 78 },
    ],
    trend: "increasing",
    changePercent: 8.3,
  },
  {
    name: "Affective Depth",
    color: "hsl(var(--trait-empathetic))",
    data: [
      { date: "Oct", value: 80 },
      { date: "Nov", value: 82 },
      { date: "Dec", value: 84 },
      { date: "Jan", value: 85 },
    ],
    trend: "increasing",
    changePercent: 6.2,
  },
  {
    name: "Introspective Orientation",
    color: "hsl(var(--trait-introspective))",
    data: [
      { date: "Oct", value: 85 },
      { date: "Nov", value: 88 },
      { date: "Dec", value: 90 },
      { date: "Jan", value: 91 },
    ],
    trend: "increasing",
    changePercent: 7.0,
  },
  {
    name: "Behavioral Consistency",
    color: "hsl(var(--trait-consistent))",
    data: [
      { date: "Oct", value: 70 },
      { date: "Nov", value: 69 },
      { date: "Dec", value: 68 },
      { date: "Jan", value: 68 },
    ],
    trend: "stable",
    changePercent: -2.8,
  },
];

export function PersonalityEvolution() {
  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-primary" />
          <h3 className="font-semibold text-foreground">Personality Evolution</h3>
          <InfoTooltip 
            content="Longitudinal trait trajectories showing how personality dimensions evolve over time through continued interaction" 
          />
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted border border-border">
          <Calendar className="w-3 h-3 text-muted-foreground" />
          <span className="text-xs text-muted-foreground">90-day window</span>
        </div>
      </div>

      {/* Combined Chart */}
      <div className="h-64 mb-6">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis 
              dataKey="date" 
              stroke="hsl(var(--muted-foreground))" 
              fontSize={12}
              allowDuplicatedCategory={false}
            />
            <YAxis 
              domain={[50, 100]} 
              stroke="hsl(var(--muted-foreground))" 
              fontSize={12}
            />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: "hsl(var(--card))", 
                border: "1px solid hsl(var(--border))", 
                borderRadius: "8px" 
              }} 
            />
            {traitEvolutions.map((trait) => (
              <Line
                key={trait.name}
                data={trait.data}
                type="monotone"
                dataKey="value"
                name={trait.name}
                stroke={trait.color}
                strokeWidth={2}
                dot={{ r: 3, fill: trait.color }}
                activeDot={{ r: 5 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Trait Legend with Trends */}
      <div className="grid grid-cols-2 gap-3">
        {traitEvolutions.map((trait) => (
          <div 
            key={trait.name}
            className="flex items-center justify-between p-3 bg-muted/30 rounded-lg border border-border/50"
          >
            <div className="flex items-center gap-2">
              <div 
                className="w-3 h-3 rounded-full" 
                style={{ backgroundColor: trait.color }}
              />
              <span className="text-xs text-foreground">{trait.name}</span>
            </div>
            <div className={cn(
              "text-xs font-medium",
              trait.trend === "increasing" ? "text-green-500" : 
              trait.trend === "decreasing" ? "text-red-400" : "text-muted-foreground"
            )}>
              {trait.changePercent > 0 ? "+" : ""}{trait.changePercent}%
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-border">
        <p className="text-xs text-muted-foreground/60 text-center">
          Trait values are normalized scores (0-100) computed from behavioral feature aggregation
        </p>
      </div>
    </div>
  );
}
