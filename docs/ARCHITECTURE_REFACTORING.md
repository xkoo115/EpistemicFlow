# EpistemicFlow 核心架构重构说明

## 重构概述

本次重构将 EpistemicFlow 的控制权从手动业务逻辑完全移交给 Microsoft agent_framework 的原生编排能力。

### 核心变更

| 变更点 | 原架构 | 新架构 |
|--------|--------|--------|
| 工具调用 | 手动调用文献检索函数 | 原生 `@tool` 装饰器，LLM 自主决定调用 |
| 动态编排 | 手动 `asyncio.gather` | 原生 `WorkflowBuilder` + `FanOut/FanIn` |
| 事件流 | 手动组装 SSE 日志 | 原生 `WorkflowEvent` 实时透传 |
| 评审委员会 | 未实现 | 原生 `GroupChatOrchestrator` 隔离子图 |
| 状态管理 | 自定义 StateManager | 原生 `CheckpointStorage` + Saga 适配器 |

---

## API 端点说明

### 新旧 API 对比

| 功能 | 旧 API | 新 API（原生架构） |
|------|--------|-------------------|
| 启动工作流 | `POST /api/v1/workflows/start` | `POST /api/v1/workflows/native/start` |
| SSE 事件流 | `GET /api/stream/workflow/{session_id}` | `GET /api/native/stream/workflow/{session_id}` |
| 恢复工作流 | 不支持 | `POST /api/v1/workflows/native/resume` |
| 检查点列表 | 不支持 | `GET /api/v1/workflows/native/{session_id}/checkpoints` |

### 使用新 API 的示例

```javascript
// 1. 启动工作流
const response = await fetch('/api/v1/workflows/native/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        research_idea: '研究深度学习在药物发现中的应用',
        paper_type: 'research_paper',
        target_journal: 'Nature',
    }),
});
const { session_id } = await response.json();

// 2. 监听事件流
const eventSource = new EventSource(`/api/native/stream/workflow/${session_id}`);

eventSource.addEventListener('agent_thought', (e) => {
    const data = JSON.parse(e.data);
    console.log('Agent思考:', data.thought);
});

eventSource.addEventListener('tool_call_start', (e) => {
    const data = JSON.parse(e.data);
    console.log('工具调用:', data.tool_name, data.arguments);
});

eventSource.addEventListener('output', (e) => {
    const data = JSON.parse(e.data);
    console.log('最终输出:', data.output);
});

// 3. 从检查点恢复
const resumeResponse = await fetch('/api/v1/workflows/native/resume', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        checkpoint_id: 'cp_xxx',
        human_feedback: { comment: '请修改第三章' },
    }),
});
```

---

## 测试覆盖

### 单元测试

- `tests/unit/test_native_workflow.py` - 原生工具注册测试
- `tests/unit/test_saga_integration.py` - Saga 状态管理测试

### 集成测试

- `tests/integration/test_epistemic_workflow.py` - 完整工作流测试

### 运行测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 运行特定测试文件
pytest tests/unit/test_native_workflow.py -v
```

---

## 模块结构

```
agents/
├── tools_native.py           # 原生工具注册（文献检索）
├── workflow_native.py        # 原生动态编排（Map-Reduce）
├── polishing_and_review.py   # 手稿润色 + 评审委员会
├── event_stream_native.py    # 原生事件流 → SSE 桥接
├── saga_integration.py       # Saga 状态机兼容性
└── epistemic_workflow.py     # 统一工作流入口
```

---

## 1. 原生工具调用 (Native Tool Calling)

### 文件：`agents/tools_native.py`

**核心变更**：使用 `@tool` 装饰器将文献检索封装为标准工具。

```python
from agent_framework import tool

@tool(approval_mode="never_require")
async def search_semantic_scholar(
    query: Annotated[str, "搜索查询字符串"],
    limit: Annotated[int, "返回结果数量"] = 20,
) -> str:
    """使用 Semantic Scholar API 搜索学术论文。"""
    # ... 实现省略
    return json.dumps(result)
```

**原生特性**：
- LLM 自主决定何时调用工具
- 工具结果作为原生 `ToolMessage` 返回
- 自动进入事件流，可被 SSE 桥接层捕获

**使用方式**：
```python
from agents.tools_native import get_literature_tools

agent = Agent(
    client=client,
    name="research_agent",
    tools=get_literature_tools(),  # 注册所有工具
)
```

---

## 2. 原生动态编排 (Native Dynamic Orchestration)

### 文件：`agents/workflow_native.py`

**核心变更**：使用 `WorkflowBuilder` 构建 Map-Reduce 拓扑。

```python
from agent_framework import WorkflowBuilder, Executor, handler

class SubsetAnalysisExecutor(Executor):
    @handler
    async def analyze(
        self,
        request: SubsetAnalysisRequest,
        ctx: WorkflowContext[SubResearcherOutput],
    ) -> None:
        # 处理逻辑
        await ctx.send_message(output)

