import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  Bot,
  Check,
  ChevronDown,
  CircleStop,
  LoaderCircle,
  Play,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";
import { api, csrfHeaders } from "../api";

export type Source = {
  chunk_id?: string;
  document_id?: string;
  title?: string;
  source_type?: string;
  source_id?: string;
  source_revision?: number;
  content?: string;
  score?: number;
};
type Step = {
  id: string;
  sequence: number;
  kind: string;
  status: string;
  tool_name?: string | null;
  arguments?: Record<string, unknown>;
  result?: unknown;
  error?: string | null;
};
type Run = {
  id: string;
  prompt: string;
  status: string;
  output: string;
  error?: string | null;
  provider: string;
  is_mock: boolean;
  model: string;
  steps: Step[];
  sources?: Source[];
  created_at: string;
};
const activeStates = new Set(["queued", "running", "waiting_approval"]);
const runLabels: Record<string, string> = {queued:"排队中",running:"执行中",waiting_approval:"等待审批",succeeded:"已完成",failed:"失败",cancelled:"已取消",interrupted:"已中断",rejected:"已拒绝",pending:"待执行"};
const statusLabel = (status: string) => runLabels[status] || status;
const message = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "请求失败，请重试。";

export function SourceList({ sources }: { sources: Source[] }) {
  return (
    <div className="source-list">
      {sources.map((source, index) => (
        <details
          className="source-card"
          key={source.chunk_id || `${source.document_id}-${index}`}
        >
          <summary>
            <span className="source-number">{index + 1}</span>
            <span>
              {source.title || "故事来源"}
              <small>
                {source.source_type?.replaceAll("_", " ") || "knowledge"} ·
                修订 {source.source_revision ?? "—"}
              </small>
            </span>
            <ChevronDown size={14} />
          </summary>
          <p>{source.content || "未返回来源摘要。"}</p>
          <small className="source-id">
            来源{" "}
            {source.source_id ||
              source.document_id ||
              source.chunk_id ||
              "无来源标识"}
          </small>
        </details>
      ))}
    </div>
  );
}

