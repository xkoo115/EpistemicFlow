<div align="center">

# 🧬 EpistemicFlow

## AI 驱动的自动化科研平台

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 19](https://img.shields.io/badge/react-19-61DAFB.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.100+-green.svg)](https://fastapi.tiangolo.com/)

---

**EpistemicFlow** 是一个基于 FastAPI 和 Microsoft Agent Framework 构建的 AI 驱动的自动化科研平台。项目采用纯 Python 后端技术栈，结合 React + TypeScript 前端，旨在通过多智能体协作自动化科研流程，包括文献检索、实验设计、数据分析、论文写作等环节。

</div>

---

## 🌟 核心特性

| 特性 | 描述 |
|------|------|
| 🤖 **多智能体协作** | 基于 Microsoft Agent Framework，涵盖构思、研究、同行评审和图表审查（VLM）等多类智能体 |
| 🎯 **意图捕获与双轨分类** | 自动识别用户意图，支持研究论文 (Research Paper) 与综述论文 (Survey Paper) 双轨 |
| ⚡ **Map-Reduce 架构** | 支持高吞吐量的并行文献分析，提升处理效率 |
| 👥 **HITL (Human-in-the-Loop)** | 提供完善的人工干预机制，用户可随时中断并介入工作流 |
| 🔄 **Saga 状态机制** | 支持工作流状态的安全回滚，具有强大的系统容错及状态管理能力 |
| 🐳 **Docker 沙箱执行引擎** | 提供安全隔离的代码执行环境（如实验数据分析、代码运行评估） |
| 🎨 **现代化前端界面** | React + TypeScript + Tailwind CSS，利用 SSE 实现实时事件推送 |

---

## 🏗 技术栈

### 🐍 后端技术栈

```yaml
框架: FastAPI (异步)
AI 引擎: Microsoft Agent Framework
数据库:
  - 开发: SQLite
  - 生产: PostgreSQL
ORM: SQLAlchemy 2.0 (异步) + Alembic
沙箱隔离: Docker SDK
配置管理: Pydantic Settings
测试: pytest
队列任务: Celery/Redis (可选)
```

### ⚛️ 前端技术栈

```yaml
核心框架: React 19.2.4
开发语言: TypeScript 5.9.3
构建工具: Vite 8.0.3
样式框架: Tailwind CSS 3.4.19
样式处理: PostCSS 8.5.8 + Autoprefixer 10.4.27
通信方式: REST API + SSE (Server-Sent Events)
```

---

## 🚀 快速开始

### 1️⃣ 环境准备

确保您的系统已安装以下环境与依赖：

| 依赖 | 版本要求 | 用途 |
|------|----------|------|
| 🔵 **Python** | >= 3.11 | 后端运行环境 |
| 🟢 **Node.js** | 最新 LTS 版本 | 前端构建和运行 |
| 🐳 **Docker** | 最新稳定版 | 沙箱容器隔离 |
| 🐳 **Docker Compose** | 最新稳定版 | 容器编排管理 |
| 🔧 **Make** | 可选 | 快捷命令执行 |

### 2️⃣ 获取代码与配置服务

克隆项目到本地，并基于提供模板配置环境变量：

```bash
git clone <repository-url>
cd EpistemicFlow

# 从预设的环境变量模板创建自己的配置
cp .env.example .env
```

在 `.env` 中按需填入密钥和模型服务信息：

```env
# 核心大模型配置
LLM_GPT4__PROVIDER=openai
LLM_GPT4__API_KEY=your-openai-api-key

# OLLAMA 本地模型配置示例
LLM_OLLAMA__PROVIDER=ollama
LLM_OLLAMA__MODEL_NAME=llama2
LLM_OLLAMA__BASE_URL=http://localhost:11434

# 数据库配置（默认使用本地 SQLite）
DB_URL=sqlite+aiosqlite:///./epistemicflow.db
```

### 3️⃣ 一键启动 (推荐)

项目预置了 `Makefile` 提供便捷的全生命周期管理操作：

```bash
# 自动安装依赖 + 构建镜像 + 启动后端服务及数据库 + 执行数据库迁移
make quickstart
```

> 💡 **提示**: 如果不想使用 Make，也可通过 Docker Compose 直接拉起容器编排：
> ```bash
> docker-compose up -d
> ```

### 4️⃣ 手动分离式本地启动

#### 📋 前置依赖安装

**后端依赖：**
```bash
# 创建并激活虚拟环境 (以下为 Windows 示例，Linux/Mac 建议用 source .venv/bin/activate)
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 安装后端依赖
pip install -r requirements.txt
```

**前端依赖：**
```bash
cd frontend
npm install
# 核心依赖包括：
# - React 19.2.4
# - TypeScript 5.9.3
# - Vite 8.0.3
# - Tailwind CSS 3.4.19
# - Autoprefixer 10.4.27
# - PostCSS 8.5.8
cd ..
```

#### 🚀 启动后端应用

```bash
# 激活虚拟环境
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 初始化数据库
python scripts/init.py

# 启动 FastAPI 服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

后端启动成功后，您会看到类似输出：
```
INFO:     Will watch for changes in these directories: ['D:\\EpistemicFlow']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxx] using WatchFiles
INFO:     Started server process [xxxx]
INFO:     Waiting for application startup.
初始化数据库...
数据库表创建完成
INFO:     Application startup complete.
```

#### 🎨 启动前端应用

```bash
cd frontend
npm run dev -- --host
```

前端启动成功后，您会看到类似输出：
```
VITE v8.0.3  ready in xxx ms
➜  Local:   http://localhost:5173/
➜  Network: http://172.18.0.1:5173/
➜  Network: http://192.168.1.3:5173/
```

#### 🌐 访问应用

- **前端界面**: http://localhost:5173/
- **后端 API 文档**: http://localhost:8000/docs
- **后端 ReDoc**: http://localhost:8000/redoc

#### 🔧 常见问题解决

**问题 1: 前端显示 "Cannot find module 'tailwindcss'"**
```bash
cd frontend
npm install -D tailwindcss@^3.4.0 postcss autoprefixer
```

**问题 2: TypeScript 编译错误 "erasableSyntaxOnly"**
- 已在 `tsconfig.app.json` 中移除此选项
- 如仍有问题，确保 TypeScript 版本为 5.9.3 或更高

**问题 3: 端口被占用**
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <进程ID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

---

## 📖 如何使用

### 🎯 前端工作台界面

### 前端工作台界面
在浏览器中打开配置的前端服务 (默认 `http://localhost:5173/`)。平台将呈现三大核心板块：
- **AgentRoster (智能体列表)**: 查看、监控、及管理当前配置并激活的所有辅助智能体。
- **MainCanvas (主画布)**: 进行主要的流程交互，如发起构思意图输入，或者审核智能体生成的草案。
- **ActivityLog (活动日志)**: 通过后台 SSE 推送，实时记录并展示智能体执行细节 (例如 Agent Thought)、工具调用结果及沙箱中直接返回的内容输出。

