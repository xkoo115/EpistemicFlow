"""
工作流状态模型
用于记录多智能体执行的状态机节点（Saga模式的基石）
"""

from typing import Any, Dict, Optional
from enum import Enum
import json
from datetime import datetime

from sqlalchemy import String, Text, DateTime, JSON, Integer, Enum as SQLEnum, Column, func
from sqlalchemy.orm import declarative_base

from .base import BaseModel


Base = declarative_base()


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


class WorkflowState(Base):
    """工作流状态表

    用于记录多智能体执行的状态机节点，支持Saga模式
    """
    __tablename__ = "workflow_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), index=True, nullable=False)
    workflow_name = Column(String(255), nullable=False)
    current_stage = Column(SQLEnum(WorkflowStage), nullable=False)
    status = Column(SQLEnum(WorkflowStatus), nullable=False, default=WorkflowStatus.PENDING)
    agent_state_json = Column(JSON, nullable=True)
    human_feedback = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    @property
    def agent_state(self) -> Optional[Dict[str, Any]]:
        """获取智能体状态（反序列化）"""
        return self.agent_state_json

    @agent_state.setter
    def agent_state(self, value: Optional[Dict[str, Any]]) -> None:
        """设置智能体状态"""
        self.agent_state_json = value

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
            f"stage={self.current_stage.value}, "
            f"status={self.status.value})>"
        )

    def to_dict(self, exclude: Optional[list] = None) -> Dict[str, Any]:
        """将模型实例转换为字典

        Args:
            exclude: 要排除的字段列表

        Returns:
            包含模型数据的字典
        """
        result = {}
        exclude_set = set(exclude or [])

        # 获取实例的所有属性，排除私有属性和方法
        for key, value in vars(self).items():
            if key.startswith("_"):
                continue
            if key in exclude_set:
                continue
            # 处理特殊类型
            if isinstance(value, datetime):
                value = value.isoformat()
            result[key] = value

        return result

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """从字典更新模型属性

        Args:
            data: 包含更新数据的字典
        """
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
