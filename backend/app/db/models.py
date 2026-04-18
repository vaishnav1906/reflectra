from sqlalchemy import (
    Boolean,
    Column,
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
