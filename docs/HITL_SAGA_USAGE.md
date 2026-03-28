# HITL 检查点与 Saga 回滚机制使用指南

本文档介绍如何使用 EpistemicFlow 的 HITL（Human-in-the-Loop）检查点与 Saga 回滚机制。

## 核心概念

### 1. StateManager（状态管理器）

StateManager 负责 Agent Session 状态的序列化、持久化和恢复。

**核心功能：**
- 创建检查点（Checkpoint）
- 从检查点恢复状态
- 状态分叉（Forking）
- 状态完整性验证

**使用示例：**

```python
from core.state_manager import StateManager
from agent_framework import AgentSession
from models.workflow_state import WorkflowStage

# 创建 StateManager
state_manager = StateManager(db_session)

# 创建 Agent Session
session = AgentSession(session_id="research-001")
session.state["research_topic"] = "深度学习在医学影像中的应用"
session.state["messages"] = [...]

# 创建检查点
checkpoint = await state_manager.create_checkpoint(
    session_id="research-001",
    workflow_name="research_workflow",
    current_stage=WorkflowStage.CONCEPTION,
    agent_session=session,
    metadata={"description": "科研计划生成完毕"},
)

# 从检查点恢复
restored_session = await state_manager.restore_from_checkpoint(checkpoint.id)

# 验证恢复的状态
assert restored_session.state["research_topic"] == "深度学习在医学影像中的应用"
```

### 2. InterruptEvent（中断事件）

InterruptEvent 用于触发 HITL 中断，让工作流在关键节点挂起并等待人工审核。

**使用示例：**

```python
from core.interrupt_event import (
    InterruptEvent,
    InterruptReason,
    InterruptPriority,
    raise_interrupt,
)

# 方式 1: 直接抛出中断事件
def generate_research_plan(session):
    # ... 生成科研计划 ...
    plan = {...}

    # 触发中断，等待人工审核
    raise InterruptEvent(
        reason=InterruptReason.RESEARCH_PLAN_REVIEW,
        message="科研计划已生成，请审核并确认",
        session_id=session.session_id,
        priority=InterruptPriority.HIGH,
        context={"research_plan": plan},
        suggested_actions=[
            "批准计划并继续执行",
            "修改计划目标",
            "调整方法论",
        ],
    )

# 方式 2: 使用便捷函数
def select_literature(session, papers):
    # ... 文献检索 ...

    raise_interrupt(
        reason=InterruptReason.LITERATURE_SELECTION,
        message="文献检索完成，请选择相关文献",
        session_id=session.session_id,
        context={"papers": papers},
        suggested_actions=["选择所有文献", "手动选择"],
    )
```

### 3. FastAPI 路由接口

#### 3.1 触发中断

```python
POST /api/v1/workflow/{state_id}/interrupt

请求体：
{
    "reason": "research_plan_review",
    "message": "科研计划已生成，请审核",
    "priority": "high",
    "context": {
        "research_plan": {...}
    },
    "suggested_actions": ["批准", "修改"]
}

响应：
{
    "reason": "research_plan_review",
    "message": "科研计划已生成，请审核",
    "session_id": "research-001",
    "checkpoint_id": 123,
    "priority": "high",
    "context": {...},
    "suggested_actions": [...],
    "created_at": "2024-01-01T10:00:00"
}
```

#### 3.2 恢复执行

```python
POST /api/v1/workflow/session/{session_id}/resume

请求体：
{
    "feedback": "批准计划，继续执行",
    "action": "批准计划",
    "additional_data": {
        "approved": true
    }
}

响应：
{
    "checkpoint_id": 123,
    "session_id": "research-001",
    "status": "running",
    "message": "工作流已恢复，正在继续执行"
}
```

#### 3.3 回滚到历史检查点

```python
POST /api/v1/workflow/session/{session_id}/rollback

请求体：
{
    "checkpoint_id": 100,
    "reason": "用户要求修改研究主题",
    "human_instruction": "增加针对 Transformer 模型的对比实验",
    "additional_state": {
        "new_experiment": "Transformer comparison"
    }
}

响应：
{
    "original_checkpoint_id": 100,
    "new_checkpoint_id": 200,
    "new_session_id": "research-002",
    "workflow_name": "research_workflow",
    "current_stage": "conception",
    "message": "已从检查点 100 回滚并创建新的执行路径"
}
```

#### 3.4 查询检查点历史

```python
GET /api/v1/workflow/session/{session_id}/history?limit=50

响应：
{
    "session_id": "research-001",
    "checkpoints": [
        {
            "id": 150,
            "session_id": "research-001",
            "workflow_name": "research_workflow",
            "current_stage": "analysis",
            "status": "paused",
            "created_at": "2024-01-01T12:00:00",
            ...
        },
        ...
    ],
    "total_count": 10
}
```

#### 3.5 验证状态完整性

```python
GET /api/v1/workflow/{state_id}/validate

响应：
{
    "checkpoint_id": 123,
    "is_valid": true,
    "state_hash": "a1b2c3d4...",
    "message": "状态验证通过"
}
```

## 完整工作流示例

### 场景：科研计划生成与审核

