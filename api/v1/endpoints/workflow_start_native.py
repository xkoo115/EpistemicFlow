"""
工作流启动 API 端点（原生架构版本）

本模块使用重构后的原生 agent_framework 架构，
替代原有的手动业务逻辑控制。

核心变更：
- 使用 EpistemicWorkflow 统一入口
- 使用原生事件流替代手动 SSE 组装
- 使用 SagaStateManager 管理状态
"""

from typing import Optional, Dict, Any, List, Literal
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
import uuid
import asyncio

from database.session import get_db_session
from database.repositories.workflow_state_repository import WorkflowStateRepository
from models.workflow_state import WorkflowStage, WorkflowStatus
from core.state_manager import StateManager


# ============================================================================
# 请求/响应模型定义
# ============================================================================

PaperTypeLiteral = Literal["research_paper", "survey_paper"]


class WorkflowStartRequest(BaseModel):
    """工作流启动请求模型"""
    research_idea: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="研究方向/假设描述",
    )
    paper_type: PaperTypeLiteral = Field(
        default="research_paper",
        description="论文类型",
    )
    target_journal: Optional[str] = Field(
        default=None,
        description="目标期刊",
    )
    llm_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="模型配置",
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="关键词列表",
    )


class WorkflowStartResponse(BaseModel):
    """工作流启动响应模型"""
    session_id: str = Field(description="会话 ID")
    workflow_id: int = Field(description="工作流状态记录 ID")
    status: WorkflowStatus = Field(description="初始状态")
    current_stage: WorkflowStage = Field(description="当前阶段")
    message: str = Field(description="启动消息")


class LaTeXExportResponse(BaseModel):
    """LaTeX 导出响应模型"""
    session_id: str = Field(description="会话 ID")
    filename: str = Field(description="文件名")
    content: str = Field(description="LaTeX 源码")
    metadata: Dict[str, Any] = Field(description="元数据")


class WorkflowResumeRequest(BaseModel):
    """工作流恢复请求模型"""
    checkpoint_id: str = Field(description="检查点 ID")
    human_feedback: Optional[Dict[str, Any]] = Field(
        default=None,
        description="人类反馈",
    )


# ============================================================================
# 路由器定义
# ============================================================================

router = APIRouter()


# ============================================================================
# 工作流启动接口（原生架构）
# ============================================================================

