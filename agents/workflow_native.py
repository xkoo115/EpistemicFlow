"""
原生工作流编排模块 (Native Workflow Orchestration)

本模块利用 agent_framework 的原生 WorkflowBuilder，彻底重构文献调研阶段的动态编排。

核心变更：
- 使用 WorkflowBuilder + Executor 替代手动 asyncio.gather
- 使用 FanOutEdgeGroup 实现 Map 阶段的并发分发
- 使用 FanInEdgeGroup 实现 Reduce 阶段的消息聚合
- 动态实例化能力：根据文献规模动态生成执行器

设计原则：
- 声明式编排：通过拓扑结构定义工作流
- 类型安全：使用泛型确保消息类型正确
- 可观测性：所有事件自动进入原生事件流
"""

from typing import Any, Dict, List, Optional, Sequence, TypeVar, Generic, Never
from dataclasses import dataclass, field
import asyncio
import uuid

from agent_framework import (
    Agent,
    AgentSession,
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    Workflow,
    WorkflowRunResult,
    WorkflowEvent,
    WorkflowCheckpoint,
    FileCheckpointStorage,
    InMemoryCheckpointStorage,
    handler,
    Message,
    Content,
)
from agent_framework.openai import OpenAIChatClient

from agents.tools_native import get_literature_tools
from agents.schemas import (
    PaperMetadata,
    LiteratureSubset,
    SubResearcherOutput,
    AggregatedResearchState,
    DomainSurveyOutput,
)
from core.config import LLMConfig, settings


# ============================================================================
# 类型变量定义
# ============================================================================

# 执行器输入类型
InT = TypeVar("InT")
# 执行器输出类型
OutT = TypeVar("OutT")


# ============================================================================
# 数据模型定义
# ============================================================================

@dataclass
class LiteratureSearchRequest:
    """文献检索请求"""
    query: str
    """检索查询"""
    sources: List[str] = field(default_factory=lambda: ["semantic_scholar", "arxiv"])
    """检索源"""
    limit_per_source: int = 10
    """每个源的结果数"""


@dataclass
class LiteratureSearchResult:
    """文献检索结果"""
    query: str
    papers: List[PaperMetadata]
    total_count: int
    source: str = "unified"


@dataclass
class SubsetAnalysisRequest:
    """子集分析请求"""
    subset: LiteratureSubset
    research_topic: str
    subset_id: str


@dataclass
class SurveyGenerationRequest:
    """综述生成请求"""
    aggregated_state: AggregatedResearchState
    research_topic: str


# ============================================================================
# 执行器定义 (Executor)
# ============================================================================

class LiteratureSearchExecutor(Executor):
    """
    文献检索执行器
    
    负责调用原生工具执行文献检索。
    这是 Map-Reduce 工作流的起点。
    
    原生特性：
    - 继承自 agent_framework.Executor
    - 使用 @handler 装饰器定义处理函数
    - 通过 WorkflowContext 发送消息到下游
    """
    
    def __init__(
        self,
        id: str = "literature_search",
        llm_config: Optional[LLMConfig] = None,
    ):
        """
        初始化文献检索执行器
        
        Args:
            id: 执行器 ID
            llm_config: LLM 配置（用于智能检索）
        """
        super().__init__(id=id)
        self._llm_config = llm_config or settings.get_llm_config()
    
    @handler
    async def search(
        self,
        request: LiteratureSearchRequest,
        ctx: WorkflowContext[LiteratureSearchResult],
    ) -> None:
        """
        执行文献检索
        
        这是核心处理函数，使用 @handler 装饰器注册。
        
        原生特性说明：
        - @handler 装饰器将此方法注册为消息处理器
        - ctx 参数提供工作流上下文，用于发送消息和访问状态
        - 返回 None，通过 ctx.send_message() 发送结果
        
        Args:
            request: 检索请求
            ctx: 工作流上下文
        """
        # 导入统一检索工具
        from tools.literature import LiteratureSearchTool
        
        tool = LiteratureSearchTool()
        
        # 执行检索
        result = await tool.search(
            query=request.query,
            sources=request.sources,
            limit_per_source=request.limit_per_source,
        )
        
        # 构建输出
        search_result = LiteratureSearchResult(
            query=request.query,
            papers=result.papers,
            total_count=len(result.papers),
        )
        
        # 发送消息到下游执行器
        # 原生特性：通过 ctx.send_message() 发送消息
        await ctx.send_message(search_result)
        
        # 可选：发送中间数据事件（用于实时监控）
        # 原生特性：通过 ctx.emit_event() 发送自定义事件
        # 这会触发 WorkflowEvent.data 事件，可被 SSE 桥接层捕获
        await ctx.emit_event({
            "type": "literature_search_completed",
            "query": request.query,
            "count": len(result.papers),
        })


