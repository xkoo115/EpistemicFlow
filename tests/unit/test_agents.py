"""
智能体模块异步单元测试

本测试模块提供：
- Pydantic 分类器测试
- 并发 Map-Reduce 任务分配逻辑测试
- Mock 机制（Mock 掉底层 Model Client 网络请求）

关键设计：
- 使用 pytest-asyncio 支持异步测试
- Mock ChatResponse 避免实际 API 调用
- 验证并发生成的 SubResearcherAgent 数量
- 验证最终状态聚合（Reduce）逻辑的正确性
"""

import pytest
import asyncio
from typing import Any, Dict, List, Optional, Sequence
from unittest.mock import AsyncMock, MagicMock, patch
import json

from agent_framework import (
    ChatResponse,
    Message,
    Content,
)

from agents.base import (
    ModelClientFactory,
    SessionManager,
    AgentSessionInfo,
    ResearchContextProvider,
)
from agents.schemas import (
    PaperType,
    ClassificationReasoning,
    IdeationOutput,
    PaperMetadata,
    LiteratureSubset,
    SubResearcherOutput,
    AggregatedResearchState,
    DomainSurveyOutput,
    parse_ideation_output,
)
from agents.ideation import IdeationAgent, IdeationBatchProcessor
from agents.research import (
    PartitionConfig,
    TaskDistributor,
    SubResearcherAgent,
    LeadResearcherAgent,
)
from core.config import LLMConfig, LLMProvider


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_config() -> LLMConfig:
    """Mock LLM 配置"""
    return LLMConfig(
        provider=LLMProvider.OPENAI,
        api_key="test-api-key",
        base_url="http://localhost:8080",
        model_name="gpt-4",
        temperature=0.7,
        max_tokens=1000,
    )


@pytest.fixture
def mock_ideation_output() -> Dict[str, Any]:
    """Mock 构思输出 JSON"""
    return {
        "paper_type": "research_paper",
        "confidence": 0.85,
        "reasoning": {
            "key_indicators": ["提出新方法", "包含实验设计"],
            "reasoning_steps": [
                "1. 分析用户输入，识别关键意图",
                "2. 发现'提出一种新的深度学习架构'，表明是原创研究",
            ],
            "confidence_factors": ["明确的创新点"],
        },
        "research_topic": "基于注意力机制的图像分类方法研究",
        "keywords": ["深度学习", "注意力机制", "图像分类"],
        "research_questions": ["如何设计更高效的注意力机制？"],
        "input_summary": "用户希望研究一种新的图像分类方法",
    }


@pytest.fixture
def mock_sub_researcher_output() -> Dict[str, Any]:
    """Mock 助理研究员输出 JSON"""
    return {
        "subset_id": "subset_0",
        "agent_id": "sub_researcher_subset_0",
        "key_findings": [
            "注意力机制显著提升了模型性能",
            "多头注意力能够捕获不同层次的特征",
        ],
        "methodologies": [
            "Transformer 架构",
            "自注意力机制",
        ],
        "research_gaps": [
            "计算复杂度仍然较高",
        ],
        "trends": [
            "轻量化注意力机制设计",
        ],
        "papers_analyzed": 5,
        "confidence": 0.8,
        "raw_summary": "分析了 5 篇关于注意力机制的论文",
    }


@pytest.fixture
def sample_papers() -> List[PaperMetadata]:
    """示例论文列表"""
    papers = []
    for i in range(20):
        paper = PaperMetadata(
            title=f"论文 {i + 1}: 关于深度学习的研究",
            authors=[f"作者 {j + 1}" for j in range(3)],
            abstract=f"这是第 {i + 1} 篇论文的摘要，讨论了深度学习在图像处理中的应用。",
            publication_year=2020 + (i % 5),
            venue="ICML" if i % 2 == 0 else "NeurIPS",
            relevance_score=0.8 - (i * 0.01),
        )
        papers.append(paper)
    return papers


