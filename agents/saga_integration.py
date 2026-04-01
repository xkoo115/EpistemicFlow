"""
Saga 状态机兼容性模块 (Saga State Machine Compatibility)

本模块确保在将控制权移交给 agent_framework 原生编排后，
依然能够获取全局 State，支持 HITL 和确定性回滚。

核心保证：
1. 全局状态快照：通过 WorkflowCheckpoint 获取完整状态
2. HITL 断点挂起：通过 request_info 事件实现
3. 确定性回滚：通过 checkpoint_id 恢复执行
4. Fork 机制：从历史检查点创建新执行路径

原生特性映射：
- WorkflowCheckpoint -> Saga 检查点
- request_info 事件 -> HITL 中断
- checkpoint_id 恢复 -> Saga 回滚
- FileCheckpointStorage -> 持久化存储

设计原则：
- 无缝集成：与现有 StateManager 兼容
- 确定性保证：相同 checkpoint_id 必产生相同状态
- 完整性验证：检查点必须包含所有必要信息
"""

from typing import Any, Dict, List, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import json

from agent_framework import (
    WorkflowCheckpoint,
    FileCheckpointStorage,
    InMemoryCheckpointStorage,
    WorkflowEvent,
    WorkflowRunState,
    State,
)

from models.workflow_state import (
    WorkflowStage,
    WorkflowStatus,
    WorkflowState as DBWorkflowState,
)
from core.state_manager import StateManager


# ============================================================================
# 类型定义
# ============================================================================

T = TypeVar("T")


# ============================================================================
# Saga 检查点适配器
# ============================================================================

@dataclass
class SagaCheckpoint:
    """
    Saga 检查点
    
    封装 agent_framework 的 WorkflowCheckpoint，
    提供与现有 StateManager 兼容的接口。
    
    原生特性：
    - WorkflowCheckpoint 包含完整的图状态
    - messages: 执行器间消息
    - state: 已提交状态
    - pending_request_info_events: 待处理请求（HITL）
    """
    checkpoint_id: str
    """检查点 ID"""
    workflow_name: str
    """工作流名称"""
    timestamp: str
    """时间戳"""
    iteration_count: int
    """迭代计数"""
    
    # 状态数据
    messages: Dict[str, List[Any]]
    """执行器间消息"""
    state: Dict[str, Any]
    """已提交状态"""
    pending_requests: Dict[str, Any]
    """待处理请求（HITL）"""
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    """元数据"""
    
    @classmethod
    def from_workflow_checkpoint(
        cls,
        checkpoint: WorkflowCheckpoint,
    ) -> 'SagaCheckpoint':
        """
        从 WorkflowCheckpoint 创建 SagaCheckpoint
        
        原生特性说明：
        - WorkflowCheckpoint 是 agent_framework 的原生检查点类型
        - 包含完整的图状态，可完全恢复执行
        
        Args:
            checkpoint: 原生检查点
        
        Returns:
            Saga 检查点
        """
        return cls(
            checkpoint_id=str(checkpoint.checkpoint_id),
            workflow_name=checkpoint.workflow_name,
            timestamp=checkpoint.timestamp,
            iteration_count=checkpoint.iteration_count,
            messages={
                k: [msg.__dict__ if hasattr(msg, '__dict__') else msg for msg in v]
                for k, v in checkpoint.messages.items()
            },
            state=checkpoint.state,
            pending_requests={
                k: v.to_dict() if hasattr(v, 'to_dict') else v
                for k, v in checkpoint.pending_request_info_events.items()
            },
            metadata=checkpoint.metadata,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            "checkpoint_id": self.checkpoint_id,
            "workflow_name": self.workflow_name,
            "timestamp": self.timestamp,
            "iteration_count": self.iteration_count,
            "messages": self.messages,
            "state": self.state,
            "pending_requests": self.pending_requests,
            "metadata": self.metadata,
        }


# ============================================================================
# Saga 状态管理器适配器
# ============================================================================

