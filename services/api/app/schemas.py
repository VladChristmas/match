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
