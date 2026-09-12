import type { AIBudgetLimit, AIConnection, AIProviderUsage, AIStatus, AIRoute, ListResponse } from "./types";

const API_ROOT = "/api/v1";

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(status: number, message: string, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function csrfToken(): string | undefined {
  return document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith("newsroom_csrf="))
    ?.slice("newsroom_csrf=".length);
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (method !== "GET" && method !== "HEAD") {
    const token = csrfToken();
    if (token) headers.set("X-CSRF-Token", decodeURIComponent(token));
  }
  let response: Response;
  try {
    response = await fetch(`${API_ROOT}${path}`, { ...init, headers, credentials: "same-origin" });
  } catch (error) {
    throw new ApiError(0, "Newsroom is unavailable offline.", error);
  }
  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try { body = JSON.parse(text); } catch { body = text; }
  }
  if (!response.ok) {
    const message = typeof body === "object" && body && "error" in body
      ? String((body as { error?: { message?: string } }).error?.message ?? "Request failed")
      : "Request failed";
    throw new ApiError(response.status, message, body);
  }
  return body as T;
}

export function apiList<T>(path: string, init?: RequestInit): Promise<ListResponse<T>> {
  return apiFetch<ListResponse<T>>(path, init);
}

export function isApiUnavailable(error: unknown): boolean {
  return error instanceof ApiError && error.status === 0;
}

export function jsonBody(value: unknown): string { return JSON.stringify(value); }

export function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function shortId(value?: string | null): string { return value ? `${value.slice(0, 12)}…` : "—"; }

export function getAIStatus(): Promise<AIStatus> {
  return apiFetch<AIStatus>("/ai/status");
}

export function createAIProvider(input: {
  display_name: string;
  base_url: string;
  model: string;
  credential_required: boolean;
  max_input_chars?: number;
  max_output_tokens?: number;
}): Promise<AIConnection> {
  return apiFetch<AIConnection>("/ai/providers", { method: "POST", body: jsonBody(input) });
}

export function updateAIProvider(id: string, input: {
  expected_revision: number;
  display_name?: string;
  base_url?: string;
  model?: string;
  enabled?: boolean;
  credential_required?: boolean;
  max_input_chars?: number;
  max_output_tokens?: number;
}): Promise<AIConnection> {
  return apiFetch<AIConnection>(`/ai/providers/${encodeURIComponent(id)}`, { method: "PATCH", body: jsonBody(input) });
}

export function setAIProviderCredential(id: string, expected_revision: number, secret: string): Promise<AIConnection> {
  return apiFetch<AIConnection>(`/ai/providers/${encodeURIComponent(id)}/credential`, {
    method: "PUT",
    body: jsonBody({ expected_revision, secret }),
  });
}

export function removeAIProviderCredential(id: string, expected_revision: number): Promise<AIConnection> {
  return apiFetch<AIConnection>(`/ai/providers/${encodeURIComponent(id)}/credential`, {
    method: "DELETE",
    body: jsonBody({ expected_revision }),
  });
}

export function deleteAIProvider(id: string, expected_revision: number): Promise<{ id: string; deleted: boolean; generation: number; removal_required?: boolean }> {
  return apiFetch<{ id: string; deleted: boolean; generation: number; removal_required?: boolean }>(`/ai/providers/${encodeURIComponent(id)}`, {
    method: "DELETE",
    body: jsonBody({ expected_revision }),
  });
}

export function testAIProvider(id: string, expected_revision: number): Promise<{
  capability: string;
  connection_id: string;
  status: "passed" | "failed";
  validation_status: "passed" | "failed";
  validation_code: string;
  validation_revision: number;
  validated_at: string;
  revision: number;
  generation: number;
  provider: string;
  model: string;
}> {
  return apiFetch(`/ai/providers/${encodeURIComponent(id)}/test`, {
    method: "POST",
    body: jsonBody({ expected_revision, authorize_paid: true }),
  });
}

export function setAIRoute(input: {
  provider_route: "local" | "connection";
  connection_id?: string;
  fallback_policy?: "local" | "fail";
  expected_generation: number;
}): Promise<AIRoute> {
  return apiFetch<AIRoute>("/ai/routes/article_analysis", { method: "PUT", body: jsonBody(input) });
}

export function setPaidEnabled(enabled: boolean): Promise<{ enabled: boolean; updated_at: string }> {
  return apiFetch<{ enabled: boolean; updated_at: string }>("/budgets/paid-enabled", { method: "PUT", body: jsonBody({ enabled }) });
}

export function configureGlobalBudget(input: {
  period: "daily" | "monthly" | "lifetime";
  cap_type: "paid_requests" | "usd";
  cap_value: number;
}): Promise<AIBudgetLimit> {
  return apiFetch<AIBudgetLimit>("/budgets/limits", {
    method: "PUT",
    body: jsonBody({ scope_type: "global", scope_id: null, enabled: true, ...input }),
  });
}

export function listAIUsage(): Promise<ListResponse<AIProviderUsage>> {
  return apiList<AIProviderUsage>("/provider-usage?page_size=50");
}
