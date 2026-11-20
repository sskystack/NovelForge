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
  const [chapterTitle, setChapterTitle] = useState("Chapter 1");
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
          throw new Error("Give your story a title before creating it.");
        if (genres.length > 30) throw new Error("Use up to 30 genres.");
        if (language.trim().length < 2)
          throw new Error("Enter a language code such as zh-CN or en.");
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
            title: chapterTitle.trim() || "Chapter 1",
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
          : "Creation failed. Your inputs are still here.",
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
        className="settings-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-title"
        aria-describedby="onboarding-description"
        tabIndex={-1}
        ref={dialog}
      >
        <header className="dialog-header">
          <div>
            <p className="eyebrow">A new beginning · {step + 1} of 3</p>
            <h1 id="onboarding-title">Start your story</h1>
          </div>
          <button
            className="icon-button"
            type="button"
            title="Close project setup"
            disabled={busy}
            onClick={() => finish(savedNovel.current || undefined)}
          >
            <X size={20} />
          </button>
        </header>
        <div className="dialog-content">
          <form className="settings-form" onSubmit={advance} aria-busy={busy}>
            <p id="onboarding-description" className="muted small">
              {step === 0
                ? "Begin with a title and a single idea. You can develop the rest as you write."
                : step === 1
                  ? "Give the opening a direction, or leave the first chapter for later."
                  : "Review your starting point. Everything here comes from you."}
            </p>
            {step === 0 && (
              <>
                <label>
                  Story title
                  <input
                    autoComplete="off"
                    required
                    maxLength={200}
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                  />
                </label>
                <label>
                  Premise{" "}
                  <span className="muted">
                    Optional · one sentence is enough
                  </span>
                  <textarea
                    rows={4}
                    maxLength={20000}
                    value={premise}
                    onChange={(event) => setPremise(event.target.value)}
                    placeholder="Who wants what, and what stands in their way?"
                  />
                </label>
                <div className="form-columns">
                  <label>
                    Genres{" "}
                    <span className="muted">Optional · comma separated</span>
                    <input
                      value={genre}
                      onChange={(event) => setGenre(event.target.value)}
                      placeholder="Fantasy, mystery"
                    />
                  </label>
                  <label>
                    Writing language
                    <input
                      required
                      minLength={2}
                      maxLength={32}
                      value={language}
                      onChange={(event) => setLanguage(event.target.value)}
                      placeholder="zh-CN or en"
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
                  Create an empty first chapter
                </label>
                {createChapter && (
                  <>
                    <label>
                      First chapter title
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
                      First chapter goal{" "}
                      <span className="muted">Optional · planning note</span>
                      <textarea
                        rows={4}
                        maxLength={20000}
                        value={chapterGoal}
                        onChange={(event) => setChapterGoal(event.target.value)}
                        placeholder="Introduce the keeper, reveal the missing letter, leave a question open…"
                      />
                    </label>
                    <p className="field-hint">
                      Your goal is saved in project writing preferences. The
                      manuscript begins empty.
                    </p>
                  </>
                )}
              </>
            )}
            {step === 2 && (
              <>
                <section className="server-card" aria-label="Project review">
                  <div className="server-heading">
                    <strong>{title}</strong>
                    <span className="badge">{language}</span>
                  </div>
                  <p className="small">
                    {premise.trim() ||
                      "No premise yet — you can develop it later."}
                  </p>
                  {genre.trim() && (
                    <p className="small muted">Genres: {genre}</p>
                  )}
                  <p className="small">
                    {createChapter
                      ? `First chapter: ${chapterTitle.trim() || "Chapter 1"}`
                      : "Project only · add chapters when you are ready"}
                  </p>
                  {createChapter && chapterGoal.trim() && (
                    <p className="small">Opening goal: {chapterGoal}</p>
                  )}
                </section>
                <div className="info-card">
                  <BookOpen size={20} />
                  <div>
                    <strong>A starting point, in your own words</strong>
                    <p>
                      This creates your project
                      {createChapter ? " and an empty draft chapter" : ""}. No
                      AI request is made and no story facts are approved
                      automatically.
                    </p>
                  </div>
                </div>
              </>
            )}
            {projectSaved && error && (
              <p className="success-notice" role="status">
                <Check size={16} /> Your project is saved. The first chapter
                could not be created. Retry, or continue and add it later.
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
                  Continue without chapter
                </button>
              ) : (
                <button
                  className="secondary"
                  type="button"
                  disabled={busy}
                  onClick={() => (step === 0 ? finish() : setStep(step - 1))}
                >
                  {step === 0 ? "Cancel" : "Back"}
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
                      ? "Creating first chapter…"
                      : "Creating project…"}
                  </>
                ) : step < 2 ? (
                  <>
                    Continue <ArrowRight size={15} />
                  </>
                ) : projectSaved ? (
                  "Retry first chapter"
                ) : (
                  "Create project"
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
                Skip first chapter for now
              </button>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
