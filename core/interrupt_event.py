"""
中断事件模块

本模块实现 HITL（Human-in-the-Loop）的中断事件机制，允许工作流在关键节点
主动挂起并等待人工审核。

核心概念：
- InterruptEvent: 中断事件，触发工作流挂起
- InterruptReason: 中断原因枚举
- InterruptHandler: 中断处理器，负责捕获中断并保存状态

设计原则：
- 非侵入性：智能体通过抛出异常触发中断，无需修改核心执行逻辑
- 可恢复性：中断后必须能够从断点精确恢复执行
- 信息完整性：中断事件必须包含足够的上下文信息供人工决策
"""

from typing import Any, Dict, Optional
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from agent_framework import AgentSession


class InterruptReason(str, Enum):
    """
    中断原因枚举

    定义工作流可能挂起的所有原因
    """

    # 科研流程相关
    RESEARCH_PLAN_REVIEW = "research_plan_review"  # 科研计划需要审核
    LITERATURE_SELECTION = "literature_selection"  # 文献选择需要确认
    METHODOLOGY_APPROVAL = "methodology_approval"  # 方法设计需要批准
    DATA_VALIDATION = "data_validation"  # 数据收集需要验证
    RESULT_INTERPRETATION = "result_interpretation"  # 结果解释需要讨论
    CONCLUSION_REVIEW = "conclusion_review"  # 结论需要审核

    # 质量控制相关
    QUALITY_CHECK = "quality_check"  # 质量检查未通过
    ERROR_RECOVERY = "error_recovery"  # 错误恢复需要人工介入
    AMBIGUITY_RESOLUTION = "ambiguity_resolution"  # 歧义需要澄清

    # 资源管理相关
    RESOURCE_ALLOCATION = "resource_allocation"  # 资源分配需要确认
    BUDGET_APPROVAL = "budget_approval"  # 预算需要批准

    # 自定义
    CUSTOM = "custom"  # 自定义原因


class InterruptPriority(str, Enum):
    """
    中断优先级枚举

    用于排序和调度多个中断事件
    """

    LOW = "low"  # 低优先级
    NORMAL = "normal"  # 正常优先级
    HIGH = "high"  # 高优先级
    CRITICAL = "critical"  # 关键优先级（必须立即处理）