# 构建工作流
builder = WorkflowBuilder(start_executor=search_executor)

# Map 阶段：Fan-Out
builder = builder.add_fan_out_edges(
    source=search_executor,
    targets=subset_executors,
)

# Reduce 阶段：Fan-In
builder = builder.add_fan_in_edges(
    sources=subset_executors,
    target=aggregator,
)

workflow = builder.build()
```

**原生特性**：
- `add_fan_out_edges`：消息广播到多个执行器
- `add_fan_in_edges`：消息聚合为列表
- 动态实例化：根据文献规模动态创建执行器

---

## 3. 手稿润色智能体 (Polishing Agent)

### 文件：`agents/polishing_and_review.py`

**核心能力**：
- 整合分散的研究结论
- 执行高阶反思推理（Reflection）
- 生成结构化的 LaTeX 源码

```python
class PolishingAgent:
    async def polish(
        self,
        research_results: Dict[str, Any],
        figures: List[Dict[str, Any]],
        tables: List[Dict[str, Any]],
    ) -> Manuscript:
        # 第一轮：生成初稿
        draft = await agent.run(prompt)
        
        # 第二轮：反思与改进
        reflection = await agent.run(reflection_prompt)
        
        # 第三轮：生成最终版本
        final = await agent.run(final_prompt)
        
        return final
```

---

## 4. 同行评审委员会 (Peer Review Board)

### 文件：`agents/polishing_and_review.py`

**核心架构**：固定编排的评审子图，完全隔离运行。

```
评审委员会拓扑：
┌─────────────────┐
│ NoveltyReviewer │ ──┐
└─────────────────┘   │
┌─────────────────────┼──┐
│ MethodologyReviewer │ ──┼──> EditorInChief
└─────────────────────┘   │
┌─────────────────┐       │
│ ImpactReviewer  │ ──────┘
└─────────────────┘
```

**四个固定角色**：
1. **NoveltyReviewer**：新颖性审稿人，硬性对比 SOTA
2. **MethodologyReviewer**：方法论审稿人，审查统计严谨性
3. **ImpactReviewer**：影响力审稿人
4. **EditorInChief**：主编/协调员，聚合意见并输出综合报告

```python
class PeerReviewBoardBuilder:
    def build(self) -> Workflow:
        novelty = NoveltyReviewer()
        methodology = MethodologyReviewer()
        impact = ImpactReviewer()
        editor = EditorInChief()
        
        builder = WorkflowBuilder(start_executor=novelty)
        
        # Fan-Out：并发评审
        builder = builder.add_fan_out_edges(
            source=novelty,
            targets=[methodology, impact],
        )
        
        # Fan-In：聚合结果
        builder = builder.add_fan_in_edges(
            sources=[novelty, methodology, impact],
            target=editor,
        )
        
        return builder.build()
```

---

## 5. 原生事件流监听 (Native Event Streaming)

### 文件：`agents/event_stream_native.py`

**核心变更**：直接监听 `WorkflowEvent` 并透传到 FastAPI SSE。

```python
class NativeEventToSSEConverter:
    def convert(self, event: WorkflowEvent) -> Optional[SSEEvent]:
        if event.type == "started":
            return SSEEvent(event_type=SSEEventType.WORKFLOW_START, ...)
        elif event.type == "executor_invoked":
            return SSEEvent(event_type=SSEEventType.AGENT_THOUGHT, ...)
        elif event.type == "data":
            return SSEEvent(event_type=SSEEventType.TOOL_CALL_START, ...)
        # ...
```

**事件类型映射**：

| WorkflowEvent | SSE Event | 说明 |
|---------------|-----------|------|
| `started` | `workflow_start` | 工作流启动 |
| `executor_invoked` | `agent_thought` | Agent 开始执行 |
| `data` | `tool_call_start/result` | 工具调用 |
| `output` | `workflow_complete` | 最终输出 |

**SSE 路由**：
```python
@router.get("/workflow/{session_id}")
async def stream_workflow_events(session_id: str):
    event_stream = await get_workflow_event_stream(session_id)
    generator = SSEStreamGenerator()
    
    return StreamingResponse(
        generator.generate(event_stream, session_id),
        media_type="text/event-stream",
    )
```

---

## 6. Saga 状态机兼容性 (Saga Compatibility)

### 文件：`agents/saga_integration.py`

**核心保证**：
1. 全局状态快照：通过 `WorkflowCheckpoint` 获取
2. HITL 断点挂起：通过 `request_info` 事件
3. 确定性回滚：通过 `checkpoint_id` 恢复
4. Fork 机制：从历史检查点创建新路径

```python
class SagaStateManager:
    async def create_checkpoint(
        self,
        workflow_name: str,
        state: State,
        messages: Dict[str, List[Any]],
    ) -> SagaCheckpoint:
        # 创建原生检查点
        checkpoint = WorkflowCheckpoint(...)
        checkpoint_id = await self._checkpoint_storage.save(checkpoint)
        return SagaCheckpoint.from_workflow_checkpoint(checkpoint)
    
    async def fork_from_checkpoint(
        self,
        checkpoint_id: str,
        new_session_id: str,
        human_feedback: Optional[Dict[str, Any]] = None,
    ) -> SagaCheckpoint:
        # Fork 并注入人类反馈
        source = await self.restore_checkpoint(checkpoint_id)
        new_state = source.state.copy()
        new_state["human_feedback"] = human_feedback
        # ...
