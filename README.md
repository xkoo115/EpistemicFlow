# EpistemicFlow - AI驱动的自动化科研平台

EpistemicFlow 是一个基于 FastAPI 和 Microsoft Agent Framework 的 AI 驱动的自动化科研平台，采用纯 Python 技术栈构建。

## 项目概述

EpistemicFlow 旨在通过多智能体协作自动化科研流程，包括文献检索、实验设计、数据分析、论文写作等环节。平台采用模块化设计，支持灵活的工作流编排和状态管理。

### 核心特性

- **多智能体协作**: 基于 Microsoft Agent Framework 的多智能体系统
- **意图捕获与双轨分类**: 自动识别用户意图（研究论文 vs 综述论文）
- **Map-Reduce 架构**: 高吞吐量并行文献分析
- **会话状态隔离**: 每个智能体拥有独立的会话状态
- **结构化输出**: 使用 Pydantic 强制模型返回符合预期的 JSON 格式

## 技术栈

- **后端框架**: FastAPI (异步)
- **数据库**: SQLAlchemy 2.0 (异步) + aiosqlite/asyncpg
- **配置管理**: Pydantic Settings
- **AI 引擎**: Microsoft Agent Framework
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
│   ├── __init__.py        # 模块导出
│   ├── base.py            # Agent 基础管理器
│   ├── schemas.py         # Pydantic 输出模型
│   ├── ideation.py        # 构思智能体 (阶段一)
│   └── research.py        # 研究智能体 (阶段二)
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
│   │   ├── test_config.py
│   │   ├── test_models.py
│   │   ├── test_repositories.py
│   │   └── test_agents.py  # 智能体测试
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
pytest tests/unit/test_agents.py -v

# 生成测试覆盖率报告
pytest --cov=core --cov=models --cov=database --cov=agents tests/
```

### 5. 启动开发服务器

```bash
# 使用 uvicorn 启动
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 核心功能

### 阶段一：意图捕获与双轨分类

`IdeationAgent` 负责理解用户的科研意图，并进行双轨分类：

- **研究论文轨道 (RESEARCH_PAPER)**: 用户希望提出新方法、新理论或进行实验研究
- **综述论文轨道 (SURVEY_PAPER)**: 用户希望系统梳理某一领域的研究现状

```python
from agents import IdeationAgent, create_ideation_agent
from core.config import settings

# 创建构思智能体
llm_config = settings.get_llm_config()
agent = create_ideation_agent(llm_config)

# 分析用户意图
result = await agent.analyze(
    "我想研究一种新的基于图神经网络的分子性质预测方法"
)

print(f"分类结果: {result.paper_type}")  # RESEARCH_PAPER
print(f"研究主题: {result.research_topic}")
print(f"关键词: {result.keywords}")
print(f"置信度: {result.confidence}")
```

### 阶段二：动态文献调研与规划编排 (Map-Reduce)

采用 Map-Reduce 架构实现高吞吐量并行文献分析：

- **Map 阶段**: `LeadResearcherAgent` 将文献集合分割为子集，动态实例化多个 `SubResearcherAgent` 并发处理
- **Reduce 阶段**: 聚合所有助理智能体的结果，生成领域现状综述

```python
from agents import (
    LeadResearcherAgent,
    PaperMetadata,
    PartitionConfig,
)
from core.config import settings

# 创建首席研究员智能体
llm_config = settings.get_llm_config()
agent = LeadResearcherAgent(
    name="lead_researcher",
    llm_config=llm_config,
    max_concurrent_subsets=5,  # 最大并发子集数
    partition_config=PartitionConfig(
        max_papers_per_subset=10,
        balance_by_tokens=True,
    ),
)

# 准备文献数据
papers = [
    PaperMetadata(
        title="论文标题",
        authors=["作者1", "作者2"],
        abstract="摘要内容",
        publication_year=2023,
    ),
    # ... 更多论文
]

# 执行文献调研
survey = await agent.conduct_research(
    papers=papers,
    research_topic="深度学习在图像分类中的应用",
)

print(f"综述标题: {survey.title}")
print(f"方法论综述: {survey.methodology_review}")
print(f"当前挑战: {survey.current_challenges}")
print(f"未来方向: {survey.future_directions}")
```

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

## 智能体架构

### 基础设施层

| 组件 | 描述 |
|------|------|
| `ModelClientFactory` | 模型客户端工厂，支持 OpenAI/Ollama/DeepSeek 等 |
| `SessionManager` | 会话管理器，确保多智能体会话状态隔离 |
| `ResearchContextProvider` | 科研上下文提供者，注入研究主题、文献列表等 |
| `AgentManager` | 智能体管理器，统一管理智能体生命周期 |

### 智能体层

| 智能体 | 职责 | 输出模型 |
|--------|------|----------|
| `IdeationAgent` | 意图捕获与双轨分类 | `IdeationOutput` |
| `SubResearcherAgent` | 并行处理文献子集 | `SubResearcherOutput` |
| `LeadResearcherAgent` | 协调 Map-Reduce，生成综述 | `DomainSurveyOutput` |

### 输出模型

所有输出模型使用 Pydantic 定义，确保类型安全：

```python
from agents.schemas import IdeationOutput, PaperType

# IdeationOutput 包含：
# - paper_type: PaperType (RESEARCH_PAPER / SURVEY_PAPER)
# - confidence: float (0.0 - 1.0)
# - reasoning: ClassificationReasoning (思维链推理)
# - research_topic: str
# - keywords: List[str]
```

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
- **Mock 机制**: 无需实际 API 调用即可测试智能体逻辑
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

## 开发路线图

### 已完成

- [x] 阶段一：FastAPI 脚手架、配置管理、数据库初始化
- [x] 阶段二：核心智能体角色与工作流定义
  - [x] Agent 基础层与客户端配置
  - [x] 意图捕获与双轨分类机制
  - [x] Map-Reduce 架构实现
  - [x] 异步单元测试

### 进行中

- [ ] 阶段三：文献检索与知识图谱构建
- [ ] 阶段四：实验设计与执行引擎

### 计划中

- [ ] 阶段五：论文写作与评审
- [ ] 阶段六：可视化与交互界面

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
