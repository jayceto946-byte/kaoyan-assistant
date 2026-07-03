# 考研智能辅助系统

面向考研数学与专业课复习的本地智能辅助系统。项目围绕教材、错题、知识点和复习节奏构建，重点提供可追溯、可复习、可长期积累的学习辅助，而不是通用聊天机器人。

## 核心能力

- 教材导入与章节管理：支持 PDF/扫描件解析，章节内容进入本地索引。
- RAG 对话与讲解：结合教材片段、知识图谱和向量检索回答问题。
- 错题本：支持手动录入、图片 OCR、讲题、错因记录和复习状态。
- 习题库：支持 Word/PDF/文本导入、结构化候选题和练习状态管理。
- 学习记忆：记录概念接触、薄弱点和复习建议。
- 桌面端：Electron + FastAPI，本地运行，用户数据保存在本机。
- Docker 部署：提供本地服务化部署方式。

## 项目结构

```text
backend/      FastAPI 后端接口
frontend/     React + Vite 前端
desktop/      Electron 桌面壳与自动更新配置
graph/        LangGraph 对话与检索流程
ingestion/    教材解析、OCR、MinerU/Kimi 接入
knowledge/    知识图谱、概念记忆与可视化
memory/       错题本、习题库、间隔复习
scripts/      构建、导出、备份和部署脚本
docs/         部署、数据安全、桌面更新说明
tests/        后端与核心工作流测试
```

## 快速开始

### 后端

```powershell
cd D:\AI\agent\kaoyan-assistant
.\venv310\Scripts\Activate.ps1
python -m uvicorn backend.main:app --port 8000
```

### 前端

```powershell
cd D:\AI\agent\kaoyan-assistant\frontend
npm install
npm run dev
```

### 测试

```powershell
cd D:\AI\agent\kaoyan-assistant
.\venv310\Scripts\python.exe -m pytest -q
```

### 前端生产构建

```powershell
cd D:\AI\agent\kaoyan-assistant\frontend
npm run build
```

## 桌面版安装包

Windows 安装包不提交到源码仓库，请在 GitHub Releases 下载。

当前发布通道使用 `v*` tag 触发 `.github/workflows/desktop-release.yml`，构建完成后会把安装包发布到 Releases。手动发布时，需要上传：

- `kaoyan-assistant-desktop-setup-0.1.0.exe`
- `kaoyan-assistant-desktop-setup-0.1.0.exe.blockmap`
- `latest.yml`

## Docker 部署

详见 [docs/docker_deploy.md](docs/docker_deploy.md)。

```powershell
docker compose up -d --build
```

## 配置与数据安全

复制 `.env.example` 为 `.env` 后填写模型 Key。真实 `.env`、本地教材、向量库、用户学习数据、打包产物和虚拟环境均被 `.gitignore` 排除。

更多数据安全说明见 [docs/data_safety.md](docs/data_safety.md)。

## 开发约定

长期约束和架构说明见 [AGENTS.md](AGENTS.md)，版本记录和验证结果见 [patch_notes.md](patch_notes.md)。