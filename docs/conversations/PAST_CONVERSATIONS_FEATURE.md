# Past Conversations Feature - Complete Implementation Guide

## Overview

The Past Conversations feature allows users to:
- View all their previous chat sessions, sorted by most recent first
- Click on any past conversation to load and view all messages
- See message previews and relative timestamps (e.g., "2 hours ago")
- Automatically sync the conversation list when a new conversation is created
- Filter conversations by mode (Reflection or Mirror)

---

## Architecture

### Frontend Components

#### 1. **Custom Hook: `usePastConversations`** (`src/hooks/usePastConversations.ts`)
- Manages conversation fetching and state
- Fetches conversation list from backend
- Retrieves message previews for each conversation
- Calculates relative timestamps ("2 hours ago", "Yesterday", etc.)
- Provides both `fetchConversations` and `refreshConversations` methods

**Usage:**
```typescript
const { conversations, isLoading, error, fetchConversations, refreshConversations } = usePastConversations();
```

#### 2. **ConversationHistoryModal** (`src/components/chat/ConversationHistoryModal.tsx`)
- Overlay modal displaying past conversations
- Subscribes to conversation refresh events
- Shows:
  - Conversation title (AI-generated or "Untitled")
  - Message preview (first 60 characters of first user message)
  - Relative timestamp ("2 hours ago")
  - Loading and error states
- Triggered by:
  - Right-click on "Conversation" in sidebar (AppSidebar)
  - "History" button in ChatPage header

#### 3. **ChatPage** (`src/pages/ChatPage.tsx`)
- Triggers conversation refresh when new conversation is created
- Passes userId and mode to modal
- Handles conversation selection and loading

#### 4. **Refresh Utility** (`src/utils/conversationRefresh.ts`)
- Pub/Sub system for conversation list refresh
- Allows ChatPage to notify modal when new conversation is created
- Prevents need for polling or constant re-fetching

### Backend Endpoints

#### 1. **GET `/conversations`** (Chat API)
```
Query Parameters:
- user_id (required): User's UUID
- mode (optional): "reflection" or "mirror" to filter by mode

Response:
{
  "conversations": [
    {
      "id": "uuid",
      "title": "Conversation Title",
      "created_at": "2024-01-20T15:30:00+00:00"
    }
  ]
}
```

**Features:**
- Filters by user_id (user isolation)
- Optionally filters by mode
- Returns conversations sorted by created_at DESC (most recent first)
- Includes detailed logging for debugging

#### 2. **GET `/conversations/{conversation_id}/messages`** (Chat API)
```
Query Parameters:
- user_id (required): User's UUID to validate ownership

Response:
[
  {
    "id": "msg-uuid",
    "conversation_id": "conv-uuid",
    "user_id": "user-uuid",
    "role": "user",
    "content": "Message content",
    "created_at": "2024-01-20T15:30:05+00:00",
    "embedding": null,
    "token_count": null
  }
]
```

**Features:**
- Validates conversation belongs to user
- Returns messages in chronological order (created_at ASC)
- Supports empty conversations

---

## Session ID (Conversation ID) Handling

### How Session IDs are Generated

1. **New Conversation:**
   - User sends first message with `conversation_id: null`
   - Backend generates UUID using PostgreSQL: `gen_random_uuid()`
   - UUID is returned in response and stored in frontend URL params
   - All subsequent messages use this conversation_id

2. **Existing Conversation:**
   - User sends message with `conversation_id` set
   - Backend validates conversation exists and belongs to user
   - Messages are stored with the existing conversation_id

### Database Schema

**conversations table:**
```sql
id: UUID (PRIMARY KEY, auto-generated)
user_id: UUID (FOREIGN KEY → users.id)
title: TEXT (nullable, AI-generated or user-provided)
mode: VARCHAR(32) (default: 'reflection')
metadata: JSONB (default: {})
created_at: TIMESTAMP (server-generated)
updated_at: TIMESTAMP (server-generated)

Indexes:
- idx_conversations_user_id (user_id)
- idx_conversations_user_created (user_id, created_at DESC)
```

**messages table:**
```sql
id: UUID (PRIMARY KEY, auto-generated)
conversation_id: UUID (FOREIGN KEY → conversations.id, ON DELETE CASCADE)
user_id: UUID (FOREIGN KEY → users.id, ON DELETE CASCADE)
role: VARCHAR(32) ('user' or 'assistant')
content: TEXT
embedding: Vector(1536) (optional, for semantic search)
token_count: INTEGER (optional)
created_at: TIMESTAMP (server-generated)

Indexes:
- idx_messages_conversation_created (conversation_id, created_at ASC)
- idx_messages_user_id (user_id)
- idx_messages_role (role)
```

### CRUD Operations

Located in `backend/app/db/crud.py`:

