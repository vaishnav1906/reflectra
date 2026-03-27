import { useState, useCallback } from "react";
import { formatDistanceToNow } from "date-fns";

interface ConversationItem {
  id: string;
  title: string | null;
  created_at: string;
  messagePreview?: string;
  relativeTime?: string;
}

interface UsePastConversationsReturn {
  conversations: ConversationItem[];
  isLoading: boolean;
  error: string;
  fetchConversations: (userId: string, mode?: string) => Promise<void>;
  refreshConversations: (userId: string, mode?: string) => Promise<void>;
}

const API_BASE = "/api";

/**
 * Custom hook for managing past conversations
 * Fetches and caches conversation list from the backend
 * Includes message previews and relative timestamps
 */
export function usePastConversations(): UsePastConversationsReturn {
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchConversations = useCallback(
    async (userId: string, mode?: string) => {
      if (!userId || userId === "" || userId === "anonymous") {
        setError("Please log in to view conversation history");
        setConversations([]);
        return;
      }

      setIsLoading(true);
      setError("");

      try {
        const modeParam = mode ? `&mode=${mode}` : "";
        const url = `${API_BASE}/conversations?user_id=${userId}${modeParam}`;

        console.log("📡 Fetching conversations:", {
          url,
          userId,
          mode,
        });

        const res = await fetch(url);

        if (!res.ok) {
          const errorText = await res.text();
          console.error("❌ API Error:", errorText);
          throw new Error(
            `Failed to fetch conversations: ${res.status} ${res.statusText}`
          );
        }

        const data = await res.json();

        // Handle both data.conversations and direct array format
        let conversationsList: ConversationItem[] = Array.isArray(data)
          ? data
          : data.conversations || [];

        // Fetch message previews for each conversation
        conversationsList = await Promise.all(
          conversationsList.map(async (conv) => {
            try {
              const msgRes = await fetch(
                `${API_BASE}/conversations/${conv.id}/messages?user_id=${userId}`
              );
              if (msgRes.ok) {
                const messages = await msgRes.json();
                // Get first user message or first message as preview
                const userMessage = messages.find(
                  (m: any) => m.role === "user"
                );
                const messageToPreview = userMessage || messages[0];
                if (messageToPreview) {
                  conv.messagePreview = messageToPreview.content
                    .substring(0, 60)
                    .trim();
                  if (messageToPreview.content.length > 60) {
                    conv.messagePreview += "...";
                  }
                }
              }
            } catch (err) {
              console.warn(
                `Failed to fetch messages for conversation ${conv.id}:`,
                err
              );
            }

            // Add relative timestamp
            conv.relativeTime = formatDistanceToNow(new Date(conv.created_at), {
              addSuffix: true,
            });

            return conv;
          })
        );

        console.log("✅ Fetched conversations with previews:", conversationsList);

        setConversations(conversationsList);
      } catch (err) {
        const errorMsg =
          err instanceof Error ? err.message : "Failed to load conversations";
        console.error("❌ Error:", errorMsg);
        setError(errorMsg);
        setConversations([]);
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  // Alias for explicit refresh
  const refreshConversations = useCallback(
    async (userId: string, mode?: string) => {
      await fetchConversations(userId, mode);
    },
    [fetchConversations]
  );

  return {
    conversations,
    isLoading,
    error,
    fetchConversations,
    refreshConversations,
  };
}
