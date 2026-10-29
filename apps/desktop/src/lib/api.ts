import type {
  AccessTokenIssued,
  AccessTokenRead,
  AdminMetrics,
  AgentAction,
  AgentActionCreate,
  AgentDecision,
  AgentSettings,
  AgentSettingsUpdate,
  AutonomyBudget,
  AutonomyBudgetUpdate,
  AutonomyErrorLog,
  CalibrationRule,
  CommunicationProfile,
  CommunicationProfileUpdate,
  CompatibilityAssessment,
  CompatibilityRequest,
  Conversation,
  ConversationCreate,
  DecisionEvaluateRequest,
  DynamicsChange,
  Draft,
  Feedback,
  FeedbackClassification,
  FeedbackCreate,
  HealthResponse,
  LLMStatus,
  Message,
  MessageImport,
  PrivacyExport,
  RelationshipSignal,
  RelationshipTimelineEntry,
  RiskAssessment,
  RiskRequest,
  UserProfile,
  UserProfileUpdate,
  VisionObservation,
  VisionObservationCreate,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export interface ApiClientOptions {
  baseUrl: string;
  token: string;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/** Общий таймаут HTTP-запроса: интерфейс не должен «висеть» на недоступном API. */
const API_TIMEOUT_MS = 20000;

export class ApiClient {
  private readonly baseUrl: string;
  readonly token: string;

  constructor({ baseUrl, token }: ApiClientOptions) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.token = token;
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const { data } = await this.requestFull<T>(path, init);
    return data as T;
  }

  /** Низкоуровневый запрос: используется оффлайн-очередью при повторном воспроизведении. */
  send(
    path: string,
    init: { method: string; body?: string; idempotencyKey?: string },
  ): Promise<unknown> {
    const headers: Record<string, string> = {};
    if (init.idempotencyKey) headers["Idempotency-Key"] = init.idempotencyKey;
    return this.request<unknown>(path, { method: init.method, headers, body: init.body });
  }

  health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health");
  }

  /** Фактический статус LLM-шлюза (провайдер, fallback, лимит) — UI-индикатор. */
  llmStatus(): Promise<LLMStatus> {
    return this.request<LLMStatus>("/api/v1/llm/status");
  }

  ready(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health/ready");
  }

  getProfile(): Promise<UserProfile> {
    return this.request<UserProfile>("/api/v1/profile");
  }

  updateProfile(payload: UserProfileUpdate): Promise<UserProfile> {
    return this.request<UserProfile>("/api/v1/profile", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  getCommunication(): Promise<CommunicationProfile> {
    return this.request<CommunicationProfile>("/api/v1/profile/communication");
  }

  updateCommunication(payload: CommunicationProfileUpdate): Promise<CommunicationProfile> {
    return this.request<CommunicationProfile>("/api/v1/profile/communication", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  listFeedback(limit = 50, offset = 0): Promise<Feedback[]> {
    return this.request<Feedback[]>(`/api/v1/feedback?limit=${limit}&offset=${offset}`);
  }

  createFeedback(payload: FeedbackCreate): Promise<Feedback> {
    return this.request<Feedback>("/api/v1/feedback", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  listConversations(limit = 50, offset = 0): Promise<Conversation[]> {
    return this.request<Conversation[]>(
      `/api/v1/conversations?limit=${limit}&offset=${offset}`,
    );
  }

  createConversation(payload: ConversationCreate): Promise<Conversation> {
    return this.request<Conversation>("/api/v1/conversations", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  getConversation(id: string): Promise<Conversation> {
    return this.request<Conversation>(`/api/v1/conversations/${id}`);
  }

  listMessages(id: string, limit = 200, offset = 0): Promise<Message[]> {
    return this.request<Message[]>(
      `/api/v1/conversations/${id}/messages?limit=${limit}&offset=${offset}`,
    );
  }

  importMessage(id: string, payload: MessageImport): Promise<Message> {
    return this.request<Message>(`/api/v1/conversations/${id}/messages/import`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  createDraft(id: string): Promise<Draft> {
    return this.request<Draft>(`/api/v1/conversations/${id}/drafts`, {
      method: "POST",
    });
  }

  createCompatibility(payload: CompatibilityRequest): Promise<CompatibilityAssessment> {
    return this.request<CompatibilityAssessment>("/api/v1/analysis/compatibility", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  listCompatibility(limit = 50): Promise<CompatibilityAssessment[]> {
    return this.request<CompatibilityAssessment[]>(
      `/api/v1/analysis/compatibility?limit=${limit}`,
    );
  }

  createRisk(payload: RiskRequest): Promise<RiskAssessment> {
    return this.request<RiskAssessment>("/api/v1/analysis/risk", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  listRisk(limit = 50): Promise<RiskAssessment[]> {
    return this.request<RiskAssessment[]>(`/api/v1/analysis/risk?limit=${limit}`);
  }

  getAgentSettings(): Promise<AgentSettings> {
    return this.request<AgentSettings>("/api/v1/agent/settings");
  }

  updateAgentSettings(payload: AgentSettingsUpdate): Promise<AgentSettings> {
    return this.request<AgentSettings>("/api/v1/agent/settings", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  pauseAgent(): Promise<AgentSettings> {
    return this.request<AgentSettings>("/api/v1/agent/pause", { method: "POST" });
  }

  resumeAgent(): Promise<AgentSettings> {
    return this.request<AgentSettings>("/api/v1/agent/resume", { method: "POST" });
  }

  listActions(status?: string, limit = 50): Promise<AgentAction[]> {
    const query = new URLSearchParams({ limit: String(limit) });
    if (status) query.set("status", status);
    return this.request<AgentAction[]>(`/api/v1/agent/actions?${query.toString()}`);
  }

  createAction(payload: AgentActionCreate, idempotencyKey?: string): Promise<AgentAction> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    return this.request<AgentAction>("/api/v1/agent/actions", {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
  }

  /**
   * Создание действия с фактическим HTTP-статусом: лаборатория тестирования
   * различает 201 (создано) и 200 (повтор по Idempotency-Key — доказательство
   * отсутствия дубля). Аддитивно: `createAction` не изменяется.
   */
  async createActionWithStatus(
    payload: AgentActionCreate,
    idempotencyKey?: string,
  ): Promise<{ status: number; action: AgentAction }> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    const { status, data } = await this.requestFull<AgentAction>("/api/v1/agent/actions", {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    return { status, action: data as AgentAction };
  }

  /** Запрос, возвращающий статус и разобранное тело (одно обращение к сети). */
  private async requestFull<T>(
    path: string,
    init?: RequestInit,
  ): Promise<{ status: number; data: T | null }> {
    const headers = new Headers(init?.headers);
    headers.set("Accept", "application/json");
    if (init?.body !== undefined && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (this.token) {
      headers.set("Authorization", `Bearer ${this.token}`);
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        ...init,
        headers,
        signal: controller.signal,
      });
    } catch {
      throw new ApiError(0, `Не удалось подключиться к API (${this.baseUrl})`);
    } finally {
      clearTimeout(timer);
    }
    try {
      const text = await response.text();
      const data = text ? (safeJson(text) as T) : null;
      if (!response.ok) {
        const detail =
          data && typeof data === "object" && "detail" in data
            ? (data as { detail: unknown }).detail
            : data;
        const message = typeof detail === "string" ? detail : `HTTP ${response.status}`;
        throw new ApiError(response.status, message, data);
      }
      return { status: response.status, data };
    } finally {
      clearTimeout(timer);
    }
  }

  approveAction(id: string): Promise<AgentAction> {
    return this.request<AgentAction>(`/api/v1/agent/actions/${id}/approve`, {
      method: "POST",
    });
  }

  rejectAction(id: string): Promise<AgentAction> {
    return this.request<AgentAction>(`/api/v1/agent/actions/${id}/reject`, {
      method: "POST",
    });
  }

  listVisionObservations(conversationId?: string, limit = 25): Promise<VisionObservation[]> {
    const query = new URLSearchParams({ limit: String(limit) });
    if (conversationId) query.set("conversation_id", conversationId);
    return this.request<VisionObservation[]>(
      `/api/v1/vision/observations?${query.toString()}`,
    );
  }

  createVisionObservation(payload: VisionObservationCreate): Promise<VisionObservation> {
    return this.request<VisionObservation>("/api/v1/vision/observations", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  listTokens(): Promise<AccessTokenRead[]> {
    return this.request<AccessTokenRead[]>("/api/v1/tokens");
  }

  issueToken(label: string): Promise<AccessTokenIssued> {
    return this.request<AccessTokenIssued>("/api/v1/tokens", {
      method: "POST",
      body: JSON.stringify({ label }),
    });
  }

  rotateToken(id: string): Promise<AccessTokenIssued> {
    return this.request<AccessTokenIssued>(`/api/v1/tokens/${id}/rotate`, {
      method: "POST",
    });
  }

  revokeToken(id: string): Promise<void> {
    return this.request<void>(`/api/v1/tokens/${id}`, { method: "DELETE" });
  }

  adminMetrics(): Promise<AdminMetrics> {
    return this.request<AdminMetrics>("/api/v1/admin/metrics");
  }

  // --- Decision Loop (прозрачность решений агента) ---

  listDecisions(conversationId?: string, limit = 50): Promise<AgentDecision[]> {
    const query = new URLSearchParams({ limit: String(limit) });
    if (conversationId) query.set("conversation_id", conversationId);
    return this.request<AgentDecision[]>(`/api/v1/agent/decisions?${query.toString()}`);
  }

  evaluateDecision(payload: DecisionEvaluateRequest): Promise<AgentDecision> {
    return this.request<AgentDecision>("/api/v1/agent/decisions/evaluate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  // --- Adaptive Autonomy: бюджет, ошибки, калибровка ---

  getAutonomyBudget(): Promise<AutonomyBudget> {
    return this.request<AutonomyBudget>("/api/v1/autonomy/budget");
  }

  updateAutonomyBudget(payload: AutonomyBudgetUpdate): Promise<AutonomyBudget> {
    return this.request<AutonomyBudget>("/api/v1/autonomy/budget", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  listAutonomyErrors(limit = 50): Promise<AutonomyErrorLog[]> {
    return this.request<AutonomyErrorLog[]>(`/api/v1/autonomy/errors?limit=${limit}`);
  }

  resetAutonomyErrors(): Promise<AutonomyBudget> {
    return this.request<AutonomyBudget>("/api/v1/autonomy/reset-errors", { method: "POST" });
  }

  listCalibrationRules(limit = 50): Promise<CalibrationRule[]> {
    return this.request<CalibrationRule[]>(`/api/v1/autonomy/calibration-rules?limit=${limit}`);
  }

  classifyFeedback(id: string, classification?: string): Promise<FeedbackClassification> {
    return this.request<FeedbackClassification>(`/api/v1/autonomy/feedback/${id}/classify`, {
      method: "POST",
      body: JSON.stringify({ classification: classification ?? null }),
    });
  }

  // --- Relationship Dynamics ---

  listDynamicsSignals(conversationId?: string, dimension?: string): Promise<RelationshipSignal[]> {
    const query = new URLSearchParams();
    if (conversationId) query.set("conversation_id", conversationId);
    if (dimension) query.set("dimension", dimension);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return this.request<RelationshipSignal[]>(`/api/v1/dynamics/signals${suffix}`);
  }

  computeDynamicsSignals(conversationId: string): Promise<RelationshipSignal[]> {
    return this.request<RelationshipSignal[]>(
      `/api/v1/dynamics/signals/compute?conversation_id=${conversationId}`,
      { method: "POST" },
    );
  }

  listDynamicsTimeline(conversationId?: string): Promise<RelationshipTimelineEntry[]> {
    const suffix = conversationId ? `?conversation_id=${conversationId}` : "";
    return this.request<RelationshipTimelineEntry[]>(`/api/v1/dynamics/timeline${suffix}`);
  }

  compareDynamicsPeriods(conversationId: string, days = 30): Promise<DynamicsChange[]> {
    return this.request<DynamicsChange[]>(
      `/api/v1/dynamics/compare?conversation_id=${conversationId}&days=${days}`,
    );
  }

  // --- Privacy: экспорт и удаление ---

  exportPrivacy(): Promise<PrivacyExport> {
    return this.request<PrivacyExport>("/api/v1/privacy/export");
  }

  requestDeletion(): Promise<void> {
    return this.request<void>("/api/v1/privacy/deletion-request", { method: "POST" });
  }
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return error.message;
    return `${error.status}: ${error.message}`;
  }
  if (error instanceof Error) return error.message;
  return String(error);
}
