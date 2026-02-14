import { useState, useEffect } from "react";
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
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [mode, setMode] = useState<InteractionMode>("reflection");
  const [backendStatus, setBackendStatus] = useState<"checking" | "connected" | "disconnected">("checking");

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
        credentials: "include", // Include cookies for session management
        body: JSON.stringify({
          user_id: userId,
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
        mode: data.mode,
        mirror_active: data.mirror_active,
        full_response: data
      });

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

      const errorMessage = err instanceof Error 
        ? err.message 
        : "Unknown error occurred";

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
              <h1 className="text-lg font-semibold">Conversation</h1>
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
              <ModeToggle mode={mode} onModeChange={setMode} />
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