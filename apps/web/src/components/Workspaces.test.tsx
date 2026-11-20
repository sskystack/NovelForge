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

describe("创作助手", () => {
  it("shows exact tool arguments, source revisions and an explicit mock label", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(json([run]));
    render(<AgentWorkspace novelId="novel-1" draftDirty={false} />);
    expect(await screen.findByText("演示模型 · 固定输出")).toBeTruthy();
    expect(screen.getByText(/Lighthouse keeper/)).toBeTruthy();
    expect(screen.getByText(/chapter version · 修订 2/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "批准操作" })).toBeTruthy();
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
      await screen.findByRole("button", { name: "批准操作" }),
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
        await screen.findByRole("button", { name: "批准操作" })
      ).hasAttribute("disabled"),
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "拒绝" }));
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
    fireEvent.click(await screen.findByRole("button", { name: "取消任务" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/run-1/cancel"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
    expect(await screen.findByText(/已取消 ·/)).toBeTruthy();
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
    await screen.findByText("任务记录会显示在这里。");
    fireEvent.change(screen.getByLabelText("描述这次任务"), {
      target: { value: "Trace the lighthouse" },
    });
    fireEvent.click(screen.getByRole("button", { name: "开始任务" }));
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
    expect(screen.getByRole("button", { name: "重试" })).toBeTruthy();
  });
});

describe("Knowledge workspace", () => {
  it("selects a source and displays the exact revision and excerpt in its detail panel", async () => {
    const sources = [run.sources[0], { ...run.sources[0], chunk_id: "chunk-2", title: "第二份来源", source_revision: 7, content: "只有第二份来源包含的证据" }];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => String(input).endsWith("/documents") ? json([]) : json({ results: sources }));
    render(<KnowledgeWorkspace novelId="novel-1" />);
    fireEvent.change(screen.getByLabelText("检索故事资料"), { target: { value: "灯塔" } });
    fireEvent.click(screen.getByRole("button", { name: "搜索" }));
    fireEvent.click(await screen.findByRole("button", { name: /第二份来源/ }));
    const details = screen.getByRole("complementary", { name: "来源详情" });
    expect(details.textContent).toContain("第二份来源");
    expect(details.textContent).toContain("修订 7");
    expect(details.textContent).toContain("只有第二份来源包含的证据");
  });

  it("searches approved knowledge by default and displays inspectable sources", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) =>
        String(input).endsWith("/documents")
          ? json([])
          : json({ results: run.sources }),
      );
    render(<KnowledgeWorkspace novelId="novel-1" />);
    fireEvent.change(screen.getByLabelText("检索故事资料"), {
      target: { value: "灯塔" },
    });
    fireEvent.click(screen.getByRole("button", { name: "搜索" }));
    expect((await screen.findAllByText("The first letter")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("The lamp is green.").length).toBeGreaterThan(0);
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
    expect(await screen.findByText("已保存密钥")).toBeTruthy();
    expect(
      (
        screen.getByPlaceholderText(
          "留空保留现有密钥",
        ) as HTMLInputElement
      ).value,
    ).toBe("");
    fireEvent.click(
      screen.getByRole("button", { name: "保存模型设置" }),
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
    await screen.findByText("已保存密钥");
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
      await screen.findByRole("button", { name: "清除已保存的模型密钥" }),
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
    expect(await screen.findByText("已清除模型密钥。")).toBeTruthy();
  });

  it("prevents default settings from overwriting unavailable saved configuration", async () => {
    setup(() => json({ detail: "Settings unavailable" }, 503));
    render(<SettingsDialog onClose={vi.fn()} onSaved={vi.fn()} />);
    expect(
      await screen.findByRole("button", { name: "重新加载设置" }),
    ).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "保存模型设置" }),
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
    await screen.findByText("已保存密钥");
    fireEvent.click(screen.getByRole("tab", { name: "MCP 工具" }));
    fireEvent.change(screen.getByLabelText("连接名称"), {
      target: { value: "Research" },
    });
    fireEvent.change(screen.getByLabelText("启动命令"), {
      target: { value: "/local/server" },
    });
    fireEvent.change(screen.getByLabelText("允许的工具（逗号分隔）"), {
      target: { value: "lookup" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "添加为禁用连接" }),
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
        "连接已添加且保持禁用，请先检查工具权限。",
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
    await screen.findByText("已保存密钥");
    fireEvent.click(screen.getByRole("tab", { name: "MCP 工具" }));
    fireEvent.click(screen.getByRole("button", { name: "移除" }));
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE"),
    ).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "确认移除连接" }));
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
