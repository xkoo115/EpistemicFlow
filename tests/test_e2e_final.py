"""
端到端集成测试（修复版）

本测试验证核心功能，使用 Mock 对象模拟外部依赖。
"""

import pytest
import asyncio
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json
import tempfile
import os

# 兼容性处理：AsyncMock 在 Python 3.7 中不可用
try:
    from unittest.mock import AsyncMock
except ImportError:
    class AsyncMock(Mock):
        """Python 3.7 兼容的 AsyncMock"""
        async def __call__(self, *args, **kwargs):
            return super().__call__(*args, **kwargs)


# ============================================================================
# 测试固件
# ============================================================================

@pytest.fixture
def sample_domain_survey():
    """示例领域综述固件"""
    from agents.schemas import DomainSurveyOutput, PaperMetadata

    return DomainSurveyOutput(
        title="深度学习在图像分类中的应用研究",
        abstract="本文综述了深度学习技术在图像分类领域的最新进展。",
        introduction="随着深度学习技术的快速发展，图像分类任务取得了显著突破。",
        methodology_review="主流方法包括卷积神经网络、注意力机制等。",
        current_challenges=[
            "计算资源需求大",
            "小样本学习困难",
            "模型可解释性不足",
        ],
        future_directions=[
            "轻量化模型设计",
            "自监督学习",
            "多模态融合",
        ],
        conclusion="深度学习在图像分类领域展现出巨大潜力，但仍面临诸多挑战。",
        key_references=[
            PaperMetadata(
                title="Deep Residual Learning for Image Recognition",
                authors=["Kaiming He", "Xiangyu Zhang"],
                publication_year=2016,
            )
        ],
        coverage_score=0.85,
        coherence_score=0.9,
    )


# ============================================================================
# SSE 流式输出测试
# ============================================================================

class TestEventBus:
    """事件总线测试"""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        """测试订阅和发布"""
        from api.stream import EventBus, SSEEvent, EventType

        # 创建新的事件总线实例
        bus = EventBus()

        # 清空状态
        bus._subscriptions.clear()
        bus._queues.clear()

        # 订阅
        queue = await bus.subscribe("session_1")

        # 发布事件
        event = SSEEvent(
            event_type=EventType.AGENT_THOUGHT,
            session_id="session_1",
            data={"thought": "测试思考"},
        )
        await bus.publish(event)

        # 获取事件
        received = await bus.get_event("session_1", timeout=1.0)

        assert received is not None
        assert received.event_type == EventType.AGENT_THOUGHT
        assert received.data["thought"] == "测试思考"

        # 取消订阅
        await bus.unsubscribe("session_1")

    @pytest.mark.asyncio
    async def test_event_type_filter(self):
        """测试事件类型过滤"""
        from api.stream import EventBus, SSEEvent, EventType

        bus = EventBus()
        bus._subscriptions.clear()
        bus._queues.clear()

        # 订阅特定事件类型
        queue = await bus.subscribe(
            "session_2",
            event_types=[EventType.AGENT_THOUGHT],
        )

        # 发布不同类型的事件
        thought_event = SSEEvent(
            event_type=EventType.AGENT_THOUGHT,
            session_id="session_2",
            data={"thought": "思考"},
        )
        action_event = SSEEvent(
            event_type=EventType.AGENT_ACTION,
            session_id="session_2",
            data={"action": "行动"},
        )

        await bus.publish(thought_event)
        await bus.publish(action_event)

        # 只应该收到 thought 事件
        received = await bus.get_event("session_2", timeout=1.0)
        assert received.event_type == EventType.AGENT_THOUGHT

        # 不应该有更多事件
        received = await bus.get_event("session_2", timeout=0.5)
        assert received is None

        await bus.unsubscribe("session_2")

    @pytest.mark.asyncio
    async def test_event_history(self):
        """测试事件历史"""
        from api.stream import EventBus, SSEEvent, EventType

        bus = EventBus()

        # 发布多个事件
        for i in range(5):
            event = SSEEvent(
                event_type=EventType.HEARTBEAT,
                session_id="test",
                data={"count": i},
            )
            await bus.publish(event)

        # 获取历史
        history = bus.get_history(limit=3)

        assert len(history) == 3
        # 应该是最新的 3 个事件
        assert history[0].data["count"] == 2
        assert history[1].data["count"] == 3
        assert history[2].data["count"] == 4


# ============================================================================
# 数据模型测试
# ============================================================================