class SubsetAnalysisExecutor(Executor):
    """
    子集分析执行器
    
    负责分析单个文献子集，提取关键发现。
    在 Map-Reduce 架构中，多个实例并行运行（Map 阶段）。
    
    原生特性：
    - 每个实例拥有独立的 Agent
    - Agent 配备原生工具（文献检索）
    - 通过 Agent.run() 执行分析
    """
    
    def __init__(
        self,
        subset_id: str,
        llm_config: Optional[LLMConfig] = None,
    ):
        """
        初始化子集分析执行器
        
        Args:
            subset_id: 子集 ID（用于标识）
            llm_config: LLM 配置
        """
        super().__init__(id=f"subset_analyzer_{subset_id}")
        self._subset_id = subset_id
        self._llm_config = llm_config or settings.get_llm_config()
        
        # 创建 Agent（延迟初始化）
        self._agent: Optional[Agent] = None
    
    def _get_agent(self) -> Agent:
        """获取或创建 Agent（延迟初始化）"""
        if self._agent is None:
            # 创建模型客户端
            client = OpenAIChatClient(
                model_id=self._llm_config.model_name,
                api_key=self._llm_config.api_key,
                base_url=self._llm_config.base_url,
            )
            
            # 创建 Agent，注册原生工具
            self._agent = Agent(
                client=client,
                name=f"sub_researcher_{self._subset_id}",
                instructions=self._get_instructions(),
                tools=get_literature_tools(),  # 注册原生工具
            )
        
        return self._agent
    
    def _get_instructions(self) -> str:
        """获取系统指令"""
        return """你是一位专业的文献分析研究员，负责深入分析分配给你的文献子集。

你的核心任务是：
1. 仔细阅读每篇论文的标题、摘要和元信息
2. 提取关键发现和创新点
3. 识别使用的研究方法论
4. 发现研究空白和未解决的问题
5. 总结研究趋势和发展方向

分析要求：
- 关注方法论的创新性和有效性
- 注意不同研究之间的关联和差异
- 识别潜在的研究空白和机会
- 保持客观、严谨的分析态度

你可以使用提供的工具进行补充检索，以获取更多相关信息。"""
    
    @handler
    async def analyze(
        self,
        request: SubsetAnalysisRequest,
        ctx: WorkflowContext[SubResearcherOutput],
    ) -> None:
        """
        分析文献子集
        
        原生特性说明：
        - Agent 自主决定是否调用工具
        - 工具调用结果作为原生 ToolMessage 返回
        - 整个过程完全由 LLM 控制
        
        Args:
            request: 分析请求
            ctx: 工作流上下文
        """
        agent = self._get_agent()
        
        # 构建分析提示
        prompt = self._build_analysis_prompt(request.subset, request.research_topic)
        
        # 调用 Agent（原生方式）
        # Agent 会自主决定是否调用工具
        response = await agent.run(prompt)
        
        # 解析响应
        output = self._parse_response(response, request.subset)
        
        # 发送结果到下游
        await ctx.send_message(output)
    
    def _build_analysis_prompt(
        self,
        subset: LiteratureSubset,
        research_topic: str,
    ) -> str:
        """构建分析提示"""
        papers_text = []
        for i, paper in enumerate(subset.papers, 1):
            paper_info = f"""
论文 {i}:
标题: {paper.title}
作者: {', '.join(paper.authors[:3]) if paper.authors else '未知'}
年份: {paper.publication_year or '未知'}
摘要: {paper.abstract or '无摘要'}
"""
            papers_text.append(paper_info)
        
        return f"""请分析以下 {len(subset.papers)} 篇论文：

研究主题: {research_topic}

{''.join(papers_text)}

请按照以下步骤进行分析：
1. 总结每篇论文的核心贡献
2. 提取共同的研究方法论
3. 识别研究空白和未解决的问题
4. 总结研究趋势

如果需要更多信息，可以使用提供的检索工具进行补充查询。

请返回 JSON 格式的分析结果。"""
    
    def _parse_response(
        self,
        response: Any,
        subset: LiteratureSubset,
    ) -> SubResearcherOutput:
        """解析响应"""
        import json
        
        text = response.text if hasattr(response, 'text') else str(response)
        
        try:
            # 尝试解析 JSON
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            data = json.loads(text.strip())
            
            return SubResearcherOutput(
                subset_id=self._subset_id,
                agent_id=self.id,
                papers_analyzed=len(subset.papers),
                key_findings=data.get("key_findings", []),
                methodologies=data.get("methodologies", []),
                research_gaps=data.get("research_gaps", []),
                trends=data.get("trends", []),
                confidence=data.get("confidence", 0.8),
                raw_summary=data.get("summary", ""),
            )
        except Exception:
            # 解析失败，返回基本结果
            return SubResearcherOutput(
                subset_id=self._subset_id,
                agent_id=self.id,
                papers_analyzed=len(subset.papers),
                confidence=0.5,
                raw_summary=text,
            )