@dataclass
class InterruptEvent(Exception):
    """
    中断事件

    当智能体需要人工介入时抛出此异常。FastAPI 捕获后会调用 StateManager
    保存状态并返回等待审核的响应。

    继承自 Exception，因此可以通过 try-except 捕获。

    Attributes:
        reason: 中断原因
        message: 人类可读的描述信息
        session_id: 会话 ID
        checkpoint_id: 检查点 ID（由 StateManager 填充）
        priority: 优先级
        context: 上下文信息（供人工决策参考）
        suggested_actions: 建议的操作列表
        metadata: 额外的元数据
        created_at: 创建时间
    """

    reason: InterruptReason
    message: str
    session_id: str
    checkpoint_id: Optional[int] = None
    priority: InterruptPriority = InterruptPriority.NORMAL
    context: Dict[str, Any] = field(default_factory=dict)
    suggested_actions: list[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __str__(self) -> str:
        """字符串表示"""
        return (
            f"InterruptEvent(reason={self.reason.value}, "
            f"session_id={self.session_id}, "
            f"message={self.message})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典（用于 JSON 序列化）

        Returns:
            包含所有属性的字典
        """
        return {
            "reason": self.reason.value,
            "message": self.message,
            "session_id": self.session_id,
            "checkpoint_id": self.checkpoint_id,
            "priority": self.priority.value,
            "context": self.context,
            "suggested_actions": self.suggested_actions,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InterruptEvent":
        """
        从字典创建实例

        Args:
            data: 包含事件数据的字典

        Returns:
            InterruptEvent 实例
        """
        return cls(
            reason=InterruptReason(data["reason"]),
            message=data["message"],
            session_id=data["session_id"],
            checkpoint_id=data.get("checkpoint_id"),
            priority=InterruptPriority(data.get("priority", "normal")),
            context=data.get("context", {}),
            suggested_actions=data.get("suggested_actions", []),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


class InterruptHandler:
    """
    中断处理器

    负责捕获中断事件并执行相应的处理逻辑。

    使用场景：
    1. FastAPI 路由中捕获 InterruptEvent
    2. 调用 StateManager 保存当前状态
    3. 返回等待人工审核的响应给前端
    """

    @staticmethod
    def create_research_plan_interrupt(
        session_id: str,
        research_plan: Dict[str, Any],
        message: str = "科研计划已生成，请审核并确认",
    ) -> InterruptEvent:
        """
        创建科研计划审核中断

        Args:
            session_id: 会话 ID
            research_plan: 科研计划数据
            message: 描述信息

        Returns:
            InterruptEvent 实例
        """
        return InterruptEvent(
            reason=InterruptReason.RESEARCH_PLAN_REVIEW,
            message=message,
            session_id=session_id,
            priority=InterruptPriority.HIGH,
            context={
                "research_plan": research_plan,
                "plan_summary": {
                    "title": research_plan.get("title"),
                    "objectives": research_plan.get("objectives"),
                    "methodology": research_plan.get("methodology"),
                },
            },
            suggested_actions=[
                "批准计划并继续执行",
                "修改计划目标",
                "调整方法论",
                "拒绝计划并重新生成",
            ],
        )

    @staticmethod
    def create_literature_selection_interrupt(
        session_id: str,
        papers: list[Dict[str, Any]],
        message: str = "文献检索完成，请选择相关文献",
    ) -> InterruptEvent:
        """
        创建文献选择中断

        Args:
            session_id: 会话 ID
            papers: 检索到的文献列表
            message: 描述信息

        Returns:
            InterruptEvent 实例
        """
        return InterruptEvent(
            reason=InterruptReason.LITERATURE_SELECTION,
            message=message,
            session_id=session_id,
            priority=InterruptPriority.NORMAL,
            context={
                "total_papers": len(papers),
                "papers": papers[:10],  # 只显示前 10 篇
                "papers_summary": [
                    {
                        "title": p.get("title"),
                        "authors": p.get("authors"),
                        "year": p.get("year"),
                    }
                    for p in papers[:10]
                ],
            },
            suggested_actions=[
                "选择所有文献",
                "手动选择相关文献",
                "调整检索关键词",
                "扩大检索范围",
            ],
        )

    @staticmethod
    def create_methodology_approval_interrupt(
        session_id: str,
        methodology: Dict[str, Any],
        message: str = "研究方法已设计，请审批",
    ) -> InterruptEvent:
        """
        创建方法审批中断

        Args:
            session_id: 会话 ID
            methodology: 方法设计数据
            message: 描述信息

        Returns:
            InterruptEvent 实例
        """
        return InterruptEvent(
            reason=InterruptReason.METHODOLOGY_APPROVAL,
            message=message,
            session_id=session_id,
            priority=InterruptPriority.HIGH,
            context={
                "methodology": methodology,
                "methodology_summary": {
                    "approach": methodology.get("approach"),
                    "data_collection": methodology.get("data_collection"),
                    "analysis_methods": methodology.get("analysis_methods"),
                },
            },
            suggested_actions=[
                "批准方法设计",
                "修改数据收集方式",
                "调整分析方法",
                "重新设计方法",
            ],
        )

    @staticmethod
    def create_error_recovery_interrupt(
        session_id: str,
        error_message: str,
        error_context: Dict[str, Any],
        message: str = "执行过程中发生错误，需要人工介入",
    ) -> InterruptEvent:
        """
        创建错误恢复中断

        Args:
            session_id: 会话 ID
            error_message: 错误信息
            error_context: 错误上下文
            message: 描述信息

        Returns:
            InterruptEvent 实例
        """
        return InterruptEvent(
            reason=InterruptReason.ERROR_RECOVERY,
            message=message,
            session_id=session_id,
            priority=InterruptPriority.CRITICAL,
            context={
                "error_message": error_message,
                "error_context": error_context,
            },
            suggested_actions=[
                "重试当前操作",
                "跳过当前步骤",
                "回滚到上一个检查点",
                "终止工作流",
            ],
        )

    @staticmethod
    def create_quality_check_interrupt(
        session_id: str,
        quality_report: Dict[str, Any],
        message: str = "质量检查未通过，需要人工审核",
    ) -> InterruptEvent:
        """
        创建质量检查中断

        Args:
            session_id: 会话 ID
            quality_report: 质量检查报告
            message: 描述信息

        Returns:
            InterruptEvent 实例
        """
        return InterruptEvent(
            reason=InterruptReason.QUALITY_CHECK,
            message=message,
            session_id=session_id,
            priority=InterruptPriority.HIGH,
            context={
                "quality_report": quality_report,
                "failed_checks": quality_report.get("failed_checks", []),
                "warnings": quality_report.get("warnings", []),
            },
            suggested_actions=[
                "查看详细报告",
                "修复问题并重新检查",
                "忽略警告继续执行",
                "调整质量标准",
            ],
        )


def raise_interrupt(
    reason: InterruptReason,
    message: str,
    session_id: str,
    **kwargs: Any,
) -> None:
    """
    触发中断的便捷函数

    在智能体代码中调用此函数来触发 HITL 中断。

    Args:
        reason: 中断原因
        message: 描述信息
        session_id: 会话 ID
        **kwargs: 其他参数（传递给 InterruptEvent）

    Raises:
        InterruptEvent: 总是抛出中断事件

    Example:
        >>> # 在科研计划生成后触发中断
        >>> raise_interrupt(
        ...     reason=InterruptReason.RESEARCH_PLAN_REVIEW,
        ...     message="科研计划已生成，请审核",
        ...     session_id=session.session_id,
        ...     context={"research_plan": plan},
        ... )
    """
    raise InterruptEvent(
        reason=reason,
        message=message,
        session_id=session_id,
        **kwargs,
    )