### 🔄 工作流控制与人员介入 (HITL)
当系统处于关键决策节点（如科研构思完成后需用户确认，或遇到错误需调整）：
1. 流程会自动暂停并挂起。
2. 用户可在前端主画布审批当前的阶段性成果，或提供修改建议以改变其执行方向。
3. 若对某个阶段结果不满意，或系统提示不合格，可通过 Saga 的回滚接口直接退回到最近一次有效的检查点，从新规划执行。
*(若需通过 API 命令完成以上操作，可参阅 `docs/HITL_SAGA_USAGE.md` 进行高级控制)*

---

## 📡 API 接口查询与联调

后端启动后，可以直接访问以下自带的交互式接口文档环境：
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 🔌 常用核心 API 路由

| 方法 | 路由 | 描述 |
|------|------|------|
| POST | `/api/v1/workflows/` | 创建新的科研工作流 |
| GET | `/api/v1/workflows/{state_id}` | 查询工作流当下执行状态 |
| POST | `/api/v1/workflows/{state_id}/interrupt` | 触发人工强行中断 (HITL) |
| POST | `/api/v1/workflows/session/{session_id}/resume` | 提供反馈并恢复被中断的工作流 |
| POST | `/api/v1/workflows/session/{session_id}/rollback` | Saga 状态回滚处理 |
| GET | `/api/stream/events/{session_id}` | 建立 SSE 连接，接收系统级别实时推送 |
- `POST /api/v1/workflows/` — 创建新的科研工作流
- `GET /api/v1/workflows/{state_id}` — 查询工作流当下执行状态
- `POST /api/v1/workflows/{state_id}/interrupt` — 触发人工强行中断 (HITL)
- `POST /api/v1/workflows/session/{session_id}/resume` — 提供反馈并恢复被中断的工作流
- `POST /api/v1/workflows/session/{session_id}/rollback` — Saga 状态回滚处理
- `GET /api/stream/events/{session_id}` — 建立 SSE 连接，接收系统级别实时推送

---

## 📂 获取更多文档

项目中已内置了不同模块和演进阶段的专属文档：

| 文档 | 描述 |
|------|------|
| 📘 **API_DOCUMENTATION.md** | 详尽且包含 Request / Response Demo 的 API 接口定义 |
| 📗 **docs/HITL_SAGA_USAGE.md** | 人工干预与状态回滚高级用法说明 |
| 📙 **docs/QUICKSTART_PHASE4.md** | 第四阶段测试（包含 Docker 沙箱、VLM 验证）的独立快速入门指北 |
| 📕 **frontend/README.md** | 前端工作指引及进一步开发明细 |

---

## 🗺 开发路线图

| 阶段 | 状态 | 描述 |
|------|------|------|
| 🏗️ **阶段一** | ✅ 已完成 | FastAPI 脚手架、架构搭建、数据库初始化 |
| 🤖 **阶段二** | ✅ 已完成 | 构思、研究等多角色智能体核心与 Map-Reduce 架构定义 |
| 👥 **阶段三** | ✅ 已完成 | HITL 人工干预设计、Saga 状态容错执行与回滚 |
| 🐳 **阶段四** | ✅ 已完成 | Docker 安全沙箱代码执行引擎、VLM 图表审查及同行打分评审 |
| 📝 **阶段五** | 🚧 进行中 | 论文撰写及评审流程进一步闭环优化 |
| 🎨 **阶段六** | 📋 计划中 | 前端可视化、多画布面板与用户交互的深入完善 |

---

## 🤝 贡献与支持

我们欢迎任何形式的贡献！如果您想为项目做出贡献，请遵循以下步骤：

1. 🍴 **Fork** 项目代码仓
2. 🌿 **创建分支** - 建立属于您的 Feature 或 Bugfix 分支
3. 💾 **提交变更** - 提交相关的变更、测试及更新记录
4. 📤 **推送代码** - 推送到远程分支并发起 Pull Request (PR) 申请合并

---

## 📄 许可证

本项目遵循 [MIT License](LICENSE) 协议。

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给我们一个 Star！**

Made with ❤️ by EpistemicFlow Team

</div>

## 📄 许可证

本项目遵循 [MIT License] 协议。