1. **`create_conversation()`** - Creates new conversation record
2. **`create_message()`** - Creates and stores message with conversation_id
3. **`get_user_conversations()`** - Lists all conversations for a user
4. **`get_conversation_by_id()`** - Fetches specific conversation by ID and user_id
5. **`get_conversation_history()`** - Gets all messages in a conversation

---

## Row-Level Security (RLS) Policies

### Requirements

The database should have RLS policies to enforce user isolation:

```sql
-- Enable RLS on conversations table
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

-- Conversations: Users can only SELECT/INSERT/UPDATE/DELETE their own
CREATE POLICY conversations_user_isolation ON conversations
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Enable RLS on messages table
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Messages: Users can only access messages in their conversations
CREATE POLICY messages_user_isolation ON messages
  USING (
    conversation_id IN (
      SELECT id FROM conversations WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    conversation_id IN (
      SELECT id FROM conversations WHERE user_id = auth.uid()
    )
  );
```

### How It Works

- Backend includes `user_id` in all queries
- RLS policies further restrict at the database level
- User cannot see or modify other users' conversations/messages
- Double protection: application-level + database-level

### Verification

Check if RLS is enabled:
```sql
SELECT schemaname, tablename, rowsecurity 
FROM pg_tables 
WHERE tablename IN ('conversations', 'messages');
```

If `rowsecurity` is `true`, policies are enabled.

---

## Data Flow

### Loading Past Conversations

```
User clicks "History" button
    ↓
ConversationHistoryModal opens (isOpen = true)
    ↓
useEffect triggers fetchConversations()
    ↓
usePastConversations hook:
  - Calls GET /conversations?user_id={id}&mode={mode}
  - For each conversation:
    - Calls GET /conversations/{id}/messages?user_id={id}
    - Extracts first user message as preview
    - Calculates relative timestamp
    ↓
Modal displays conversation list with previews and timestamps
    ↓
User clicks a conversation
    ↓
ChatPage:
  - Calls setActiveConversationId()
  - Updates URL with conversation_id
  - ChatContext loads messages via GET /conversations/{id}/messages
  - Messages display in chronological order
```

### Creating New Conversation & Auto-Refresh

```
User types message and sends
    ↓
ChatPage.handleSend():
  - Sends POST /chat with conversation_id=null
    ↓
Backend:
  - Generates UUID via gen_random_uuid()
  - Creates conversation record
  - Stores user message
  - Generates AI response
  - Stores assistant message
  - Returns conversation_id and title
    ↓
ChatPage:
  - Updates activeConversationId from response
  - Updates URL with new conversation_id
  - Calls triggerConversationRefresh()
    ↓
conversationRefresh pub/sub:
  - Notifies all subscribers
  - ConversationHistoryModal (if subscribed) refetches
  - If modal is open, new conversation appears in list
```

---

## Testing Instructions

### Prerequisites
- Backend running: `cd backend && python3 -m uvicorn app.main:app --reload`
- Frontend running: `cd frontend && npm run dev`
- Logged in with valid user_id

### Test 1: Basic Conversation Loading

1. **Create a conversation:**
   - Navigate to `/app/chat`
   - Send a message: "Hello, how are you?"
   - Wait for response
   - Note the conversation_id in URL

2. **View Past Conversations:**
   - Click "History" button
   - Verify conversation appears in list
   - Check that:
     - Title is displayed (e.g., first message preview)
     - Message preview shows content
     - Timestamp shows "just now" or recently

3. **Load Conversation:**
   - Click on the conversation in the modal
   - Modal closes
   - Messages appear in chat (both user and assistant)
   - Verify chronological order

### Test 2: Multiple Conversations

1. **Create in Reflection mode:**
   - Switch to Reflection mode
   - Send: "I feel overwhelmed about work"
   - Send: "What should I do?"
   - Note conversation appears

2. **Switch to Mirror mode:**
   - Click mode toggle to Mirror
   - Send: "yo I'm hyped!"
   - New conversation created
   - Note two conversations in history

3. **Filter by mode:**
   - In History modal, verify both show
   - (Mode filtering can be enhanced if needed)

### Test 3: Empty State

1. **Logout and login with new user**
2. **Open History**
3. **Verify "No conversations yet" message**
4. **Send a message**
5. **Open History again**
6. **Verify conversation now appears**

### Test 4: Auto-Refresh

1. **Keep History modal open**
2. **Send a new message in chat**
3. **Verify conversation refreshes in modal**
4. **Don't need to close/reopen modal**

### Test 5: Message Consistency

1. **Load a past conversation**
2. **Count messages (should be: user messages + assistant messages)**
3. **Verify no duplicates**
4. **Verify roles are correct (user/assistant)**

### Test 6: Database Verification

```bash
# SSH into database
cd /workspaces/reflectra/backend
python test_conversations.py
```

Output should show:
- Total users and conversations
- Message counts
- Recent messages in chronological order

