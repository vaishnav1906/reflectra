# Architecture Fix

This document is the canonical summary for the chat-state and routing architecture fixes.

## Core Outcomes
- Chat state persistence across route changes via context-level state.
- URL-driven conversation loading and new-conversation behavior.
- Strict reflection vs mirror mode behavior separation.
- Dynamic personality page values from backend instead of hardcoded values.

## Frontend Areas
- Chat context provider wrapped around app routes.
- Chat page refactored to consume shared context state.
- Personality page mapped to backend persona data.

## Backend Areas
- Reflection mode updates persona traits and regenerates snapshots.
- Mirror mode reads persona snapshots and responds without mutating traits.

## Verification
- Route navigation retains conversation state.
- Mode switching starts new sessions cleanly.
- Reflection messages impact persona metrics.
- Mirror messages use profile without direct trait mutation.
