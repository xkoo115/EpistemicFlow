"""
工作流状态仓库
提供对WorkflowState模型的CRUD操作和数据访问方法
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from models.workflow_state import WorkflowState, WorkflowStage, WorkflowStatus


class WorkflowStateRepository:
    """工作流状态仓库"""

    def __init__(self, session: AsyncSession):
        """初始化仓库

        Args:
            session: 数据库会话
        """
        self.session = session

    async def create(
        self,
        session_id: str,
        workflow_name: str,
        current_stage: WorkflowStage,
        status: WorkflowStatus = WorkflowStatus.PENDING,
        agent_state: Optional[Dict[str, Any]] = None,
        human_feedback: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowState:
        """创建工作流状态记录

        Args:
            session_id: 会话ID
            workflow_name: 工作流名称
            current_stage: 当前阶段
            status: 状态
            agent_state: 智能体状态
            human_feedback: 人工反馈
            metadata: 元数据

        Returns:
            WorkflowState: 创建的工作流状态记录
        """
        workflow_state = WorkflowState(
            session_id=session_id,
            workflow_name=workflow_name,
            current_stage=current_stage,
            status=status,
            agent_state_json=agent_state,
            human_feedback=human_feedback,
            metadata_json=metadata,
        )

        self.session.add(workflow_state)
        await self.session.flush()
        await self.session.refresh(workflow_state)

        return workflow_state

    async def get_by_id(self, state_id: int) -> Optional[WorkflowState]:
        """根据ID获取工作流状态

        Args:
            state_id: 状态ID

        Returns:
            Optional[WorkflowState]: 工作流状态记录，如果不存在则返回None
        """
        stmt = select(WorkflowState).where(WorkflowState.id == state_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_session_id(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[WorkflowState]:
        """根据会话ID获取工作流状态列表

        Args:
            session_id: 会话ID
            limit: 返回记录数限制
            offset: 偏移量

        Returns:
            List[WorkflowState]: 工作流状态记录列表
        """
        stmt = (
            select(WorkflowState)
            .where(WorkflowState.session_id == session_id)
            .order_by(WorkflowState.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_by_session_and_stage(
        self,
        session_id: str,
        stage: WorkflowStage,
    ) -> Optional[WorkflowState]:
        """获取指定会话和阶段的最新工作流状态

        Args:
            session_id: 会话ID
            stage: 阶段

        Returns:
            Optional[WorkflowState]: 最新的工作流状态记录
        """
        stmt = (
            select(WorkflowState)
            .where(
                and_(
                    WorkflowState.session_id == session_id,
                    WorkflowState.current_stage == stage,
                )
            )
            .order_by(WorkflowState.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        state_id: int,
        status: WorkflowStatus,
        error_message: Optional[str] = None,
    ) -> Optional[WorkflowState]:
        """更新工作流状态

        Args:
            state_id: 状态ID
            status: 新状态
            error_message: 错误信息

        Returns:
            Optional[WorkflowState]: 更新后的工作流状态记录
        """
        stmt = (
            update(WorkflowState)
            .where(WorkflowState.id == state_id)
            .values(
                status=status,
                error_message=error_message,
                updated_at=func.now(),
            )
            .returning(WorkflowState)
        )

        result = await self.session.execute(stmt)
        await self.session.flush()

        workflow_state = result.scalar_one_or_none()
        if workflow_state:
            await self.session.refresh(workflow_state)

        return workflow_state

    async def update_agent_state(
        self,
        state_id: int,
        agent_state: Dict[str, Any],
        merge: bool = True,
    ) -> Optional[WorkflowState]:
        """更新智能体状态

        Args:
            state_id: 状态ID
            agent_state: 新的智能体状态
            merge: 是否合并到现有状态（True）还是替换（False）

        Returns:
            Optional[WorkflowState]: 更新后的工作流状态记录
        """
        workflow_state = await self.get_by_id(state_id)
        if not workflow_state:
            return None

        if merge and workflow_state.agent_state_json:
            # 合并状态
            merged_state = {**workflow_state.agent_state_json, **agent_state}
            workflow_state.agent_state_json = merged_state
        else:
            # 替换状态
            workflow_state.agent_state_json = agent_state

        workflow_state.updated_at = func.now()
        await self.session.flush()
        await self.session.refresh(workflow_state)

        return workflow_state

    async def add_human_feedback(
        self,
        state_id: int,
        feedback: str,
    ) -> Optional[WorkflowState]:
        """添加人工反馈

        Args:
            state_id: 状态ID
            feedback: 反馈内容

        Returns:
            Optional[WorkflowState]: 更新后的工作流状态记录
        """
        workflow_state = await self.get_by_id(state_id)
        if not workflow_state:
            return None

        if workflow_state.human_feedback:
            # 追加反馈
            workflow_state.human_feedback = (
                f"{workflow_state.human_feedback}\n\n{feedback}"
            )
        else:
            workflow_state.human_feedback = feedback

        workflow_state.updated_at = func.now()
        await self.session.flush()
        await self.session.refresh(workflow_state)

        return workflow_state

    async def delete_by_id(self, state_id: int) -> bool:
        """根据ID删除工作流状态

        Args:
            state_id: 状态ID

        Returns:
            bool: 是否成功删除
        """
        stmt = delete(WorkflowState).where(WorkflowState.id == state_id)
        result = await self.session.execute(stmt)
        await self.session.flush()

        return result.rowcount > 0

    async def cleanup_old_states(
        self,
        days: int = 30,
        statuses: Optional[List[WorkflowStatus]] = None,
    ) -> int:
        """清理旧的工作流状态记录

        Args:
            days: 保留天数
            statuses: 要清理的状态列表，如果为None则清理所有状态

        Returns:
            int: 删除的记录数
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        conditions = [WorkflowState.created_at < cutoff_date]
        if statuses:
            conditions.append(WorkflowState.status.in_(statuses))

        stmt = delete(WorkflowState).where(and_(*conditions))
        result = await self.session.execute(stmt)
        await self.session.flush()

        return result.rowcount

    async def get_statistics(
        self,
        workflow_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """获取工作流统计信息

        Args:
            workflow_name: 工作流名称过滤
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            Dict[str, Any]: 统计信息
        """
        conditions = []

        if workflow_name:
            conditions.append(WorkflowState.workflow_name == workflow_name)

        if start_date:
            conditions.append(WorkflowState.created_at >= start_date)

        if end_date:
            conditions.append(WorkflowState.created_at <= end_date)

        where_clause = and_(*conditions) if conditions else True

        # 查询总数
        total_stmt = select(func.count(WorkflowState.id)).where(where_clause)
        total_result = await self.session.execute(total_stmt)
        total = total_result.scalar() or 0

        # 按状态统计
        status_stmt = (
            select(WorkflowState.status, func.count(WorkflowState.id))
            .where(where_clause)
            .group_by(WorkflowState.status)
        )
        status_result = await self.session.execute(status_stmt)
        status_stats = {row[0]: row[1] for row in status_result}

        # 按阶段统计
        stage_stmt = (
            select(WorkflowState.current_stage, func.count(WorkflowState.id))
            .where(where_clause)
            .group_by(WorkflowState.current_stage)
        )
        stage_result = await self.session.execute(stage_stmt)
        stage_stats = {row[0]: row[1] for row in stage_result}

        # 平均执行时间（仅计算已完成的工作流）
        duration_stmt = select(
            func.avg(
                func.extract(
                    "epoch", WorkflowState.updated_at - WorkflowState.created_at
                )
            )
        ).where(
            and_(
                where_clause,
                WorkflowState.status == WorkflowStatus.COMPLETED,
            )
        )
        duration_result = await self.session.execute(duration_stmt)
        avg_duration = duration_result.scalar() or 0

        return {
            "total": total,
            "status_stats": status_stats,
            "stage_stats": stage_stats,
            "avg_duration_seconds": avg_duration,
        }
