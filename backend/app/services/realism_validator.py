import re
from typing import Dict, List

def score_mirror_candidate(candidate: str, sampled_profile: Dict, recent_outputs: List[str]) -> float:
    """
    Score a generated mirror response against the sampled behavioral profile and recent outputs.
    Returns a score between 0.0 and 1.0 (1.0 being perfect realism).
    """
    score = 1.0
    lower_candidate = candidate.lower()
    
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

    # 4. AI-isms (Therapy/Helpful filler)
    ai_isms = ["it sounds like", "maybe you should", "have you considered", "i understand that", "as an ai", "i'm here to help"]
    for marker in ai_isms:
        if marker in lower_candidate:
            score -= 0.6
            
    return max(0.0, score)