class AggregationExecutor(Executor):
    """
    聚合执行器
    
    负责聚合所有子集分析结果（Reduce 阶段）。
    
    原生特性：
    - 接收来自多个上游执行器的消息（Fan-In）
    - 消息自动聚合为列表
    - 执行全局汇总和去重
    """
    
    def __init__(self, id: str = "aggregator"):
        super().__init__(id=id)
    
    @handler
    async def aggregate(
        self,
        results: List[SubResearcherOutput],  # 自动聚合的消息列表
        ctx: WorkflowContext[AggregatedResearchState],
    ) -> None:
        """
        聚合子结果
        
        原生特性说明：
        - 参数类型为 List，表示接收聚合的消息
        - agent_framework 自动将多个上游消息聚合为列表
        - 这就是 "operator.add 思想" 的实现
        
        Args:
            results: 所有子集分析结果（自动聚合）
            ctx: 工作流上下文
        """
        # 聚合内容
        all_findings = []
        all_methodologies = []
        all_gaps = []
        all_trends = []
        
        for result in results:
            all_findings.extend(result.key_findings)
            all_methodologies.extend(result.methodologies)
            all_gaps.extend(result.research_gaps)
            all_trends.extend(result.trends)
        
        # 去重
        unique_findings = list(dict.fromkeys(all_findings))
        unique_methodologies = list(dict.fromkeys(all_methodologies))
        unique_gaps = list(dict.fromkeys(all_gaps))
        unique_trends = list(dict.fromkeys(all_trends))
        
        # 构建聚合状态
        aggregated = AggregatedResearchState(
            total_papers=sum(r.papers_analyzed for r in results),
            total_subsets=len(results),
            successful_analyses=sum(1 for r in results if r.confidence > 0.5),
            all_key_findings=unique_findings,
            all_methodologies=unique_methodologies,
            all_research_gaps=unique_gaps,
            all_trends=unique_trends,
            sub_results={r.subset_id: r for r in results},
        )
        
        # 发送聚合结果
        await ctx.send_message(aggregated)


