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
        # 注意：使用 asyncio.ensure_future 确保任务在事件循环中运行
        print(f"[DEBUG] 添加后台任务...")
        
        async def _safe_run_ideation_agent():
            """安全包装函数，捕获所有异常"""
            try:
                await _run_ideation_agent(
                    session_id=session_id,
                    workflow_id=workflow_state.id,
                    research_idea=request.research_idea,
                    paper_type=request.paper_type,
                    model_config=request.llm_config,
                )
            except Exception as e:
                print(f"[ERROR] 后台任务执行失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 使用 asyncio.ensure_future 而不是 BackgroundTasks
        asyncio.ensure_future(_safe_run_ideation_agent())
        print(f"[DEBUG] 后台任务已添加")

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
    print(f"\n[DEBUG] _run_ideation_agent 开始执行")
    print(f"[DEBUG] session_id: {session_id}")
    print(f"[DEBUG] workflow_id: {workflow_id}")
    
    # 重新加载配置，确保 .env 文件被正确加载
    from dotenv import load_dotenv
    load_dotenv()
    print(f"[DEBUG] .env 文件已加载")
    
    from database.session import db_manager
    from agents.ideation import IdeationAgent
    from core.config import settings, init_settings
    from api.stream import (
        publish_agent_thought,
        publish_workflow_stage_change,
        publish_agent_action,
    )
    
    # 重新初始化 settings 对象，使其重新读取环境变量
    settings = init_settings()
    
    print(f"[DEBUG] 导入完成")
    print(f"[DEBUG] settings.default_llm: {settings.default_llm}")
    print(f"[DEBUG] settings.llms keys: {list(settings.llms.keys())}")

    async with db_manager.session_factory() as db:
        print(f"[DEBUG] 数据库会话创建成功")
        repository = WorkflowStateRepository(db)
        state_manager = StateManager(db)
        print(f"[DEBUG] Repository 和 StateManager 创建成功")

        try:
            print(f"[DEBUG] 开始执行 try 块...")
            
            # 发布工作流阶段变更事件
            print(f"[DEBUG] 发布工作流阶段变更事件...")
            await publish_workflow_stage_change(
                session_id,
                "initialization",
                "conception",
                "开始执行构思智能体",
            )
            print(f"[DEBUG] 工作流阶段变更事件发布成功")

            # 更新状态为 RUNNING
            print(f"[DEBUG] 更新状态为 RUNNING...")
            await repository.update_status(
                workflow_id,
                WorkflowStatus.RUNNING,
            )
            print(f"[DEBUG] 状态已更新为 RUNNING")

            # 发布智能体思考事件
            print(f"[DEBUG] 发布智能体思考事件...")
            await publish_agent_thought(
                session_id,
                "ideation_agent",
                f"正在分析用户的研究想法：{research_idea[:100]}...",
            )
            print(f"[DEBUG] 智能体思考事件发布成功")

            # 获取 LLM 配置
            print(f"[DEBUG] 获取 LLM 配置...")
            try:
                llm_name = None
                if model_config and "llm_name" in model_config:
                    llm_name = model_config["llm_name"]
                
                print(f"[DEBUG] llm_name: {llm_name}")
                print(f"[DEBUG] settings.default_llm: {settings.default_llm}")
                print(f"[DEBUG] settings.llms keys: {list(settings.llms.keys())}")
                
                llm_config = settings.get_llm_config(llm_name)
                print(f"[DEBUG] LLM 配置获取成功: {llm_config.model_name}")
            except Exception as e:
                print(f"[ERROR] 获取 LLM 配置失败: {e}")
                import traceback
                traceback.print_exc()
                raise

            # 创建 IdeationAgent
            print(f"[DEBUG] 创建 IdeationAgent...")
            ideation_agent = IdeationAgent(
                name="ideation_agent",
                llm_config=llm_config,
            )
            print(f"[DEBUG] IdeationAgent 创建成功")

            # 发布智能体行动事件
            print(f"[DEBUG] 发布智能体行动事件...")
            await publish_agent_action(
                session_id,
                "ideation_agent",
                "analyze",
                {"research_idea": research_idea, "paper_type": paper_type},
            )
            print(f"[DEBUG] 智能体行动事件发布成功")

            # 执行意图分析
            print(f"[DEBUG] 执行意图分析（调用 DeepSeek）...")
            result = await ideation_agent.analyze(research_idea)
            print(f"[DEBUG] 意图分析完成！结果: {result.paper_type.value}")

            # 发布分析结果
            print(f"[DEBUG] 发布分析结果...")
            await publish_agent_thought(
                session_id,
                "ideation_agent",
                f"分析完成！\n"
                f"论文类型: {result.paper_type.value}\n"
                f"研究主题: {result.research_topic}\n"
                f"关键词: {', '.join(result.keywords)}\n"
                f"置信度: {result.confidence:.2f}",
            )
            print(f"[DEBUG] 分析结果发布成功")

            # 更新工作流状态中的分析结果
            workflow_state = await repository.get_by_id(workflow_id)
            if workflow_state:
                agent_state = workflow_state.agent_state_json or {}
                agent_state["ideation_result"] = {
                    "paper_type": result.paper_type.value,
                    "research_topic": result.research_topic,
                    "keywords": result.keywords,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning.model_dump() if result.reasoning else None,
                }
                workflow_state.agent_state_json = agent_state
                workflow_state.current_stage = WorkflowStage.CONCEPTION
                await db.commit()

            # 发布工作流阶段变更事件
            await publish_workflow_stage_change(
                session_id,
                "conception",
                "research",
                "构思阶段完成，进入研究阶段",
            )

            # 更新阶段到 LITERATURE_REVIEW
            await repository.update_stage(
                workflow_id,
                WorkflowStage.LITERATURE_REVIEW,
            )

            # 启动 LeadResearcherAgent（后台任务）
            print(f"[DEBUG] 启动 LeadResearcherAgent...")
            asyncio.ensure_future(_run_research_agent(
                session_id=session_id,
                workflow_id=workflow_id,
                research_topic=result.research_topic,
                keywords=result.keywords,
                paper_type=result.paper_type.value,
                model_config=model_config,
            ))

        except Exception as e:
            # 记录错误
            error_msg = f"执行构思智能体失败: {str(e)}"
            await publish_agent_thought(
                session_id,
                "ideation_agent",
                f"❌ 错误: {error_msg}",
            )
            await repository.update_status(
                workflow_id,
                WorkflowStatus.FAILED,
                error_message=error_msg,
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


async def _run_research_agent(
    session_id: str,
    workflow_id: int,
    research_topic: str,
    keywords: List[str],
    paper_type: str,
    model_config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    运行 LeadResearcherAgent（后台任务）

    此函数在后台异步执行，负责文献调研和综述生成。

    Args:
        session_id: 会话 ID
        workflow_id: 工作流状态 ID
        research_topic: 研究主题
        keywords: 关键词列表
        paper_type: 论文类型
        model_config: 模型配置
    """
    print(f"\n[DEBUG] _run_research_agent 开始执行")
    print(f"[DEBUG] session_id: {session_id}")
    print(f"[DEBUG] workflow_id: {workflow_id}")
    print(f"[DEBUG] research_topic: {research_topic}")
    print(f"[DEBUG] keywords: {keywords}")
    print(f"[DEBUG] paper_type: {paper_type}")

    # 重新加载配置
    from dotenv import load_dotenv
    load_dotenv()

    from database.session import db_manager
    from agents.research import LeadResearcherAgent
    from core.config import settings, init_settings
    from api.stream import (
        publish_agent_thought,
        publish_workflow_stage_change,
        publish_agent_action,
    )

    # 重新初始化 settings
    settings = init_settings()

    async with db_manager.session_factory() as db:
        repository = WorkflowStateRepository(db)
        state_manager = StateManager(db)

        try:
            # 更新状态为 RUNNING
            await repository.update_status(
                workflow_id,
                WorkflowStatus.RUNNING,
            )

            # 发布智能体思考事件
            await publish_agent_thought(
                session_id,
                "research_agent",
                f"开始文献调研...\n研究主题: {research_topic}\n关键词: {', '.join(keywords)}",
            )

            # 获取 LLM 配置
            llm_name = None
            if model_config and "llm_name" in model_config:
                llm_name = model_config["llm_name"]

            llm_config = settings.get_llm_config(llm_name)
            print(f"[DEBUG] LLM 配置: {llm_config.model_name}")

            # 创建 LeadResearcherAgent
            research_agent = LeadResearcherAgent(
                name="research_agent",
                llm_config=llm_config,
            )

            # 发布智能体行动事件
            await publish_agent_action(
                session_id,
                "research_agent",
                "search_literature",
                {
                    "research_topic": research_topic,
                    "keywords": keywords,
                    "paper_type": paper_type,
                },
            )

            # 执行文献调研
            print(f"[DEBUG] 执行文献调研...")

            try:
                # 导入文献搜索工具
                from tools.literature import LiteratureSearchTool

                # 创建文献搜索工具
                literature_tool = LiteratureSearchTool()

                # 发布智能体思考事件
                await publish_agent_thought(
                    session_id,
                    "research_agent",
                    f"正在搜索相关文献...\n研究主题: {research_topic}\n关键词: {', '.join(keywords)}",
                )

                # 搜索文献
                search_query = f"{research_topic} {' '.join(keywords)}"
                print(f"[DEBUG] 搜索查询: {search_query}")

                search_result = await literature_tool.search(
                    query=search_query,
                    limit=20,
                    sources=["semantic_scholar", "arxiv"],
                )

                # 提取论文列表
                papers = search_result.papers if hasattr(search_result, 'papers') else []

                print(f"[DEBUG] 找到 {len(papers)} 篇文献")
                if search_result.errors:
                    print(f"[DEBUG] 搜索错误: {search_result.errors}")

                await publish_agent_thought(
                    session_id,
                    "research_agent",
                    f"找到 {len(papers)} 篇相关文献，正在分析...",
                )

                # 执行文献调研（Map-Reduce）
                if papers:
                    print(f"[DEBUG] 开始 Map-Reduce 分析...")
                    result = await research_agent.conduct_research(
                        papers=papers,
                        research_topic=research_topic,
                    )

                    print(f"[DEBUG] Map-Reduce 分析完成")

                    await publish_agent_thought(
                        session_id,
                        "research_agent",
                        f"文献调研完成！\n"
                        f"共分析 {len(papers)} 篇论文\n"
                        f"综述标题: {result.title}\n"
                        f"主要发现:\n{result.key_findings[:500]}...",
                    )

                    research_result = {
                        "papers_found": len(papers),
                        "research_topic": research_topic,
                        "keywords": keywords,
                        "survey_title": result.title,
                        "key_findings": result.key_findings,
                        "methodology_summary": result.methodology_summary,
                        "future_directions": result.future_directions,
                        "status": "completed",
                    }
                else:
                    await publish_agent_thought(
                        session_id,
                        "research_agent",
                        "未找到相关文献，请尝试其他关键词",
                    )

                    research_result = {
                        "papers_found": 0,
                        "research_topic": research_topic,
                        "keywords": keywords,
                        "status": "no_results",
                    }

            except Exception as e:
                print(f"[ERROR] 文献调研失败: {e}")
                import traceback
                traceback.print_exc()

                await publish_agent_thought(
                    session_id,
                    "research_agent",
                    f"文献调研失败: {str(e)}",
                )

                research_result = {
                    "papers_found": 0,
                    "research_topic": research_topic,
                    "keywords": keywords,
                    "status": "error",
                    "error": str(e),
                }

            # 更新工作流状态
            workflow_state = await repository.get_by_id(workflow_id)
            if workflow_state:
                agent_state = workflow_state.agent_state_json or {}
                agent_state["research_result"] = research_result
                workflow_state.agent_state_json = agent_state
                await db.commit()

            # 发布阶段变更事件
            await publish_workflow_stage_change(
                session_id,
                "research",
                "review",
                "文献调研完成，等待人工审核",
            )

            # 更新阶段到 LITERATURE_REVIEW（等待人工审核）
            await repository.update_stage(
                workflow_id,
                WorkflowStage.LITERATURE_REVIEW,
            )

            # 更新状态为 PAUSED（等待人工审核）
            await repository.update_status(
                workflow_id,
                WorkflowStatus.PAUSED,
            )

            # 发布 HITL 中断事件
            from api.stream import publish_hitl_interrupt
            await publish_hitl_interrupt(
                session_id,
                "literature_review_complete",
                {
                    "stage": "literature_review",
                    "message": "文献调研已完成，请审核研究结果",
                    "research_result": research_result,
                    "actions": [
                        {
                            "id": "approve",
                            "label": "✓ 批准并继续",
                            "description": "研究结果符合预期，继续执行写作阶段",
                        },
                        {
                            "id": "modify",
                            "label": "✎ 修改关键词",
                            "description": "调整研究关键词，重新搜索文献",
                        },
                        {
                            "id": "reject",
                            "label": "✗ 拒绝结果",
                            "description": "研究结果不符合预期，终止工作流",
                        },
                    ],
                },
            )

            print(f"[DEBUG] LeadResearcherAgent 执行完成，等待人工审核")

        except Exception as e:
            # 记录错误
            error_msg = f"执行研究智能体失败: {str(e)}"
            print(f"[ERROR] {error_msg}")
            import traceback
            traceback.print_exc()

            await publish_agent_thought(
                session_id,
                "research_agent",
                f"❌ 错误: {error_msg}",
            )
            await repository.update_status(
                workflow_id,
                WorkflowStatus.FAILED,
                error_message=error_msg,
            )


async def _run_writing_agent(
    session_id: str,
    workflow_id: int,
    research_result: Dict[str, Any],
) -> None:
    """
    运行写作智能体（后台任务）

    此函数在后台异步执行，负责论文写作。

    Args:
        session_id: 会话 ID
        workflow_id: 工作流状态 ID
        research_result: 研究结果
    """
    print(f"\n[DEBUG] _run_writing_agent 开始执行")
    print(f"[DEBUG] session_id: {session_id}")
    print(f"[DEBUG] workflow_id: {workflow_id}")

    # 重新加载配置
    from dotenv import load_dotenv
    load_dotenv()

    from database.session import db_manager
    from core.config import settings, init_settings
    from api.stream import (
        publish_agent_thought,
        publish_workflow_stage_change,
        publish_agent_action,
    )

    # 重新初始化 settings
    settings = init_settings()

    async with db_manager.session_factory() as db:
        repository = WorkflowStateRepository(db)

        try:
            # 发布智能体思考事件
            await publish_agent_thought(
                session_id,
                "writing_agent",
                f"开始论文写作...\n基于 {research_result.get('papers_found', 0)} 篇文献",
            )

            # 更新阶段到 WRITING
            await repository.update_stage(
                workflow_id,
                WorkflowStage.WRITING,
            )

            # 发布阶段变更事件
            await publish_workflow_stage_change(
                session_id,
                "review",
                "writing",
                "审核通过，开始论文写作",
            )

            # 模拟写作过程
            await publish_agent_thought(
                session_id,
                "writing_agent",
                "正在生成论文大纲...",
            )

            await asyncio.sleep(2)

            await publish_agent_thought(
                session_id,
                "writing_agent",
                "正在撰写引言部分...",
            )

            await asyncio.sleep(2)

            await publish_agent_thought(
                session_id,
                "writing_agent",
                "正在撰写方法论部分...",
            )

            await asyncio.sleep(2)

            await publish_agent_thought(
                session_id,
                "writing_agent",
                "正在撰写结果和讨论部分...",
            )

            await asyncio.sleep(2)

            # 生成论文内容
            paper_content = f"""# {research_result.get('survey_title', '研究论文')}

## 摘要

本文综述了{research_result.get('research_topic', '相关领域')}的研究进展。

## 引言

{research_result.get('key_findings', '本文总结了相关研究的主要发现。')[:500]}

## 方法论

{research_result.get('methodology_summary', '本文采用了系统文献综述的方法。')[:500]}

## 结果与讨论

基于对{research_result.get('papers_found', 0)}篇文献的分析，我们发现了以下主要趋势...

## 未来方向

{research_result.get('future_directions', '未来研究可以从以下几个方向展开...')[:500]}

## 结论

本文系统综述了{research_result.get('research_topic', '相关领域')}的研究现状，为后续研究提供了参考。
"""

            await publish_agent_thought(
                session_id,
                "writing_agent",
                f"论文写作完成！\n\n{paper_content[:500]}...",
            )

            # 更新工作流状态
            workflow_state = await repository.get_by_id(workflow_id)
            if workflow_state:
                agent_state = workflow_state.agent_state_json or {}
                agent_state["paper_content"] = paper_content
                agent_state["writing_status"] = "completed"
                workflow_state.agent_state_json = agent_state
                await db.commit()

            # 发布阶段变更事件
            await publish_workflow_stage_change(
                session_id,
                "writing",
                "completion",
                "论文写作完成",
            )

            # 更新阶段到 COMPLETION
            await repository.update_stage(
                workflow_id,
                WorkflowStage.COMPLETION,
            )

            # 更新状态为 COMPLETED
            await repository.update_status(
                workflow_id,
                WorkflowStatus.COMPLETED,
            )

            print(f"[DEBUG] WritingAgent 执行完成")

        except Exception as e:
            # 记录错误
            error_msg = f"执行写作智能体失败: {str(e)}"
            print(f"[ERROR] {error_msg}")
            import traceback
            traceback.print_exc()

            await publish_agent_thought(
                session_id,
                "writing_agent",
                f"❌ 错误: {error_msg}",
            )
            await repository.update_status(
                workflow_id,
                WorkflowStatus.FAILED,
                error_message=error_msg,
            )
