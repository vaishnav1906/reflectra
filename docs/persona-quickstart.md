# Persona Quickstart

## Setup
1. Create and activate the project virtual environment at repo root.
2. Install backend requirements.
3. Run migrations.

## Key Endpoints
- POST /persona/reflection
- GET /persona/profile/{user_id}
- GET /persona/metrics/{user_id}
- POST /mirror/chat

## Core Flow
1. Reflection messages extract trait signals.
2. Trait metrics update with weighted logic.
3. Persona snapshots regenerate with stability index.
4. Mirror responses consume the latest persona snapshot.

For complete architecture, see persona-system.md.