class SurveyGenerationExecutor(Executor):
    """
    综述生成执行器
    
    负责基于聚合状态生成领域现状综述。
    这是 Map-Reduce 工作流的终点。
    """
    
    def __init__(
        self,
        id: str = "survey_generator",
        llm_config: Optional[LLMConfig] = None,
    ):
        super().__init__(id=id)
        self._llm_config = llm_config or settings.get_llm_config()
        self._agent: Optional[Agent] = None
    
    def _get_agent(self) -> Agent:
        """获取或创建 Agent"""
        if self._agent is None:
            client = OpenAIChatClient(
                model_id=self._llm_config.model_name,
                api_key=self._llm_config.api_key,
                base_url=self._llm_config.base_url,
            )
            
            self._agent = Agent(
                client=client,
                name="survey_generator",
                instructions="""你是一位资深的首席研究员，负责撰写领域现状综述。

你的核心任务是：
1. 整合多个助理研究员的分析结果
2. 识别跨子集的共同主题和趋势
3. 发现研究领域的整体格局
4. 撰写结构化、连贯的综述报告

综述要求：
- 引言：介绍研究背景和重要性
- 方法论综述：系统梳理主要研究方法
- 当前挑战：指出领域面临的关键问题
- 未来方向：展望潜在的研究机会
- 结论：总结主要发现""",
            )
        
        return self._agent
    
    @handler
    async def generate(
        self,
        request: SurveyGenerationRequest,
        ctx: WorkflowContext[Never, DomainSurveyOutput],
    ) -> None:
        """
        生成综述
        
        原生特性说明：
        - ctx 类型为 WorkflowContext[Never, DomainSurveyOutput]
        - Never 表示不再发送消息到下游
        - DomainSurveyOutput 表示这是最终输出类型
        - 通过 ctx.yield_output() 输出最终结果
        
        Args:
            request: 综述生成请求
            ctx: 工作流上下文
        """
        agent = self._get_agent()
        
        # 构建提示
        prompt = self._build_survey_prompt(request.aggregated_state, request.research_topic)
        
        # 调用 Agent
        response = await agent.run(prompt)
        
        # 解析响应
        survey = self._parse_survey_response(response, request.research_topic)
        
        # 输出最终结果
        # 原生特性：通过 ctx.yield_output() 输出最终结果
        # 这会触发 WorkflowEvent.output 事件
        await ctx.yield_output(survey)
    
    def _build_survey_prompt(
        self,
        state: AggregatedResearchState,
        research_topic: str,
    ) -> str:
        """构建综述生成提示"""
        findings_text = "\n".join(f"- {f}" for f in state.all_key_findings[:20])
        methods_text = "\n".join(f"- {m}" for m in state.all_methodologies[:15])
        gaps_text = "\n".join(f"- {g}" for g in state.all_research_gaps[:10])
        trends_text = "\n".join(f"- {t}" for t in state.all_trends[:10])
        
        return f"""请基于以下分析结果，撰写关于"{research_topic}"的领域现状综述。

分析统计：
- 分析论文总数: {state.total_papers}
- 成功分析子集数: {state.successful_analyses}/{state.total_subsets}

关键发现：
{findings_text or '无'}

主要方法论：
{methods_text or '无'}

研究空白：
{gaps_text or '无'}

研究趋势：
{trends_text or '无'}

请撰写一篇结构完整、内容连贯的综述报告。"""
    
    def _parse_survey_response(
        self,
        response: Any,
        research_topic: str,
    ) -> DomainSurveyOutput:
        """解析综述响应"""
        import json
        
        text = response.text if hasattr(response, 'text') else str(response)
        
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            data = json.loads(text.strip())
            
            return DomainSurveyOutput(
                research_topic=research_topic,
                introduction=data.get("introduction", ""),
                methodology_review=data.get("methodology_review", ""),
                current_challenges=data.get("current_challenges", []),
                future_directions=data.get("future_directions", []),
                conclusion=data.get("conclusion", ""),
                key_references=data.get("key_references", []),
            )
        except Exception:
            return DomainSurveyOutput(
                research_topic=research_topic,
                introduction=text,
            )


# ============================================================================
# 动态工作流构建器
# ============================================================================

