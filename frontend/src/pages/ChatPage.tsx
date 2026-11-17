import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { TypingIndicator } from "@/components/chat/TypingIndicator";
import { ModeToggle } from "@/components/chat/ModeToggle";
import { ActiveMirrorIndicator, MirrorStyle } from "@/components/chat/ActiveMirrorIndicator";
import { ConversationHistoryModal } from "@/components/chat/ConversationHistoryModal";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { MessageSquare, EyeOff } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { useChatContext, isInteractionMode, type InteractionMode, type Message } from "@/contexts/ChatContext";
import { triggerConversationRefresh } from "@/utils/conversationRefresh";

import { apiFetch } from "@/lib/api";
import { ChatError, sendChat } from "@/lib/chatStream";
import { useTypewriter } from "@/hooks/useTypewriter";
import { useAuth } from "@/contexts/AuthContext";
import { MirrorMark } from "@/components/MirrorMark";
import { TypedInMessage } from "@/components/chat/TypedInMessage";
const API_BASE = "/api";
// Prefix for the "AI is rate-limited, try again" notice (excluded from conversation context).
const BUSY_PREFIX = "⏳";

export function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [isTyping, setIsTyping] = useState(false);
  // The reply as it is being written (null while waiting for the first words).
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const streamingTextRef = useRef<string | null>(null);
  streamingTextRef.current = streamingText;
  // The reply that was already on screen while streaming: it shouldn't animate in again.
  const [streamedId, setStreamedId] = useState<string | null>(null);
  // What is on screen of the streaming reply: revealed smoothly, not in network-sized chunks.
  const { shown: typedText, shownRef: typedRef } = useTypewriter(streamingText);
  const [assistantTaskType, setAssistantTaskType] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<"checking" | "connected" | "disconnected">("checking");
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [incognitoFeedback, setIncognitoFeedback] = useState<"enabled" | "disabled" | null>(null);
  // Switching mode flips the mirror over (only after a switch, not on arrival).
  const [modeFlips, setModeFlips] = useState(0);
  // The opener you came for from a notification types itself in.
  const [typeInId, setTypeInId] = useState<string | null>(null);
  
  // Get chat state from context (persists across navigation)
  const {
    activeConversationId,
    setActiveConversationId,
    adoptNewConversation,
    loadingMessages,
    messages,
    setMessages,
    mode,
    conversationTitle,
    setConversationTitle,
    activeMirrorStyle,
    setActiveMirrorStyle,
    detectedEmotion,
    setDetectedEmotion,
    isIncognito,
    incognitoSessionId,
    setIncognitoMode,
    startNewConversation,
  } = useChatContext();

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const userId = localStorage.getItem("user_id") || "";
  const { user } = useAuth();
  const firstName = (user?.display_name || "").trim().split(/\s+/)[0] || "";
  const greetingName = firstName ? firstName.charAt(0).toUpperCase() + firstName.slice(1) : "";

  const modeDescriptions: Record<InteractionMode, string> = {
    reflection: "Reflection · a friend who notices",
    mirror: "Mirror · you, talking back",
  };

  const emptyStateDescriptions: Record<InteractionMode, string> = {
    reflection: "Say whatever's on your mind. Reflectra listens, and tells you what it notices.",
    mirror: "Talk to yourself, out loud. Or ask it to draft something the way you'd write it.",
  };

  const formatTaskType = (taskType: string) =>
    taskType
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");

  // Ensure mode is in URL
  useEffect(() => {
    const urlMode = searchParams.get("mode");
    if (!isInteractionMode(urlMode)) {
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set("mode", "reflection");
      setSearchParams(nextParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  // Check backend connection
  useEffect(() => {
    const checkBackend = async () => {
      try {
        const res = await apiFetch(`${API_BASE}/health`);
        setBackendStatus(res.ok ? "connected" : "disconnected");
      } catch {
        setBackendStatus("disconnected");
      }
    };
    checkBackend();
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleModeChange = (newMode: InteractionMode) => {
    if (newMode === mode) return;
    
    console.log(`🔄 Mode change: ${mode} → ${newMode}`);
    
    // Start new conversation when switching modes
    setModeFlips((n) => n + 1);
    startNewConversation();
    setAssistantTaskType(null);
    setSearchParams({ mode: newMode });
  };

  // Arrived from a notification: once its conversation has loaded, Reflectra's opener types itself in.
  useEffect(() => {
    if (searchParams.get("from") !== "nudge" || loadingMessages || messages.length === 0) return;
    if (messages.length === 1 && messages[0].role === "assistant") setTypeInId(messages[0].id);
    const next = new URLSearchParams(searchParams);
    next.delete("from");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams, loadingMessages, messages]);

  const handleIncognitoChange = (enabled: boolean) => {
    setIncognitoFeedback(enabled ? "enabled" : "disabled");
    setIncognitoMode(enabled);
  };

  useEffect(() => {
    if (!incognitoFeedback) return;

    const timeout = window.setTimeout(() => {
      setIncognitoFeedback(null);
    }, 900);

    return () => window.clearTimeout(timeout);
  }, [incognitoFeedback]);

  const handleSend = async (content: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsTyping(true);

    try {
      const data = await sendChat(
        {
          user_id: userId,
          conversation_id: activeConversationId,
          message: content,
          mode,
          is_incognito: isIncognito,
          incognito_session_id: incognitoSessionId,
          // e.g. "Sunday 1:57 AM": lets replies feel aware of the moment.
          client_local_time: new Date().toLocaleString([], {
            weekday: "long",
            hour: "numeric",
            minute: "2-digit",
          }),
          // Incognito chats are not stored server-side, so send recent context.
          history: isIncognito
            ? messages
                .filter((m) => !m.content.startsWith("⚠️ Error") && !m.content.startsWith(BUSY_PREFIX))
                .slice(-16)
                .map((m) => ({ role: m.role, content: m.content }))
            : undefined,
          // So "tomorrow" in "i'll do it tomorrow" means the user's tomorrow.
          tz_offset_minutes: -new Date().getTimezoneOffset(),
        },
        {
          // The reply appears while it is being written...
          onPartial: (text) => setStreamingText(text),
          // ...and if that draft is thrown away for a better one, back to "typing".
          onReset: () => setStreamingText(null),
        },
      );

      // Update mirror style if in mirror mode
      if (data.active_mirror_style) setActiveMirrorStyle(data.active_mirror_style);
      if (data.detected_emotion) setDetectedEmotion(data.detected_emotion);
      if (mode === "mirror") {
        setAssistantTaskType(
          typeof data.assistant_task_type === "string" ? data.assistant_task_type : null
        );
      }

      // Update conversation ID for new conversations
      if (!isIncognito && !activeConversationId && data.conversation_id) {
        adoptNewConversation(data.conversation_id);
        setConversationTitle(data.title);
        setSearchParams({ 
          conversation_id: data.conversation_id,
          mode 
        });
        
        // Trigger refresh for any subscribers (like the conversation history modal)
        console.log("✅ New conversation created, triggering refresh");
        triggerConversationRefresh();
      } else if (isIncognito && data.conversation_id) {
        setConversationTitle(data.title || "Incognito Session");
      } else if (activeConversationId && isInteractionMode(data.mode) && data.mode !== mode) {
        // Opened from a link that didn't know this conversation's mode: follow the server.
        setSearchParams({ conversation_id: activeConversationId, mode: data.mode }, { replace: true });
      }

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        serverId: typeof data.message_id === "string" ? data.message_id : undefined,
        peopleUsed: Array.isArray(data.people_used) ? data.people_used : [],
        remembered: Array.isArray(data.remembered) ? data.remembered : [],
        feedback: null,
        role: "assistant",
        content: data.reply,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };

      if (streamingTextRef.current) {
        // Let the on-screen typing finish the final text before it settles into a message.
        setStreamingText(data.reply);
        const until = Date.now() + 2500;
        while (typedRef.current !== data.reply && Date.now() < until) {
          await new Promise((resolve) => setTimeout(resolve, 40));
        }
        setStreamedId(aiMessage.id);
      }
      setMessages((prev) => [...prev, aiMessage]);
    } catch (err) {
      if (err instanceof ChatError && err.status === 429) {
        // The AI is briefly rate-limited. Nothing was saved, so the user can resend.
        setMessages((prev) => [
          ...prev,
          {
            id: (Date.now() + 1).toString(),
            role: "assistant",
            content: `${BUSY_PREFIX} ${err.message || "Reflectra is catching its breath. Give it a few seconds and send that again."}`,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          },
        ]);
        return;
      }
      console.error("❌ Chat error:", err);
      const errorMessage = err instanceof Error ? err.message : "Unknown error occurred";

      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: `⚠️ Error: ${errorMessage}`,
          timestamp: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        },
      ]);
    } finally {
      setStreamingText(null);
      setIsTyping(false);
    }
  };

  const handleSelectConversation = (convId: string) => {
    setActiveConversationId(convId);
    setAssistantTaskType(null);
    setSearchParams({ conversation_id: convId, mode });
  };

  const handleNewChat = () => {
    startNewConversation();
    setAssistantTaskType(null);
  };

  if (!userId || userId === "anonymous") {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <h2 className="text-2xl font-semibold">Login Required</h2>
          <p className="text-muted-foreground">
            Please log in to access the chat feature.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex">
      <div className="flex-1 flex flex-col">
        <header className="chat-header px-6 py-4 md:px-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <h1 className="chat-title truncate">
                {conversationTitle || (isIncognito ? "Incognito session" : "New conversation")}
              </h1>
              <p className="eyebrow mt-1 !text-[0.62rem]">
                {modeDescriptions[mode]}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <ModeToggle mode={mode} onModeChange={handleModeChange} />

              <label className="flex cursor-pointer items-center gap-2.5 rounded-full border border-white/10 bg-white/[0.03] py-1.5 pl-3.5 pr-2">
                <EyeOff className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-xs font-medium text-foreground/85">Incognito</span>
                <Switch checked={isIncognito} onCheckedChange={handleIncognitoChange} aria-label="Incognito mode" />
              </label>
              
              {mode === "mirror" && activeMirrorStyle && (
                <ActiveMirrorIndicator
                  activeStyle={activeMirrorStyle as MirrorStyle}
                  detectedEmotion={detectedEmotion || undefined}
                />
              )}

              {mode === "mirror" && assistantTaskType && assistantTaskType !== "generic" && (
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent/10 border border-accent/20">
                  <span className="text-xs text-accent font-medium">
                    Task: {formatTaskType(assistantTaskType)}
                  </span>
                </div>
              )}
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowHistoryModal(true)}
                className="gap-2 rounded-full border-white/10 bg-white/[0.03] hover:bg-white/[0.07]"
              >
                <MessageSquare className="w-3.5 h-3.5" />
                History
              </Button>
              
              {backendStatus === "connected" && (
                <div className="flex items-center gap-1.5" title="Connected">
                  <div className="h-1.5 w-1.5 rounded-full bg-emerald-400 pulse-indicator"></div>
                  <span className="sr-only">Connected</span>
                </div>
              )}
            </div>
          </div>
        </header>

        {incognitoFeedback && (
          <div className="mx-8 mt-3">
            <div
              className={cn(
                "inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-medium shadow-lg",
                "animate-in fade-in slide-in-from-top-2 zoom-in-95 duration-300",
                incognitoFeedback === "enabled"
                  ? "border-primary/30 bg-primary/15 text-primary"
                  : "border-border bg-muted/80 text-muted-foreground"
              )}
            >
              <EyeOff className="h-3.5 w-3.5" />
              {incognitoFeedback === "enabled" ? "Incognito enabled" : "Incognito disabled"}
            </div>
          </div>
        )}

        {isIncognito && (
          <div className="mx-6 mt-3 flex items-center gap-2.5 rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-xs text-muted-foreground md:mx-8 md:w-fit">
            <EyeOff className="h-3.5 w-3.5 shrink-0 text-primary" />
            <span>
              <span className="font-medium text-foreground">Incognito is on.</span> Nothing here is saved or used to learn about you.
            </span>
          </div>
        )}

        <ScrollArea className="flex-1 px-4 py-6 md:px-8">
          <div className="max-w-3xl mx-auto space-y-6">
            {loadingMessages && (
              <div className="sticky top-0 z-10 flex justify-center py-2">
                <div className="rounded-full border border-border bg-background/95 px-3 py-1 text-xs text-muted-foreground shadow-sm backdrop-blur">
                  Loading messages...
                </div>
              </div>
            )}

            {messages.length === 0 && !isTyping && !loadingMessages && (
              <div
                key={`${mode}-${modeFlips}`}
                className={cn("chat-empty flex flex-col items-center px-4 pt-[12vh] text-center", modeFlips > 0 && "mode-flip")}
              >
                <span className="mode-flip-mark">
                  <MirrorMark className="h-20 w-20" breathing />
                </span>
                {activeConversationId ? (
                  <>
                    <h2 className="mt-8 font-display text-4xl">Nothing here yet.</h2>
                    <p className="mt-3 text-muted-foreground">This conversation has no messages.</p>
                  </>
                ) : (
                  <>
                    <h2 className="mt-8 font-display text-[clamp(2.2rem,5vw,3.6rem)] leading-[1.05] text-balance">
                      {mode === "mirror" ? (
                        <>Hello, <em className="text-iridescent">you.</em></>
                      ) : (
                        <>What&apos;s on your mind{greetingName ? <>, <em className="text-iridescent">{greetingName}</em></> : null}?</>
                      )}
                    </h2>
                    <p className="mt-4 max-w-md text-muted-foreground text-balance">
                      {emptyStateDescriptions[mode]}
                    </p>
                  </>
                )}
              </div>
            )}
            {messages.map((msg) => {
              if (msg.id === typeInId) {
                return (
                  <TypedInMessage key={msg.id} role={msg.role} content={msg.content} timestamp={msg.timestamp} onDone={() => setTypeInId(null)} />
                );
              }
              return (
              <ChatMessage
                key={msg.id}
                role={msg.role}
                content={msg.content}
                timestamp={msg.timestamp}
                noFade={msg.id === streamedId}
                peopleUsed={msg.peopleUsed}
                remembered={msg.remembered}
                rating={
                  msg.role === "assistant" && msg.serverId && !isIncognito
                    ? {
                        messageId: msg.serverId,
                        mode,
                        initial: msg.feedback ?? null,
                        initialReasons: msg.feedbackReasons ?? [],
                        onChange: (verdict, reasons) =>
                          setMessages((prev) =>
                            prev.map((m) => (m.id === msg.id ? { ...m, feedback: verdict, feedbackReasons: reasons } : m)),
                          ),
                      }
                    : undefined
                }
              />
              );
            })}
            {isTyping && streamingText && typedText ? (
              <ChatMessage role="assistant" content={typedText} timestamp="" streaming />
            ) : isTyping ? (
              <TypingIndicator />
            ) : null}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        <div className="px-4 pb-5 pt-3 md:px-8">
          <div className="max-w-3xl mx-auto">
            <ChatInput onSend={handleSend} isLoading={isTyping} />
          </div>
        </div>
      </div>

      <ConversationHistoryModal
        isOpen={showHistoryModal}
        onClose={() => setShowHistoryModal(false)}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        userId={userId}
        mode={mode}
      />
    </div>
  );
}
