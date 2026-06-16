import type {
  ChatResponse,
  Connector,
  Conversation,
  ConversationMessage,
  DashboardStats,
  DocumentItem,
  ReadinessResponse,
  SyncRun
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";
const DEFAULT_TIMEOUT_MS = 30_000;

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("docmind_token");
}

function authHeaders(): HeadersInit {
  const token = getStoredToken();
  if (token) {
    return {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`
    };
  }
  return {
    "Content-Type": "application/json",
    "X-Tenant-Id": process.env.NEXT_PUBLIC_TENANT_ID ?? "deep-bleue-ia",
    "X-User-Id": process.env.NEXT_PUBLIC_USER_ID ?? "alice",
    "X-User-Email": process.env.NEXT_PUBLIC_USER_EMAIL ?? "alice@deepbleue.ai",
    "X-User-Groups": process.env.NEXT_PUBLIC_USER_GROUPS ?? "everyone"
  };
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        ...authHeaders(),
        ...(init?.headers ?? {})
      },
      cache: "no-store"
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("L'opération a pris trop de temps. Veuillez réessayer.");
    }
    throw new Error("Serveur inaccessible. Vérifiez que l'application est démarrée.");
  } finally {
    clearTimeout(timeout);
  }

  if (response.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("docmind_token");
      localStorage.removeItem("docmind_user");
      window.location.href = "/login";
    }
    throw new Error("Session expirée. Reconnectez-vous.");
  }

  if (!response.ok) {
    const body = await response.text();
    let message = body || `Erreur API ${response.status}`;
    try {
      const parsed = JSON.parse(body) as { detail?: string; error?: { message?: string } };
      message = parsed.detail ?? parsed.error?.message ?? message;
    } catch {
      // Keep raw body as fallback.
    }
    throw new Error(message);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  readiness: () => request<ReadinessResponse>("/health/ready"),
  stats: () => request<DashboardStats>("/dashboard/stats"),
  connectors: () => request<Connector[]>("/connectors"),
  createLocalConnector: (name: string, rootPath: string) =>
    request<Connector>("/connectors", {
      method: "POST",
      body: JSON.stringify({ name, type: "local", config: { root_path: rootPath } })
    }),
  createConnector: (name: string, type: string, config: Record<string, unknown>) =>
    request<Connector>("/connectors", {
      method: "POST",
      body: JSON.stringify({ name, type, config })
    }),
  deleteConnector: (connectorId: string) =>
    request<void>(`/connectors/${connectorId}`, { method: "DELETE" }),
  syncConnector: (connectorId: string) =>
    request<SyncRun>(`/connectors/${connectorId}/sync`, {
      method: "POST",
      body: JSON.stringify({ mode: "foreground" })
    }, 5 * 60_000),
  syncRuns: (connectorId: string) => request<SyncRun[]>(`/connectors/${connectorId}/sync-runs`),
  documents: () => request<DocumentItem[]>("/documents?limit=100"),
  uploadDocument: async (file: File): Promise<DocumentItem> => {
    const token = getStoredToken();
    const headers: HeadersInit = token
      ? { "Authorization": `Bearer ${token}` }
      : {
          "X-Tenant-Id": process.env.NEXT_PUBLIC_TENANT_ID ?? "deep-bleue-ia",
          "X-User-Id": process.env.NEXT_PUBLIC_USER_ID ?? "alice",
        };
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_BASE_URL}/documents/upload`, {
      method: "POST",
      headers,
      body: formData,
    });
    if (!response.ok) {
      const body = await response.text();
      let message = "Upload impossible.";
      try { message = (JSON.parse(body) as { detail?: string }).detail ?? message; } catch {}
      throw new Error(message);
    }
    return response.json() as Promise<DocumentItem>;
  },
  chat: (question: string, topK = 8, conversationId?: string) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({
        question,
        top_k: topK,
        ...(conversationId && { conversation_id: conversationId })
      })
    }),
  conversations: () => request<Conversation[]>("/conversations"),
  deleteConversation: (id: string) =>
    request<void>(`/conversations/${id}`, { method: "DELETE" }),
  conversationMessages: (id: string) =>
    request<ConversationMessage[]>(`/conversations/${id}/messages`),
  login: async (email: string, password: string): Promise<{ access_token: string; email: string | null; display_name: string | null }> => {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    if (!response.ok) {
      const body = await response.text();
      let message = "Identifiants incorrects.";
      try { message = (JSON.parse(body) as { detail?: string }).detail ?? message; } catch {}
      throw new Error(message);
    }
    return response.json() as Promise<{ access_token: string; email: string | null; display_name: string | null }>;
  },
  register: async (email: string, password: string, displayName?: string): Promise<{ access_token: string; email: string | null; display_name: string | null }> => {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, display_name: displayName })
    });
    if (!response.ok) {
      const body = await response.text();
      let message = "Inscription impossible.";
      try { message = (JSON.parse(body) as { detail?: string }).detail ?? message; } catch {}
      throw new Error(message);
    }
    return response.json() as Promise<{ access_token: string; email: string | null; display_name: string | null }>;
  }
};
