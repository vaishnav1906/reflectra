import { useState, useEffect } from "react";
import { Clock, BookOpen, AlertCircle, Info, Loader2, Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const API_BASE = "/api";

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
  const [initialData, setInitialData] = useState<TimetableData | null>(null);
  const [data, setData] = useState<TimetableData>({
    classesPerDay: 3,
    avgDuration: 4,
    hasUpcomingDeadlines: false,
    isExamPeriod: false,
  });
  const [workloadLevel, setWorkloadLevel] = useState("low");

  const [isModified, setIsModified] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);

  // Fetch initial state
  useEffect(() => {
    const fetchContext = async () => {
      try {
        const userId = localStorage.getItem("user_id");
        if (!userId) return;

        const res = await fetch(`${API_BASE}/schedule-context/${userId}`);
        if (res.ok) {
          const json = await res.json();
          const loadedData = {
            classesPerDay: json.schedule_context.classes_per_day,
            avgDuration: json.schedule_context.study_hours,
            hasUpcomingDeadlines: json.schedule_context.has_deadlines,
            isExamPeriod: json.schedule_context.is_exam_period,
          };
          setData(loadedData);
          setInitialData(loadedData);
          setWorkloadLevel(json.derived_context.workload_level);
        }
      } catch (err) {
        console.error("Failed to fetch schedule context", err);
      } finally {
        setIsFetching(false);
      }
    };
    fetchContext();
  }, []);

  const updateData = (updates: Partial<TimetableData>) => {
    const newData = { ...data, ...updates };
    setData(newData);
    setIsModified(true);
    
    // Optimistic workload calculation
    const wl = newData.classesPerDay > 4 || newData.isExamPeriod ? "high" : newData.classesPerDay > 2 ? "moderate" : "low";
    setWorkloadLevel(wl);
  };

  const handleSave = async () => {
    setIsLoading(true);
    try {
      const userId = localStorage.getItem("user_id");
      if (!userId) return;

      const res = await fetch(`${API_BASE}/schedule-context/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          classes_per_day: data.classesPerDay,
          study_hours: data.avgDuration,
          has_deadlines: data.hasUpcomingDeadlines,
          is_exam_period: data.isExamPeriod,
        }),
      });

      if (res.ok) {
        const json = await res.json();
        setInitialData(data);
        setIsModified(false);
        setWorkloadLevel(json.derived_context.workload_level);
        onUpdate?.(data);
      }
      
      // UX Smoothness minimum delay
      await new Promise(r => setTimeout(r, 1000));
      
    } catch (error) {
      console.error("Failed to update context", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    if (initialData) {
      setData(initialData);
      const wl = initialData.classesPerDay > 4 || initialData.isExamPeriod ? "high" : initialData.classesPerDay > 2 ? "moderate" : "low";
      setWorkloadLevel(wl);
    }
    setIsModified(false);
  };

  if (isFetching) {
    return (
      <div className="bg-card border border-border rounded-xl p-6 flex flex-col items-center justify-center space-y-3 min-h-[300px]">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span className="text-sm text-muted-foreground">Loading context profile...</span>
      </div>
    );
  }

  return (
    <div className={cn(
      "bg-card border border-border rounded-xl p-6 relative transition-all duration-300",
      isLoading && "opacity-80 pointer-events-none"
    )}>
      {isLoading && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-background/60 rounded-xl backdrop-blur-[2px]">
          <Loader2 className="w-8 h-8 animate-spin text-primary mb-2" />
          <p className="text-sm font-medium text-foreground">Extracting Context Profile...</p>
        </div>
      )}

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
                  Used by the AI to naturally adapt to your stress levels and workload.
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        
        <span className={cn(
          "text-xs px-2 py-1 rounded-full capitalize",
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

      {/* Action Buttons */}
      {isModified && (
        <div className="mt-8 flex items-center justify-end gap-3 pt-4 border-t border-border">
          <button 
            onClick={handleCancel}
            className="text-sm flex items-center gap-1.5 px-3 py-1.5 text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded-md transition-colors"
          >
            <X className="w-4 h-4" /> Cancel
          </button>
          <button 
            onClick={handleSave}
            className="text-sm flex items-center gap-1.5 px-4 py-1.5 bg-primary text-primary-foreground hover:bg-primary/90 rounded-md transition-colors font-medium shadow-sm"
          >
            <Check className="w-4 h-4" /> Save Context
          </button>
        </div>
      )}

      {/* Pattern insight */}
      {!isModified && (data.hasUpcomingDeadlines || data.isExamPeriod) && (
        <div className="mt-6 pt-4 border-t border-border">
          <p className="text-xs text-muted-foreground/70 italic">
            {data.isExamPeriod
              ? "AI context adjusted for exam stress level. Focusing on shorter, actionable outputs."
              : "AI context applied for high-deadline urgency. Priority tracking active."}
          </p>
        </div>
      )}
    </div>
  );
}
