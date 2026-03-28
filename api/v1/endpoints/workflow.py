"""
工作流API端点
提供工作流状态管理的RESTful接口
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database.session import get_db_session
from database.repositories.workflow_state_repository import WorkflowStateRepository
from models.workflow_state import WorkflowStage, WorkflowStatus


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

        return WorkflowStateResponse.from_orm(workflow_state)
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
        return WorkflowStateResponse.from_orm(updated_state)

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
