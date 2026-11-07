# NovelForge

[English](README.md) | [简体中文](README.zh-CN.md)

NovelForge 是一款开源小说创作工作台，正式设定由作者控制并保留版本历史。当前产品方向为 **Desktop-Local First（桌面本地优先）**：优先交付 Windows 和 macOS 桌面版，项目数据保存在用户本机。

> **开发状态：**仓库目前已有 NF-012 以前的后端和 Web 基础，但还不是可安装的桌面应用。NF-010 至 NF-012 尚有验收缺口，详见[路线图](docs/ROADMAP.md)。当前没有 Tauri 桌面壳、打包的 Python sidecar、正式 SQLite 本地模式、FTS5 索引或安装包。

## 当前进度

- 已实现的基础包括：用户身份与小说归属、正式设定 CRUD 和审批历史、大纲与章节、不可变章节版本、接入后端的 Web 编辑器、AI Provider 接口、知识摄取/检索原型和 Context Compiler。
- 截至审查提交 `27360af`，本地 API 测试为 57 项通过，最近一次 GitHub CI 通过。这些结果不代表桌面打包完成，也不代表 NF-010 至 NF-012 的全部验收条件已满足。
- 审查时 GitHub 仓库没有 Issues；同步后已创建 NF-013 至 NF-022 的远程跟踪 Issue（#1–#10），其中 NF-018 和 NF-020 标记为 deferred，见 [ROADMAP.md](docs/ROADMAP.md)。
- 当前可运行的是开发环境中的 API 和 Web 应用。首批正式安装目标为 Windows x64 EXE 和 macOS DMG。Android 和远程 SaaS/自托管服务暂缓。

## 桌面版目标

目标技术栈为 React + Vite、Tauri 2、随应用打包的 FastAPI Python sidecar、SQLAlchemy/Alembic 和 SQLite。数据库计划放入系统用户级应用数据目录，全文检索计划使用 SQLite FTS5。模型 API 凭据由本地配置，并且不进入浏览器构建产物或日志。sidecar 必须仅监听 loopback、校验本地请求授权，随桌面应用启动/退出，并在升级时保留用户数据。

以上是目标架构，不代表功能已经实现。向量检索应通过适配接口隔离。当前原型将向量存为 JSON，并由 Python 计算 cosine 相似度；FTS5 和可打包的向量方案需要先经过专门设计与测试。

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
