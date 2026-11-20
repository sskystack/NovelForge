import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const native = vi.hoisted(() => ({ isTauri: vi.fn(), invoke: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => native);
import { api, initializeApi, setSessionToken } from "./api";

beforeEach(() => {
  native.isTauri.mockReset().mockReturnValue(false);
  native.invoke.mockReset();
  window.sessionStorage.clear(); window.localStorage.clear();
});
afterEach(() => vi.restoreAllMocks());

describe("API runtime boundary", () => {
  it("uses the same-origin web proxy and ignores stale remote origin preferences", async () => {
    window.localStorage.setItem("novelforge.apiOrigin", "https://untrusted.example");
    await initializeApi();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
    await api("/auth/me");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/auth/me", expect.anything());
    expect(native.invoke).not.toHaveBeenCalled();
  });

  it("uses the host-provided port and launch credential and restores the session on reload", async () => {
    native.isTauri.mockReturnValue(true);
    native.invoke.mockResolvedValue({ status: "ready", apiOrigin: "http://127.0.0.1:43891", apiToken: "launch-secret" });
    await initializeApi();
    setSessionToken("user-session");
    await initializeApi();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
    await api("/novels");
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:43891/api/v1/novels", expect.objectContaining({
      headers: expect.objectContaining({ authorization: "Bearer user-session", "x-novelforge-local-token": "launch-secret" }),
    }));
    expect(JSON.stringify(window.sessionStorage)).not.toContain("launch-secret");
  });

  it("reports native startup failures with the log location", async () => {
    native.isTauri.mockReturnValue(true);
    native.invoke.mockResolvedValue({ status: "failed", error: "Migration failed", logPath: "/test/logs/api.log" });
    await expect(initializeApi()).rejects.toThrow("Migration failed Log: /test/logs/api.log");
  });

  it("rejects a non-loopback address returned by the host", async () => {
    native.isTauri.mockReturnValue(true);
    native.invoke.mockResolvedValue({ status: "ready", apiOrigin: "https://untrusted.example", apiToken: "launch-secret" });
    await expect(initializeApi()).rejects.toThrow("invalid local service address");
  });

  it("turns HTML error pages into a readable service error", async () => {
    await initializeApi();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("<html>Bad gateway</html>", { status: 502 }));
    await expect(api("/novels")).rejects.toThrow("invalid response (HTTP 502)");
  });

  it("clears an expired desktop session and notifies the workspace", async () => {
    native.isTauri.mockReturnValue(true);
    native.invoke.mockResolvedValue({ status: "ready", apiOrigin: "http://127.0.0.1:43891", apiToken: "launch-secret" });
    await initializeApi(); setSessionToken("expired-session");
    const listener = vi.fn();
    window.addEventListener("novelforge:session-expired", listener);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ code: "INVALID_SESSION", detail: "Please sign in again" }), { status: 401 }));
    await expect(api("/novels")).rejects.toThrow("INVALID_SESSION");
    expect(window.sessionStorage.getItem("novelforge.desktopSession")).toBeNull();
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener("novelforge:session-expired", listener);
  });
});
