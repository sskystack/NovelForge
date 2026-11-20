import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  ArrowUpRight,
  BookOpen,
  Bot,
  Check,
  ChevronRight,
  FileText,
  Focus,
  History,
  Library,
  LoaderCircle,
  LogOut,
  PanelRight,
  Plus,
  RotateCcw,
  Save,
  Settings2,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Markdown } from "@tiptap/markdown";
import {
  ApiError,
  api,
  csrfHeaders,
  initializeApi,
  request,
  setSessionToken,
} from "./api";
import { parseMarkdown, serializeMarkdown } from "./markdown";
import { AgentWorkspace } from "./components/AgentWorkspace";
import { KnowledgeWorkspace } from "./components/KnowledgeWorkspace";
import { SettingsDialog } from "./components/SettingsDialog";
import { ProjectOnboarding } from "./components/ProjectOnboarding";

type User = { id: string; email: string; display_name: string };
type Novel = { id: string; title: string; premise: string; status: string };
type Chapter = {
  id: string;
  title: string;
  chapter_number: number | null;
  current_version: number;
  status: string;
  summary: string;
};
type Version = {
  id: string;
  version_number: number;
  content_format: "tiptap" | "markdown";
  tiptap_json: Record<string, unknown> | null;
  markdown: string | null;
  created_at: string;
};
type Mode = "rich" | "markdown";
type Generation = {
  id: string;
  status: string;
  output: { markdown?: string; source_ids?: string[] };
  expected_version: number | null;
  error_message?: string;
};
type Analysis = {
  id: string;
  chapter_version_id: string;
  summary_candidate: string;
  candidates: {
    events: unknown[];
    character_states: unknown[];
    consistency_warnings: unknown[];
  };
  proposal_ids: string[];
};
type AnalysisProposal = {
  id: string;
  proposal_type: string;
  payload: Record<string, unknown>;
  evidence: Record<string, unknown>;
  status: string;
};

function AuthScreen({
  onAuthenticated,
}: {
  onAuthenticated: (user: User) => void;
}) {
  const [register, setRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (register)
        await api<User>("/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, password, display_name: displayName }),
          headers: csrfHeaders(),
        });
      const result = await api<User>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
        headers: csrfHeaders(),
      });
      setSessionToken(
        result.response.headers.get("X-NovelForge-Session") || "",
      );
      onAuthenticated(result.data);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "登录失败，请检查输入后重试。",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="auth-shell">
      <section className="auth-introduction">
        <div className="brand-mark">
          <BookOpen size={23} /> NovelForge
        </div>
        <p className="eyebrow">NovelForge · macOS</p>
        <h2>
          专注故事，
          <br />
          从这一章
          <br />
          <em>继续。</em>
        </h2>
        <p>
          在本地整理长篇书稿，检索故事资料，逐步审核助手建议。
        </p>
        <div className="auth-principles">
          <span>
            <FileText size={16} /> 版本记录
          </span>
          <span>
            <ShieldCheck size={16} /> 作者审核
          </span>
        </div>
      </section>
      <section className="auth-card">
        <span className="badge">本地创作工作空间</span>
        <h1>{register ? "创建本地账户" : "登录工作空间"}</h1>
        <p className="muted">
          书稿、设定与创作助手，都在这里。
        </p>
        <form onSubmit={submit}>
          {register && (
            <label>
              显示名称
              <input
                autoComplete="name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </label>
          )}
          <label>
            邮箱
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label>
            密码
            <input
              type="password"
              autoComplete={register ? "new-password" : "current-password"}
              required
              minLength={12}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {register && (
            <p className="field-hint">
              密码至少 12 个字符。账户保存在本地服务。
            </p>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button className="primary wide" type="submit" disabled={busy}>
            {busy ? "处理中…" : register ? "创建账户" : "登录"}
            <ArrowUpRight size={16} />
          </button>
        </form>
        <button
          className="link-button"
          onClick={() => setRegister((value) => !value)}
        >
          {register ? "已有账户？登录" : "注册本地账户"}
        </button>
        <p className="auth-footnote">正文与设定始终由你决定。</p>
      </section>
    </main>
  );
}

function RichEditor({
  value,
  onChange,
}: {
  value: Record<string, unknown>;
  onChange: (value: Record<string, unknown>) => void;
}) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Markdown.configure({ markedOptions: { gfm: true } }),
    ],
    content: value,
    editorProps: {
      attributes: {
        "aria-label": "章节正文",
        role: "textbox",
        "aria-multiline": "true",
        "data-placeholder": "从第一句话开始……",
      },
    },
    onUpdate: ({ editor: current }) =>
      onChange(current.getJSON() as Record<string, unknown>),
  });
  useEffect(() => {
    if (editor && JSON.stringify(editor.getJSON()) !== JSON.stringify(value))
      editor.commands.setContent(value, { emitUpdate: false });
  }, [editor, value]);
  return <EditorContent editor={editor} className="rich-editor" />;
}

