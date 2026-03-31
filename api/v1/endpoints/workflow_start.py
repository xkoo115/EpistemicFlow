"""
工作流启动与导出 API 端点

本模块提供端到端闭环的关键接口：
- POST /workflows/start: 启动新的科研工作流
- GET /workflows/{session_id}/export/latex: 导出 LaTeX 手稿

设计原则：
- 启动接口接收用户初始需求，创建 Saga 起点
- 异步唤醒 IdeationAgent，开始工作流
- 导出接口返回符合学术规范的 LaTeX 源码
"""

from typing import Optional, Dict, Any, List, Literal
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
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

# 定义论文类型字面量
PaperTypeLiteral = Literal["research_paper", "survey_paper"]


class WorkflowStartRequest(BaseModel):
    """
    工作流启动请求模型

    用户通过此模型提交初始科研需求，启动整个工作流。
    """

    research_idea: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="研究方向/假设描述，用户输入的核心科研 Idea",
    )

    paper_type: PaperTypeLiteral = Field(
        default="research_paper",
        description="论文类型：research_paper（原创研究）或 survey_paper（综述）",
    )

    llm_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="偏好的模型配置，如 LLM 选择、温度参数等",
    )

    keywords: List[str] = Field(
        default_factory=list,
        description="用户提供的关键词列表（可选）",
    )

    constraints: Dict[str, Any] = Field(
        default_factory=dict,
        description="约束条件，如字数限制、参考文献数量等",
    )


class WorkflowStartResponse(BaseModel):
    """
    工作流启动响应模型

    返回新创建的工作流信息，前端据此开始 SSE 监听。
    """

    session_id: str = Field(description="会话 ID，用于后续所有操作和 SSE 监听")
    workflow_id: int = Field(description="工作流状态记录 ID")
    status: WorkflowStatus = Field(description="初始状态")
    current_stage: WorkflowStage = Field(description="当前阶段")
    message: str = Field(description="启动消息")


class LaTeXExportResponse(BaseModel):
    """
    LaTeX 导出响应模型

    返回完整的 LaTeX 源码，可直接编译为 PDF。
    """

    session_id: str = Field(description="会话 ID")
    filename: str = Field(description="建议的文件名")
    content: str = Field(description="LaTeX 源码内容")
    metadata: Dict[str, Any] = Field(description="元数据，如字数、章节数等")


# ============================================================================
# 路由器定义
# ============================================================================

router = APIRouter()


# ============================================================================
# 工作流启动接口
# ============================================================================

