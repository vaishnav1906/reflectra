import { useEffect, useState } from "react";
import { X, MessageSquare, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { format } from "date-fns";

interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
}

interface ConversationHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectConversation: (conversationId: string) => void;
  onNewChat: () => void;
  userId: string;
  mode?: string; // "reflection" or "mirror"
}

const API_BASE = "/api";

export function ConversationHistoryModal({
  isOpen,
  onClose,
  onSelectConversation,
  onNewChat,
  userId,
  mode,
}: ConversationHistoryModalProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isOpen && userId) {
      console.log("\n=== CONVERSATION HISTORY MODAL OPENED ===");
      console.log("👤 userId from props:", userId);
      console.log("📦 userId type:", typeof userId);
      console.log("🔢 userId length:", userId?.length || 0);
      console.log("🎯 mode:", mode);
      console.log("📧 email from localStorage:", localStorage.getItem("email"));
      
      if (!userId || userId === "" || userId === "anonymous") {
        console.warn("⚠️ Invalid or anonymous userId, skipping fetch");
        setError("Please log in to view conversation history");
        return;
      }
      
      fetchConversations();
    }
  }, [isOpen, userId, mode]);

  const fetchConversations = async () => {
    setIsLoading(true);
    setError("");
    try {
      // Add mode parameter if provided
      const modeParam = mode ? `&mode=${mode}` : "";
      const url = `${API_BASE}/conversations?user_id=${userId}${modeParam}`;
      
      console.log("\n=== FETCHING CONVERSATIONS ===");
      console.log("📡 URL:", url);
      console.log("👤 User ID:", userId);
      console.log("🎯 Mode:", mode);
      
      const res = await fetch(url);
      
      console.log("📨 Response status:", res.status, res.statusText);
      console.log("📨 Response headers:", Object.fromEntries(res.headers.entries()));
      
      if (!res.ok) {
        const errorText = await res.text();
        console.error("❌ Error response body:", errorText);
        throw new Error(`Failed to fetch conversations: ${res.status} ${errorText}`);
      }
      
      const data = await res.json();
      console.log("✅ Raw API response:", JSON.stringify(data, null, 2));
      console.log("📊 data.conversations:", data.conversations);
      console.log("📊 Array.isArray(data.conversations):", Array.isArray(data.conversations));
      console.log("📊 Number of conversations:", data.conversations?.length || 0);
      
      // Try both data.conversations and data (in case backend format changes)
      const conversationsList = data.conversations || data || [];
      console.log("📋 Final conversations list:", conversationsList);
      
      setConversations(conversationsList);
      console.log("✅ State updated with", conversationsList.length, "conversations\n");
    } catch (err) {
      console.error("❌ Fetch conversations error:", err);
      console.error("❌ Error details:", {
        message: err instanceof Error ? err.message : 'Unknown error',
        stack: err instanceof Error ? err.stack : undefined
      });
      setError(err instanceof Error ? err.message : "Failed to load conversations");
      setConversations([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectConversation = (conversationId: string) => {
    onSelectConversation(conversationId);
    onClose();
  };

  const handleNewChat = () => {
    onNewChat();
    onClose();
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <Card className="w-full max-w-2xl max-h-[80vh] flex flex-col pointer-events-auto animate-in fade-in zoom-in-95 duration-200">
          <CardHeader className="border-b">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <MessageSquare className="w-5 h-5 text-primary" />
                <CardTitle>Conversation History</CardTitle>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={onClose}
                className="h-8 w-8"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>

          <CardContent className="flex-1 p-0 overflow-hidden">
            {/* New Chat Button */}
            <div className="p-4 border-b">
              <Button
                onClick={handleNewChat}
                className="w-full justify-start gap-2"
                variant="outline"
              >
                <Plus className="h-4 w-4" />
                Start New Conversation
              </Button>
            </div>

            {/* Conversations List */}
            <ScrollArea className="h-[calc(80vh-200px)]">
              <div className="p-4 space-y-2">
                {isLoading && (
                  <div className="text-center py-8 text-muted-foreground">
                    Loading conversations...
                  </div>
                )}

                {error && (
                  <div className="text-center py-8">
                    <div className="text-destructive mb-2">{error}</div>
                    {error.includes("log in") && (
                      <p className="text-sm text-muted-foreground">
                        User ID: {userId || "not set"}
                      </p>
                    )}
                  </div>
                )}

                {!isLoading && !error && (conversations || []).length === 0 && (
                  <div className="text-center py-8 text-muted-foreground">
                    <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>No conversations yet</p>
                    <p className="text-sm mt-1">Start a new chat to begin</p>
                  </div>
                )}

                {!isLoading &&
                  !error &&
                  (conversations || []).map((conv) => (
                    <button
                      key={conv.id}
                      onClick={() => handleSelectConversation(conv.id)}
                      className={cn(
                        "w-full text-left p-4 rounded-lg border border-border",
                        "hover:bg-primary/30 hover:border-primary",
                        "transition-all duration-200",
                        "focus:outline-none focus:ring-2 focus:ring-primary"
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <h3 className="font-medium truncate text-foreground">
                            {conv.title || "Untitled Conversation"}
                          </h3>
                          <p className="text-sm text-muted-foreground mt-1">
                            {format(new Date(conv.created_at), "MMM d, yyyy 'at' h:mm a")}
                          </p>
                        </div>
                        <MessageSquare className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-1" />
                      </div>
                    </button>
                  ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
