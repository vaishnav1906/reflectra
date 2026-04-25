import * as React from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";

import { cn } from "@/lib/utils";

const Slider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SliderPrimitive.Root
    ref={ref}
    className={cn(
      "group relative flex w-full touch-none select-none items-center cursor-grab active:cursor-grabbing",
      className
    )}
    {...props}
  >
    <SliderPrimitive.Track className="relative h-[0.625rem] w-full grow overflow-hidden rounded-full border border-white/8 bg-white/7 shadow-inner shadow-black/30">
      <SliderPrimitive.Range className="absolute h-full rounded-full bg-gradient-to-r from-primary/75 via-primary to-accent/70 shadow-[0_0_18px_hsl(var(--primary)/0.35)] transition-all duration-300" />
    </SliderPrimitive.Track>
    <SliderPrimitive.Thumb className="block h-6 w-6 rounded-full border border-white/65 bg-background/95 shadow-[0_10px_28px_rgba(0,0,0,0.35),0_0_0_6px_hsl(var(--primary)/0.14)] transition-all duration-200 hover:scale-110 hover:shadow-[0_12px_34px_rgba(0,0,0,0.42),0_0_0_8px_hsl(var(--primary)/0.18)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/45 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50" />
  </SliderPrimitive.Root>
));
Slider.displayName = SliderPrimitive.Root.displayName;

export { Slider };
