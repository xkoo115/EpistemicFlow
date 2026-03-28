# EpistemicFlow 阶段四至阶段六快速入门指南

## 快速开始

### 1. 安装依赖

```bash
# 安装所有依赖
pip install -r requirements.txt

# 或使用 pipenv
pipenv install
```

### 2. 配置环境变量

创建 `.env` 文件：

```bash
# 应用配置
APP_ENVIRONMENT=development
APP_DEBUG=true
APP_HOST=0.0.0.0
APP_PORT=8000

# 数据库配置
DB_URL=sqlite+aiosqlite:///./epistemicflow.db

# LLM 配置
LLM_GPT4__PROVIDER=openai
LLM_GPT4__API_KEY=your-api-key
LLM_GPT4__MODEL_NAME=gpt-4
LLM_GPT4__TEMPERATURE=0.7

# Docker 配置（沙箱执行）
DOCKER_HOST=unix:///var/run/docker.sock
```

### 3. 启动服务

```bash
# 启动 FastAPI 服务
python main.py

# 或使用 uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 访问 API 文档

打开浏览器访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 使用示例

### 示例 1：沙箱执行

```python
import asyncio
from core.sandbox import DockerSandbox, SandboxConfig

async def run_experiment():
    # 创建沙箱
    sandbox = DockerSandbox(
        config=SandboxConfig(
            timeout=60,
            enable_debugging=True,
        )
    )

    # 执行实验代码
    code = """
import numpy as np
import matplotlib.pyplot as plt

# 生成数据
x = np.linspace(0, 10, 100)
y = np.sin(x)

# 绘图
plt.figure(figsize=(10, 6))
plt.plot(x, y, label='sin(x)')
plt.xlabel('x')
plt.ylabel('y')
plt.title('Sine Wave')
plt.legend()
plt.savefig('result.png')
plt.close()

print("实验完成！")
"""

    result = await sandbox.execute(code)

    print(f"状态: {result.status}")
    print(f"输出: {result.stdout}")
    print(f"执行时间: {result.execution_time_ms:.2f}ms")

asyncio.run(run_experiment())
```

### 示例 2：VLM 图表审查

```python
import asyncio
from agents.vlm_review import VLMFigureReviewer
from core.config import settings

async def review_figure():
    # 创建审查器
    reviewer = VLMFigureReviewer(
        settings.get_llm_config(),
        target_journal="Nature",
    )

    # 审查图表
    result = await reviewer.review_figure(
        "results/figure1.png",
        figure_id="fig1",
        context="实验结果对比图",
    )

    print(f"综合评分: {result.overall_score:.1f}/10")
    print(f"审查结论: {result.verdict.value}")
    print(f"优点: {result.strengths}")
    print(f"缺点: {result.weaknesses}")
    print(f"改进建议: {result.improvement_suggestions}")

asyncio.run(review_figure())
```

### 示例 3：同行评审

```python
import asyncio
from agents.reviewers import PeerReviewCommittee
from agents.vlm_review import PolishedManuscript
from core.config import settings

async def conduct_review():
    # 准备手稿
    manuscript = PolishedManuscript(
        title="深度学习在图像分类中的应用",
        abstract="本文综述了深度学习技术的最新进展...",
        sections=[...],
        conclusion="深度学习展现出巨大潜力...",
    )

    # 创建评审委员会
    committee = PeerReviewCommittee(settings.get_llm_config())

    # 执行评审
    report = await committee.conduct_review(manuscript)

    print(f"新颖性评分: {report.novelty_review.overall_score:.1f}")
    print(f"方法论评分: {report.methodology_review.overall_score:.1f}")
    print(f"影响力评分: {report.impact_review.overall_score:.1f}")
    print(f"平均评分: {report.average_score:.1f}")
    print(f"最终决策: {report.editor_decision.value}")

    await committee.close()

asyncio.run(conduct_review())
```

### 示例 4：SSE 流式监控

**后端**：

```python
from api.stream import event_bus, EventType, SSEEvent

# 发布智能体思考事件
await event_bus.publish(SSEEvent(
    event_type=EventType.AGENT_THOUGHT,
    session_id="session123",
    agent_name="novelty_reviewer",
    data={"thought": "正在分析论文新颖性..."},
))

# 发布工作流状态变更
await event_bus.publish(SSEEvent(
    event_type=EventType.WORKFLOW_STAGE_CHANGE,
    session_id="session123",
    data={
        "from_stage": "conception",
        "to_stage": "literature_review",
    },
))
```

**前端**：

```javascript
// 订阅事件流
const eventSource = new EventSource('/api/stream/events/session123');

// 监听所有事件
eventSource.onmessage = (e) => {
    const data = JSON.parse(e.data);
    console.log(`[${data.timestamp}] ${e.type}:`, data);
};

// 监听特定事件
eventSource.addEventListener('agent_thought', (e) => {
    const data = JSON.parse(e.data);
    appendToLog(`[${data.agent_name}] ${data.data.thought}`);
});

