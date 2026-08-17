import type { ListResponse } from "./types";

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

export function jsonBody(value: unknown): string { return JSON.stringify(value); }

export function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function shortId(value?: string | null): string { return value ? `${value.slice(0, 12)}…` : "—"; }
