import { Zap, Heart, Sparkles, Skull, Flame, Sun, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

export type MirrorStyle = "badass" | "calm" | "chaotic" | "dark_humor" | "aggressive" | "happy";

interface MirrorStyleSelectorProps {
  selectedStyle: MirrorStyle;
  onStyleChange: (style: MirrorStyle) => void;
  disabled?: boolean;
}

const MIRROR_STYLES = [
  {
    id: "badass" as MirrorStyle,
    name: "Badass",
    icon: Zap,
    color: "text-amber-500",
    description: "Confident, direct, and calmly assertive. Reframes doubt into power.",
  },
  {
    id: "calm" as MirrorStyle,
    name: "Calm",
    icon: Heart,
    color: "text-blue-500",
    description: "Grounded, stable, and emotionally regulated. De-escalates stress.",
  },
  {
    id: "chaotic" as MirrorStyle,
    name: "Chaotic",
    icon: Sparkles,
    color: "text-purple-500",
    description: "High energy and unpredictable. Amplifies excitement with controlled spontaneity.",
  },
  {
    id: "dark_humor" as MirrorStyle,
    name: "Dark Humor",
    icon: Skull,
    color: "text-slate-500",
    description: "Sarcastic wit and sharp observations. Uses humor to expose truth.",
  },
  {
    id: "aggressive" as MirrorStyle,
    name: "Aggressive",
    icon: Flame,
    color: "text-red-500",
    description: "Intense and blunt. Calls out excuses and pushes accountability.",
  },
  {
    id: "happy" as MirrorStyle,
    name: "Happy",
    icon: Sun,
    color: "text-yellow-500",
    description: "Optimistic and encouraging. Highlights wins and reinforces confidence.",
  },
];

export function MirrorStyleSelector({ selectedStyle, onStyleChange, disabled }: MirrorStyleSelectorProps) {
  const selected = MIRROR_STYLES.find(s => s.id === selectedStyle) || MIRROR_STYLES[0];
  const SelectedIcon = selected.icon;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          disabled={disabled}
          className="gap-2 min-w-[140px]"
        >
          <SelectedIcon className={cn("w-4 h-4", selected.color)} />
          <span>{selected.name}</span>
          <ChevronDown className="w-3 h-3 ml-auto opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[280px]">
        <DropdownMenuLabel className="text-xs text-muted-foreground">
          Mirror Style
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {MIRROR_STYLES.map((style) => {
          const Icon = style.icon;
          const isSelected = selectedStyle === style.id;
          
          return (
            <DropdownMenuItem
              key={style.id}
              onClick={() => onStyleChange(style.id)}
              className={cn(
                "flex flex-col items-start gap-1 p-3 cursor-pointer",
                isSelected && "bg-accent"
              )}
            >
              <div className="flex items-center gap-2 w-full">
                <Icon className={cn("w-4 h-4", style.color)} />
                <span className="font-medium">{style.name}</span>
                {isSelected && (
                  <div className="ml-auto w-2 h-2 rounded-full bg-primary" />
                )}
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {style.description}
              </p>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

