import re
from typing import Dict, List

from app.constants import (
    MIRROR_DECISIVE_MARKERS,
    MIRROR_DEPTH_MARKERS,
    MIRROR_GENERIC_FILLERS,
    MIRROR_HEDGING_MARKERS,
    MIRROR_MIN_TOPIC_OVERLAP,
)


def _tokenize_content_words(text: str) -> set[str]:
    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "just",
        "have",
        "your",
        "you",
        "are",
        "was",
        "were",
        "about",
        "into",
        "they",
        "them",
        "what",
        "when",
        "where",
        "will",
        "would",
        "could",
        "should",
    }
    words = re.findall(r"[a-zA-Z']+", (text or "").lower())
    return {word for word in words if len(word) > 3 and word not in stop_words}


def score_mirror_candidate(
    candidate: str,
    sampled_profile: Dict,
    recent_outputs: List[str],
    source_message: str = "",
    task_execution_mode: bool = False,
) -> float:
    """
    Score a generated mirror response against the sampled behavioral profile and recent outputs.
    Returns a score between 0.0 and 1.0 (1.0 being perfect realism).
    """
    score = 1.0
    lower_candidate = candidate.lower()
    candidate_words = re.findall(r"[a-zA-Z']+", lower_candidate)
    candidate_word_count = len(candidate_words)
    
    # 1. Anti-Repetition
    for recent in recent_outputs[-3:]:
        if len(recent) > 3 and (recent.lower() == lower_candidate or recent.lower() in lower_candidate):
            score -= 0.5
            
    # 2. Structure Density
    structure_pref = sampled_profile.get("structure_preference", "loose")
    if structure_pref == "loose":
        if re.search(r'^\s*[-*]\s', candidate, re.MULTILINE):
            score -= 0.3
        if "1." in candidate or "2." in candidate:
            score -= 0.2

    # 3. Reasoning Depth
    reasoning_vis = sampled_profile.get("reasoning_visibility", "low")
    if reasoning_vis == "low":
        explanation_markers = ["because", "therefore", "which means", "the reason is", "so basically"]
        # Softer penalty and higher tolerance for conversational responses
        count = sum(1 for marker in explanation_markers if marker in lower_candidate)
        if count > 1:
            score -= 0.1
    else:
        if candidate_word_count > 10:
            depth_markers_found = sum(1 for marker in MIRROR_DEPTH_MARKERS if marker in lower_candidate)
            if depth_markers_found == 0:
                score -= 0.08

    # 4. Four-trait behavioral alignment
    communication_style = float(sampled_profile.get("communication_style", 0.5))
    emotional_expressiveness = float(sampled_profile.get("emotional_expressiveness", 0.5))
    decision_framing = float(sampled_profile.get("decision_framing", 0.5))
    reflection_depth = float(sampled_profile.get("reflection_depth", 0.5))

    if communication_style < 0.35 and candidate_word_count > 70:
        score -= 0.12
    if communication_style > 0.68 and candidate_word_count < 10:
        score -= 0.14

    hedging_hits = sum(1 for marker in MIRROR_HEDGING_MARKERS if marker in lower_candidate)
    decisive_hits = sum(1 for marker in MIRROR_DECISIVE_MARKERS if marker in lower_candidate)
    if decision_framing > 0.68 and hedging_hits > 0:
        score -= 0.16
    if decision_framing < 0.35 and decisive_hits > 1:
        score -= 0.14

    emotional_words = {
        "love",
        "hate",
        "happy",
        "sad",
        "angry",
        "stressed",
        "excited",
        "overwhelmed",
        "frustrated",
    }
    emotional_hits = sum(1 for word in emotional_words if word in lower_candidate)
    expressive_punctuation = candidate.count("!") + candidate.count("?")
    if emotional_expressiveness < 0.35 and (emotional_hits >= 2 or expressive_punctuation >= 3):
        score -= 0.12
    if emotional_expressiveness > 0.68 and emotional_hits == 0 and expressive_punctuation == 0 and candidate_word_count > 10:
        score -= 0.06

    depth_hits = sum(1 for marker in MIRROR_DEPTH_MARKERS if marker in lower_candidate)
    if reflection_depth < 0.35 and depth_hits >= 3:
        score -= 0.12
    if reflection_depth > 0.68 and candidate_word_count > 12 and depth_hits == 0:
        score -= 0.08

    # 5. AI-isms (Therapy/Helpful filler)
    ai_isms = ["it sounds like", "maybe you should", "have you considered", "i understand that", "as an ai", "i'm here to help"]
    for marker in ai_isms:
        if marker in lower_candidate:
            score -= 0.6

    # 6. Generic filler penalties
    if lower_candidate.strip() in MIRROR_GENERIC_FILLERS:
        score -= 0.6
    generic_phrases = {
        "let me know",
        "hope this helps",
        "anything else",
        "i can help with that",
        "feel free to ask",
    }
    if any(phrase in lower_candidate for phrase in generic_phrases):
        score -= 0.18

    # 7. Mode-specific contract penalties
    if task_execution_mode:
        if re.search(r"^(here is|here's|i will|i'll|let me)\b", lower_candidate):
            score -= 0.24
        if "here is a draft" in lower_candidate or "here's a draft" in lower_candidate:
            score -= 0.35
        if source_message and re.sub(r"\s+", " ", source_message.strip().lower()) == re.sub(r"\s+", " ", candidate.strip().lower()):
            score -= 0.4
    else:
        source_has_question = "?" in (source_message or "")
        if "??" in candidate:
            score -= 0.25
        elif "?" in candidate and not source_has_question:
            score -= 0.08

        if re.search(r"^(can|could|would|do)\s+you\b", lower_candidate):
            score -= 0.3

        if re.search(r"\b(you|your|yours|u)\b", lower_candidate):
            score -= 0.25

        if not re.search(r"\b(i|i'm|im|i've|i'd|i'll|my|me|myself)\b", lower_candidate):
            score -= 0.18

        if re.search(r"\b(option|alternatively|on the other hand|either|or maybe|could also)\b", lower_candidate):
            score -= 0.14

    # 8. Topical continuity check
    if source_message:
        source_tokens = _tokenize_content_words(source_message)
        if source_tokens:
            candidate_tokens = _tokenize_content_words(candidate)
            overlap = len(source_tokens & candidate_tokens)
            overlap_ratio = overlap / max(len(source_tokens), 1)
            if overlap == 0:
                score -= 0.22
            elif overlap_ratio < MIRROR_MIN_TOPIC_OVERLAP:
                score -= 0.1
            
    return max(0.0, score)