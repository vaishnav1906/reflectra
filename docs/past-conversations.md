# Past Conversations

Implementation reference for the past conversations experience.

## User Capabilities
- View previous sessions sorted by most recent.
- Load any prior conversation.
- See message previews and relative timestamps.
- Refresh list when new conversations appear.

## Architecture
- Frontend hook gathers conversation list and lightweight preview data.
- Modal UI renders list, loading, and error states.
- Backend enforces user isolation and returns ordered records.

## Data Model Expectations
- Conversations table keyed by UUID.
- Messages table linked by conversation_id.
- Queries scoped by user_id.

## Testing
- Create conversations in both reflection and mirror mode.
- Verify list ordering and preview text.
- Verify loading a conversation restores message timeline.
- Verify users cannot access another user’s conversation.
