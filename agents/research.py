"""
研究智能体模块 (Map-Reduce 架构)

本模块实现"阶段二：动态文献调研与规划编排"。

核心架构：
- LeadResearcherAgent（首席研究员智能体）：负责任务分发和结果聚合
- SubResearcherAgent（助理研究员智能体）：负责并行处理文献子集

Map-Reduce 工作流：
1. Map 阶段：首席智能体将文献集合切割为子集，动态实例化多个助理智能体并发处理
2. Reduce 阶段：聚合所有助理智能体的结果，生成领域现状综述

设计原则：
- 高吞吐量：使用 asyncio.gather 实现真正的并发处理
- 状态隔离：每个助理智能体拥有独立的 AgentSession
- 容错机制：单个子集失败不影响整体工作流
"""

from typing import Any, Dict, List, Optional, Sequence
import asyncio
import uuid
import time
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from agent_framework import (
    Agent,
    AgentSession,
    ChatResponse,
    Message,
    Content,
    Role,
)

from agents.base import (
    BaseResearchAgent,
    ModelClientFactory,
    SessionManager,
    ResearchContextProvider,
    AgentManager,
)
from agents.schemas import (
    PaperMetadata,
    LiteratureSubset,
    SubResearcherOutput,
    AggregatedResearchState,
    DomainSurveyOutput,
    get_sub_researcher_response_format,
    get_domain_survey_response_format,
    parse_sub_researcher_output,
    parse_domain_survey_output,
)
from core.config import LLMConfig


# ============================================================================
# 任务分发策略
# ============================================================================

@dataclass
class PartitionConfig:
    """
    分区配置

    控制如何将文献集合分割为子集。
    """
    max_papers_per_subset: int = 10
    """每个子集的最大论文数"""

    min_papers_per_subset: int = 3
    """每个子集的最小论文数"""

    max_subsets: int = 10
    """最大子集数量"""

    balance_by_tokens: bool = True
    """是否按 token 数量平衡"""

    theme_grouping: bool = False
    """是否按主题分组"""


