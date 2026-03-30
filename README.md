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
| 🚀 **一键启动** | 开箱即用，只需配置 API Key 即可启动完整系统 |

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
测试: pytest + Playwright E2E
队列任务: Celery/Redis (可选)
```

### ⚛️ 前端技术栈

```yaml
核心框架: React 19.2.4
开发语言: TypeScript 5.9.3
构建工具: Vite 8.0.1
样式框架: Tailwind CSS 3.4.19
流程可视化: React Flow (@xyflow/react)
通信方式: REST API + SSE (Server-Sent Events)
E2E 测试: Playwright
```

---

## 🚀 快速开始（一键启动）

### 📋 环境要求

| 依赖 | 版本要求 | 用途 |
|------|----------|------|
| 🔵 **Python** | >= 3.10 | 后端运行环境 |
| 🟢 **Node.js** | >= 18.0 | 前端构建和运行 |
| 🐳 **Docker** | 最新稳定版 (可选) | 沙箱容器隔离 |

### ⚡ 一键启动步骤

#### 步骤 1: 获取代码

```bash
git clone <repository-url>
cd EpistemicFlow
```

#### 步骤 2: 配置 API Key

**Windows:**
```bash
# 复制配置模板
copy .env.template .env

# 编辑配置文件，填入您的 API Key
notepad .env
```

**Linux/macOS:**
```bash
# 复制配置模板
cp .env.template .env

# 编辑配置文件，填入您的 API Key
nano .env  # 或使用您喜欢的编辑器
```

**必需配置项:**
```env
# DeepSeek 配置 (推荐，性价比高)
LLM_DEEPSEEK__API_KEY=your-api-key-here
LLM_DEEPSEEK__BASE_URL=https://api.deepseek.com
DEFAULT_LLM=deepseek

# 或使用 OpenAI
# LLM_GPT4__API_KEY=your-openai-api-key
# DEFAULT_LLM=gpt4
```

#### 步骤 3: 一键启动

**Windows:**
```bash
# 双击运行 start.bat 或在命令行执行:
start.bat
```

**Linux/macOS:**
```bash
# 添加执行权限
chmod +x start.sh

# 运行启动脚本
./start.sh
```

#### 步骤 4: 访问应用

启动成功后，浏览器会自动打开，或手动访问：

- **前端界面**: http://localhost:5173
- **后端 API 文档**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 🛑 停止服务

**Windows:**
```bash
stop.bat
```

**Linux/macOS:**
```bash
./stop.sh
```

---

## 🔧 支持的大模型

| 模型 | 配置前缀 | 获取 API Key |
|------|----------|--------------|
| **DeepSeek** (推荐) | `LLM_DEEPSEEK__` | https://platform.deepseek.com/ |
| **OpenAI GPT-4** | `LLM_GPT4__` | https://platform.openai.com/ |
| **Anthropic Claude** | `LLM_CLAUDE__` | https://console.anthropic.com/ |
| **Ollama** (本地免费) | `LLM_OLLAMA__` | https://ollama.ai/ |

### 配置示例

**DeepSeek (推荐):**
```env
LLM_DEEPSEEK__PROVIDER=deepseek
LLM_DEEPSEEK__API_KEY=sk-xxxxx
LLM_DEEPSEEK__BASE_URL=https://api.deepseek.com
LLM_DEEPSEEK__MODEL_NAME=deepseek-chat
DEFAULT_LLM=deepseek
```

**OpenAI GPT-4:**
```env
LLM_GPT4__PROVIDER=openai
LLM_GPT4__API_KEY=sk-xxxxx
LLM_GPT4__BASE_URL=https://api.openai.com/v1
LLM_GPT4__MODEL_NAME=gpt-4-turbo-preview
DEFAULT_LLM=gpt4
```

**Ollama (本地):**
```env
# 先安装 Ollama 并拉取模型: ollama pull llama2
LLM_OLLAMA__PROVIDER=ollama
LLM_OLLAMA__BASE_URL=http://localhost:11434
LLM_OLLAMA__MODEL_NAME=llama2
DEFAULT_LLM=ollama
```

---

## 🧪 测试

### E2E 测试 (Playwright)

```bash
cd frontend

# 运行所有 E2E 测试
npm run e2e

# UI 模式调试
npm run e2e:ui

# 显示浏览器运行
npm run e2e:headed

# 查看测试报告
npm run e2e:report
```

### 单元测试 (Vitest)

```bash
cd frontend

# 运行单元测试
npm run test

# UI 模式
npm run test:ui
```

### 后端测试 (pytest)

```bash
# 激活虚拟环境后
pytest

# 带覆盖率
pytest --cov=.
```

---

## 📖 使用指南

### 🎯 前端工作台界面

在浏览器中打开前端界面 (默认 `http://localhost:5173/`)，平台呈现三大核心板块：

