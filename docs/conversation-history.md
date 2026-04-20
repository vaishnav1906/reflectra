# Conversation History

Canonical documentation for conversation history behavior and troubleshooting.

## Feature Scope
- Fetch and list user conversations in reverse-chronological order.
- Open a selected conversation and load message history.
- Show conversation previews and timestamps.
- Refresh list when new conversations are created.

## Backend Endpoints
- GET /conversations?user_id={id}&mode={optional}
- GET /conversations/{conversation_id}/messages?user_id={id}

## Debugging Checklist
1. Confirm user_id exists in local storage and is valid.
2. Verify backend health endpoint responds.
3. Validate /conversations request returns user data.
4. Validate selected conversation message endpoint returns messages.
5. Confirm user isolation by user_id filters.

## Operational Notes
- Conversation and message storage is database-backed.
- History UI opens from chat navigation interactions.
- Root-level ad-hoc scripts moved to scripts and tests directories.
