import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

export type InteractionMode = "reflection" | "mirror";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

interface ChatContextType {
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
  startNewConversation: () => void;
  loadConversation: (convId: string) => Promise<void>;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

const API_BASE = "/api";

export function ChatProvider({ children }: { children: ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationTitle, setConversationTitle] = useState<string | null>(null);
  const [activeMirrorStyle, setActiveMirrorStyle] = useState<string | null>(null);
  const [detectedEmotion, setDetectedEmotion] = useState<string | null>(null);

  // Get mode from URL, default to reflection
  const mode = (searchParams.get("mode") || "reflection") as InteractionMode;

  // Sync conversation state from URL
  useEffect(() => {
    const urlConvId = searchParams.get("conversation_id");
    
    if (urlConvId && urlConvId !== conversationId) {
      // URL has a conversation ID - load it
      console.log("🔄 ChatContext: Loading conversation from URL:", urlConvId);
      setConversationId(urlConvId);
      loadConversation(urlConvId);
    } else if (!urlConvId && conversationId) {
      // URL doesn't have conversation ID but we have one - start fresh
      console.log("🆕 ChatContext: Starting new conversation");
      setConversationId(null);
      setMessages([]);
      setConversationTitle(null);
    }
  }, [searchParams.get("conversation_id")]);

  const loadConversation = async (convId: string) => {
    try {
      const userId = localStorage.getItem("user_id") || "anonymous";
      const url = `${API_BASE}/conversations/${convId}/messages?user_id=${userId}`;
      
      console.log("📥 ChatContext: Fetching messages for conversation:", convId);
      
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`Failed to load conversation: ${res.status}`);
      }

      const data = await res.json();
      const loadedMessages: Message[] = (data || []).map((msg: any) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        timestamp: new Date(msg.created_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      }));

      setMessages(loadedMessages);
      console.log(`✅ ChatContext: Loaded ${loadedMessages.length} messages`);
    } catch (err) {
      console.error("❌ ChatContext: Error loading conversation:", err);
      setMessages([]);
    }
  };

  const startNewConversation = () => {
    console.log("🆕 ChatContext: Explicitly starting new conversation");
    setConversationId(null);
    setMessages([]);
    setConversationTitle(null);
    setActiveMirrorStyle(null);
    setDetectedEmotion(null);
    
    // Update URL to remove conversation_id
    const newParams: Record<string, string> = { mode };
    setSearchParams(newParams);
  };

  const value: ChatContextType = {
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