class DynamicMapReduceWorkflowBuilder:
    """
    动态 Map-Reduce 工作流构建器
    
    根据文献规模动态构建工作流拓扑。
    
    原生特性：
    - 使用 WorkflowBuilder 构建拓扑
    - 使用 add_fan_out_edges 实现 Map 阶段
    - 使用 add_fan_in_edges 实现 Reduce 阶段
    - 支持检查点持久化
    """
    
    def __init__(
        self,
        llm_config: Optional[LLMConfig] = None,
        max_concurrent_subsets: int = 5,
        checkpoint_storage: Optional[FileCheckpointStorage] = None,
    ):
        """
        初始化工作流构建器
        
        Args:
            llm_config: LLM 配置
            max_concurrent_subsets: 最大并发子集数
            checkpoint_storage: 检查点存储（用于 Saga）
        """
        self._llm_config = llm_config or settings.get_llm_config()
        self._max_concurrent_subsets = max_concurrent_subsets
        self._checkpoint_storage = checkpoint_storage
    
    def build(
        self,
        papers: List[PaperMetadata],
        research_topic: str,
    ) -> Workflow:
        """
        构建工作流
        
        根据文献数量动态生成执行器实例。
        
        原生特性说明：
        - WorkflowBuilder 是 agent_framework 的核心构建器
        - add_edge/add_fan_out_edges/add_fan_in_edges 定义拓扑
        - build() 返回可执行的 Workflow
        
        Args:
            papers: 文献列表
            research_topic: 研究主题
        
        Returns:
            构建完成的工作流
        """
        # 1. 分割文献为子集
        subsets = self._partition_papers(papers)
        
        # 2. 创建执行器实例
        # 搜索执行器（起点）
        search_executor = LiteratureSearchExecutor(
            llm_config=self._llm_config,
        )
        
        # 子集分析执行器（Map 阶段）
        # 动态实例化：根据子集数量创建对应数量的执行器
        subset_executors = [
            SubsetAnalysisExecutor(
                subset_id=subset.subset_id,
                llm_config=self._llm_config,
            )
            for subset in subsets
        ]
        
        # 聚合执行器（Reduce 阶段）
        aggregator = AggregationExecutor()
        
        # 综述生成执行器（终点）
        survey_executor = SurveyGenerationExecutor(
            llm_config=self._llm_config,
        )
        
        # 3. 构建工作流拓扑
        builder = WorkflowBuilder(
            start_executor=search_executor,
            name="literature_review_workflow",
            checkpoint_storage=self._checkpoint_storage,
        )
        
        # Map 阶段：搜索 -> 子集分析（Fan-Out）
        # 原生特性：add_fan_out_edges 实现消息广播
        # 搜索结果会被发送到所有子集分析执行器
        builder = builder.add_fan_out_edges(
            source=search_executor,
            targets=subset_executors,
        )
        
        # Reduce 阶段：子集分析 -> 聚合（Fan-In）
        # 原生特性：add_fan_in_edges 实现消息聚合
        # 所有子集分析结果会被聚合为列表，发送给聚合执行器
        builder = builder.add_fan_in_edges(
            sources=subset_executors,
            target=aggregator,
        )
        
        # 综述生成：聚合 -> 综述（单边）
        builder = builder.add_edge(
            source=aggregator,
            target=survey_executor,
        )
        
        # 4. 构建并返回工作流
        return builder.build()
    
    def _partition_papers(
        self,
        papers: List[PaperMetadata],
        max_per_subset: int = 10,
    ) -> List[LiteratureSubset]:
        """
        分割文献为子集
        
        Args:
            papers: 文献列表
            max_per_subset: 每个子集的最大论文数
        
        Returns:
            文献子集列表
        """
        if not papers:
            return []
        
        subsets = []
        for i in range(0, len(papers), max_per_subset):
            subset_papers = papers[i:i + max_per_subset]
            subset = LiteratureSubset(
                subset_id=f"subset_{i // max_per_subset}",
                papers=subset_papers,
            )
            subsets.append(subset)
        
        return subsets


# ============================================================================
# 工作流运行器
# ============================================================================

async def run_literature_review_workflow(
    query: str,
    research_topic: str,
    llm_config: Optional[LLMConfig] = None,
    checkpoint_id: Optional[str] = None,
    stream: bool = True,
) -> DomainSurveyOutput:
    """
    运行文献调研工作流
    
    这是高层 API，封装了工作流的构建和执行。
    
    原生特性说明：
    - workflow.run() 返回 WorkflowRunResult
    - stream=True 时返回事件流
    - 支持 checkpoint_id 恢复执行
    
    Args:
        query: 检索查询
        research_topic: 研究主题
        llm_config: LLM 配置
        checkpoint_id: 检查点 ID（用于恢复）
        stream: 是否流式执行
    
    Returns:
        领域现状综述
    """
    # 1. 执行初始检索
    from tools.literature import LiteratureSearchTool
    tool = LiteratureSearchTool()
    result = await tool.search(query=query, limit_per_source=15)
    
    # 2. 构建工作流
    builder = DynamicMapReduceWorkflowBuilder(
        llm_config=llm_config,
    )
    workflow = builder.build(result.papers, research_topic)
    
    # 3. 执行工作流
    if stream:
        # 流式执行
        # 原生特性：workflow.run(stream=True) 返回事件流
        event_stream = workflow.run(
            LiteratureSearchRequest(query=query),
            stream=True,
        )
        
        # 消费事件流
        final_result = None
        async for event in event_stream:
            # event 是 WorkflowEvent 类型
            if event.type == "output":
                # 最终输出
                final_result = event.data
            elif event.type == "data":
                # 中间数据（如 Agent 响应）
                pass
            elif event.type == "executor_completed":
                # 执行器完成
                pass
        
        return final_result
    else:
        # 非流式执行
        result = await workflow.run(
            LiteratureSearchRequest(query=query),
        )
        return result.get_output()
