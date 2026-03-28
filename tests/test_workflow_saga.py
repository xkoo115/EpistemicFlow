"""
Saga 事务流集成测试

测试完整的 HITL 工作流程，包括：
- 触发执行 -> HITL 挂起 -> 提交反馈并恢复
- 回滚到历史检查点并分叉
- 状态完整性验证

注意：本测试专注于 StateManager 的核心功能测试
"""

import pytest
import pytest_asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from models.workflow_state import Base, WorkflowStage, WorkflowStatus
from core.state_manager import StateManager
from core.interrupt_event import InterruptEvent, InterruptReason, InterruptPriority
from agent_framework import AgentSession, Message, Content


# ============================================================================
# 测试固件
# ============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    创建测试数据库会话

    使用内存 SQLite 数据库进行测试，确保表已创建
    """
    # 导入 Base（确保表定义已加载）
    from models.workflow_state import Base as WorkflowStateBase
    import tempfile
    import os
    
    # 创建临时文件数据库（确保所有连接使用同一个数据库）
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    try:
        # 创建数据库引擎
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_path}",
            echo=False,
            future=True,
            poolclass=NullPool,
        )

        # 创建所有表
        async with engine.begin() as conn:
            await conn.run_sync(WorkflowStateBase.metadata.create_all)

        # 创建会话工厂
        async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        # 创建会话
        async with async_session_factory() as session:
            yield session

        # 清理
        await engine.dispose()
    finally:
        # 删除临时文件
        if os.path.exists(db_path):
            os.unlink(db_path)


# ============================================================================
# 核心功能测试
# ============================================================================


@pytest.mark.asyncio
async def test_checkpoint_creation_and_restore(
    test_db_session: AsyncSession,
):
    """
    测试检查点创建与恢复

    流程：
    1. 创建 Agent Session
    2. 创建检查点
    3. 从检查点恢复
    4. 验证状态一致性
    """
    state_manager = StateManager(test_db_session)

    # 1. 创建 Agent Session
    session = AgentSession(session_id="test-checkpoint-001")
    session.state["research_topic"] = "深度学习在医学影像中的应用"
    session.state["iteration_count"] = 1
    session.state["messages"] = [
        Message(role="user", contents=[Content.from_text("开始研究")])
    ]

    # 2. 创建检查点
    checkpoint = await state_manager.create_checkpoint(
        session_id="test-checkpoint-001",
        workflow_name="research_workflow",
        current_stage=WorkflowStage.CONCEPTION,
        agent_session=session,
    )

    assert checkpoint.id is not None
    assert checkpoint.session_id == "test-checkpoint-001"
    assert checkpoint.current_stage == WorkflowStage.CONCEPTION

    # 3. 从检查点恢复
    restored_session = await state_manager.restore_from_checkpoint(checkpoint.id)

    # 4. 验证状态一致性
    assert restored_session.session_id == session.session_id
    assert restored_session.state["research_topic"] == session.state["research_topic"]
    assert restored_session.state["iteration_count"] == session.state["iteration_count"]
    assert len(restored_session.state["messages"]) == len(session.state["messages"])


@pytest.mark.asyncio
async def test_saga_rollback_and_fork(
    test_db_session: AsyncSession,
):
    """
    测试 Saga 回滚与分叉

    流程：
    1. 创建多个检查点
    2. 回滚到历史检查点
    3. 注入新指令并分叉
    4. 验证新路径独立性
    """
    state_manager = StateManager(test_db_session)

    # 1. 创建初始检查点
    session1 = AgentSession(session_id="test-rollback-001")
    session1.state["research_topic"] = "原始研究主题"
    session1.state["iteration_count"] = 1

    checkpoint1 = await state_manager.create_checkpoint(
        session_id="test-rollback-001",
        workflow_name="research_workflow",
        current_stage=WorkflowStage.CONCEPTION,
        agent_session=session1,
    )

    # 2. 创建第二个检查点（模拟工作流继续执行）
    session2 = AgentSession(session_id="test-rollback-001")
    session2.state["research_topic"] = "修改后的研究主题"
    session2.state["iteration_count"] = 2
    session2.state["methodology"] = "CNN-based approach"

    checkpoint2 = await state_manager.create_checkpoint(
        session_id="test-rollback-001",
        workflow_name="research_workflow",
        current_stage=WorkflowStage.METHODOLOGY_DESIGN,
        agent_session=session2,
    )

    # 3. 回滚到第一个检查点并分叉
    new_checkpoint = await state_manager.fork_from_checkpoint(
        checkpoint_id=checkpoint1.id,
        new_session_id="test-rollback-002",
        workflow_name="research_workflow",
        new_stage=WorkflowStage.CONCEPTION,
        human_feedback="增加针对 Transformer 模型的对比实验",
        additional_state={"new_experiment": "Transformer comparison"},
    )

    # 4. 验证新路径独立性
    assert new_checkpoint.session_id == "test-rollback-002"
    assert new_checkpoint.id != checkpoint1.id
    assert new_checkpoint.id != checkpoint2.id

    # 恢复新检查点并验证状态
    restored = await state_manager.restore_from_checkpoint(new_checkpoint.id)
    assert restored.state["research_topic"] == "原始研究主题"
    assert restored.state["iteration_count"] == 1
    assert "human_feedback" in restored.state
    assert "Transformer" in restored.state["human_feedback"]
    assert restored.state["new_experiment"] == "Transformer comparison"


@pytest.mark.asyncio
async def test_interrupt_event_handling(
    test_db_session: AsyncSession,
):
    """
    测试中断事件处理

    流程：
    1. 创建 Agent Session 和检查点
    2. 创建中断事件
    3. 验证中断事件序列化
    """
    state_manager = StateManager(test_db_session)

    # 1. 创建 Agent Session 和检查点
    session = AgentSession(session_id="test-interrupt-001")
    session.state["research_plan"] = {
        "title": "医学影像研究",
        "objectives": ["提高准确率"],
    }

    checkpoint = await state_manager.create_checkpoint(
        session_id="test-interrupt-001",
        workflow_name="research_workflow",
        current_stage=WorkflowStage.CONCEPTION,
        agent_session=session,
    )

    # 2. 创建中断事件
    interrupt = InterruptEvent(
        reason=InterruptReason.RESEARCH_PLAN_REVIEW,
        message="科研计划已生成，请审核",
        session_id="test-interrupt-001",
        priority=InterruptPriority.HIGH,
        context={"research_plan": session.state["research_plan"]},
        suggested_actions=["批准", "修改"],
    )

    # 3. 验证中断事件序列化
    interrupt_dict = interrupt.to_dict()
    assert interrupt_dict["reason"] == InterruptReason.RESEARCH_PLAN_REVIEW.value
    assert interrupt_dict["session_id"] == "test-interrupt-001"

    # 反序列化
    restored_interrupt = InterruptEvent.from_dict(interrupt_dict)
    assert restored_interrupt.reason == interrupt.reason
    assert restored_interrupt.message == interrupt.message


@pytest.mark.asyncio
async def test_checkpoint_history(
    test_db_session: AsyncSession,
):
    """
    测试检查点历史查询

    流程：
    1. 创建多个检查点
    2. 查询历史
    3. 验证排序和数量
    """
    state_manager = StateManager(test_db_session)

    # 1. 创建多个检查点
    session = AgentSession(session_id="test-history-001")

    for i in range(5):
        session.state["iteration"] = i
        await state_manager.create_checkpoint(
            session_id="test-history-001",
            workflow_name="research_workflow",
            current_stage=WorkflowStage.CONCEPTION,
            agent_session=session,
        )

    # 2. 查询历史
    history = await state_manager.get_session_history("test-history-001", limit=10)

    # 3. 验证排序和数量
    assert len(history) == 5
    # 验证按时间倒序排列（created_at 降序）
    for i in range(len(history) - 1):
        assert history[i].created_at >= history[i + 1].created_at


@pytest.mark.asyncio
async def test_state_integrity_validation(
    test_db_session: AsyncSession,
):
    """
    测试状态完整性验证

    流程：
    1. 创建检查点
    2. 验证状态哈希
    3. 确保数据完整性
    """
    state_manager = StateManager(test_db_session)

    # 1. 创建检查点
    session = AgentSession(session_id="test-integrity-001")
    session.state["important_data"] = "重要数据"

    checkpoint = await state_manager.create_checkpoint(
        session_id="test-integrity-001",
        workflow_name="research_workflow",
        current_stage=WorkflowStage.CONCEPTION,
        agent_session=session,
    )

    # 2. 验证状态哈希
    metadata = checkpoint.metadata_json or {}
    state_hash = metadata.get("state_hash")

    assert state_hash is not None
    assert len(state_hash) == 64  # SHA256 哈希长度

    # 3. 恢复并验证数据完整性
    restored = await state_manager.restore_from_checkpoint(checkpoint.id)
    assert restored.state["important_data"] == "重要数据"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s", "--tb=short"])
