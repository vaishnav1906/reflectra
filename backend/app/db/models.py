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
    behavioral_insights = relationship("BehavioralInsight", back_populates="user", cascade="all, delete-orphan")
    reflection_logs = relationship("ReflectionLog", back_populates="user", cascade="all, delete-orphan")


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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
