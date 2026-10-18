import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UserProfileBase(BaseModel):
    relationship_goals: list[str] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    boundaries: dict[str, Any] = Field(default_factory=dict)


class UserProfileUpdate(BaseModel):
    relationship_goals: list[str] | None = None
    values: list[str] | None = None
    preferences: dict[str, Any] | None = None
    boundaries: dict[str, Any] | None = None


class UserProfileRead(UserProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    profile_version: int
    created_at: datetime
    updated_at: datetime


class CommunicationProfileBase(BaseModel):
    style_preferences: dict[str, Any] = Field(default_factory=dict)
    tone_preferences: dict[str, Any] = Field(default_factory=dict)
    typical_message_length: str | None = None
    humor_preferences: dict[str, Any] = Field(default_factory=dict)
    initiative_preferences: dict[str, Any] = Field(default_factory=dict)


class CommunicationProfileUpdate(BaseModel):
    style_preferences: dict[str, Any] | None = None
    tone_preferences: dict[str, Any] | None = None
    typical_message_length: str | None = None
    humor_preferences: dict[str, Any] | None = None
    initiative_preferences: dict[str, Any] | None = None


class CommunicationProfileRead(CommunicationProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime


class FeedbackCreate(BaseModel):
    feedback_type: str = Field(min_length=1, max_length=32)
    rating: int | None = Field(default=None, ge=1, le=5)
    correction: str | None = None
    conversation_id: uuid.UUID | None = None
    action_id: uuid.UUID | None = None


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID | None
    action_id: uuid.UUID | None
    feedback_type: str
    rating: int | None
    correction: str | None
    created_at: datetime


class ConversationCreate(BaseModel):
    match_id: uuid.UUID | None = None
    autonomy_mode: str | None = Field(default=None, max_length=32)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    match_id: uuid.UUID | None
    status: str
    autonomy_mode: str
    last_activity_at: datetime | None
    context_version: int
    created_at: datetime
    updated_at: datetime


class MessageImport(BaseModel):
    content: str = Field(min_length=1)
    direction: str = Field(default="inbound", pattern="^(inbound|outbound)$")
    external_message_id: str | None = Field(default=None, max_length=255)
    source: str = Field(default="manual", max_length=32)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    external_message_id: str | None
    direction: str
    content: str | None
    source: str
    processing_status: str
    created_at: datetime
    processed_at: datetime | None


class DraftRead(BaseModel):
    text: str
    provider: str
    model: str
    latency_ms: int
    validation_ok: bool
    issues: list[str]


class CounterpartInput(BaseModel):
    goals: list[str] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)
    lifestyle: dict[str, Any] = Field(default_factory=dict)


class CompatibilityRequest(BaseModel):
    match_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    counterpart: CounterpartInput = Field(default_factory=CounterpartInput)
    reciprocity: float | None = Field(default=None, ge=0.0, le=1.0)


class CompatibilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    match_id: uuid.UUID | None
    conversation_id: uuid.UUID | None
    goals_alignment: float
    values_alignment: float
    lifestyle_alignment: float
    reciprocity: float
    uncertainty: float
    explanation: str | None
    model_version: str
    assessed_at: datetime


class RiskRequest(BaseModel):
    match_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    messages: list[str] = Field(default_factory=list)


class RiskSignalRead(BaseModel):
    category: str
    matches: int


class RiskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    match_id: uuid.UUID | None
    conversation_id: uuid.UUID | None
    risk_category: str
    signals: list[RiskSignalRead]
    confidence: float
    explanation: str | None
    recommended_action: str
    assessed_at: datetime
