# 开源小说工具：证据、采纳与边界

核实日期：2026-11-20。本文承接 [小说写作工具调研](NOVEL_WRITING_APP_RESEARCH.md)，只把官方文档中可核实的功能作为来源事实；产品取舍另行说明。未以 Stars、下载量或未经复现的质量指标作结论，也未运行这些项目来推断它们的实际生成质量。

**维护范围：NovelForge 从本轮起只维护 macOS。** 浏览器/Vite 是 macOS 应用前端的开发与测试入口，不代表独立网页、Android、Windows 或 Linux 产品承诺。学习竞品的跨平台经验，不引入额外平台构建、移动交互或第二套 CI。

## 1. 本轮抽查的官方证据

三组 README 和许可证文件（`COPYING` 或 `LICENSE`）均通过 GitHub 官方仓库实际读取；表内链接固定到核实时的默认分支提交，避免后续 README 变化影响判断。

| 项目 / 核实版本 | 官方文档中的事实 | NovelForge 的采纳判断 |
| --- | --- | --- |
| Manuskript / `5241f69ada7e06726f3c300b8851768380bf0900` | [README · Features](https://github.com/olivierkes/manuskript/blob/5241f69ada7e06726f3c300b8851768380bf0900/README.md#features)明确支持从一句 premise 扩展到段落和完整摘要，并支持角色、情节、大纲、索引卡、章节和场景整理。[Free Software](https://github.com/olivierkes/manuskript/blob/5241f69ada7e06726f3c300b8851768380bf0900/README.md#free-software)说明 GPL v3 或更高版本；[COPYING](https://github.com/olivierkes/manuskript/blob/5241f69ada7e06726f3c300b8851768380bf0900/COPYING)为 GPL v3 文本。 | 立即采用“先一句想法，再逐步展开”的交互顺序，原创实现轻量建项目向导；不复制 GPL 实现。多级概要和索引卡后置，避免要求作者先填完整世界资料。 |
| Hurricane NovelWriter / `98b55526d772ce2291350018e0e09dbc0181728c` | [README · 核心概念](https://github.com/Hurricane0698/novelwriter/blob/98b55526d772ce2291350018e0e09dbc0181728c/README.md#核心概念)区分 Studio 与 Atlas，说明按章相关世界模型注入、续写候选由作者采纳，以及“本章改变了什么？”提供原值、建议值和出处。[LICENSE](https://github.com/Hurricane0698/novelwriter/blob/98b55526d772ce2291350018e0e09dbc0181728c/LICENSE)为 MIT。 | 保留稿纸、知识与助手的职责分区；把检索来源、版本和作者审批接到现有领域模型。无需复制另一套世界模型或迁移现有正典数据结构。 |
| HadenKai 小说工坊 / `5bfd1402400c4a9892cf36ae6387b1458d3916cd` | [README · 功能亮点](https://github.com/HadenKai/novel-writer/blob/5bfd1402400c4a9892cf36ae6387b1458d3916cd/README.md#功能亮点)列出构思→起草→自检→修订，以及精修产物先预览、作者采用才落正文；README 也说明可撤销修改、上下文预算和离线临时数据测试。[LICENSE](https://github.com/HadenKai/novel-writer/blob/5bfd1402400c4a9892cf36ae6387b1458d3916cd/LICENSE)为 MIT。 | 采用明确的任务进度、待审批工具调用、隔离测试资料和预览后采纳原则。四阶段写作不是当前所有 Agent 请求的强制状态机；不把一个通用工具循环宣称为已实现完整四阶段创作。 |

原调研还列出 novelWriter、bibisco、云音小说工厂、Manong Novel 等。它们可继续作为候选方向，但本轮没有重新逐项核实其所有功能与许可，不据此复制代码或作能力承诺。

## 2. 已实现的产品闭环：从想法进入首章

原创组件：[ProjectOnboarding.tsx](../apps/web/src/components/ProjectOnboarding.tsx)。入口由 [App.tsx](../apps/web/src/App.tsx) 的项目按钮和空项目提示接入，并遵守现有未保存稿导航保护。

流程是：**定位 → 可选首章 → 创建前确认 → 进入项目/稿纸**。

1. 定位只要求故事标题，另收集可选 premise、逗号分隔题材和写作语言；题材会去空、去重，接受中英文逗号。
2. 作者可为首章命名并写下目标，也可跳过首章。首章目标存入 `writing_preferences.first_chapter_goal`，作为规划资料，不冒充已发生事件的章节摘要。
3. 确认页展示实际会保存的资料。创建只调用本地项目/章节 API，不发起模型调用，不生成正文，不创建或批准正典。
4. 完成后打开已创建项目；选建首章时，它是空白 `draft` 章节。作者可以直接写作，再有意识地调用 AI 或维护正典。

接口契约已对照现有代码验证，而非推测字段：

| 操作 | 使用的现有接口 | 契约来源 |
| --- | --- | --- |
| 保存小说定位 | `POST /api/v1/novels`：`title`、`premise`、`genre`、`language`、`writing_preferences` | [projects/schemas.py](../apps/api/novelforge/projects/schemas.py) 的 `NovelCreate` |
| 创建空白首章 | `POST /api/v1/novels/{id}/chapters`：`title`、`chapter_number: 1`、`status: "draft"` | [planning/schemas.py](../apps/api/novelforge/planning/schemas.py) 的 `ChapterCreate`，以及 [planning/models.py](../apps/api/novelforge/planning/models.py) 的 `ChapterStatus` |
| 本地会话与 CSRF | 复用 `api()` 和 `csrfHeaders()`，不另造请求路径或凭证存储 | [api.ts](../apps/web/src/api.ts) |

失败恢复是闭环的一部分：

- 项目请求失败：确认页保留资料，作者可返回修改或重试。
- 项目已成功而首章失败：组件保留已返回的项目对象，只重试首章请求，避免再次创建同名项目；也可选择进入已有项目后再加章节。
- 部分成功后点关闭或 Escape：仍把已保存项目交回项目列表，不让作者以为全部未保存。
- 提交中阻止双击重复提交与关闭；提供明确的忙碌文案、错误提示和局部成功提示。
- 对话框支持 Escape、Tab 焦点循环与关闭后的焦点恢复。

## 3. 与本轮其他实现的对应关系

| 借鉴方向 | 当前代码对应 | 边界与下一步 |
| --- | --- | --- |
| 稿纸优先、按需查阅设定与助手 | [App.tsx](../apps/web/src/App.tsx)、[styles.css](../apps/web/src/styles.css) 的写作工作台；[KnowledgeWorkspace.tsx](../apps/web/src/components/KnowledgeWorkspace.tsx)、[AgentWorkspace.tsx](../apps/web/src/components/AgentWorkspace.tsx) | 写作、知识、Agent 入口已有分工；不为复刻竞品再建立第二套页面或数据模型。 |
| 可见上下文与来源 | [ai/context.py](../apps/api/novelforge/ai/context.py)、[knowledge/service.py](../apps/api/novelforge/knowledge/service.py)、Agent 界面的来源与修订信息 | 展示检索命中与来源支持作者核对，不能等同于保证模型已理解全部正典或消除幻觉。 |
| 可审批的 Agent 工具调用 | [ai/agent_service.py](../apps/api/novelforge/ai/agent_service.py)、[ai/mcp_gateway.py](../apps/api/novelforge/ai/mcp_gateway.py)、Agent 审批界面 | 工具循环有预算与执行记录，外部工具需明确启用/授权；不在建项目向导中悄悄调用模型或工具。 |
| 正文草稿与正典提案分开 | [ai/generation_service.py](../apps/api/novelforge/ai/generation_service.py)、[ai/analysis_service.py](../apps/api/novelforge/ai/analysis_service.py)、[canon/revision_service.py](../apps/api/novelforge/canon/revision_service.py) | 复用版本和审批领域模型。并排文本 diff、逐块采纳和全部类型的撤销一致性需要单独设计与验证，不能仅凭“有审批”就宣称完成。 |
| 可读、可迁移的项目资料 | [projects/archive.py](../apps/api/novelforge/projects/archive.py) 的 JSON 工程包与清单校验 | 当前是工程备份，包含草稿、版本、生成/分析与审计相关资料；不能把它描述成已排除这些资料的纯成书导出。后续出版导出应使用独立字段白名单和隐私检查。 |

## 4. 后置项与理由

- **多级概要、人物访谈、世界规则向导**：可以沿用当前分步设计，但需要作者随时能跳过，并明确 AI 产物进入提案队列；本轮不扩展后端 schema 或自动写入正典。
- **项目概览与首章目标常驻显示**：当前目标已保存在写作偏好中，但除创建预览外还没有专门的持续编辑入口，也未自动注入后续提示词。后续应提供可见的读取/编辑位置，再决定是否让作者选入生成上下文。
- **场景卡、故事时间线、揭示顺序**：已有章节与正典状态是良好基础，但卡片排序和叙述时间需要稳定语义与独立交互验证；避免本轮并行扩展造成不一致。
- **固定四阶段 Agent**：先保留现有可观测工具执行、审批和失败恢复。固定构思/起草/自检/修订需要产物模型、阶段预算和失败语义，不能只替换进度标签。
- **章节生命周期**：研究提出的 `draft → review → canon → exported` 是产品建议，不是当前 API 枚举。当前支持 `planned / draft / in_progress / review / completed`；正典审批和导出应继续有独立记录，不能把 `canon`、`exported` 直接写入章节状态。
- **干净的 Markdown/EPUB/PDF 成书导出**：从工程备份另开出版路径，明确章节选择、顺序、版本、来源和排除字段，再做格式与内容校验。
- **按任务绑定模型**：模型/MCP 设置已有入口；本轮未声称每个写作模块都有独立模型绑定，后续应结合实际 task profile 而非增加一组空设置。

## 5. 许可、数据与维护边界

本轮只阅读官方文档并借鉴交互思想；新向导和测试是 NovelForge 原创代码，没有复制上述项目的实现、提示词、图标、字体、截图或正文。GPL 项目只作为产品研究；MIT 也不意味着忽略第三方资源各自许可。将来如确需引入代码，必须先逐文件核查许可和来源并保留必要声明，不从未知许可仓库移植。

竞品中的名家文风、同人素材、参考小说拆解不是本轮采纳内容。测试只使用自造的灯塔/信件故事资料；读取公开 README/许可证不涉及真实用户小说。向导只保存作者输入到当前本地服务，不向模型提供商发送文本。

macOS 运行、打包和发布继续使用现有 Tauri、Python sidecar 与 GitHub Actions。此向导功能没有新增 CircleCI 项目、跨平台矩阵或新的常驻服务。0.2.0 的纸白/墨绿设计已在 0.2.1 被石墨导航、冷白画布和蓝色操作替换；新的 Figma 设计稿与实现记录见 `UI_DESIGN.md` 和 `RELEASE_0.2.1.md`。

## 6. 实际验证与限制

新增测试：[ProjectOnboarding.test.tsx](../apps/web/src/components/ProjectOnboarding.test.tsx)。本轮实际执行：

```sh
cd apps/web
npm run test -- src/components/ProjectOnboarding.test.tsx
npm run typecheck
npx eslint src/components/ProjectOnboarding.tsx src/components/ProjectOnboarding.test.tsx
```

结果：**11 项向导测试通过；TypeScript 检查与新增组件 ESLint 通过。** 覆盖关闭/取消、返回时输入保留、完整定位与 CSRF 请求、跳过首章、项目失败重试、部分成功后仅重试首章、三种局部成功退出方式、提交期间防重复和键盘焦点行为。请求断言证明向导只调用项目与章节接口，没有 AI 或正典写请求。前端测试使用 mock fetch，没有启动真实数据库或发送真实模型请求。

这些测试验证前端请求契约和恢复行为，不证明远程模型质量，也不代替整包 macOS 验收。主代理负责集成测试、冻结 sidecar 与原生包检查；不得把未完成的签名、公证或后置功能写成已完成。

恢复保障的适用范围是同一次打开的向导中，**项目成功响应已经收到**之后发生的章节失败。现有创建接口没有幂等键；如服务器已提交但响应在网络中丢失、应用崩溃或窗口被系统终止，客户端无法单凭失败响应保证恰好创建一次。后续可单独评估幂等键与未完成向导恢复，当前不为此扩展已冻结后端。
