import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

const user = { id: "user-1", email: "writer@example.com", display_name: "Writer" };
const novel = { id: "novel-1", title: "Star Sea", premise: "", status: "active" };
const chapter = { id: "chapter-1", title: "第一章", chapter_number: 1, current_version: 1, status: "planned", summary: "" };
const emptyVersion = { id: "version-1", version_number: 1, content_format: "tiptap", tiptap_json: { type: "doc", content: [] }, markdown: null, created_at: "2026-11-07T00:00:00Z" };
const apiBase = "";

function response(data: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(data === null ? null : JSON.stringify(data), { status, headers: { "Content-Type": "application/json", ...headers } });
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); window.sessionStorage.clear(); });

describe("NovelForge workspace", () => {
  it("signs in, loads a project and displays the chapter editor", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/auth/me")) return response(user);
      if (url.endsWith("/novels")) return response([novel]);
      if (url.endsWith("/chapters?limit=100")) return response({ items: [chapter], next_cursor: null });
      if (url.endsWith("/chapters/chapter-1/versions")) return response([emptyVersion]);
      if (url.endsWith("/chapters/chapter-1")) return response(chapter, 200, { ETag: '"1"' });
      return response({}, 404);
    });
    render(<App />);

    expect(await screen.findByRole("heading", { name: "第一章" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "第一章" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(`${apiBase}/api/v1/novels/novel-1/chapters?limit=100`, expect.objectContaining({ credentials: "include" }));
  });

  it("signs in with CSRF cookies and submits credentials", async () => {
    Object.defineProperty(document, "cookie", { configurable: true, value: "novelforge_csrf=csrf-value" });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/auth/me")) return response({}, 401);
      if (url.endsWith("/auth/login")) return response(user);
      if (url.endsWith("/novels")) return response([]);
      if (url.endsWith("/novels/novel-1/chapters?limit=100")) return response({ items: [] });
      return response({}, 404);
    });
    render(<App />);
    fireEvent.change(await screen.findByLabelText("邮箱"), { target: { value: user.email } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "correct horse battery staple" } });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(`${apiBase}/api/v1/auth/login`, expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ "x-csrf-token": "csrf-value" }),
    })));
  });

  it("creates a project from the project rail", async () => {
    let created = false;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/auth/me")) return response(user);
      if (url.endsWith("/novels") && init?.method === "POST") { created = true; return response(novel, 201); }
      if (url.endsWith("/novels")) return response(created ? [novel] : []);
      if (url.endsWith("/chapters?limit=100")) return response({ items: [] });
      return response({}, 404);
    });
    render(<App />);
    await screen.findByRole("heading", { name: "创建第一部作品" });
    const input = screen.getAllByLabelText("快速新建作品名称")[0];
    fireEvent.change(input, { target: { value: "Star Sea" } });
    fireEvent.submit(input.closest("form")!);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(`${apiBase}/api/v1/novels`, expect.objectContaining({ method: "POST" })));
    expect(await screen.findByRole("heading", { name: "还没有章节" })).toBeTruthy();
  });

  it("saves the selected editor mode with the current ETag", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/auth/me")) return response(user);
      if (url.endsWith("/novels")) return response([novel]);
      if (url.endsWith("/chapters?limit=100")) return response({ items: [chapter] });
      if (url.endsWith("/chapters/chapter-1/versions")) return response([emptyVersion]);
      if (url.endsWith("/chapters/chapter-1") && init?.method === "PATCH") return response({ ...chapter, current_version: 2 }, 200, { ETag: '"2"' });
      if (url.endsWith("/chapters/chapter-1")) return response(chapter, 200, { ETag: '"1"' });
      return response({}, 404);
    });
    render(<App />);
    await screen.findByRole("heading", { name: "第一章" });
    fireEvent.click(screen.getByRole("button", { name: "Markdown" }));
    const source = screen.getByLabelText("Markdown 源码");
    fireEvent.change(source, { target: { value: "# Draft" } });
    fireEvent.click(screen.getAllByRole("button", { name: /保存/ }).find((button) => !button.hasAttribute("disabled"))!);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(`${apiBase}/api/v1/novels/novel-1/chapters/chapter-1`, expect.objectContaining({
      method: "PATCH",
      headers: expect.objectContaining({ "if-match": '"1"' }),
      body: JSON.stringify({ content_format: "markdown", markdown: "# Draft" }),
    })));
  });

  it("shows a generated draft for review before accepting it", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/auth/me")) return response(user);
      if (url.endsWith("/novels")) return response([novel]);
      if (url.endsWith("/chapters?limit=100")) return response({ items: [chapter] });
      if (url.endsWith("/chapters/chapter-1/versions")) return response([emptyVersion]);
      if (url.endsWith("/chapters/chapter-1")) return response(chapter, 200, { ETag: '"1"' });
      if (url.endsWith("/ai/generations") && init?.method === "POST") return response({ id: "generation-1", status: "succeeded", output: { markdown: "Preview only", source_ids: ["source-1"] }, expected_version: 1 }, 202);
      return response({}, 404);
    });
    render(<App />);
    await screen.findByRole("heading", { name: "第一章" });
    fireEvent.click(screen.getAllByRole("button", { name: /生成预览/ }).find((button) => !button.hasAttribute("disabled"))!);
    expect(await screen.findByRole("heading", { name: "生成内容预览" })).toBeTruthy();
    expect(screen.getByText("Preview only")).toBeTruthy();
    expect(screen.getByRole("button", { name: /采纳为新版本/ })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(`${apiBase}/api/v1/novels/novel-1/ai/generations`, expect.objectContaining({ method: "POST" }));
  });
});

