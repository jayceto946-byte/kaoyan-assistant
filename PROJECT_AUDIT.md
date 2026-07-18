# PROJECT_AUDIT

> 审阅日期：2026-07-18  
> 审阅方法：从完整目录树、入口注册、API、持久化实现、前端路由、依赖、测试与构建脚本反向追踪。原 README、项目名称和历史文件只用于交叉检查，不作为功能成立的主要证据。  
> 数据边界：没有写入或清理正式 data/。运行与截图使用 desktop/sample_data 的隔离副本以及独立 demo seed。

## 1. 项目定位

这是一个面向考研学习的本地优先学习辅助系统。当前主线不是通用聊天，而是把教材、章节、检索片段、概念、习题、错题、复习记录和会话组织成可持续积累的学习数据。

默认交付入口是 Electron；开发时可以分别运行 FastAPI 与 React/Vite。核心本地数据闭环可以在没有在线模型时使用，教材解析、OCR、回答生成、章节重点和知识图谱增强则依赖外部服务或本地模型。

## 2. 实际技术栈

| 层级 | 代码中使用的技术 |
|---|---|
| 桌面端 | Electron 37、electron-builder、electron-updater |
| 前端 | React 19、TypeScript 6、Vite 8、React Router 7、Tailwind CSS 4 |
| 内容渲染 | react-markdown、remark-gfm、remark-math、rehype-katex、KaTeX |
| 后端 | Python 3.10、FastAPI、Uvicorn、Pydantic 2 |
| LLM 编排 | LangGraph、LangChain、OpenAI 兼容客户端；默认配置指向 DeepSeek |
| 检索 | ChromaDB、sentence-transformers、BGE 中文嵌入、词法索引、知识图谱精确命中、可选 CrossEncoder |
| 文档摄取 | PyMuPDF、MinerU API/CLI/已有输出、Kimi 目录识别、PaddleOCR/外部 OCR |
| 持久化 | ChromaDB、多个 SQLite、JSON、PDF、图片与派生文件 |
| 测试与构建 | pytest、Vitest、ESLint、PyInstaller、electron-builder、Docker |

## 3. 目录与入口

    backend/main.py                 FastAPI 入口，注册 12 组 API 路由
    backend/api/                   chat、agent、books、exercises、mistakes、kg、
                                   reports、system、assets、highlights、jobs、backups
    frontend/src/main.tsx          React 入口
    frontend/src/App.tsx           页面路由
    frontend/src/api/client.ts     REST 与 SSE 客户端
    desktop/main.cjs               Electron 主进程
    graph/main_graph.py            问答主图与 run_graph_stream()
    ingestion/                     PDF、MinerU、OCR、切分、词法和向量索引
    knowledge/                     知识图谱、概念记忆、章节重点
    memory/                        习题、错题、SM-2、学习事件
    config.py                      模型、路径和运行配置
    requirements.txt               Python 依赖
    frontend/package.json          前端依赖与脚本
    desktop/package.json           Electron 依赖、脚本与打包配置
    tests/                         后端测试
    frontend/src/**/*.test.*       前端 Vitest
    scripts/                       构建、备份、重建索引、评测和样例脚本

前端实际路由：

- /：学习对话和主工作台
- /learning：学习情况、概念复习和知识图谱增强入口
- /mistakes：错题录入、列表、今日复习和统计
- /exercises：习题导入、练习会话和题库
- /books：教材导入
- /weekly：独立周报页，未列入主导航
- /highlights：章节重点页，未列入主导航
- /settings：系统健康、模型、资料库、数据安全与更新
- /kg：重定向到 /learning；KnowledgeGraphPage.tsx 是空文件

## 4. 架构与存储

    Electron
      → 启动 FastAPI 或打包后的 PyInstaller 后端
      → 生成每次启动使用的本地 API token
      → 将 React 应用加载到无边框窗口
      → 用户数据写入 Electron userData/data

    React/Vite
      → REST：教材、习题、错题、学习、系统、备份
      → SSE：plan → retrieve → chapter → generate → done/error

    FastAPI
      → graph/：规划、检索、章节准备、生成和反馈
      → ingestion/：教材摄取、切分和索引
      → knowledge/：知识图谱、概念记忆、章节重点
      → memory/：习题、错题、间隔复习与学习事件

    Storage
      → ChromaDB：向量索引
      → SQLite：习题、错题、学习事件和任务
      → JSON：会话与部分学习状态
      → Files：教材、章节、图片、索引和模型文件

后端的 LocalApiBoundaryMiddleware 在 Electron 模式下校验随机令牌，并限制不可信浏览器 Origin。教材归档、恢复、永久清理预览和备份恢复链也已经存在。

## 5. 主要功能调用链

