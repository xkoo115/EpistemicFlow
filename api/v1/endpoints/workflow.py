"""
工作流API端点
提供工作流状态管理的RESTful接口，包括：
- 基础 CRUD 操作
- HITL 挂起与恢复机制
- Saga 回滚与分叉操作
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
import uuid

from database.session import get_db_session
from database.repositories.workflow_state_repository import WorkflowStateRepository
from models.workflow_state import WorkflowStage, WorkflowStatus
from core.state_manager import StateManager, StateSerializationError, StateDeserializationError
from core.interrupt_event import InterruptEvent, InterruptReason, InterruptPriority


# Pydantic模型定义
class WorkflowStateCreate(BaseModel):
    """创建工作流状态请求模型"""

    session_id: str = Field(..., min_length=1, max_length=64, description="会话ID")
    workflow_name: str = Field(
        ..., min_length=1, max_length=128, description="工作流名称"
    )
    current_stage: WorkflowStage = Field(..., description="当前阶段")
    status: WorkflowStatus = Field(default=WorkflowStatus.PENDING, description="状态")
    agent_state: Optional[Dict[str, Any]] = Field(None, description="智能体状态")
    human_feedback: Optional[str] = Field(None, description="人工反馈")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class WorkflowStateUpdate(BaseModel):
    """更新工作流状态请求模型"""

    status: Optional[WorkflowStatus] = Field(None, description="状态")
    agent_state: Optional[Dict[str, Any]] = Field(None, description="智能体状态")
    human_feedback: Optional[str] = Field(None, description="人工反馈")
    error_message: Optional[str] = Field(None, description="错误信息")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class WorkflowStateResponse(BaseModel):
    """工作流状态响应模型"""

    id: int
    session_id: str
    workflow_name: str
    current_stage: WorkflowStage
    status: WorkflowStatus
    agent_state: Optional[Dict[str, Any]]
    human_feedback: Optional[str]
    error_message: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class WorkflowStateSummary(BaseModel):
    """工作流状态摘要模型"""

    id: int
    session_id: str
    workflow_name: str
    current_stage: WorkflowStage
    status: WorkflowStatus
    created_at: str
    updated_at: str
    has_agent_state: bool
    has_human_feedback: bool
    has_error: bool


class WorkflowStatistics(BaseModel):
    """工作流统计模型"""

    total: int
    status_stats: Dict[str, int]
    stage_stats: Dict[str, int]
    avg_duration_seconds: float


# 创建路由器
router = APIRouter()


def workflow_state_to_response(workflow_state) -> WorkflowStateResponse:
    """将工作流状态模型转换为响应模型

    Args:
        workflow_state: 工作流状态数据库模型

    Returns:
        WorkflowStateResponse: API响应模型
    """
    return WorkflowStateResponse(
        id=workflow_state.id,
        session_id=workflow_state.session_id,
        workflow_name=workflow_state.workflow_name,
        current_stage=workflow_state.current_stage,
        status=workflow_state.status,
        agent_state=workflow_state.agent_state_json,
        human_feedback=workflow_state.human_feedback,
        error_message=workflow_state.error_message,
        metadata=workflow_state.metadata_json if workflow_state.metadata_json else {},
        created_at=workflow_state.created_at.isoformat() if workflow_state.created_at else "",
        updated_at=workflow_state.updated_at.isoformat() if workflow_state.updated_at else "",
    )


@router.post("/", response_model=WorkflowStateResponse)
async def create_workflow_state(
    workflow_data: WorkflowStateCreate,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowStateResponse:
    """创建工作流状态记录

    Args:
        workflow_data: 工作流数据
        db: 数据库会话

    Returns:
        WorkflowStateResponse: 创建的工作流状态
    """
    repository = WorkflowStateRepository(db)

    try:
        workflow_state = await repository.create(
            session_id=workflow_data.session_id,
            workflow_name=workflow_data.workflow_name,
            current_stage=workflow_data.current_stage,
            status=workflow_data.status,
            agent_state=workflow_data.agent_state,
            human_feedback=workflow_data.human_feedback,
            metadata=workflow_data.metadata,
        )

        return workflow_state_to_response(workflow_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建工作流状态失败: {str(e)}")


@router.get("/{state_id}", response_model=WorkflowStateResponse)
async def get_workflow_state(
    state_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowStateResponse:
    """获取工作流状态记录

    Args:
        state_id: 状态ID
        db: 数据库会话

    Returns:
        WorkflowStateResponse: 工作流状态
    """
    repository = WorkflowStateRepository(db)

    workflow_state = await repository.get_by_id(state_id)
    if not workflow_state:
        raise HTTPException(status_code=404, detail="工作流状态不存在")

    return WorkflowStateResponse.from_orm(workflow_state)


@router.get("/session/{session_id}", response_model=List[WorkflowStateSummary])
async def get_workflow_states_by_session(
    session_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> List[WorkflowStateSummary]:
    """根据会话ID获取工作流状态列表

    Args:
        session_id: 会话ID
        limit: 返回记录数限制
        offset: 偏移量
        db: 数据库会话

    Returns:
        List[WorkflowStateSummary]: 工作流状态摘要列表
    """
    repository = WorkflowStateRepository(db)

    workflow_states = await repository.get_by_session_id(session_id, limit, offset)

    return [
        WorkflowStateSummary(**state.to_summary_dict()) for state in workflow_states
    ]


@router.put("/{state_id}", response_model=WorkflowStateResponse)
async def update_workflow_state(
    state_id: int,
    update_data: WorkflowStateUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowStateResponse:
    """更新工作流状态记录

    Args:
        state_id: 状态ID
        update_data: 更新数据
        db: 数据库会话

    Returns:
        WorkflowStateResponse: 更新后的工作流状态
    """
    repository = WorkflowStateRepository(db)

    # 检查记录是否存在
    workflow_state = await repository.get_by_id(state_id)
    if not workflow_state:
        raise HTTPException(status_code=404, detail="工作流状态不存在")

    try:
        # 更新状态
        if update_data.status:
            updated_state = await repository.update_status(
                state_id,
                update_data.status,
                update_data.error_message,
            )
            if not updated_state:
                raise HTTPException(status_code=500, detail="更新状态失败")

        # 更新智能体状态
        if update_data.agent_state is not None:
            updated_state = await repository.update_agent_state(
                state_id,
                update_data.agent_state,
                merge=True,
            )
            if not updated_state:
                raise HTTPException(status_code=500, detail="更新智能体状态失败")

        # 添加人工反馈
        if update_data.human_feedback:
            updated_state = await repository.add_human_feedback(
                state_id,
                update_data.human_feedback,
            )
            if not updated_state:
                raise HTTPException(status_code=500, detail="添加人工反馈失败")

        # 获取更新后的记录
        updated_state = await repository.get_by_id(state_id)
        return workflow_state_to_response(updated_state)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新工作流状态失败: {str(e)}")


@router.delete("/{state_id}")
async def delete_workflow_state(
    state_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """删除工作流状态记录

    Args:
        state_id: 状态ID
        db: 数据库会话

    Returns:
        Dict[str, Any]: 删除结果
    """
    repository = WorkflowStateRepository(db)

    deleted = await repository.delete_by_id(state_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="工作流状态不存在")

    return {"message": "工作流状态删除成功", "state_id": state_id}


@router.get(
    "/session/{session_id}/stage/{stage}/latest", response_model=WorkflowStateResponse
)
async def get_latest_workflow_state_by_stage(
    session_id: str,
    stage: WorkflowStage,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowStateResponse:
    """获取指定会话和阶段的最新工作流状态

    Args:
        session_id: 会话ID
        stage: 阶段
        db: 数据库会话

    Returns:
        WorkflowStateResponse: 最新工作流状态
    """
    repository = WorkflowStateRepository(db)

    workflow_state = await repository.get_latest_by_session_and_stage(session_id, stage)
    if not workflow_state:
        raise HTTPException(status_code=404, detail="未找到指定阶段的工作流状态")

    return WorkflowStateResponse.from_orm(workflow_state)


@router.get("/statistics/summary", response_model=WorkflowStatistics)
async def get_workflow_statistics(
    workflow_name: Optional[str] = Query(None, description="工作流名称过滤"),
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowStatistics:
    """获取工作流统计信息

    Args:
        workflow_name: 工作流名称
        days: 统计天数
        db: 数据库会话

    Returns:
        WorkflowStatistics: 工作流统计信息
    """
    repository = WorkflowStateRepository(db)

    from datetime import datetime, timedelta

    start_date = datetime.utcnow() - timedelta(days=days)

    stats = await repository.get_statistics(
        workflow_name=workflow_name,
        start_date=start_date,
    )

    return WorkflowStatistics(**stats)


@router.post("/{state_id}/feedback")
async def add_feedback_to_workflow_state(
    state_id: int,
    feedback: str = Body(..., embed=True, min_length=1),
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """为工作流状态添加反馈

    Args:
        state_id: 状态ID
        feedback: 反馈内容
        db: 数据库会话

    Returns:
        Dict[str, Any]: 操作结果
    """
    repository = WorkflowStateRepository(db)

    updated_state = await repository.add_human_feedback(state_id, feedback)
    if not updated_state:
        raise HTTPException(status_code=404, detail="工作流状态不存在")

    return {
        "message": "反馈添加成功",
        "state_id": state_id,
        "has_feedback": bool(updated_state.human_feedback),
    }


@router.post("/cleanup/old")
async def cleanup_old_workflow_states(
    days: int = Body(30, embed=True, ge=1, le=365),
    statuses: Optional[List[WorkflowStatus]] = Body(None, embed=True),
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """清理旧的工作流状态记录

    Args:
        days: 保留天数
        statuses: 要清理的状态列表
        db: 数据库会话

    Returns:
        Dict[str, Any]: 清理结果
    """
    repository = WorkflowStateRepository(db)

    deleted_count = await repository.cleanup_old_states(days, statuses)

    return {
        "message": "清理完成",
        "deleted_count": deleted_count,
        "days": days,
        "statuses": statuses,
    }


# ============================================================================
# HITL 挂起与恢复接口
# ============================================================================


class InterruptEventResponse(BaseModel):
    """中断事件响应模型"""

    reason: str
    message: str
    session_id: str
    checkpoint_id: int
    priority: str
    context: Dict[str, Any]
    suggested_actions: List[str]
    created_at: str


class HumanFeedbackRequest(BaseModel):
    """人类反馈请求模型"""

    feedback: str = Field(..., min_length=1, description="反馈内容")
    action: Optional[str] = Field(None, description="选择的操作")
    additional_data: Optional[Dict[str, Any]] = Field(
        None, description="额外的结构化数据"
    )


class ResumeResponse(BaseModel):
    """恢复执行响应模型"""

    checkpoint_id: int
    session_id: str
    status: WorkflowStatus
    message: str


@router.post("/{state_id}/interrupt", response_model=InterruptEventResponse)
async def interrupt_workflow(
    state_id: int,
    interrupt_data: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db_session),
) -> InterruptEventResponse:
    """
    触发工作流中断

    当智能体执行到关键节点时，主动触发中断并保存状态。

    Args:
        state_id: 工作流状态 ID
        interrupt_data: 中断事件数据（包含 reason, message, context 等）
        db: 数据库会话

    Returns:
        InterruptEventResponse: 中断事件响应

    使用场景：
        - 科研计划生成完毕，等待人工审核
        - 文献检索完成，需要选择相关文献
        - 方法设计完成，需要审批
    """
    repository = WorkflowStateRepository(db)
    state_manager = StateManager(db)

    # 获取当前工作流状态
    workflow_state = await repository.get_by_id(state_id)
    if not workflow_state:
        raise HTTPException(status_code=404, detail="工作流状态不存在")

    try:
        # 创建中断事件
        interrupt_event = InterruptEvent.from_dict(
            {
                "session_id": workflow_state.session_id,
                **interrupt_data,
            }
        )

        # 更新工作流状态为暂停
        updated_state = await repository.update_status(
            state_id, WorkflowStatus.PAUSED, interrupt_event.message
        )

        if not updated_state:
            raise HTTPException(status_code=500, detail="更新状态失败")

        # 返回中断事件响应
        return InterruptEventResponse(
            reason=interrupt_event.reason.value,
            message=interrupt_event.message,
            session_id=interrupt_event.session_id,
            checkpoint_id=state_id,
            priority=interrupt_event.priority.value,
            context=interrupt_event.context,
            suggested_actions=interrupt_event.suggested_actions,
            created_at=interrupt_event.created_at.isoformat(),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"触发中断失败: {str(e)}"
        )


@router.post(
    "/session/{session_id}/resume", response_model=ResumeResponse
)
async def resume_workflow(
    session_id: str,
    feedback_data: HumanFeedbackRequest,
    checkpoint_id: Optional[int] = Query(None, description="检查点ID（可选）"),
    db: AsyncSession = Depends(get_db_session),
) -> ResumeResponse:
    """
    恢复工作流执行

    接收人类反馈，唤醒状态机并继续执行。

    Args:
        session_id: 会话 ID
        feedback_data: 人类反馈数据
        checkpoint_id: 可选的检查点 ID（如果不提供，使用最新的检查点）
        db: 数据库会话

    Returns:
        ResumeResponse: 恢复执行响应

    技术细节：
        1. 从数据库加载检查点状态
        2. 将人类反馈注入到 Session 状态中
        3. 更新工作流状态为 RUNNING
        4. 返回恢复确认（实际执行由后台任务处理）
    """
    repository = WorkflowStateRepository(db)
    state_manager = StateManager(db)

    try:
        # 获取检查点
        if checkpoint_id:
            checkpoint = await repository.get_by_id(checkpoint_id)
        else:
            checkpoint = await state_manager.get_latest_checkpoint(session_id)

        if not checkpoint:
            raise HTTPException(status_code=404, detail="检查点不存在")

        # 添加人类反馈
        await repository.add_human_feedback(checkpoint.id, feedback_data.feedback)

        # 更新状态为 RUNNING
        updated_state = await repository.update_status(
            checkpoint.id, WorkflowStatus.RUNNING
        )

        if not updated_state:
            raise HTTPException(status_code=500, detail="更新状态失败")

        # 在实际实现中，这里应该触发后台任务继续执行工作流
        # 例如：await workflow_executor.resume(checkpoint.id, feedback_data)

        return ResumeResponse(
            checkpoint_id=checkpoint.id,
            session_id=session_id,
            status=WorkflowStatus.RUNNING,
            message="工作流已恢复，正在继续执行",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"恢复工作流失败: {str(e)}"
        )


# ============================================================================
# Saga 回滚与分叉接口
# ============================================================================


class RollbackRequest(BaseModel):
    """回滚请求模型"""

    checkpoint_id: int = Field(..., description="目标检查点ID")
    reason: str = Field(..., min_length=1, description="回滚原因")
    human_instruction: Optional[str] = Field(
        None, description="人类修改指令（如'增加对比实验'）"
    )
    additional_state: Optional[Dict[str, Any]] = Field(
        None, description="额外的状态更新"
    )


class RollbackResponse(BaseModel):
    """回滚响应模型"""

    original_checkpoint_id: int
    new_checkpoint_id: int
    new_session_id: str
    workflow_name: str
    current_stage: WorkflowStage
    message: str


@router.post(
    "/session/{session_id}/rollback", response_model=RollbackResponse
)
async def rollback_workflow(
    session_id: str,
    rollback_data: RollbackRequest,
    db: AsyncSession = Depends(get_db_session),
) -> RollbackResponse:
    """
    回滚工作流到历史检查点

    从历史节点提取状态重建 Session，并分叉出新的执行路径。

    Args:
        session_id: 当前会话 ID
        rollback_data: 回滚请求数据
        db: 数据库会话

    Returns:
        RollbackResponse: 回滚响应

    Saga 模式核心操作：
        1. 从历史检查点恢复状态
        2. 注入人类修改指令
        3. 创建新的检查点（分叉）
        4. 返回新检查点信息

    使用场景：
        - 用户要求修改历史决策
        - 系统检测到错误需要回滚
        - 探索不同的决策分支
    """
    repository = WorkflowStateRepository(db)
    state_manager = StateManager(db)

    try:
        # 获取原始检查点
        original_checkpoint = await repository.get_by_id(
            rollback_data.checkpoint_id
        )
        if not original_checkpoint:
            raise HTTPException(
                status_code=404,
                detail=f"检查点不存在: {rollback_data.checkpoint_id}",
            )

        # 生成新的会话 ID（分叉）
        new_session_id = str(uuid.uuid4())

        # 从检查点分叉
        new_checkpoint = await state_manager.fork_from_checkpoint(
            checkpoint_id=rollback_data.checkpoint_id,
            new_session_id=new_session_id,
            workflow_name=original_checkpoint.workflow_name,
            new_stage=original_checkpoint.current_stage,
            human_feedback=rollback_data.human_instruction,
            additional_state=rollback_data.additional_state,
        )

        # 更新新检查点的状态为 RUNNING
        await repository.update_status(
            new_checkpoint.id, WorkflowStatus.RUNNING
        )

        return RollbackResponse(
            original_checkpoint_id=rollback_data.checkpoint_id,
            new_checkpoint_id=new_checkpoint.id,
            new_session_id=new_session_id,
            workflow_name=new_checkpoint.workflow_name,
            current_stage=new_checkpoint.current_stage,
            message=f"已从检查点 {rollback_data.checkpoint_id} 回滚并创建新的执行路径",
        )

    except HTTPException:
        raise
    except (StateSerializationError, StateDeserializationError) as e:
        raise HTTPException(status_code=500, detail=f"状态操作失败: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"回滚工作流失败: {str(e)}"
        )


class CheckpointHistoryResponse(BaseModel):
    """检查点历史响应模型"""

    session_id: str
    checkpoints: List[WorkflowStateSummary]
    total_count: int


@router.get(
    "/session/{session_id}/history",
    response_model=CheckpointHistoryResponse,
)
async def get_checkpoint_history(
    session_id: str,
    limit: int = Query(50, ge=1, le=500, description="返回记录数限制"),
    db: AsyncSession = Depends(get_db_session),
) -> CheckpointHistoryResponse:
    """
    获取会话的检查点历史

    查询指定会话的所有检查点，用于回滚决策。

    Args:
        session_id: 会话 ID
        limit: 返回记录数限制
        db: 数据库会话

    Returns:
        CheckpointHistoryResponse: 检查点历史响应
    """
    repository = WorkflowStateRepository(db)
    state_manager = StateManager(db)

    try:
        # 获取检查点历史
        checkpoints = await state_manager.get_session_history(
            session_id, limit=limit
        )

        # 转换为摘要格式
        checkpoint_summaries = [
            WorkflowStateSummary(**cp.to_summary_dict()) for cp in checkpoints
        ]

        return CheckpointHistoryResponse(
            session_id=session_id,
            checkpoints=checkpoint_summaries,
            total_count=len(checkpoint_summaries),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"获取检查点历史失败: {str(e)}"
        )


class StateValidationResponse(BaseModel):
    """状态验证响应模型"""

    checkpoint_id: int
    is_valid: bool
    state_hash: Optional[str]
    message: str


@router.get(
    "/{state_id}/validate", response_model=StateValidationResponse
)
async def validate_checkpoint_state(
    state_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> StateValidationResponse:
    """
    验证检查点状态的完整性

    检查状态哈希是否匹配，确保数据未损坏。

    Args:
        state_id: 检查点 ID
        db: 数据库会话

    Returns:
        StateValidationResponse: 验证结果
    """
    repository = WorkflowStateRepository(db)

    try:
        # 获取检查点
        checkpoint = await repository.get_by_id(state_id)
        if not checkpoint:
            raise HTTPException(status_code=404, detail="检查点不存在")

        # 检查状态是否存在
        if not checkpoint.agent_state_json:
            return StateValidationResponse(
                checkpoint_id=state_id,
                is_valid=False,
                state_hash=None,
                message="检查点状态为空",
            )

        # 验证状态哈希
        metadata = checkpoint.metadata_json or {}
        expected_hash = metadata.get("state_hash")

        if not expected_hash:
            return StateValidationResponse(
                checkpoint_id=state_id,
                is_valid=True,
                state_hash=None,
                message="检查点未记录状态哈希，无法验证",
            )

        # 计算实际哈希
        import hashlib
        import json

        state_json = json.dumps(
            checkpoint.agent_state_json, sort_keys=True, ensure_ascii=False
        )
        actual_hash = hashlib.sha256(state_json.encode("utf-8")).hexdigest()

        is_valid = actual_hash == expected_hash

        return StateValidationResponse(
            checkpoint_id=state_id,
            is_valid=is_valid,
            state_hash=actual_hash,
            message="状态验证通过" if is_valid else "状态哈希不匹配，数据可能已损坏",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"验证状态失败: {str(e)}"
        )
