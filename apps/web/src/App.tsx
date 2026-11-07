import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { BookOpen, ChevronRight, LogOut, Plus, RotateCcw, Save } from "lucide-react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Markdown } from "@tiptap/markdown";

type User = { id: string; email: string; display_name: string };
type Novel = { id: string; title: string; premise: string; status: string };
type Chapter = { id: string; title: string; chapter_number: number | null; current_version: number; status: string; summary: string };
type Version = { id: string; version_number: number; content_format: "tiptap" | "markdown"; tiptap_json: Record<string, unknown> | null; markdown: string | null; created_at: string };
type Mode = "rich" | "markdown";

function parseMarkdown(markdown: string): Record<string, unknown> {
  const nodes: Record<string, unknown>[] = [];
  for (const block of markdown.split(/\n{2,}/).map((value) => value.trim()).filter(Boolean)) {
    const heading = block.match(/^(#{1,6})\s+(.+)$/);
    if (heading) nodes.push({ type: "heading", attrs: { level: heading[1].length }, content: [{ type: "text", text: heading[2] }] });
    else if (block.startsWith("> ")) nodes.push({ type: "blockquote", content: [{ type: "paragraph", content: [{ type: "text", text: block.slice(2) }] }] });
    else nodes.push({ type: "paragraph", content: [{ type: "text", text: block }] });
  }
  return { type: "doc", content: nodes.length ? nodes : [{ type: "paragraph" }] };
}

function serializeMarkdown(document: Record<string, unknown>): string {
  const blocks = Array.isArray(document.content) ? document.content as Record<string, unknown>[] : [];
  return blocks.map((block) => {
    const content = Array.isArray(block.content) ? block.content as Record<string, unknown>[] : [];
    const text = content.map((node) => String(node.text || "")).join("");
    if (block.type === "heading") return `${"#".repeat(Number((block.attrs as { level?: number } | undefined)?.level || 1))} ${text}`;
    if (block.type === "blockquote") return `> ${text}`;
    if (block.type === "bulletList" || block.type === "orderedList") return content.map((item, index) => {
      const children = Array.isArray(item.content) ? item.content as Record<string, unknown>[] : [];
      const itemText = children.flatMap((node) => Array.isArray(node.content) ? (node.content as Record<string, unknown>[]).map((leaf) => String(leaf.text || "")) : []).join("");
      return block.type === "orderedList" ? `${index + 1}. ${itemText}` : `- ${itemText}`;
    }).join("\n");
    return text;
  }).join("\n\n");
}

async function api<T>(path: string, init: RequestInit = {}): Promise<{ data: T; response: Response }> {
  const response = await fetch(`/api/v1${path}`, { credentials: "include", ...init, headers: { "Content-Type": "application/json", ...(init.headers || {}) } });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) throw new Error(`${data?.code ? `${data.code}: ` : ""}${data?.detail || "Request failed"}`);
  return { data, response };
}

function csrfHeaders(): Record<string, string> {
  const token = document.cookie.split("; ").find((item) => item.trim().startsWith("novelforge_csrf="))?.split("=")[1];
  return token ? { "X-CSRF-Token": decodeURIComponent(token) } : {};
}

function AuthScreen({ onAuthenticated }: { onAuthenticated: (user: User) => void }) {
  const [register, setRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError(""); setBusy(true);
    try {
      if (register) await api<User>("/auth/register", { method: "POST", body: JSON.stringify({ email, password, display_name: displayName }), headers: csrfHeaders() });
      const result = await api<User>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }), headers: csrfHeaders() });
      onAuthenticated(result.data);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Unable to sign in"); }
    finally { setBusy(false); }
  };
  return <main className="auth-shell"><section className="auth-card"><div className="brand-mark"><BookOpen size={20} /> NovelForge</div><h1>{register ? "Create your workspace" : "Welcome back"}</h1><p className="muted">Keep every chapter grounded in your approved story.</p><form onSubmit={submit}>{register && <label>Display name<input value={displayName} onChange={(e) => setDisplayName(e.target.value)} /></label>}<label>Email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label><label>Password<input type="password" required minLength={12} value={password} onChange={(e) => setPassword(e.target.value)} /></label>{error && <p className="error">{error}</p>}<button className="primary wide" type="submit" disabled={busy}>{busy ? "Working…" : register ? "Create account" : "Sign in"}</button></form><button className="link-button" onClick={() => setRegister((value) => !value)}>{register ? "Already have an account? Sign in" : "Create an account"}</button></section></main>;
}