### 5.1 教材问答

    ChatPage / useChat
      → POST /api/chat/stream
      → 读取会话历史并识别追问
      → graph.main_graph.run_graph_stream
      → 本地意图分类，必要时调用 planner
      → retrieval_node 混合检索
      → teach/summarize 时进入 chapter_subgraph
      → generator 流式生成
      → ThinkingFilter 与 LaTeX 清洗
      → feedback_node 本地概念链接和 learning event
      → SSE done 或 error
      → 前端累积正文、显示教材范围并保存会话

检索组合 KG occurrence 精确命中、Chroma 向量、词法索引、语义角色过滤和相邻 chunk。safe_retrieval 与节点异常处理提供降级，单个 collection 或知识图谱异常不应直接打断对话。

### 5.2 教材导入

    BooksPage / SettingsLibrary
      → books API 创建任务
      → PDF、本地路径、已有 MinerU 输出或外部结果
      → importer 标准化章节
      → chapter splitter
      → chunk 与词法索引
      → Chroma collection
      → 教材列表和任务状态更新

MinerU、扫描件 OCR 与 Kimi Vision 不是仓库内置服务。已有 MinerU 结果和文本层解析是可用的降级入口。

### 5.3 习题

    ExercisesPage
      → exercises API
      → memory.exercise_bank
      → SQLite 题库、导入批次和练习会话
      → 练习提交事务
      → 质量、状态、历史和会话进度
      → 可选写入错题本

支持手动录入、Word/PDF 文本抽取候选、教材页范围候选、批量编辑导入、最近批次回滚、暂停/恢复/放弃会话。自动分析和答案草稿依赖 LLM。

### 5.4 错题与复习

    MistakesPage
      → mistakes API
      → memory.mistake_book
      → SQLite
      → SM2Scheduler.review()
      → 下次复习时间与 review_history

图片录入前端支持裁剪、亮度/对比度/灰度和 OCR 后编辑。OCR、图片讲解和文本讲解依赖相应模型或 API；手动录入、CRUD 和复习调度不依赖外部服务。

### 5.5 学习情况与报告

    LearningPage / Chat dashboard
      → /api/kg/learning-summary
      → ConceptMemory + 错题 + 计划 + 图谱摘要

    WeeklyPage
      → /api/reports/weekly
      → 会话 + 错题 + 习题 + ConceptMemory
      → 规则聚合

周报不是模型评测。审阅发现报告字段兼容缺陷：核心练习和复习历史写入 date，而 reports.py 只读取 timestamp/time，因此可能低估 practiced_exercises 与 reviewed_mistakes。

### 5.6 条件式增强与 Agent

章节重点和知识图谱增强具备任务创建、轮询、结构化产物和查看接口，但需要教材派生数据和 LLM。

受控 Agent 后端已有只读工具选择、提案式工具注册和 API，前端也有请求方法与 AgentResultCard；主页面没有调用 runReadOnlyAgent 或 callAgentTool 的用户入口，尚未形成产品闭环。

## 6. 完成度分类

### 已完整实现

此处“完整”表示代码调用链、持久化与本地交互闭环存在，并不表示所有外部模型能力都已配置。

- React 路由、响应式布局和 Electron 桌面壳。
- 教材列表、切换、多教材隔离、归档、恢复和清理预览。
- REST/SSE 对话、会话历史、追问改写、阶段事件、错误事件和 thinking 过滤。
- 混合检索与检索源失败降级。
- 手动错题录入、CRUD、筛选、复习、SM-2 兼容调度和统计。
- 习题 CRUD、状态、练习历史、练习会话、批量导入与回滚。
- 概念记忆、学习事件、学习情况与规则周报 API。
- 系统健康检查、本地 API 边界、备份与恢复申请。
- Markdown、GFM 与 KaTeX 渲染。

### 部分实现或依赖外部条件

- PDF 自动摄取、扫描件识别、OCR 错题识别和图片讲解。
- 教材 RAG 回答生成和章节讲解。
- 章节重点与知识图谱增强。
- 自动答案草稿与题目自动分析。
- Electron 自动更新。
- Docker 和 Windows 安装包构建，本轮没有实际产出验证。
- 受控 Agent 的前端使用闭环。

### 仅有界面、渲染支撑或不可达入口

- AgentResultCard 有渲染能力，但没有主界面触发入口。
- /weekly 与 /highlights 可直接访问，但不在主侧栏。
- KnowledgeGraphPage.tsx 为空，/kg 已重定向。

### 规划中但尚未实现

- 完整通用 Tool Calling / Agent Loop 与可确认写操作流程。
- PWA、离线缓存、安装入口与推送。
- 独立目标和进度规划产品流程。
- 已发布可用的自动更新通道。
- 仓库级开源许可证与贡献规范。

## 7. 演示数据审计

desktop/sample_data 实际只有一套“优化设计”教材，而该目录历史 README 声称有三本，说明已过期。当前样例包含 PDF、章节/图片、进度目录、ChromaDB 和离线 BGE 模型；原始样例只有 0 道习题和少量错题，不足以覆盖所有展示页。