# ============================================================================
# Mock 辅助函数
# ============================================================================

def create_mock_chat_response(json_output: Dict[str, Any]) -> ChatResponse:
    """
    创建 Mock ChatResponse

    模拟模型返回的 JSON 响应，避免实际 API 调用。

    Args:
        json_output: 要返回的 JSON 数据

    Returns:
        Mock 的 ChatResponse 对象
    """
    json_str = json.dumps(json_output, ensure_ascii=False)
    message = Message(
        role="assistant",
        contents=[Content.from_text(json_str)],
    )
    return ChatResponse(
        messages=[message],
        finish_reason="stop",
        model_id="gpt-4",
    )


def create_mock_chat_response_with_text(text: str) -> ChatResponse:
    """创建包含文本的 Mock ChatResponse"""
    message = Message(
        role="assistant",
        contents=[Content.from_text(text)],
    )
    return ChatResponse(
        messages=[message],
        finish_reason="stop",
        model_id="gpt-4",
    )


# ============================================================================
# Pydantic 分类器测试
# ============================================================================

class TestPydanticSchemas:
    """Pydantic 模型测试"""

    def test_paper_type_enum(self):
        """测试论文类型枚举"""
        assert PaperType.RESEARCH_PAPER.value == "research_paper"
        assert PaperType.SURVEY_PAPER.value == "survey_paper"

    def test_ideation_output_validation(self, mock_ideation_output):
        """测试 IdeationOutput 模型验证"""
        output = IdeationOutput.model_validate(mock_ideation_output)

        assert output.paper_type == PaperType.RESEARCH_PAPER
        assert output.confidence == 0.85
        assert output.research_topic == "基于注意力机制的图像分类方法研究"
        assert len(output.keywords) == 3
        assert "深度学习" in output.keywords

    def test_ideation_output_research_paper(self, mock_ideation_output):
        """测试研究论文分类"""
        output = IdeationOutput.model_validate(mock_ideation_output)
        assert output.paper_type == PaperType.RESEARCH_PAPER
        assert output.research_questions is not None

    def test_ideation_output_survey_paper(self):
        """测试综述论文分类"""
        survey_data = {
            "paper_type": "survey_paper",
            "confidence": 0.9,
            "reasoning": {
                "key_indicators": ["系统性综述", "对比分析"],
                "reasoning_steps": ["识别为综述研究"],
                "confidence_factors": ["明确的综述意图"],
            },
            "research_topic": "深度学习综述",
            "keywords": ["深度学习", "综述"],
            "survey_scope": "2018-2023 年深度学习发展",
            "input_summary": "用户希望综述深度学习领域",
        }
        output = IdeationOutput.model_validate(survey_data)
        assert output.paper_type == PaperType.SURVEY_PAPER
        assert output.survey_scope is not None

    def test_classification_reasoning(self):
        """测试分类推理模型"""
        reasoning = ClassificationReasoning(
            key_indicators=["指标1", "指标2"],
            reasoning_steps=["步骤1", "步骤2"],
            confidence_factors=["因素1"],
        )
        assert len(reasoning.key_indicators) == 2
        assert len(reasoning.reasoning_steps) == 2

    def test_sub_researcher_output_validation(self, mock_sub_researcher_output):
        """测试 SubResearcherOutput 模型验证"""
        output = SubResearcherOutput.model_validate(mock_sub_researcher_output)

        assert output.subset_id == "subset_0"
        assert len(output.key_findings) == 2
        assert len(output.methodologies) == 2
        assert output.papers_analyzed == 5
        assert output.confidence == 0.8

    def test_paper_metadata(self):
        """测试论文元数据模型"""
        paper = PaperMetadata(
            title="测试论文",
            authors=["作者1", "作者2"],
            abstract="这是摘要",
            publication_year=2023,
            venue="ICML",
        )
        assert paper.title == "测试论文"
        assert len(paper.authors) == 2
        assert paper.publication_year == 2023


