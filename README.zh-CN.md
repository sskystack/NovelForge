# NovelForge

[English](README.md) | [简体中文](README.zh-CN.md)

NovelForge 是一款开源小说创作工作台，正式设定由作者控制并保留版本历史。自 2026-11-20 起，产品仅维护 **macOS 本地桌面版**，不再同步维护 Android、Windows 或其他平台。项目数据保存在用户本机。后续开发必须先阅读项目级 [AGENTS.md](AGENTS.md)。

> **开发状态（2026-11-20）：**已恢复桌面打包源码并修复本地运行链路，macOS Apple Silicon 0.1.1 DMG 已完成原生界面和冻结 sidecar 验证。0.2.0 已增加写作工作台、持久化 Agent 循环、Function Calling、FTS5/RAG、MCP SDK 和模型设置。实际能力、验证与限制见 [Agent 差距分析](docs/AGENT_GAP_ANALYSIS.md)。[路线图](docs/ROADMAP.md)保留历史审查状态，其跨平台计划已被 macOS-only 决策取代。

## 当前进度

- 已实现的基础包括：用户身份与小说归属、正式设定 CRUD 和审批历史、大纲与章节、不可变章节版本、接入后端的 Web 编辑器、AI Provider 接口、知识摄取/检索原型和 Context Compiler。
- 当前本地验证为 118 项 API 测试、47 项前端测试、6/6 固定检索回归，以及冻结 sidecar 的 16 项业务检查通过。原生界面已验证注册登录、中文项目和章节、保存、格式转换、AI 预览采纳、版本恢复、分析、重启保留数据和退出。模型请求使用 mock 和本地协议替身，未调用付费模型。
- 审查时 GitHub 仓库没有 Issues；同步后已创建 NF-013 至 NF-022 的远程跟踪 Issue（#1–#10），其中 NF-018 和 NF-020 标记为 deferred，见 [ROADMAP.md](docs/ROADMAP.md)。
- 当前已验证 macOS Apple Silicon DMG。Android/Windows 脚手架仅为历史文件，不再测试或发布。macOS 采用 ad-hoc 签名，尚未完成 Developer ID 签名和公证。其他平台已退出维护范围；远程 SaaS/自托管服务不属于当前版本目标。

## 桌面版目标

目标技术栈为 React + Vite、Tauri 2、随应用打包的 FastAPI Python sidecar、SQLAlchemy/Alembic 和 SQLite。数据库位于系统用户级应用数据目录，全文检索使用可选 SQLite FTS5。模型 API 凭据通过本地设置配置，不进入浏览器构建产物或日志；当前存入权限受限的本地数据库，尚未接入系统钥匙串加密。sidecar 必须仅监听 loopback、校验本地请求授权，随桌面应用启动/退出，并在升级时保留用户数据。

上述桌面运行链路已经实现；打包和本地配置说明见 [Desktop README](apps/desktop/README.md)。检索仍为原型：向量存为 JSON，并由 Python 计算 cosine 相似度；FTS5 已实现；大规模 ANN、真实语义检索和重排仍需实际模型与语料评测。Mock 仅为离线演示。

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

macOS 开发入口为 `./script/build_and_run.sh`，Codex Run 使用同一入口，开发资料默认存入被忽略的 `.local-data/`。`npm run tauri:build --prefix apps/desktop` 构建独立应用。PowerShell 脚本为不再维护的历史文件。

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

Android、Windows 和其他平台不再维护；历史 backlog 不构成支持承诺。云端 SaaS、多设备同步不属于当前版本目标。

## 许可证

目标许可证为 Apache-2.0；仓库尚未添加许可证文件。