本次处理：

1. 将 sample_data 复制到仓库外的独立 demo-runtime/data，约 240 MB。
2. 新增 scripts/seed_docs_demo.py，只接受显式 data-dir。
3. 脚本拒绝正式 data/ 和 desktop/sample_data。
4. 使用稳定 ID 写入 6 道非个人习题、1 道错题和 1 个展示会话；可重复运行。
5. 正式数据和内置样例均未被修改。
6. 六张页面截图统一使用 1440 × 900，保存在 docs/images/。

开源发布前必须确认内置教材 PDF、OCR 派生内容和模型文件的分发授权，并考虑 Git LFS 或替换为可授权样例。

## 8. 实际安装、启动与验证

### 实测环境

- Python 3.10.11
- 后端隔离端口：127.0.0.1:8765
- 前端：127.0.0.1:5173
- 截图视口：1440 × 900
- 移动检查：390 × 844

### 实际结果

| 项目 | 结果 |
|---|---|
| pip install -r requirements.txt | 命令完成；既有 venv 仍有多组可选 OCR/解析依赖冲突 |
| frontend npm install | 成功 |
| desktop npm install | 成功 |
| FastAPI health | 200，version 1.0.0 |
| 后端 pytest | 137 passed，1 条 Starlette/httpx 弃用警告 |
| 前端 Vitest | 3 files / 9 passed |
| ESLint | 通过 |
| TypeScript + Vite build | 通过，2061 modules transformed |
| Web 主要页面 | 六类真实页面已通过浏览器自动化检查 |
| 浏览器控制台 | 主要页面无 error/warn |
| 移动布局 | 390 × 844 可渲染，无控制台错误 |
| Electron | 首次暴露 desktopAppUrl 作用域缺陷；最小修复后进入真实应用和首次引导 |
| demo seed | 直接运行、幂等运行、受保护路径拒绝均已验证 |

### 实测有效命令

    .\venv310\Scripts\python.exe -m pip install -r requirements.txt
    .\venv310\Scripts\python.exe -m pytest -q

    cd frontend
    npm.cmd install
    npm.cmd run test
    npm.cmd run lint
    npm.cmd run build
    npm.cmd run dev -- --host 127.0.0.1

    cd ..\desktop
    npm.cmd install
    npm.cmd run dev:existing

隔离后端实际以等价的 uvicorn 命令启动：

    .\venv310\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8765

标准开发端口可改为 8000。完整隔离变量见根 README 的“演示数据”。

## 9. 当前问题

### 发布阻断或高优先级

1. 仓库没有 LICENSE。不能声称采用 MIT、Apache-2.0 或其他开源协议。
2. desktop/sample_data 含教材 PDF 和派生内容，公开分发授权未知。
3. launch.ps1 仍使用废弃的 Gradio main.py web，并检查 requirements 未声明的 gradio。
4. install.ps1 创建 venv 而不是 venv310，只检查 3.10+，并生成旧 Gradio 启动脚本。
5. requirements.txt 只有宽泛下限，无锁文件。现有 venv 的 PaddleOCR、Marker、Pillow、protobuf、PyYAML、websockets 等可选栈存在冲突。

### 功能与一致性

6. 周报读取历史字段与核心存储写入字段不一致，可能低估已练习和已复习数量。
7. 受控 Agent 后端与前端结果卡片没有形成用户可触发闭环。
8. 独立 KnowledgeGraphPage 是空文件，旧名称容易造成误解。
9. 自动更新 GitHub owner/repo 仍是占位配置。
10. 部分前端 fetch 没有统一经过 api/client.ts，需要继续核验强制令牌模式下的认证一致性。
11. sample_data 的历史 README 与实际内容不一致。

### 本轮已修复

12. desktopAppUrl 原来被声明在 loadAppUrl 内部，却从 createWindow 和 IPC 外部调用。实际 Electron 窗口无法进入应用；移动为模块级函数后已复测通过。

## 10. 未验证范围

- 没有调用真实付费 LLM、Moonshot/Kimi、OCR 或 MinerU 服务，因此未评价生成质量、识别准确率和服务配额。
- 没有构建 Docker 镜像、PyInstaller 后端、NSIS 安装包或自动更新发布。
- 没有执行破坏性教材清理或真实备份恢复。
- 没有对内置教材和派生内容做法律授权判断。
- 未做跨平台 Electron 验证；当前实测环境是 Windows。

## 11. 审阅结论

当前仓库已经具备可运行的本地学习数据闭环、可展示的 React/Electron 界面和较完整的后端测试。适合作为“持续开发中的本地考研学习辅助系统”发布代码和项目材料，但不宜宣传为完全离线、开箱即用或已具备完整 Agent 能力。

正式公开前最重要的工作不是增加营销措辞，而是补充许可证、处理样例内容授权、锁定依赖、修正旧启动脚本和周报字段兼容，并验证可分发安装包。