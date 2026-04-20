# Persona System

## Summary
Dynamic personality modeling with snapshot-driven mirror response generation.

## Layers
- constants: trait taxonomy and tuning values
- repository: persona persistence and retrieval
- services: trait extraction, updates, snapshots, mirroring
- api: persona and mirror endpoints

## Important Behaviors
- Trait updates use weighted moving averages and confidence bounds.
- Snapshot stability index summarizes confidence maturity.
- Mirror system adapts style using snapshot certainty.
- User data remains isolated by user_id.

## Runtime Notes
- Cache latest snapshots for faster mirror generation.
- Invalidate cache when trait updates regenerate snapshots.
- Keep extraction/update paths conservative for drift control.
