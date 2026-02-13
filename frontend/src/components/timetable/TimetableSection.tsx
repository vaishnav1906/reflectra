import { useState } from "react";
import { Clock, BookOpen, AlertCircle, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface TimetableData {
  classesPerDay: number;
  avgDuration: number; // in hours
  hasUpcomingDeadlines: boolean;
  isExamPeriod: boolean;
}

interface TimetableSectionProps {
  onUpdate?: (data: TimetableData) => void;
}

export function TimetableSection({ onUpdate }: TimetableSectionProps) {
  const [data, setData] = useState<TimetableData>({
    classesPerDay: 3,
    avgDuration: 4,
    hasUpcomingDeadlines: false,
    isExamPeriod: false,
  });

  const updateData = (updates: Partial<TimetableData>) => {
    const newData = { ...data, ...updates };
    setData(newData);
    onUpdate?.(newData);
  };

  const workloadLevel = data.classesPerDay > 4 || data.isExamPeriod ? "high" : data.classesPerDay > 2 ? "moderate" : "light";

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-primary" />
          <h3 className="font-medium text-foreground">Schedule Context</h3>
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button className="p-0.5 rounded hover:bg-muted/50 transition-colors">
                  <Info className="w-3.5 h-3.5 text-muted-foreground" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-xs bg-card border border-border">
                <p className="text-xs text-muted-foreground">
                  Used only to understand workload patterns. No calendar syncing or notifications.
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        
        <span className={cn(
          "text-xs px-2 py-1 rounded-full",
          workloadLevel === "high" ? "bg-accent/10 text-accent" :
          workloadLevel === "moderate" ? "bg-primary/10 text-primary" :
          "bg-muted text-muted-foreground"
        )}>
          {workloadLevel} workload
        </span>
      </div>

      <div className="space-y-6">
        {/* Classes per day */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm text-foreground">Classes per day</span>
            </div>
            <span className="text-sm font-medium text-primary">{data.classesPerDay}</span>
          </div>
          <Slider
            value={[data.classesPerDay]}
            onValueChange={([value]) => updateData({ classesPerDay: value })}
            min={0}
            max={8}
            step={1}
            className="w-full"
          />
          <div className="flex justify-between mt-1 text-xs text-muted-foreground">
            <span>None</span>
            <span>Full day</span>
          </div>
        </div>

        {/* Duration */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm text-foreground">Avg. daily study hours</span>
            </div>
            <span className="text-sm font-medium text-primary">{data.avgDuration}h</span>
          </div>
          <Slider
            value={[data.avgDuration]}
            onValueChange={([value]) => updateData({ avgDuration: value })}
            min={0}
            max={12}
            step={1}
            className="w-full"
          />
        </div>

        {/* Deadline period */}
        <div className="flex items-center justify-between pt-4 border-t border-border">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-muted-foreground" />
            <div>
              <p className="text-sm text-foreground">Upcoming deadlines</p>
              <p className="text-xs text-muted-foreground">Projects or assignments due soon</p>
            </div>
          </div>
          <Switch
            checked={data.hasUpcomingDeadlines}
            onCheckedChange={(checked) => updateData({ hasUpcomingDeadlines: checked })}
          />
        </div>

        {/* Exam period */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-muted-foreground" />
            <div>
              <p className="text-sm text-foreground">Exam period</p>
              <p className="text-xs text-muted-foreground">Currently in or preparing for exams</p>
            </div>
          </div>
          <Switch
            checked={data.isExamPeriod}
            onCheckedChange={(checked) => updateData({ isExamPeriod: checked })}
          />
        </div>
      </div>

      {/* Pattern insight */}
      {(data.hasUpcomingDeadlines || data.isExamPeriod) && (
        <div className="mt-6 pt-4 border-t border-border">
          <p className="text-xs text-muted-foreground/70 italic">
            {data.isExamPeriod
              ? "Hesitation patterns tend to increase during exam periods."
              : "Your reflections may be shorter during high-deadline periods."}
          </p>
        </div>
      )}
    </div>
  );
}
