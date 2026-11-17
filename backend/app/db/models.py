from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
    Numeric,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    email = Column(String(320), unique=True, nullable=False, index=True)
    display_name = Column(Text)
    birth_date = Column(Date)  # optional; age is worked out from it
    # Supabase Auth user id (auth.users.id); set on first authenticated sign-in.
    auth_user_id = Column(UUID(as_uuid=True), unique=True, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    personality_profile = relationship("PersonalityProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    schedule_context = relationship("ScheduleContext", back_populates="user", uselist=False, cascade="all, delete-orphan")
    user_settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    behavioral_insights = relationship("BehavioralInsight", back_populates="user", cascade="all, delete-orphan")
    reflection_logs = relationship("ReflectionLog", back_populates="user", cascade="all, delete-orphan")
    linguistic_fingerprint = relationship("LinguisticFingerprint", back_populates="user", uselist=False, cascade="all, delete-orphan")
    reaction_patterns = relationship("ReactionPattern", back_populates="user", cascade="all, delete-orphan")
    mirror_response_memories = relationship("MirrorResponseMemory", back_populates="user", cascade="all, delete-orphan")
    external_inputs = relationship("ExternalInput", back_populates="user", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="user", cascade="all, delete-orphan")
    people = relationship("Person", back_populates="user", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(Text)
    mode = Column(String(32), nullable=False, server_default=text("'reflection'"))
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    behavioral_insights = relationship("BehavioralInsight", back_populates="conversation")
    reflection_logs = relationship("ReflectionLog", back_populates="conversation")
    mirror_response_memories = relationship("MirrorResponseMemory", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False, index=True)
    content = Column(Text, nullable=False)
    # Length differs between databases (1024 or 1536); embedding_service reads the real one.
    embedding = Column(Vector(1536))
    token_count = Column(Integer)
    emotional_intensity = Column(Float)
    reflection_depth = Column(Float)
    response_delay_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="messages")
    conversation = relationship("Conversation", back_populates="messages")


class PersonalityProfile(Base):
    __tablename__ = "personality_profile"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    openness = Column(Float)
    conscientiousness = Column(Float)
    extraversion = Column(Float)
    agreeableness = Column(Float)
    neuroticism = Column(Float)
    themes = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    traits = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    values = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    stressors = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="personality_profile")


class BehavioralInsight(Base):
    __tablename__ = "behavioral_insights"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"))
    insight_text = Column(Text, nullable=False)
    tags = Column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    confidence = Column(Float)
    # "reflection" = evidence-backed pattern across conversations; "signal" = legacy per-message line.
    kind = Column(String(32), nullable=False, server_default=text("'signal'"))
    title = Column(Text)
    evidence = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="behavioral_insights")
    conversation = relationship("Conversation", back_populates="behavioral_insights")


class ReflectionLog(Base):
    __tablename__ = "reflection_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"))
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    sentiment = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="reflection_logs")
    conversation = relationship("Conversation", back_populates="reflection_logs")


class UserPersonaMetric(Base):
    __tablename__ = "user_persona_metrics"
    __table_args__ = (
        UniqueConstraint("user_id", "trait_name", name="uq_user_trait"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    trait_name = Column(String(128), nullable=False, index=True)
    score = Column(Float, nullable=False, server_default=text("0.5"))
    confidence = Column(Float, nullable=False, server_default=text("0.1"))
    evidence_count = Column(Integer, nullable=False, server_default=text("0"))
    last_signal = Column(Float)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PersonaSnapshot(Base):
    __tablename__ = "persona_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    persona_vector = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    stability_index = Column(Float)
    summary_text = Column(Text)
    
    # Probabilistic behavioral traits (e.g., verbosity: {short: 0.7, medium: 0.3})
    behavioral_traits = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    
    # Anchor point for baseline historical comparison
    is_historical_anchor = Column(Boolean, nullable=False, server_default=text("false"))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ScheduleContext(Base):
    __tablename__ = "schedule_context"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    classes_per_day = Column(Integer, nullable=False, server_default=text("0"))
    study_hours = Column(Integer, nullable=False, server_default=text("0"))
    has_deadlines = Column(Boolean, nullable=False, server_default=text("false"))
    is_exam_period = Column(Boolean, nullable=False, server_default=text("false"))
    workload_level = Column(String(32), nullable=False, server_default=text("'low'"))
    stress_level = Column(Float, nullable=False, server_default=text("0.0"))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="schedule_context")


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    persona_mirroring = Column(Boolean, nullable=False, server_default=text("true"))
    pattern_tracking = Column(Boolean, nullable=False, server_default=text("true"))
    daily_reflections = Column(Boolean, nullable=False, server_default=text("true"))
    digital_twin_enabled = Column(Boolean, nullable=False, server_default=text("true"))
    twin_autonomy_mode = Column(String(32), nullable=False, server_default=text("'draft_only'"))
    twin_mirror_intensity = Column(Float, nullable=False, server_default=text("0.8"))
    twin_require_approval = Column(Boolean, nullable=False, server_default=text("true"))
    # Which reminders the user wants, and when (see app.services.notification_prefs).
    notifications = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    theme = Column(JSONB)  # {"hue": 0-359, "saturation": 30-100}; None = the default violet
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="user_settings")


class MirrorLog(Base):
    __tablename__ = "mirror_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    inference_duration_ms = Column(Integer, nullable=False)
    realism_score = Column(Numeric(4, 3), nullable=False)
    retries_used = Column(Integer, nullable=False, server_default=text("0"))
    fallback_triggered = Column(Boolean, nullable=False, server_default=text("false"))
    confidence_lower = Column(Float)
    confidence_upper = Column(Float)
    confidence_tier = Column(String(32))
    style_enforcement_strength = Column(Float)
    reaction_match_score = Column(Float)
    source_weights = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MirrorResponseMemory(Base):
    __tablename__ = "mirror_response_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    response_hash = Column(String(64), nullable=False, index=True)
    response_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="mirror_response_memories")
    conversation = relationship("Conversation", back_populates="mirror_response_memories")


