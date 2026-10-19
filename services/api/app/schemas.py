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


class IntegrationCapabilitiesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    supported: bool
    manual_import: bool
    screen_observation: bool
    direct_messaging: bool
    auto_send: bool
    requires_authorization: bool


class IntegrationRead(BaseModel):
    platform_id: str
    display_name: str
    status: str
    capabilities: IntegrationCapabilitiesRead


class AgentSettingsUpdate(BaseModel):
    default_autonomy_mode: str | None = Field(default=None, max_length=32)
    queue_paused: bool | None = None


class AgentSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    default_autonomy_mode: str
    queue_paused: bool
    created_at: datetime
    updated_at: datetime


class AgentActionCreate(BaseModel):
    conversation_id: uuid.UUID
    text: str | None = Field(default=None, min_length=1)
    generate: bool = True
    schedule_in_seconds: int | None = Field(default=None, ge=0, le=7 * 24 * 3600)


class AgentActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID
    action_type: str
    text: str | None
    provider: str | None
    model: str | None
    validation_ok: bool | None
    status: str
    idempotency_key: str | None
    error: str | None
    attempts: int
    created_at: datetime
    decided_at: datetime | None
    sent_at: datetime | None
    scheduled_at: datetime | None
    next_attempt_at: datetime | None


class DecisionEvaluateRequest(BaseModel):
    conversation_id: uuid.UUID
    trigger_text: str | None = Field(default=None, max_length=4000)


class AgentDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID
    action_id: uuid.UUID | None
    action: str
    mode: str
    rationale: str
    confidence: float
    alternatives: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    escalation_reason: str | None
    missing: list[str]
    created_at: datetime


class VisionObservationCreate(BaseModel):
    conversation_id: uuid.UUID
    frame_base64: str = Field(min_length=1)
    source_label: str = Field(default="window", max_length=255)
    captured_at: datetime | None = None
    analyze: bool = True


class VisionObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID
    source_label: str
    frame_width: int
    frame_height: int
    frame_bytes: int
    content_sha256: str
    analysis_pending: bool
    summary: str | None
    provider: str | None
    model: str | None
    captured_at: datetime | None
    created_at: datetime


class AccessTokenCreate(BaseModel):
    label: str = Field(default="", max_length=128)


class AccessTokenIssued(BaseModel):
    id: uuid.UUID
    token: str
    label: str
    created_at: datetime


class AccessTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class AdminMetric(BaseModel):
    total: int
    by_key: dict[str, int] = {}


class AdminMetrics(BaseModel):
    generated_at: datetime
    users: AdminMetric
    conversations: AdminMetric
    messages: AdminMetric
    model_runs: AdminMetric
    model_runs_by_provider: AdminMetric
    vision_observations: AdminMetric
    agent_actions: AdminMetric
    feedback: AdminMetric
    access_tokens: AdminMetric
    settings: dict[str, str]