@router.post("/start", response_model=WorkflowStartResponse)
async def start_workflow(
    request: WorkflowStartRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowStartResponse:
    """
    启动新的科研工作流

    这是系统的主入口，接收用户的科研 Idea 并初始化整个工作流。

    工作流程：
    1. 生成唯一的 session_id
    2. 创建初始 WorkflowState（Saga 起点）
    3. 保存用户输入到 agent_state
    4. 异步唤醒 IdeationAgent（后台任务）
    5. 返回 session_id，前端开始 SSE 监听

    Args:
        request: 启动请求，包含科研 Idea 和配置
        background_tasks: FastAPI 后台任务
        db: 数据库会话

    Returns:
        WorkflowStartResponse: 启动响应，包含 session_id

    前端使用示例：
        const response = await fetch('/api/v1/workflows/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                research_idea: '研究一种新的注意力机制...',
                paper_type: 'research_paper',
            }),
        });
        const { session_id } = await response.json();
        // 开始 SSE 监听
        const eventSource = new EventSource(`/api/stream/${session_id}`);
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
                "keywords": request.keywords or [],
                "constraints": request.constraints or {},
            },
            "model_config": request.llm_config or {},
            "workflow_metadata": {
                "started_at": asyncio.get_event_loop().time(),
                "source": "api_start",
            },
        }

        # 创建初始工作流状态（Saga 起点）
        workflow_state = await repository.create(
            session_id=session_id,
            workflow_name="epistemicflow_research",
            current_stage=WorkflowStage.INITIALIZATION,
            status=WorkflowStatus.PENDING,
            agent_state=initial_agent_state,
            metadata={
                "paper_type": request.paper_type,
                "idea_length": len(request.research_idea),
            },
        )

        # 异步唤醒 IdeationAgent（后台任务）
        # 注意：这里使用后台任务，避免阻塞响应
        background_tasks.add_task(
            _run_ideation_agent,
            session_id=session_id,
            workflow_id=workflow_state.id,
            research_idea=request.research_idea,
            paper_type=request.paper_type,
            model_config=request.llm_config,
        )

        return WorkflowStartResponse(
            session_id=session_id,
            workflow_id=workflow_state.id,
            status=WorkflowStatus.PENDING,
            current_stage=WorkflowStage.INITIALIZATION,
            message="工作流已启动，IdeationAgent 正在分析您的科研 Idea",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"启动工作流失败: {str(e)}",
        )


async def _run_ideation_agent(
    session_id: str,
    workflow_id: int,
    research_idea: str,
    paper_type: str,
    model_config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    运行 IdeationAgent（后台任务）

    此函数在后台异步执行，不阻塞 API 响应。

    Args:
        session_id: 会话 ID
        workflow_id: 工作流状态 ID
        research_idea: 科研 Idea
        paper_type: 论文类型（字符串值）
        model_config: 模型配置

    注意：
        此函数需要独立管理数据库会话，因为后台任务
        不能使用 FastAPI 的依赖注入。
    """
    from database.session import async_session_factory
    from agents.ideation import IdeationAgent
    from core.config import settings

    async with async_session_factory() as db:
        repository = WorkflowStateRepository(db)
        state_manager = StateManager(db)

        try:
            # 更新状态为 RUNNING
            await repository.update_status(
                workflow_id,
                WorkflowStatus.RUNNING,
            )

            # 获取 LLM 配置
            llm_config = settings.get_llm_config(
                model_config.get("llm_name", "default") if model_config else "default"
            )

            # 创建 IdeationAgent
            ideation_agent = IdeationAgent(
                name="ideation_agent",
                llm_config=llm_config,
            )

            # 执行意图分析
            # 注意：这里需要根据 IdeationAgent 的实际接口调整
            # result = await ideation_agent.analyze(research_idea, paper_type)

            # 模拟执行（实际实现需要调用 IdeationAgent）
            await asyncio.sleep(2)  # 模拟处理时间

            # 更新状态到下一阶段
            await repository.update_status(
                workflow_id,
                WorkflowStatus.PAUSED,  # 等待 HITL 确认
            )

            # 更新阶段
            workflow_state = await repository.get_by_id(workflow_id)
            if workflow_state:
                workflow_state.current_stage = WorkflowStage.CONCEPTION
                await db.commit()

        except Exception as e:
            # 记录错误
            await repository.update_status(
                workflow_id,
                WorkflowStatus.FAILED,
                error_message=str(e),
            )
        finally:
            # 清理资源
            if 'ideation_agent' in locals():
                await ideation_agent.close()


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
    """
    导出 LaTeX 格式手稿

    当工作流状态为 COMPLETED 时，将最终合并的 LaTeX 文本作为 .tex 文件返回。

    Args:
        session_id: 会话 ID
        db: 数据库会话

    Returns:
        LaTeXExportResponse: LaTeX 源码和元数据

    前端使用示例：
        const response = await fetch(`/api/v1/workflows/${sessionId}/export/latex`);
        const { filename, content } = await response.json();

        // 触发文件下载
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    """
    repository = WorkflowStateRepository(db)

    try:
        # 获取最新的工作流状态
        workflow_state = await repository.get_latest_by_session_and_stage(
            session_id,
            WorkflowStage.COMPLETION,
        )

        if not workflow_state:
            # 尝试获取任何阶段的最新状态
            states = await repository.get_by_session_id(session_id, limit=1)
            if not states:
                raise HTTPException(
                    status_code=404,
                    detail=f"会话不存在: {session_id}",
                )
            workflow_state = states[0]

        # 检查状态
        if workflow_state.status != WorkflowStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"工作流尚未完成，当前状态: {workflow_state.status.value}",
            )

        # 从 agent_state 中提取 LaTeX 内容
        agent_state = workflow_state.agent_state_json or {}
        latex_content = agent_state.get("latex_source")

        if not latex_content:
            # 如果没有存储的 LaTeX，尝试从其他字段构建
            latex_content = _build_latex_from_state(agent_state, workflow_state)

        # 生成文件名
        paper_title = agent_state.get("paper_title", "research_paper")
        safe_title = "".join(
            c if c.isalnum() or c in " -_" else "_" for c in paper_title
        )[:50]
        filename = f"{safe_title}.tex"

        # 计算元数据
        metadata = {
            "char_count": len(latex_content),
            "line_count": latex_content.count("\n") + 1,
            "section_count": latex_content.count("\\section{"),
            "subsection_count": latex_content.count("\\subsection{"),
            "equation_count": latex_content.count("\\begin{equation}"),
            "figure_count": latex_content.count("\\begin{figure}"),
            "table_count": latex_content.count("\\begin{table}"),
            "bibliography_count": latex_content.count("\\bibitem"),
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


def _build_latex_from_state(
    agent_state: Dict[str, Any],
    workflow_state,
) -> str:
    """
    从工作流状态构建 LaTeX 内容

    当 agent_state 中没有直接存储的 LaTeX 源码时，
    尝试从其他字段（如综述内容、章节内容）构建。

    Args:
        agent_state: 智能体状态
        workflow_state: 工作流状态

    Returns:
        LaTeX 源码
    """
    # 获取论文标题
    title = agent_state.get("paper_title", "Research Paper")
    author = agent_state.get("author", "EpistemicFlow")

    # 获取各章节内容
    abstract = agent_state.get("abstract", "")
    introduction = agent_state.get("introduction", "")
    methodology = agent_state.get("methodology", "")
    results = agent_state.get("results", "")
    discussion = agent_state.get("discussion", "")
    conclusion = agent_state.get("conclusion", "")
    references = agent_state.get("references", [])

    # 构建 LaTeX 模板
    latex_template = f"""% 自动生成的 LaTeX 手稿
% 由 EpistemicFlow 生成
% 生成时间: {workflow_state.updated_at.isoformat() if workflow_state.updated_at else ''}

\\documentclass[11pt,a4paper]{{article}}

% 基础宏包
\\usepackage[utf8]{{inputenc}}
\\usepackage{{amsmath,amssymb,amsfonts}}
\\usepackage{{graphicx}}
\\usepackage{{hyperref}}
\\usepackage{{booktabs}}
\\usepackage{{geometry}}

\\geometry{{margin=1in}}

% 标题信息
\\title{{{title}}}
\\author{{{author}}}
\\date{{\\today}}

\\begin{{document}}

\\maketitle

% 摘要
\\begin{{abstract}}
{abstract}
\\end{{abstract}}

% 引言
\\section{{Introduction}}
{introduction}

% 方法
\\section{{Methodology}}
{methodology}

% 结果
\\section{{Results}}
{results}

% 讨论
\\section{{Discussion}}
{discussion}

% 结论
\\section{{Conclusion}}
{conclusion}

% 参考文献
\\begin{{thebibliography}}{{99}}
"""

    # 添加参考文献
    for i, ref in enumerate(references, 1):
        latex_template += f"\\bibitem{{ref{i}}} {ref}\n"

    latex_template += """\\end{thebibliography}

\\end{document}
"""

    return latex_template


# ============================================================================
# 辅助接口
# ============================================================================

@router.get("/{session_id}/status")
async def get_workflow_status(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    获取工作流状态

    简化的状态查询接口，用于前端轮询（作为 SSE 的补充）。

    Args:
        session_id: 会话 ID
        db: 数据库会话

    Returns:
        工作流状态信息
    """
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
    }
