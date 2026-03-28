# EpistemicFlow - AI驱动的自动化科研平台

EpistemicFlow 是一个基于 FastAPI 和 Microsoft AutoGen 的 AI 驱动的自动化科研平台，采用纯 Python 技术栈构建。

## 项目概述

EpistemicFlow 旨在通过多智能体协作自动化科研流程，包括文献检索、实验设计、数据分析、论文写作等环节。平台采用模块化设计，支持灵活的工作流编排和状态管理。

## 技术栈

- **后端框架**: FastAPI (异步)
- **数据库**: SQLAlchemy (异步) + aiosqlite/asyncpg
- **配置管理**: Pydantic Settings
- **AI 引擎**: Microsoft AutoGen (准备集成)
- **测试框架**: pytest + pytest-asyncio
- **代码质量**: black, mypy, ruff

## 项目结构

```
EpistemicFlow/
├── api/                    # API 接口层
│   ├── v1/                # API v1 版本
│   └── v2/                # API v2 版本
├── core/                  # 核心模块
│   └── config.py          # 全局配置管理
├── agents/                # 智能体模块
├── models/                # 数据模型
│   ├── base.py           # 基础模型
│   └── workflow_state.py # 工作流状态模型
├── schemas/               # Pydantic 模式
├── database/              # 数据库层
│   ├── session.py        # 数据库会话管理
│   └── repositories/     # 数据仓库
├── services/              # 业务服务层
├── utils/                 # 工具函数
├── tests/                 # 测试文件
│   ├── unit/             # 单元测试
│   └── integration/      # 集成测试
├── alembic/              # 数据库迁移
├── pyproject.toml        # 项目配置
├── requirements.txt      # 依赖文件
└── README.md             # 项目说明
```

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd EpistemicFlow

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# 应用配置
APP_ENVIRONMENT=development
APP_DEBUG=true
APP_HOST=0.0.0.0
APP_PORT=8000

# 数据库配置
DB_URL=sqlite+aiosqlite:///./epistemicflow.db
DB_ECHO=false

# 大模型配置
LLM_GPT4__PROVIDER=openai
LLM_GPT4__API_KEY=your-openai-api-key
LLM_GPT4__MODEL_NAME=gpt-4
LLM_GPT4__TEMPERATURE=0.7

LLM_OLLAMA__PROVIDER=ollama
LLM_OLLAMA__MODEL_NAME=llama2
LLM_OLLAMA__BASE_URL=http://localhost:11434

# 默认模型
DEFAULT_LLM=gpt4
```

### 3. 初始化数据库

```bash
# 运行初始化脚本
python -c "from database.session import init_database; import asyncio; asyncio.run(init_database())"
```

### 4. 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/unit/test_config.py
pytest tests/unit/test_models.py

# 生成测试覆盖率报告
pytest --cov=core --cov=models --cov=database tests/
```

### 5. 启动开发服务器

```bash
# 使用 uvicorn 启动
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 核心功能

### 配置管理

基于 `pydantic-settings` 的配置管理系统，支持：
- 多环境配置（开发/测试/生产）
- 模型不可知性（支持多种大模型提供商）
- 环境变量和配置文件混合加载
- 类型安全的配置验证

### 数据库持久化

采用异步 SQLAlchemy 实现：
- 异步数据库操作
- 工作流状态管理（Saga 模式基石）
- 数据仓库模式封装
- 连接池管理

### 工作流状态管理

`WorkflowState` 模型支持：
- 多阶段状态跟踪（构思、文献检索、分析等）
- 智能体状态持久化
- 人工反馈集成
- 错误处理和恢复

## 开发指南

### 代码规范

```bash
# 代码格式化
black .

# 类型检查
mypy .

# 代码质量检查
ruff check .
```

### 数据库迁移

```bash
# 初始化 Alembic
alembic init alembic

# 创建迁移
alembic revision --autogenerate -m "描述"

# 应用迁移
alembic upgrade head
```

### 测试策略

- **单元测试**: 测试独立模块功能
- **集成测试**: 测试模块间交互
- **异步测试**: 使用 `pytest-asyncio`
- **测试覆盖率**: 使用 `pytest-cov`

## API 文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 部署

### Docker 部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 生产环境配置

1. 使用 PostgreSQL 或 MySQL 替代 SQLite
2. 配置反向代理（Nginx）
3. 设置 HTTPS
4. 配置监控和日志
5. 使用环境变量管理敏感信息

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

MIT License

## 联系方式

- 项目主页: [GitHub Repository]
- 问题反馈: [GitHub Issues]
- 文档: [项目 Wiki]