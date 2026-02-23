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
import { MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import { useChatContext, type Message } from "@/contexts/ChatContext";

const API_BASE = "/api";

export function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [isTyping, setIsTyping] = useState(false);
  const [backendStatus, setBackendStatus] = useState<"checking" | "connected" | "disconnected">("checking");
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  
  // Get chat state from context (persists across navigation)
  const {
    conversationId,
    setConversationId,
    messages,
    setMessages,
    mode,
    conversationTitle,
    setConversationTitle,
    activeMirrorStyle,
    setActiveMirrorStyle,
    detectedEmotion,
    setDetectedEmotion,
    startNewConversation,
  } = useChatContext();

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const userId = localStorage.getItem("user_id") || "";

  // Ensure mode is in URL
  useEffect(() => {
    const urlMode = searchParams.get("mode");
    if (!urlMode) {
      setSearchParams({ mode: "reflection" }, { replace: true });
    }
  }, []);

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

  const handleModeChange = (newMode: "reflection" | "mirror") => {
    if (newMode === mode) return;
    
    console.log(`🔄 Mode change: ${mode} → ${newMode}`);
    
    // Start new conversation when switching modes
    startNewConversation();
    setSearchParams({ mode: newMode });
  };

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
          conversation_id: conversationId,
          text: content,
          mode,
        }),
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`HTTP ${res.status}: ${errText || res.statusText}`);
      }

      const data = await res.json();

      // Update mirror style if in mirror mode
      if (data.active_mirror_style) setActiveMirrorStyle(data.active_mirror_style);
      if (data.detected_emotion) setDetectedEmotion(data.detected_emotion);

      // Update conversation ID for new conversations
      if (!conversationId && data.conversation_id) {
        setConversationId(data.conversation_id);
        setConversationTitle(data.title);
        setSearchParams({ 
          conversation_id: data.conversation_id,
          mode 
        });
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
    setSearchParams({ conversation_id: convId, mode });
  };

  const handleNewChat = () => {
    startNewConversation();
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
                {conversationTitle || "New Conversation"}
              </h1>
              <p className="text-sm text-muted-foreground">
                {mode === "mirror" ? "Persona mirroring active" : "Reflection mode"}
              </p>
            </div>
            <div className="flex items-center gap-4">
              <ModeToggle mode={mode} onModeChange={handleModeChange} />
              
              {mode === "mirror" && activeMirrorStyle && (
                <ActiveMirrorIndicator
                  activeStyle={activeMirrorStyle as MirrorStyle}
                  detectedEmotion={detectedEmotion || undefined}
                />
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

        <ScrollArea className="flex-1 px-8 py-6">
          <div className="max-w-3xl mx-auto space-y-6">
            {messages.length === 0 && !isTyping && (
              <div className="text-center py-12">
                <h2 className="text-2xl font-semibold mb-2">Start a Conversation</h2>
                <p className="text-muted-foreground">
                  {mode === "mirror"
                    ? "Your persona will mirror your communication style"
                    : "Reflect on your thoughts and feelings"}
                </p>
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
