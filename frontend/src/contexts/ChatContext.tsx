import { createContext, useContext, useState, useEffect, useRef, ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { apiFetch } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
export type InteractionMode = "reflection" | "mirror";

export function isInteractionMode(mode: string | null): mode is InteractionMode {
  return mode === "reflection" || mode === "mirror";
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  /** The stored message's id, for rating a reply (absent in incognito). */
  serverId?: string;
  feedback?: "up" | "down" | null;
  feedbackReasons?: string[];
  /** People whose card the reply drew on. */
  peopleUsed?: { id: string; name: string }[];
  /** Past messages the reply visibly drew on. */
  remembered?: RememberedMoment[];
}

export interface RememberedMoment {
  said: string;
  when: string;
  conversation_id: string;
}

interface ChatContextType {
  activeConversationId: string | null;
  setActiveConversationId: (id: string | null) => void;
  /** A conversation the chat just created: its messages are already on screen, so don't reload them. */
  adoptNewConversation: (id: string) => void;
  loadingMessages: boolean;
  isIncognito: boolean;
  incognitoSessionId: string | null;
  // Backwards-compatible aliases for existing consumers
  conversationId: string | null;
  setConversationId: (id: string | null) => void;
  messages: Message[];
  setMessages: (messages: Message[] | ((prev: Message[]) => Message[])) => void;
  mode: InteractionMode;
  conversationTitle: string | null;
  setConversationTitle: (title: string | null) => void;
  activeMirrorStyle: string | null;
  setActiveMirrorStyle: (style: string | null) => void;
  detectedEmotion: string | null;
  setDetectedEmotion: (emotion: string | null) => void;
  setIncognitoMode: (enabled: boolean) => void;
  startNewConversation: () => void;
  loadConversation: (convId: string) => Promise<void>;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

const API_BASE = "/api";

export function ChatProvider({ children }: { children: ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [conversationTitle, setConversationTitle] = useState<string | null>(null);
  const [activeMirrorStyle, setActiveMirrorStyle] = useState<string | null>(null);
  const [detectedEmotion, setDetectedEmotion] = useState<string | null>(null);
  const [isIncognito, setIsIncognito] = useState(false);
  const [incognitoSessionId, setIncognitoSessionId] = useState<string | null>(null);
  const latestMessageRequestId = useRef(0);
  // Set when the chat itself just created this conversation. Reloading it from the server
  // would replace the reply on screen (losing its "remembered"/People chips) or show it twice.
  const createdHere = useRef<string | null>(null);
  const adoptNewConversation = (id: string) => {
    createdHere.current = id;
    setActiveConversationId(id);
  };

  // Get mode from URL, default to reflection
  const modeParam = searchParams.get("mode");
  const mode: InteractionMode = isInteractionMode(modeParam) ? modeParam : "reflection";

  const urlConversationId = searchParams.get("conversation_id");

  const clearConversationState = () => {
    setActiveConversationId(null);
    setMessages([]);
    setLoadingMessages(false);
    setConversationTitle(null);
    setActiveMirrorStyle(null);
    setDetectedEmotion(null);
  };

  // Drop all in-memory chat state when the signed-in user changes (logout,
  // account deletion, or switching accounts) so nothing leaks between users.
  const { user: authUser } = useAuth();
  const authUserId = authUser?.id ?? null;
  const previousAuthUserId = useRef<string | null>(authUserId);
  useEffect(() => {
    if (previousAuthUserId.current !== authUserId) {
      previousAuthUserId.current = authUserId;
      clearConversationState();
      setIsIncognito(false);
      setIncognitoSessionId(null);
    }
  }, [authUserId]);

  const clearIncognitoSessionHistory = (sessionId: string) => {
    void apiFetch(`/api/chat/incognito-history/${sessionId}`, {
      method: "DELETE",
    }).catch((error) => {
      console.warn("Failed to clear incognito session history:", error);
    });
  };

  const setIncognitoMode = (enabled: boolean) => {
    const previousSessionId = incognitoSessionId;
    setIsIncognito(enabled);
    clearConversationState();

    if (enabled) {
      if (previousSessionId) {
        clearIncognitoSessionHistory(previousSessionId);
      }
      setIncognitoSessionId(crypto.randomUUID());
    } else {
      if (previousSessionId) {
        clearIncognitoSessionHistory(previousSessionId);
      }
      setIncognitoSessionId(null);
    }

    setSearchParams({ mode });
  };

  // Sync active conversation from URL
  useEffect(() => {
    if (isIncognito) {
      return;
    }

    if (urlConversationId !== activeConversationId) {
      console.log("🔄 ChatContext: Syncing active conversation from URL:", urlConversationId);
      setActiveConversationId(urlConversationId);
    }

    if (!urlConversationId && activeConversationId) {
      // New chat route should reset visible chat content
      setMessages([]);
      setConversationTitle(null);
      setActiveMirrorStyle(null);
      setDetectedEmotion(null);
    }
  }, [urlConversationId, activeConversationId, isIncognito]);

  // Load messages whenever the active conversation changes.
  // Uses cancellation to prevent stale responses from overwriting current state.
  useEffect(() => {
    if (!activeConversationId || isIncognito) {
      setLoadingMessages(false);
      return;
    }
    if (createdHere.current === activeConversationId) {
      createdHere.current = null; // opening it again later loads it normally
      setLoadingMessages(false);
      return;
    }

    let isCancelled = false;
    const controller = new AbortController();
    const requestId = ++latestMessageRequestId.current;

    const loadMessages = async () => {
      setLoadingMessages(true);

      try {
        const userId = localStorage.getItem("user_id") || "anonymous";
        const url = `${API_BASE}/conversations/${activeConversationId}/messages?user_id=${userId}`;

        console.log("📥 ChatContext: Fetching messages for conversation:", activeConversationId);

        const res = await apiFetch(url, { signal: controller.signal });
        if (!res.ok) {
          throw new Error(`Failed to load conversation: ${res.status}`);
        }

        const data = await res.json();
        const loadedMessages: Message[] = (data || []).map((msg: { id: string; role: "user" | "assistant"; content: string; created_at: string; feedback?: "up" | "down" | null; feedback_reasons?: string[] }) => ({
          id: msg.id,
          serverId: msg.id,
          feedback: msg.feedback ?? null,
          feedbackReasons: msg.feedback_reasons ?? [],
          role: msg.role,
          content: msg.content,
          timestamp: new Date(msg.created_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        }));

        if (!isCancelled && requestId === latestMessageRequestId.current) {
          setMessages(loadedMessages);
          console.log(`✅ ChatContext: Loaded ${loadedMessages.length} messages`);
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          return;
        }

        console.error("❌ ChatContext: Error loading conversation:", err);
        if (!isCancelled && requestId === latestMessageRequestId.current) {
          setMessages([]);
        }
      } finally {
        if (!isCancelled && requestId === latestMessageRequestId.current) {
          setLoadingMessages(false);
        }
      }
    };

    loadMessages();

    return () => {
      isCancelled = true;
      controller.abort();
    };
  }, [activeConversationId, isIncognito]);

  const loadConversation = async (convId: string) => {
    if (isIncognito) {
      return;
    }

    setActiveConversationId(convId);
  };

  const startNewConversation = () => {
    console.log("🆕 ChatContext: Explicitly starting new conversation");
    const previousSessionId = isIncognito ? incognitoSessionId : null;
    clearConversationState();

    if (isIncognito) {
      if (previousSessionId) {
        clearIncognitoSessionHistory(previousSessionId);
      }
      setIncognitoSessionId(crypto.randomUUID());
    }
    
    // Update URL to remove conversation_id
    const newParams: Record<string, string> = { mode };
    setSearchParams(newParams);
  };

  const value: ChatContextType = {
    activeConversationId,
    setActiveConversationId,
    adoptNewConversation,
    loadingMessages,
    conversationId: activeConversationId,
    setConversationId: setActiveConversationId,
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
    loadConversation,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChatContext() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error("useChatContext must be used within ChatProvider");
  }
  return context;
}
