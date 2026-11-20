import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Check, Library, Plus, Search, X } from "lucide-react";
import { api, csrfHeaders } from "../api";
import { SourceList } from "./AgentWorkspace";
import type { Source } from "./AgentWorkspace";
type KnowledgeDocument = {
  id: string;
  title: string;
  source_revision: number;
  visibility: string;
  status: string;
  error_message?: string | null;
};

export function KnowledgeWorkspace({ novelId }: { novelId: string }) {
  const [query, setQuery] = useState("");
  const [includeDrafts, setIncludeDrafts] = useState(false);
  const [sources, setSources] = useState<Source[]>([]);
  const [searched, setSearched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [visibility, setVisibility] = useState("draft");
  const [notice, setNotice] = useState("");
  const loadDocuments = useCallback(async () => {
    const { data } = await api<KnowledgeDocument[]>(
      `/novels/${novelId}/knowledge/documents`,
    );
    setDocuments(Array.isArray(data) ? data : []);
  }, [novelId]);
  useEffect(() => {
    void loadDocuments().catch((error) =>
      setError(
        error instanceof Error
          ? error.message
          : "Could not load indexed material.",
      ),
    );
  }, [loadDocuments]);
  const ingest = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim() || !content.trim() || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const { data } = await api<KnowledgeDocument>(
        `/novels/${novelId}/knowledge/documents`,
        {
          method: "POST",
          headers: csrfHeaders(),
          body: JSON.stringify({
            title: title.trim(),
            content: content.trim(),
            visibility,
            source_revision: 1,
          }),
        },
      );
      setDocuments((items) => [
        data,
        ...items.filter((item) => item.id !== data.id),
      ]);
      if (data.status === "failed")
        throw new Error(
          data.error_message ||
            "Indexing failed. Your source is listed below for review.",
        );
      setTitle("");
      setContent("");
      setAdding(false);
      setNotice(
        "Story material indexed. Search it using the visibility filter below.",
      );
      try {
        await loadDocuments();
      } catch {
        setError(
          "Your material was saved, but the document list could not refresh. Reopen Story knowledge to reload it.",
        );
      }
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Could not index material. Your entered text is preserved.",
      );
    } finally {
      setBusy(false);
    }
  };
  const search = async (event: FormEvent) => {
    event.preventDefault();
    if (!query.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const { data } = await api<{ results: Source[] }>(
        `/novels/${novelId}/knowledge/search?query=${encodeURIComponent(query.trim())}&include_drafts=${includeDrafts}&limit=20`,
      );
      setSources(data.results);
      setSearched(true);
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Search failed. Try a narrower query.",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="tool-workspace" aria-labelledby="knowledge-title">
      <header className="section-header">
        <div>
          <p className="eyebrow">The details that hold a world together</p>
          <h1 id="knowledge-title">Story knowledge</h1>
          <p className="muted">
            Search indexed story material and inspect its source revision.
          </p>
        </div>
        <button
          className="secondary"
          onClick={() => setAdding((value) => !value)}
        >
          {adding ? <X size={15} /> : <Plus size={15} />}
          {adding ? "Close material form" : "Add material"}
        </button>
      </header>
      {adding && (
        <form className="material-form settings-form" onSubmit={ingest}>
          <h2>Add story material</h2>
          <p className="small muted">
            Indexing uses your configured embedding provider. Add only material
            you want that provider to process.
          </p>
          <label>
            Material title
            <input
              required
              maxLength={500}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="A character note, scene reference, or world detail"
            />
          </label>
          <label>
            Source text
            <textarea
              required
              maxLength={200000}
              rows={6}
              value={content}
              onChange={(event) => setContent(event.target.value)}
            />
          </label>
          <label>
            Visibility
            <select
              value={visibility}
              onChange={(event) => setVisibility(event.target.value)}
            >
              <option value="draft">Draft — include only when requested</option>
              <option value="approved">
                Approved — available to story retrieval
              </option>
              <option value="private">Private — excluded from retrieval</option>
            </select>
          </label>
          <button
            className="primary"
            disabled={busy || !title.trim() || !content.trim()}
          >
            <Check size={15} />
            {busy ? "Indexing…" : "Index material"}
          </button>
        </form>
      )}
      {notice && (
        <p className="success-notice" role="status">
          <Check size={15} />
          {notice}
        </p>
      )}
      <form className="knowledge-search" onSubmit={search}>
        <label htmlFor="knowledge-query" className="field-label">
          Search your story
        </label>
        <div className="search-input">
          <Search size={18} />
          <input
            id="knowledge-query"
            placeholder="A character, place, event, or detail…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            required
            maxLength={2000}
          />
          <button className="primary" disabled={busy || !query.trim()}>
            {busy ? "Searching…" : "Search"}
          </button>
        </div>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={includeDrafts}
            onChange={(event) => setIncludeDrafts(event.target.checked)}
          />{" "}
          Include draft material
        </label>
      </form>
      {error && (
        <p className="inline-error" role="alert">
          {error}
        </p>
      )}
      {searched && (
        <p className="muted small" role="status">
          {sources.length} matching sources ·{" "}
          {includeDrafts
            ? "approved and draft material"
            : "approved material only"}
        </p>
      )}
      {sources.length ? (
        <SourceList sources={sources} />
      ) : (
        <div className="panel-empty">
          <Library size={34} strokeWidth={1.3} />
          <h2>
            {searched ? "No matching sources yet" : "Every detail has a place"}
          </h2>
          <p>
            {searched
              ? "Try a different phrase. Approved story facts and saved chapter material become searchable when indexed."
              : "Find the established facts behind your next scene. Results keep their source identity and revision so you can check them."}
          </p>
        </div>
      )}
      <section className="indexed-material">
        <h2>
          Indexed material <span>{documents.length}</span>
        </h2>
        {documents.length ? (
          documents.map((document) => (
            <article className="material-row" key={document.id}>
              <div>
                <strong>{document.title}</strong>
                <small>
                  revision {document.source_revision} · {document.visibility}
                </small>
                {document.error_message && (
                  <p className="error">{document.error_message}</p>
                )}
              </div>
              <span className="badge">{document.status}</span>
            </article>
          ))
        ) : (
          <p className="muted small">
            No material indexed yet. Add a story reference to begin.
          </p>
        )}
      </section>
    </section>
  );
}
