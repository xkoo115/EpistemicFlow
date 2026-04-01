"""
EpistemicFlow 统一工作流入口 (Unified Workflow Entry Point)

本模块是重构后的核心入口，整合所有阶段的完整工作流。

完整工作流阶段：
Stage 1: 构思阶段 (Ideation) - 意图捕获与双轨分类
Stage 2: 文献调研 (Literature Review) - Map-Reduce 动态编排
Stage 3: 方法论设计 (Methodology Design) - 实验规划
Stage 4: 手稿润色 (Polishing) - 高阶推理与 LaTeX 生成
Stage 5: 同行评审 (Peer Review) - 固定编排评审委员会

原生特性：
- 完全基于 agent_framework 的原生编排
- 统一的事件流和状态管理
- 支持 HITL 和 Saga 回滚
- 可观测性：所有事件实时透传

使用示例：
    from agents.epistemic_workflow import EpistemicWorkflow
    
    workflow = EpistemicWorkflow()
    result = await workflow.run(
        research_idea="研究深度学习在药物发现中的应用",
        stream=True,
    )
"""

from typing import Any, Dict, List, Optional, AsyncIterator, Never
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from datetime import datetime

from agent_framework import (
    Agent,
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    Workflow,
    WorkflowRunResult,
    WorkflowEvent,
    FileCheckpointStorage,
    State,
    handler,
)
from agent_framework.openai import OpenAIChatClient

from agents.tools_native import get_literature_tools
from agents.workflow_native import (
    LiteratureSearchExecutor,
    SubsetAnalysisExecutor,
    AggregationExecutor,
    SurveyGenerationExecutor,
    DynamicMapReduceWorkflowBuilder,
)
from agents.polishing_and_review import (
    PolishingAgent,
    PeerReviewBoardBuilder,
    Manuscript,
    ConsolidatedReview,
)
from agents.saga_integration import (
    SagaStateManager,
    HITLManager,
    get_saga_manager,
)
from agents.event_stream_native import (
    register_workflow_event_stream,
    SSEStreamGenerator,
)
from core.config import LLMConfig, settings


# ============================================================================
# 工作流阶段定义
# ============================================================================

class EpistemicStage(str, Enum):
    """EpistemicFlow 工作流阶段"""
    IDEATION = "ideation"
    """构思阶段：意图捕获与分类"""
    LITERATURE_REVIEW = "literature_review"
    """文献调研：Map-Reduce 动态编排"""
    METHODOLOGY_DESIGN = "methodology_design"
    """方法论设计：实验规划"""
    DATA_COLLECTION = "data_collection"
    """数据收集：实验执行"""
    ANALYSIS = "analysis"
    """分析：结果处理"""
    POLISHING = "polishing"
    """手稿润色：LaTeX 生成"""
    PEER_REVIEW = "peer_review"
    """同行评审：评审委员会"""
    COMPLETION = "completion"
    """完成"""


# ============================================================================
# 工作流输入/输出模型
# ============================================================================

@dataclass
class EpistemicWorkflowInput:
    """工作流输入"""
    research_idea: str
    """研究想法/主题"""
    target_journal: Optional[str] = None
    """目标期刊"""
    research_type: Optional[str] = None
    """研究类型：research_paper / survey_paper"""
    additional_context: Dict[str, Any] = field(default_factory=dict)
    """额外上下文"""


@dataclass
class EpistemicWorkflowOutput:
    """工作流输出"""
    research_idea: str
    """研究想法"""
    research_type: str
    """研究类型"""
    literature_survey: Optional[Any] = None
    """文献综述"""
    methodology: Optional[Any] = None
    """方法论设计"""
    manuscript: Optional[Manuscript] = None
    """最终手稿"""
    review_result: Optional[ConsolidatedReview] = None
    """评审结果"""
    final_verdict: Optional[str] = None
    """最终结论"""
    session_id: str = ""
    """会话 ID"""
    checkpoint_id: str = ""
    """最终检查点 ID"""


# ============================================================================
# 阶段执行器定义
# ============================================================================

