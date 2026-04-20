#!/usr/bin/env python3
"""Backfill BehavioralInsight rows from existing reflection conversations.

Usage:
  python backfill_behavioral_insights.py
  python backfill_behavioral_insights.py --dry-run
  python backfill_behavioral_insights.py --limit 200
"""

import argparse
import asyncio
from typing import Dict, List, Tuple

from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db.models import BehavioralInsight, Conversation, Message


def extract_words(text: str) -> List[str]:
    import re

    return re.findall(r"[a-zA-Z']+", text.lower())


def derive_fallback_traits(user_text: str) -> List[Dict[str, float]]:
    words = extract_words(user_text)
    lower_text = user_text.lower()
    word_count = len(words)

    fallback_traits: List[Dict[str, float]] = []

    comm_signal = max(0.0, min(1.0, (word_count - 4) / 24.0))
    comm_strength = min(0.16, 0.07 + (min(word_count, 40) / 500.0))
    fallback_traits.append(
        {
            "name": "communication_style",
            "signal": comm_signal,
            "strength": comm_strength,
        }
    )

    emotional_keywords = {
        "feel",
        "felt",
        "sad",
        "happy",
        "anxious",
        "worried",
        "stressed",
        "overwhelmed",
        "excited",
        "frustrated",
        "angry",
    }
    emotion_hits = sum(1 for word in words if word in emotional_keywords)
    exclamations = user_text.count("!")
    express_signal = max(0.0, min(1.0, 0.25 + (emotion_hits * 0.15) + (exclamations * 0.08)))
    if emotion_hits > 0 or exclamations > 0:
        fallback_traits.append(
            {
                "name": "emotional_expressiveness",
                "signal": express_signal,
                "strength": min(0.18, 0.08 + (emotion_hits * 0.02) + (exclamations * 0.01)),
            }
        )

    hedge_phrases = ["maybe", "perhaps", "i think", "kind of", "sort of", "not sure"]
    decisive_words = {"definitely", "certain", "will", "must", "clear", "decided"}
    hedge_hits = sum(1 for phrase in hedge_phrases if phrase in lower_text)
    decisive_hits = sum(1 for word in words if word in decisive_words)
    decision_signal = max(0.0, min(1.0, 0.5 + (decisive_hits * 0.12) - (hedge_hits * 0.14)))
    if hedge_hits > 0 or decisive_hits > 0:
        fallback_traits.append(
            {
                "name": "decision_framing",
                "signal": decision_signal,
                "strength": min(0.17, 0.08 + ((hedge_hits + decisive_hits) * 0.02)),
            }
        )

    depth_markers = {
        "why",
        "because",
        "realize",
        "pattern",
        "meaning",
        "reflect",
        "thinking",
        "understand",
    }
    depth_hits = sum(1 for word in words if word in depth_markers)
    depth_signal = max(0.0, min(1.0, 0.2 + (depth_hits * 0.14)))
    if depth_hits > 0:
        fallback_traits.append(
            {
                "name": "reflection_depth",
                "signal": depth_signal,
                "strength": min(0.18, 0.08 + (depth_hits * 0.02)),
            }
        )

    return [
        trait
        for trait in fallback_traits
        if abs(trait["signal"] - 0.5) >= 0.08 or trait["name"] == "communication_style"
    ]


