"""Trait extraction service using LLM for behavioral nudge detection."""

import json
import logging
import os
from typing import Dict, List

from app.constants import TRAIT_LIST, TRAIT_DEFINITIONS, MAX_STRENGTH_PER_MESSAGE

logger = logging.getLogger(__name__)

# Initialize Mistral client
MISTRAL_AVAILABLE = False
mistral_client = None

try:
    from mistralai import Mistral
    api_key = os.getenv("MISTRAL_API_KEY")
    if api_key:
        mistral_client = Mistral(api_key=api_key)
        MISTRAL_AVAILABLE = True
        logger.info("✅ Mistral client initialized for trait extraction")
except Exception as e:
    logger.warning(f"⚠️ Mistral not available for trait extraction: {e}")


# Build trait definitions for prompt
TRAIT_DESCRIPTIONS = "\n".join([
    f"- **{trait}**: {TRAIT_DEFINITIONS[trait]['description']}\n"
    f"  Low (0.0-0.3): {TRAIT_DEFINITIONS[trait]['low_indicator']}\n"
    f"  High (0.7-1.0): {TRAIT_DEFINITIONS[trait]['high_indicator']}"
    for trait in TRAIT_LIST
])

NUDGE_EXTRACTION_PROMPT = f"""You are a behavioral trait analyzer for a gradual personality modeling system.

Analyze the user's message and detect ONLY clearly observable behavioral signals.

**Available Traits:**
{TRAIT_DESCRIPTIONS}

**Your Task:**
For each trait that is CLEARLY demonstrated in this specific message:
- Determine the **signal**: the target trait value based on this message (0.0 to 1.0)
- Determine the **strength**: how confident you are in this observation (0.0 to 0.2 max)

**Critical Rules:**
1. NEVER set strength > 0.2 (prevents dramatic shifts)
2. ONLY include traits with clear evidence in this message
3. If unsure, omit the trait entirely
4. Be conservative - single messages should nudge gradually
5. signal represents the trait level (0.0 = low extreme, 1.0 = high extreme, 0.5 = neutral)
6. strength represents observation confidence (higher = stronger evidence)

**Examples:**

Message: "idk maybe"
→ {{"nudges": [{{"trait": "communication_style", "signal": 0.2, "strength": 0.12}}, {{"trait": "decision_framing", "signal": 0.15, "strength": 0.15}}]}}

Message: "I've been thinking deeply about why I keep avoiding difficult conversations. There's a pattern here - every time conflict emerges, I intellectualize it rather than addressing it directly. I think this stems from..."
→ {{"nudges": [{{"trait": "communication_style", "signal": 0.85, "strength": 0.18}}, {{"trait": "reflection_depth", "signal": 0.9, "strength": 0.2}}, {{"trait": "emotional_expressiveness", "signal": 0.6, "strength": 0.1}}]}}

Message: "yes"
→ {{"nudges": [{{"trait": "communication_style", "signal": 0.1, "strength": 0.08}}]}}

Message: "I feel completely overwhelmed and anxious about everything right now!"
→ {{"nudges": [{{"trait": "emotional_expressiveness", "signal": 0.85, "strength": 0.18}}]}}

**Output Format (JSON ONLY, no markdown):**
{{
  "nudges": [
    {{"trait": "trait_name", "signal": 0.0-1.0, "strength": 0.0-0.2}}
  ]
}}

If no clear traits are detected, return: {{"nudges": []}}
"""


async def extract_traits(message: str) -> List[Dict]:
    """
    Extract behavioral nudges from a message using LLM.
    
    Args:
        message: The user's message to analyze
        
    Returns:
        List of dicts with keys: name, signal, strength
        (Note: Returns 'name' instead of 'trait' for backward compatibility)
    """
    if not MISTRAL_AVAILABLE or not mistral_client:
        logger.warning("⚠️ Mistral not available, returning empty nudge list")
        return []
    
    try:
        logger.info(f"🔍 Extracting behavioral nudges from: '{message[:50]}...'")
        
        messages = [
            {"role": "system", "content": NUDGE_EXTRACTION_PROMPT},
            {"role": "user", "content": message}
        ]
        
        response = mistral_client.chat.complete(
            model="mistral-small-latest",
            messages=messages,
            max_tokens=400,
            temperature=0.2,  # Very low temperature for consistent extraction
        )
        
        content = response.choices[0].message.content.strip()
        logger.info(f"📥 LLM response: {content[:100]}...")
        
        # Try to extract JSON from the response
        # Sometimes LLM wraps JSON in markdown code blocks
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()
        elif "```" in content:
            json_start = content.find("```") + 3
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()
        
        # Parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON: {e}")
            logger.error(f"Content was: {content}")
            return []
        
        # Validate structure
        if not isinstance(data, dict) or "nudges" not in data:
            logger.error(f"❌ Invalid response structure (expected 'nudges' key): {data}")
            return []
        
        nudges = data.get("nudges", [])
        if not isinstance(nudges, list):
            logger.error(f"❌ nudges is not a list: {nudges}")
            return []
        
        # Validate each nudge
        validated_nudges = []
        for nudge in nudges:
            if not isinstance(nudge, dict):
                logger.warning(f"⚠️ Skipping invalid nudge (not a dict): {nudge}")
                continue
            
            trait = nudge.get("trait")
            signal = nudge.get("signal")
            strength = nudge.get("strength")
            
            # Validate trait name
            if trait not in TRAIT_LIST:
                logger.warning(f"⚠️ Skipping invalid trait name: {trait}")
                continue
            
            # Validate and clamp signal (0.0 to 1.0)
            try:
                signal = float(signal)
                signal = max(0.0, min(1.0, signal))
            except (TypeError, ValueError):
                logger.warning(f"⚠️ Invalid signal value for {trait}: {signal}")
                continue
            
            # Validate and STRICTLY CAP strength (0.0 to MAX_STRENGTH_PER_MESSAGE)
            try:
                strength = float(strength)
                strength = max(0.0, min(MAX_STRENGTH_PER_MESSAGE, strength))
                
                # Log if strength was capped
                if strength == MAX_STRENGTH_PER_MESSAGE and nudge.get("strength", 0) > MAX_STRENGTH_PER_MESSAGE:
                    logger.warning(
                        f"⚠️ Strength capped for {trait}: "
                        f"{nudge.get('strength')} → {MAX_STRENGTH_PER_MESSAGE}"
                    )
            except (TypeError, ValueError):
                logger.warning(f"⚠️ Invalid strength value for {trait}: {strength}")
                continue
            
            # Use 'name' instead of 'trait' for backward compatibility with update service
            validated_nudges.append({
                "name": trait,
                "signal": signal,
                "strength": strength,
            })
        
        if validated_nudges:
            nudge_summary = ", ".join([
                f"{n['name']}(signal={n['signal']:.2f}, strength={n['strength']:.2f})"
                for n in validated_nudges
            ])
            logger.info(f"✅ Extracted {len(validated_nudges)} valid nudges: {nudge_summary}")
        else:
            logger.info("✅ No nudges extracted from this message")
        
        return validated_nudges
        
    except Exception as e:
        logger.error(f"❌ Trait extraction error: {e}")
        logger.exception("Full traceback:")
        return []
