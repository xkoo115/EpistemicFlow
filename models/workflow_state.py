"""
工作流状态模型
用于记录多智能体执行的状态机节点（Saga模式的基石）
"""

from typing import Any, Dict, Optional
from sqlalchemy import String, Text, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
import json

from .base import Base, TimestampMixin


class WorkflowStage(str, Enum):
    """工作流阶段枚举"""

    INITIALIZATION = "initialization"  # 初始化
    CONCEPTION = "conception"  # 构思
    LITERATURE_REVIEW = "literature_review"  # 文献检索
    METHODOLOGY_DESIGN = "methodology_design"  # 方法设计
    DATA_COLLECTION = "data_collection"  # 数据收集
    ANALYSIS = "analysis"  # 分析
    WRITING = "writing"  # 写作
    REVIEW = "review"  # 评审
    COMPLETION = "completion"  # 完成
    ERROR = "error"  # 错误


class WorkflowStatus(str, Enum):
    """工作流状态枚举"""

    PENDING = "pending"  # 待处理
    RUNNING = "running"  # 运行中
    PAUSED = "paused"  # 暂停
    COMPLETED = "completed"  # 完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 取消


class WorkflowState(Base, TimestampMixin):
    """工作流状态表

    用于记录多智能体执行的状态机节点，支持Saga模式
    """

    __tablename__ = "workflow_states"

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键ID"
    )

    session_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="会话ID，用于关联同一工作流的所有状态",
    )

    workflow_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="工作流名称"
    )

    current_stage: Mapped[WorkflowStage] = mapped_column(
        String(32), nullable=False, comment="当前阶段"
    )

    status: Mapped[WorkflowStatus] = mapped_column(
        String(32), nullable=False, default=WorkflowStatus.PENDING, comment="当前状态"
    )

    agent_state_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, comment="智能体状态JSON，存储智能体的内部状态"
    )

    human_feedback: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="人工反馈"
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="错误信息"
    )

    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, comment="元数据JSON，存储工作流相关配置和参数"
    )

    # 性能优化索引
    __table_args__ = (
        Index("ix_workflow_states_session_stage", "session_id", "current_stage"),
        Index("ix_workflow_states_status_created", "status", "created_at"),
        Index("ix_workflow_states_workflow_name", "workflow_name"),
    )

    @property
    def agent_state(self) -> Optional[Dict[str, Any]]:
        """获取智能体状态（反序列化）"""
        if self.agent_state_json:
            return self.agent_state_json
        return None

    @agent_state.setter
    def agent_state(self, value: Optional[Dict[str, Any]]) -> None:
        """设置智能体状态"""
        self.agent_state_json = value

    @property
    def metadata(self) -> Optional[Dict[str, Any]]:
        """获取元数据（反序列化）"""
        if self.metadata_json:
            return self.metadata_json
        return None

    @metadata.setter
    def metadata(self, value: Optional[Dict[str, Any]]) -> None:
        """设置元数据"""
        self.metadata_json = value

    def add_agent_state(self, key: str, value: Any) -> None:
        """添加智能体状态项"""
        if self.agent_state_json is None:
            self.agent_state_json = {}
        self.agent_state_json[key] = value

    def get_agent_state(self, key: str, default: Any = None) -> Any:
        """获取智能体状态项"""
        if self.agent_state_json and key in self.agent_state_json:
            return self.agent_state_json[key]
        return default

    def add_metadata(self, key: str, value: Any) -> None:
        """添加元数据项"""
        if self.metadata_json is None:
            self.metadata_json = {}
        self.metadata_json[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """获取元数据项"""
        if self.metadata_json and key in self.metadata_json:
            return self.metadata_json[key]
        return default

    def to_summary_dict(self) -> Dict[str, Any]:
        """转换为摘要字典（用于API响应）"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "workflow_name": self.workflow_name,
            "current_stage": self.current_stage,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "has_agent_state": self.agent_state_json is not None,
            "has_human_feedback": bool(self.human_feedback),
            "has_error": bool(self.error_message),
        }

    def __repr__(self) -> str:
        return (
            f"<WorkflowState(id={self.id}, "
            f"session_id={self.session_id}, "
            f"workflow_name={self.workflow_name}, "
            f"stage={self.current_stage}, "
            f"status={self.status})>"
        )
