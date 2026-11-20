import { MarkdownManager } from "@tiptap/markdown";
import StarterKit from "@tiptap/starter-kit";

const markdown = new MarkdownManager({ extensions: [StarterKit], markedOptions: { gfm: true } });

export function parseMarkdown(source: string): Record<string, unknown> {
  markdown.instance.walkTokens(markdown.instance.lexer(source), (token) => {
    if (["table", "image", "html"].includes(token.type)) {
      throw new Error("This chapter contains tables, images, or HTML. Keep editing in Markdown to preserve that content.");
    }
  });
  return markdown.parse(source) as Record<string, unknown>;
}

export function serializeMarkdown(document: Record<string, unknown>): string {
  return markdown.serialize(document);
}