class TestDataModels:
    """数据模型测试"""

    def test_domain_survey_output(self, sample_domain_survey):
        """测试领域综述输出模型"""
        assert sample_domain_survey.title == "深度学习在图像分类中的应用研究"
        assert len(sample_domain_survey.current_challenges) == 3
        assert len(sample_domain_survey.future_directions) == 3
        assert sample_domain_survey.coverage_score == 0.85

    def test_paper_metadata(self):
        """测试论文元数据模型"""
        from agents.schemas import PaperMetadata, LiteratureSource

        paper = PaperMetadata(
            title="Test Paper",
            authors=["Author 1", "Author 2"],
            abstract="This is a test abstract.",
            publication_year=2024,
            venue="Test Conference",
            source=LiteratureSource.ARXIV,
            relevance_score=0.9,
        )

        assert paper.title == "Test Paper"
        assert len(paper.authors) == 2
        assert paper.publication_year == 2024
        assert paper.source == LiteratureSource.ARXIV

    def test_ideation_output(self):
        """测试构思输出模型"""
        from agents.schemas import IdeationOutput, PaperType, ClassificationReasoning

        output = IdeationOutput(
            paper_type=PaperType.RESEARCH_PAPER,
            confidence=0.85,
            reasoning=ClassificationReasoning(
                key_indicators=["提出新方法"],
                reasoning_steps=["步骤1", "步骤2"],
                confidence_factors=["明确的创新点"],
            ),
            research_topic="深度学习图像分类",
            keywords=["深度学习", "图像分类"],
            input_summary="用户希望研究新的图像分类方法",
        )

        assert output.paper_type == PaperType.RESEARCH_PAPER
        assert output.confidence == 0.85
        assert len(output.keywords) == 2


# ============================================================================
# 配置测试
# ============================================================================

class TestConfig:
    """配置测试"""

    def test_settings_load(self):
        """测试配置加载"""
        from core.config import settings

        assert settings.app is not None
        assert settings.database is not None
        assert settings.default_llm is not None

    def test_llm_config(self):
        """测试 LLM 配置"""
        from core.config import LLMConfig, LLMProvider

        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test_key",
            model_name="gpt-4",
            temperature=0.7,
        )

        assert config.provider == LLMProvider.OPENAI
        assert config.model_name == "gpt-4"
        assert config.temperature == 0.7

    def test_environment_enum(self):
        """测试环境枚举"""
        from core.config import Environment

        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.TESTING.value == "testing"
        assert Environment.PRODUCTION.value == "production"


# ============================================================================
# VLM 审查模型测试
# ============================================================================

class TestVLMModels:
    """VLM 审查模型测试"""

    def test_figure_review_output(self):
        """测试图表审查输出模型"""
        from agents.vlm_review import (
            FigureReviewOutput,
            FigureReviewScore,
            ReviewVerdict,
            FigureType,
            ReviewAspect,
        )

        review = FigureReviewOutput(
            figure_id="fig1",
            figure_type=FigureType.LINE_CHART,
            scores=[
                FigureReviewScore(
                    aspect=ReviewAspect.AESTHETICS,
                    score=8.0,
                    rationale="配色协调",
                )
            ],
            overall_score=8.0,
            verdict=ReviewVerdict.ACCEPT,
            strengths=["清晰的标签"],
            weaknesses=["缺少误差棒"],
        )

        assert review.figure_id == "fig1"
        assert review.overall_score == 8.0
        assert review.verdict == ReviewVerdict.ACCEPT

    def test_polished_manuscript(self):
        """测试润色手稿模型"""
        from agents.vlm_review import PolishedManuscript, ManuscriptSection

        manuscript = PolishedManuscript(
            title="测试论文",
            abstract="这是摘要",
            sections=[
                ManuscriptSection(
                    section_id="intro",
                    title="引言",
                    content="引言内容",
                    order=1,
                )
            ],
            conclusion="这是结论",
            total_word_count=1000,
            coherence_score=0.9,
            academic_style_score=0.85,
        )

        assert manuscript.title == "测试论文"
        assert len(manuscript.sections) == 1
        assert manuscript.coherence_score == 0.9


# ============================================================================
# 同行评审模型测试
# ============================================================================

class TestReviewerModels:
    """同行评审模型测试"""

    def test_reviewer_comment(self):
        """测试审稿人意见模型"""
        from agents.reviewers import (
            ReviewerComment,
            AspectScore,
            ReviewDecision,
            ReviewerRole,
        )

        comment = ReviewerComment(
            reviewer_id="reviewer_1",
            reviewer_role=ReviewerRole.NOVELTY_REVIEWER,
            aspect_scores=[
                AspectScore(
                    aspect="新颖性",
                    score=8.0,
                    rationale="有创新点",
                )
            ],
            overall_score=8.0,
            decision=ReviewDecision.ACCEPT,
            confidence=0.9,
            strengths=["创新性强"],
            weaknesses=["实验不足"],
        )

        assert comment.reviewer_role == ReviewerRole.NOVELTY_REVIEWER
        assert comment.overall_score == 8.0
        assert comment.decision == ReviewDecision.ACCEPT

    def test_peer_review_report(self):
        """测试同行评审报告模型"""
        from agents.reviewers import PeerReviewReport, ReviewDecision

        report = PeerReviewReport(
            manuscript_id="paper_001",
            manuscript_title="测试论文",
            review_start_timestamp="2024-01-01T00:00:00",
            average_score=8.0,
            consensus_level=0.9,
            editor_decision=ReviewDecision.ACCEPT,
        )

        assert report.manuscript_id == "paper_001"
        assert report.average_score == 8.0
        assert report.editor_decision == ReviewDecision.ACCEPT


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
