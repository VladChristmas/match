import type {
  AgentAction,
  AgentActionCreate,
  AgentSettings,
  AgentSettingsUpdate,
  CommunicationProfile,
  CommunicationProfileUpdate,
  CompatibilityAssessment,
  CompatibilityRequest,
  Conversation,
  ConversationCreate,
  Draft,
  Feedback,
  FeedbackCreate,
  HealthResponse,
  Message,
  MessageImport,
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

export class ApiClient {
  private readonly baseUrl: string;
  readonly token: string;

  constructor({ baseUrl, token }: ApiClientOptions) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.token = token;
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const headers = new Headers(init?.headers);
    headers.set("Accept", "application/json");
    if (init?.body !== undefined && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (this.token) {
      headers.set("Authorization", `Bearer ${this.token}`);
    }

    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, { ...init, headers });
    } catch {
      throw new ApiError(0, `Не удалось подключиться к API (${this.baseUrl})`);
    }

    const text = await response.text();
    const data = text ? safeJson(text) : null;

    if (!response.ok) {
      const detail =
        data && typeof data === "object" && "detail" in data
          ? (data as { detail: unknown }).detail
          : data;
      const message = typeof detail === "string" ? detail : `HTTP ${response.status}`;
      throw new ApiError(response.status, message, data);
    }

    return data as T;
  }

  health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health");
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
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return error.message;
    return `${error.status}: ${error.message}`;
  }
  if (error instanceof Error) return error.message;
  return String(error);
}
