import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Check, Library, Plus, Search, X } from "lucide-react";
import { api, csrfHeaders } from "../api";
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
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);
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
          : "无法加载资料列表。",
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
            "索引失败，已保存的资料显示在下方，请检查。",
        );
      setTitle("");
      setContent("");
      setAdding(false);
      setNotice(
        "资料已保存并索引，可按可见范围筛选检索。",
      );
      try {
        await loadDocuments();
      } catch {
        setError(
          "资料已保存，但列表刷新失败。重新进入知识与设定可再次加载。",
        );
      }
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "索引失败，输入内容已保留。",
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
      setSelectedSource(data.results[0] || null);
      setSearched(true);
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "检索失败，请缩小关键词范围后重试。",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="tool-workspace" aria-labelledby="knowledge-title">
      <header className="section-header">
        <div>
          <p className="eyebrow">故事资料</p>
          <h1 id="knowledge-title">知识与设定</h1>
          <p className="muted">
            检索已保存资料，核对每一条来源。
          </p>
        </div>
        <button
          className="secondary"
          onClick={() => setAdding((value) => !value)}
        >
          {adding ? <X size={15} /> : <Plus size={15} />}
          {adding ? "收起资料表单" : "添加资料"}
        </button>
      </header>
      {adding && (
        <form className="material-form settings-form" onSubmit={ingest}>
          <h2>添加故事资料</h2>
          <p className="small muted">
            索引会使用已配置的嵌入服务，请仅提交允许该服务处理的资料。
          </p>
          <label>
            资料标题
            <input
              required
              maxLength={500}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="人物笔记、场景参考或世界观细节"
            />
          </label>
          <label>
            资料正文
            <textarea
              required
              maxLength={200000}
              rows={6}
              value={content}
              onChange={(event) => setContent(event.target.value)}
            />
          </label>
          <label>
            可见范围
            <select
              value={visibility}
              onChange={(event) => setVisibility(event.target.value)}
            >
              <option value="draft">草稿 · 仅显式包含时检索</option>
              <option value="approved">
                已批准 · 可用于故事检索
              </option>
              <option value="private">私有 · 不参与检索</option>
            </select>
          </label>
          <button
            className="primary"
            disabled={busy || !title.trim() || !content.trim()}
          >
            <Check size={15} />
            {busy ? "正在索引…" : "保存并索引"}
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
          检索故事资料
        </label>
        <div className="search-input">
          <Search size={18} />
          <input
            id="knowledge-query"
            placeholder="搜索人物、地点、事件或细节…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            required
            maxLength={2000}
          />
          <button className="primary" disabled={busy || !query.trim()}>
            {busy ? "正在检索…" : "搜索"}
          </button>
        </div>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={includeDrafts}
            onChange={(event) => setIncludeDrafts(event.target.checked)}
          />{" "}
          包含草稿资料
        </label>
      </form>
      {error && (
        <p className="inline-error" role="alert">
          {error}
        </p>
      )}
      {searched && (
        <p className="muted small" role="status">
          {sources.length} 条来源 ·{" "}
          {includeDrafts
            ? "已批准与草稿资料"
            : "仅已批准资料"}
        </p>
      )}
      {sources.length ? (
        <div className="knowledge-results">
          <div className="result-list" aria-label="检索结果">
            {sources.map((source, index) => <button key={source.chunk_id || index} className={`result-card ${selectedSource === source ? "active" : ""}`} onClick={() => setSelectedSource(source)} aria-pressed={selectedSource === source}>
              <strong>{source.title || "故事来源"}</strong>
              <small>{source.source_type?.replaceAll("_", " ")} · 修订 {source.source_revision ?? "—"}</small>
              <p>{source.content}</p>
            </button>)}
          </div>
          {selectedSource && <aside className="source-detail" aria-label="来源详情">
            <h2>来源详情</h2><h3>{selectedSource.title || "故事来源"}</h3>
            <span className="badge">修订 {selectedSource.source_revision ?? "—"}</span>
            <p>{selectedSource.content || "未返回来源摘要。"}</p>
            <small className="source-id">来源 {selectedSource.source_id || selectedSource.document_id || selectedSource.chunk_id || "无来源标识"}</small>
          </aside>}
        </div>
      ) : (
        <div className="panel-empty">
          <Library size={34} strokeWidth={1.3} />
          <h2>
            {searched ? "没有找到匹配资料" : "让每个细节有据可查"}
          </h2>
          <p>
            {searched
              ? "换个关键词，或先添加资料。已保存的故事资料完成索引后即可检索。"
              : "查找下一场景所需的已知事实。结果保留来源和修订，便于核对。"}
          </p>
        </div>
      )}
      <section className="indexed-material">
        <h2>
          已索引资料 <span>{documents.length}</span>
        </h2>
        {documents.length ? (
          documents.map((document) => (
            <article className="material-row" key={document.id}>
              <div>
                <strong>{document.title}</strong>
                <small>
                  修订 {document.source_revision} · {document.visibility}
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
            还没有索引资料。添加一份故事参考即可开始。
          </p>
        )}
      </section>
    </section>
  );
}
