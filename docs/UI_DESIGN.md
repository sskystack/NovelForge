# NovelForge 0.2.1 — 中文 macOS 创作工作台

2026-11-20。产品仅维护 macOS。用户否定了 0.2.0 的暖纸/橄榄风格，本版完全替换其样式表，改用石墨导航、冷灰画布、白色正文页与克制蓝色动作。所有重要界面标签、表单、导航、保存和任务状态优先简体中文；模型输出、工具名称与服务错误保留原始内容，不伪装为本地生成。

## 实际 Figma 交付

通过官方 Figma MCP `create_new_file` 创建，并用 `create_session`、`use_figma` 实际写入可编辑节点。上一次 `whoami` 返回的 View 席位并没有阻止本次在 Draft 创建和编辑，不能将其描述为无权限或无稿。

文件：[NovelForge · macOS 中文创作工作台](https://www.figma.com/design/DogOPwqSYvOJtzXnsGXSZS)

| 设计稿 | 节点与链接 | 验证 |
| --- | --- | --- |
| 写作工作台 | [6:129](https://www.figma.com/design/DogOPwqSYvOJtzXnsGXSZS?node-id=6-129) | 已写入、官方截图导出并检查 |
| 知识与设定 | [7:2](https://www.figma.com/design/DogOPwqSYvOJtzXnsGXSZS?node-id=7-2) | 已写入、官方截图导出并检查 |
| 助手执行与审批 | [7:70](https://www.figma.com/design/DogOPwqSYvOJtzXnsGXSZS?node-id=7-70) | 已写入、官方截图导出并检查 |
| 模型与连接设置 | [8:2](https://www.figma.com/design/DogOPwqSYvOJtzXnsGXSZS?node-id=8-2) | 已写入、官方截图导出并检查 |
| 首次项目引导 | [8:74](https://www.figma.com/design/DogOPwqSYvOJtzXnsGXSZS?node-id=8-74) | 已写入、官方截图导出并检查 |
| 设计规范与状态板 | [8:136](https://www.figma.com/design/DogOPwqSYvOJtzXnsGXSZS?node-id=8-136) | 写入返回成功；截图时达到 Starter MCP 配额限制 |

规范板截图请求返回：`You've reached the Figma MCP tool call limit on the Starter plan.` 此限制发生在五屏和规范板已成功创建之后，阻止后续截图和微调，不表示设计文件没有完成。没有继续循环调用，也没有上传真实小说或任何凭据。

建立了 Primitive / Semantic 两套变量集合，包含 15 个颜色语义 token、8 个间距 token、6 个中文文字样式，以及默认/悬停/禁用按钮状态组件。基于现有代码组件清单检查了 Code Connect（无映射）、新文件（无既有屏幕）和官方可用库；搜索并导入了 Simple Design System Button 家族作为组件参考。macOS 社区 UI kit 提示需接受 Apple EULA，未代用户接受协议。新稿采用自有 token，避免将第三方移动风格直接套进 Tauri。

关键规范：

- 导航 `#171A21`，画布 `#F6F7FA`，内容 `#FFFFFF`，正文 `#242A35`。
- 主动作 `#5368F4`，悬停 `#4055DF`，选中背景 `#EEF1FF`。
- 分隔 `#E3E7EF`，错误、待审批、成功使用独立语义色。
- 界面使用本地 SF / 苹方字体；Figma 使用已验证存在的 Noto Sans SC 展示中文。正文 17px、行高 2；标题约 22px，重要说明和表单标签至少 12px。
- 单一浅色内容模式，固定深色导航不代表不完整的深色主题。未实现或声称自动深浅模式。

## 前端落地与结构变化

`apps/web/src/styles.css` 全量替换旧的累积覆盖规则，新版约 371 行紧凑规则，按窗口、书稿、检查器、知识/任务、设置、登录和 Mac 断点分组。颜色 token 和主要几何与 Figma 对齐；无远程字体、位图背景或装饰资源依赖。

1. 应用固定为 Mac 窗口高度。左侧项目栏、正文内容、右侧检查器分别滚动，正文底部保存状态和 AI 操作可达。
2. 1440 宽采用项目栏/正文/历史三栏；1100 和 900 宽保留项目栏与正文，历史通过显式检查器按钮打开并可关闭，带遮罩以表明覆盖状态。
3. 新建作品向导、快速新建、作品切换、章节新增仍调用真实接口。长章节名截断并提供完整 `title`，没有仅装饰的按钮。
4. 知识页从简单折叠列表调整为结果与来源详情双栏。选择结果显示该来源的确切修订、正文和标识；900 宽自动纵向排列。
5. 助手页保留独立任务输入、历史和执行步骤。任务状态中文显示，工具名、参数、结果、来源原样可查；批准仍绑定既有步骤。
6. 设置对话框采用左侧类别导航与单列表单；MCP 默认禁用、白名单逐项授权、模型和 HTTP 令牌只写入且读取 masked。
7. 项目向导加入“故事定位 / 首章方向 / 确认创建”步骤条，保留部分成功后的首章单独重试。

本地运行边界未改：`api.ts` 继续 Tauri 动态 loopback origin、本地 launch token、会话 bearer/sessionStorage 与 CSRF。没有硬编码桌面端口。未保存保护、保存期间新编辑跟踪、ETag 乐观并发、历史恢复为新版本、Markdown 安全转换、AI 预览后显式采纳均保留。

## 技能与连接能力

本次使用并阅读官方 `figma-create-new-file`、`figma-use`、`figma-generate-design`、`figma-generate-library`，以及 Plugin API / design-system references。Product Design index/audit/user-context/critical overrides 用于既有流程与截图审查；已有代码和当前界面是明确设计目标，无需等待用户补参考。Playwright skill 已读，实际界面输入全部通过 CUA 进行。

会话中官方 Figma MCP 可用并实际创建/编辑/截图；FastCtx 未暴露，文件检查使用 `rg`、批量 shell 与 Python。CUA Chrome 连接可用，浏览器清单没有 IAB，因此使用单独的 Chrome 测试标签。Artifact/Consensus 等工具与当前任务无关，没有将“工具已列出”说成“连接已验证”。

Build macOS Apps 与 CircleCI 技能已盘点。原生图标、签名和 DMG 属主代理；没有把 Tauri 重写为 SwiftUI。仓库 CI 为 GitHub Actions，没有添加重复 CircleCI。

## 真实验收证据

测试只使用聊天工作目录 `work/ui-qa/novelforge-ui.db` 的隔离 SQLite、合成账户与虚构小说《雾港来信》。未接触生产用户数据库，没有付费模型调用。该库包含上一轮已验证的知识、mock 运行、批准与取消记录。

本轮 CUA 实际验证：

- 中文登录后加载真实章节；1440×900、1100×800、900×740 三个 Mac 窗口尺寸。
- 三尺寸 `scrollWidth` 没有超过窗口宽度。900 宽正文内部滚动实际达到 `scrollTop=132`，内容高 820、可视高 688，底部动作可达。
- 900 宽显式打开、关闭故事检查器；遮罩与关闭入口存在，历史未被永久隐藏。
- 设置对话框真实打开并读取 masked 模型配置；项目向导真实打开并显示三步导航。
- 知识搜索真实返回来源并显示双栏详情；助手真实读取任务历史和中文终态。
- 最终浏览器控制台没有相关 error/warn，无框架错误遮罩。

曾遇到网页按钮无响应，最终经原生 Chrome AX 定位为浏览器密码管理器对合成测试密码弹出的原生提示，背景网页输入被拦截。关闭提示后按钮立即正常；不是应用事件、透明网页遮罩或 API 问题。没有修改产品逻辑来绕过浏览器提示。

截图在聊天输出目录 `outputs/novelforge-redesign/`：`figma-writing.png`、`figma-knowledge.png`、`figma-agent.png`、`figma-settings.png`、`figma-onboarding.png`、`figma-workflows.png`、`app-1440.png`、`app-1100.png`、`app-900.png`、`app-900-inspector.png`、`app-knowledge.png`、`app-agent.png`、`app-settings.png`、`app-onboarding.png`。

原有 47 项前端测试均通过中文标签适配，另补来源选择后详情精确匹配的关键测试；最终 48 项通过，typecheck、lint、build 全通过。主代理另已构建 0.2.1 DMG，并更新 `/Applications/NovelForge.app`：原生登录、合成旧项目读取、保存新增版本、知识来源检索、助手工具循环及设置/MCP 页面通过。Finder 简介和 DMG 窗口实际显示新图标，图标资源与嵌套签名校验通过；Dock 受当前 UI 工具窗口捕获限制未单独截图验收。原生截图为 `native-0.2.1-writing.png`、`installed-finder-icon.png` 和 `dmg-icon.png`。使用隔离资料，不读取真实书稿库；旧安装已备份，测试应用已退出。

## 清理与限制

本轮自建 API PID 36063、Vite 进程均已停止；测试 Chrome 标签已关闭、viewport override 已 reset。未关闭用户 Figma 标签或改动用户浏览记录。

- Figma Starter 配额限制阻止规范板最后一张截图和后续微调，五屏及规范板的创建和节点返回已完成。
- 自有任务/API 返回的英文模型输出与服务错误保留原文；通用界面与主要状态为中文。
- Vite 仍提示 TipTap 主 bundle 超过 500 kB，构建成功；未为压缩体积改动 Markdown 转换安全性。
- 本轮不实现 Android，不将小 Mac 窗口兼容声称为移动端产品。
