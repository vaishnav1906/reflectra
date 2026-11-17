import { useEffect, useState } from "react";
import { ChatMessage, type ChatMessageProps } from "@/components/chat/ChatMessage";
import { TypingIndicator } from "@/components/chat/TypingIndicator";
import { prefersReducedMotion } from "@/lib/motion";

/**
 * A message that types itself in, as if Reflectra were writing it right now: used for
 * the opener you land on from a notification. A short pause, then about 45 characters
 * a second (faster for long ones, so it never takes more than ~3 seconds).
 */
export function TypedInMessage(props: ChatMessageProps & { onDone?: () => void }) {
  const { content, onDone, ...rest } = props;
  const instant = prefersReducedMotion();
  const [count, setCount] = useState(instant ? content.length : -1); // -1: still "thinking"

  useEffect(() => {
    if (instant) {
      onDone?.();
      return;
    }
    let frame = 0;
    const pause = window.setTimeout(() => {
      const start = performance.now();
      const perMs = Math.max(0.045, content.length / 3000);
      const step = (now: number) => {
        const next = Math.min(content.length, Math.round((now - start) * perMs));
        setCount(next);
        if (next < content.length) frame = requestAnimationFrame(step);
        else onDone?.();
      };
      frame = requestAnimationFrame(step);
    }, 800);
    return () => {
      window.clearTimeout(pause);
      cancelAnimationFrame(frame);
    };
  }, [content]); // eslint-disable-line react-hooks/exhaustive-deps

  if (count < 0) return <TypingIndicator />;
  return <ChatMessage {...rest} content={content.slice(0, count)} streaming={count < content.length} noFade />;
}
