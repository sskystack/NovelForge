# NovelForge

[English](README.md) | [简体中文](README.zh-CN.md)

NovelForge 是一款开源小说创作工作台，正式设定由作者控制并保留版本历史。当前产品方向为 **Desktop-Local First（桌面本地优先）**：优先交付 Windows 和 macOS 桌面版，项目数据保存在用户本机。

> **开发状态（2026-11-20）：**已恢复桌面打包源码并修复本地运行链路，macOS Apple Silicon 0.1.1 DMG 已完成原生界面和冻结 sidecar 验证。当前支持 Tauri 2、打包 Python sidecar 和带备份迁移的 SQLite 本地模式；FTS5、完整 Agent 执行循环和 MCP 接入仍待补全。[路线图](docs/ROADMAP.md)保留了较早审查时的状态。

## 当前进度

- 已实现的基础包括：用户身份与小说归属、正式设定 CRUD 和审批历史、大纲与章节、不可变章节版本、接入后端的 Web 编辑器、AI Provider 接口、知识摄取/检索原型和 Context Compiler。
- 当前本地验证为 83 项 API 测试、19 项前端测试通过，并覆盖冻结 sidecar 的 12 项业务检查。原生界面已验证注册登录、中文项目和章节、保存、格式转换、AI 预览采纳、版本恢复、分析、重启保留数据和退出。模型请求使用 mock 和本地协议替身，未调用付费模型。
- 审查时 GitHub 仓库没有 Issues；同步后已创建 NF-013 至 NF-022 的远程跟踪 Issue（#1–#10），其中 NF-018 和 NF-020 标记为 deferred，见 [ROADMAP.md](docs/ROADMAP.md)。
- 当前已验证 macOS Apple Silicon DMG。Windows 打包配置保留，但尚未在本次工作中实机验证。macOS 采用 ad-hoc 签名，尚未完成 Developer ID 签名和公证。Android 和远程 SaaS/自托管服务暂缓。

## 桌面版目标

目标技术栈为 React + Vite、Tauri 2、随应用打包的 FastAPI Python sidecar、SQLAlchemy/Alembic 和 SQLite。数据库计划放入系统用户级应用数据目录，全文检索计划使用 SQLite FTS5。模型 API 凭据由本地配置，并且不进入浏览器构建产物或日志。sidecar 必须仅监听 loopback、校验本地请求授权，随桌面应用启动/退出，并在升级时保留用户数据。

上述桌面运行链路已经实现；打包和本地配置说明见 [Desktop README](apps/desktop/README.md)。检索仍为原型：向量存为 JSON，并由 Python 计算 cosine 相似度；FTS5 和可打包的向量索引尚待实现。

## 当前源码开发环境

当前开发流程需要 Python 3.12+、`uv`、Node.js 20+、npm，以及可选的 GNU Make。当前 API 默认连接 PostgreSQL，测试套件使用 SQLite。该开发环境不是面向普通用户的桌面安装方式。

```sh
./scripts/setup.sh
make dev-api       # API health: http://127.0.0.1:8000/health
make dev-web       # Web UI: http://localhost:5173
make test
make lint
make typecheck
```

Windows PowerShell 可运行 `./scripts/setup.ps1`。脚本安装开发依赖；不会生成桌面安装包，也不会把 Python/Node 运行时打包进应用。

## 项目文档

- [路线图与审查状态](docs/ROADMAP.md)
- [产品需求](docs/PRD.md)
- [架构](docs/ARCHITECTURE.md)
- [数据库设计](docs/DATABASE.md)
- [API 契约](docs/API.md) 和 [OpenAPI 文件](openapi.yaml)
- [Agent 与检索规格](docs/AGENT_SPEC.md)
- [开发指南](docs/DEVELOPMENT.md)
- [平台打包计划](docs/PLATFORM_PACKAGING.md)
- [工程 backlog](docs/GITHUB_ISSUES.md)

云端 SaaS、自托管服务器、Android 和多设备同步仍保留在 backlog 中，但暂不属于当前版本目标。

## 许可证

目标许可证为 Apache-2.0；仓库尚未添加许可证文件。