# ============================================================================
# 任务分发器测试
# ============================================================================

class TestTaskDistributor:
    """任务分发器测试"""

    def test_distribute_evenly(self, sample_papers):
        """测试均匀分割"""
        config = PartitionConfig(
            max_papers_per_subset=5,
            balance_by_tokens=False,
        )
        distributor = TaskDistributor(config)
        subsets = distributor.distribute(sample_papers)

        # 验证子集数量
        assert len(subsets) == 4  # 20 papers / 5 per subset

        # 验证每子集论文数
        for subset in subsets:
            assert len(subset.papers) <= 5

        # 验证总论文数
        total_papers = sum(len(s.papers) for s in subsets)
        assert total_papers == 20

    def test_distribute_by_tokens(self, sample_papers):
        """测试按 Token 平衡分割"""
        config = PartitionConfig(
            max_papers_per_subset=10,
            balance_by_tokens=True,
        )
        distributor = TaskDistributor(config)
        subsets = distributor.distribute(sample_papers)

        # 验证子集不为空
        assert len(subsets) > 0

        # 验证每子集都有 estimated_tokens
        for subset in subsets:
            assert subset.estimated_tokens is not None
            assert subset.estimated_tokens >= 0

    def test_distribute_empty_papers(self):
        """测试空论文列表"""
        config = PartitionConfig()
        distributor = TaskDistributor(config)
        subsets = distributor.distribute([])

        assert len(subsets) == 0

    def test_distribute_small_collection(self):
        """测试小规模论文集"""
        papers = [
            PaperMetadata(title="论文1", authors=["作者1"]),
            PaperMetadata(title="论文2", authors=["作者2"]),
        ]
        config = PartitionConfig(
            max_papers_per_subset=5,
            min_papers_per_subset=1,
        )
        distributor = TaskDistributor(config)
        subsets = distributor.distribute(papers)

        # 小于 max_papers_per_subset，应该只有一个子集
        assert len(subsets) == 1
        assert len(subsets[0].papers) == 2

    def test_max_subsets_limit(self, sample_papers):
        """测试最大子集数限制"""
        config = PartitionConfig(
            max_papers_per_subset=2,  # 理论上会产生 10 个子集
            max_subsets=3,  # 但限制为 3 个
        )
        distributor = TaskDistributor(config)
        subsets = distributor.distribute(sample_papers)

        assert len(subsets) <= 3


# ============================================================================
# 会话管理器测试
# ============================================================================

class TestSessionManager:
    """会话管理器测试"""

    @pytest.mark.asyncio
    async def test_create_session(self):
        """测试会话创建"""
        manager = SessionManager()
        session = await manager.create_session("test_agent")

        assert session.session_id is not None
        assert session.state is not None

    @pytest.mark.asyncio
    async def test_session_state_isolation(self):
        """测试会话状态隔离"""
        manager = SessionManager()

        # 创建两个会话
        session1 = await manager.create_session("agent1", {"key": "value1"})
        session2 = await manager.create_session("agent2", {"key": "value2"})

        # 验证状态隔离
        assert session1.state.get("key") == "value1"
        assert session2.state.get("key") == "value2"

        # 修改一个会话不影响另一个
        session1.state["new_key"] = "new_value"
        assert "new_key" not in session2.state

    @pytest.mark.asyncio
    async def test_update_session_state(self):
        """测试会话状态更新"""
        manager = SessionManager()
        session = await manager.create_session("test_agent")

        # 更新状态
        success = await manager.update_session_state(
            session.session_id,
            {"updated_key": "updated_value"},
        )
        assert success is True

        # 验证更新
        session_info = await manager.get_session(session.session_id)
        assert session_info.state.get("updated_key") == "updated_value"

    @pytest.mark.asyncio
    async def test_close_session(self):
        """测试会话关闭"""
        manager = SessionManager()
        session = await manager.create_session("test_agent")

        # 关闭会话
        success = await manager.close_session(session.session_id)
        assert success is True

        # 验证会话已删除
        session_info = await manager.get_session(session.session_id)
        assert session_info is None

    @pytest.mark.asyncio
    async def test_session_count(self):
        """测试会话计数"""
        manager = SessionManager()

        # 初始为 0
        count = await manager.get_session_count()
        assert count == 0

        # 创建会话
        await manager.create_session("agent1")
        await manager.create_session("agent2")

        count = await manager.get_session_count()
        assert count == 2