class TaskDistributor:
    """
    任务分发器

    负责将文献集合分割为多个子集，用于 Map 阶段的并行处理。

    分割策略：
    - 简单分割：按数量均匀分割
    - Token 平衡：预估每个子集的 token 数量，尽量平衡
    - 主题分组：按论文主题聚类后分割
    """

    def __init__(self, config: Optional[PartitionConfig] = None):
        """
        初始化任务分发器

        Args:
            config: 分区配置
        """
        self._config = config or PartitionConfig()

    def distribute(
        self,
        papers: Sequence[PaperMetadata],
    ) -> List[LiteratureSubset]:
        """
        分发文献集合

        将论文列表分割为多个子集。

        Args:
            papers: 论文元数据列表

        Returns:
            文献子集列表
        """
        if not papers:
            return []

        # 计算子集数量
        total_papers = len(papers)
        num_subsets = self._calculate_num_subsets(total_papers)

        # 执行分割
        if self._config.theme_grouping:
            return self._distribute_by_theme(papers, num_subsets)
        elif self._config.balance_by_tokens:
            return self._distribute_by_tokens(papers, num_subsets)
        else:
            return self._distribute_evenly(papers, num_subsets)

    def _calculate_num_subsets(self, total_papers: int) -> int:
        """
        计算子集数量

        Args:
            total_papers: 总论文数

        Returns:
            子集数量
        """
        # 基于每子集论文数计算
        num_by_size = total_papers // self._config.max_papers_per_subset
        if total_papers % self._config.max_papers_per_subset > 0:
            num_by_size += 1

        # 限制最大子集数
        return min(num_by_size, self._config.max_subsets, total_papers)

    def _distribute_evenly(
        self,
        papers: Sequence[PaperMetadata],
        num_subsets: int,
    ) -> List[LiteratureSubset]:
        """
        均匀分割

        Args:
            papers: 论文列表
            num_subsets: 子集数量

        Returns:
            子集列表
        """
        subsets = []
        papers_per_subset = len(papers) // num_subsets
        remainder = len(papers) % num_subsets

        start_idx = 0
        for i in range(num_subsets):
            # 处理余数
            end_idx = start_idx + papers_per_subset + (1 if i < remainder else 0)

            subset = LiteratureSubset(
                subset_id=f"subset_{i}",
                papers=list(papers[start_idx:end_idx]),
                theme=f"文献子集 {i + 1}",
            )
            subsets.append(subset)

            start_idx = end_idx

        return subsets

    def _distribute_by_tokens(
        self,
        papers: Sequence[PaperMetadata],
        num_subsets: int,
    ) -> List[LiteratureSubset]:
        """
        按 Token 平衡分割

        预估每篇论文的 token 数量，尽量使每个子集的 token 数量相近。

        Args:
            papers: 论文列表
            num_subsets: 子集数量

        Returns:
            子集列表
        """
        # 估算每篇论文的 token 数量
        # 简化估算：标题 + 摘要的字符数 / 4
        paper_tokens = []
        for paper in papers:
            text_length = len(paper.title)
            if paper.abstract:
                text_length += len(paper.abstract)
            estimated_tokens = text_length // 4
            paper_tokens.append((paper, estimated_tokens))

        # 按总 token 数平均分配
        total_tokens = sum(t for _, t in paper_tokens)
        target_tokens_per_subset = total_tokens // num_subsets

        subsets = []
        current_subset_papers = []
        current_tokens = 0
        subset_idx = 0

        for paper, tokens in paper_tokens:
            current_subset_papers.append(paper)
            current_tokens += tokens

            # 当达到目标 token 数或还有剩余论文时，创建新子集
            remaining_papers = len(papers) - sum(len(s.papers) for s in subsets) - len(current_subset_papers)
            if (current_tokens >= target_tokens_per_subset and
                subset_idx < num_subsets - 1 and
                remaining_papers >= self._config.min_papers_per_subset):

                subset = LiteratureSubset(
                    subset_id=f"subset_{subset_idx}",
                    papers=current_subset_papers,
                    estimated_tokens=current_tokens,
                )
                subsets.append(subset)

                current_subset_papers = []
                current_tokens = 0
                subset_idx += 1

        # 添加最后一个子集
        if current_subset_papers:
            subset = LiteratureSubset(
                subset_id=f"subset_{subset_idx}",
                papers=current_subset_papers,
                estimated_tokens=current_tokens,
            )
            subsets.append(subset)

        return subsets

    def _distribute_by_theme(
        self,
        papers: Sequence[PaperMetadata],
        num_subsets: int,
    ) -> List[LiteratureSubset]:
        """
        按主题分组分割

        简化实现：按标题关键词聚类。

        Args:
            papers: 论文列表
            num_subsets: 子集数量

        Returns:
            子集列表
        """
        # 简化实现：回退到均匀分割
        # 完整实现需要 NLP 聚类
        return self._distribute_evenly(papers, num_subsets)


# ============================================================================
# 助理研究员智能体 (SubResearcherAgent)
# ============================================================================

class SubResearcherAgent(BaseResearchAgent[SubResearcherOutput]):
    """
    助理研究员智能体

    负责处理单个文献子集，提取关键发现、方法论和研究趋势。

    在 Map-Reduce 架构中，多个 SubResearcherAgent 实例并行运行，
    每个实例处理一个文献子集，实现高吞吐量的文献分析。

    会话隔离：
    - 每个实例拥有独立的 AgentSession
    - 消息历史互不干扰
    - 状态完全隔离
    """

    def __init__(
        self,
        name: str,
        llm_config: LLMConfig,
        subset_id: str,
        session_manager: Optional[SessionManager] = None,
        context_provider: Optional[ResearchContextProvider] = None,
    ):
        """
        初始化助理研究员智能体

        Args:
            name: 智能体名称
            llm_config: LLM 配置
            subset_id: 子集 ID（用于标识和追踪）
            session_manager: 会话管理器
            context_provider: 上下文提供者
        """
        self._subset_id = subset_id
        super().__init__(
            name=name,
            llm_config=llm_config,
            session_manager=session_manager,
            context_provider=context_provider,
        )

    def _default_instructions(self) -> str:
        """获取默认系统指令"""
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