function mockWorkspace(override?: (url: string, init?: RequestInit) => Promise<Response> | undefined) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const custom = override?.(url, init);
    if (custom) return custom;
    if (url.endsWith("/ready")) return response({ status: "ready" });
    if (url.endsWith("/auth/me")) return response(user);
    if (url.endsWith("/novels")) return response([novel]);
    if (url.endsWith("/chapters?limit=100")) return response({ items: [chapter, { ...chapter, id: "chapter-2", title: "Second", chapter_number: 2 }] });
    if (url.endsWith("/chapters/chapter-1/versions")) return response([emptyVersion]);
    if (url.endsWith("/chapters/chapter-1")) return response(chapter, 200, { ETag: '"1"' });
    return response({}, 404);
  });
}

describe("workspace runtime regressions", () => {
  it("opens guided project setup from the first-project empty state", async () => {
    mockWorkspace((url) => url.endsWith("/novels") ? Promise.resolve(response([])) : undefined);
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "新建作品向导" }));
    expect(await screen.findByRole("dialog", { name: "新建作品" })).toBeTruthy();
    expect(screen.getByLabelText("作品名称")).toBeTruthy();
  });

  it("does not open project setup over an unsaved chapter", async () => {
    mockWorkspace(); render(<App />);
    await screen.findByRole("heading", { name: "第一章" });
    fireEvent.click(screen.getByRole("button", { name: "Markdown" }));
    fireEvent.change(screen.getByLabelText("Markdown 源码"), { target: { value: "Keep this manuscript" } });
    fireEvent.click(screen.getByRole("button", { name: "新建作品" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect((await screen.findByRole("alert")).textContent).toContain("请先保存当前修改");
    expect((screen.getByLabelText("Markdown 源码") as HTMLTextAreaElement).value).toBe("Keep this manuscript");
  });

  it("keeps an unsaved manuscript when visiting a different workspace section", async () => {
    mockWorkspace((url) => url.endsWith("/knowledge/documents") ? Promise.resolve(response([])) : undefined);
    render(<App />);
    await screen.findByRole("heading", { name: "第一章" });
    fireEvent.click(screen.getByRole("button", { name: "Markdown" }));
    fireEvent.change(screen.getByLabelText("Markdown 源码"), { target: { value: "A draft that stays on the desk" } });
    fireEvent.click(screen.getByRole("button", { name: "知识与设定" }));
    await screen.findByRole("heading", { name: "知识与设定" });
    fireEvent.click(screen.getByRole("button", { name: /^书稿/ }));
    expect((screen.getByLabelText("Markdown 源码") as HTMLTextAreaElement).value).toBe("A draft that stays on the desk");
    expect(screen.getByText("有未保存修改")).toBeTruthy();
  });

  it("saves the draft with the desktop keyboard shortcut and current ETag", async () => {
    const fetchMock = mockWorkspace((url, init) => url.endsWith("/chapters/chapter-1") && init?.method === "PATCH" ? Promise.resolve(response({ ...chapter, current_version: 2 }, 200, { ETag: '"2"' })) : undefined);
    render(<App />);
    await screen.findByRole("heading", { name: "第一章" });
    fireEvent.click(screen.getByRole("button", { name: "Markdown" }));
    const source = screen.getByLabelText("Markdown 源码");
    fireEvent.change(source, { target: { value: "Saved from the keyboard" } });
    fireEvent.keyDown(source, { key: "s", metaKey: true });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/chapters/chapter-1"), expect.objectContaining({ method: "PATCH", headers: expect.objectContaining({ "if-match": '"1"' }), body: JSON.stringify({ content_format: "markdown", markdown: "Saved from the keyboard" }) })));
  });

  it("does not discard an unsaved draft when switching chapters", async () => {
    const fetchMock = mockWorkspace();
    render(<App />);
    await screen.findByRole("heading", { name: "第一章" });
    fireEvent.click(screen.getByRole("button", { name: "Markdown" }));
    fireEvent.change(screen.getByLabelText("Markdown 源码"), { target: { value: "不能丢失的正文" } });
    fireEvent.click(screen.getByRole("button", { name: "2. Second" }));
    expect((screen.getByLabelText("Markdown 源码") as HTMLTextAreaElement).value).toBe("不能丢失的正文");
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", expect.stringContaining("请先保存当前修改"));
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/chapters/chapter-2"))).toBe(false);
  });

  it("keeps edits made while a previous save is in flight dirty", async () => {
    let completeSave!: (value: Response) => void;
    mockWorkspace((url, init) => url.endsWith("/chapters/chapter-1") && init?.method === "PATCH"
      ? new Promise((resolve) => { completeSave = resolve; }) : undefined);
    render(<App />);
    await screen.findByRole("heading", { name: "第一章" });
    fireEvent.click(screen.getByRole("button", { name: "Markdown" }));
    fireEvent.change(screen.getByLabelText("Markdown 源码"), { target: { value: "First save" } });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(completeSave).toBeTypeOf("function"));
    fireEvent.change(screen.getByLabelText("Markdown 源码"), { target: { value: "Newer unsaved edit" } });
    completeSave(response({ ...chapter, current_version: 2 }, 200, { ETag: '"2"' }));
    await waitFor(() => expect(screen.getByRole("button", { name: "保存" }).hasAttribute("disabled")).toBe(false));
    expect((screen.getByLabelText("Markdown 源码") as HTMLTextAreaElement).value).toBe("Newer unsaved edit");
    expect(screen.getByText("有未保存修改")).toBeTruthy();
  });

  it("shows failed generation errors instead of an empty preview", async () => {
    mockWorkspace((url) => url.endsWith("/ai/generations") ? Promise.resolve(response({ id: "failed", status: "failed", output: {}, error_message: "Provider is not configured" }, 202)) : undefined);
    render(<App />);
    await screen.findByRole("heading", { name: "第一章" });
    fireEvent.click(screen.getByRole("button", { name: "生成预览" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Provider is not configured");
    expect(screen.queryByRole("heading", { name: "生成内容预览" })).toBeNull();
  });

  it("prevents accepting an AI preview over an unsaved draft", async () => {
    mockWorkspace((url) => url.endsWith("/ai/generations") ? Promise.resolve(response({ id: "draft", status: "succeeded", output: { markdown: "Preview" } }, 202)) : undefined);
    render(<App />);
    await screen.findByRole("heading", { name: "第一章" });
    fireEvent.click(screen.getByRole("button", { name: "生成预览" }));
    await screen.findByRole("heading", { name: "生成内容预览" });
    fireEvent.click(screen.getByRole("button", { name: "Markdown" }));
    expect(screen.getByRole("button", { name: "采纳为新版本" }).hasAttribute("disabled")).toBe(true);
  });

  it("reports startup connectivity errors with a retry action", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Network failed"));
    render(<App />);
    expect(await screen.findByRole("heading", { name: "NovelForge 无法启动" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "重试" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "登录" })).toBeNull();
  });
});