```python
from agent_framework import AgentSession, Message, Content
from core.state_manager import StateManager
from core.interrupt_event import InterruptEvent, InterruptReason
from models.workflow_state import WorkflowStage

async def research_workflow():
    """完整的科研工作流示例"""

    # 1. 初始化
    session = AgentSession(session_id="research-001")
    session.state["research_topic"] = "深度学习在医学影像中的应用"

    # 创建初始检查点
    checkpoint1 = await state_manager.create_checkpoint(
        session_id="research-001",
        workflow_name="research_workflow",
        current_stage=WorkflowStage.INITIALIZATION,
        agent_session=session,
    )

    # 2. 生成科研计划
    plan = await generate_research_plan(session)
    session.state["research_plan"] = plan

    # 创建检查点
    checkpoint2 = await state_manager.create_checkpoint(
        session_id="research-001",
        workflow_name="research_workflow",
        current_stage=WorkflowStage.CONCEPTION,
        agent_session=session,
    )

    # 3. 触发 HITL 中断（等待人工审核）
    try:
        raise InterruptEvent(
            reason=InterruptReason.RESEARCH_PLAN_REVIEW,
            message="科研计划已生成，请审核",
            session_id=session.session_id,
            context={"research_plan": plan},
        )
    except InterruptEvent as e:
        # FastAPI 捕获中断，保存状态并返回给前端
        # 前端显示审核界面，等待用户反馈
        pass

    # 4. 用户提交反馈后恢复执行
    # （这部分由 FastAPI 路由处理）
    # POST /api/v1/workflow/session/research-001/resume
    # {"feedback": "批准计划"}

    # 5. 继续执行文献检索
    papers = await search_literature(session)
    session.state["collected_papers"] = papers

    # 6. 如果遇到错误，可以回滚
    # POST /api/v1/workflow/session/research-001/rollback
    # {"checkpoint_id": checkpoint1.id, "reason": "需要调整研究方向"}
```

## Saga 回滚模式

### 场景：错误恢复与决策分叉

```python
async def saga_rollback_example():
    """Saga 回滚示例"""

    # 假设工作流执行到某个阶段遇到错误
    session.state["error"] = "数据收集失败"

    # 创建错误检查点
    error_checkpoint = await state_manager.create_checkpoint(
        session_id="research-001",
        workflow_name="research_workflow",
        current_stage=WorkflowStage.ERROR,
        agent_session=session,
    )

    # 用户决定回滚到科研计划阶段并调整策略
    # POST /api/v1/workflow/session/research-001/rollback
    rollback_request = {
        "checkpoint_id": plan_checkpoint.id,
        "reason": "数据收集失败，需要调整计划",
        "human_instruction": "使用公开数据集代替自收集数据",
    }

    # 系统从历史检查点恢复状态并注入新指令
    new_session = await state_manager.fork_from_checkpoint(
        checkpoint_id=plan_checkpoint.id,
        new_session_id="research-002",  # 新的会话 ID
        workflow_name="research_workflow",
        new_stage=WorkflowStage.CONCEPTION,
        human_feedback="使用公开数据集代替自收集数据",
    )

    # 新会话从调整后的状态继续执行
    # 原错误状态不影响新路径
    assert "error" not in new_session.state
```

## 最佳实践

### 1. 检查点创建时机

在以下关键节点创建检查点：
- 工作流启动时
- 每个阶段完成时
- 执行耗时操作前
- 需要人工审核时

### 2. 中断事件设计

- 提供清晰的描述信息（message）
- 包含足够的上下文（context）供人工决策
- 提供建议操作（suggested_actions）
- 设置合适的优先级（priority）

### 3. 状态管理

- 避免在状态中存储大文件（使用文件存储，状态中只保存路径）
- 定期清理旧的检查点（使用 cleanup 接口）
- 验证状态完整性（使用 validate 接口）

### 4. 错误处理

- 捕获 StateSerializationError 和 StateDeserializationError
- 记录详细的错误日志
- 提供回滚选项给用户

## 性能优化

### 1. 状态大小控制

```python
# 不推荐：在状态中存储大文件
session.state["large_data"] = large_dataset  # ❌

# 推荐：只存储引用
session.state["large_data_path"] = "/data/large_dataset.pkl"  # ✅
```

### 2. 检查点清理

```python
# 定期清理 30 天前的已完成检查点
POST /api/v1/workflow/cleanup/old
{
    "days": 30,
    "statuses": ["completed", "cancelled"]
}
```

### 3. 批量操作

使用批量接口减少数据库查询次数：
- `get_session_history()` 批量获取检查点
- `get_statistics()` 批量获取统计信息

## 故障排查

### 1. 状态哈希不匹配

**问题：** 验证状态时提示"状态哈希不匹配"

**原因：** 数据在存储过程中被损坏

**解决：**
- 检查数据库连接
- 验证 JSON 序列化配置
- 考虑从更早的检查点恢复

### 2. 反序列化失败

**问题：** 从检查点恢复时抛出 StateDeserializationError

**原因：**
- 状态格式版本不兼容
- 自定义类型未注册

**解决：**
```python
from agent_framework import register_state_type

# 注册自定义类型
register_state_type(MyCustomModel)
```

### 3. 并发冲突

**问题：** 多个并发请求导致状态混乱

**解决：**
- 使用数据库事务
- 实现乐观锁（基于 updated_at 时间戳）
- 避免同时更新同一个会话

## 总结

HITL 检查点与 Saga 回滚机制为 EpistemicFlow 提供了强大的状态管理和错误恢复能力：

1. **确定性恢复：** 从任何历史检查点精确恢复状态
2. **人工介入：** 在关键节点挂起并等待人工审核
3. **错误恢复：** 回滚到历史状态并尝试新策略
4. **决策分叉：** 从同一历史节点探索不同决策路径
5. **完整性保证：** 状态哈希验证确保数据未损坏

通过合理使用这些机制，可以构建健壮、可恢复的多智能体工作流系统。