function Workspace({
  user,
  onLogout,
}: {
  user: User;
  onLogout: () => Promise<void>;
}) {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [novel, setNovel] = useState<Novel | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [chapter, setChapter] = useState<Chapter | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [mode, setMode] = useState<Mode>("rich");
  const [richContent, setRichContent] = useState<Record<string, unknown>>({
    type: "doc",
    content: [],
  });
  const [markdown, setMarkdown] = useState("");
  const [etag, setEtag] = useState("");
  const [dirty, setDirty] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [loading, setLoading] = useState(true);
  const [generation, setGeneration] = useState<Generation | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [analysisProposals, setAnalysisProposals] = useState<
    AnalysisProposal[]
  >([]);
  const [busyAI, setBusyAI] = useState(false);
  const [serviceStatus, setServiceStatus] = useState<
    "checking" | "ready" | "unavailable"
  >("checking");
  const [selecting, setSelecting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [view, setView] = useState<"manuscript" | "knowledge" | "agent">(
    "manuscript",
  );
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [inspectorTab, setInspectorTab] = useState<"history" | "assistant">(
    "history",
  );
  const [focusMode, setFocusMode] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [provider, setProvider] = useState<string | null>(null);
  const closeSettings = useCallback(() => setSettingsOpen(false), []);
  const closeOnboarding = useCallback(() => setOnboardingOpen(false), []);
  const selection = useRef(0);
  const editRevision = useRef(0);
  const dirtyRef = useRef(false);
  const mutation = useRef(false);
  const refreshProvider = useCallback(() => {
    void api<{ provider: string }>("/settings/ai")
      .then(({ data }) => setProvider(data.provider))
      .catch(() => setProvider(null));
  }, []);
  useEffect(() => {
    refreshProvider();
  }, [refreshProvider]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (dirtyRef.current || mutation.current) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);
  const setDocumentDirty = useCallback((value: boolean) => {
    if (value) editRevision.current += 1;
    dirtyRef.current = value;
    setDirty(value);
  }, []);
  const canNavigate = () => {
    if (dirtyRef.current || mutation.current) {
      setError(
        "请先保存当前修改，再切换章节、创建作品或退出。",
      );
      return false;
    }
    return true;
  };

  useEffect(() => {
    let active = true;
    const check = () =>
      void request("/ready")
        .then(() => {
          if (active) setServiceStatus("ready");
        })
        .catch(() => {
          if (active) setServiceStatus("unavailable");
        });
    check();
    const timer = window.setInterval(check, 10_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const loadChapterFor = useCallback(
    async (
      selectedNovel: Novel,
      selected: Chapter,
      requestId = ++selection.current,
    ) => {
      setSelecting(true);
      setError("");
      try {
        const [detail, history] = await Promise.all([
          api<Chapter>(`/novels/${selectedNovel.id}/chapters/${selected.id}`),
          api<Version[]>(
            `/novels/${selectedNovel.id}/chapters/${selected.id}/versions`,
          ),
        ]);
        if (requestId !== selection.current) return;
        const latest = history.data.find(
          (version) => version.version_number === detail.data.current_version,
        );
        if (!latest)
          throw new Error(
            "章节在加载时已更新，请重新选择章节。",
          );
        setChapter(detail.data);
        setEtag(
          detail.response.headers.get("ETag") ||
            `"${detail.data.current_version}"`,
        );
        setVersions(history.data);
        if (latest.content_format === "markdown") {
          setMode("markdown");
          setMarkdown(latest.markdown || "");
          setRichContent({ type: "doc", content: [] });
        } else {
          const content = latest.tiptap_json || { type: "doc", content: [] };
          setMode("rich");
          setRichContent(content);
          setMarkdown(serializeMarkdown(content));
        }
        setGeneration(null);
        setAnalysis(null);
        setAnalysisProposals([]);
        setBusyAI(false);
        setDocumentDirty(false);
        setNotice("");
      } catch (requestError) {
        if (requestId === selection.current)
          setError(
            requestError instanceof Error
              ? requestError.message
              : "无法加载章节。",
          );
      } finally {
        if (requestId === selection.current) setSelecting(false);
      }
    },
    [setDocumentDirty],
  );

  const loadProject = useCallback(
    async (selected: Novel) => {
      const requestId = ++selection.current;
      setSelecting(true);
      setError("");
      try {
        const result = await api<{ items: Chapter[] }>(
          `/novels/${selected.id}/chapters?limit=100`,
        );
        if (requestId !== selection.current) return;
        setNovel(selected);
        setChapter(null);
        setVersions([]);
        setChapters(result.data.items);
        setGeneration(null);
        setAnalysis(null);
        setAnalysisProposals([]);
        setBusyAI(false);
        if (result.data.items[0])
          await loadChapterFor(selected, result.data.items[0], requestId);
        else {
          setEtag("");
          setRichContent({ type: "doc", content: [] });
          setMarkdown("");
          setDocumentDirty(false);
        }
      } catch (requestError) {
        if (requestId === selection.current)
          setError(
            requestError instanceof Error
              ? requestError.message
              : "无法加载作品。",
          );
      } finally {
        if (requestId === selection.current) setSelecting(false);
      }
    },
    [loadChapterFor, setDocumentDirty],
  );
  const loadChapter = async (selected: Chapter) => {
    if (novel && canNavigate()) await loadChapterFor(novel, selected);
  };

  useEffect(() => {
    let active = true;
    api<Novel[]>("/novels")
      .then(async (result) => {
        if (active) {
          setNovels(result.data);
          if (result.data[0]) await loadProject(result.data[0]);
        }
      })
      .catch((requestError) => {
        if (active)
          setError(
            requestError instanceof Error
              ? requestError.message
              : "无法加载作品列表。",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [loadProject]);

  const createNovel = async (event: FormEvent) => {
    event.preventDefault();
    if (!newTitle.trim() || !canNavigate()) return;
    try {
      const result = await api<Novel>("/novels", {
        method: "POST",
        headers: csrfHeaders(),
        body: JSON.stringify({ title: newTitle }),
      });
      setNovels((items) => [result.data, ...items]);
      setNewTitle("");
      await loadProject(result.data);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "无法创建作品。",
      );
    }
  };

  const createChapter = async () => {
    if (!novel || !canNavigate()) return;
    const chapterNumber =
      Math.max(0, ...chapters.map((item) => item.chapter_number || 0)) + 1;
    const title = `第 ${chapterNumber} 章`;
    try {
      const result = await api<Chapter>(`/novels/${novel.id}/chapters`, {
        method: "POST",
        headers: csrfHeaders(),
        body: JSON.stringify({ title, chapter_number: chapterNumber }),
      });
      setChapters((items) => [...items, result.data]);
      await loadChapterFor(novel, result.data);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "无法创建章节。",
      );
    }
  };

  const switchMode = (nextMode: Mode) => {
    if (nextMode === mode) return;
    try {
      if (nextMode === "markdown") setMarkdown(serializeMarkdown(richContent));
      else setRichContent(parseMarkdown(markdown));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "无法安全转换当前内容，请保留原格式。",
      );
      return;
    }
    setMode(nextMode);
    setDocumentDirty(true);
    setNotice("");
  };

  const save = async () => {
    if (!novel || !chapter || !etag || mutation.current) return;
    mutation.current = true;
    setSaving(true);
    const revision = editRevision.current;
    setNotice("");
    setError("");
    try {
      const payload =
        mode === "markdown"
          ? { content_format: "markdown", markdown }
          : { content_format: "tiptap", content: richContent };
      const result = await api<Chapter>(
        `/novels/${novel.id}/chapters/${chapter.id}`,
        {
          method: "PATCH",
          headers: { ...csrfHeaders(), "If-Match": etag },
          body: JSON.stringify(payload),
        },
      );
      setChapter(result.data);
      setEtag(
        result.response.headers.get("ETag") ||
          `"${result.data.current_version}"`,
      );
      setGeneration(null);
      setAnalysis(null);
      setAnalysisProposals([]);
      if (revision === editRevision.current) {
        setDocumentDirty(false);
        setNotice("已保存");
      }
      try {
        setVersions(
          (
            await api<Version[]>(
              `/novels/${novel.id}/chapters/${chapter.id}/versions`,
            )
          ).data,
        );
      } catch {
        setError(
          "正文已保存，但版本列表刷新失败。恢复历史前请重新加载。",
        );
      }
    } catch (requestError) {
      if (
        requestError instanceof Error &&
        requestError.message.includes("CHAPTER_VERSION_CONFLICT")
      )
        setError(
          "章节已在其他位置更新。当前草稿已保留，请核对最新版本后再保存。",
        );
      else
        setError(
          requestError instanceof Error ? requestError.message : "保存失败。",
        );
    } finally {
      mutation.current = false;
      setSaving(false);
    }
  };

  const restore = async (version: Version) => {
    if (!novel || !chapter || !canNavigate()) return;
    mutation.current = true;
    setSaving(true);
    setError("");
    try {
      const result = await api<Chapter>(
        `/novels/${novel.id}/chapters/${chapter.id}/restore/${version.id}`,
        { method: "POST", headers: { ...csrfHeaders(), "If-Match": etag } },
      );
      setEtag(
        result.response.headers.get("ETag") ||
          `"${result.data.current_version}"`,
      );
      await loadChapterFor(novel, result.data);
      setNotice("历史内容已恢复为新版本。");
    } catch (requestError) {
      setError(
        requestError instanceof Error &&
          requestError.message.includes("CHAPTER_VERSION_CONFLICT")
          ? "章节已被更新，请重新加载后再恢复历史。"
          : requestError instanceof Error
            ? requestError.message
            : "恢复失败。",
      );
    } finally {
      mutation.current = false;
      setSaving(false);
    }
  };

  const generateDraft = async () => {
    if (!novel || !chapter || dirtyRef.current || mutation.current || busyAI)
      return;
    const requestId = selection.current;
    setBusyAI(true);
    setError("");
    try {
      const result = await api<Generation>(
        `/novels/${novel.id}/ai/generations`,
        {
          method: "POST",
          headers: csrfHeaders(),
          body: JSON.stringify({
            chapter_id: chapter.id,
            task_profile: "writing",
            instructions: "Continue this chapter in the established voice.",
          }),
        },
      );
      if (requestId !== selection.current) return;
      if (result.data.status !== "succeeded")
        throw new Error(
          result.data.error_message ||
            "生成失败，正文没有改动。",
        );
      setGeneration(result.data);
    } catch (requestError) {
      if (requestId === selection.current)
        setError(
          requestError instanceof Error
            ? requestError.message
            : "生成失败。",
        );
    } finally {
      if (requestId === selection.current) setBusyAI(false);
    }
  };

  const acceptDraft = async () => {
    if (!novel || !chapter || !generation || !canNavigate()) return;
    mutation.current = true;
    setSaving(true);
    try {
      await api(`/novels/${novel.id}/ai/generations/${generation.id}/accept`, {
        method: "POST",
        headers: csrfHeaders(),
        body: JSON.stringify({ expected_version: chapter.current_version }),
      });
      setGeneration(null);
      await loadChapterFor(novel, chapter);
      setNotice("预览已采纳为正文新版本。");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "无法采纳预览。",
      );
    } finally {
      mutation.current = false;
      setSaving(false);
    }
  };

  const analyzeLatest = async () => {
    if (
      !novel ||
      !versions[0] ||
      dirtyRef.current ||
      mutation.current ||
      busyAI
    )
      return;
    const requestId = selection.current;
    setBusyAI(true);
    try {
      const result = await api<Analysis>(
        `/novels/${novel.id}/ai/analysis/${versions[0].id}`,
        { method: "POST", headers: csrfHeaders() },
      );
      const proposals = await api<AnalysisProposal[]>(
        `/novels/${novel.id}/ai/analysis-proposals?chapter_version_id=${versions[0].id}`,
      );
      if (requestId !== selection.current) return;
      setAnalysis(result.data);
      setAnalysisProposals(proposals.data);
    } catch (requestError) {
      if (requestId === selection.current)
        setError(
          requestError instanceof Error
            ? requestError.message
            : "版本分析失败。",
        );
    } finally {
      if (requestId === selection.current) setBusyAI(false);
    }
  };

  const decideAnalysisProposal = async (
    proposal: AnalysisProposal,
    decision: "approve" | "reject",
  ) => {
    if (!novel) return;
    try {
      await api(
        `/novels/${novel.id}/ai/analysis-proposals/${proposal.id}/${decision}`,
        {
          method: "POST",
          headers: csrfHeaders(),
          body: JSON.stringify({ reason: "Reviewed in chapter workspace" }),
        },
      );
      setAnalysisProposals((items) =>
        items.filter((item) => item.id !== proposal.id),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "无法审核提案。",
      );
    }
  };

  const applySummaryCandidate = async () => {
    if (!novel || !chapter || !analysis || !canNavigate()) return;
    if (analysis.chapter_version_id !== versions[0]?.id) {
      setError(
        "这份分析来自旧版本，请重新分析最新保存的正文。",
      );
      return;
    }
    mutation.current = true;
    setSaving(true);
    try {
      const result = await api<Chapter>(
        `/novels/${novel.id}/chapters/${chapter.id}`,
        {
          method: "PATCH",
          headers: { ...csrfHeaders(), "If-Match": etag },
          body: JSON.stringify({ summary: analysis.summary_candidate }),
        },
      );
      setChapter(result.data);
      setEtag(
        result.response.headers.get("ETag") ||
          `"${result.data.current_version}"`,
      );
      setVersions(
        (
          await api<Version[]>(
            `/novels/${novel.id}/chapters/${chapter.id}/versions`,
          )
        ).data,
      );
      setNotice("摘要已采纳为章节新版本。");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "无法采纳摘要。",
      );
    } finally {
      mutation.current = false;
      setSaving(false);
    }
  };

  const reconnect = async () => {
    setServiceStatus("checking");
    try {
      await initializeApi(true);
      await request("/ready");
      setServiceStatus("ready");
      setError("");
    } catch (requestError) {
      setServiceStatus("unavailable");
      setError(
        requestError instanceof Error
          ? requestError.message
          : "本地服务无法重新启动。",
      );
    }
  };
  const signOut = async () => {
    if (!canNavigate()) return;
    try {
      await onLogout();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "退出失败，请重试。",
      );
    }
  };

  const versionLabel = useMemo(
    () =>
      chapter ? `版本 ${chapter.current_version}` : "未选择章节",
    [chapter],
  );
  const plainText = useMemo(
    () => (mode === "markdown" ? markdown : serializeMarkdown(richContent)),
    [mode, markdown, richContent],
  );
  const wordCount = useMemo(
    () =>
      (
        plainText.match(/[\u3400-\u9fff]|[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)*/g) ||
        []
      ).length,
    [plainText],
  );
  return (
    <main
      className={`workspace ${focusMode ? "focus-mode" : ""} ${inspectorOpen ? "inspector-open" : ""} ${view !== "manuscript" ? "tools-view" : ""}`}
      onKeyDown={(event) => {
        if (
          (event.metaKey || event.ctrlKey) &&
          event.key.toLowerCase() === "s"
        ) {
          event.preventDefault();
          if (dirty && !saving) void save();
        }
      }}
    >
      <a href="#main-content" className="skip-link">
        跳到正文工作区
      </a>
      <header className="topbar">
        <div className="topbar-brand">
          <div className="brand-mark">
            <BookOpen size={20} /> NovelForge
          </div>
          <span className="topbar-divider" />
          <span className="workspace-label">创作工作台</span>
        </div>
        <div className="top-actions">
          <span className="service-label">
            <i
              className={`service-indicator ${serviceStatus}`}
              aria-label={`API ${serviceStatus}`}
              title={`API ${serviceStatus}`}
            />
            <span>
              {serviceStatus === "ready"
                ? "本地服务正常"
                : serviceStatus === "checking"
                  ? "正在连接…"
                  : "本地服务离线"}
            </span>
          </span>
          {serviceStatus === "unavailable" && (
            <button className="secondary" onClick={() => void reconnect()}>
              重新连接
            </button>
          )}
          <button
            className={`provider-button ${provider === "mock" ? "demo" : ""}`}
            onClick={() => setSettingsOpen(true)}
          >
            {provider === "mock"
              ? "演示模型"
              : provider
                ? "模型已配置"
                : "配置模型"}
          </button>
          <span className="user-label">{user.display_name || user.email}</span>
          <button
            className="icon-button"
            title="设置与连接"
            onClick={() => setSettingsOpen(true)}
          >
            <Settings2 size={18} />
          </button>
          <button
            className="icon-button"
            title="退出登录"
            onClick={() => void signOut()}
          >
            <LogOut size={17} />
          </button>
        </div>
      </header>
      <div className="workspace-grid">
        <aside className="sidebar" aria-label="项目导航">
          <div className="sidebar-section">
            <div className="sidebar-heading">
              <span>作品库</span>
              <button
                className="icon-button"
                title="新建作品"
                onClick={() => {
                  if (canNavigate()) setOnboardingOpen(true);
                }}
              >
                <Plus size={16} />
              </button>
            </div>
            <form className="new-project" onSubmit={createNovel}>
              <input
                id="new-project"
                aria-label="快速新建作品名称"
                placeholder="快速新建作品…"
                value={newTitle}
                onChange={(event) => setNewTitle(event.target.value)}
              />
              <button
                type="submit"
                className="icon-button"
                title="创建作品"
                disabled={!newTitle.trim()}
              >
                <Plus size={15} />
              </button>
            </form>
            <div className="project-list">
              {novels.map((item) => (
                <button
                  title={item.title}
                  className={`project-item ${novel?.id === item.id ? "selected" : ""}`}
                  key={item.id}
                  onClick={() => {
                    if (canNavigate()) void loadProject(item);
                  }}
                >
                  <BookOpen size={17} />
                  <span>{item.title}</span>
                  <ChevronRight size={14} />
                </button>
              ))}
            </div>
          </div>
          {novel && (
            <>
              <nav className="workspace-nav" aria-label="工作区">
                <button
                  className={view === "manuscript" ? "active" : ""}
                  aria-current={view === "manuscript" ? "page" : undefined}
                  onClick={() => setView("manuscript")}
                >
                  <FileText size={17} />
                  书稿<span>{chapters.length}</span>
                </button>
                <button
                  className={view === "knowledge" ? "active" : ""}
                  aria-current={view === "knowledge" ? "page" : undefined}
                  onClick={() => setView("knowledge")}
                >
                  <Library size={17} />
                  知识与设定
                </button>
                <button
                  className={view === "agent" ? "active" : ""}
                  aria-current={view === "agent" ? "page" : undefined}
                  onClick={() => setView("agent")}
                >
                  <Bot size={18} />
                  创作助手
                </button>
              </nav>
              <div className="chapter-navigation">
                <div className="sidebar-heading">
                  <span>章节目录</span>
                  <button
                    className="icon-button"
                    onClick={() => void createChapter()}
                    title="添加章节"
                  >
                    <Plus size={16} />
                  </button>
                </div>
                <nav className="chapter-list" aria-label="章节目录">
                  {chapters.map((item) => (
                    <button
                      className={`chapter-item ${chapter?.id === item.id ? "active" : ""}`}
                      aria-current={
                        chapter?.id === item.id ? "true" : undefined
                      }
                      title={item.title}
                      aria-label={`${item.chapter_number ? `${item.chapter_number}. ` : ""}${item.title}`}
                      key={item.id}
                      onClick={() => {
                        setView("manuscript");
                        void loadChapter(item);
                      }}
                    >
                      <span className="chapter-number" aria-hidden="true">
                        {String(item.chapter_number || "—").padStart(2, "0")}
                      </span>
                      <span className="chapter-label">{item.title}</span>
                      {chapter?.id === item.id && (
                        <i
                          className={`chapter-dot ${dirty ? "dirty" : ""}`}
                          aria-hidden="true"
                        />
                      )}
                    </button>
                  ))}
                </nav>
                {!chapters.length && (
                  <p className="small muted">
                    添加第一章，开始写作。
                  </p>
                )}
              </div>
            </>
          )}
          <footer className="sidebar-footer">
            <ShieldCheck size={16} />
            <span>
              本地保存 · 版本可追溯
              <small>所有改动由你审核。</small>
            </span>
          </footer>
        </aside>
        <div id="main-content" className="main-content" tabIndex={-1}>
          {view === "manuscript" || !novel ? (
            <section className="editor-area" aria-label="书稿工作区">
              {loading || selecting ? (
                <div className="empty-state" role="status">
                  <LoaderCircle className="spin" size={25} />
                  <p>正在加载作品…</p>
                </div>
              ) : novel ? (
                <>
                  <div className="editor-topline">
                    <div className="breadcrumb">
                      <BookOpen size={14} />
                      <span>{novel.title}</span>
                      <ChevronRight size={13} />
                      <span>书稿</span>
                    </div>
                    <div className="editor-view-actions">
                      <button
                        className={`icon-button ${focusMode ? "active" : ""}`}
                        title={
                          focusMode ? "退出专注模式" : "进入专注模式"
                        }
                        aria-pressed={focusMode}
                        onClick={() => setFocusMode((value) => !value)}
                      >
                        <Focus size={17} />
                      </button>
                      <button
                        className={`icon-button inspector-toggle ${inspectorOpen ? "active" : ""}`}
                        title="打开故事检查器"
                        aria-expanded={inspectorOpen}
                        onClick={() => setInspectorOpen((value) => !value)}
                      >
                        <PanelRight size={17} />
                      </button>
                    </div>
                  </div>
                  <div className="editor-header">
                    <div>
                      <p className="eyebrow">
                        {chapter
                          ? `第 ${String(chapter.chapter_number || "—").padStart(2, "0")} 章 / 共 ${chapters.length} 章`
                          : "尚未创建章节"}
                      </p>
                      <h1 title={chapter?.title}>{chapter?.title || "还没有章节"}</h1>
                    </div>
                    <div className="editor-actions">
                      <span
                        className={`save-state ${dirty ? "unsaved" : ""}`}
                        role="status"
                      >
                        {saving
                          ? "正在保存…"
                          : dirty
                            ? "有未保存修改"
                            : notice || versionLabel}
                      </span>
                      <button
                        className="primary"
                        title="保存（⌘S）"
                        disabled={!dirty || !chapter || saving}
                        onClick={() => void save()}
                      >
                        <Save size={15} /> 保存
                      </button>
                    </div>
                  </div>
                  {chapter && (
                    <>
                      <div className="editor-toolbar">
                        <div
                          className="mode-toggle"
                          role="group"
                          aria-label="编辑格式"
                        >
                          <button
                            className={mode === "rich" ? "active" : ""}
                            aria-pressed={mode === "rich"}
                            onClick={() => switchMode("rich")}
                          >
                            富文本
                          </button>
                          <button
                            className={mode === "markdown" ? "active" : ""}
                            aria-pressed={mode === "markdown"}
                            onClick={() => switchMode("markdown")}
                          >
                            Markdown
                          </button>
                        </div>
                        <span className="manuscript-meta">
                          {wordCount.toLocaleString()} 字 / 词
                        </span>
                      </div>
                      <div className="manuscript-page">
                        {mode === "rich" ? (
                          <RichEditor
                            value={richContent}
                            onChange={(value) => {
                              setRichContent(value);
                              setDocumentDirty(true);
                              setNotice("");
                            }}
                          />
                        ) : (
                          <textarea
                            className="markdown-editor"
                            aria-label="Markdown 源码"
                            value={markdown}
                            onChange={(event) => {
                              setMarkdown(event.target.value);
                              setDocumentDirty(true);
                              setNotice("");
                            }}
                            placeholder="从第一句话开始……"
                            spellCheck={false}
                          />
                        )}
                      </div>
                      <footer className="editor-bottomline">
                        <span>
                          {mode === "rich"
                            ? "富文本正文"
                            : "Markdown 源码"}
                        </span>
                        <span>
                          {dirty
                            ? "当前草稿尚未保存"
                            : "所有修改已保存到本地"}
                        </span>
                      </footer>
                    </>
                  )}
                  {!chapter && (
                    <div className="chapter-empty">
                      <FileText size={36} strokeWidth={1} />
                      <p>为故事写下第一句话。</p>
                      <button
                        className="primary create-first"
                        onClick={() => void createChapter()}
                      >
                        <Plus size={16} /> 创建章节
                      </button>
                    </div>
                  )}
                  <div className="ai-actions">
                    <button
                      className="secondary"
                      disabled={busyAI || dirty || saving || !chapter}
                      onClick={() => void generateDraft()}
                    >
                      <Sparkles size={15} /> 生成预览
                    </button>
                    <button
                      className="secondary"
                      disabled={busyAI || dirty || saving || !versions[0]}
                      onClick={() => void analyzeLatest()}
                    >
                      <FileText size={15} /> 分析当前版本
                    </button>
                    {busyAI && (
                      <span className="small muted" role="status">
                        正在准备审核…
                      </span>
                    )}
                  </div>
                  {generation?.status === "succeeded" && (
                    <section className="review-panel">
                      <div className="review-heading">
                        <h2>生成内容预览</h2>
                        <span>
                          {generation.output.source_ids?.length || 0} 条上下文来源
                        </span>
                      </div>
                      <p className="small muted">
                        {provider === "mock"
                          ? "演示模型输出，仅用于流程测试。"
                          : ""}
                        审核后采纳，才会创建正文新版本。
                      </p>
                      <pre>{generation.output.markdown}</pre>
                      <div className="review-actions">
                        <button
                          className="primary"
                          disabled={dirty || saving}
                          onClick={() => void acceptDraft()}
                        >
                          <Check size={15} /> 采纳为新版本
                        </button>
                        <button
                          className="icon-button"
                          title="丢弃预览"
                          onClick={() => setGeneration(null)}
                        >
                          <X size={16} />
                        </button>
                      </div>
                    </section>
                  )}
                  {analysis && (
                    <section className="review-panel">
                      <div className="review-heading">
                        <h2>版本分析</h2>
                        <span>
                          {analysis.proposal_ids.length} 条待审提案
                        </span>
                      </div>
                      <p className="analysis-summary">
                        {analysis.summary_candidate}
                      </p>
                      <div className="review-actions">
                        <button
                          className="secondary"
                          disabled={dirty || saving}
                          onClick={() => void applySummaryCandidate()}
                        >
                          <Check size={15} /> 采纳摘要
                        </button>
                      </div>
                      {analysisProposals.map((proposal) => (
                        <div className="proposal-row" key={proposal.id}>
                          <div>
                            <strong>
                              {proposal.proposal_type.replaceAll("_", " ")}
                            </strong>
                            <pre>
                              {JSON.stringify(proposal.payload, null, 2)}
                            </pre>
                            <small>
                              依据 · 章节版本{" "}
                              {String(proposal.evidence.version_number || "")}
                            </small>
                          </div>
                          <div className="proposal-actions">
                            <button
                              className="icon-button"
                              title="批准提案"
                              onClick={() =>
                                void decideAnalysisProposal(proposal, "approve")
                              }
                            >
                              <Check size={15} />
                            </button>
                            <button
                              className="icon-button"
                              title="拒绝提案"
                              onClick={() =>
                                void decideAnalysisProposal(proposal, "reject")
                              }
                            >
                              <X size={15} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </section>
                  )}
                </>
              ) : (
                <div className="empty-state">
                  <div className="empty-book">
                    <BookOpen size={35} strokeWidth={1.2} />
                  </div>
                  <p className="eyebrow">开始创作</p>
                  <h1>创建第一部作品</h1>
                  <p>
                    用一个项目收纳书稿、资料与创作记录。
                  </p>
                  <button
                    className="primary"
                    onClick={() => {
                      if (canNavigate()) setOnboardingOpen(true);
                    }}
                  >
                    <Plus size={16} /> 新建作品向导
                  </button>
                </div>
              )}
            </section>
          ) : view === "knowledge" ? (
            <KnowledgeWorkspace key={novel.id} novelId={novel.id} />
          ) : (
            <AgentWorkspace
              key={novel.id}
              novelId={novel.id}
              draftDirty={dirty}
            />
          )}
        </div>
        {inspectorOpen && <button className="inspector-backdrop" aria-label="关闭故事检查器遮罩" onClick={() => setInspectorOpen(false)} />}
        <aside
          className={`history-panel ${view !== "manuscript" ? "context-panel" : ""}`}
          aria-label="故事检查器"
        >
          <div className="inspector-header">
            <span className="sidebar-heading">故事检查器</span>
            <button
              className="icon-button inspector-close"
              title="关闭故事检查器"
              onClick={() => setInspectorOpen(false)}
            >
              <X size={16} />
            </button>
          </div>
          <div
            className="inspector-tabs"
            role="tablist"
            aria-label="检查器分类"
          >
            <button
              role="tab"
              aria-selected={inspectorTab === "history"}
              onClick={() => setInspectorTab("history")}
            >
              <History size={14} />
              版本历史
            </button>
            <button
              role="tab"
              aria-selected={inspectorTab === "assistant"}
              onClick={() => setInspectorTab("assistant")}
            >
              <Sparkles size={14} />
              写作助手
            </button>
          </div>
          {inspectorTab === "history" ? (
            <>
              <div className="sidebar-heading history-title">
                <span>版本历史</span>
                <span>{versions.length}</span>
              </div>
              <p className="inspector-description">
                恢复历史会创建新版本，当前内容始终可追溯。
              </p>
              {versions.length === 0 && (
                <p className="muted small">
                  章节版本会显示在这里。
                </p>
              )}
              {versions.map((version) => (
                <div
                  className={`version-row ${version.version_number === chapter?.current_version ? "current" : ""}`}
                  key={version.id}
                >
                  <div className="version-timeline-dot" />
                  <div>
                    <strong>
                      版本 {version.version_number}
                      {version.version_number === chapter?.current_version && (
                        <span className="current-label">当前</span>
                      )}
                    </strong>
                    <small>
                      {new Date(version.created_at).toLocaleString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </small>
                    <small>
                      {version.content_format === "tiptap"
                        ? "富文本"
                        : "Markdown"}
                    </small>
                  </div>
                  <button
                    className="icon-button"
                    title={`恢复版本 ${version.version_number}`}
                    aria-label={`恢复版本 ${version.version_number}`}
                    disabled={
                      !chapter ||
                      dirty ||
                      saving ||
                      version.version_number === chapter.current_version
                    }
                    onClick={() => void restore(version)}
                  >
                    <RotateCcw size={15} />
                  </button>
                </div>
              ))}
            </>
          ) : (
            <div className="assistant-intro">
              <div className="assistant-mark">
                <Sparkles size={22} strokeWidth={1.5} />
              </div>
              <h2>
                创作助手
                <br />
                由你把关。
              </h2>
              <p>
                生成续写预览，或分析已保存版本。审核之后再决定是否采纳。
              </p>
              <div className="inspector-note">
                <ShieldCheck size={16} />
                <span>
                  建议与正文分开保存，批准后才应用。
                </span>
              </div>
              <button
                className="secondary wide"
                disabled={!novel}
                onClick={() => {
                  setView("agent");
                  setInspectorOpen(false);
                }}
              >
                <Bot size={16} /> 进入创作助手 <ArrowUpRight size={14} />
              </button>
              <button
                className="text-button"
                onClick={() => setSettingsOpen(true)}
              >
                配置模型与工具
              </button>
            </div>
          )}
          <div className="inspector-note bottom">
            <ShieldCheck size={16} />
            <span>
              {dirty
                ? "请先保存草稿，再恢复历史版本。"
                : "正文始终由作者控制。"}
            </span>
          </div>
        </aside>
      </div>
      {error && (
        <div className="error toast" role="alert">
          <span>{error}</span>
          <button
            className="icon-button"
            title="关闭错误提示"
            onClick={() => setError("")}
          >
            <X size={16} />
          </button>
        </div>
      )}
      {settingsOpen && (
        <SettingsDialog onClose={closeSettings} onSaved={refreshProvider} />
      )}
      <ProjectOnboarding
        open={onboardingOpen}
        onClose={closeOnboarding}
        onCreated={(created) => {
          setNovels((items) => [
            created,
            ...items.filter((item) => item.id !== created.id),
          ]);
          setView("manuscript");
          setFocusMode(false);
          void loadProject(created);
        }}
      />
    </main>
  );
}

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checked, setChecked] = useState(false);
  const [startupError, setStartupError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    initializeApi(attempt > 0)
      .then(() => api<User>("/auth/me"))
      .then((result) => {
        if (active) setUser(result.data);
      })
      .catch((error) => {
        if (!active) return;
        if (error instanceof ApiError && error.status === 401) setUser(null);
        else
          setStartupError(
            error instanceof Error
              ? error.message
              : "无法启动 NovelForge。",
          );
      })
      .finally(() => {
        if (active) setChecked(true);
      });
    return () => {
      active = false;
    };
  }, [attempt]);
  useEffect(() => {
    const expired = () => setUser(null);
    window.addEventListener("novelforge:session-expired", expired);
    return () =>
      window.removeEventListener("novelforge:session-expired", expired);
  }, []);
  if (!checked)
    return (
      <main className="auth-shell">
        <p className="muted">正在启动 NovelForge…</p>
      </main>
    );
  if (startupError)
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <h1>NovelForge 无法启动</h1>
          <p className="error" role="alert">
            {startupError}
          </p>
          <button
            className="primary"
            onClick={() => {
              setStartupError("");
              setChecked(false);
              setAttempt((value) => value + 1);
            }}
          >
            重试
          </button>
        </section>
      </main>
    );
  if (!user) return <AuthScreen onAuthenticated={setUser} />;
  return (
    <Workspace
      user={user}
      onLogout={async () => {
        await api("/auth/logout", { method: "POST", headers: csrfHeaders() });
        setSessionToken("");
        setUser(null);
      }}
    />
  );
}