def build_behavioral_insight_payload(user_text: str, traits: List[Dict[str, float]]) -> Dict[str, object]:
    if not traits:
        return {
            "text": "Communication pattern observed in recent reflection message.",
            "tags": ["behavioral-pattern"],
            "confidence": 0.55,
        }

    def trait_priority(trait: Dict[str, float]) -> float:
        return abs(float(trait["signal"]) - 0.5) * float(trait["strength"])

    top_traits = sorted(traits, key=trait_priority, reverse=True)[:2]

    phrase_map = {
        "communication_style": ("more concise wording", "more elaborated wording"),
        "emotional_expressiveness": ("a more emotionally reserved tone", "higher emotional expressiveness"),
        "decision_framing": ("more hesitant framing", "more decisive framing"),
        "reflection_depth": ("surface-level framing", "deeper reflective framing"),
    }

    observations: List[str] = []
    tags = ["behavioral-pattern"]
    strengths: List[float] = []
    text_lower = user_text.lower()

    for trait in top_traits:
        trait_name = str(trait["name"])
        signal = float(trait["signal"])
        strength = float(trait["strength"])
        low_phrase, high_phrase = phrase_map.get(
            trait_name,
            (f"lower {trait_name.replace('_', ' ')}", f"higher {trait_name.replace('_', ' ')}"),
        )
        observations.append(high_phrase if signal >= 0.5 else low_phrase)
        tags.append(trait_name)
        strengths.append(strength)

    if any(token in text_lower for token in ["exam", "deadline", "project"]):
        tags.append("workload-context")
    if any(token in text_lower for token in ["stress", "overwhelmed", "anxious", "worried"]):
        tags.append("stress-signal")

    insight_text = (
        f"Recent reflection shows {observations[0]}."
        if len(observations) == 1
        else f"Recent reflection shows {observations[0]} with {observations[1]}."
    )

    avg_strength = (sum(strengths) / len(strengths)) if strengths else 0.08
    confidence = max(0.55, min(0.9, 0.5 + (avg_strength * 1.8)))

    return {
        "text": insight_text,
        "tags": sorted(set(tags)),
        "confidence": round(confidence, 3),
    }


async def fetch_latest_reflection_messages(session) -> List[Tuple]:
    stmt = (
        select(
            Conversation.id,
            Conversation.user_id,
            Message.content,
            Message.created_at,
        )
        .join(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.mode == "reflection", Message.role == "user")
        .order_by(Conversation.id, Message.created_at.desc())
    )
    result = await session.execute(stmt)
    rows = result.all()

    latest_by_conversation = {}
    for row in rows:
        if row.id not in latest_by_conversation:
            latest_by_conversation[row.id] = row

    return list(latest_by_conversation.values())


async def fetch_existing_conversation_insights(session) -> set:
    stmt = select(BehavioralInsight.conversation_id).where(BehavioralInsight.conversation_id.is_not(None))
    result = await session.execute(stmt)
    return {row[0] for row in result.all() if row[0] is not None}


async def backfill(dry_run: bool = False, limit: int = 0) -> None:
    async with AsyncSessionLocal() as session:
        latest_messages = await fetch_latest_reflection_messages(session)
        existing_conversation_ids = await fetch_existing_conversation_insights(session)

        candidates = [row for row in latest_messages if row.id not in existing_conversation_ids]
        if limit > 0:
            candidates = candidates[:limit]

        print(f"Found {len(latest_messages)} reflection conversations")
        print(f"Existing conversation-linked insights: {len(existing_conversation_ids)}")
        print(f"Backfill candidates: {len(candidates)}")

        if not candidates:
            print("Nothing to backfill.")
            return

        inserts = 0
        for row in candidates:
            traits = derive_fallback_traits(row.content or "")
            payload = build_behavioral_insight_payload(row.content or "", traits)

            if dry_run:
                print(
                    f"[DRY RUN] conv={row.id} user={row.user_id} text='{payload['text']}' tags={payload['tags']}"
                )
                inserts += 1
                continue

            insight = BehavioralInsight(
                user_id=row.user_id,
                conversation_id=row.id,
                insight_text=payload["text"],
                tags=payload["tags"],
                confidence=payload["confidence"],
            )
            session.add(insight)
            inserts += 1

        if dry_run:
            print(f"Dry run complete. Would insert {inserts} insights.")
            return

        await session.commit()
        print(f"Inserted {inserts} behavioral insights.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill behavioral insights from reflection conversations")
    parser.add_argument("--dry-run", action="store_true", help="Preview inserts without writing to DB")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of conversations to process")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(backfill(dry_run=args.dry_run, limit=args.limit))
