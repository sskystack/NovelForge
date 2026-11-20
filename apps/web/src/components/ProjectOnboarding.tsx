import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { ArrowRight, BookOpen, Check, LoaderCircle, X } from "lucide-react";
import { api, csrfHeaders } from "../api";

type Novel = { id: string; title: string; premise: string; status: string };
type Chapter = {
  id: string;
  title: string;
  chapter_number: number | null;
  current_version: number;
  status: string;
  summary: string;
};
type Props = {
  open: boolean;
  onClose: () => void;
  onCreated: (novel: Novel, chapter?: Chapter) => void;
};

export function ProjectOnboarding({ open, ...props }: Props) {
  return open ? <OnboardingForm {...props} /> : null;
}

function OnboardingForm({ onClose, onCreated }: Omit<Props, "open">) {
  const dialog = useRef<HTMLDivElement>(null);
  const busyRef = useRef(false);
  const savedNovel = useRef<Novel | null>(null);
  const callbacks = useRef({ onClose, onCreated });
  callbacks.current = { onClose, onCreated };
  const [step, setStep] = useState(0);
  const [title, setTitle] = useState("");
  const [premise, setPremise] = useState("");
  const [genre, setGenre] = useState("");
  const [language, setLanguage] = useState("zh-CN");
  const [createChapter, setCreateChapter] = useState(true);
  const [chapterTitle, setChapterTitle] = useState("第一章");
  const [chapterGoal, setChapterGoal] = useState("");
  const [busy, setBusy] = useState(false);
  const [projectSaved, setProjectSaved] = useState(false);
  const [error, setError] = useState("");

  const finish = (novel?: Novel, chapter?: Chapter) => {
    if (novel) callbacks.current.onCreated(novel, chapter);
    callbacks.current.onClose();
  };

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (!busyRef.current) {
          if (savedNovel.current)
            callbacks.current.onCreated(savedNovel.current);
          callbacks.current.onClose();
        }
      }
      if (event.key !== "Tab") return;
      const elements = dialog.current?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]',
      );
      if (!elements?.length) return;
      const first = elements[0],
        last = elements[elements.length - 1];
      if (
        event.shiftKey &&
        (document.activeElement === first ||
          document.activeElement === dialog.current)
      ) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === last ||
          document.activeElement === dialog.current)
      ) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      previous?.focus();
    };
  }, []);

  // The API has separate project/chapter transactions. Retain the first response
  // so retrying a chapter failure never submits a second project creation.
  const create = async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    let novel = savedNovel.current;
    let chapter: Chapter | undefined;
    try {
      if (!novel) {
        const genres = [
          ...new Set(
            genre
              .split(/[,，]/)
              .map((value) => value.trim())
              .filter(Boolean),
          ),
        ];
        if (!title.trim())
          throw new Error("请先填写作品名称。");
        if (genres.length > 30) throw new Error("最多填写 30 个题材。");
        if (language.trim().length < 2)
          throw new Error("请输入语言代码，例如 zh-CN 或 en。");
        const { data } = await api<Novel>("/novels", {
          method: "POST",
          headers: csrfHeaders(),
          body: JSON.stringify({
            title: title.trim(),
            premise: premise.trim(),
            genre: genres,
            language: language.trim(),
            writing_preferences:
              createChapter && chapterGoal.trim()
                ? { first_chapter_goal: chapterGoal.trim() }
                : {},
          }),
        });
        novel = data;
        savedNovel.current = data;
        setProjectSaved(true);
      }
      if (createChapter) {
        const { data } = await api<Chapter>(`/novels/${novel.id}/chapters`, {
          method: "POST",
          headers: csrfHeaders(),
          body: JSON.stringify({
            title: chapterTitle.trim() || "第一章",
            chapter_number: 1,
            status: "draft",
          }),
        });
        chapter = data;
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "创建失败，输入内容已保留。",
      );
      busyRef.current = false;
      setBusy(false);
      return;
    }
    busyRef.current = false;
    setBusy(false);
    finish(novel, chapter);
  };

  const advance = (event: FormEvent) => {
    event.preventDefault();
    if (busyRef.current) return;
    if (step < 2) {
      setError("");
      setStep(step + 1);
    } else void create();
  };

  return (
    <div className="modal-backdrop">
      <div
        className="settings-dialog onboarding-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-title"
        aria-describedby="onboarding-description"
        tabIndex={-1}
        ref={dialog}
      >
        <header className="dialog-header">
          <div>
            <p className="eyebrow">新建作品 · {step + 1} of 3</p>
            <h1 id="onboarding-title">新建作品</h1>
          </div>
          <button
            className="icon-button"
            type="button"
            title="关闭新建向导"
            disabled={busy}
            onClick={() => finish(savedNovel.current || undefined)}
          >
            <X size={20} />
          </button>
        </header>
        <div className="dialog-content">
          <form className="settings-form" onSubmit={advance} aria-busy={busy}><ol className="wizard-steps" aria-label="新建作品步骤">{["故事定位", "首章方向", "确认创建"].map((label, index) => <li key={label} aria-current={step === index ? "step" : undefined}>{index + 1} {label}</li>)}</ol>
            <p id="onboarding-description" className="muted small">
              {step === 0
                ? "先给作品一个名称，写下一句话构思。其他内容可以边写边完善。"
                : step === 1
                  ? "确定开篇方向，也可以稍后再添加第一章。"
                  : "确认作品信息，创建后即可进入书稿。"}
            </p>
            {step === 0 && (
              <>
                <label>
                  作品名称
                  <input
                    autoComplete="off"
                    required
                    maxLength={200}
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                  />
                </label>
                <label>
                  一句话构思{" "}
                  <span className="muted">
                    可选，一句话即可
                  </span>
                  <textarea
                    rows={4}
                    maxLength={20000}
                    value={premise}
                    onChange={(event) => setPremise(event.target.value)}
                    placeholder="谁想达成什么？又有什么阻碍？"
                  />
                </label>
                <div className="form-columns">
                  <label>
                    题材{" "}
                    <span className="muted">可选，逗号分隔</span>
                    <input
                      value={genre}
                      onChange={(event) => setGenre(event.target.value)}
                      placeholder="奇幻，悬疑"
                    />
                  </label>
                  <label>
                    写作语言
                    <input
                      required
                      minLength={2}
                      maxLength={32}
                      value={language}
                      onChange={(event) => setLanguage(event.target.value)}
                      placeholder="例如 zh-CN 或 en"
                    />
                  </label>
                </div>
              </>
            )}
            {step === 1 && (
              <>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={createChapter}
                    onChange={(event) => setCreateChapter(event.target.checked)}
                  />{" "}
                  同时创建第一章空白书稿
                </label>
                {createChapter && (
                  <>
                    <label>
                      第一章标题
                      <input
                        required
                        maxLength={200}
                        value={chapterTitle}
                        onChange={(event) =>
                          setChapterTitle(event.target.value)
                        }
                      />
                    </label>
                    <label>
                      首章目标{" "}
                      <span className="muted">可选，作为规划笔记</span>
                      <textarea
                        rows={4}
                        maxLength={20000}
                        value={chapterGoal}
                        onChange={(event) => setChapterGoal(event.target.value)}
                        placeholder="引入守塔人，揭开失踪信件，留下一个悬念……"
                      />
                    </label>
                    <p className="field-hint">
                      目标会保存为作品偏好，正文保持空白。
                    </p>
                  </>
                )}
              </>
            )}
            {step === 2 && (
              <>
                <section className="server-card" aria-label="确认作品信息">
                  <div className="server-heading">
                    <strong>{title}</strong>
                    <span className="badge">{language}</span>
                  </div>
                  <p className="small">
                    {premise.trim() ||
                      "尚未填写构思，可稍后完善。"}
                  </p>
                  {genre.trim() && (
                    <p className="small muted">题材： {genre}</p>
                  )}
                  <p className="small">
                    {createChapter
                      ? `首章：${chapterTitle.trim() || "第一章"}`
                      : "仅创建项目，之后再添加章节"}
                  </p>
                  {createChapter && chapterGoal.trim() && (
                    <p className="small">开篇目标： {chapterGoal}</p>
                  )}
                </section>
                <div className="info-card">
                  <BookOpen size={20} />
                  <div>
                    <strong>从你的构思开始</strong>
                    <p>
                      将创建作品
                      {createChapter ? "和空白章节" : ""}。不会调用模型，也不会自动批准任何设定。
                    </p>
                  </div>
                </div>
              </>
            )}
            {projectSaved && error && (
              <p className="success-notice" role="status">
                <Check size={16} /> 作品已保存，但首章创建失败。可以重试，也可以先进入作品稍后添加。
              </p>
            )}
            {error && (
              <p className="inline-error" role="alert">
                {error}
              </p>
            )}
            <div className="dialog-actions">
              {projectSaved && error ? (
                <button
                  className="secondary"
                  type="button"
                  disabled={busy}
                  onClick={() => finish(savedNovel.current || undefined)}
                >
                  先进入作品
                </button>
              ) : (
                <button
                  className="secondary"
                  type="button"
                  disabled={busy}
                  onClick={() => (step === 0 ? finish() : setStep(step - 1))}
                >
                  {step === 0 ? "取消" : "上一步"}
                </button>
              )}
              <button
                className="primary"
                type="submit"
                disabled={
                  busy ||
                  (step === 0 && !title.trim()) ||
                  (step === 1 && createChapter && !chapterTitle.trim())
                }
              >
                {busy ? (
                  <>
                    <LoaderCircle size={15} className="spin" />{" "}
                    {projectSaved
                      ? "正在创建第一章…"
                      : "正在创建作品…"}
                  </>
                ) : step < 2 ? (
                  <>
                    下一步 <ArrowRight size={15} />
                  </>
                ) : projectSaved ? (
                  "重试创建第一章"
                ) : (
                  "创建作品"
                )}
              </button>
            </div>
            {step === 1 && !projectSaved && (
              <button
                type="button"
                className="text-button"
                onClick={() => {
                  setCreateChapter(false);
                  setStep(2);
                }}
              >
                暂时跳过第一章
              </button>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
