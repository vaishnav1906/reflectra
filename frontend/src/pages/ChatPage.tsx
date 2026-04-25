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

const API_BASE = "/api";

export function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [isTyping, setIsTyping] = useState(false);
  const [assistantTaskType, setAssistantTaskType] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<"checking" | "connected" | "disconnected">("checking");
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [incognitoFeedback, setIncognitoFeedback] = useState<"enabled" | "disabled" | null>(null);
  
  // Get chat state from context (persists across navigation)
  const {
    activeConversationId,
    setActiveConversationId,
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

  const modeDescriptions: Record<InteractionMode, string> = {
    reflection: "Reflection mode",
    mirror: "Persona mirror active (explicit task commands enabled)",
  };

  const emptyStateDescriptions: Record<InteractionMode, string> = {
    reflection: "Reflect on your thoughts and feelings",
    mirror: "Your persona will mirror your communication style and handle explicit task requests",
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
        const res = await fetch(`${API_BASE}/health`);
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
    startNewConversation();
    setAssistantTaskType(null);
    setSearchParams({ mode: newMode });
  };

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
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          user_id: userId,
          conversation_id: activeConversationId,
          message: content,
          mode,
          is_incognito: isIncognito,
          incognito_session_id: incognitoSessionId,
        }),
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`HTTP ${res.status}: ${errText || res.statusText}`);
      }

      const data = await res.json();
      if (!data || typeof data.reply !== "string") {
        throw new Error("Invalid chat response payload");
      }

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
        setActiveConversationId(data.conversation_id);
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
      }

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.reply,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (err) {
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
        <header className="px-8 py-4 border-b border-border">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-semibold">
                {conversationTitle || (isIncognito ? "Incognito Session" : "New Conversation")}
              </h1>
              <p className="text-sm text-muted-foreground">
                {modeDescriptions[mode]}
              </p>
            </div>
            <div className="flex items-center gap-4">
              <ModeToggle mode={mode} onModeChange={handleModeChange} />

              <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/40 px-3 py-2">
                <div className="flex items-center gap-2">
                  <EyeOff className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-xs font-medium text-foreground">Incognito</p>
                    <p className="text-[10px] text-muted-foreground">Temporary session</p>
                  </div>
                </div>
                <Switch checked={isIncognito} onCheckedChange={handleIncognitoChange} />
              </div>
              
              {mode === "mirror" && activeMirrorStyle && (
                <ActiveMirrorIndicator
                  activeStyle={activeMirrorStyle as MirrorStyle}
                  detectedEmotion={detectedEmotion || undefined}
                />
              )}

              {mode === "mirror" && assistantTaskType && assistantTaskType !== "generic" && (
                <div className="flex items-center gap-2 px-2 py-1 rounded-full bg-amber-500/10 border border-amber-500/20">
                  <span className="text-xs text-amber-700 font-medium">
                    Task: {formatTaskType(assistantTaskType)}
                  </span>
                </div>
              )}
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowHistoryModal(true)}
                className="gap-2"
              >
                <MessageSquare className="w-4 h-4" />
                History
              </Button>
              
              {backendStatus === "connected" && (
                <div className="flex items-center gap-2 px-2 py-1 rounded-full bg-green-500/10">
                  <div className="w-2 h-2 rounded-full bg-green-500"></div>
                  <span className="text-xs text-green-600">Connected</span>
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
          <div className="mx-8 mt-4 rounded-xl border border-white/10 bg-white/5 px-4 py-3 backdrop-blur-sm">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
                <EyeOff className="h-4 w-4" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">Incognito Mode ON</p>
                <p className="text-sm text-muted-foreground">
                  This conversation is temporary and won’t be saved or used to improve your profile.
                </p>
              </div>
            </div>
          </div>
        )}

        <ScrollArea className="flex-1 px-8 py-6">
          <div className="max-w-3xl mx-auto space-y-6">
            {loadingMessages && (
              <div className="sticky top-0 z-10 flex justify-center py-2">
                <div className="rounded-full border border-border bg-background/95 px-3 py-1 text-xs text-muted-foreground shadow-sm backdrop-blur">
                  Loading messages...
                </div>
              </div>
            )}

            {messages.length === 0 && !isTyping && !loadingMessages && (
              <div className="text-center py-12">
                {activeConversationId ? (
                  <>
                    <h2 className="text-2xl font-semibold mb-2">No messages yet</h2>
                    <p className="text-muted-foreground">This conversation has no messages yet.</p>
                  </>
                ) : (
                  <>
                    <h2 className="text-2xl font-semibold mb-2">Start a Conversation</h2>
                    <p className="text-muted-foreground">
                      {emptyStateDescriptions[mode]}
                    </p>
                  </>
                )}
              </div>
            )}
            {messages.map((msg) => (
              <ChatMessage key={msg.id} {...msg} className={cn()} />
            ))}
            {isTyping && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        <div className="px-8 py-6 border-t">
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
