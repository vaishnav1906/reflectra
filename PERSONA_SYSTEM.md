# Dynamic Personality Modeling + Mirror Engine System

A production-grade personality modeling system using FastAPI, async SQLAlchemy, and Supabase/PostgreSQL.

## 🏗️ Architecture

### Clean Separation of Concerns

```
backend/app/
├── constants.py                 # Trait taxonomy and configuration
├── db/
│   ├── models.py               # SQLAlchemy models
│   └── database.py             # DB connection
├── repository/
│   └── persona_repository.py   # Data access layer
├── services/
│   ├── trait_extraction_service.py      # LLM-based trait extraction
│   ├── persona_update_service.py        # Weighted moving average updates
│   ├── snapshot_service.py              # Snapshot generation
│   └── mirror_engine.py                 # Personalized response generation
└── api/
    ├── persona.py              # Reflection endpoints
    └── mirror.py               # Mirror chat endpoints
```

## 📊 Database Models

### UserPersonaMetric

Stores individual trait measurements with confidence tracking.

```python
{
    "id": UUID,
    "user_id": UUID,
    "trait_name": str,           # From TRAIT_LIST
    "score": float,              # 0.0 to 1.0
    "confidence": float,         # 0.0 to 1.0
    "evidence_count": int,       # Number of observations
    "last_signal": float,        # Most recent signal
    "last_updated": datetime
}
```

**Unique constraint:** (user_id, trait_name)

### PersonaSnapshot

Stores periodic snapshots of complete personality profile.

```python
{
    "id": UUID,
    "user_id": UUID,
    "persona_vector": {          # Grouped traits
        "emotional_profile": {...},
        "cognitive_profile": {...},
        "communication_profile": {...},
        "motivational_profile": {...}
    },
    "stability_index": float,    # 0.0 to 1.0
    "summary_text": str,         # Human-readable summary
    "created_at": datetime
}
```

## 🎯 Trait Taxonomy

15 core personality dimensions:

**Emotional Profile:**
- emotional_intensity
- anxiety_level
- optimism_level
- emotional_stability

**Cognitive Profile:**
- analytical_thinking
- overthinking_tendency
- decision_confidence

**Communication Profile:**
- directness
- formality
- expressiveness

**Motivational Profile:**
- achievement_drive
- validation_seeking
- avoidance_pattern
- growth_orientation
- self_criticism

All traits initialized at:
- score = 0.5 (neutral)
- confidence = 0.1 (uncertain)

## 🔄 Trait Update Algorithm

### Weighted Moving Average

```python
new_score = (old_score * old_confidence + signal * strength) / (old_confidence + strength)
```

### Directional Confidence Logic

**Same Direction (reinforcement):**
```python
new_confidence = min(1.0, old_confidence + 0.05 * strength)
```

**Opposite Direction (conflict):**
```python
new_confidence = max(0.05, old_confidence - 0.03 * strength)
```

### Drift Prevention (every 20 evidence updates)

1. Remove traits with `confidence < 0.1` AND `evidence_count < 3`
2. Clamp scores to `[0.05, 0.95]`
3. Detect oscillation (future enhancement)

## 📸 Snapshot Generation

### Stability Index

```python
stability_index = average(confidence across all traits)
```

**Interpretation:**
- < 0.3: Unstable (emerging profile)
- 0.3 - 0.7: Developing
- > 0.7: Stable (well-established)

### Summary Generation

Deterministic text generation:
1. Identify top 3 highest-scoring traits
2. Identify low-confidence (unstable) traits
3. Build structured descriptive paragraph

Example:
```
"This is a well-established personality profile. Key characteristics include 
very high analytical thinking, high decision confidence, and moderate directness. 
The profile shows variability in emotional intensity and validation seeking."
```

## 🪞 Mirror Engine

### System Prompt Construction

```python
User Personality Baseline:
- Emotional Intensity: High (0.73)
- Analytical Thinking: Very High (0.85)
- Decision Confidence: Moderate (0.58)
- Directness: High (0.71)
- Expressiveness: Low (0.34)

Stability Index: 0.68

Rules:
- Match sentence rhythm and structure
- Match cognitive style (analytical vs intuitive)
- Match emotional intensity level
- Stay within stored personality bounds
- Stability > 0.7 → mirror strongly
- Stability < 0.3 → mirror lightly
```

### Adaptive Mirroring