eventSource.addEventListener('workflow_stage_change', (e) => {
    const data = JSON.parse(e.data);
    updateWorkflowUI(data.data.from_stage, data.data.to_stage);
});
```

---

## 完整工作流示例

```python
import asyncio
from core.sandbox import DockerSandbox, SandboxConfig
from agents.vlm_review import VLMFigureReviewer, IntegrationPolishingAgent
from agents.reviewers import PeerReviewCommittee
from agents.schemas import DomainSurveyOutput
from core.config import settings

async def complete_workflow():
    """完整的科研工作流"""

    # 1. 沙箱执行实验
    print("=== 阶段 1: 沙箱执行 ===")
    sandbox = DockerSandbox(config=SandboxConfig(timeout=300))
    execution_result = await sandbox.execute(
        code=open("experiment.py").read()
    )
    print(f"执行状态: {execution_result.status}")

    # 2. VLM 审查图表
    print("\n=== 阶段 2: 图表审查 ===")
    reviewer = VLMFigureReviewer(settings.get_llm_config())
    figure_reviews = await reviewer.batch_review([
        "results/fig1.png",
        "results/fig2.png",
    ])
    for review in figure_reviews:
        print(f"{review.figure_id}: {review.overall_score:.1f}/10")

    # 3. 润色整合
    print("\n=== 阶段 3: 润色整合 ===")
    polishing_agent = IntegrationPolishingAgent(settings.get_llm_config())
    manuscript = await polishing_agent.polish_manuscript(
        domain_survey,  # 假设已有
        figure_reviews=figure_reviews,
    )
    print(f"手稿字数: {manuscript.total_word_count}")
    print(f"连贯性: {manuscript.coherence_score:.2f}")

    # 4. 同行评审
    print("\n=== 阶段 4: 同行评审 ===")
    committee = PeerReviewCommittee(settings.get_llm_config())
    review_report = await committee.conduct_review(
        manuscript,
        figure_reviews=figure_reviews,
    )
    print(f"平均评分: {review_report.average_score:.1f}")
    print(f"最终决策: {review_report.editor_decision.value}")

    await committee.close()

    # 5. 导出最终手稿
    print("\n=== 阶段 5: 导出手稿 ===")
    await polishing_agent.export_to_markdown(
        manuscript,
        "final_manuscript.md",
    )
    print("手稿已导出到 final_manuscript.md")

asyncio.run(complete_workflow())
```

---

## 测试

### 运行所有测试

```bash
# 运行单元测试
pytest tests/unit -v

# 运行集成测试
pytest tests/integration -v

# 运行端到端测试
pytest tests/test_e2e_workflow.py -v

# 运行所有测试并生成覆盖率报告
pytest tests/ -v --cov=. --cov-report=html
```

### 运行特定测试

```bash
# 测试沙箱执行
pytest tests/test_e2e_workflow.py::TestDockerSandbox -v

# 测试同行评审
pytest tests/test_e2e_workflow.py::TestPeerReviewCommittee -v

# 测试 SSE 事件总线
pytest tests/test_e2e_workflow.py::TestEventBus -v
```

---

## 常见问题

### Q1: Docker 连接失败

**问题**: `DockerException: 无法连接到 Docker 守护进程`

**解决方案**:
1. 确保 Docker 已安装并运行
2. 检查 Docker 守护进程权限
3. 配置 `DOCKER_HOST` 环境变量

```bash
# Linux
sudo systemctl start docker
sudo usermod -aG docker $USER

# macOS
open -a Docker

# Windows
# 启动 Docker Desktop
```

### Q2: LLM API 调用失败

**问题**: `APIConnectionError: 连接超时`

**解决方案**:
1. 检查 API Key 是否正确
2. 检查网络连接
3. 配置代理（如需要）

```bash
# 配置代理
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=http://proxy:port
```

### Q3: SSE 连接断开

**问题**: 前端 EventSource 连接频繁断开

**解决方案**:
1. 检查 Nginx 配置（禁用缓冲）
2. 增加超时时间
3. 实现自动重连

```nginx
# Nginx 配置
location /api/stream/ {
    proxy_pass http://backend;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 86400s;
}
```

```javascript
// 前端自动重连
let eventSource;

function connectSSE() {
    eventSource = new EventSource('/api/stream/events/session123');

    eventSource.onerror = (e) => {
        eventSource.close();
        setTimeout(connectSSE, 5000);  // 5秒后重连
    };
}

connectSSE();
```

---

## 性能优化建议

### 1. 沙箱预热

```python
# 预拉取 Docker 镜像
sandbox = DockerSandbox()
await sandbox.pull_image("python:3.11-slim")
```

### 2. 并行执行

```python
# 并行执行多个实验
results = await asyncio.gather(*[
    sandbox.execute(code)
    for code in experiment_codes
])
```

### 3. 事件批处理

```python
# 批量发布事件
events = [SSEEvent(...) for _ in range(100)]
await asyncio.gather(*[
    event_bus.publish(event)
    for event in events
])
```

---

## 下一步

- 阅读详细文档: `docs/PHASE4_DELIVERY.md`
- 查看 API 文档: http://localhost:8000/docs
- 运行示例代码: `examples/`
- 参与开发: `CONTRIBUTING.md`

---

**祝您使用愉快！**