# ============================================================================
# 上下文提供者测试
# ============================================================================

class TestResearchContextProvider:
    """科研上下文提供者测试"""

    def test_context_provider_creation(self):
        """测试上下文提供者创建"""
        provider = ResearchContextProvider(
            research_topic="深度学习研究",
            collected_papers=[{"title": "论文1"}],
        )

        assert provider.research_topic == "深度学习研究"
        assert len(provider.collected_papers) == 1

    def test_add_papers(self):
        """测试添加论文"""
        provider = ResearchContextProvider()
        provider.add_paper({"title": "论文1"})
        provider.add_papers([{"title": "论文2"}, {"title": "论文3"}])

        assert len(provider.collected_papers) == 3

    def test_workflow_state(self):
        """测试工作流状态"""
        provider = ResearchContextProvider()
        provider.update_workflow_state("stage", "analysis")
        provider.update_workflow_state("progress", 0.5)

        assert provider.get_workflow_state("stage") == "analysis"
        assert provider.get_workflow_state("progress") == 0.5

    def test_to_context_messages(self):
        """测试转换为上下文消息"""
        provider = ResearchContextProvider(
            research_topic="测试主题",
            collected_papers=[{"title": "论文1"}, {"title": "论文2"}],
        )

        messages = provider.to_context_messages()
        assert len(messages) == 1
        assert messages[0].role == "system"


# ============================================================================
# IdeationAgent 测试 (使用 Mock)
# ============================================================================