function RichEditor({ value, onChange }: { value: Record<string, unknown>; onChange: (value: Record<string, unknown>) => void }) {
  const editor = useEditor({ extensions: [StarterKit, Markdown.configure({ markedOptions: { gfm: true } })], content: value, onUpdate: ({ editor: current }) => onChange(current.getJSON() as Record<string, unknown>) });
  useEffect(() => { if (editor && JSON.stringify(editor.getJSON()) !== JSON.stringify(value)) editor.commands.setContent(value); }, [editor, value]);
  return <EditorContent editor={editor} className="rich-editor" />;
}

function Workspace({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [novel, setNovel] = useState<Novel | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [chapter, setChapter] = useState<Chapter | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [mode, setMode] = useState<Mode>("rich");
  const [richContent, setRichContent] = useState<Record<string, unknown>>({ type: "doc", content: [] });
  const [markdown, setMarkdown] = useState("");
  const [etag, setEtag] = useState("");
  const [dirty, setDirty] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [loading, setLoading] = useState(true);

  const loadProject = useCallback(async (selected: Novel) => {
    setNovel(selected); setChapter(null); setVersions([]); setError("");
    const result = await api<{ items: Chapter[] }>(`/novels/${selected.id}/chapters?limit=100`);
    setChapters(result.data.items);
    if (result.data.items[0]) await loadChapterFor(selected, result.data.items[0]);
    else { setChapter(null); setEtag(""); setRichContent({ type: "doc", content: [] }); setMarkdown(""); setDirty(false); }
  }, []);
  const loadChapterFor = async (selectedNovel: Novel, selected: Chapter) => {
    setChapter(selected); setError("");
    const [detail, history] = await Promise.all([
      api<Chapter>(`/novels/${selectedNovel.id}/chapters/${selected.id}`),
      api<Version[]>(`/novels/${selectedNovel.id}/chapters/${selected.id}/versions`),
    ]);
    setEtag(detail.response.headers.get("ETag") || `"${detail.data.current_version}"`);
    setVersions(history.data);
    const latest = history.data[0];
    if (latest?.content_format === "markdown") {
      setMode("markdown"); setMarkdown(latest.markdown || "");
      setRichContent(parseMarkdown(latest.markdown || ""));
    } else {
      setMode("rich"); setRichContent(latest?.tiptap_json || { type: "doc", content: [] });
      setMarkdown(serializeMarkdown(latest?.tiptap_json || { type: "doc", content: [] }));
    }
    setDirty(false);
  };
  const loadChapter = useCallback(async (selected: Chapter) => { if (novel) await loadChapterFor(novel, selected); }, [novel]);

  useEffect(() => {
    let active = true;
    api<Novel[]>("/novels").then(async (result) => { if (active) { setNovels(result.data); if (result.data[0]) await loadProject(result.data[0]); } }).catch((requestError) => { if (active) setError(requestError instanceof Error ? requestError.message : "Unable to load projects"); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [loadProject]);

  const createNovel = async (event: FormEvent) => {
    event.preventDefault(); if (!newTitle.trim()) return;
    try { const result = await api<Novel>("/novels", { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ title: newTitle }) }); setNovels((items) => [result.data, ...items]); setNewTitle(""); await loadProject(result.data); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not create project"); }
  };

  const createChapter = async () => {
    if (!novel) return;
    const title = `Chapter ${chapters.length + 1}`;
    try { const result = await api<Chapter>(`/novels/${novel.id}/chapters`, { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ title, chapter_number: chapters.length + 1 }) }); setChapters((items) => [...items, result.data]); await loadChapter(result.data); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not create chapter"); }
  };

  const switchMode = (nextMode: Mode) => {
    if (nextMode === mode) return;
    if (nextMode === "markdown") setMarkdown(serializeMarkdown(richContent));
    else setRichContent(parseMarkdown(markdown));
    setMode(nextMode); setDirty(true); setNotice("");
  };

  const save = async () => {
    if (!novel || !chapter || !etag) return;
    setNotice(""); setError("");
    try {
      const payload = mode === "markdown" ? { content_format: "markdown", markdown } : { content_format: "tiptap", content: richContent };
      const result = await api<Chapter>(`/novels/${novel.id}/chapters/${chapter.id}`, { method: "PATCH", headers: { ...csrfHeaders(), "If-Match": etag }, body: JSON.stringify(payload) });
      setChapter(result.data); setEtag(result.response.headers.get("ETag") || `"${result.data.current_version}"`);
      setVersions((await api<Version[]>(`/novels/${novel.id}/chapters/${chapter.id}/versions`)).data);
      setDirty(false); setNotice("Saved");
    } catch (requestError) {
      if (requestError instanceof Error && requestError.message.includes("CHAPTER_VERSION_CONFLICT")) setError("This chapter changed elsewhere. Your local draft is preserved; reload the latest version before saving again.");
      else setError(requestError instanceof Error ? requestError.message : "Save failed");
    }
  };

  const restore = async (version: Version) => {
    if (!novel || !chapter) return;
    setError("");
    try { const result = await api<Chapter>(`/novels/${novel.id}/chapters/${chapter.id}/restore/${version.id}`, { method: "POST", headers: { ...csrfHeaders(), "If-Match": etag } }); setEtag(result.response.headers.get("ETag") || `"${result.data.current_version}"`); await loadChapterFor(novel, result.data); setNotice("Restored as a new version"); }
    catch (requestError) { setError(requestError instanceof Error && requestError.message.includes("CHAPTER_VERSION_CONFLICT") ? "The chapter changed elsewhere. Reload before restoring." : requestError instanceof Error ? requestError.message : "Restore failed"); }
  };

  const versionLabel = useMemo(() => chapter ? `Version ${chapter.current_version}` : "No chapter selected", [chapter]);
  return <main className="workspace"><header className="topbar"><div className="brand-mark"><BookOpen size={19} /> NovelForge</div><div className="top-actions"><span className="user-label">{user.display_name || user.email}</span><button className="icon-button" title="Sign out" onClick={onLogout}><LogOut size={17} /></button></div></header><div className="workspace-grid"><aside className="sidebar"><div className="sidebar-heading"><span>Projects</span><button className="icon-button" title="New project" onClick={() => document.getElementById("new-project")?.focus()}><Plus size={17} /></button></div><form className="new-project" onSubmit={createNovel}><input id="new-project" aria-label="New project title" placeholder="New project title" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} /></form>{novels.map((item) => <button className={`project-item ${novel?.id === item.id ? "selected" : ""}`} key={item.id} onClick={() => void loadProject(item)}><BookOpen size={16} /><span>{item.title}</span><ChevronRight size={14} /></button>)}</aside><section className="editor-area">{loading ? <div className="empty-state">Loading workspace…</div> : novel ? <><div className="editor-header"><div><p className="eyebrow">{novel.title}</p><h1>{chapter?.title || "No chapters yet"}</h1></div><div className="editor-actions"><span className="save-state">{dirty ? "Unsaved changes" : notice || versionLabel}</span><button className="primary" disabled={!dirty || !chapter} onClick={() => void save()}><Save size={16} /> Save</button></div></div><div className="chapter-tabs">{chapters.map((item) => <button className={chapter?.id === item.id ? "active" : ""} key={item.id} onClick={() => void loadChapter(item)}>{item.chapter_number ? `${item.chapter_number}. ` : ""}{item.title}</button>)}<button className="add-chapter" onClick={() => void createChapter()} title="Add chapter"><Plus size={15} /></button></div>{chapter && <><div className="mode-toggle" role="group" aria-label="Editor mode"><button className={mode === "rich" ? "active" : ""} aria-pressed={mode === "rich"} onClick={() => switchMode("rich")}>Rich text</button><button className={mode === "markdown" ? "active" : ""} aria-pressed={mode === "markdown"} onClick={() => switchMode("markdown")}>Markdown</button></div>{mode === "rich" ? <RichEditor value={richContent} onChange={(value) => { setRichContent(value); setDirty(true); setNotice(""); }} /> : <textarea className="markdown-editor" aria-label="Markdown source" value={markdown} onChange={(event) => { setMarkdown(event.target.value); setDirty(true); setNotice(""); }} spellCheck={false} />}</>}{!chapter && <button className="primary create-first" onClick={() => void createChapter()}><Plus size={16} /> Create chapter</button>}</> : <div className="empty-state"><BookOpen size={24} /><h1>Create your first project</h1><p>Your chapters and story data will stay in one workspace.</p></div>}{error && <p className="error toast" role="alert">{error}</p>}</section><aside className="history-panel"><div className="sidebar-heading"><span>Version history</span><span className="muted">{versions.length}</span></div>{versions.map((version) => <div className="version-row" key={version.id}><div><strong>Version {version.version_number}</strong><small>{version.content_format} · {new Date(version.created_at).toLocaleString()}</small></div><button className="icon-button" title={`Restore version ${version.version_number}`} aria-label={`Restore version ${version.version_number}`} disabled={!chapter || dirty || version.version_number === chapter.current_version} onClick={() => void restore(version)}><RotateCcw size={15} /></button></div>)}</aside></div></main>;
}

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  useEffect(() => { api<User>("/auth/me").then((result) => setUser(result.data)).catch(() => setUser(null)).finally(() => setChecked(true)); }, []);
  if (!checked) return <main className="auth-shell"><p className="muted">Loading NovelForge…</p></main>;
  if (!user) return <AuthScreen onAuthenticated={setUser} />;
  return <Workspace user={user} onLogout={() => { void api("/auth/logout", { method: "POST", headers: csrfHeaders() }).finally(() => setUser(null)); }} />;
}
