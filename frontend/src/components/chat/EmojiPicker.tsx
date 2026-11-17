import { Suspense, lazy, useState } from "react";
import { Loader2, Smile } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

/**
 * The full emoji set, WhatsApp style: recently used, every category, skin tones and
 * a search box (focused straight away on computers, so you can just type "laugh").
 *
 * The picker library is only downloaded the first time you open it, and it uses your
 * device's own emoji font, so no emoji images are fetched from anywhere.
 */

const Picker = lazy(async () => {
  const mod = await import("emoji-picker-react");
  const Component = mod.default;
  return {
    default: function ReflectraEmojiPicker({ onPick }: { onPick: (emoji: string) => void }) {
      const finePointer = typeof window !== "undefined" && window.matchMedia?.("(pointer: fine)").matches;
      return (
        <Component
          onEmojiClick={(data) => onPick(data.emoji)}
          theme={mod.Theme.DARK}
          emojiStyle={mod.EmojiStyle.NATIVE}
          suggestedEmojisMode={mod.SuggestionMode.RECENT}
          searchPlaceholder="Search emoji"
          autoFocusSearch={Boolean(finePointer)}
          lazyLoadEmojis
          previewConfig={{ showPreview: false }}
          width="100%"
          height={400}
          className="reflectra-emoji"
        />
      );
    },
  };
});

export function EmojiPicker({
  onPick,
  onClose,
  disabled,
}: {
  onPick: (emoji: string) => void;
  /** Called when the picker closes, so the message box can take focus back. */
  onClose?: () => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) onClose?.();
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          className={cn(
            "rounded-lg p-2 text-muted-foreground transition-colors hover:text-primary",
            open && "text-primary",
            disabled && "cursor-not-allowed opacity-50",
          )}
          title="Emoji"
          aria-label="Add an emoji"
        >
          <Smile className="h-4 w-4" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        side="top"
        align="end"
        sideOffset={12}
        className="w-[min(352px,calc(100vw-2rem))] overflow-hidden border-white/10 bg-popover p-0"
        // The picker focuses its own search box; Radix shouldn't move focus around it.
        onOpenAutoFocus={(event) => event.preventDefault()}
        onCloseAutoFocus={(event) => event.preventDefault()}
      >
        <Suspense
          fallback={
            <div className="grid h-[400px] place-items-center text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
          }
        >
          <Picker onPick={onPick} />
        </Suspense>
      </PopoverContent>
    </Popover>
  );
}