export function AgentWorkspace({
  novelId,
  draftDirty,
}: {
  novelId: string;
  draftDirty: boolean;
}) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [useMcp, setUseMcp] = useState(false);
  const base = `/novels/${novelId}/agent/runs`;
  const refresh = useCallback(async () => {
    setError("");
    try {
      const result = await api<Run[]>(base);
      setRuns(result.data);
      setRun((current) =>
        current
          ? result.data.find((item) => item.id === current.id) || current
          : result.data[0] || null,
      );
    } catch (error) {
      setError(message(error));
    } finally {
      setLoading(false);
    }
  }, [base]);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  const runId = run?.id;
  const running = Boolean(run && activeStates.has(run.status));
  useEffect(() => {
    if (!runId || !running) return;
    let active = true;
    const timer = window.setInterval(() => {
      void api<Run>(`${base}/${runId}`)
        .then(({ data }) => {
          if (!active) return;
          setRun(data);
          setRuns((items) =>
            items.map((item) => (item.id === data.id ? data : item)),
          );
        })
        .catch((error) => {
          if (active) setError(message(error));
        });
    }, 1200);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [base, runId, running]);
  const start = async (event: FormEvent) => {
    event.preventDefault();
    if (
      !prompt.trim() ||
      busy ||
      draftDirty ||
      runs.some((item) => activeStates.has(item.status))
    )
      return;
    setBusy(true);
    setError("");
    try {
      const { data } = await api<Run>(base, {
        method: "POST",
        headers: csrfHeaders(),
        body: JSON.stringify({
          prompt: prompt.trim(),
          max_rounds: 6,
          max_tool_calls: 12,
          max_seconds: 60,
          max_tokens: 12000,
          use_mcp: useMcp,
        }),
      });
      setRun(data);
      setRuns((items) => [data, ...items]);
      setPrompt("");
    } catch (error) {
      setError(message(error));
    } finally {
      setBusy(false);
    }
  };
  const act = async (path: string, payload?: unknown) => {
    if (
      !run ||
      busy ||
      (draftDirty &&
        Boolean((payload as { approve?: boolean } | undefined)?.approve))
    )
      return;
    setBusy(true);
    setError("");
    try {
      await api(`${base}/${run.id}/${path}`, {
        method: "POST",
        headers: csrfHeaders(),
        ...(payload ? { body: JSON.stringify(payload) } : {}),
      });
      const { data } = await api<Run>(`${base}/${run.id}`);
      setRun(data);
      setRuns((items) =>
        items.map((item) => (item.id === data.id ? data : item)),
      );
    } catch (error) {
      setError(message(error));
    } finally {
      setBusy(false);
    }
  };
  const selectRun = async (selected: Run) => {
    setRun(selected);
    setError("");
    try {
      const { data } = await api<Run>(`${base}/${selected.id}`);
      setRun((current) => (current?.id === selected.id ? data : current));
    } catch (error) {
      setError(message(error));
    }
  };
  return (
    <section
      className="tool-workspace agent-workspace"
      aria-labelledby="agent-title"
    >
      <header className="section-header">
        <div>
          <p className="eyebrow">可追溯的创作协作</p>
          <h1 id="agent-title">创作助手</h1>
          <p className="muted">
            检索故事，核对细节，逐步审核改动。
          </p>
        </div>
        <button
          className="icon-button"
          title="刷新任务"
          onClick={() => void refresh()}
        >
          <RefreshCw size={17} />
        </button>
      </header>
      <div className="safety-note">
        <ShieldCheck size={18} />
        <span>
          助手使用已保存的故事数据，修改操作需要你的批准。
        </span>
      </div>
      <form className="agent-composer" onSubmit={start}>
        <label htmlFor="agent-prompt">描述这次任务</label>
        <textarea
          id="agent-prompt"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="例如：核对灯塔设定与第一章是否一致，并整理人物提案。"
          rows={3}
          required
          maxLength={20000}
        />
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={useMcp}
            onChange={(event) => setUseMcp(event.target.checked)}
          />{" "}
          允许本次任务使用已启用的 MCP 工具
        </label>
        <div className="composer-footer">
          <small>
            {draftDirty
              ? "请先保存正文，再开始任务或批准操作。"
              : "上限 6 轮 · 12 次工具调用 · 60 秒"}
          </small>
          <button
            className="primary"
            disabled={
              busy ||
              draftDirty ||
              !prompt.trim() ||
              runs.some((item) => activeStates.has(item.status))
            }
          >
            <Play size={14} /> 开始任务
          </button>
        </div>
      </form>
      {error && (
        <div className="inline-error" role="alert">
          {error}
          <button className="text-button" onClick={() => void refresh()}>
            重试
          </button>
        </div>
      )}
      {loading ? (
        <p className="loading-state" role="status">
          <LoaderCircle size={18} className="spin" /> 正在加载任务…
        </p>
      ) : (
        <div className="agent-layout">
          <nav className="task-list" aria-label="助手任务记录">
            <h2>
              最近任务 <span>{runs.length}</span>
            </h2>
            {runs.length === 0 && (
              <p className="muted small">任务记录会显示在这里。</p>
            )}
            {runs.map((item) => (
              <button
                key={item.id}
                className={`task-item ${item.id === run?.id ? "active" : ""}`}
                onClick={() => void selectRun(item)}
              >
                <span>{item.prompt}</span>
                <small>
                  <i className={`status-dot ${item.status}`} />
                  {statusLabel(item.status)}
                </small>
              </button>
            ))}
          </nav>
          <div className="task-detail">
            {run ? (
              <>
                <div className="task-heading">
                  <div>
                    <span className={`badge ${run.is_mock ? "warning" : ""}`}>
                      {run.is_mock
                        ? "演示模型 · 固定输出"
                        : `${run.provider} · ${run.model}`}
                    </span>
                    <h2>{run.prompt}</h2>
                    <p className="muted small" role="status">
                      {statusLabel(run.status)} ·{" "}
                      {new Date(run.created_at).toLocaleString()}
                    </p>
                  </div>
                  {activeStates.has(run.status) && (
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() => void act("cancel")}
                    >
                      <CircleStop size={15} /> 取消任务
                    </button>
                  )}
                </div>
                <ol className="step-list">
                  {run.steps.map((step) => (
                    <li key={step.id} className={`agent-step ${step.status}`}>
                      <div className="step-marker">
                        {step.status === "succeeded" ? (
                          <Check size={14} />
                        ) : step.status === "running" ? (
                          <LoaderCircle size={14} className="spin" />
                        ) : (
                          step.sequence
                        )}
                      </div>
                      <div className="step-content">
                        <div className="step-heading">
                          <strong>{step.tool_name || "模型处理"}</strong>
                          <span className="badge">
                            {statusLabel(step.status)}
                          </span>
                        </div>
                        {step.kind === "tool" && (
                          <small className="muted">
                            工具调用 · {step.tool_name}
                          </small>
                        )}
                        {step.arguments && (
                          <details open={step.status === "waiting_approval"}>
                            <summary>操作参数</summary>
                            <pre>{JSON.stringify(step.arguments, null, 2)}</pre>
                          </details>
                        )}
                        {step.result != null && (
                          <details>
                            <summary>执行结果</summary>
                            <pre>
                              {typeof step.result === "string"
                                ? step.result
                                : JSON.stringify(step.result, null, 2)}
                            </pre>
                          </details>
                        )}
                        {step.error && <p className="error">{step.error}</p>}
                        {step.status === "waiting_approval" && (
                          <div className="approval-card">
                            <ShieldCheck size={18} />
                            <p>
                              请核对以上参数。批准只授权这一次工具调用，设定提案仍需独立审核后采纳。
                            </p>
                            <div className="review-actions">
                              <button
                                className="primary"
                                disabled={busy || draftDirty}
                                onClick={() =>
                                  void act(`steps/${step.id}/decision`, {
                                    approve: true,
                                  })
                                }
                              >
                                <Check size={14} /> 批准操作
                              </button>
                              <button
                                className="secondary"
                                disabled={busy}
                                onClick={() =>
                                  void act(`steps/${step.id}/decision`, {
                                    approve: false,
                                  })
                                }
                              >
                                <X size={14} /> 拒绝
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
                {run.error && (
                  <p className="inline-error" role="alert">
                    {run.error}
                  </p>
                )}
                {run.output && (
                  <section className="agent-output">
                    <h3>任务回复</h3>
                    <p>{run.output}</p>
                  </section>
                )}
                {Boolean(run.sources?.length) && (
                  <section>
                    <h3>引用的故事来源</h3>
                    <SourceList sources={run.sources!} />
                  </section>
                )}
              </>
            ) : (
              <div className="panel-empty">
                <Bot size={32} strokeWidth={1.3} />
                <h2>从一个明确任务开始</h2>
                <p>
                  查找设定、检查连续性，或整理待审提案。每一步执行及其来源都会保留。
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
