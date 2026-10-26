export type UUID = string;
export type JsonObject = Record<string, unknown>;

/** Статус LLM-шлюза (`GET /api/v1/llm/status`). */
export interface LLMStatus {
  provider: string;
  fallback_providers: string[];
  declared_providers: string[];
  skipped_providers: string[];
  user_request_limit: number;
  user_request_limit_enabled: boolean;
  timeout_seconds: number;
}

export interface UserProfile {
  id: UUID;
  user_id: UUID;
  relationship_goals: string[];
  values: string[];
  preferences: JsonObject;
  boundaries: JsonObject;
  profile_version: number;
  created_at: string;
  updated_at: string;
}

export interface UserProfileUpdate {
  relationship_goals?: string[];
  values?: string[];
  preferences?: JsonObject;
  boundaries?: JsonObject;
}

export interface CommunicationProfile {
  id: UUID;
  user_id: UUID;
  style_preferences: JsonObject;
  tone_preferences: JsonObject;
  typical_message_length: string | null;
  humor_preferences: JsonObject;
  initiative_preferences: JsonObject;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface CommunicationProfileUpdate {
  style_preferences?: JsonObject;
  tone_preferences?: JsonObject;
  typical_message_length?: string | null;
  humor_preferences?: JsonObject;
  initiative_preferences?: JsonObject;
}

export interface Feedback {
  id: UUID;
  user_id: UUID;
  conversation_id: UUID | null;
  action_id: UUID | null;
  feedback_type: string;
  rating: number | null;
  correction: string | null;
  created_at: string;
}

export interface FeedbackCreate {
  feedback_type: string;
  rating?: number | null;
  correction?: string | null;
  conversation_id?: UUID | null;
}

export type Direction = "inbound" | "outbound";

export interface Conversation {
  id: UUID;
  user_id: UUID;
  match_id: UUID | null;
  status: string;
  autonomy_mode: string;
  last_activity_at: string | null;
  context_version: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationCreate {
  match_id?: UUID | null;
  autonomy_mode?: string | null;
}

export interface Message {
  id: UUID;
  conversation_id: UUID;
  external_message_id: string | null;
  direction: Direction;
  content: string | null;
  source: string;
  processing_status: string;
  created_at: string;
  processed_at: string | null;
}

export interface MessageImport {
  content: string;
  direction?: Direction;
  external_message_id?: string | null;
  source?: string;
}

export interface Draft {
  text: string;
  provider: string;
  model: string;
  latency_ms: number;
  validation_ok: boolean;
  issues: string[];
}

export interface CounterpartInput {
  goals: string[];
  values: string[];
  lifestyle: JsonObject;
}

export interface CompatibilityRequest {
  match_id?: UUID | null;
  conversation_id?: UUID | null;
  counterpart: CounterpartInput;
  reciprocity?: number | null;
}

export interface CompatibilityAssessment {
  id: UUID;
  user_id: UUID;
  match_id: UUID | null;
  conversation_id: UUID | null;
  goals_alignment: number;
  values_alignment: number;
  lifestyle_alignment: number;
  reciprocity: number;
  uncertainty: number;
  explanation: string | null;
  model_version: string;
  assessed_at: string;
}

export interface RiskRequest {
  match_id?: UUID | null;
  conversation_id?: UUID | null;
  messages: string[];
}

export interface RiskSignal {
  category: string;
  matches: number;
}

export interface RiskAssessment {
  id: UUID;
  user_id: UUID;
  match_id: UUID | null;
  conversation_id: UUID | null;
  risk_category: string;
  signals: RiskSignal[];
  confidence: number;
  explanation: string | null;
  recommended_action: string;
  assessed_at: string;
}

export interface HealthResponse {
  status: string;
  [key: string]: unknown;
}

export interface AgentSettings {
  id: UUID;
  user_id: UUID;
  default_autonomy_mode: string;
  queue_paused: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentSettingsUpdate {
  default_autonomy_mode?: string;
  queue_paused?: boolean;
}

export interface AgentAction {
  id: UUID;
  user_id: UUID;
  conversation_id: UUID;
  action_type: string;
  text: string | null;
  provider: string | null;
  model: string | null;
  validation_ok: boolean | null;
  status: string;
  idempotency_key: string | null;
  error: string | null;
  attempts: number;
  created_at: string;
  decided_at: string | null;
  sent_at: string | null;
}

export interface AgentActionCreate {
  conversation_id: UUID;
  text?: string | null;
  generate?: boolean;
}

export interface CaptureTarget {
  handle: number;
  title: string;
}

export interface CapturedFrame {
  width: number;
  height: number;
  png_base64: string;
}

export interface VisionObservation {
  id: UUID;
  user_id: UUID;
  conversation_id: UUID;
  source_label: string;
  frame_width: number;
  frame_height: number;
  frame_bytes: number;
  content_sha256: string;
  analysis_pending: boolean;
  summary: string | null;
  provider: string | null;
  model: string | null;
  captured_at: string | null;
  created_at: string;
}

export interface VisionObservationCreate {
  conversation_id: UUID;
  frame_base64: string;
  source_label?: string;
  captured_at?: string | null;
  analyze?: boolean;
}

export interface AdminMetric {
  total: number;
  by_key: Record<string, number>;
}

export interface AdminMetrics {
  generated_at: string;
  users: AdminMetric;
  conversations: AdminMetric;
  messages: AdminMetric;
  model_runs: AdminMetric;
  model_runs_by_provider: AdminMetric;
  vision_observations: AdminMetric;
  agent_actions: AdminMetric;
  feedback: AdminMetric;
  access_tokens: AdminMetric;
  settings: Record<string, string>;
}

export interface AccessTokenRead {
  id: UUID;
  label: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface AccessTokenIssued {
  id: UUID;
  token: string;
  label: string;
  created_at: string;
}

export type MemoryKind = "fact" | "preference" | "hypothesis" | "temporary_state" | "agreement";
export type MemoryStatus = "received" | "classified" | "verified" | "used" | "revised";

export interface Memory {
  id: UUID;
  user_id: UUID;
  conversation_id: UUID | null;
  kind: MemoryKind;
  status: MemoryStatus;
  content: string;
  source: string;
  confidence: number;
  valid_until: string | null;
  created_at: string;
  updated_at: string;
}

export interface MemoryCreate {
  kind: MemoryKind;
  content: string;
  source?: string;
  confidence?: number;
  valid_until?: string | null;
  conversation_id?: UUID | null;
}

export interface MemoryUpdate {
  content?: string | null;
  confidence?: number | null;
}

export interface MemoryEvent {
  id: UUID;
  memory_id: UUID;
  event_type: string;
  actor: string;
  detail: string | null;
  created_at: string;
}

export interface LocalProfile {
  user_id: UUID;
  kind: "profile" | "communication";
  profile_json: string;
  updated_at: string;
}

export interface LocalConversation {
  id: UUID;
  user_id: UUID;
  match_id: UUID | null;
  status: string;
  autonomy_mode: string;
  last_activity_at: string | null;
  context_version: number;
  created_at: string;
  updated_at: string;
}

export interface LocalMessage {
  id: UUID;
  conversation_id: UUID;
  external_message_id: string | null;
  direction: Direction;
  content: string | null;
  source: string;
  processing_status: string;
  created_at: string;
  processed_at: string | null;
}

export interface AgentDecision {
  id: UUID;
  user_id: UUID;
  conversation_id: UUID;
  action_id: UUID | null;
  action: string;
  mode: string;
  rationale: string;
  confidence: number;
  alternatives: Record<string, unknown>[];
  evidence: Record<string, unknown>[];
  escalation_reason: string | null;
  missing: string[];
  created_at: string;
}

export interface DecisionEvaluateRequest {
  conversation_id: UUID;
  trigger_text?: string | null;
}

export interface AutonomyBudget {
  id: UUID;
  user_id: UUID;
  max_messages_per_day: number;
  active_start_hour: number;
  active_end_hour: number;
  allowed_conversation_ids: string[];
  actions_always_confirm: string[];
  auto_stop_after_errors: number;
  consecutive_errors: number;
  last_error_at: string | null;
  global_paused: boolean;
  created_at: string;
  updated_at: string;
}

export interface AutonomyBudgetUpdate {
  max_messages_per_day?: number;
  active_start_hour?: number;
  active_end_hour?: number;
  allowed_conversation_ids?: string[];
  actions_always_confirm?: string[];
  auto_stop_after_errors?: number;
  global_paused?: boolean;
}

export interface AutonomyErrorLog {
  id: UUID;
  user_id: UUID;
  conversation_id: UUID | null;
  action_id: UUID | null;
  error_type: string;
  created_at: string;
}

export interface CalibrationRule {
  id: UUID;
  user_id: UUID;
  rule_type: string;
  condition: Record<string, unknown>;
  action: Record<string, unknown>;
  confidence: number;
  applies_count: number;
  last_applied_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface FeedbackClassification {
  feedback_id: UUID;
  classification: string;
  rule_created: boolean;
}

export interface RelationshipSignal {
  id: UUID;
  user_id: UUID;
  conversation_id: UUID;
  dimension: string;
  value: number;
  evidence: Record<string, unknown>[];
  observed_at: string;
  created_at: string;
}

export interface RelationshipTimelineEntry {
  id: UUID;
  user_id: UUID;
  conversation_id: UUID;
  event_type: string;
  description: string;
  signals_before: Record<string, unknown>[];
  signals_after: Record<string, unknown>[];
  created_at: string;
}

export interface DynamicsChange {
  dimension?: string;
  before?: number;
  after?: number;
  delta?: number;
  direction?: string;
  [key: string]: unknown;
}

export type PrivacyExport = Record<string, unknown>;