class IdeationExecutor(Executor):
    """
    构思阶段执行器
    
    负责意图捕获和双轨分类（研究论文 vs 综述论文）。
    
    原生特性：
    - 使用 Agent 进行意图理解
    - 输出结构化的研究计划
    """
    
    def __init__(
        self,
        id: str = "ideation",
        llm_config: Optional[LLMConfig] = None,
    ):
        super().__init__(id=id)
        self._llm_config = llm_config or settings.get_llm_config()
        self._agent: Optional[Agent] = None
    
    def _get_agent(self) -> Agent:
        if self._agent is None:
            client = OpenAIChatClient(
                model_id=self._llm_config.model_name,
                api_key=self._llm_config.api_key,
                base_url=self._llm_config.base_url,
            )
            
            self._agent = Agent(
                client=client,
                name="ideation_agent",
                instructions="""你是一位资深的研究顾问，负责帮助用户明确研究意图。

你的核心任务是：
1. 理解用户的研究想法
2. 判断研究类型（原创研究 vs 综述论文）
3. 提炼研究问题和假设
4. 识别关键概念和术语
5. 建议初步的研究方向

输出要求：
- 研究类型：research_paper 或 survey_paper
- 研究问题：明确、具体
- 关键概念：列表
- 建议方向：列表""",
            )
        
        return self._agent
    
    @handler
    async def ideate(
        self,
        input: EpistemicWorkflowInput,
        ctx: WorkflowContext[Dict[str, Any]],
    ) -> None:
        """执行构思"""
        agent = self._get_agent()
        
        prompt = f"""请分析以下研究想法：

{input.research_idea}

请：
1. 判断研究类型（research_paper 或 survey_paper）
2. 提炼核心研究问题
3. 识别关键概念和术语
4. 建议研究方向

请返回 JSON 格式的分析结果。"""
        
        response = await agent.run(prompt)
        
        # 解析响应
        result = self._parse_response(response)
        result["original_idea"] = input.research_idea
        result["target_journal"] = input.target_journal
        
        # 更新工作流状态
        ctx.set_state("current_stage", EpistemicStage.LITERATURE_REVIEW.value)
        ctx.set_state("research_type", result.get("research_type", "research_paper"))
        
        # 发送到下游
        await ctx.send_message(result)
    
    def _parse_response(self, response: Any) -> Dict[str, Any]:
        """解析响应"""
        import json
        
        text = response.text if hasattr(response, 'text') else str(response)
        
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            return json.loads(text.strip())
        except Exception:
            return {
                "research_type": "research_paper",
                "research_questions": [],
                "key_concepts": [],
                "suggested_directions": [],
            }


class MethodologyDesignExecutor(Executor):
    """
    方法论设计执行器
    
    负责基于文献综述设计实验方法论。
    """
    
    def __init__(
        self,
        id: str = "methodology_design",
        llm_config: Optional[LLMConfig] = None,
    ):
        super().__init__(id=id)
        self._llm_config = llm_config or settings.get_llm_config()
        self._agent: Optional[Agent] = None
    
    def _get_agent(self) -> Agent:
        if self._agent is None:
            client = OpenAIChatClient(
                model_id=self._llm_config.model_name,
                api_key=self._llm_config.api_key,
                base_url=self._llm_config.base_url,
            )
            
            self._agent = Agent(
                client=client,
                name="methodology_agent",
                instructions="""你是一位方法论专家，负责设计严谨的实验方案。

你的核心任务是：
1. 基于文献综述识别最佳实践
2. 设计实验流程和数据收集方案
3. 选择合适的评估指标
4. 规划基线对比实验
5. 确保可复现性

输出要求：
- 实验设计：详细步骤
- 数据集：描述和来源
- 评估指标：列表和理由
- 基线方法：列表
- 可复现性保证：措施""",
            )
        
        return self._agent
    
    @handler
    async def design(
        self,
        literature_result: Dict[str, Any],
        ctx: WorkflowContext[Dict[str, Any]],
    ) -> None:
        """设计方法论"""
        agent = self._get_agent()
        
        prompt = f"""请基于以下文献综述，设计实验方法论：

研究主题: {literature_result.get('research_topic', '未知')}
关键发现: {literature_result.get('key_findings', [])}
研究空白: {literature_result.get('research_gaps', [])}

请设计完整的实验方案。返回 JSON 格式。"""
        
        response = await agent.run(prompt)
        result = self._parse_response(response)
        
        ctx.set_state("current_stage", EpistemicStage.POLISHING.value)
        await ctx.send_message(result)
    
    def _parse_response(self, response: Any) -> Dict[str, Any]:
        """解析响应"""
        import json
        
        text = response.text if hasattr(response, 'text') else str(response)
        
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            
            return json.loads(text.strip())
        except Exception:
            return {"methodology": text}


class PolishingExecutor(Executor):
    """
    手稿润色执行器
    
    负责生成高质量 LaTeX 手稿。
    """
    
    def __init__(
        self,
        id: str = "polishing",
        llm_config: Optional[LLMConfig] = None,
    ):
        super().__init__(id=id)
        self._polishing_agent = PolishingAgent(llm_config)
    
    @handler
    async def polish(
        self,
        methodology: Dict[str, Any],
        ctx: WorkflowContext[Manuscript],
    ) -> None:
        """执行润色"""
        # 获取文献综述结果
        literature_result = ctx.get_state("literature_result", {})
        
        # 执行润色
        manuscript = await self._polishing_agent.polish(
            research_results={
                "methodology": methodology,
                "literature": literature_result,
            },
            figures=[],
            tables=[],
            target_journal=ctx.get_state("target_journal"),
        )
        
        ctx.set_state("current_stage", EpistemicStage.PEER_REVIEW.value)
        await ctx.send_message(manuscript)


