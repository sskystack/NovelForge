import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectOnboarding } from "./ProjectOnboarding";

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const novel = {
  id: "new-novel",
  title: "The Keeper",
  premise: "A keeper loses the last letter.",
  status: "active",
};
const chapter = {
  id: "first-chapter",
  title: "The letter",
  chapter_number: 1,
  current_version: 1,
  status: "draft",
  summary: "",
};
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  document.cookie = "novelforge_csrf=; max-age=0";
});

function begin() {
  fireEvent.change(screen.getByLabelText("Story title"), {
    target: { value: "The Keeper" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
}

function review() {
  begin();
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
}

describe("Project onboarding", () => {
  it("does not render when closed, and cancels without creating anything", () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    const close = vi.fn();
    const created = vi.fn();
    const { rerender } = render(
      <ProjectOnboarding open={false} onClose={close} onCreated={created} />,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
    rerender(<ProjectOnboarding open onClose={close} onCreated={created} />);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(close).toHaveBeenCalledOnce();
    expect(created).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("preserves inputs when moving back and blocks blank titles", () => {
    render(<ProjectOnboarding open onClose={vi.fn()} onCreated={vi.fn()} />);
    expect(
      (screen.getByRole("button", { name: "Continue" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    begin();
    fireEvent.change(screen.getByLabelText(/First chapter goal/), {
      target: { value: "Find the letter" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(
      (screen.getByLabelText("Story title") as HTMLInputElement).value,
    ).toBe("The Keeper");
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(
      (screen.getByLabelText(/First chapter goal/) as HTMLTextAreaElement)
        .value,
    ).toBe("Find the letter");
  });

  it("saves the premise, language and genres, then creates an empty draft without an AI call", async () => {
    document.cookie = "novelforge_csrf=onboarding-token";
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) =>
        String(input).endsWith("/chapters")
          ? json(chapter, 201)
          : json(novel, 201),
      );
    const created = vi.fn();
    const close = vi.fn();
    render(<ProjectOnboarding open onClose={close} onCreated={created} />);
    fireEvent.change(screen.getByLabelText(/Premise/), {
      target: { value: novel.premise },
    });
    fireEvent.change(screen.getByLabelText(/Genres/), {
      target: { value: "Mystery， Fantasy, Mystery" },
    });
    fireEvent.change(screen.getByLabelText("Writing language"), {
      target: { value: "en" },
    });
    begin();
    fireEvent.change(screen.getByLabelText("First chapter title"), {
      target: { value: "The letter" },
    });
    fireEvent.change(screen.getByLabelText(/First chapter goal/), {
      target: { value: "Find the letter" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));
    await waitFor(() => expect(created).toHaveBeenCalledWith(novel, chapter));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/novels",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "x-csrf-token": "onboarding-token",
        }),
        body: JSON.stringify({
          title: "The Keeper",
          premise: novel.premise,
          genre: ["Mystery", "Fantasy"],
          language: "en",
          writing_preferences: { first_chapter_goal: "Find the letter" },
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/novels/new-novel/chapters",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          title: "The letter",
          chapter_number: 1,
          status: "draft",
        }),
      }),
    );
    expect(close).toHaveBeenCalledOnce();
  });

  it("can skip the first chapter and creates just a project", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(json(novel, 201));
    const created = vi.fn();
    render(<ProjectOnboarding open onClose={vi.fn()} onCreated={created} />);
    begin();
    fireEvent.click(
      screen.getByRole("button", { name: "Skip first chapter for now" }),
    );
    expect(
      screen.getByText("Project only · add chapters when you are ready"),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));
    await waitFor(() => expect(created).toHaveBeenCalledWith(novel, undefined));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("retains all fields after a project creation failure and can retry", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json({ detail: "Storage unavailable" }, 503))
      .mockImplementation(async (input) =>
        String(input).endsWith("/chapters")
          ? json(chapter, 201)
          : json(novel, 201),
      );
    const created = vi.fn();
    render(<ProjectOnboarding open onClose={vi.fn()} onCreated={created} />);
    review();
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Storage unavailable",
    );
    expect(created).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(
      (screen.getByLabelText("Story title") as HTMLInputElement).value,
    ).toBe("The Keeper");
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));
    await waitFor(() => expect(created).toHaveBeenCalledOnce());
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("retries only the chapter after a partial failure, never creating a duplicate project", async () => {
    let chapterCalls = 0;
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        if (!String(input).endsWith("/chapters")) return json(novel, 201);
        return ++chapterCalls === 1
          ? json({ detail: "Chapter unavailable" }, 503)
          : json(chapter, 201);
      });
    const created = vi.fn();
    render(<ProjectOnboarding open onClose={vi.fn()} onCreated={created} />);
    review();
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Chapter unavailable",
    );
    expect(screen.getByRole("status").textContent).toContain(
      "Your project is saved",
    );
    expect(created).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Retry first chapter" }),
    );
    await waitFor(() => expect(created).toHaveBeenCalledWith(novel, chapter));
    expect(
      fetchMock.mock.calls.filter(([input]) => input === "/api/v1/novels"),
    ).toHaveLength(1);
    expect(chapterCalls).toBe(2);
  });

  it.each(["Continue without chapter", "Close project setup", "Escape"])(
    "returns the saved project through %s after a chapter failure",
    async (action) => {
      const fetchMock = vi
        .spyOn(globalThis, "fetch")
        .mockImplementation(async (input) =>
          String(input).endsWith("/chapters")
            ? json({ detail: "Try later" }, 503)
            : json(novel, 201),
        );
      const created = vi.fn();
      const close = vi.fn();
      render(<ProjectOnboarding open onClose={close} onCreated={created} />);
      review();
      fireEvent.click(screen.getByRole("button", { name: "Create project" }));
      await screen.findByRole("alert");
      if (action === "Escape") fireEvent.keyDown(document, { key: "Escape" });
      else fireEvent.click(screen.getByRole("button", { name: action }));
      expect(created.mock.calls[0][0]).toEqual(novel);
      expect(close).toHaveBeenCalledOnce();
      expect(fetchMock).toHaveBeenCalledTimes(2);
    },
  );

  it("blocks double submission and closing while creation is in flight", async () => {
    let resolve!: (response: Response) => void;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
      () =>
        new Promise<Response>((done) => {
          resolve = done;
        }),
    );
    const close = vi.fn();
    const created = vi.fn();
    render(<ProjectOnboarding open onClose={close} onCreated={created} />);
    begin();
    fireEvent.click(
      screen.getByRole("button", { name: "Skip first chapter for now" }),
    );
    const create = screen.getByRole("button", { name: "Create project" });
    fireEvent.click(create);
    fireEvent.click(create);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(close).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(
      (
        screen.getByRole("button", {
          name: "Close project setup",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    resolve(json(novel, 201));
    await waitFor(() => expect(created).toHaveBeenCalledOnce());
  });

  it("traps keyboard focus and restores it when the dialog closes", () => {
    const trigger = document.createElement("button");
    document.body.append(trigger);
    trigger.focus();
    const close = vi.fn();
    const { unmount } = render(
      <ProjectOnboarding open onClose={close} onCreated={vi.fn()} />,
    );
    expect(document.activeElement).toBe(screen.getByRole("dialog"));
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Close project setup" }),
    );
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Cancel" }),
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(close).toHaveBeenCalledOnce();
    unmount();
    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });
});
