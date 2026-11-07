import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

const user = { id: "user-1", email: "writer@example.com", display_name: "Writer" };
const novel = { id: "novel-1", title: "Star Sea", premise: "", status: "active" };
const chapter = { id: "chapter-1", title: "Chapter 1", chapter_number: 1, current_version: 1, status: "planned", summary: "" };
const emptyVersion = { id: "version-1", version_number: 1, content_format: "tiptap", tiptap_json: { type: "doc", content: [] }, markdown: null, created_at: "2026-11-07T00:00:00Z" };

function response(data: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(data === null ? null : JSON.stringify(data), { status, headers: { "Content-Type": "application/json", ...headers } });
}

afterEach(() => vi.restoreAllMocks());

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

    expect(await screen.findByRole("heading", { name: "Chapter 1" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Chapter 1" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/novels/novel-1/chapters?limit=100", expect.objectContaining({ credentials: "include" }));
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
    fireEvent.change(await screen.findByLabelText("Email"), { target: { value: user.email } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct horse battery staple" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/v1/auth/login", expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ "X-CSRF-Token": "csrf-value" }),
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
    await screen.findByRole("heading", { name: "Create your first project" });
    const input = screen.getAllByLabelText("New project title")[0];
    fireEvent.change(input, { target: { value: "Star Sea" } });
    fireEvent.submit(input.closest("form")!);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/v1/novels", expect.objectContaining({ method: "POST" })));
    expect(await screen.findByRole("heading", { name: "No chapters yet" })).toBeTruthy();
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
    await screen.findByRole("heading", { name: "Chapter 1" });
    fireEvent.click(screen.getByRole("button", { name: "Markdown" }));
    const source = screen.getByLabelText("Markdown source");
    fireEvent.change(source, { target: { value: "# Draft" } });
    fireEvent.click(screen.getAllByRole("button", { name: /Save/ }).find((button) => !button.hasAttribute("disabled"))!);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/v1/novels/novel-1/chapters/chapter-1", expect.objectContaining({
      method: "PATCH",
      headers: expect.objectContaining({ "If-Match": '"1"' }),
      body: JSON.stringify({ content_format: "markdown", markdown: "# Draft" }),
    })));
  });
});
