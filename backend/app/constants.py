"""Constants for personality modeling."""

# Feature Flags
ENABLE_MIRROR_MODE = True

# Mirror mode trait controls
MIRROR_CORE_TRAITS = [
    "communication_style",
    "emotional_expressiveness",
    "decision_framing",
    "reflection_depth",
]

MIRROR_DEFAULT_TRAIT_SCORES = {
    "communication_style": 0.5,
    "emotional_expressiveness": 0.5,
    "decision_framing": 0.5,
    "reflection_depth": 0.5,
}

MIRROR_MIN_CONFIDENCE_FOR_TRAIT = 0.2

MIRROR_GENERIC_FILLERS = {
    "hmm",
    "ok",
    "okay",
    "k",
    "idk",
    "sure",
    "same",
    "nah",
    "yeah",
    "sup",
}

MIRROR_HEDGING_MARKERS = {
    "maybe",
    "i think",
    "probably",
    "possibly",
    "might",
    "not sure",
    "i guess",
    "sort of",
    "kind of",
}

MIRROR_DECISIVE_MARKERS = {
    "definitely",
    "for sure",
    "will",
    "must",
    "clearly",
    "the answer is",
    "do this",
}

MIRROR_DEPTH_MARKERS = {
    "because",
    "pattern",
    "cycle",
    "underneath",
    "root",
    "meaning",
    "why",
    "loop",
}

MIRROR_MIN_TOPIC_OVERLAP = 0.12

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

# Score update: new = old + alpha * (signal - old), with
#   alpha = strength * (1 - SCORE_INERTIA * confidence)
# so one message moves a trait at most 20% of the way toward its signal, and
# well-established traits (high confidence) move even less.
SCORE_INERTIA = 0.8

# Confidence update (saturating, so it approaches but never jumps to the bounds):
#   aligned signal     -> confidence += CONFIDENCE_INCREASE_RATE * strength * (1 - confidence)
#   conflicting signal -> confidence -= CONFIDENCE_DECREASE_RATE * strength * confidence
# With typical strengths (~0.12-0.18) about 30 consistent messages take a trait
# from the 0.1 default to ~0.6 ("developing" -> close to "stable").
CONFIDENCE_INCREASE_RATE = 0.25
CONFIDENCE_DECREASE_RATE = 0.30
ALIGNMENT_DISTANCE = 0.2  # |signal - score| below this reinforces the current score
CONFLICT_DISTANCE = 0.35  # |signal - score| above this counts as contradicting evidence
MIN_CONFIDENCE = 0.05
MAX_CONFIDENCE = 0.98

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
