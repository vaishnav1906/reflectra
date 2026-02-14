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
}

const API_BASE = "/api";

export function ConversationHistoryModal({
  isOpen,
  onClose,
  onSelectConversation,
  onNewChat,
  userId,
}: ConversationHistoryModalProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isOpen && userId) {
      fetchConversations();
    }
  }, [isOpen, userId]);

  const fetchConversations = async () => {
    setIsLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/conversations?user_id=${userId}`);
      if (!res.ok) {
        throw new Error("Failed to fetch conversations");
      }
      const data = await res.json();
      setConversations(data.conversations || []);
    } catch (err) {
      console.error("Error fetching conversations:", err);
      setError("Failed to load conversations");
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
                  <div className="text-center py-8 text-destructive">
                    {error}
                  </div>
                )}

                {!isLoading && !error && conversations.length === 0 && (
                  <div className="text-center py-8 text-muted-foreground">
                    <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>No conversations yet</p>
                    <p className="text-sm mt-1">Start a new chat to begin</p>
                  </div>
                )}

                {!isLoading &&
                  !error &&
                  conversations.map((conv) => (
                    <button
                      key={conv.id}
                      onClick={() => handleSelectConversation(conv.id)}
                      className={cn(
                        "w-full text-left p-4 rounded-lg border",
                        "hover:bg-accent hover:border-primary/50",
                        "transition-all duration-200",
                        "focus:outline-none focus:ring-2 focus:ring-primary"
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <h3 className="font-medium truncate">
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