class LinguisticFingerprint(Base):
    __tablename__ = "linguistic_fingerprints"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    characteristic_phrases = Column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    abbreviation_stats = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    sentence_patterns = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    sample_count = Column(Integer, nullable=False, server_default=text("0"))
    confidence = Column(Float, nullable=False, server_default=text("0.1"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="linguistic_fingerprint")


class ReactionPattern(Base):
    __tablename__ = "reaction_patterns"
    __table_args__ = (
        UniqueConstraint("user_id", "stimulus_tag", "response_template", name="uq_reaction_pattern_user_stimulus_template"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stimulus_tag = Column(String(64), nullable=False, index=True)
    response_template = Column(Text, nullable=False)
    phrase_bank = Column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    style_signature = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    confidence = Column(Float, nullable=False, server_default=text("0.3"))
    frequency = Column(Integer, nullable=False, server_default=text("1"))
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="reaction_patterns")


class ExternalInput(Base):
    __tablename__ = "external_inputs"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    source = Column(String(64), nullable=False, server_default=text("'pasted_prompt'"))
    content = Column(Text, nullable=False)
    extracted_markers = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    confidence_weight = Column(Float, nullable=False, server_default=text("0.1"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="external_inputs")


class Feedback(Base):
    """What the user said about something Reflectra produced: a reply, a trait reading
    or a reflection. One row per thing; changing your mind updates it."""

    __tablename__ = "feedback"
    __table_args__ = (UniqueConstraint("user_id", "target_type", "target_id", name="uq_feedback_target"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_type = Column(String(16), nullable=False)  # "reply" | "trait" | "reflection"
    target_id = Column(String(64), nullable=False)  # message id, trait key or reflection id
    verdict = Column(String(16), nullable=False)  # "up" / "down" for replies, "agree" / "disagree" otherwise
    reasons = Column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    note = Column(Text)
    value = Column(Float)  # a trait: where the user would put themselves (0-1)
    details = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # mode, titles, before/after values
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="feedback")


class Person(Base):
    """Someone in the user's life, as the user describes them.

    status: "active" (the user added or confirmed them), "suggested" (Reflectra
    noticed the name and is asking), "dismissed" (the user said no; never suggested
    again under this name).
    notes: what came up about them in chats, each with the user's exact words:
    [{"id", "text", "quote", "date", "conversation_id", "source": "chat" | "you"}]
    """

    __tablename__ = "people"
    __table_args__ = (UniqueConstraint("user_id", "name_key", name="uq_people_user_name"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    name_key = Column(String(80), nullable=False)  # lowercased name, for uniqueness
    aliases = Column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    relationship_label = Column(String(80))  # "best friend", "mom", "manager"
    description = Column(Text)  # in the user's words
    birthday = Column(String(10))  # "MM-DD" or "YYYY-MM-DD"
    notes = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    status = Column(String(16), nullable=False, server_default=text("'active'"))
    mention_count = Column(Integer, nullable=False, server_default=text("0"))
    last_mentioned_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="people")


class Job(Base):
    """Background work queued by a request and run by the worker (app.worker)."""

    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(40), nullable=False)
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status = Column(String(12), nullable=False, server_default=text("'queued'"))  # queued | running | done | failed
    attempts = Column(Integer, nullable=False, server_default=text("0"))
    dedupe_key = Column(String(120))
    last_error = Column(Text)
    run_after = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LifeFact(Base):
    """Something lasting about the user's life, in their own words: what they do, what's
    going on, what they're working toward. They can edit, pin or delete any of it."""

    __tablename__ = "life_facts"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(16), nullable=False)  # about | situation | goal | preference | routine | place
    statement = Column("text", Text, nullable=False)  # the fact itself
    quote = Column(Text)  # their exact words it came from (None when they typed it in themselves)
    source = Column(String(8), nullable=False, server_default=text("'chat'"))  # chat | you
    status = Column(String(12), nullable=False, server_default=text("'active'"))  # active | resolved | outdated
    pinned = Column(Boolean, nullable=False, server_default=text("false"))
    mention_count = Column(Integer, nullable=False, server_default=text("1"))
    first_seen = Column(String(10))  # YYYY-MM-DD, the user's local date
    last_seen = Column(String(10))
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PushSubscription(Base):
    """Where to deliver a notification: a browser (Web Push) now, phone apps later."""

    __tablename__ = "push_subscriptions"
    __table_args__ = (UniqueConstraint("endpoint", name="uq_push_endpoint"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(String(12), nullable=False, server_default=text("'web'"))  # web | android | ios
    endpoint = Column(Text, nullable=False)  # Web Push endpoint, or an FCM/APNs device token
    keys = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # p256dh / auth for Web Push
    user_agent = Column(String(200))
    failures = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_sent_at = Column(DateTime(timezone=True))


class NotificationSent(Base):
    """A nudge that went out: what it was about, and the question it opens with."""

    __tablename__ = "notifications_sent"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(20), nullable=False)  # follow_up | birthday | weekly_digest | check_in | test
    ref = Column(String(64))  # the follow-up / person it's about, or the ISO week
    local_date = Column(String(10), nullable=False)
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    opener = Column(Text)  # what Reflectra says first when the nudge is opened
    url = Column(Text)
    delivered = Column(Integer, nullable=False, server_default=text("0"))  # devices it reached
    opened_at = Column(DateTime(timezone=True))
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

