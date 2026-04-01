"""
单元测试：Saga 状态机兼容性模块

测试 agents/saga_integration.py 中的状态管理和检查点功能。
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from agent_framework import (
    WorkflowCheckpoint,
    InMemoryCheckpointStorage,
    State,
    WorkflowRunState,
)

from agents.saga_integration import (
    SagaCheckpoint,
    SagaStateManager,
    HITLInterruptPoint,
    HITLManager,
    WorkflowStateSynchronizer,
    get_saga_manager,
    create_saga_checkpoint,
    restore_saga_checkpoint,
)


class TestSagaCheckpoint:
    """Saga 检查点测试"""
    
    def test_from_workflow_checkpoint(self):
        """测试从 WorkflowCheckpoint 创建 SagaCheckpoint"""
        # 创建原生检查点
        checkpoint = WorkflowCheckpoint(
            workflow_name="test_workflow",
            graph_signature_hash="abc123",
            messages={
                "executor_1": [MagicMock(__dict__={"content": "test"})],
            },
            state={"key": "value"},
            pending_request_info_events={},
            iteration_count=5,
            metadata={"custom": "data"},
        )
        checkpoint.checkpoint_id = "cp_001"
        
        # 转换
        saga_checkpoint = SagaCheckpoint.from_workflow_checkpoint(checkpoint)
        
        # 验证
        assert saga_checkpoint.checkpoint_id == "cp_001"
        assert saga_checkpoint.workflow_name == "test_workflow"
        assert saga_checkpoint.iteration_count == 5
        assert saga_checkpoint.state == {"key": "value"}
    
    def test_to_dict(self):
        """测试转换为字典"""
        checkpoint = SagaCheckpoint(
            checkpoint_id="cp_002",
            workflow_name="test",
            timestamp="2024-01-01T00:00:00",
            iteration_count=1,
            messages={},
            state={"test": "value"},
            pending_requests={},
        )
        
        data = checkpoint.to_dict()
        
        assert data["checkpoint_id"] == "cp_002"
        assert data["workflow_name"] == "test"
        assert data["state"] == {"test": "value"}


class TestSagaStateManager:
    """Saga 状态管理器测试"""
    
    @pytest.mark.asyncio
    async def test_create_checkpoint(self):
        """测试创建检查点"""
        manager = SagaStateManager()
        
        # 创建状态
        state = State()
        state.set("test_key", "test_value")
        
        # 创建检查点
        checkpoint = await manager.create_checkpoint(
            workflow_name="test_workflow",
            state=state,
            messages={"executor_1": []},
            pending_requests={},
            metadata={"iteration_count": 1},
        )
        
        # 验证
        assert checkpoint.workflow_name == "test_workflow"
        assert checkpoint.checkpoint_id is not None
    
    @pytest.mark.asyncio
    async def test_restore_checkpoint(self):
        """测试恢复检查点"""
        manager = SagaStateManager()
        
        # 先创建一个检查点
        state = State()
        state.set("key", "value")
        
        created = await manager.create_checkpoint(
            workflow_name="test",
            state=state,
            messages={},
            pending_requests={},
        )
        
        # 恢复
        restored = await manager.restore_checkpoint(created.checkpoint_id)
        
        # 验证
        assert restored.checkpoint_id == created.checkpoint_id
        assert restored.workflow_name == "test"
    
    @pytest.mark.asyncio
    async def test_fork_from_checkpoint(self):
        """测试 Fork 操作"""
        manager = SagaStateManager()
        
        # 创建源检查点
        state = State()
        state.set("original", "data")
        
        source = await manager.create_checkpoint(
            workflow_name="test",
            state=state,
            messages={},
            pending_requests={},
        )
        
        # Fork
        forked = await manager.fork_from_checkpoint(
            checkpoint_id=source.checkpoint_id,
            new_session_id="fork_session",
            human_feedback={"comment": "请修改"},
        )
        
        # 验证
        assert forked.state["forked_from"] == source.checkpoint_id
        assert forked.state["human_feedback"] == {"comment": "请修改"}
    
    @pytest.mark.asyncio
    async def test_verify_checkpoint_integrity(self):
        """测试检查点完整性验证"""
        manager = SagaStateManager()
        
        # 创建有效检查点
        state = State()
        checkpoint = await manager.create_checkpoint(
            workflow_name="test",
            state=state,
            messages={},
            pending_requests={},
        )
        
        # 验证
        is_valid = await manager.verify_checkpoint_integrity(checkpoint.checkpoint_id)
        assert is_valid is True
        
        # 验证不存在的检查点
        is_valid = await manager.verify_checkpoint_integrity("nonexistent")
        assert is_valid is False


class TestHITLManager:
    """HITL 管理器测试"""
    
    @pytest.mark.asyncio
    async def test_create_interrupt(self):
        """测试创建中断点"""
        saga_manager = SagaStateManager()
        hitl_manager = HITLManager(saga_manager)
        
        # 创建 request_info 事件
        event = MagicMock()
        event.request_id = "req_001"
        event.source_executor_id = "executor_1"
        event.request_type = MagicMock(__name__="HumanFeedback")
        event.data = {"question": "请确认"}
        event.response_type = MagicMock(__name__="FeedbackResponse")
        
        # 创建中断
        interrupt = await hitl_manager.create_interrupt(event)
        
        # 验证
        assert interrupt.request_id == "req_001"
        assert interrupt.executor_id == "executor_1"
        assert interrupt.request_type == "HumanFeedback"
    
    @pytest.mark.asyncio
    async def test_get_pending_interrupts(self):
        """测试获取待处理中断"""
        saga_manager = SagaStateManager()
        hitl_manager = HITLManager(saga_manager)
        
        # 创建中断
        event = MagicMock()
        event.request_id = "req_002"
        event.source_executor_id = "executor_1"
        event.request_type = MagicMock(__name__="Test")
        event.data = {}
        event.response_type = MagicMock(__name__="TestResponse")
        
        await hitl_manager.create_interrupt(event)
        
        # 获取待处理中断
        pending = await hitl_manager.get_pending_interrupts("session_1")
        
        assert len(pending) == 1
        assert pending[0].request_id == "req_002"


class TestWorkflowStateSynchronizer:
    """工作流状态同步器测试"""
    
    def test_map_run_state_to_status(self):
        """测试运行状态映射"""
        # 测试各种状态映射
        assert WorkflowStateSynchronizer.map_run_state_to_status(
            WorkflowRunState.STARTED
        ).value == "pending"
        
        assert WorkflowStateSynchronizer.map_run_state_to_status(
            WorkflowRunState.IN_PROGRESS
        ).value == "running"
        
        assert WorkflowStateSynchronizer.map_run_state_to_status(
            WorkflowRunState.FAILED
        ).value == "failed"
    
    def test_map_checkpoint_to_workflow_state(self):
        """测试检查点映射到工作流状态"""
        checkpoint = SagaCheckpoint(
            checkpoint_id="cp_003",
            workflow_name="test",
            timestamp="2024-01-01T00:00:00",
            iteration_count=1,
            messages={},
            state={"current_stage": "literature_review"},
            pending_requests={},
        )
        
        result = WorkflowStateSynchronizer.map_checkpoint_to_workflow_state(
            checkpoint,
            session_id="session_1",
        )
        
        assert result["session_id"] == "session_1"
        assert result["checkpoint_id"] == "cp_003"
        assert result["current_stage"] == "literature_review"


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    @pytest.mark.asyncio
    async def test_create_saga_checkpoint(self):
        """测试便捷创建检查点"""
        state = State()
        state.set("key", "value")
        
        checkpoint = await create_saga_checkpoint(
            workflow_name="test",
            state=state,
            messages={},
            pending_requests={},
        )
        
        assert checkpoint.workflow_name == "test"
    
    @pytest.mark.asyncio
    async def test_restore_saga_checkpoint(self):
        """测试便捷恢复检查点"""
        # 先创建
        state = State()
        created = await create_saga_checkpoint(
            workflow_name="test",
            state=state,
            messages={},
            pending_requests={},
        )
        
        # 恢复
        restored = await restore_saga_checkpoint(created.checkpoint_id)
        
        assert restored.checkpoint_id == created.checkpoint_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
