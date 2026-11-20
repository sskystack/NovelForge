import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AgentWorkspace } from "./AgentWorkspace";
import { KnowledgeWorkspace } from "./KnowledgeWorkspace";
import { SettingsDialog } from "./SettingsDialog";

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const settings = {
  provider: "mock",
  base_url: "",
  chat_model: "mock-chat",
  embedding_model: "mock-embedding",
  timeout_seconds: 30,
  api_key_configured: true,
};
const run = {
  id: "run-1",
  prompt: "Check the lighthouse",
  status: "waiting_approval",
  provider: "mock",
  is_mock: true,
  model: "mock-chat",
  created_at: "2026-11-20T00:00:00Z",
  output: "",
  steps: [
    {
      id: "step-1",
      sequence: 1,
      kind: "tool",
      status: "waiting_approval",
      tool_name: "propose_canon",
      arguments: { name: "Lighthouse keeper" },
      result: null,
    },
  ],
  sources: [
    {
      chunk_id: "chunk-1",
      title: "The first letter",
      source_type: "chapter_version",
      source_revision: 2,
      content: "The lamp is green.",
    },
  ],
};
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Agent studio", () => {
  it("shows exact tool arguments, source revisions and an explicit mock label", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(json([run]));
    render(<AgentWorkspace novelId="novel-1" draftDirty={false} />);
    expect(await screen.findByText("Mock · deterministic demo")).toBeTruthy();
    expect(screen.getByText(/Lighthouse keeper/)).toBeTruthy();
    expect(screen.getByText(/chapter version · revision 2/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Approve action" })).toBeTruthy();
  });

  it("binds approval to the existing step and never resubmits tool arguments", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, init) =>
        String(input).endsWith("/decision") && init?.method === "POST"
          ? json({})
          : String(input).endsWith("/run-1")
            ? json({ ...run, status: "succeeded", steps: [] })
            : json([run]),
      );
    render(<AgentWorkspace novelId="novel-1" draftDirty={false} />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Approve action" }),
    );
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/novels/novel-1/agent/runs/run-1/steps/step-1/decision",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ approve: true }),
        }),
      ),
    );
  });

  it("blocks approval over unsaved manuscript edits but still permits rejecting", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) =>
        String(input).endsWith("/run-1")
          ? json(run)
          : String(input).endsWith("/decision")
            ? json({})
            : json([run]),
      );
    render(<AgentWorkspace novelId="novel-1" draftDirty />);
    expect(
      (
        await screen.findByRole("button", { name: "Approve action" })
      ).hasAttribute("disabled"),
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/steps/step-1/decision"),
        expect.objectContaining({ body: JSON.stringify({ approve: false }) }),
      ),
    );
  });

  it("can cancel a running task without approving any pending action", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) =>
        String(input).endsWith("/run-1")
          ? json({ ...run, status: "cancelled", steps: [] })
          : String(input).endsWith("/cancel")
            ? json({})
            : json([run]),
      );
    render(<AgentWorkspace novelId="novel-1" draftDirty={false} />);
    fireEvent.click(await screen.findByRole("button", { name: "Cancel task" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/run-1/cancel"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
    expect(await screen.findByText(/cancelled ·/)).toBeTruthy();
  });

  it("starts a bounded task with MCP disabled unless explicitly selected", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (_input, init) =>
        init?.method === "POST"
          ? json({ ...run, status: "queued", steps: [] }, 202)
          : json([]),
      );
    render(<AgentWorkspace novelId="novel-1" draftDirty={false} />);
    await screen.findByText("Your first task will appear here.");
    fireEvent.change(screen.getByLabelText("What would you like to work on?"), {
      target: { value: "Trace the lighthouse" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start task" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/novels/novel-1/agent/runs",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            prompt: "Trace the lighthouse",
            max_rounds: 6,
            max_tool_calls: 12,
            max_seconds: 60,
            max_tokens: 12000,
            use_mcp: false,
          }),
        }),
      ),
    );
  });

  it("offers retry after a real service failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      json({ detail: "Local agent service unavailable" }, 503),
    );
    render(<AgentWorkspace novelId="novel-1" draftDirty={false} />);
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Local agent service unavailable",
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
  });
});

describe("Knowledge workspace", () => {
  it("searches approved knowledge by default and displays inspectable sources", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) =>
        String(input).endsWith("/documents")
          ? json([])
          : json({ results: run.sources }),
      );
    render(<KnowledgeWorkspace novelId="novel-1" />);
    fireEvent.change(screen.getByLabelText("Search your story"), {
      target: { value: "灯塔" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("The first letter")).toBeTruthy();
    expect(screen.getByText("The lamp is green.")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("query=%E7%81%AF%E5%A1%94&include_drafts=false"),
      expect.anything(),
    );
  });
});

