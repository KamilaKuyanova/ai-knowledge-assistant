export interface Source {
  document_id: number;
  filename: string;
  page: number | null;
  quote: string;
  score: number;
}

export interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  answered: boolean;
  created_at: string;
}

export interface Chat {
  id: number;
  title: string;
  created_at: string;
}

export interface DocumentInfo {
  id: number;
  filename: string;
  status: "processing" | "ready" | "failed";
  error: string | null;
  page_count: number | null;
  chunk_count: number;
  created_at: string;
}

export interface UserSettings {
  top_k: number;
  min_score: number;
}

export interface User {
  id: number;
  email: string;
  settings: UserSettings;
}

const TOKEN_KEY = "kb_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY));

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

let onUnauthorized: () => void = () => {};
export const setUnauthorizedHandler = (fn: () => void) => (onUnauthorized = fn);

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (typeof init.body === "string") headers.set("Content-Type", "application/json");

  let res: Response;
  try {
    res = await fetch(`/api${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Нет связи с сервером");
  }
  if (!res.ok) {
    let detail = `Ошибка ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = "Проверьте правильность введённых данных";
    } catch {
      /* тело не JSON */
    }
    if (res.status === 401 && token) onUnauthorized();
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  register: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username: email, password }),
    }),
  me: () => request<User>("/auth/me"),
  saveSettings: (s: UserSettings) => request<User>("/auth/settings", { method: "PUT", body: JSON.stringify(s) }),

  documents: () => request<DocumentInfo[]>("/documents"),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<DocumentInfo>("/documents", { method: "POST", body: form });
  },
  deleteDocument: (id: number) => request<void>(`/documents/${id}`, { method: "DELETE" }),

  chats: () => request<Chat[]>("/chats"),
  createChat: () => request<Chat>("/chats", { method: "POST" }),
  deleteChat: (id: number) => request<void>(`/chats/${id}`, { method: "DELETE" }),
  messages: (id: number) => request<Message[]>(`/chats/${id}/messages`),
  ask: (id: number, question: string) =>
    request<Message>(`/chats/${id}/ask`, { method: "POST", body: JSON.stringify({ question }) }),
};