- **AgentSidebar (智能体侧边栏)**: 查看智能体状态和 Saga 时间旅行树
- **WorkflowCanvas (主画布)**: 工作流执行和 HITL 干预界面
- **TerminalLog (活动日志)**: 通过 SSE 实时推送的智能体执行日志

### 🔄 HITL 人工干预流程

当系统处于关键决策节点时：

1. 工作流自动暂停，状态变为 `WAITING_FOR_HUMAN`
2. 主画布切换到 **干预仪表板**，显示 Diff 视图和结构化表单
3. 用户审核内容，填写修改建议
4. 点击"继续执行"，工作流恢复运行

### ⏪ Saga 时间旅行

在左侧 Saga 树中：

1. 点击任意历史节点
2. 在弹出的回滚模态框中输入纠偏指令
3. 系统从该检查点创建新分支继续执行

---

## 📡 API 接口

### 核心路由

| 方法 | 路由 | 描述 |
|------|------|------|
| POST | `/api/v1/workflow/` | 创建工作流 |
| GET | `/api/v1/workflow/{state_id}` | 查询工作流状态 |
| POST | `/api/v1/workflow/{state_id}/interrupt` | 触发 HITL 中断 |
| POST | `/api/v1/workflow/session/{session_id}/resume` | 恢复工作流 |
| POST | `/api/v1/workflow/session/{session_id}/rollback` | Saga 回滚 |
| GET | `/api/stream/events/{session_id}` | SSE 事件流 |

### SSE 事件类型

| 事件类型 | 描述 |
|----------|------|
| `agent_thought` | 智能体思考过程 |
| `tool_call_start` | 工具调用开始 |
| `tool_call_result` | 工具调用结果 |
| `sandbox_stdout` | 沙箱标准输出 |
| `workflow_stage_change` | 工作流阶段变更 |
| `hitl_interrupt` | HITL 中断事件 |
| `heartbeat` | 心跳 |

---

## 📂 项目结构

```
EpistemicFlow/
├── main.py                    # FastAPI 入口
├── .env                       # 环境配置 (需创建)
├── .env.template              # 配置模板
├── start.bat / start.sh       # 一键启动脚本
├── stop.bat / stop.sh         # 停止脚本
├── api/                       # API 路由
│   ├── v1/                    # REST API
│   └── stream.py              # SSE 流式路由
├── agents/                    # 智能体模块
├── core/                      # 核心模块
│   ├── config.py              # 配置管理
│   ├── state_manager.py       # 状态管理
│   └── interrupt_event.py     # HITL 中断
├── database/                  # 数据库层
├── models/                    # 数据模型
├── frontend/                  # React 前端
│   ├── src/
│   │   ├── components/        # 组件
│   │   ├── hooks/             # 自定义 Hooks
│   │   └── types/             # TypeScript 类型
│   ├── e2e/                   # E2E 测试
│   └── playwright.config.ts   # Playwright 配置
└── tests/                     # 后端测试
```

---

## 📚 更多文档

| 文档 | 描述 |
|------|------|
| 📘 [API_DOCUMENTATION.md](API_DOCUMENTATION.md) | 详细的 API 接口定义 |
| 📗 [frontend/README.md](frontend/README.md) | 前端开发指南 |
| 📙 [.vscode/launch.json](.vscode/launch.json) | VS Code 调试配置 |

---

## 🗺 开发路线图

| 阶段 | 状态 | 描述 |
|------|------|------|
| 🏗️ **阶段一** | ✅ 已完成 | FastAPI 脚手架、架构搭建、数据库初始化 |
| 🤖 **阶段二** | ✅ 已完成 | 构思、研究等多角色智能体核心与 Map-Reduce 架构定义 |
| 👥 **阶段三** | ✅ 已完成 | HITL 人工干预设计、Saga 状态容错执行与回滚 |
| 🐳 **阶段四** | ✅ 已完成 | Docker 安全沙箱代码执行引擎、VLM 图表审查 |
| 🧪 **阶段五** | ✅ 已完成 | E2E 测试环境、一键启动脚本 |
| 📝 **阶段六** | 🚧 进行中 | 论文撰写及评审流程进一步闭环优化 |

---

## 🤝 贡献与支持

我们欢迎任何形式的贡献！

1. 🍴 **Fork** 项目代码仓
2. 🌿 **创建分支** - 建立您的 Feature 或 Bugfix 分支
3. 💾 **提交变更** - 提交相关的变更、测试及更新记录
4. 📤 **推送代码** - 推送到远程分支并发起 Pull Request

---

## 📄 许可证

本项目遵循 [MIT License](LICENSE) 协议。

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给我们一个 Star！**

Made with ❤️ by EpistemicFlow Team

</div>
