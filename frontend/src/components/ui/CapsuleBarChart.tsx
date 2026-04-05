import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { cn } from "@/lib/utils";

interface CapsuleBarChartProps {
  data: any[];
  dataKey: string;
  xAxisKey?: string;
  color?: string;
  height?: number;
  className?: string;
}

export function CapsuleBarChart({
  data,
  dataKey,
  xAxisKey = "name",
  color = "#00F0FF",
  height = 300,
  className,
}: CapsuleBarChartProps) {
  return (
    <div className={cn("w-full", className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 20, right: 0, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.1)" />
          <XAxis 
            dataKey={xAxisKey} 
            axisLine={false} 
            tickLine={false} 
            tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 12, fontWeight: "bold" }} 
            dy={10} 
          />
          <YAxis 
            axisLine={false} 
            tickLine={false} 
            tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 12, fontWeight: "bold" }} 
            dx={-10}
          />
          <Tooltip 
            cursor={{ fill: "rgba(255,255,255,0.05)" }}
            contentStyle={{ backgroundColor: "#18181b", border: "1px solid #27272a", borderRadius: "12px", color: "#fff", fontWeight: "bold" }}
            itemStyle={{ color: color }}
          />
          <Bar 
            dataKey={dataKey} 
            fill={color} 
            radius={[10, 10, 0, 0]} // Capsule top, flat bottom (or adjust to [10,10,10,10] if needed)
            barSize={32}
            style={{ filter: `drop-shadow(0 0 8px ${color}66)` }}
            animationDuration={1500}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