输出要求：
- 必须返回严格的 JSON 格式
- key_findings 应包含具体、有价值的发现
- methodologies 应列出主要的研究方法
- research_gaps 应指出未解决的问题
- trends 应总结研究趋势"""

    @property
    def subset_id(self) -> str:
        """获取子集 ID"""
        return self._subset_id

    async def analyze_subset(
        self,
        subset: LiteratureSubset,
        research_topic: Optional[str] = None,
    ) -> SubResearcherOutput:
        """
        分析文献子集

        Args:
            subset: 文献子集
            research_topic: 研究主题（用于聚焦分析）

        Returns:
            分析结果
        """
        # 构建分析提示
        analysis_prompt = self._build_subset_prompt(subset, research_topic)

        # 获取结构化输出格式
        response_format = get_sub_researcher_response_format()

        # 发送消息
        response = await self.send_message(
            user_input=analysis_prompt,
            response_format=response_format,
            include_context=True,
        )

        # 解析响应
        result = self._parse_response(response)
        result.subset_id = self._subset_id
        result.agent_id = self._name
        result.papers_analyzed = len(subset.papers)

        return result

    def _build_subset_prompt(
        self,
        subset: LiteratureSubset,
        research_topic: Optional[str],
    ) -> str:
        """
        构建子集分析提示

        Args:
            subset: 文献子集
            research_topic: 研究主题

        Returns:
            分析提示
        """
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

        topic_context = f"\n研究主题: {research_topic}\n" if research_topic else ""

        return f"""请分析以下 {len(subset.papers)} 篇论文：
{topic_context}
{''.join(papers_text)}

请按照以下步骤进行分析：
1. 总结每篇论文的核心贡献
2. 提取共同的研究方法论
3. 识别研究空白和未解决的问题
4. 总结研究趋势

请返回符合指定格式的 JSON 输出。"""

    def _parse_response(self, response: ChatResponse) -> SubResearcherOutput:
        """解析模型响应"""
        if not response.messages:
            raise ValueError("模型返回空响应")

        message = response.messages[0]
        text_content = message.text if hasattr(message, 'text') else ""

        if not text_content and message.contents:
            for content in message.contents:
                if hasattr(content, 'text') and content.text:
                    text_content = content.text
                    break

        if not text_content:
            raise ValueError("无法从响应中提取文本内容")

        try:
            cleaned_text = self._clean_json_text(text_content)
            return parse_sub_researcher_output(cleaned_text)
        except Exception as e:
            raise ValueError(f"解析模型响应失败: {e}")

    def _clean_json_text(self, text: str) -> str:
        """清理 JSON 文本"""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()


# ============================================================================
# 首席研究员智能体 (LeadResearcherAgent)
# ============================================================================

class LeadResearcherAgent(BaseResearchAgent[DomainSurveyOutput]):
    """
    首席研究员智能体

    负责协调整个文献调研过程，包括：
    - 任务分发（Map 阶段）
    - 结果聚合（Reduce 阶段）
    - 生成领域现状综述

    Map-Reduce 工作流：
    1. 接收文献集合，分割为子集
    2. 动态实例化多个 SubResearcherAgent
    3. 使用 asyncio.gather 并发执行分析
    4. 聚合所有结果，生成综述报告
    """

    def __init__(
        self,
        name: str,
        llm_config: LLMConfig,
        sub_agent_llm_config: Optional[LLMConfig] = None,
        max_concurrent_subsets: int = 5,
        partition_config: Optional[PartitionConfig] = None,
        session_manager: Optional[SessionManager] = None,
        context_provider: Optional[ResearchContextProvider] = None,
    ):
        """
        初始化首席研究员智能体

        Args:
            name: 智能体名称
            llm_config: 首席智能体的 LLM 配置（用于生成综述）
            sub_agent_llm_config: 助理智能体的 LLM 配置（可选，默认与首席相同）
            max_concurrent_subsets: 最大并发子集数
            partition_config: 分区配置
            session_manager: 会话管理器
            context_provider: 上下文提供者
        """
        self._sub_agent_llm_config = sub_agent_llm_config or llm_config
        self._max_concurrent_subsets = max_concurrent_subsets
        self._partition_config = partition_config or PartitionConfig()
        self._task_distributor = TaskDistributor(self._partition_config)

        super().__init__(
            name=name,
            llm_config=llm_config,
            session_manager=session_manager,
            context_provider=context_provider,
        )

    def _default_instructions(self) -> str:
        """获取默认系统指令"""
        return """你是一位资深的首席研究员，负责协调文献调研工作并撰写领域现状综述。

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
- 结论：总结主要发现