class TestIdeationAgent:
    """构思智能体测试"""

    @pytest.mark.asyncio
    async def test_ideation_agent_creation(self, mock_llm_config):
        """测试智能体创建"""
        agent = IdeationAgent(
            name="test_ideation",
            llm_config=mock_llm_config,
        )

        assert agent.name == "test_ideation"
        assert agent.agent is not None

        await agent.close()

    @pytest.mark.asyncio
    async def test_ideation_agent_analyze(
        self,
        mock_llm_config,
        mock_ideation_output,
    ):
        """测试意图分析（使用 Mock）"""
        # 创建 Mock 响应
        mock_response = create_mock_chat_response(mock_ideation_output)

        # 创建智能体
        agent = IdeationAgent(
            name="test_ideation",
            llm_config=mock_llm_config,
        )

        # Mock send_message 方法
        with patch.object(
            agent,
            'send_message',
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await agent.analyze("我想研究一种新的深度学习方法")

            # 验证结果
            assert result.paper_type == PaperType.RESEARCH_PAPER
            assert result.confidence == 0.85
            assert "深度学习" in result.keywords

        await agent.close()

    @pytest.mark.asyncio
    async def test_ideation_agent_classify_only(
        self,
        mock_llm_config,
        mock_ideation_output,
    ):
        """测试仅分类"""
        mock_response = create_mock_chat_response(mock_ideation_output)

        agent = IdeationAgent(
            name="test_ideation",
            llm_config=mock_llm_config,
        )

        with patch.object(
            agent,
            'send_message',
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            paper_type = await agent.classify_only("研究新方法")

            assert paper_type == PaperType.RESEARCH_PAPER

        await agent.close()

    @pytest.mark.asyncio
    async def test_ideation_agent_survey_classification(
        self,
        mock_llm_config,
    ):
        """测试综述分类"""
        survey_output = {
            "paper_type": "survey_paper",
            "confidence": 0.9,
            "reasoning": {
                "key_indicators": ["综述"],
                "reasoning_steps": ["识别为综述"],
                "confidence_factors": ["明确意图"],
            },
            "research_topic": "深度学习综述",
            "keywords": ["深度学习"],
            "input_summary": "综述深度学习",
        }
        mock_response = create_mock_chat_response(survey_output)

        agent = IdeationAgent(
            name="test_ideation",
            llm_config=mock_llm_config,
        )

        with patch.object(
            agent,
            'send_message',
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await agent.analyze("我想综述深度学习领域的发展")

            assert result.paper_type == PaperType.SURVEY_PAPER

        await agent.close()


# ============================================================================
# Map-Reduce 架构测试
# ============================================================================

class TestMapReduceArchitecture:
    """Map-Reduce 架构测试"""

    @pytest.mark.asyncio
    async def test_sub_researcher_count(
        self,
        mock_llm_config,
        sample_papers,
    ):
        """
        测试并发生成的 SubResearcherAgent 数量

        验证 Map 阶段正确创建指定数量的助理智能体。
        """
        # 配置分区
        config = PartitionConfig(
            max_papers_per_subset=5,
            max_subsets=4,
        )
        distributor = TaskDistributor(config)
        subsets = distributor.distribute(sample_papers)

        # 验证子集数量
        assert len(subsets) == 4

        # 为每个子集创建助理智能体
        sub_agents = []
        for subset in subsets:
            agent = SubResearcherAgent(
                name=f"sub_agent_{subset.subset_id}",
                llm_config=mock_llm_config,
                subset_id=subset.subset_id,
            )
            sub_agents.append(agent)

        # 验证智能体数量
        assert len(sub_agents) == 4

        # 清理
        for agent in sub_agents:
            await agent.close()

    @pytest.mark.asyncio
    async def test_concurrent_subset_processing(
        self,
        mock_llm_config,
        sample_papers,
        mock_sub_researcher_output,
    ):
        """
        测试并发子集处理

        验证 asyncio.gather 正确并发执行多个子集分析。
        """
        config = PartitionConfig(
            max_papers_per_subset=5,
            max_subsets=4,
        )
        distributor = TaskDistributor(config)
        subsets = distributor.distribute(sample_papers)

        # 创建 Mock 响应
        mock_response = create_mock_chat_response(mock_sub_researcher_output)

        # 记录执行顺序
        execution_order = []

        async def mock_analyze_subset(subset, topic):
            execution_order.append(subset.subset_id)
            return SubResearcherOutput.model_validate(mock_sub_researcher_output)

        # 并发执行
        tasks = [
            mock_analyze_subset(subset, "测试主题")
            for subset in subsets
        ]
        results = await asyncio.gather(*tasks)

        # 验证结果数量
        assert len(results) == 4

        # 验证所有子集都被处理
        assert len(execution_order) == 4

    @pytest.mark.asyncio
    async def test_reduce_aggregation(
        self,
        mock_llm_config,
        sample_papers,
    ):
        """
        测试 Reduce 阶段聚合逻辑

        验证所有助理智能体的结果正确聚合为全局状态。
        """
        # 创建模拟的子结果
        sub_results = []
        for i in range(4):
            result = SubResearcherOutput(
                subset_id=f"subset_{i}",
                agent_id=f"agent_{i}",
                key_findings=[f"发现 {i}_1", f"发现 {i}_2"],
                methodologies=[f"方法 {i}"],
                research_gaps=[f"空白 {i}"],
                trends=[f"趋势 {i}"],
                papers_analyzed=5,
                confidence=0.8,
            )
            sub_results.append(result)

        # 模拟聚合逻辑
        all_findings = []
        all_methodologies = []
        all_gaps = []
        all_trends = []

        for result in sub_results:
            all_findings.extend(result.key_findings)
            all_methodologies.extend(result.methodologies)
            all_gaps.extend(result.research_gaps)
            all_trends.extend(result.trends)

        # 去重
        unique_findings = list(dict.fromkeys(all_findings))

        # 验证聚合结果
        assert len(unique_findings) == 8  # 4 subsets * 2 findings
        assert len(all_methodologies) == 4
        assert len(all_gaps) == 4
        assert len(all_trends) == 4

    @pytest.mark.asyncio
    async def test_lead_researcher_creation(
        self,
        mock_llm_config,
    ):
        """测试首席研究员智能体创建"""
        agent = LeadResearcherAgent(
            name="test_lead",
            llm_config=mock_llm_config,
            max_concurrent_subsets=3,
        )

        assert agent.name == "test_lead"
        assert agent._max_concurrent_subsets == 3

        await agent.close()


# ============================================================================
# 模型客户端工厂测试
# ============================================================================

class TestModelClientFactory:
    """模型客户端工厂测试"""

    def test_create_client(self, mock_llm_config):
        """测试客户端创建"""
        client = ModelClientFactory.create_client(mock_llm_config)
        assert client is not None

    def test_client_caching(self, mock_llm_config):
        """测试客户端缓存"""
        # 清空缓存
        ModelClientFactory.clear_cache()

        # 创建客户端（带缓存键）
        client1 = ModelClientFactory.create_client(
            mock_llm_config,
            cache_key="test_key",
        )
        client2 = ModelClientFactory.create_client(
            mock_llm_config,
            cache_key="test_key",
        )

        # 应该返回同一个实例
        assert client1 is client2

    def test_get_chat_options(self, mock_llm_config):
        """测试获取聊天选项"""
        options = ModelClientFactory.get_chat_options(mock_llm_config)

        assert options["temperature"] == 0.7
        assert options["max_tokens"] == 1000

    def test_get_chat_options_with_response_format(self, mock_llm_config):
        """测试带响应格式的聊天选项"""
        response_format = {"type": "json_object"}
        options = ModelClientFactory.get_chat_options(
            mock_llm_config,
            response_format=response_format,
        )

        assert "response_format" in options
        assert options["response_format"]["type"] == "json_object"


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""

    def test_empty_keywords(self):
        """测试空关键词"""
        output = IdeationOutput(
            paper_type=PaperType.RESEARCH_PAPER,
            confidence=0.5,
            reasoning=ClassificationReasoning(),
            research_topic="测试主题",
            keywords=[],
            input_summary="测试",
        )
        assert len(output.keywords) == 0

    def test_low_confidence(self):
        """测试低置信度"""
        output = IdeationOutput(
            paper_type=PaperType.RESEARCH_PAPER,
            confidence=0.1,  # 低置信度
            reasoning=ClassificationReasoning(),
            research_topic="测试主题",
            keywords=["测试"],
            input_summary="测试",
        )
        assert output.confidence < 0.5

    @pytest.mark.asyncio
    async def test_single_paper_subset(self):
        """测试单论文子集"""
        papers = [PaperMetadata(title="单篇论文", authors=["作者"])]
        config = PartitionConfig(max_papers_per_subset=10)
        distributor = TaskDistributor(config)
        subsets = distributor.distribute(papers)

        assert len(subsets) == 1
        assert len(subsets[0].papers) == 1

    def test_json_parsing_with_markdown(self):
        """测试带 Markdown 标记的 JSON 解析"""
        json_with_markdown = """```json
{"paper_type": "research_paper", "confidence": 0.8, "reasoning": {"key_indicators": [], "reasoning_steps": [], "confidence_factors": []}, "research_topic": "测试", "keywords": [], "input_summary": "测试"}
```"""
        # 清理 Markdown
        cleaned = json_with_markdown.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # 解析
        data = json.loads(cleaned)
        assert data["paper_type"] == "research_paper"