- **High Stability (> 0.7):** Strong mirroring with confident adjustments
- **Medium Stability (0.3 - 0.7):** Moderate mirroring
- **Low Stability (< 0.3):** Light mirroring, baseline responses

## 🚀 API Endpoints

### POST /persona/reflection

Process a reflection message to update personality traits.

**Request:**
```json
{
  "user_id": "uuid",
  "message": "I'm really worried about this decision..."
}
```

**Response:**
```json
{
  "success": true,
  "traits_extracted": 4,
  "traits_updated": 4,
  "stability_index": 0.456,
  "snapshot_id": "uuid",
  "summary": "This is a developing personality profile..."
}
```

### GET /persona/profile/{user_id}

Get latest personality profile.

**Response:**
```json
{
  "snapshot_id": "uuid",
  "user_id": "uuid",
  "persona_vector": {...},
  "stability_index": 0.456,
  "summary": "...",
  "created_at": "2026-02-20T..."
}
```

### GET /persona/metrics/{user_id}

Get all trait metrics for a user.

**Response:**
```json
{
  "user_id": "uuid",
  "metrics": [
    {
      "trait_name": "analytical_thinking",
      "score": 0.732,
      "confidence": 0.654,
      "evidence_count": 12,
      "last_signal": 0.8,
      "last_updated": "2026-02-20T..."
    },
    ...
  ]
}
```

### POST /mirror/chat

Generate mirror response based on personality profile.

**Request:**
```json
{
  "user_id": "uuid",
  "message": "What should I do about this situation?"
}
```

**Response:**
```json
{
  "success": true,
  "response": "Let's analyze this systematically...",
  "mirroring_active": true
}
```

## 🔧 Performance Optimizations

### Snapshot Caching

```python
# In-memory cache of latest snapshots
_snapshot_cache: Dict[str, Dict] = {}

# Invalidated after trait updates
invalidate_snapshot_cache(user_id)
```

### Lazy Initialization

Traits are initialized on first reflection:
```python
await PersonaRepository.initialize_missing_traits(db, user_id)
```

### Batch Operations

All trait updates committed in single transaction:
```python
async with db.begin():
    for trait in extracted_traits:
        await update_trait(...)
```

## 🛡️ Error Handling

### LLM Failures

```python
# Graceful degradation
if not MISTRAL_AVAILABLE:
    return []  # Empty trait list
```

### JSON Validation

```python
# Strict validation of LLM output
- Validate trait names against TRAIT_LIST
- Clamp signal/strength to [0.0, 1.0]
- Reject malformed JSON
```

### Database Isolation

```python
# Each user's data is isolated
WHERE user_id = ?

# Unique constraints prevent duplicates
UNIQUE(user_id, trait_name)
```

## 🗃️ Database Migration

Apply migration to create persona tables:

```bash
cd backend
alembic upgrade head
```

This creates:
- `user_persona_metrics` table
- `persona_snapshots` table
- Necessary indexes and constraints

## 📝 Example Usage

```python
from app.services.trait_extraction_service import extract_traits
from app.services.persona_update_service import update_traits
from app.services.snapshot_service import generate_persona_snapshot
from app.services.mirror_engine import generate_mirror_response

# 1. Extract traits from message
traits = await extract_traits("I'm so anxious about this decision...")

# 2. Update user's trait metrics
result = await update_traits(db, user_id, traits)
print(f"Stability: {result['stability_index']}")

# 3. Generate snapshot
snapshot = await generate_persona_snapshot(db, user_id)
print(snapshot.summary_text)

# 4. Generate mirror response
response = await generate_mirror_response(db, user_id, "What should I do?")
print(response)
```

## 🧪 Testing

Run the example demo:

```bash
cd backend
python example_persona_usage.py
```

This demonstrates:
- Trait extraction from multiple messages
- Incremental trait updates
- Snapshot generation
- Mirror response generation

## 🔐 Multi-User Support

The system is fully multi-user aware:

- All operations scoped by `user_id`
- Database constraints ensure isolation
- No cross-user data leakage
- Concurrent updates handled safely

## 📊 Monitoring

Key metrics to track:

- **Stability Index**: Overall profile confidence
- **Evidence Count**: Number of observations per trait
- **Confidence Distribution**: Health of trait measurements
- **Snapshot Frequency**: How often profiles are updated

## 🔮 Future Enhancements

- Oscillation detection and smoothing
- Trait correlation analysis
- Temporal pattern recognition
- Multi-modal trait extraction (voice, image)
- Federated learning for privacy

## 📄 License

Part of the Reflectra project.
