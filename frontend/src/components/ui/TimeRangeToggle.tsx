import React from "react";
import { cn } from "@/lib/utils";

interface TimeRangeToggleProps {
  value: '1d' | '2d' | '3d' | '7d' | '30d' | '90d';
  onChange: (value: '1d' | '2d' | '3d' | '7d' | '30d' | '90d') => void;
  className?: string;
}

export function TimeRangeToggle({ value, onChange, className }: TimeRangeToggleProps) {
  const options = [
    { label: "1D", value: "1d" },
    { label: "2D", value: "2d" },
    { label: "3D", value: "3d" },
    { label: "7D", value: "7d" },
    { label: "30D", value: "30d" },
    { label: "90D", value: "90d" },
  ] as const;

  return (
    <div className={cn("flex bg-muted rounded-lg p-1 border border-border", className)}>
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={cn(
            "px-4 py-1.5 text-sm font-medium rounded-md transition-colors",
            value === opt.value
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