---

## Troubleshooting

### Problem: "No conversations yet" but user sent messages

**Possible Causes:**
1. User ID mismatch between frontend and backend
2. RLS policy blocking access
3. Messages not persisted to database
4. Wrong conversation_id in URL

**Debug Steps:**
```
1. Check browser console for user_id:
   localStorage.getItem("user_id")

2. Check API responses:
   - Network tab → /conversations request
   - Response should show conversation_id
   - Check response status and error message

3. Check backend logs:
   - Look for "Creating new conversation"
   - Look for "Stored user message"
   - Look for "Stored assistant message"

4. Verify database:
   python test_conversations.py
   - Should show conversations and messages
```

### Problem: Message previews not showing

**Possible Causes:**
1. Messages fetch failed silently
2. First message is assistant message (expected)
3. Message content is empty

**Debug Steps:**
```
1. Check browser console:
   - Look for errors in usePastConversations hook
   - Network tab → /conversations/{id}/messages requests

2. Verify response structure:
   - Each message should have: id, role, content, created_at

3. Check backend:
   - Verify get_conversation_history() returns messages
```

### Problem: Timestamp always shows current time

**Possible Causes:**
1. `created_at` from backend is incorrect
2. Browser timezone issue
3. `formatDistanceToNow` not working

**Debug Steps:**
```
1. Check API response created_at:
   - Should be ISO 8601 format
   - Should be past time, not current

2. Check browser timezone:
   new Date().getTimezoneOffset()

3. Verify date-fns installation:
   npm ls date-fns
```

### Problem: Can't load conversations (401/403 error)

**Possible Causes:**
1. User not authenticated
2. RLS policy blocking access
3. user_id not in request

**Debug Steps:**
```
1. Check authentication:
   - localStorage.getItem("user_id") should exist
   - Should be valid UUID format

2. Check RLS policies:
   - Are they enabled?
   - Do they filter by auth.uid()?

3. Check backend logs:
   - Look for "Invalid UUID format"
   - Look for "Conversation not found"
   - Look for RLS denial errors
```

---

## Performance Considerations

1. **Message Preview Fetching:**
   - Currently fetches full message list for each conversation
   - For 100+ conversations, consider:
     - Caching message previews in conversations table
     - Using pagination
     - Lazy-loading previews on scroll

2. **Timestamp Calculations:**
   - `formatDistanceToNow` is fast for recent dates
   - Consider memoization for 100+ conversations

3. **Database Queries:**
   - Indexes on (user_id, created_at DESC) optimize list fetches
   - Indexes on (conversation_id, created_at ASC) optimize history fetches

---

## Security Checklist

- [x] User can only see their own conversations (user_id filter)
- [x] User can only see their own messages (user_id filter + RLS)
- [x] conversation_id is UUID (not sequential/guessable)
- [x] User_id validated in backend before returning data
- [x] RLS policies enabled on database tables
- [x] No sensitive data in message previews

---

## Future Enhancements

1. **Search Past Conversations:**
   - Search by title or message content
   - Filter by date range
   - Filter by mode

2. **Conversation Metadata:**
   - Add tags/labels to conversations
   - Pin favorite conversations
   - Archive old conversations

3. **Export Conversations:**
   - Export to PDF or JSON
   - Copy conversation link
   - Share conversations (with RLS)

4. **Real-time Sync:**
   - WebSocket for live updates
   - Multi-device sync
   - Notification when conversations are accessed

---

## File Structure

```
frontend/
├── src/
│   ├── hooks/
│   │   └── usePastConversations.ts       (New: conversation fetch hook)
│   ├── utils/
│   │   └── conversationRefresh.ts        (New: pub/sub refresh system)
│   ├── components/
│   │   └── chat/
│   │       └── ConversationHistoryModal.tsx  (Enhanced: with previews + refresh)
│   ├── pages/
│   │   └── ChatPage.tsx                  (Enhanced: triggers refresh)
│   └── contexts/
│       └── ChatContext.tsx               (Unchanged: loads messages by ID)
│
backend/
├── app/
│   ├── api/
│   │   └── chat.py
│   │       ├── GET /conversations         (List with user isolation)
│   │       └── GET /conversations/{id}/messages  (Load with user validation)
│   ├── db/
│   │   ├── models.py                     (Conversation & Message schemas)
│   │   └── crud.py
│   │       ├── get_user_conversations()
│   │       ├── get_conversation_by_id()
│   │       └── get_conversation_history()
│   └── alembic/versions/
│       └── 0001_init_schema.py           (Database migrations)
```

---

## Version History

- **v1.0** (March 27, 2026): Initial implementation
  - Past conversations list with previews
  - Auto-refresh on new conversation creation
  - Message preview with relative timestamps
  - Session ID (conversation_id) handling
  - User isolation and RLS policies