@router.post("/start", response_model=WorkflowStartResponse)
async def start_workflow(
    request: WorkflowStartRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowStartResponse:
    """
    启动新的科研工作流（原生架构）
    
    使用重构后的 EpistemicWorkflow，完全基于 agent_framework 原生编排。
    
    原生特性：
    - 工作流由 WorkflowBuilder 构建
    - 事件流由 WorkflowEvent 驱动
    - 状态由 CheckpointStorage 管理
    
    Args:
        request: 启动请求
        background_tasks: 后台任务
        db: 数据库会话
    
    Returns:
        WorkflowStartResponse: 启动响应
    """
    # 生成唯一的 session_id
    session_id = str(uuid.uuid4())
    
    # 初始化状态管理器和仓库
    repository = WorkflowStateRepository(db)
    state_manager = StateManager(db)
    
    try:
        # 构建初始智能体状态
        initial_agent_state = {
            "user_input": {
                "research_idea": request.research_idea,
                "paper_type": request.paper_type,
                "target_journal": request.target_journal,
                "keywords": request.keywords or [],
            },
            "model_config": request.llm_config or {},
            "workflow_metadata": {
                "started_at": asyncio.get_event_loop().time(),
                "source": "api_start_native",
                "architecture": "agent_framework_native",
            },
        }
        
        # 创建初始工作流状态（Saga 起点）
        workflow_state = await repository.create(
            session_id=session_id,
            workflow_name="epistemicflow_native",
            current_stage=WorkflowStage.INITIALIZATION,
            status=WorkflowStatus.PENDING,
            agent_state=initial_agent_state,
            metadata={
                "paper_type": request.paper_type,
                "idea_length": len(request.research_idea),
                "architecture": "native",
            },
        )
        
        # 异步运行原生工作流
        async def _safe_run_native_workflow():
            """安全包装函数"""
            try:
                await _run_native_workflow(
                    session_id=session_id,
                    workflow_id=workflow_state.id,
                    research_idea=request.research_idea,
                    paper_type=request.paper_type,
                    target_journal=request.target_journal,
                    model_config=request.llm_config,
                )
            except Exception as e:
                print(f"[ERROR] 原生工作流执行失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 启动后台任务
        asyncio.ensure_future(_safe_run_native_workflow())
        
        return WorkflowStartResponse(
            session_id=session_id,
            workflow_id=workflow_state.id,
            status=WorkflowStatus.PENDING,
            current_stage=WorkflowStage.INITIALIZATION,
            message="工作流已启动（原生架构），正在执行...",
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"启动工作流失败: {str(e)}",
        )


async def _run_native_workflow(
    session_id: str,
    workflow_id: int,
    research_idea: str,
    paper_type: str,
    target_journal: Optional[str] = None,
    model_config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    运行原生工作流（后台任务）
    
    使用 EpistemicWorkflow 统一入口，完全基于 agent_framework 原生编排。
    
    原生特性说明：
    - EpistemicWorkflow 内部使用 WorkflowBuilder 构建拓扑
    - 所有事件通过 WorkflowEvent 实时产生
    - 事件流通过 register_workflow_event_stream 注册
    - SSE 桥接层直接消费原生事件流
    
    Args:
        session_id: 会话 ID
        workflow_id: 工作流状态 ID
        research_idea: 科研 Idea
        paper_type: 论文类型
        target_journal: 目标期刊
        model_config: 模型配置
    """
    print(f"\n[DEBUG] _run_native_workflow 开始执行")
    print(f"[DEBUG] session_id: {session_id}")
    print(f"[DEBUG] workflow_id: {workflow_id}")
    
    # 重新加载配置
    from dotenv import load_dotenv
    load_dotenv()
    
    from database.session import db_manager
    from core.config import settings, init_settings
    
    # 导入原生工作流模块
    from agents.epistemic_workflow import (
        EpistemicWorkflow,
        EpistemicWorkflowInput,
    )
    from agents.event_stream_native import register_workflow_event_stream
    from agents.saga_integration import get_saga_manager
    
    # 重新初始化 settings
    settings = init_settings()
    
    async with db_manager.session_factory() as db:
        repository = WorkflowStateRepository(db)
        
        try:
            # 更新状态为 RUNNING
            await repository.update_status(
                workflow_id,
                WorkflowStatus.RUNNING,
            )
            
            # 获取 LLM 配置
            llm_name = None
            if model_config and "llm_name" in model_config:
                llm_name = model_config["llm_name"]
            
            llm_config = settings.get_llm_config(llm_name)
            print(f"[DEBUG] LLM 配置: {llm_config.model_name}")
            
            # 创建原生工作流
            workflow = EpistemicWorkflow(
                llm_config=llm_config,
                checkpoint_storage_path=f"./checkpoints/{session_id}",
            )
            
            # 创建输入
            input_data = EpistemicWorkflowInput(
                research_idea=research_idea,
                target_journal=target_journal,
                research_type=paper_type,
            )
            
            print(f"[DEBUG] 开始执行原生工作流...")
            
            # 执行工作流（流式）
            # 原生特性：workflow.run_stream 返回 WorkflowEvent 流
            event_stream = workflow.run_stream(input_data)
            
            # 注册事件流（供 SSE 桥接层消费）
            # 原生特性：事件流被注册后，SSE 路由可以直接消费
            await register_workflow_event_stream(session_id, event_stream)
            
            # 消费事件流并更新数据库状态
            final_result = None
            
            async for event in event_stream:
                print(f"[DEBUG] 事件: {event.type}")
                
                # 根据事件类型更新状态
                if event.type == "status":
                    # 工作流状态变更
                    state = event.state.value if hasattr(event.state, 'value') else str(event.state)
                    
                    # 映射到数据库状态
                    from agents.saga_integration import WorkflowStateSynchronizer
                    db_status = WorkflowStateSynchronizer.map_run_state_to_status(
                        event.state
                    )
                    
                    await repository.update_status(workflow_id, db_status)
                
                elif event.type == "output":
                    # 最终输出
                    final_result = event.data
                    
                    # 更新工作流状态
                    workflow_state = await repository.get_by_id(workflow_id)
                    if workflow_state:
                        agent_state = workflow_state.agent_state_json or {}
                        
                        # 根据输出类型更新状态
                        if hasattr(final_result, 'latex_source'):
                            agent_state["latex_source"] = final_result.latex_source
                        if hasattr(final_result, 'review_result'):
                            agent_state["review_result"] = final_result.review_result
                        
                        workflow_state.agent_state_json = agent_state
                        await db.commit()
                
                elif event.type == "failed":
                    # 工作流失败
                    details = event.details
                    error_msg = details.message if details else "未知错误"
                    
                    await repository.update_status(
                        workflow_id,
                        WorkflowStatus.FAILED,
                        error_message=error_msg,
                    )
            
            # 工作流完成
            if final_result:
                await repository.update_stage(
                    workflow_id,
                    WorkflowStage.COMPLETION,
                )
                await repository.update_status(
                    workflow_id,
                    WorkflowStatus.COMPLETED,
                )
                
                print(f"[DEBUG] 原生工作流执行完成")
            else:
                print(f"[DEBUG] 原生工作流未产生输出")
        
        except Exception as e:
            error_msg = f"执行原生工作流失败: {str(e)}"
            print(f"[ERROR] {error_msg}")
            import traceback
            traceback.print_exc()
            
            await repository.update_status(
                workflow_id,
                WorkflowStatus.FAILED,
                error_message=error_msg,
            )


# ============================================================================
# 工作流恢复接口（Saga 回滚）
# ============================================================================

@router.post("/resume", response_model=WorkflowStartResponse)
async def resume_workflow(
    request: WorkflowResumeRequest,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowStartResponse:
    """
    从检查点恢复工作流
    
    原生特性：
    - 使用 SagaStateManager.fork_from_checkpoint
    - 支持注入人类反馈
    - 确定性恢复
    
    Args:
        request: 恢复请求
        db: 数据库会话
    
    Returns:
        WorkflowStartResponse: 恢复响应
    """
    # 生成新的 session_id
    new_session_id = str(uuid.uuid4())
    
    repository = WorkflowStateRepository(db)
    
    try:
        # 获取 Saga 管理器
        from agents.saga_integration import get_saga_manager
        
        saga_manager = get_saga_manager()
        
        # Fork 并注入人类反馈
        new_checkpoint = await saga_manager.fork_from_checkpoint(
            checkpoint_id=request.checkpoint_id,
            new_session_id=new_session_id,
            human_feedback=request.human_feedback,
        )
        
        # 创建新的工作流状态记录
        workflow_state = await repository.create(
            session_id=new_session_id,
            workflow_name="epistemicflow_resumed",
            current_stage=WorkflowStage.INITIALIZATION,
            status=WorkflowStatus.PENDING,
            agent_state=new_checkpoint.state,
            metadata={
                "forked_from": request.checkpoint_id,
                "has_human_feedback": request.human_feedback is not None,
            },
        )
        
        # 异步恢复执行
        async def _safe_resume_workflow():
            try:
                await _resume_native_workflow(
                    session_id=new_session_id,
                    workflow_id=workflow_state.id,
                    checkpoint_id=new_checkpoint.checkpoint_id,
                )
            except Exception as e:
                print(f"[ERROR] 恢复工作流失败: {e}")
        
        asyncio.ensure_future(_safe_resume_workflow())
        
        return WorkflowStartResponse(
            session_id=new_session_id,
            workflow_id=workflow_state.id,
            status=WorkflowStatus.PENDING,
            current_stage=WorkflowStage.INITIALIZATION,
            message=f"工作流已从检查点 {request.checkpoint_id} 恢复",
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"恢复工作流失败: {str(e)}",
        )


async def _resume_native_workflow(
    session_id: str,
    workflow_id: int,
    checkpoint_id: str,
) -> None:
    """恢复原生工作流执行"""
    from dotenv import load_dotenv
    load_dotenv()
    
    from database.session import db_manager
    from core.config import init_settings
    from agents.epistemic_workflow import EpistemicWorkflow, EpistemicWorkflowInput
    
    settings = init_settings()
    
    async with db_manager.session_factory() as db:
        repository = WorkflowStateRepository(db)
        
        try:
            await repository.update_status(workflow_id, WorkflowStatus.RUNNING)
            
            llm_config = settings.get_llm_config()
            
            workflow = EpistemicWorkflow(llm_config=llm_config)
            
            # 从检查点恢复
            result = await workflow.run(
                EpistemicWorkflowInput(research_idea=""),
                checkpoint_id=checkpoint_id,
            )
            
            await repository.update_status(workflow_id, WorkflowStatus.COMPLETED)
            
        except Exception as e:
            await repository.update_status(
                workflow_id,
                WorkflowStatus.FAILED,
                error_message=str(e),
            )


# ============================================================================
# LaTeX 导出接口
# ============================================================================

@router.get(
    "/{session_id}/export/latex",
    response_model=LaTeXExportResponse,
)
async def export_latex(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> LaTeXExportResponse:
    """导出 LaTeX 格式手稿"""
    repository = WorkflowStateRepository(db)
    
    try:
        states = await repository.get_by_session_id(session_id, limit=1)
        if not states:
            raise HTTPException(
                status_code=404,
                detail=f"会话不存在: {session_id}",
            )
        
        workflow_state = states[0]
        
        if workflow_state.status != WorkflowStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"工作流尚未完成，当前状态: {workflow_state.status.value}",
            )
        
        agent_state = workflow_state.agent_state_json or {}
        latex_content = agent_state.get("latex_source", "")
        
        if not latex_content:
            raise HTTPException(
                status_code=404,
                detail="未找到 LaTeX 内容",
            )
        
        filename = f"manuscript_{session_id[:8]}.tex"
        
        metadata = {
            "char_count": len(latex_content),
            "line_count": latex_content.count("\n") + 1,
        }
        
        return LaTeXExportResponse(
            session_id=session_id,
            filename=filename,
            content=latex_content,
            metadata=metadata,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"导出 LaTeX 失败: {str(e)}",
        )


# ============================================================================
# 状态查询接口
# ============================================================================

@router.get("/{session_id}/status")
async def get_workflow_status(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """获取工作流状态"""
    repository = WorkflowStateRepository(db)
    
    states = await repository.get_by_session_id(session_id, limit=1)
    if not states:
        raise HTTPException(
            status_code=404,
            detail=f"会话不存在: {session_id}",
        )
    
    state = states[0]
    return {
        "session_id": session_id,
        "status": state.status.value,
        "current_stage": state.current_stage.value,
        "workflow_name": state.workflow_name,
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
        "has_error": bool(state.error_message),
        "error_message": state.error_message,
        "architecture": state.metadata.get("architecture", "legacy") if state.metadata else "legacy",
    }


# ============================================================================
# 检查点列表接口
# ============================================================================

@router.get("/{session_id}/checkpoints")
async def list_checkpoints(
    session_id: str,
) -> List[Dict[str, Any]]:
    """
    列出工作流的所有检查点
    
    原生特性：使用 SagaStateManager.list_checkpoints
    """
    from agents.saga_integration import get_saga_manager
    
    saga_manager = get_saga_manager()
    
    checkpoints = await saga_manager.list_checkpoints(
        workflow_name=f"epistemicflow_{session_id}",
    )
    
    return [
        {
            "checkpoint_id": cp.checkpoint_id,
            "timestamp": cp.timestamp,
            "iteration_count": cp.iteration_count,
        }
        for cp in checkpoints
    ]
