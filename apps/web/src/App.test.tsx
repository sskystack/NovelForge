import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("shows the initial workspace state", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "创作工作台正在初始化" })).toBeTruthy();
  });
});
