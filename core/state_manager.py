"""
状态管理器模块

本模块提供多智能体系统的状态序列化与反序列化功能，是 HITL（Human-in-the-Loop）
检查点与 Saga 回滚机制的基石。

核心功能：
1. 提取 Agent Session 的上下文消息和记忆历史
2. 将状态序列化为 JSON 并保存至 WorkflowState 表
3. 从数据库 JSON 数据中精准重建 Agent Session

设计原则：
- 确定性序列化：相同状态必须产生相同的 JSON 表示
- 完整性恢复：反序列化后的 Session 必须完全恢复记忆
- 版本兼容：支持状态格式的向前兼容
"""

from typing import Any, Dict, Optional, Sequence
import json
from datetime import datetime
import hashlib

from agent_framework import AgentSession, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.workflow_state_repository import WorkflowStateRepository
from models.workflow_state import WorkflowState, WorkflowStage, WorkflowStatus


class StateSerializationError(Exception):
    """状态序列化异常"""
    pass


class StateDeserializationError(Exception):
    """状态反序列化异常"""
    pass


class StateManager:
    """
    状态管理器

    负责 Agent Session 状态的持久化与恢复，支持：
    - 检查点创建（Checkpoint Creation）
    - 状态快照（State Snapshot）
    - 确定性回滚（Deterministic Rollback）
    - 状态分叉（State Forking）

    使用场景：
    1. HITL 挂起：当工作流执行到关键节点时，保存当前状态并等待人工审核
    2. Saga 回滚：当检测到错误或收到回滚指令时，从历史检查点恢复状态
    3. 状态分叉：从历史节点创建新的执行路径，用于探索不同的决策分支
    """

    # 状态格式版本号（用于向前兼容）
    STATE_FORMAT_VERSION = "1.0.0"

    def __init__(self, db_session: AsyncSession):
        """
        初始化状态管理器

        Args:
            db_session: 数据库会话
        """
        self._repository = WorkflowStateRepository(db_session)

    async def create_checkpoint(
        self,
        session_id: str,
        workflow_name: str,
        current_stage: WorkflowStage,
        agent_session: AgentSession,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowState:
        """
        创建检查点

        将当前 Agent Session 的完整状态序列化并保存到数据库。

        Args:
            session_id: 会话 ID
            workflow_name: 工作流名称
            current_stage: 当前阶段
            agent_session: Agent Session 对象
            metadata: 额外的元数据

        Returns:
            创建的 WorkflowState 记录

        技术细节：
        - 使用 agent_framework 的 AgentSession.to_dict() 方法进行序列化
        - 该方法会自动处理 Pydantic 模型和其他复杂类型的序列化
        - 消息历史存储在 session.state["messages"] 中
        """
        try:
            # 序列化 Agent Session
            serialized_state = self._serialize_agent_session(agent_session)

            # 计算状态哈希（用于验证完整性）
            state_hash = self._compute_state_hash(serialized_state)

            # 准备元数据
            checkpoint_metadata = {
                "state_format_version": self.STATE_FORMAT_VERSION,
                "state_hash": state_hash,
                "checkpoint_timestamp": datetime.utcnow().isoformat(),
                **(metadata or {}),
            }

            # 保存到数据库
            workflow_state = await self._repository.create(
                session_id=session_id,
                workflow_name=workflow_name,
                current_stage=current_stage,
                status=WorkflowStatus.PAUSED,  # 检查点默认为暂停状态
                agent_state=serialized_state,
                metadata=checkpoint_metadata,
            )

            return workflow_state

        except Exception as e:
            raise StateSerializationError(f"创建检查点失败: {str(e)}") from e

    async def restore_from_checkpoint(
        self,
        checkpoint_id: int,
    ) -> AgentSession:
        """
        从检查点恢复

        从数据库中读取序列化的状态并重建 Agent Session。

        Args:
            checkpoint_id: 检查点 ID（WorkflowState 的主键）

        Returns:
            恢复的 AgentSession 对象

        技术细节：
        - 使用 AgentSession.from_dict() 方法进行反序列化
        - 该方法会自动恢复 Pydantic 模型和其他复杂类型
        - 消息历史会自动恢复到 session.state["messages"] 中
        - 验证状态哈希以确保数据完整性
        """
        try:
            # 从数据库读取状态
            workflow_state = await self._repository.get_by_id(checkpoint_id)
            if not workflow_state:
                raise StateDeserializationError(f"检查点不存在: {checkpoint_id}")

            if not workflow_state.agent_state_json:
                raise StateDeserializationError(f"检查点状态为空: {checkpoint_id}")

            # 验证状态哈希
            metadata = workflow_state.metadata_json or {}
            expected_hash = metadata.get("state_hash")
            if expected_hash:
                actual_hash = self._compute_state_hash(workflow_state.agent_state_json)
                if actual_hash != expected_hash:
                    raise StateDeserializationError(
                        f"状态哈希不匹配，数据可能已损坏。"
                        f"期望: {expected_hash}, 实际: {actual_hash}"
                    )

            # 反序列化 Agent Session
            agent_session = self._deserialize_agent_session(
                workflow_state.agent_state_json
            )

            return agent_session

        except StateDeserializationError:
            raise
        except Exception as e:
            raise StateDeserializationError(f"从检查点恢复失败: {str(e)}") from e

    async def fork_from_checkpoint(
        self,
        checkpoint_id: int,
        new_session_id: str,
        workflow_name: str,
        new_stage: WorkflowStage,
        human_feedback: Optional[str] = None,
        additional_state: Optional[Dict[str, Any]] = None,
    ) -> WorkflowState:
        """
        从检查点分叉

        从历史检查点创建新的执行路径。这是 Saga 模式的核心操作。

        Args:
            checkpoint_id: 历史检查点 ID
            new_session_id: 新会话 ID
            workflow_name: 工作流名称
            new_stage: 新阶段
            human_feedback: 人类反馈（将注入到新状态中）
            additional_state: 额外的状态更新

        Returns:
            新创建的 WorkflowState 记录

        使用场景：
        - 用户要求修改历史决策（如"增加对比实验"）
        - 系统检测到错误需要回滚并尝试新策略
        - 探索不同的决策分支（A/B 测试）
        """
        try:
            # 从历史检查点恢复状态
            agent_session = await self.restore_from_checkpoint(checkpoint_id)

            # 注入人类反馈
            if human_feedback:
                agent_session.state["human_feedback"] = human_feedback
                agent_session.state["feedback_timestamp"] = datetime.utcnow().isoformat()

            # 注入额外状态
            if additional_state:
                agent_session.state.update(additional_state)

            # 标记为分叉状态
            agent_session.state["forked_from"] = checkpoint_id
            agent_session.state["fork_timestamp"] = datetime.utcnow().isoformat()

            # 创建新的检查点
            new_checkpoint = await self.create_checkpoint(
                session_id=new_session_id,
                workflow_name=workflow_name,
                current_stage=new_stage,
                agent_session=agent_session,
                metadata={
                    "fork_source": checkpoint_id,
                    "fork_reason": human_feedback or "系统分叉",
                },
            )

            # 添加人类反馈到数据库记录
            if human_feedback:
                await self._repository.add_human_feedback(
                    new_checkpoint.id, human_feedback
                )

            return new_checkpoint

        except Exception as e:
            raise StateSerializationError(f"从检查点分叉失败: {str(e)}") from e

    def _serialize_agent_session(self, agent_session: AgentSession) -> Dict[str, Any]:
        """
        序列化 Agent Session

        使用 agent_framework 提供的序列化方法，确保所有复杂类型
        （如 Pydantic 模型、Message 对象）都能正确序列化。

        Args:
            agent_session: Agent Session 对象

        Returns:
            序列化后的字典

        技术细节：
        - AgentSession.to_dict() 会递归序列化 state 字典中的所有值
        - Message 对象会被序列化为包含 "type" 字段的字典
        - Pydantic 模型会被序列化为 model_dump() 的结果
        - 列表和字典会被递归处理
        """
        serialized = agent_session.to_dict()

        # 添加额外的元数据
        serialized["serialization_metadata"] = {
            "format_version": self.STATE_FORMAT_VERSION,
            "serialized_at": datetime.utcnow().isoformat(),
            "session_type": "agent_framework.AgentSession",
        }

        return serialized

    def _deserialize_agent_session(
        self, serialized_state: Dict[str, Any]
    ) -> AgentSession:
        """
        反序列化 Agent Session

        使用 agent_framework 提供的反序列化方法，确保所有复杂类型
        都能正确恢复。

        Args:
            serialized_state: 序列化的状态字典

        Returns:
            恢复的 AgentSession 对象

        技术细节：
        - AgentSession.from_dict() 会递归反序列化 state 字典中的所有值
        - 包含 "type" 字段的字典会被恢复为对应的类型实例
        - Message 对象会被完整恢复，包括 role、contents 等字段
        - Pydantic 模型会被恢复为对应的模型实例
        """
        # 移除序列化元数据（不需要恢复到 Session 中）
        serialized_state.pop("serialization_metadata", None)

        # 使用 agent_framework 的反序列化方法
        agent_session = AgentSession.from_dict(serialized_state)

        return agent_session

    def _compute_state_hash(self, state: Dict[str, Any]) -> str:
        """
        计算状态哈希

        用于验证状态的完整性，检测数据是否在存储过程中被损坏。

        Args:
            state: 状态字典

        Returns:
            SHA256 哈希值（十六进制字符串）
        """
        # 将状态转换为确定性的 JSON 字符串
        # sort_keys=True 确保字典键的顺序一致
        state_json = json.dumps(state, sort_keys=True, ensure_ascii=False)

        # 计算 SHA256 哈希
        hash_value = hashlib.sha256(state_json.encode("utf-8")).hexdigest()

        return hash_value

    async def get_session_history(
        self,
        session_id: str,
        limit: int = 100,
    ) -> Sequence[WorkflowState]:
        """
        获取会话历史

        查询指定会话的所有检查点，按时间倒序排列。

        Args:
            session_id: 会话 ID
            limit: 返回记录数限制

        Returns:
            WorkflowState 列表
        """
        return await self._repository.get_by_session_id(session_id, limit=limit)

    async def get_latest_checkpoint(
        self,
        session_id: str,
        stage: Optional[WorkflowStage] = None,
    ) -> Optional[WorkflowState]:
        """
        获取最新检查点

        查询指定会话（和可选阶段）的最新检查点。

        Args:
            session_id: 会话 ID
            stage: 可选的阶段过滤

        Returns:
            最新的 WorkflowState 记录，不存在则返回 None
        """
        if stage:
            return await self._repository.get_latest_by_session_and_stage(
                session_id, stage
            )
        else:
            # 获取最新的检查点
            states = await self._repository.get_by_session_id(session_id, limit=1)
            return states[0] if states else None

    async def update_checkpoint_status(
        self,
        checkpoint_id: int,
        status: WorkflowStatus,
        error_message: Optional[str] = None,
    ) -> Optional[WorkflowState]:
        """
        更新检查点状态

        Args:
            checkpoint_id: 检查点 ID
            status: 新状态
            error_message: 错误信息（可选）

        Returns:
            更新后的 WorkflowState 记录
        """
        return await self._repository.update_status(checkpoint_id, status, error_message)

    def extract_message_history(
        self, agent_session: AgentSession
    ) -> Sequence[Message]:
        """
        提取消息历史

        从 Agent Session 中提取完整的消息历史。

        Args:
            agent_session: Agent Session 对象

        Returns:
            Message 对象列表

        技术细节：
        - 消息历史存储在 session.state["messages"] 中
        - 这是 InMemoryHistoryProvider 的默认存储位置
        - 消息按时间顺序排列（最早的在前）
        """
        messages = agent_session.state.get("messages", [])
        return list(messages)

    def inject_message(
        self,
        agent_session: AgentSession,
        message: Message,
    ) -> None:
        """
        注入消息

        向 Agent Session 的消息历史中添加新消息。

        Args:
            agent_session: Agent Session 对象
            message: 要添加的消息

        使用场景：
        - 恢复执行时注入人类反馈消息
        - 回滚后注入修正指令
        """
        if "messages" not in agent_session.state:
            agent_session.state["messages"] = []

        agent_session.state["messages"].append(message)

    def inject_human_feedback_as_message(
        self,
        agent_session: AgentSession,
        feedback: str,
        role: str = "user",
    ) -> None:
        """
        将人类反馈注入为消息

        创建一个包含人类反馈的消息并注入到 Session 中。

        Args:
            agent_session: Agent Session 对象
            feedback: 反馈内容
            role: 消息角色（默认为 "user"）

        技术细节：
        - 使用 agent_framework 的 Message 和 Content 类
        - Content.from_text() 创建文本内容
        - 消息会被添加到 session.state["messages"] 列表
        """
        from agent_framework import Content

        message = Message(
            role=role,
            contents=[Content.from_text(feedback)],
        )
        self.inject_message(agent_session, message)