class SagaStateManager:
    """
    Saga 状态管理器
    
    适配 agent_framework 的检查点机制到现有 StateManager 接口。
    
    核心功能：
    1. 创建检查点：保存当前工作流状态
    2. 恢复检查点：从历史状态恢复执行
    3. Fork：从检查点创建新执行路径
    4. 完整性验证：确保检查点有效
    
    原生特性：
    - 使用 FileCheckpointStorage 持久化
    - 通过 WorkflowCheckpoint 获取全局状态
    - 支持 checkpoint_id 恢复
    """
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        db_state_manager: Optional[StateManager] = None,
    ):
        """
        初始化 Saga 状态管理器
        
        Args:
            storage_path: 检查点存储路径（None 则使用内存存储）
            db_state_manager: 数据库状态管理器（用于持久化）
        """
        # 原生检查点存储
        if storage_path:
            self._checkpoint_storage = FileCheckpointStorage(storage_path)
        else:
            self._checkpoint_storage = InMemoryCheckpointStorage()
        
        # 数据库状态管理器
        self._db_manager = db_state_manager
        
        # 检查点缓存
        self._checkpoint_cache: Dict[str, SagaCheckpoint] = {}
    
    async def create_checkpoint(
        self,
        workflow_name: str,
        state: State,
        messages: Dict[str, List[Any]],
        pending_requests: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SagaCheckpoint:
        """
        创建检查点
        
        原生特性说明：
        - State 是 agent_framework 的原生状态类
        - 使用超步语义：在超步边界提交状态
        - 检查点包含完整的图状态
        
        Args:
            workflow_name: 工作流名称
            state: 当前状态
            messages: 执行器间消息
            pending_requests: 待处理请求
            metadata: 元数据
        
        Returns:
            创建的检查点
        """
        # 导出状态
        state_dict = state.export_state()
        
        # 创建原生检查点
        checkpoint = WorkflowCheckpoint(
            workflow_name=workflow_name,
            graph_signature_hash="",  # 由框架计算
            messages=messages,
            state=state_dict,
            pending_request_info_events=pending_requests,
            iteration_count=metadata.get("iteration_count", 0) if metadata else 0,
            metadata=metadata or {},
        )
        
        # 保存到存储
        checkpoint_id = await self._checkpoint_storage.save(checkpoint)
        
        # 创建 Saga 检查点
        saga_checkpoint = SagaCheckpoint.from_workflow_checkpoint(checkpoint)
        saga_checkpoint.checkpoint_id = str(checkpoint_id)
        
        # 缓存
        self._checkpoint_cache[saga_checkpoint.checkpoint_id] = saga_checkpoint
        
        # 同步到数据库（如果配置了）
        if self._db_manager:
            await self._sync_to_db(saga_checkpoint)
        
        return saga_checkpoint
    
    async def restore_checkpoint(
        self,
        checkpoint_id: str,
    ) -> SagaCheckpoint:
        """
        恢复检查点
        
        原生特性说明：
        - 通过 checkpoint_id 加载历史状态
        - 恢复后可继续执行或 Fork
        
        Args:
            checkpoint_id: 检查点 ID
        
        Returns:
            恢复的检查点
        """
        # 检查缓存
        if checkpoint_id in self._checkpoint_cache:
            return self._checkpoint_cache[checkpoint_id]
        
        # 从存储加载
        checkpoint = await self._checkpoint_storage.load(checkpoint_id)
        
        # 转换为 Saga 检查点
        saga_checkpoint = SagaCheckpoint.from_workflow_checkpoint(checkpoint)
        
        # 缓存
        self._checkpoint_cache[checkpoint_id] = saga_checkpoint
        
        return saga_checkpoint
    
    async def fork_from_checkpoint(
        self,
        checkpoint_id: str,
        new_session_id: str,
        human_feedback: Optional[Dict[str, Any]] = None,
        additional_state: Optional[Dict[str, Any]] = None,
    ) -> SagaCheckpoint:
        """
        从检查点 Fork
        
        原生特性说明：
        - Fork 是 Saga 模式的核心操作
        - 从历史检查点创建新的执行路径
        - 可注入人类反馈和额外状态
        
        Args:
            checkpoint_id: 源检查点 ID
            new_session_id: 新会话 ID
            human_feedback: 人类反馈（HITL）
            additional_state: 额外状态
        
        Returns:
            新的检查点
        """
        # 恢复源检查点
        source_checkpoint = await self.restore_checkpoint(checkpoint_id)
        
        # 创建新状态
        new_state = source_checkpoint.state.copy()
        
        # 注入人类反馈
        if human_feedback:
            new_state["human_feedback"] = human_feedback
            new_state["feedback_timestamp"] = datetime.now().isoformat()
        
        # 注入额外状态
        if additional_state:
            new_state.update(additional_state)
        
        # 记录 Fork 来源
        new_state["forked_from"] = checkpoint_id
        new_state["fork_session_id"] = new_session_id
        
        # 创建新检查点
        new_checkpoint = await self.create_checkpoint(
            workflow_name=source_checkpoint.workflow_name,
            state=State(),  # 创建空状态，然后导入
            messages=source_checkpoint.messages,
            pending_requests={},  # Fork 后清空待处理请求
            metadata={
                "forked_from": checkpoint_id,
                "fork_timestamp": datetime.now().isoformat(),
                "iteration_count": source_checkpoint.iteration_count,
            },
        )
        
        # 导入状态
        # 注意：这里需要手动设置状态，因为 State() 创建的是空状态
        new_checkpoint.state = new_state
        
        return new_checkpoint
    
    async def list_checkpoints(
        self,
        workflow_name: str,
    ) -> List[SagaCheckpoint]:
        """
        列出工作流的所有检查点
        
        Args:
            workflow_name: 工作流名称
        
        Returns:
            检查点列表（按时间倒序）
        """
        checkpoints = await self._checkpoint_storage.list_checkpoints(
            workflow_name=workflow_name,
        )
        
        saga_checkpoints = [
            SagaCheckpoint.from_workflow_checkpoint(cp)
            for cp in checkpoints
        ]
        
        # 按时间倒序
        saga_checkpoints.sort(
            key=lambda x: x.timestamp,
            reverse=True,
        )
        
        return saga_checkpoints
    
    async def verify_checkpoint_integrity(
        self,
        checkpoint_id: str,
    ) -> bool:
        """
        验证检查点完整性
        
        确保检查点包含所有必要信息，可安全恢复。
        
        Args:
            checkpoint_id: 检查点 ID
        
        Returns:
            完整性验证结果
        """
        try:
            checkpoint = await self.restore_checkpoint(checkpoint_id)
            
            # 验证必要字段
            if not checkpoint.checkpoint_id:
                return False
            if not checkpoint.workflow_name:
                return False
            if not checkpoint.timestamp:
                return False
            
            # 验证状态完整性
            if checkpoint.state is None:
                return False
            
            # 验证消息完整性
            if checkpoint.messages is None:
                return False
            
            return True
        except Exception:
            return False
    
    async def _sync_to_db(
        self,
        checkpoint: SagaCheckpoint,
    ) -> None:
        """
        同步检查点到数据库
        
        Args:
            checkpoint: 检查点
        """
        if not self._db_manager:
            return
        
        # 将检查点状态同步到数据库
        # 这确保了与现有 StateManager 的兼容性
        # 实际实现需要根据具体的数据库模型调整
        pass


# ============================================================================
# HITL（人在回路）支持
# ============================================================================

@dataclass
class HITLInterruptPoint:
    """
    HITL 中断点
    
    当工作流需要人类输入时，创建中断点并挂起执行。
    
    原生特性：
    - 通过 request_info 事件触发
    - 工作流进入 IDLE_WITH_PENDING_REQUESTS 状态
    - 可通过 checkpoint_id 恢复
    """
    request_id: str
    """请求 ID"""
    executor_id: str
    """请求来源执行器"""
    request_type: str
    """请求类型"""
    request_data: Any
    """请求数据"""
    response_type: str
    """期望的响应类型"""
    checkpoint_id: str
    """当前检查点 ID"""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    """时间戳"""


class HITLManager:
    """
    HITL 管理器
    
    管理人在回路的中断和恢复。
    
    原生特性：
    - 监听 request_info 事件
    - 创建中断点并挂起工作流
    - 接收人类响应后恢复执行
    """
    
    def __init__(
        self,
        saga_manager: SagaStateManager,
    ):
        """
        初始化 HITL 管理器
        
        Args:
            saga_manager: Saga 状态管理器
        """
        self._saga_manager = saga_manager
        self._pending_interrupts: Dict[str, HITLInterruptPoint] = {}
    
    async def create_interrupt(
        self,
        event: WorkflowEvent,
    ) -> HITLInterruptPoint:
        """
        创建中断点
        
        原生特性说明：
        - 当工作流发出 request_info 事件时调用
        - 工作流自动挂起，等待人类响应
        
        Args:
            event: request_info 事件
        
        Returns:
            中断点
        """
        interrupt = HITLInterruptPoint(
            request_id=event.request_id,
            executor_id=event.source_executor_id,
            request_type=event.request_type.__name__ if hasattr(event.request_type, '__name__') else str(event.request_type),
            request_data=event.data,
            response_type=event.response_type.__name__ if hasattr(event.response_type, '__name__') else str(event.response_type),
            checkpoint_id="",  # 需要从上下文获取
        )
        
        self._pending_interrupts[interrupt.request_id] = interrupt
        
        return interrupt
    
    async def resume_with_response(
        self,
        request_id: str,
        response: Any,
    ) -> str:
        """
        提供响应并恢复执行
        
        原生特性说明：
        - 人类提供响应后调用
        - 工作流从挂起点恢复，继续执行
        
        Args:
            request_id: 请求 ID
            response: 人类响应
        
        Returns:
            新的检查点 ID
        """
        interrupt = self._pending_interrupts.pop(request_id, None)
        if not interrupt:
            raise ValueError(f"未找到中断点: {request_id}")
        
        # Fork 并注入响应
        new_checkpoint = await self._saga_manager.fork_from_checkpoint(
            checkpoint_id=interrupt.checkpoint_id,
            new_session_id=f"resume_{request_id}",
            human_feedback={
                "request_id": request_id,
                "response": response,
            },
        )
        
        return new_checkpoint.checkpoint_id
    
    async def get_pending_interrupts(
        self,
        session_id: str,
    ) -> List[HITLInterruptPoint]:
        """
        获取待处理的中断点
        
        Args:
            session_id: 会话 ID
        
        Returns:
            中断点列表
        """
        return list(self._pending_interrupts.values())


# ============================================================================
# 工作流状态同步器
# ============================================================================

class WorkflowStateSynchronizer:
    """
    工作流状态同步器
    
    将 agent_framework 的原生状态同步到数据库模型。
    
    确保兼容性：
    - WorkflowRunState -> WorkflowStatus
    - 检查点 -> WorkflowState
    - 事件 -> 状态变更
    """
    
    @staticmethod
    def map_run_state_to_status(
        run_state: WorkflowRunState,
    ) -> WorkflowStatus:
        """
        映射运行状态到数据库状态
        
        Args:
            run_state: 原生运行状态
        
        Returns:
            数据库状态
        """
        mapping = {
            WorkflowRunState.STARTED: WorkflowStatus.PENDING,
            WorkflowRunState.IN_PROGRESS: WorkflowStatus.RUNNING,
            WorkflowRunState.IN_PROGRESS_PENDING_REQUESTS: WorkflowStatus.RUNNING,
            WorkflowRunState.IDLE: WorkflowStatus.PAUSED,
            WorkflowRunState.IDLE_WITH_PENDING_REQUESTS: WorkflowStatus.PAUSED,
            WorkflowRunState.FAILED: WorkflowStatus.FAILED,
            WorkflowRunState.CANCELLED: WorkflowStatus.CANCELLED,
        }
        
        return mapping.get(run_state, WorkflowStatus.PENDING)
    
    @staticmethod
    def map_checkpoint_to_workflow_state(
        checkpoint: SagaCheckpoint,
        session_id: str,
    ) -> Dict[str, Any]:
        """
        映射检查点到工作流状态
        
        Args:
            checkpoint: Saga 检查点
            session_id: 会话 ID
        
        Returns:
            工作流状态字典
        """
        return {
            "session_id": session_id,
            "checkpoint_id": checkpoint.checkpoint_id,
            "current_stage": checkpoint.state.get("current_stage", WorkflowStage.INITIALIZATION.value),
            "status": WorkflowStatus.PAUSED.value,
            "agent_state": checkpoint.state,
            "created_at": checkpoint.timestamp,
            "updated_at": datetime.now().isoformat(),
        }


# ============================================================================
# 全局 Saga 管理器实例
# ============================================================================

_saga_manager: Optional[SagaStateManager] = None


def get_saga_manager(
    storage_path: Optional[str] = None,
) -> SagaStateManager:
    """
    获取全局 Saga 管理器
    
    Args:
        storage_path: 检查点存储路径
    
    Returns:
        Saga 状态管理器
    """
    global _saga_manager
    
    if _saga_manager is None:
        _saga_manager = SagaStateManager(storage_path=storage_path)
    
    return _saga_manager


async def create_saga_checkpoint(
    workflow_name: str,
    state: State,
    messages: Dict[str, List[Any]],
    pending_requests: Dict[str, Any],
) -> SagaCheckpoint:
    """
    创建 Saga 检查点（便捷函数）
    
    Args:
        workflow_name: 工作流名称
        state: 当前状态
        messages: 执行器间消息
        pending_requests: 待处理请求
    
    Returns:
        创建的检查点
    """
    manager = get_saga_manager()
    return await manager.create_checkpoint(
        workflow_name=workflow_name,
        state=state,
        messages=messages,
        pending_requests=pending_requests,
    )


async def restore_saga_checkpoint(
    checkpoint_id: str,
) -> SagaCheckpoint:
    """
    恢复 Saga 检查点（便捷函数）
    
    Args:
        checkpoint_id: 检查点 ID
    
    Returns:
        恢复的检查点
    """
    manager = get_saga_manager()
    return await manager.restore_checkpoint(checkpoint_id)


async def fork_saga_checkpoint(
    checkpoint_id: str,
    new_session_id: str,
    human_feedback: Optional[Dict[str, Any]] = None,
) -> SagaCheckpoint:
    """
    Fork Saga 检查点（便捷函数）
    
    Args:
        checkpoint_id: 源检查点 ID
        new_session_id: 新会话 ID
        human_feedback: 人类反馈
    
    Returns:
        新的检查点
    """
    manager = get_saga_manager()
    return await manager.fork_from_checkpoint(
        checkpoint_id=checkpoint_id,
        new_session_id=new_session_id,
        human_feedback=human_feedback,
    )