```

**HITL 支持**：
```python
class HITLManager:
    async def create_interrupt(
        self,
        event: WorkflowEvent,
    ) -> HITLInterruptPoint:
        # 创建中断点，工作流挂起
        ...
    
    async def resume_with_response(
        self,
        request_id: str,
        response: Any,
    ) -> str:
        # 提供响应，恢复执行
        ...
```

---

## 7. 统一工作流入口 (Unified Entry Point)

### 文件：`agents/epistemic_workflow.py`

**完整工作流阶段**：

```
Stage 1: Ideation (构思)
    ↓
Stage 2: Literature Review (文献调研) - Map-Reduce
    ↓
Stage 3: Methodology Design (方法论设计)
    ↓
Stage 4: Polishing (手稿润色) - LaTeX 生成
    ↓
Stage 5: Peer Review (同行评审) - 评审委员会
    ↓
Completion (完成)
```

**使用示例**：
```python
from agents.epistemic_workflow import EpistemicWorkflow

workflow = EpistemicWorkflow()

# 流式执行
async for event in workflow.run_stream(input):
    print(event)

# 非流式执行
result = await workflow.run(input)

# 从检查点恢复
result = await workflow.run(input, checkpoint_id="xxx")

# Fork
new_checkpoint = await workflow.fork_from_checkpoint(
    checkpoint_id="xxx",
    new_session_id="new_session",
    human_feedback={"comment": "请修改第三章"},
)
```

---

## 原生框架特性总结

### 1. 工具注册
- `@tool` 装饰器
- `FunctionTool` 类
- LLM 自主调用

### 2. 编排拓扑
- `WorkflowBuilder` 声明式构建
- `add_edge` 单边连接
- `add_fan_out_edges` 扇出（广播）
- `add_fan_in_edges` 扇入（聚合）
- `add_switch_case_edge_group` 条件路由

### 3. 执行器
- `Executor` 基类
- `@handler` 装饰器
- `WorkflowContext` 上下文

### 4. 事件流
- `WorkflowEvent` 统一事件
- `workflow.run(stream=True)` 流式执行
- 实时透传到 SSE

### 5. 状态管理
- `State` 跨执行器共享状态
- `WorkflowCheckpoint` 完整检查点
- `FileCheckpointStorage` 持久化

### 6. HITL
- `request_info` 事件
- `IDLE_WITH_PENDING_REQUESTS` 状态
- `checkpoint_id` 恢复

---

## 迁移指南

### 从旧架构迁移

1. **工具调用**：
   - 旧：手动调用 `search_semantic_scholar(query)`
   - 新：注册工具，让 LLM 自主调用

2. **编排**：
   - 旧：`asyncio.gather(*tasks)`
   - 新：`WorkflowBuilder().add_fan_out_edges()`

3. **事件流**：
   - 旧：手动组装 SSE 日志
   - 新：监听 `WorkflowEvent` 并透传

4. **状态管理**：
   - 旧：自定义 `StateManager`
   - 新：使用 `CheckpointStorage` + Saga 适配器

---

## 性能优化

1. **并发控制**：使用 `asyncio.Semaphore` 限制最大并发数
2. **背压控制**：事件队列支持背压，防止内存溢出
3. **检查点压缩**：可选的检查点压缩策略
4. **连接复用**：httpx 异步客户端连接池

---

## 可观测性

所有事件自动进入 OpenTelemetry 遥测系统：
- Agent 调用追踪
- 工具调用追踪
- 工作流执行追踪
- 状态变更追踪

---

## 测试覆盖

- 单元测试：`tests/unit/test_native_workflow.py`
- 集成测试：`tests/integration/test_epistemic_workflow.py`
- E2E 测试：`tests/e2e/test_full_workflow.py`

---

## 总结

本次重构实现了以下目标：

1. ✅ **原生工具调用**：LLM 自主决定何时调用文献检索工具
2. ✅ **原生动态编排**：Map-Reduce 使用 WorkflowBuilder 实现
3. ✅ **手稿润色智能体**：高阶推理 + LaTeX 生成
4. ✅ **评审委员会**：固定编排的隔离评审子图
5. ✅ **原生事件流**：实时透传到 FastAPI SSE
6. ✅ **Saga 兼容性**：HITL + 确定性回滚 + Fork

所有代码高内聚、低耦合，添加了详尽的中文注释，解释原生框架特性如何替代原有手动逻辑。
