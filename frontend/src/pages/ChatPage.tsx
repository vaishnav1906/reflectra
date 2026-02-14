import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { TypingIndicator } from "@/components/chat/TypingIndicator";
import { ModeToggle, InteractionMode } from "@/components/chat/ModeToggle";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Users } from "lucide-react";
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
  const [mode, setMode] = useState<InteractionMode>("reflection");
  const [backendStatus, setBackendStatus] = useState<"checking" | "connected" | "disconnected">("checking");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversationTitle, setConversationTitle] = useState<string | null>(null);

  // Sync mode with URL params on mount
  useEffect(() => {
    const urlMode = searchParams.get("mode");
    if (urlMode === "reflection" || urlMode === "mirror" || urlMode === "persona_mirror") {
      // Normalize persona_mirror to mirror
      const normalizedMode = urlMode === "persona_mirror" ? "mirror" : urlMode;
      if (normalizedMode !== mode) {
        setMode(normalizedMode as InteractionMode);
      }
    } else if (!urlMode) {
      // Set default mode in URL
      setSearchParams((prev) => {
        const newParams = new URLSearchParams(prev);
        newParams.set("mode", mode);
        return newParams;
      }, { replace: true });
    }
  }, []);

  // Handle mode changes - clear state and update URL
  const handleModeChange = (newMode: InteractionMode) => {
    console.log(`🔄 Switching mode from ${mode} to ${newMode}`);
    
    // Clear state
    setConversationId(null);
    setMessages([]);
    setConversationTitle(null);
    
    // Update mode
    setMode(newMode);
    
    // Update URL - remove conversation_id, update mode
    setSearchParams({ mode: newMode });
  };

  // Get conversation_id from URL params
  useEffect(() => {
    const convId = searchParams.get("conversation_id");
    const urlMode = searchParams.get("mode");
    
    if (convId && convId !== conversationId) {
      setConversationId(convId);
      loadConversationMessages(convId);
    } else if (!convId && conversationId) {
      // New chat - clear everything
      setConversationId(null);
      setMessages([]);
      setConversationTitle(null);
    }
    
    // Sync mode from URL
    if (urlMode === "reflection" || urlMode === "mirror") {
      if (urlMode !== mode) {
        setMode(urlMode as InteractionMode);
      }
    }
  }, [searchParams]);

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

  const loadConversationMessages = async (convId: string) => {
    try {
      const userId = localStorage.getItem("user_id") || "anonymous";
      const res = await fetch(
        `${API_BASE}/conversations/${convId}/messages?user_id=${userId}`
      );

      if (!res.ok) {
        throw new Error("Failed to load conversation");
      }

      const data = await res.json();
      const loadedMessages: Message[] = data.map((msg: any) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        timestamp: new Date(msg.created_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      }));

      setMessages(loadedMessages);
      console.log(`✅ Loaded ${loadedMessages.length} messages`);
    } catch (err) {
      console.error("❌ Error loading conversation:", err);
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
        full_response: data,
      });

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
              <ModeToggle mode={mode} onModeChange={handleModeChange} />
              {mode === "mirror" && (
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10">
                  <Users className="w-4 h-4 text-primary" />
                  <span className="text-xs">Mirroring Active</span>
                </div>
              )}
            </div>
          </div>
        </header>

        <ScrollArea className="flex-1 px-8 py-6">
          <div className="max-w-3xl mx-auto space-y-6">
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
            {messages.map((msg) => (
              <ChatMessage key={msg.id} {...msg} className={cn()} />
            ))}
            {isTyping && <TypingIndicator />}
          </div>
        </ScrollArea>

        <div className="px-8 py-6 border-t">
          <div className="max-w-3xl mx-auto">
            <ChatInput onSend={handleSend} isLoading={isTyping} />
          </div>
        </div>
      </div>
    </div>
  );
}