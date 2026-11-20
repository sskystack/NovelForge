import { describe, expect, it } from "vitest";
import { parseMarkdown, serializeMarkdown } from "./markdown";

describe("editor format conversion", () => {
  it("preserves supported rich text structure through a Markdown round trip", () => {
    const source = "# 标题\n\n**粗体**、*斜体*、[链接](https://example.com) 与 `代码`\n\n> 引用内容\n\n- 第一项\n- 第二项\n\n3. third\n4. fourth\n\n```python\nprint('hello')\n```";
    const document = parseMarkdown(source);
    const serialized = serializeMarkdown(document);
    expect(parseMarkdown(serialized)).toEqual(document);
    expect(serialized).toContain("引用内容");
    expect(serialized).toContain("**粗体**");
    expect(serialized).toContain("https://example.com");
    expect(serialized).toContain("print('hello')");
    expect(serialized).toContain("3. third");
  });

  it("handles empty chapters without inventing content", () => {
    expect(serializeMarkdown(parseMarkdown(""))).toBe("");
  });

  it("refuses a lossy conversion of unsupported Markdown instead of dropping it", () => {
    expect(() => parseMarkdown("| A | B |\n| --- | --- |\n| one | two |")).toThrow("preserve that content");
    expect(() => parseMarkdown("![illustration](https://example.com/image.png)")).toThrow("preserve that content");
  });
});
