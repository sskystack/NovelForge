import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { BookOpen, Check, ChevronRight, FileText, LogOut, Plus, RotateCcw, Save, Sparkles, X } from "lucide-react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Markdown } from "@tiptap/markdown";
import { ApiError, api, csrfHeaders, initializeApi, request, setSessionToken } from "./api";
import { parseMarkdown, serializeMarkdown } from "./markdown";

type User = { id: string; email: string; display_name: string };
type Novel = { id: string; title: string; premise: string; status: string };
type Chapter = { id: string; title: string; chapter_number: number | null; current_version: number; status: string; summary: string };
type Version = { id: string; version_number: number; content_format: "tiptap" | "markdown"; tiptap_json: Record<string, unknown> | null; markdown: string | null; created_at: string };
type Mode = "rich" | "markdown";
type Generation = { id: string; status: string; output: { markdown?: string; source_ids?: string[] }; expected_version: number | null; error_message?: string };
type Analysis = { id: string; chapter_version_id: string; summary_candidate: string; candidates: { events: unknown[]; character_states: unknown[]; consistency_warnings: unknown[] }; proposal_ids: string[] };
type AnalysisProposal = { id: string; proposal_type: string; payload: Record<string, unknown>; evidence: Record<string, unknown>; status: string };

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
      setSessionToken(result.response.headers.get("X-NovelForge-Session") || "");
      onAuthenticated(result.data);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Unable to sign in"); }
    finally { setBusy(false); }
  };
  return <main className="auth-shell"><section className="auth-card"><div className="brand-mark"><BookOpen size={20} /> NovelForge</div><h1>{register ? "Create your workspace" : "Welcome back"}</h1><p className="muted">Keep every chapter grounded in your approved story.</p><form onSubmit={submit}>{register && <label>Display name<input value={displayName} onChange={(e) => setDisplayName(e.target.value)} /></label>}<label>Email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label><label>Password<input type="password" required minLength={12} value={password} onChange={(e) => setPassword(e.target.value)} /></label>{error && <p className="error">{error}</p>}<button className="primary wide" type="submit" disabled={busy}>{busy ? "Working…" : register ? "Create account" : "Sign in"}</button></form><button className="link-button" onClick={() => setRegister((value) => !value)}>{register ? "Already have an account? Sign in" : "Create an account"}</button></section></main>;
}

function RichEditor({ value, onChange }: { value: Record<string, unknown>; onChange: (value: Record<string, unknown>) => void }) {
  const editor = useEditor({ extensions: [StarterKit, Markdown.configure({ markedOptions: { gfm: true } })], content: value, onUpdate: ({ editor: current }) => onChange(current.getJSON() as Record<string, unknown>) });
  useEffect(() => { if (editor && JSON.stringify(editor.getJSON()) !== JSON.stringify(value)) editor.commands.setContent(value, { emitUpdate: false }); }, [editor, value]);
  return <EditorContent editor={editor} className="rich-editor" />;
}