输出要求：
- 必须返回严格的 JSON 格式
- 内容应具有连贯性和逻辑性
- 引用应准确、有代表性"""

    async def conduct_research(
        self,
        papers: Sequence[PaperMetadata],
        research_topic: str,
    ) -> DomainSurveyOutput:
        """
        执行文献调研

        完整的 Map-Reduce 工作流。

        Args:
            papers: 文献集合
            research_topic: 研究主题

        Returns:
            领域现状综述
        """
        start_time = time.time()

        # Map 阶段：分发任务并并行处理
        aggregated_state = await self._map_phase(papers, research_topic)

        # Reduce 阶段：聚合结果并生成综述
        survey = await self._reduce_phase(aggregated_state, research_topic)

        # 记录处理时间
        processing_time = (time.time() - start_time) * 1000
        aggregated_state.processing_time_ms = processing_time

        return survey

    async def _map_phase(
        self,
        papers: Sequence[PaperMetadata],
        research_topic: str,
    ) -> AggregatedResearchState:
        """
        Map 阶段

        分发任务并并行执行子集分析。

        Args:
            papers: 文献集合
            research_topic: 研究主题

        Returns:
            聚合的研究状态
        """
        # 分发任务
        subsets = self._task_distributor.distribute(papers)

        if not subsets:
            return AggregatedResearchState(
                total_papers=0,
                total_subsets=0,
                successful_analyses=0,
            )

        # 创建并发控制信号量
        semaphore = asyncio.Semaphore(self._max_concurrent_subsets)

        # 定义带信号量控制的处理函数
        async def process_subset_with_semaphore(
            subset: LiteratureSubset,
        ) -> SubResearcherOutput:
            async with semaphore:
                # 动态创建助理智能体实例
                sub_agent = SubResearcherAgent(
                    name=f"sub_researcher_{subset.subset_id}",
                    llm_config=self._sub_agent_llm_config,
                    subset_id=subset.subset_id,
                )

                try:
                    return await sub_agent.analyze_subset(subset, research_topic)
                except Exception as e:
                    # 返回错误结果
                    return SubResearcherOutput(
                        subset_id=subset.subset_id,
                        agent_id=sub_agent.name,
                        papers_analyzed=len(subset.papers),
                        confidence=0.0,
                        raw_summary=f"分析失败: {str(e)}",
                    )
                finally:
                    await sub_agent.close()

        # 并行执行所有子集分析
        tasks = [process_subset_with_semaphore(subset) for subset in subsets]
        sub_results = await asyncio.gather(*tasks)

        # 聚合结果
        return self._aggregate_results(sub_results, papers, subsets)

    def _aggregate_results(
        self,
        sub_results: List[SubResearcherOutput],
        papers: Sequence[PaperMetadata],
        subsets: List[LiteratureSubset],
    ) -> AggregatedResearchState:
        """
        聚合子结果

        将所有助理智能体的结果合并为全局状态。

        Args:
            sub_results: 子结果列表
            papers: 原始论文列表
            subsets: 子集列表

        Returns:
            聚合的研究状态
        """
        # 统计
        total_papers = len(papers)
        total_subsets = len(subsets)
        successful_analyses = sum(1 for r in sub_results if r.confidence > 0)

        # 聚合内容（去重）
        all_findings = []
        all_methodologies = []
        all_gaps = []
        all_trends = []

        for result in sub_results:
            all_findings.extend(result.key_findings)
            all_methodologies.extend(result.methodologies)
            all_gaps.extend(result.research_gaps)
            all_trends.extend(result.trends)

        # 简单去重（基于字符串匹配）
        unique_findings = list(dict.fromkeys(all_findings))
        unique_methodologies = list(dict.fromkeys(all_methodologies))
        unique_gaps = list(dict.fromkeys(all_gaps))
        unique_trends = list(dict.fromkeys(all_trends))

        # 构建子结果字典
        sub_results_dict = {r.subset_id: r for r in sub_results}

        return AggregatedResearchState(
            total_papers=total_papers,
            total_subsets=total_subsets,
            successful_analyses=successful_analyses,
            all_key_findings=unique_findings,
            all_methodologies=unique_methodologies,
            all_research_gaps=unique_gaps,
            all_trends=unique_trends,
            sub_results=sub_results_dict,
        )

    async def _reduce_phase(
        self,
        aggregated_state: AggregatedResearchState,
        research_topic: str,
    ) -> DomainSurveyOutput:
        """
        Reduce 阶段

        基于聚合状态生成领域现状综述。

        Args:
            aggregated_state: 聚合的研究状态
            research_topic: 研究主题

        Returns:
            领域现状综述
        """
        # 构建综述生成提示
        prompt = self._build_survey_prompt(aggregated_state, research_topic)

        # 获取结构化输出格式
        response_format = get_domain_survey_response_format()

        # 发送消息
        response = await self.send_message(
            user_input=prompt,
            response_format=response_format,
            include_context=True,
        )

        # 解析响应
        return self._parse_survey_response(response)

    def _build_survey_prompt(
        self,
        state: AggregatedResearchState,
        research_topic: str,
    ) -> str:
        """
        构建综述生成提示

        Args:
            state: 聚合状态
            research_topic: 研究主题

        Returns:
            提示文本
        """
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

请撰写一篇结构完整、内容连贯的综述报告，包括引言、方法论综述、当前挑战、未来方向和结论。
请返回符合指定格式的 JSON 输出。"""

    def _parse_survey_response(self, response: ChatResponse) -> DomainSurveyOutput:
        """解析综述响应"""
        if not response.messages:
            raise ValueError("模型返回空响应")

        message = response.messages[0]
        text_content = message.text if hasattr(message, 'text') else ""

        if not text_content and message.contents:
            for content in message.contents:
                if hasattr(content, 'text') and content.text:
                    text_content = content.text
                    break

        if not text_content:
            raise ValueError("无法从响应中提取文本内容")

        try:
            cleaned_text = self._clean_json_text(text_content)
            return parse_domain_survey_output(cleaned_text)
        except Exception as e:
            raise ValueError(f"解析模型响应失败: {e}")

    def _clean_json_text(self, text: str) -> str:
        """清理 JSON 文本"""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()


