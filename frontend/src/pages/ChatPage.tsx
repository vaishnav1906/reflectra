import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { TypingIndicator } from "@/components/chat/TypingIndicator";
import { ModeToggle, InteractionMode } from "@/components/chat/ModeToggle";
import { ActiveMirrorIndicator, MirrorStyle } from "@/components/chat/ActiveMirrorIndicator";
import { ConversationHistoryModal } from "@/components/chat/ConversationHistoryModal";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { MessageSquare, Users } from "lucide-react";
import { cn } from "@/lib/utils";

// Use /api prefix which will be proxied by Vite to the backend
const API_BASE = "/api";
console.log("✅ Using API proxy:", API_BASE);

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [backendStatus, setBackendStatus] = useState<"checking" | "connected" | "disconnected">("checking");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversationTitle, setConversationTitle] = useState<string | null>(null);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [activeMirrorStyle, setActiveMirrorStyle] = useState<MirrorStyle>("dominant");
  const [detectedEmotion, setDetectedEmotion] = useState<string | null>(null);

  // Refs for auto-scroll behavior
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const chatContainerRef = useRef<HTMLDivElement | null>(null);

  // Get userId safely
  const userId = localStorage.getItem("user_id") || "";

  // Centralized mode reading from URL
  const mode = (searchParams.get("mode") || "reflection") as InteractionMode;

  // Auto-scroll helper functions
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const isUserNearBottom = () => {
    // Check if chatContainerRef's parent viewport is near bottom
    const container = chatContainerRef.current;
    if (!container) return true;

    // Find the scrollable viewport (parent element of our content div)
    const viewport = container.parentElement;
    if (!viewport) return true;

    const { scrollTop, scrollHeight, clientHeight } = viewport;
    return scrollHeight - scrollTop - clientHeight < 100;
  };

  // Debug logs
  console.log("📊 ChatPage render:", {
    mode,
    conversationId,
    messagesCount: messages?.length || 0,
    userId: userId || "none",
    urlParams: window.location.search,
  });

  // Ensure mode is always in URL (run once on mount)
  useEffect(() => {
    const urlMode = searchParams.get("mode");
    if (!urlMode) {
      console.log("🔧 Setting default mode in URL");
      setSearchParams({ mode: "reflection" }, { replace: true });
    }
  }, []);

  // Handle mode changes - clear state and update URL
  const handleModeChange = (newMode: InteractionMode) => {
    console.log(`🔄 Switching mode from ${mode} to ${newMode}`);
    
    if (newMode === mode) return; // Prevent unnecessary updates
    
    // Clear state
    setConversationId(null);
    setMessages([]);
    setConversationTitle(null);
    
    // Update URL - remove conversation_id, update mode
    setSearchParams({ mode: newMode });
  };

  // Load conversation when URL changes
  useEffect(() => {
    const convId = searchParams.get("conversation_id");
    
    console.log("🔄 URL changed:", {
      conversationId: convId,
      mode,
      currentState: conversationId,
    });
    
    if (convId && convId !== conversationId) {
      console.log("📥 Loading conversation:", convId);
      setConversationId(convId);
      loadConversationMessages(convId);
    } else if (!convId && conversationId) {
      // New chat - clear everything
      console.log("🆕 New chat - clearing state");
      setConversationId(null);
      setMessages([]);
      setConversationTitle(null);
    }
  }, [searchParams.get("conversation_id")]);

  // Check backend connection on mount
  useEffect(() => {
    const checkBackend = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`);
        if (res.ok) {
          setBackendStatus("connected");
          console.log("✅ Backend connected");
        } else {
          setBackendStatus("disconnected");
          console.error("❌ Backend not responding");
        }
      } catch (err) {
        setBackendStatus("disconnected");
        console.error("❌ Backend connection failed:", err);
      }
    };
    checkBackend();
  }, []);

  // Auto-scroll when new messages arrive (only if user is near bottom)
  useEffect(() => {
    if (isUserNearBottom()) {
      scrollToBottom();
    }
  }, [messages]);

  const loadConversationMessages = async (convId: string) => {
    try {
      const userId = localStorage.getItem("user_id") || "anonymous";
      const url = `${API_BASE}/conversations/${convId}/messages?user_id=${userId}`;
      
      console.log("\n=== LOADING CONVERSATION MESSAGES ===");
      console.log("📥 Conversation ID:", convId);
      console.log("👤 User ID:", userId);
      console.log("📡 URL:", url);
      
      const res = await fetch(url);
      
      console.log("📨 Response status:", res.status, res.statusText);

      if (!res.ok) {
        const errorText = await res.text();
        console.error("❌ Error response body:", errorText);
        throw new Error(`Failed to load conversation: ${res.status} - ${errorText}`);
      }

      const data = await res.json();
      console.log("✅ Raw API response:", JSON.stringify(data, null, 2));
      console.log("📊 Array.isArray(data):", Array.isArray(data));
      console.log("📊 Number of messages:", data?.length || 0);
      
      const loadedMessages: Message[] = (data || []).map((msg: any) => {
        console.log("  - Message:", { id: msg.id, role: msg.role, content_preview: msg.content?.substring(0, 50) });
        return {
          id: msg.id,
          role: msg.role,
          content: msg.content,
          timestamp: new Date(msg.created_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        };
      });

      setMessages(loadedMessages);
      console.log(`✅ Loaded and set ${loadedMessages.length} messages in state\n`);
    } catch (err) {
      console.error("❌ Error loading conversation:", err);
      console.error("❌ Error details:", {
        message: err instanceof Error ? err.message : 'Unknown error',
        stack: err instanceof Error ? err.stack : undefined
      });
      setMessages([]);
    }
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
      const userId = localStorage.getItem("user_id") || "anonymous";
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
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
        console.error("❌ Backend error response:", {
          status: res.status,
          statusText: res.statusText,
          body: errText,
          headers: Object.fromEntries(res.headers.entries()),
        });
        throw new Error(`HTTP ${res.status}: ${errText || res.statusText}`);
      }

      const data = await res.json();
      console.log("✅ Received response from backend:", {
        reply_preview: data.reply?.substring(0, 50) + "...",
        conversation_id: data.conversation_id,
        title: data.title,
        mode: data.mode,
        mirror_active: data.mirror_active,
        active_mirror_style: data.active_mirror_style,
        detected_emotion: data.detected_emotion,
        full_response: data,
      });

      // Update active mirror style and detected emotion
      if (data.active_mirror_style) {
        setActiveMirrorStyle(data.active_mirror_style);
      }
      if (data.detected_emotion) {
        setDetectedEmotion(data.detected_emotion);
      }

      // Update conversation ID if this is a new conversation
      if (!conversationId && data.conversation_id) {
        setConversationId(data.conversation_id);
        setConversationTitle(data.title);
        // Update URL with both conversation_id and mode
        setSearchParams({ 
          conversation_id: data.conversation_id,
          mode: mode 
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

      const errorMessage =
        err instanceof Error ? err.message : "Unknown error occurred";

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

  const handleSelectConversation = (conversationId: string) => {
    console.log(`📂 Selecting conversation: ${conversationId}`);
    setSearchParams({ conversation_id: conversationId, mode });
  };

  const handleNewChat = () => {
    console.log("🆕 Starting new chat");
    setSearchParams({ mode });
  };

  // Fallback if no userId
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
                {mode === "mirror"
                  ? "Persona mirroring active"
                  : "Reflection mode"}
              </p>
            </div>
            <div className="flex items-center gap-4">
              {/* Mode Toggle */}
              <ModeToggle mode={mode} onModeChange={handleModeChange} />
              
              {/* Active Mirror Archetype Indicator - auto-detected, no manual override */}
              {mode === "mirror" && activeMirrorStyle && (
                <ActiveMirrorIndicator
                  activeStyle={activeMirrorStyle}
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
                Past Conversations
              </Button>
              {backendStatus === "connected" && (
                <div className="flex items-center gap-2 px-2 py-1 rounded-full bg-green-500/10">
                  <div className="w-2 h-2 rounded-full bg-green-500"></div>
                  <span className="text-xs text-green-600">Connected</span>
                </div>
              )}
              {backendStatus === "disconnected" && (
                <div className="flex items-center gap-2 px-2 py-1 rounded-full bg-red-500/10">
                  <div className="w-2 h-2 rounded-full bg-red-500"></div>
                  <span className="text-xs text-red-600">Disconnected</span>
                </div>
              )}
            </div>
          </div>
        </header>

        <ScrollArea className="flex-1 px-8 py-6">
          <div 
            ref={chatContainerRef}
            className="max-w-3xl mx-auto space-y-6"
          >
            {messages.length === 0 && !isTyping && (
              <div className="text-center py-12">
                <h2 className="text-2xl font-semibold mb-2">
                  Start a Conversation
                </h2>
                <p className="text-muted-foreground">
                  {mode === "mirror"
                    ? "Your persona will mirror your communication style"
                    : "Reflect on your thoughts and feelings"}
                </p>
              </div>
            )}
            {(messages || []).map((msg) => (
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

      {/* Conversation History Modal */}
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
