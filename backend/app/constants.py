"""Constants for personality modeling."""

# Trait taxonomy for gradual behavioral trait shifting
# These 4 core traits map to observable behavioral patterns
TRAIT_LIST = [
    "communication_style",      # 0 = concise, 1 = verbose
    "emotional_expressiveness", # 0 = reserved, 1 = expressive
    "decision_framing",         # 0 = hesitant, 1 = decisive
    "reflection_depth",         # 0 = surface, 1 = deep
]

# Trait metadata for AI extraction
TRAIT_DEFINITIONS = {
    "communication_style": {
        "description": "Message length and detail level",
        "low_indicator": "short, direct messages with minimal elaboration",
        "high_indicator": "long, detailed messages with extensive explanation",
    },
    "emotional_expressiveness": {
        "description": "Emotional openness and expression",
        "low_indicator": "reserved, matter-of-fact, emotionally neutral language",
        "high_indicator": "emotionally expressive, uses feeling words, shares emotional states",
    },
    "decision_framing": {
        "description": "Certainty and decisiveness in statements",
        "low_indicator": "uncertain, hesitant, uses qualifiers like 'maybe', 'I think', 'possibly'",
        "high_indicator": "decisive, confident, declarative statements, clear positions",
    },
    "reflection_depth": {
        "description": "Level of introspection and analysis",
        "low_indicator": "surface-level observations, simple statements, minimal self-analysis",
        "high_indicator": "deep introspection, explores meaning and patterns, meta-cognitive awareness",
    },
}

# Default values for new traits
DEFAULT_TRAIT_SCORE = 0.5
DEFAULT_TRAIT_CONFIDENCE = 0.1

# Stability thresholds
STABILITY_THRESHOLD_UNSTABLE = 0.3
STABILITY_THRESHOLD_STABLE = 0.7

# Gradual update parameters - designed for slow convergence
MAX_STRENGTH_PER_MESSAGE = 0.2  # Maximum strength allowed per message (prevents dramatic shifts)
CONFIDENCE_INCREASE_RATE = 0.03  # How much confidence increases when signal aligns
CONFIDENCE_DECREASE_RATE = 0.02  # How much confidence decreases when signal conflicts
MIN_CONFIDENCE = 0.05
MAX_CONFIDENCE = 1.0

# Drift prevention - smoothing to prevent locking at extremes
EVIDENCE_COUNT_FOR_DRIFT_CHECK = 10  # Check every 10 updates
DRIFT_SMOOTHING_FACTOR = 0.98  # Gentle pull towards center (score * 0.98 + 0.01)
MIN_EVIDENCE_FOR_RETENTION = 3
LOW_CONFIDENCE_THRESHOLD = 0.1
EXTREME_SCORE_MIN = 0.05
EXTREME_SCORE_MAX = 0.95

# Trait groupings for snapshot (4-trait system)
TRAIT_GROUPS = {
    "behavioral_profile": [
        "communication_style",
        "emotional_expressiveness",
        "decision_framing",
        "reflection_depth",
    ],
}
