export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function authToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem("yes_sales_token") || "";
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const token = authToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (response.status === 401 && !path.startsWith("/auth/login")) {
    window.localStorage.removeItem("yes_sales_token");
    if (!window.location.pathname.startsWith("/login")) window.location.assign("/login");
  }
  if (!response.ok) {
    throw new Error(data?.error?.message || `Request failed (${response.status})`);
  }
  return data as T;
}
