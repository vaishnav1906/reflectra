import { Zap, Heart, Sparkles, Skull, Flame, Sun, Target } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export type MirrorStyle = "dominant" | "calm" | "challenger" | "chaotic" | "dark_wit" | "optimist";

interface ActiveMirrorIndicatorProps {
  activeStyle: MirrorStyle;
  detectedEmotion?: string;
  className?: string;
}

const STYLE_CONFIG: Record<MirrorStyle, { name: string; icon: typeof Zap; color: string }> = {
  dominant: { name: "Dominant", icon: Zap, color: "text-amber-500" },
  calm: { name: "Calm Anchor", icon: Heart, color: "text-blue-500" },
  challenger: { name: "Challenger", icon: Flame, color: "text-red-500" },
  chaotic: { name: "Chaotic Energy", icon: Sparkles, color: "text-purple-500" },
  dark_wit: { name: "Dark Wit", icon: Skull, color: "text-slate-500" },
  optimist: { name: "Uplifted Optimist", icon: Sun, color: "text-yellow-500" },
};

const EMOTION_DISPLAY: Record<string, string> = {
  insecure: "Uncertain",
  stressed: "Stressed",
  angry: "Frustrated",
  playful: "Playful",
  sarcastic: "Sarcastic",
  happy: "Happy",
  neutral: "Neutral",
};

export function ActiveMirrorIndicator({ activeStyle, detectedEmotion, className }: ActiveMirrorIndicatorProps) {
  const config = STYLE_CONFIG[activeStyle] || STYLE_CONFIG.dominant;
  const Icon = config.icon;
  const emotionText = detectedEmotion ? EMOTION_DISPLAY[detectedEmotion] || detectedEmotion : null;

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={cn(
              "flex items-center gap-2 px-3 py-1.5 rounded-lg border bg-card/50",
              "transition-all duration-300",
              className
            )}
          >
            <Target className="w-3 h-3 text-muted-foreground animate-pulse" />
            <Icon className={cn("w-3.5 h-3.5", config.color)} />
            <span className="text-xs font-medium text-foreground">
              {config.name}
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-xs">
          <div className="space-y-1">
            <p className="text-xs font-medium">Active Archetype: {config.name}</p>
            {emotionText && (
              <p className="text-xs text-muted-foreground">
                Detected emotional tone: {emotionText}
              </p>
            )}
            <p className="text-xs text-muted-foreground/80 mt-2">
              Auto-adapting based on your emotional state
            </p>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
