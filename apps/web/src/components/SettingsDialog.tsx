import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  Check,
  LoaderCircle,
  Plug,
  Plus,
  Settings2,
  ShieldCheck,
  X,
} from "lucide-react";
import { api, csrfHeaders } from "../api";

type AISettings = {
  provider: string;
  base_url: string;
  chat_model: string;
  embedding_model: string;
  timeout_seconds: number;
  api_key_configured: boolean;
};
type Server = {
  id: string;
  name: string;
  transport: "stdio" | "streamable-http";
  command: string;
  args: string[];
  url: string;
  allowed_tools: string[];
  enabled: boolean;
  status: string;
  last_error?: string | null;
  bearer_token_configured?: boolean;
};
type DiscoveredTool = {
  name: string;
  description?: string;
  input_schema?: unknown;
};
const defaults: AISettings = {
  provider: "mock",
  base_url: "",
  chat_model: "mock-chat",
  embedding_model: "mock-embedding",
  timeout_seconds: 30,
  api_key_configured: false,
};
const errorText = (error: unknown) =>
  error instanceof Error ? error.message : "请求失败，请重试。";

export function SettingsDialog({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [tab, setTab] = useState<"model" | "mcp">("model");
  const [settings, setSettings] = useState<AISettings>(defaults);
  const [apiKey, setApiKey] = useState("");
  const [servers, setServers] = useState<Server[]>([]);
  const [loading, setLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [serverName, setServerName] = useState("");
  const [transport, setTransport] = useState<Server["transport"]>("stdio");
  const [command, setCommand] = useState("");
  const [args, setArgs] = useState("[]");
  const [url, setUrl] = useState("");
  const [allowedTools, setAllowedTools] = useState("");
  const [discovered, setDiscovered] = useState<
    Record<string, DiscoveredTool[]>
  >({});
  const [bearerToken, setBearerToken] = useState("");
  const [deletingServer, setDeletingServer] = useState<string | null>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
      if (event.key !== "Tab") return;
      const items = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]',
      );
      if (!items?.length) return;
      const first = items[0],
        last = items[items.length - 1];
      if (
        event.shiftKey &&
        (document.activeElement === first ||
          document.activeElement === dialogRef.current)
      ) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === last ||
          document.activeElement === dialogRef.current)
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
  }, [onClose]);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([
      api<AISettings>("/settings/ai"),
      api<Server[]>("/mcp/servers"),
    ])
      .then(([ai, mcp]) => {
        if (active) {
          setSettings(ai.data);
          setServers(mcp.data);
          setInitialized(true);
        }
      })
      .catch((error) => {
        if (active) setError(errorText(error));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [loadAttempt]);
  const runAction = async (action: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (error) {
      setError(errorText(error));
    } finally {
      setBusy(false);
    }
  };
  const saveModel = (event: FormEvent) => {
    event.preventDefault();
    void runAction(async () => {
      const { api_key_configured: _configured, ...fields } = settings;
      void _configured;
      const { data } = await api<AISettings>("/settings/ai", {
        method: "PATCH",
        headers: csrfHeaders(),
        body: JSON.stringify({
          ...fields,
          ...(apiKey ? { api_key: apiKey } : {}),
        }),
      });
      setSettings(data);
      setApiKey("");
      setNotice("模型设置已保存到本地。");
      onSaved();
    });
  };
  const testModel = () =>
    void runAction(async () => {
      const { data } = await api<{ ok: boolean; message: string }>(
        "/settings/ai/test",
        { method: "POST", headers: csrfHeaders() },
      );
      if (!data.ok) throw new Error(data.message);
      setNotice(data.message || "连接成功。");
    });
  const clearKey = () =>
    void runAction(async () => {
      const { data } = await api<AISettings>("/settings/ai", {
        method: "PATCH",
        headers: csrfHeaders(),
        body: JSON.stringify({ api_key: "" }),
      });
      setSettings(data);
      setApiKey("");
      setNotice("已清除模型密钥。");
      onSaved();
    });
  const createServer = (event: FormEvent) => {
    event.preventDefault();
    void runAction(async () => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(args);
      } catch {
        throw new Error(
          'Arguments must be a JSON array, for example ["--directory", "/path"].',
        );
      }
      if (
        !Array.isArray(parsed) ||
        parsed.some((item) => typeof item !== "string")
      )
        throw new Error("启动参数必须是 JSON 字符串数组。");
      const { data } = await api<Server>("/mcp/servers", {
        method: "POST",
        headers: csrfHeaders(),
        body: JSON.stringify({
          name: serverName.trim(),
          transport,
          command: transport === "stdio" ? command.trim() : "",
          args: transport === "stdio" ? parsed : [],
          url: transport === "streamable-http" ? url.trim() : "",
          allowed_tools: allowedTools
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
          enabled: false,
          ...(transport === "streamable-http" && bearerToken
            ? { bearer_token: bearerToken }
            : {}),
        }),
      });
      setServers((items) => [...items, data]);
      setServerName("");
      setCommand("");
      setUrl("");
      setArgs("[]");
      setAllowedTools("");
      setBearerToken("");
      setNotice("连接已添加且保持禁用，请先检查工具权限。");
    });
  };
  const serverAction = (server: Server, test: boolean) =>
    void runAction(async () => {
      if (test) {
        const { data } = await api<{
          ok: boolean;
          tools: DiscoveredTool[];
          message?: string;
        }>(`/mcp/servers/${server.id}/test`, {
          method: "POST",
          headers: csrfHeaders(),
        });
        if (!data.ok)
          throw new Error(
            data.message || `Connection failed for ${server.name}.`,
          );
        setDiscovered((items) => ({ ...items, [server.id]: data.tools }));
        setNotice(`Connection test completed for ${server.name}.`);
      } else {
        await api(`/mcp/servers/${server.id}`, {
          method: "PATCH",
          headers: csrfHeaders(),
          body: JSON.stringify({ enabled: !server.enabled }),
        });
        setNotice(`${server.name} ${server.enabled ? "已禁用" : "已启用"}.`);
      }
      setServers((await api<Server[]>("/mcp/servers")).data);
    });
  const toggleTool = (server: Server, tool: string) =>
    void runAction(async () => {
      const allowed_tools = server.allowed_tools.includes(tool)
        ? server.allowed_tools.filter((item) => item !== tool)
        : [...server.allowed_tools, tool];
      const { data } = await api<Server>(`/mcp/servers/${server.id}`, {
        method: "PATCH",
        headers: csrfHeaders(),
        body: JSON.stringify({ allowed_tools }),
      });
      setServers((items) =>
        items.map((item) => (item.id === data.id ? data : item)),
      );
      setNotice(`Tool permissions saved for ${server.name}.`);
    });
  const deleteServer = (server: Server) =>
    void runAction(async () => {
      await api(`/mcp/servers/${server.id}`, {
        method: "DELETE",
        headers: csrfHeaders(),
      });
      setServers((items) => items.filter((item) => item.id !== server.id));
      setDeletingServer(null);
      setNotice(`${server.name} removed. Story data was preserved.`);
    });
  return (
    <div className="modal-backdrop">
      <div
        className="settings-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        tabIndex={-1}
        ref={dialogRef}
      >
        <header className="dialog-header">
          <div>
            <p className="eyebrow">本地工作空间</p>
            <h1 id="settings-title">设置与连接</h1>
          </div>
          <button
            className="icon-button"
            title="关闭设置"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </header>
        <div
          className="settings-tabs"
          role="tablist"
          aria-label="设置分类"
        >
          <button
            role="tab"
            aria-selected={tab === "model"}
            onClick={() => {
              setTab("model");
              setNotice("");
            }}
          >
            <Settings2 size={16} /> 模型服务
          </button>
          <button
            role="tab"
            aria-selected={tab === "mcp"}
            onClick={() => {
              setTab("mcp");
              setNotice("");
            }}
          >
            <Plug size={16} /> MCP 工具
          </button>
        </div>
        <div className="dialog-content">
          {loading ? (
            <p className="loading-state">
              <LoaderCircle className="spin" size={18} /> 正在加载设置…
            </p>
          ) : !initialized ? (
            <div className="panel-empty">
              <Settings2 size={28} />
              <h2>暂时无法读取设置</h2>
              <p>
                请重新连接本地服务，再读取已保存配置。
              </p>
              <button
                className="secondary"
                onClick={() => setLoadAttempt((value) => value + 1)}
              >
                重新加载设置
              </button>
            </div>
          ) : tab === "model" ? (
            <form className="settings-form" onSubmit={saveModel}>
              <div
                className={`info-card ${settings.provider === "mock" ? "demo-info" : ""}`}
              >
                <ShieldCheck size={20} />
                <div>
                  <strong>
                    {settings.provider === "mock"
                      ? "演示模型 · 流程测试模式"
                      : "凭据保存在本地服务"}
                  </strong>
                  <p>
                    {settings.provider === "mock"
                      ? "当前回复为固定测试输出。连接模型服务后可进行真实生成。"
                      : "已保存的密钥不会回传界面。留空表示保留现有密钥。"}
                  </p>
                </div>
              </div>
              <label>
                服务提供方
                <select
                  value={settings.provider}
                  onChange={(event) =>
                    setSettings({ ...settings, provider: event.target.value })
                  }
                >
                  <option value="mock">演示模型 · 固定输出</option>
                  <option value="openai-compatible">OpenAI 兼容服务</option>
                </select>
              </label>
              <label>
                服务地址
                <input
                  type="url"
                  value={settings.base_url}
                  placeholder="https://api.example.com/v1"
                  onChange={(event) =>
                    setSettings({ ...settings, base_url: event.target.value })
                  }
                />
              </label>
              <div className="form-columns">
                <label>
                  对话模型
                  <input
                    required
                    value={settings.chat_model}
                    onChange={(event) =>
                      setSettings({
                        ...settings,
                        chat_model: event.target.value,
                      })
                    }
                  />
                </label>
                <label>
                  嵌入模型
                  <input
                    required
                    value={settings.embedding_model}
                    onChange={(event) =>
                      setSettings({
                        ...settings,
                        embedding_model: event.target.value,
                      })
                    }
                  />
                </label>
              </div>
              <label>
                API 密钥{" "}
                <span className="muted">
                  {settings.api_key_configured
                    ? "已保存密钥"
                    : "尚未配置密钥"}
                </span>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={apiKey}
                  placeholder={
                    settings.api_key_configured
                      ? "留空保留现有密钥"
                      : "输入服务密钥"
                  }
                  onChange={(event) => setApiKey(event.target.value)}
                />
              </label>
              {settings.api_key_configured && (
                <button
                  type="button"
                  className="text-button clear-key"
                  disabled={busy}
                  onClick={clearKey}
                >
                  清除已保存的模型密钥
                </button>
              )}
              <label>
                请求超时（秒）
                <input
                  type="number"
                  min={1}
                  max={120}
                  value={settings.timeout_seconds}
                  onChange={(event) =>
                    setSettings({
                      ...settings,
                      timeout_seconds: Number(event.target.value),
                    })
                  }
                />
              </label>
              <div className="dialog-actions">
                <button
                  type="button"
                  className="secondary"
                  disabled={busy}
                  onClick={testModel}
                >
                  测试已保存连接
                </button>
                <button className="primary" disabled={busy}>
                  <Check size={15} /> 保存模型设置
                </button>
              </div>
            </form>
          ) : (
            <section>
              <div className="info-card">
                <Plug size={20} />
                <div>
                  <strong>连接可信工具</strong>
                  <p>
                    新连接默认禁用。只授权需要的工具；测试 stdio 会启动配置的本地命令。
                  </p>
                </div>
              </div>
              <div className="server-list">
                {servers.length === 0 && (
                  <p className="muted small">尚未添加 MCP 连接。</p>
                )}
                {servers.map((server) => (
                  <article className="server-card" key={server.id}>
                    <div className="server-heading">
                      <strong>{server.name}</strong>
                      <span className="badge">
                        {server.enabled
                          ? server.status || "已启用"
                          : "已禁用"}
                      </span>
                    </div>
                    <p className="small muted">
                      {server.transport} ·{" "}
                      {server.transport === "stdio"
                        ? server.command
                        : server.url}
                    </p>
                    <p className="small">
                      允许的工具：{" "}
                      {server.allowed_tools.length
                        ? server.allowed_tools.join(", ")
                        : "无"}
                    </p>
                    {server.transport === "streamable-http" && (
                      <p className="small muted">
                        Bearer 令牌：{" "}
                        {server.bearer_token_configured
                          ? "已配置 · 不回显"
                          : "未配置"}
                      </p>
                    )}
                    {server.last_error && (
                      <p className="error">{server.last_error}</p>
                    )}
                    {discovered[server.id] && (
                      <div className="discovered-tools">
                        <p className="small muted">
                          已发现工具 · 勾选允许执行的工具
                        </p>
                        {discovered[server.id].length === 0 && (
                          <p className="small muted">
                            该服务没有返回工具。
                          </p>
                        )}
                        {discovered[server.id].map((tool) => (
                          <label className="discovered-tool" key={tool.name}>
                            <input
                              type="checkbox"
                              disabled={busy}
                              checked={server.allowed_tools.includes(tool.name)}
                              onChange={() => toggleTool(server, tool.name)}
                            />
                            <span>
                              <strong>{tool.name}</strong>
                              <small>
                                {tool.description || "未提供说明。"}
                              </small>
                            </span>
                          </label>
                        ))}
                      </div>
                    )}
                    <div className="review-actions">
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() => serverAction(server, true)}
                      >
                        测试连接
                      </button>
                      <button
                        className="text-button"
                        disabled={busy}
                        onClick={() => serverAction(server, false)}
                      >
                        {server.enabled ? "禁用" : "启用"} 连接
                      </button>
                      <button
                        className="text-button danger-text"
                        disabled={busy}
                        onClick={() => setDeletingServer(server.id)}
                      >
                        移除
                      </button>
                    </div>
                    {deletingServer === server.id && (
                      <div className="remove-confirmation">
                        <p>
                          移除此连接及其保存的凭据？
                        </p>
                        <div className="review-actions">
                          <button
                            className="secondary"
                            disabled={busy}
                            onClick={() => deleteServer(server)}
                          >
                            确认移除连接
                          </button>
                          <button
                            className="text-button"
                            onClick={() => setDeletingServer(null)}
                          >
                            保留连接
                          </button>
                        </div>
                      </div>
                    )}
                  </article>
                ))}
              </div>
              <form
                className="settings-form server-form"
                onSubmit={createServer}
              >
                <h2>
                  <Plus size={17} /> 添加 MCP 连接
                </h2>
                <label>
                  连接名称
                  <input
                    required
                    value={serverName}
                    onChange={(event) => setServerName(event.target.value)}
                  />
                </label>
                <label>
                  传输方式
                  <select
                    value={transport}
                    onChange={(event) =>
                      setTransport(event.target.value as Server["transport"])
                    }
                  >
                    <option value="stdio">本地命令 · stdio</option>
                    <option value="streamable-http">Streamable HTTP</option>
                  </select>
                </label>
                {transport === "stdio" ? (
                  <>
                    <label>
                      启动命令
                      <input
                        required
                        value={command}
                        onChange={(event) => setCommand(event.target.value)}
                        placeholder="/absolute/path/to/server"
                      />
                    </label>
                    <label>
                      启动参数（JSON 数组）
                      <input
                        value={args}
                        onChange={(event) => setArgs(event.target.value)}
                        spellCheck={false}
                      />
                    </label>
                  </>
                ) : (
                  <>
                    <label>
                      服务地址
                      <input
                        type="url"
                        required
                        value={url}
                        onChange={(event) => setUrl(event.target.value)}
                        placeholder="https://example.com/mcp"
                      />
                    </label>
                    <label>
                      Bearer 令牌（可选，仅写入）
                      <input
                        type="password"
                        autoComplete="new-password"
                        value={bearerToken}
                        onChange={(event) => setBearerToken(event.target.value)}
                        placeholder="仅保存在本地，不回显到界面"
                      />
                    </label>
                  </>
                )}
                <label>
                  允许的工具（逗号分隔）
                  <input
                    value={allowedTools}
                    onChange={(event) => setAllowedTools(event.target.value)}
                    placeholder="search, read_document"
                  />
                </label>
                <button className="secondary" disabled={busy}>
                  <Plus size={15} /> 添加为禁用连接
                </button>
              </form>
            </section>
          )}
          {error && (
            <p className="inline-error" role="alert">
              {error}
            </p>
          )}
          {notice && (
            <p className="success-notice" role="status">
              <Check size={16} />
              {notice}
            </p>
          )}
          {busy && (
            <p className="muted small" role="status">
              处理中…
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
