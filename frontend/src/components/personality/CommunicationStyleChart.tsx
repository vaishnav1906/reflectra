import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar } from "recharts";

const data = [
  { trait: "Directness", value: 75 },
  { trait: "Warmth", value: 85 },
  { trait: "Detail", value: 60 },
  { trait: "Openness", value: 90 },
  { trait: "Formality", value: 40 },
  { trait: "Pace", value: 65 },
];

export function CommunicationStyleChart() {
  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <h3 className="font-semibold text-foreground mb-2">Communication Style</h3>
      <p className="text-sm text-muted-foreground mb-6">
        How you naturally express yourself in conversations
      </p>

      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} margin={{ top: 20, right: 30, bottom: 20, left: 30 }}>
            <PolarGrid stroke="hsl(var(--border))" />
            <PolarAngleAxis
              dataKey="trait"
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
            />
            <Radar
              name="Style"
              dataKey="value"
              stroke="hsl(var(--primary))"
              fill="hsl(var(--primary))"
              fillOpacity={0.2}
              strokeWidth={2}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3">
        {data.slice(0, 3).map((item) => (
          <div key={item.trait} className="text-center p-3 bg-muted/30 rounded-lg">
            <p className="text-lg font-semibold text-foreground">{item.value}%</p>
            <p className="text-xs text-muted-foreground">{item.trait}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