describe("Local model and MCP settings", () => {
  const setup = (
    override?: (url: string, init?: RequestInit) => Response | undefined,
  ) =>
    vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(
        async (input, init) =>
          override?.(String(input), init) ||
          (String(input).endsWith("/settings/ai") ? json(settings) : json([])),
      );

  it("reads masked settings and never overwrites a key when the key field is blank", async () => {
    const fetchMock = setup();
    render(<SettingsDialog onClose={vi.fn()} onSaved={vi.fn()} />);
    expect(await screen.findByText("A key is configured")).toBeTruthy();
    expect(
      (
        screen.getByPlaceholderText(
          "Leave empty to keep stored key",
        ) as HTMLInputElement
      ).value,
    ).toBe("");
    fireEvent.click(
      screen.getByRole("button", { name: "Save model settings" }),
    );
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/settings/ai",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({
            provider: "mock",
            base_url: "",
            chat_model: "mock-chat",
            embedding_model: "mock-embedding",
            timeout_seconds: 30,
          }),
        }),
      ),
    );
  });

  it("supports Escape and restores keyboard focus to the invoking control", async () => {
    setup();
    const close = vi.fn();
    const trigger = document.createElement("button");
    document.body.append(trigger);
    trigger.focus();
    const { unmount } = render(
      <SettingsDialog onClose={close} onSaved={vi.fn()} />,
    );
    await screen.findByText("A key is configured");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(close).toHaveBeenCalledOnce();
    unmount();
    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });

  it("clears a stored model key using an explicit empty secret", async () => {
    const fetchMock = setup((url, init) =>
      url.endsWith("/settings/ai") && init?.method === "PATCH"
        ? json({ ...settings, api_key_configured: false })
        : undefined,
    );
    render(<SettingsDialog onClose={vi.fn()} onSaved={vi.fn()} />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Clear stored model key" }),
    );
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/settings/ai",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ api_key: "" }),
        }),
      ),
    );
    expect(await screen.findByText("Stored model key cleared.")).toBeTruthy();
  });

  it("prevents default settings from overwriting unavailable saved configuration", async () => {
    setup(() => json({ detail: "Settings unavailable" }, 503));
    render(<SettingsDialog onClose={vi.fn()} onSaved={vi.fn()} />);
    expect(
      await screen.findByRole("button", { name: "Retry settings" }),
    ).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "Save model settings" }),
    ).toBeNull();
  });

  it("creates MCP servers disabled with an explicit tool allowlist", async () => {
    const server = {
      id: "server-1",
      name: "Research",
      transport: "stdio",
      command: "/local/server",
      args: [],
      url: "",
      allowed_tools: ["lookup"],
      enabled: false,
      status: "untested",
    };
    const fetchMock = setup((url, init) =>
      url.endsWith("/mcp/servers") && init?.method === "POST"
        ? json(server, 201)
        : undefined,
    );
    render(<SettingsDialog onClose={vi.fn()} onSaved={vi.fn()} />);
    await screen.findByText("A key is configured");
    fireEvent.click(screen.getByRole("tab", { name: "MCP servers" }));
    fireEvent.change(screen.getByLabelText("Server name"), {
      target: { value: "Research" },
    });
    fireEvent.change(screen.getByLabelText("Command"), {
      target: { value: "/local/server" },
    });
    fireEvent.change(screen.getByLabelText("Allowed tools (comma separated)"), {
      target: { value: "lookup" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Add disabled server" }),
    );
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/mcp/servers",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            name: "Research",
            transport: "stdio",
            command: "/local/server",
            args: [],
            url: "",
            allowed_tools: ["lookup"],
            enabled: false,
          }),
        }),
      ),
    );
    expect(
      await screen.findByText(
        "Server added disabled. Review its tools before enabling it.",
      ),
    ).toBeTruthy();
  });

  it("removes a server only after the explicit connection confirmation", async () => {
    const server = {
      id: "server-1",
      name: "Research",
      transport: "stdio",
      command: "/local/server",
      args: [],
      url: "",
      allowed_tools: [],
      enabled: false,
      status: "untested",
    };
    const fetchMock = setup((url, init) =>
      url.endsWith("/mcp/servers/server-1") && init?.method === "DELETE"
        ? new Response(null, { status: 204 })
        : url.endsWith("/mcp/servers")
          ? json([server])
          : undefined,
    );
    render(<SettingsDialog onClose={vi.fn()} onSaved={vi.fn()} />);
    await screen.findByText("A key is configured");
    fireEvent.click(screen.getByRole("tab", { name: "MCP servers" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE"),
    ).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Remove server" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/mcp/servers/server-1",
        expect.objectContaining({ method: "DELETE" }),
      ),
    );
    expect(
      await screen.findByText("Research removed. Story data was preserved."),
    ).toBeTruthy();
  });
});