function Workspace({ user, onLogout }: { user: User; onLogout: () => Promise<void> }) {
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
  const [generation, setGeneration] = useState<Generation | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [analysisProposals, setAnalysisProposals] = useState<AnalysisProposal[]>([]);
  const [busyAI, setBusyAI] = useState(false);
  const [serviceStatus, setServiceStatus] = useState<"checking" | "ready" | "unavailable">("checking");
  const [selecting, setSelecting] = useState(false);
  const [saving, setSaving] = useState(false);
  const selection = useRef(0);
  const editRevision = useRef(0);
  const dirtyRef = useRef(false);
  const mutation = useRef(false);
  const setDocumentDirty = useCallback((value: boolean) => {
    if (value) editRevision.current += 1;
    dirtyRef.current = value;
    setDirty(value);
  }, []);
  const canNavigate = () => {
    if (dirtyRef.current || mutation.current) {
      setError("Save your current changes before switching, creating, or signing out.");
      return false;
    }
    return true;
  };

  useEffect(() => {
    let active = true;
    const check = () => void request("/ready").then(() => {
      if (active) setServiceStatus("ready");
    }).catch(() => { if (active) setServiceStatus("unavailable"); });
    check();
    const timer = window.setInterval(check, 10_000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  const loadChapterFor = useCallback(async (selectedNovel: Novel, selected: Chapter, requestId = ++selection.current) => {
    setSelecting(true); setError("");
    try {
      const [detail, history] = await Promise.all([
        api<Chapter>(`/novels/${selectedNovel.id}/chapters/${selected.id}`),
        api<Version[]>(`/novels/${selectedNovel.id}/chapters/${selected.id}/versions`),
      ]);
      if (requestId !== selection.current) return;
      const latest = history.data.find((version) => version.version_number === detail.data.current_version);
      if (!latest) throw new Error("The chapter changed while loading. Select it again to reload.");
      setChapter(detail.data);
      setEtag(detail.response.headers.get("ETag") || `"${detail.data.current_version}"`);
      setVersions(history.data);
      if (latest.content_format === "markdown") {
        setMode("markdown"); setMarkdown(latest.markdown || "");
        setRichContent({ type: "doc", content: [] });
      } else {
        const content = latest.tiptap_json || { type: "doc", content: [] };
        setMode("rich"); setRichContent(content); setMarkdown(serializeMarkdown(content));
      }
      setGeneration(null); setAnalysis(null); setAnalysisProposals([]); setBusyAI(false);
      setDocumentDirty(false); setNotice("");
    } catch (requestError) {
      if (requestId === selection.current) setError(requestError instanceof Error ? requestError.message : "Could not load chapter");
    } finally { if (requestId === selection.current) setSelecting(false); }
  }, [setDocumentDirty]);

  const loadProject = useCallback(async (selected: Novel) => {
    const requestId = ++selection.current;
    setSelecting(true); setError("");
    try {
      const result = await api<{ items: Chapter[] }>(`/novels/${selected.id}/chapters?limit=100`);
      if (requestId !== selection.current) return;
      setNovel(selected); setChapter(null); setVersions([]); setChapters(result.data.items);
      setGeneration(null); setAnalysis(null); setAnalysisProposals([]); setBusyAI(false);
      if (result.data.items[0]) await loadChapterFor(selected, result.data.items[0], requestId);
      else { setEtag(""); setRichContent({ type: "doc", content: [] }); setMarkdown(""); setDocumentDirty(false); }
    } catch (requestError) {
      if (requestId === selection.current) setError(requestError instanceof Error ? requestError.message : "Could not load project");
    } finally { if (requestId === selection.current) setSelecting(false); }
  }, [loadChapterFor, setDocumentDirty]);
  const loadChapter = async (selected: Chapter) => { if (novel && canNavigate()) await loadChapterFor(novel, selected); };

  useEffect(() => {
    let active = true;
    api<Novel[]>("/novels").then(async (result) => { if (active) { setNovels(result.data); if (result.data[0]) await loadProject(result.data[0]); } }).catch((requestError) => { if (active) setError(requestError instanceof Error ? requestError.message : "Unable to load projects"); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [loadProject]);

  const createNovel = async (event: FormEvent) => {
    event.preventDefault(); if (!newTitle.trim() || !canNavigate()) return;
    try { const result = await api<Novel>("/novels", { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ title: newTitle }) }); setNovels((items) => [result.data, ...items]); setNewTitle(""); await loadProject(result.data); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not create project"); }
  };

  const createChapter = async () => {
    if (!novel || !canNavigate()) return;
    const chapterNumber = Math.max(0, ...chapters.map((item) => item.chapter_number || 0)) + 1;
    const title = `Chapter ${chapterNumber}`;
    try { const result = await api<Chapter>(`/novels/${novel.id}/chapters`, { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ title, chapter_number: chapterNumber }) }); setChapters((items) => [...items, result.data]); await loadChapterFor(novel, result.data); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not create chapter"); }
  };

  const switchMode = (nextMode: Mode) => {
    if (nextMode === mode) return;
    try {
      if (nextMode === "markdown") setMarkdown(serializeMarkdown(richContent));
      else setRichContent(parseMarkdown(markdown));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not convert this chapter safely."); return;
    }
    setMode(nextMode); setDocumentDirty(true); setNotice("");
  };

  const save = async () => {
    if (!novel || !chapter || !etag || mutation.current) return;
    mutation.current = true; setSaving(true);
    const revision = editRevision.current;
    setNotice(""); setError("");
    try {
      const payload = mode === "markdown" ? { content_format: "markdown", markdown } : { content_format: "tiptap", content: richContent };
      const result = await api<Chapter>(`/novels/${novel.id}/chapters/${chapter.id}`, { method: "PATCH", headers: { ...csrfHeaders(), "If-Match": etag }, body: JSON.stringify(payload) });
      setChapter(result.data); setEtag(result.response.headers.get("ETag") || `"${result.data.current_version}"`);
      setGeneration(null); setAnalysis(null); setAnalysisProposals([]);
      if (revision === editRevision.current) { setDocumentDirty(false); setNotice("Saved"); }
      try { setVersions((await api<Version[]>(`/novels/${novel.id}/chapters/${chapter.id}/versions`)).data); }
      catch { setError("Your changes were saved, but version history could not refresh. Reload it before restoring a version."); }
    } catch (requestError) {
      if (requestError instanceof Error && requestError.message.includes("CHAPTER_VERSION_CONFLICT")) setError("This chapter changed elsewhere. Your local draft is preserved; reload the latest version before saving again.");
      else setError(requestError instanceof Error ? requestError.message : "Save failed");
    } finally { mutation.current = false; setSaving(false); }
  };

  const restore = async (version: Version) => {
    if (!novel || !chapter || !canNavigate()) return;
    mutation.current = true; setSaving(true); setError("");
    try { const result = await api<Chapter>(`/novels/${novel.id}/chapters/${chapter.id}/restore/${version.id}`, { method: "POST", headers: { ...csrfHeaders(), "If-Match": etag } }); setEtag(result.response.headers.get("ETag") || `"${result.data.current_version}"`); await loadChapterFor(novel, result.data); setNotice("Restored as a new version"); }
    catch (requestError) { setError(requestError instanceof Error && requestError.message.includes("CHAPTER_VERSION_CONFLICT") ? "The chapter changed elsewhere. Reload before restoring." : requestError instanceof Error ? requestError.message : "Restore failed"); }
    finally { mutation.current = false; setSaving(false); }
  };

  const generateDraft = async () => {
    if (!novel || !chapter || dirtyRef.current || mutation.current || busyAI) return;
    const requestId = selection.current;
    setBusyAI(true); setError("");
    try {
      const result = await api<Generation>(`/novels/${novel.id}/ai/generations`, { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ chapter_id: chapter.id, task_profile: "writing", instructions: "Continue this chapter in the established voice." }) });
      if (requestId !== selection.current) return;
      if (result.data.status !== "succeeded") throw new Error(result.data.error_message || "Generation failed. Your manuscript was not changed.");
      setGeneration(result.data);
    } catch (requestError) { if (requestId === selection.current) setError(requestError instanceof Error ? requestError.message : "Generation failed"); }
    finally { if (requestId === selection.current) setBusyAI(false); }
  };

  const acceptDraft = async () => {
    if (!novel || !chapter || !generation || !canNavigate()) return;
    mutation.current = true; setSaving(true);
    try {
      await api(`/novels/${novel.id}/ai/generations/${generation.id}/accept`, { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ expected_version: chapter.current_version }) });
      setGeneration(null); await loadChapterFor(novel, chapter); setNotice("Draft accepted as a new version");
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not accept draft"); }
    finally { mutation.current = false; setSaving(false); }
  };

  const analyzeLatest = async () => {
    if (!novel || !versions[0] || dirtyRef.current || mutation.current || busyAI) return;
    const requestId = selection.current;
    setBusyAI(true);
    try {
      const result = await api<Analysis>(`/novels/${novel.id}/ai/analysis/${versions[0].id}`, { method: "POST", headers: csrfHeaders() });
      const proposals = await api<AnalysisProposal[]>(`/novels/${novel.id}/ai/analysis-proposals?chapter_version_id=${versions[0].id}`);
      if (requestId !== selection.current) return;
      setAnalysis(result.data); setAnalysisProposals(proposals.data);
    } catch (requestError) { if (requestId === selection.current) setError(requestError instanceof Error ? requestError.message : "Analysis failed"); }
    finally { if (requestId === selection.current) setBusyAI(false); }
  };

  const decideAnalysisProposal = async (proposal: AnalysisProposal, decision: "approve" | "reject") => {
    if (!novel) return;
    try {
      await api(`/novels/${novel.id}/ai/analysis-proposals/${proposal.id}/${decision}`, { method: "POST", headers: csrfHeaders(), body: JSON.stringify({ reason: "Reviewed in chapter workspace" }) });
      setAnalysisProposals((items) => items.filter((item) => item.id !== proposal.id));
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not review proposal"); }
  };

  const applySummaryCandidate = async () => {
    if (!novel || !chapter || !analysis || !canNavigate()) return;
    if (analysis.chapter_version_id !== versions[0]?.id) {
      setError("This analysis belongs to an older version. Analyze the latest saved version again."); return;
    }
    mutation.current = true; setSaving(true);
    try {
      const result = await api<Chapter>(`/novels/${novel.id}/chapters/${chapter.id}`, { method: "PATCH", headers: { ...csrfHeaders(), "If-Match": etag }, body: JSON.stringify({ summary: analysis.summary_candidate }) });
      setChapter(result.data); setEtag(result.response.headers.get("ETag") || `"${result.data.current_version}"`);
      setVersions((await api<Version[]>(`/novels/${novel.id}/chapters/${chapter.id}/versions`)).data);
      setNotice("Summary accepted as a new chapter version");
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not apply summary"); }
    finally { mutation.current = false; setSaving(false); }
  };

  const reconnect = async () => {
    setServiceStatus("checking");
    try { await initializeApi(true); await request("/ready"); setServiceStatus("ready"); setError(""); }
    catch (requestError) { setServiceStatus("unavailable"); setError(requestError instanceof Error ? requestError.message : "Could not restart the local service"); }
  };
  const signOut = async () => {
    if (!canNavigate()) return;
    try { await onLogout(); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not sign out. Please retry."); }
  };

  const versionLabel = useMemo(() => chapter ? `Version ${chapter.current_version}` : "No chapter selected", [chapter]);
  return (
    <main className="workspace">
      <header className="topbar">
        <div className="brand-mark"><BookOpen size={19} /> NovelForge</div>
        <div className="top-actions">
          <span className={`service-indicator ${serviceStatus}`} aria-label={`API ${serviceStatus}`} title={`API ${serviceStatus}`} />
          {serviceStatus === "unavailable" && <button className="secondary" onClick={() => void reconnect()}>Reconnect</button>}
          <span className="user-label">{user.display_name || user.email}</span>
          <button className="icon-button" title="Sign out" onClick={() => void signOut()}><LogOut size={17} /></button>
        </div>
      </header>
      <div className="workspace-grid">
        <aside className="sidebar">
          <div className="sidebar-heading"><span>Projects</span><button className="icon-button" title="New project" onClick={() => document.getElementById("new-project")?.focus()}><Plus size={17} /></button></div>
          <form className="new-project" onSubmit={createNovel}>
            <input id="new-project" aria-label="New project title" placeholder="New project title" value={newTitle} onChange={(event) => setNewTitle(event.target.value)} />
          </form>
          {novels.map((item) => <button className={`project-item ${novel?.id === item.id ? "selected" : ""}`} key={item.id} onClick={() => { if (canNavigate()) void loadProject(item); }}><BookOpen size={16} /><span>{item.title}</span><ChevronRight size={14} /></button>)}
        </aside>
        <section className="editor-area">
          {loading || selecting ? <div className="empty-state">Loading workspace…</div> : novel ? <>
            <div className="editor-header">
              <div><p className="eyebrow">{novel.title}</p><h1>{chapter?.title || "No chapters yet"}</h1></div>
              <div className="editor-actions"><span className="save-state">{saving ? "Saving…" : dirty ? "Unsaved changes" : notice || versionLabel}</span><button className="primary" disabled={!dirty || !chapter || saving} onClick={() => void save()}><Save size={16} /> Save</button></div>
            </div>
            <div className="chapter-tabs">
              {chapters.map((item) => <button className={chapter?.id === item.id ? "active" : ""} key={item.id} onClick={() => void loadChapter(item)}>{item.chapter_number ? `${item.chapter_number}. ` : ""}{item.title}</button>)}
              <button className="add-chapter" onClick={() => void createChapter()} title="Add chapter"><Plus size={15} /></button>
            </div>
            {chapter && <>
              <div className="mode-toggle" role="group" aria-label="Editor mode">
                <button className={mode === "rich" ? "active" : ""} aria-pressed={mode === "rich"} onClick={() => switchMode("rich")}>Rich text</button>
                <button className={mode === "markdown" ? "active" : ""} aria-pressed={mode === "markdown"} onClick={() => switchMode("markdown")}>Markdown</button>
              </div>
              <div className="ai-actions">
                <button className="secondary" disabled={busyAI || dirty || saving} onClick={() => void generateDraft()}><Sparkles size={15} /> Generate preview</button>
                <button className="secondary" disabled={busyAI || dirty || saving || !versions[0]} onClick={() => void analyzeLatest()}><FileText size={15} /> Analyze version</button>
              </div>
              {mode === "rich" ? <RichEditor value={richContent} onChange={(value) => { setRichContent(value); setDocumentDirty(true); setNotice(""); }} /> : <textarea className="markdown-editor" aria-label="Markdown source" value={markdown} onChange={(event) => { setMarkdown(event.target.value); setDocumentDirty(true); setNotice(""); }} spellCheck={false} />}
            </>}
            {!chapter && <button className="primary create-first" onClick={() => void createChapter()}><Plus size={16} /> Create chapter</button>}
            {generation?.status === "succeeded" && <section className="review-panel">
              <div className="review-heading"><h2>Generated draft</h2><span>{generation.output.source_ids?.length || 0} context sources</span></div>
              <pre>{generation.output.markdown}</pre>
              <div className="review-actions"><button className="primary" disabled={dirty || saving} onClick={() => void acceptDraft()}><Check size={15} /> Accept as new version</button><button className="icon-button" title="Discard preview" onClick={() => setGeneration(null)}><X size={16} /></button></div>
            </section>}
            {analysis && <section className="review-panel">
              <div className="review-heading"><h2>Version analysis</h2><span>{analysis.proposal_ids.length} pending proposals</span></div>
              <p className="analysis-summary">{analysis.summary_candidate}</p>
              <div className="review-actions"><button className="secondary" disabled={dirty || saving} onClick={() => void applySummaryCandidate()}><Check size={15} /> Apply summary</button></div>
              {analysisProposals.map((proposal) => <div className="proposal-row" key={proposal.id}>
                <div><strong>{proposal.proposal_type.replaceAll("_", " ")}</strong><pre>{JSON.stringify(proposal.payload, null, 2)}</pre><small>Evidence · chapter version {String(proposal.evidence.version_number || "")}</small></div>
                <div className="proposal-actions"><button className="icon-button" title="Approve proposal" onClick={() => void decideAnalysisProposal(proposal, "approve")}><Check size={15} /></button><button className="icon-button" title="Reject proposal" onClick={() => void decideAnalysisProposal(proposal, "reject")}><X size={15} /></button></div>
              </div>)}
            </section>}
          </> : <div className="empty-state"><BookOpen size={24} /><h1>Create your first project</h1><p>Your chapters and story data will stay in one workspace.</p></div>}
          {error && <p className="error toast" role="alert">{error}</p>}
        </section>
        <aside className="history-panel">
          <div className="sidebar-heading"><span>Version history</span><span className="muted">{versions.length}</span></div>
          {versions.map((version) => <div className="version-row" key={version.id}>
            <div><strong>Version {version.version_number}</strong><small>{version.content_format} · {new Date(version.created_at).toLocaleString()}</small></div>
            <button className="icon-button" title={`Restore version ${version.version_number}`} aria-label={`Restore version ${version.version_number}`} disabled={!chapter || dirty || saving || version.version_number === chapter.current_version} onClick={() => void restore(version)}><RotateCcw size={15} /></button>
          </div>)}
        </aside>
      </div>
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
    initializeApi(attempt > 0).then(() => api<User>("/auth/me"))
      .then((result) => { if (active) setUser(result.data); })
      .catch((error) => {
        if (!active) return;
        if (error instanceof ApiError && error.status === 401) setUser(null);
        else setStartupError(error instanceof Error ? error.message : "Could not start NovelForge");
      }).finally(() => { if (active) setChecked(true); });
    return () => { active = false; };
  }, [attempt]);
  useEffect(() => {
    const expired = () => setUser(null);
    window.addEventListener("novelforge:session-expired", expired);
    return () => window.removeEventListener("novelforge:session-expired", expired);
  }, []);
  if (!checked) return <main className="auth-shell"><p className="muted">Loading NovelForge…</p></main>;
  if (startupError) return <main className="auth-shell"><section className="auth-card"><h1>Unable to start NovelForge</h1><p className="error" role="alert">{startupError}</p><button className="primary" onClick={() => { setStartupError(""); setChecked(false); setAttempt((value) => value + 1); }}>Retry</button></section></main>;
  if (!user) return <AuthScreen onAuthenticated={setUser} />;
  return <Workspace user={user} onLogout={async () => { await api("/auth/logout", { method: "POST", headers: csrfHeaders() }); setSessionToken(""); setUser(null); }} />;
}
