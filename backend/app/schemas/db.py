from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    user_id: str
    title: Optional[str] = None
    mode: str = "reflection"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    user_id: UUID
    title: Optional[str] = None
    mode: str
    metadata: Dict[str, Any] = Field(alias="metadata_")
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    user_id: str
    conversation_id: str
    role: str
    content: str
    embedding: Optional[List[float]] = None
    token_count: Optional[int] = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    user_id: UUID
    role: str
    content: str
    embedding: Optional[List[float]] = None
    token_count: Optional[int] = None
    created_at: datetime


class ConversationHistoryOut(BaseModel):
    conversation_id: str
    messages: List[MessageOut]


class PersonalityProfileUpdate(BaseModel):
    openness: Optional[float] = None
    conscientiousness: Optional[float] = None
    extraversion: Optional[float] = None
    agreeableness: Optional[float] = None
    neuroticism: Optional[float] = None
    themes: Optional[Dict[str, Any]] = None
    traits: Optional[Dict[str, Any]] = None
    values: Optional[Dict[str, Any]] = None
    stressors: Optional[Dict[str, Any]] = None


class PersonalityProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    openness: Optional[float] = None
    conscientiousness: Optional[float] = None
    extraversion: Optional[float] = None
    agreeableness: Optional[float] = None
    neuroticism: Optional[float] = None
    themes: Dict[str, Any]
    traits: Dict[str, Any]
    values: Dict[str, Any]
    stressors: Dict[str, Any]
    updated_at: datetime


class ConversationListItem(BaseModel):
    """Lightweight conversation item for list view"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: Optional[str] = None
    created_at: datetime


class ConversationListOut(BaseModel):
    """List of conversations"""
    conversations: List[ConversationListItem]
