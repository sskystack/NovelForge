import { invoke, isTauri } from "@tauri-apps/api/core";

type RuntimeInfo = {
  status: "starting" | "ready" | "failed";
  apiOrigin: string | null;
  apiToken: string | null;
  error: string | null;
  logPath: string;
};

let apiOrigin = "";
let localToken = "";
let sessionToken = "";
const sessionKey = "novelforge.desktopSession";

export function isDesktop(): boolean {
  return isTauri() || window.location.protocol === "tauri:"
    || window.location.hostname === "tauri.localhost";
}

export class ApiError extends Error {
  constructor(message: string, public status: number, public code = "") {
    super(message);
  }
}

export async function initializeApi(restart = false): Promise<void> {
  // Web development continues to use Vite's same-origin proxy.
  apiOrigin = "";
  localToken = "";
  sessionToken = "";
  if (!isDesktop()) return;
  if (restart) await invoke("restart_runtime");
  const deadline = Date.now() + 55_000;
  while (Date.now() < deadline) {
    const runtime = await invoke<RuntimeInfo>("get_runtime_info");
    if (runtime.status === "failed") {
      throw new Error(`${runtime.error || "Local service startup failed"} Log: ${runtime.logPath}`);
    }
    if (runtime.status === "ready" && runtime.apiOrigin && runtime.apiToken) {
      const origin = new URL(runtime.apiOrigin);
      if (origin.protocol !== "http:" || origin.hostname !== "127.0.0.1") {
        throw new Error("The desktop host returned an invalid local service address.");
      }
      apiOrigin = origin.origin;
      localToken = runtime.apiToken;
      try { sessionToken = window.sessionStorage.getItem(sessionKey) || ""; }
      catch { /* A restricted WebView can still use an in-memory session. */ }
      return;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 150));
  }
  throw new Error("The local service did not start in time. Retry and inspect the application log.");
}

export function setSessionToken(token: string): void {
  sessionToken = token;
  if (!isDesktop()) return;
  try {
    if (token) window.sessionStorage.setItem(sessionKey, token);
    else window.sessionStorage.removeItem(sessionKey);
  } catch { /* Storage availability must not prevent signing in or signing out. */ }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<{ data: T; response: Response }> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (localToken) headers.set("X-NovelForge-Local-Token", localToken);
  if (sessionToken) headers.set("Authorization", `Bearer ${sessionToken}`);
  let response: Response;
  try {
    response = await fetch(`${apiOrigin}${path}`, {
      credentials: "include", ...init, headers: Object.fromEntries(headers.entries()),
      signal: init.signal ?? AbortSignal.timeout(120_000),
    });
  } catch {
    throw new Error("Cannot reach the local service. Check its status and retry.");
  }
  const text = await response.text();
  let data;
  try { data = text ? JSON.parse(text) : null; }
  catch { throw new ApiError(`The service returned an invalid response (HTTP ${response.status}).`, response.status); }
  if (!response.ok) {
    if (response.status === 401 && data?.code !== "LOCAL_AUTH_REQUIRED") {
      setSessionToken("");
      if (!path.startsWith("/api/v1/auth/")) window.dispatchEvent(new Event("novelforge:session-expired"));
    }
    throw new ApiError(`${data?.code ? `${data.code}: ` : ""}${data?.detail || `Request failed (HTTP ${response.status})`}`, response.status, data?.code);
  }
  return { data, response };
}

export function api<T>(path: string, init: RequestInit = {}) {
  return request<T>(`/api/v1${path}`, init);
}

export function csrfHeaders(): Record<string, string> {
  const cookie = document.cookie.split(";").map((item) => item.trim()).find((item) => item.startsWith("novelforge_csrf="));
  if (!cookie) return {};
  try { return { "X-CSRF-Token": decodeURIComponent(cookie.slice("novelforge_csrf=".length)) }; }
  catch { return {}; }
}