# ============================================================================
# 工厂函数
# ============================================================================

def create_lead_researcher_agent(
    llm_config: LLMConfig,
    sub_agent_llm_config: Optional[LLMConfig] = None,
    max_concurrent_subsets: int = 5,
    partition_config: Optional[PartitionConfig] = None,
) -> LeadResearcherAgent:
    """
    创建首席研究员智能体

    Args:
        llm_config: 首席智能体 LLM 配置
        sub_agent_llm_config: 助理智能体 LLM 配置
        max_concurrent_subsets: 最大并发子集数
        partition_config: 分区配置

    Returns:
        初始化完成的 LeadResearcherAgent
    """
    return LeadResearcherAgent(
        name="lead_researcher",
        llm_config=llm_config,
        sub_agent_llm_config=sub_agent_llm_config,
        max_concurrent_subsets=max_concurrent_subsets,
        partition_config=partition_config,
    )


def create_sub_researcher_agent(
    llm_config: LLMConfig,
    subset_id: str,
) -> SubResearcherAgent:
    """
    创建助理研究员智能体

    Args:
        llm_config: LLM 配置
        subset_id: 子集 ID

    Returns:
        初始化完成的 SubResearcherAgent
    """
    return SubResearcherAgent(
        name=f"sub_researcher_{subset_id}",
        llm_config=llm_config,
        subset_id=subset_id,
    )
