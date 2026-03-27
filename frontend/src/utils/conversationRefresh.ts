/**
 * Utility for managing conversation list refresh across components
 * Allows ChatPage to notify ConversationHistoryModal to refresh the list
 */

let refreshCallbacks: Set<() => void> = new Set();

export function subscribeToConversationRefresh(callback: () => void) {
  refreshCallbacks.add(callback);
  
  return () => {
    refreshCallbacks.delete(callback);
  };
}

export function triggerConversationRefresh() {
  console.log("🔄 Triggering conversation refresh for", refreshCallbacks.size, "subscribers");
  refreshCallbacks.forEach(callback => callback());
}