class PeerReviewExecutor(Executor):
    """
    同行评审执行器
    
    负责运行评审委员会。
    """
    
    def __init__(self, id: str = "peer_review"):
        super().__init__(id=id)
        self._review_builder = PeerReviewBoardBuilder()
    
    @handler
    async def review(
        self,
        manuscript: Manuscript,
        ctx: WorkflowContext[Never, ConsolidatedReview],
    ) -> None:
        """执行评审"""
        # 构建评审工作流
        review_workflow = self._review_builder.build()
        
        # 运行评审
        result = await review_workflow.run(manuscript)
        review_result = result.get_output()
        
        ctx.set_state("current_stage", EpistemicStage.COMPLETION.value)
        ctx.set_state("final_verdict", review_result.final_verdict.value)
        
        # 输出最终结果
        await ctx.yield_output(review_result)


# ============================================================================
# EpistemicFlow 主工作流
# ============================================================================

class EpistemicWorkflow:
    """
    EpistemicFlow 主工作流
    
    整合所有阶段的完整工作流，完全基于 agent_framework 原生编排。
    
    原生特性：
    - 使用 WorkflowBuilder 构建完整拓扑
    - 支持流式执行和事件监听
    - 支持 HITL 和 Saga 回滚
    - 统一的状态管理和检查点
    
    使用示例：
        workflow = EpistemicWorkflow()
        
        # 流式执行
        async for event in workflow.run_stream(input):
            print(event)
        
        # 非流式执行
        result = await workflow.run(input)
    """
    
    def __init__(
        self,
        llm_config: Optional[LLMConfig] = None,
        checkpoint_storage_path: Optional[str] = None,
    ):
        """
        初始化工作流
        
        Args:
            llm_config: LLM 配置
            checkpoint_storage_path: 检查点存储路径
        """
        self._llm_config = llm_config or settings.get_llm_config()
        
        # 检查点存储
        if checkpoint_storage_path:
            self._checkpoint_storage = FileCheckpointStorage(checkpoint_storage_path)
        else:
            self._checkpoint_storage = None
        
        # Saga 管理器
        self._saga_manager = get_saga_manager(checkpoint_storage_path)
        
        # 构建工作流
        self._workflow = self._build_workflow()
    
    def _build_workflow(self) -> Workflow:
        """
        构建完整工作流
        
        拓扑结构：
        Ideation -> LiteratureReview -> MethodologyDesign -> Polishing -> PeerReview
        
        原生特性说明：
        - 使用 WorkflowBuilder 声明式构建
        - 每个阶段是一个 Executor
        - 通过 add_edge 连接阶段
        - 支持条件路由（Switch-Case）
        
        Returns:
            构建完成的工作流
        """
        # 创建阶段执行器
        ideation = IdeationExecutor(llm_config=self._llm_config)
        literature_search = LiteratureSearchExecutor(llm_config=self._llm_config)
        methodology = MethodologyDesignExecutor(llm_config=self._llm_config)
        polishing = PolishingExecutor(llm_config=self._llm_config)
        peer_review = PeerReviewExecutor()
        
        # 构建工作流
        builder = WorkflowBuilder(
            start_executor=ideation,
            name="epistemic_workflow",
            checkpoint_storage=self._checkpoint_storage,
        )
        
        # 连接阶段
        # Ideation -> Literature Search
        builder = builder.add_edge(ideation, literature_search)
        
        # Literature Search -> Methodology Design
        builder = builder.add_edge(literature_search, methodology)
        
        # Methodology Design -> Polishing
        builder = builder.add_edge(methodology, polishing)
        
        # Polishing -> Peer Review
        builder = builder.add_edge(polishing, peer_review)
        
        return builder.build()
    
    async def run(
        self,
        input: EpistemicWorkflowInput,
        checkpoint_id: Optional[str] = None,
    ) -> EpistemicWorkflowOutput:
        """
        运行工作流（非流式）
        
        原生特性说明：
        - workflow.run() 返回 WorkflowRunResult
        - 支持 checkpoint_id 恢复执行
        - 结果通过 result.get_output() 获取
        
        Args:
            input: 工作流输入
            checkpoint_id: 检查点 ID（用于恢复）
        
        Returns:
            工作流输出
        """
        # 执行工作流
        if checkpoint_id:
            # 从检查点恢复
            result = await self._workflow.run(
                checkpoint_id=checkpoint_id,
                checkpoint_storage=self._checkpoint_storage,
            )
        else:
            # 新执行
            result = await self._workflow.run(input)
        
        # 构建输出
        return self._build_output(result, input)
    
    async def run_stream(
        self,
        input: EpistemicWorkflowInput,
        checkpoint_id: Optional[str] = None,
    ) -> AsyncIterator[WorkflowEvent]:
        """
        运行工作流（流式）
        
        原生特性说明：
        - workflow.run(stream=True) 返回事件流
        - 每个 WorkflowEvent 实时产生
        - 可被 SSE 桥接层直接消费
        
        Args:
            input: 工作流输入
            checkpoint_id: 检查点 ID
        
        Yields:
            工作流事件
        """
        # 获取事件流
        if checkpoint_id:
            event_stream = self._workflow.run(
                checkpoint_id=checkpoint_id,
                checkpoint_storage=self._checkpoint_storage,
                stream=True,
            )
        else:
            event_stream = self._workflow.run(input, stream=True)
        
        # 生成事件
        final_result = None
        
        async for event in event_stream:
            yield event
            
            # 捕获最终结果
            if event.type == "output":
                final_result = event.data
        
        # 保存最终检查点
        if final_result:
            await self._save_final_checkpoint(final_result)
    
    def _build_output(
        self,
        result: WorkflowRunResult,
        input: EpistemicWorkflowInput,
    ) -> EpistemicWorkflowOutput:
        """构建输出"""
        output = result.get_output()
        
        return EpistemicWorkflowOutput(
            research_idea=input.research_idea,
            research_type=output.get("research_type", "research_paper") if isinstance(output, dict) else "research_paper",
            manuscript=output if isinstance(output, Manuscript) else None,
            review_result=output if isinstance(output, ConsolidatedReview) else None,
            session_id=str(id(result)),
            checkpoint_id=str(result.metadata.get("checkpoint_id", "")),
        )
    
    async def _save_final_checkpoint(
        self,
        result: Any,
    ) -> None:
        """保存最终检查点"""
        # 实现检查点保存逻辑
        pass
    
    async def fork_from_checkpoint(
        self,
        checkpoint_id: str,
        new_session_id: str,
        human_feedback: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        从检查点 Fork
        
        原生特性说明：
        - Fork 是 Saga 模式的核心操作
        - 创建新的执行路径
        - 可注入人类反馈
        
        Args:
            checkpoint_id: 源检查点 ID
            new_session_id: 新会话 ID
            human_feedback: 人类反馈
        
        Returns:
            新检查点 ID
        """
        new_checkpoint = await self._saga_manager.fork_from_checkpoint(
            checkpoint_id=checkpoint_id,
            new_session_id=new_session_id,
            human_feedback=human_feedback,
        )
        
        return new_checkpoint.checkpoint_id


# ============================================================================
# 便捷函数
# ============================================================================

async def run_epistemic_workflow(
    research_idea: str,
    target_journal: Optional[str] = None,
    stream: bool = True,
) -> EpistemicWorkflowOutput:
    """
    运行 EpistemicFlow 工作流（便捷函数）
    
    Args:
        research_idea: 研究想法
        target_journal: 目标期刊
        stream: 是否流式执行
    
    Returns:
        工作流输出
    """
    workflow = EpistemicWorkflow()
    
    input = EpistemicWorkflowInput(
        research_idea=research_idea,
        target_journal=target_journal,
    )
    
    if stream:
        # 流式执行
        final_result = None
        
        async for event in workflow.run_stream(input):
            if event.type == "output":
                final_result = event.data
        
        return final_result
    else:
        # 非流式执行
        return await workflow.run(input)


async def resume_epistemic_workflow(
    checkpoint_id: str,
    human_feedback: Optional[Dict[str, Any]] = None,
) -> EpistemicWorkflowOutput:
    """
    从检查点恢复工作流
    
    Args:
        checkpoint_id: 检查点 ID
        human_feedback: 人类反馈
    
    Returns:
        工作流输出
    """
    workflow = EpistemicWorkflow()
    
    # Fork 并恢复
    new_checkpoint_id = await workflow.fork_from_checkpoint(
        checkpoint_id=checkpoint_id,
        new_session_id=f"resume_{checkpoint_id}",
        human_feedback=human_feedback,
    )
    
    # 从新检查点继续执行
    return await workflow.run(
        EpistemicWorkflowInput(research_idea=""),
        checkpoint_id=new_checkpoint_id,
    )
