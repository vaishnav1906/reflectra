# Persona System - Quick Start Guide

## ✅ What Was Implemented

A complete production-grade Dynamic Personality Modeling + Mirror Engine system with:

### 1. Database Layer ✓
- **UserPersonaMetric** model - Stores individual trait measurements
- **PersonaSnapshot** model - Stores complete personality profiles
- Alembic migration (`0002_add_persona_tables.py`)

### 2. Repository Layer ✓
- `persona_repository.py` - Clean data access layer
- Async operations for all CRUD
- Trait initialization and management
- Snapshot creation and retrieval

### 3. Services Layer ✓

**trait_extraction_service.py:**
- LLM-based trait extraction
- Strict JSON validation
- Trait name and value validation

**persona_update_service.py:**
- Weighted moving average algorithm
- Directional confidence logic
- Drift prevention every 20 updates

**snapshot_service.py:**
- Grouped trait vectors
- Stability index computation
- Deterministic summary generation

**mirror_engine.py:**
- Personality-based response generation
- Adaptive mirroring intensity
- Snapshot caching

### 4. API Routes ✓

**persona.py:**
- `POST /persona/reflection` - Process reflections
- `GET /persona/profile/{user_id}` - Get personality profile
- `GET /persona/metrics/{user_id}` - Get trait metrics

**mirror.py:**
- `POST /mirror/chat` - Generate mirror responses

### 5. Configuration ✓
- `constants.py` - 15 trait taxonomy
- All thresholds and parameters
- Trait groupings for snapshots

## 🚀 How to Use

### 1. Apply Database Migration

```bash
cd backend
alembic upgrade head
```

This creates the `user_persona_metrics` and `persona_snapshots` tables.

### 2. Test the API

**Process a reflection:**
```bash
curl -X POST http://localhost:8000/persona/reflection \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your-user-uuid",
    "message": "I'm really worried about this project and keep second-guessing myself."
  }'
```

**Get personality profile:**
```bash
curl http://localhost:8000/persona/profile/your-user-uuid
```

**Generate mirror response:**
```bash
curl -X POST http://localhost:8000/mirror/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your-user-uuid",
    "message": "What should I focus on?"
  }'
```

### 3. Run Example Demo

```bash
cd backend
python example_persona_usage.py
```

This shows the complete flow with test data.

## 📋 API Flow

### Reflection Flow
```
User Message
    ↓
extract_traits() → Extract personality signals
    ↓
update_traits() → Update metrics with weighted average
    ↓
generate_snapshot() → Create profile snapshot
    ↓
Return: traits_updated, stability_index, summary
```

### Mirror Flow
```
User Message
    ↓
get_cached_snapshot() → Get latest personality profile
    ↓
build_mirror_system_prompt() → Inject personality baseline
    ↓
generate_mirror_response() → LLM generates personalized response
    ↓
Return: Mirrored response
```

## 🎯 Key Features

### Weighted Moving Average
```python
new_score = (old_score * old_confidence + signal * strength) 
            / (old_confidence + strength)
```

### Confidence Tracking
- Increases when signals reinforce existing patterns
- Decreases when signals conflict
- Ensures stable convergence

### Drift Prevention
- Removes low-confidence, low-evidence traits
- Clamps extreme scores
- Prevents profile instability

### Adaptive Mirroring
- **High stability (>0.7):** Strong mirroring
- **Medium stability (0.3-0.7):** Moderate mirroring  
- **Low stability (<0.3):** Light mirroring

## 🛠️ Architecture Highlights

✅ **Async everywhere** - All DB operations and LLM calls are async
✅ **Clean separation** - Repository → Service → API layers
✅ **Multi-user isolation** - User-scoped queries and unique constraints
✅ **Error handling** - Graceful degradation when LLM unavailable
✅ **Caching** - Snapshot caching for performance
✅ **Validation** - Strict validation of LLM outputs

## 📊 Trait Taxonomy

15 traits across 4 dimensions:

1. **Emotional**: intensity, anxiety, optimism, stability
2. **Cognitive**: analytical, overthinking, decision_confidence
3. **Communication**: directness, formality, expressiveness
4. **Motivational**: achievement, validation_seeking, avoidance, growth, self_criticism

## 🔍 Example Output

```json
{
  "success": true,
  "traits_extracted": 4,
  "traits_updated": 4,
  "stability_index": 0.456,
  "snapshot_id": "...",
  "summary": "This is a developing personality profile. Key characteristics include high analytical thinking, moderate decision confidence, and high anxiety level."
}
```

## 📝 Next Steps

1. **Apply migration** - `alembic upgrade head`
2. **Test endpoints** - Use curl or Postman
3. **Integrate with existing chat** - Call persona endpoints from chat flow
4. **Monitor stability** - Track how profiles develop over time
5. **Tune parameters** - Adjust confidence rates in `constants.py`

## 📚 Documentation

See [PERSONA_SYSTEM.md](PERSONA_SYSTEM.md) for complete documentation.

## ✨ Production Ready

- No placeholders
- No pseudo-code
- Full async implementation
- Clean modular architecture
- Proper error handling
- Database migrations included
- Example code provided
