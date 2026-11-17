"""Settings and data management: what the Settings page promises must be true."""

from app.api.user import ERASABLE_MODELS, KEPT_ON_ERASE
from app.db.database import Base
from app.db.models import Conversation, Message, User
from app.services.mirror_engine import build_mirror_system_prompt


def _per_user_models():
    return [
        mapper.class_
        for mapper in Base.registry.mappers
        if mapper.class_ is not User and "user_id" in mapper.columns
    ]


def test_erase_covers_every_per_user_table():
    """A table holding user data that 'Erase' forgets is a privacy bug."""
    covered = set(ERASABLE_MODELS) | set(KEPT_ON_ERASE)
    missing = [model.__name__ for model in _per_user_models() if model not in covered]
    assert missing == [], f"Erase leaves these tables behind: {missing}"


def test_erase_keeps_only_settings():
    assert [model.__name__ for model in KEPT_ON_ERASE] == ["UserSettings"]
    assert not set(ERASABLE_MODELS) & set(KEPT_ON_ERASE)


def test_erase_deletes_messages_before_conversations():
    order = list(ERASABLE_MODELS)
    assert order.index(Message) < order.index(Conversation)


def _prompt_for(intensity: float) -> str:
    return build_mirror_system_prompt(
        sampled_profile={
            "communication_style": 0.3,
            "emotional_expressiveness": 0.5,
            "decision_framing": 0.5,
            "reflection_depth": 0.5,
        },
        stability_index=0.6,
        message_style={},
        twin_policy={"twin_mirror_intensity": intensity},
        voice_samples=["yo whats good", "nah im not doing that lol"],
        voice_description="lowercase, short",
        display_name="Sam",
    )


def test_mirror_strength_setting_changes_the_prompt():
    """The three options on the Settings page (0.3 / 0.6 / 0.9) must each do something different."""
    light, balanced, strong = _prompt_for(0.3), _prompt_for(0.6), _prompt_for(0.9)
    assert "lightly" in light
    assert "without exaggerating" in balanced
    assert "strongly" in strong
    assert len({light, balanced, strong}) == 3
