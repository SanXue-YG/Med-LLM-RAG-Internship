export type Envelope<T> = {
  code: number;
  message?: string;
  data: T;
  request_id?: string;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers || {}),
    },
  });
  const json = (await res.json()) as Envelope<T> & { detail?: unknown };
  if (!res.ok || (json.code !== undefined && json.code !== 0)) {
    const msg =
      json.message ||
      (typeof json.detail === "string" ? json.detail : null) ||
      `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return json.data;
}

export type SessionSummary = {
  session_id: string;
  title: string;
  turn_count: number;
  preview?: string;
  updated_at?: number;
  updated_at_iso?: string;
};

export type SessionTurn = {
  query: string;
  answer: string;
  created_at: string;
  meta?: Record<string, unknown> | null;
};

export type SessionDetail = {
  session_id: string;
  title?: string;
  turn_count: number;
  turns: SessionTurn[];
};

export type DocPayload = {
  slug: string;
  filename: string;
  title: string;
  markdown: string;
};

export const api = {
  listSessions: (q?: string) =>
    request<{ items: SessionSummary[]; count: number }>(
      `/api/v1/sessions${q ? `?q=${encodeURIComponent(q)}` : ""}`,
    ),
  createSession: () =>
    request<{ session_id: string; created_at: string }>("/api/v1/sessions", {
      method: "POST",
    }),
  getSession: (id: string) => request<SessionDetail>(`/api/v1/sessions/${id}`),
  deleteSession: (id: string) =>
    request<{ session_id: string; deleted: boolean }>(`/api/v1/sessions/${id}`, {
      method: "DELETE",
    }),
  ask: (query: string, sessionId?: string | null) =>
    request<{
      answer: string;
      sources?: Array<Record<string, unknown>>;
      session_id?: string;
      constraint_checks?: Record<string, unknown>;
    }>("/api/v1/qa", {
      method: "POST",
      body: JSON.stringify({
        query,
        session_id: sessionId || undefined,
        top_k: 5,
      }),
    }),
  health: () => request<Record<string, unknown>>("/health?check_ollama=true"),
  ready: () => request<Record<string, unknown>>("/ready"),
  ingestStatus: () => request<Record<string, unknown>>("/api/v1/ingest/status"),
  getDoc: (slug: string) => request<DocPayload>(`/api/v1/docs/${slug}`),
  upload: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<Record<string, unknown>>("/api/v1/ingest/upload", {
      method: "POST",
      body: fd,
    });
  },
};
