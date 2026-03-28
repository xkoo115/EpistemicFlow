"""
端到端集成测试

本测试验证从代码生成、沙箱执行、VLM 审查到多智能体评审的完整链路。

测试覆盖：
1. 沙箱执行与自愈机制
2. VLM 图表审查
3. 润色与整合
4. 同行评审委员会
5. SSE 流式输出
6. 完整工作流集成

使用 Mock 对象模拟外部依赖（Docker、LLM API），确保测试可重复执行。
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

# 导入被测模块
from core.sandbox import (
    DockerSandbox,
    SandboxConfig,
    ExecutionResult,
    SandboxStatus,
    DebuggingAgent,
)
from agents.base import ModelClientFactory
from agents.vlm_review import (
    VLMFigureReviewer,
    IntegrationPolishingAgent,
    FigureReviewOutput,
    PolishedManuscript,
    ReviewVerdict,
    FigureType,
)
from agents.reviewers import (
    PeerReviewCommittee,
    PeerReviewReport,
    ReviewDecision,
    ReviewerRole,
)
from agents.schemas import (
    DomainSurveyOutput,
    PaperMetadata,
)
from api.stream import (
    EventBus,
    SSEEvent,
    EventType,
    EventPriority,
    event_bus,
)


# ============================================================================
# Mock 对象工厂
# ============================================================================

class MockDockerClient:
    """Mock Docker 客户端"""

    def __init__(self, should_fail: bool = False, fail_times: int = 0):
        """
        初始化 Mock Docker 客户端

        Args:
            should_fail: 是否应该失败
            fail_times: 失败次数（用于测试自愈机制）
        """
        self.should_fail = should_fail
        self.fail_times = fail_times
        self.call_count = 0
        self._containers = MockContainersManager(self)

    @property
    def containers(self):
        return self._containers

    def ping(self):
        """健康检查"""
        return True

    def images(self):
        """镜像管理"""
        return MockImagesManager()


class MockContainersManager:
    """Mock 容器管理器"""

    def __init__(self, client: MockDockerClient):
        self._client = client

    def run(self, **kwargs) -> 'MockContainer':
        """运行容器"""
        return MockContainer(self._client)

    def get(self, container_id: str) -> 'MockContainer':
        """获取容器"""
        return MockContainer(self._client)


class MockImagesManager:
    """Mock 镜像管理器"""

    def pull(self, image_name: str):
        """拉取镜像"""
        pass


class MockContainer:
    """Mock 容器"""

    def __init__(self, client: MockDockerClient):
        self._client = client
        self._status = "running"
        self._exit_code = 0
        self._stdout = []
        self._stderr = []

    def reload(self):
        """重新加载状态"""
        self._client.call_count += 1

        # 模拟失败场景
        if self._client.should_fail or self._client.call_count <= self._client.fail_times:
            self._status = "exited"
            self._exit_code = 1
            self._stderr = ["Error: NameError: name 'x' is not defined"]
        else:
            self._status = "exited"
            self._exit_code = 0
            self._stdout = ["Hello, World!", "Execution completed successfully"]

    @property
    def status(self):
        return self._status

    @property
    def attrs(self):
        return {
            "State": {
                "ExitCode": self._exit_code,
            }
        }

    def logs(self, stdout=True, stderr=True, stream=False):
        """获取日志"""
        if stream:
            # 返回生成器
            def log_generator():
                if stdout:
                    for line in self._stdout:
                        yield line.encode("utf-8")
                if stderr:
                    for line in self._stderr:
                        yield line.encode("utf-8")
            return log_generator()
        else:
            if stdout and not stderr:
                return "\n".join(self._stdout).encode("utf-8")
            elif stderr and not stdout:
                return "\n".join(self._stderr).encode("utf-8")
            else:
                return ("\n".join(self._stdout) + "\n".join(self._stderr)).encode("utf-8")

    def wait(self, timeout: int = None):
        """等待容器完成"""
        pass

    def stop(self, timeout: int = None):
        """停止容器"""
        self._status = "exited"

    def remove(self, force: bool = False):
        """删除容器"""
        pass

    def stats(self, stream: bool = False):
        """获取统计信息"""
        return {
            "memory_stats": {"max_usage": 100 * 1024 * 1024},  # 100 MB
            "cpu_stats": {"cpu_usage": {"total_usage": 1000000000}},
            "precpu_stats": {"cpu_usage": {"total_usage": 0}},
        }


class MockLLMClient:
    """Mock LLM 客户端"""

    def __init__(self, response_type: str = "success"):
        """
        初始化 Mock LLM 客户端

        Args:
            response_type: 响应类型（success, error, custom）
        """
        self._response_type = response_type

    async def get_response(self, messages, options=None):
        """获取响应"""
        from agent_framework import Message, Content, ChatResponse

        if self._response_type == "success":
            # 返回成功响应
            content = self._get_success_content(messages)
            return ChatResponse(
                messages=[Message(role="assistant", contents=[Content.from_text(content)])],
                finish_reason="stop",
            )
        elif self._response_type == "error":
            # 返回错误响应
            return ChatResponse(
                messages=[Message(role="assistant", contents=[Content.from_text("{}")])],
                finish_reason="stop",
            )
        else:
            return ChatResponse(
                messages=[],
                finish_reason="stop",
            )

    def _get_success_content(self, messages) -> str:
        """根据消息内容生成成功响应"""
        # 检查消息内容，判断需要返回什么类型的响应
        message_text = ""
        figure_id = None
        for msg in messages:
            for content in msg.contents:
                if hasattr(content, 'text') and content.text:
                    message_text += content.text
                    # 尝试从消息中提取 figure_id
                    import re
                    match = re.search(r'图表 ID[：:]\s*(\S+)', content.text)
                    if match:
                        figure_id = match.group(1)

        # 根据关键词判断响应类型
        if "调试" in message_text or "debug" in message_text.lower():
            return self._get_debug_response()
        elif "图表 ID" in message_text or ("图表" in message_text and "审查" in message_text and "润色" not in message_text and "整合" not in message_text):
            return self._get_figure_review_response(figure_id)
        elif ("学术论文" in message_text and "评审" in message_text) or "决策" in message_text:
            return self._get_peer_review_response()
        elif "润色" in message_text or "polish" in message_text.lower() or "整合" in message_text:
            return self._get_polish_response()
        else:
            return "{}"

    def _get_figure_review_response(self, figure_id: str = None) -> str:
        """获取图表审查响应"""
        response = {
            "figure_id": figure_id or "test_figure",
            "figure_type": "line_chart",
            "scores": [
                {
                    "aspect": "aesthetics",
                    "score": 8.0,
                    "rationale": "配色协调，布局合理",
                    "suggestions": ["可以增加图例说明"],
                }
            ],
            "overall_score": 8.0,
            "verdict": "accept",
            "strengths": ["清晰的标签", "良好的配色"],
            "weaknesses": ["缺少误差棒"],
            "improvement_suggestions": ["添加误差棒", "增加图例"],
            "has_proper_labels": True,
            "has_legend": False,
            "has_error_bars": False,
            "colorblind_friendly": True,
        }
        return json.dumps(response, ensure_ascii=False)

    def _get_peer_review_response(self) -> str:
        """获取同行评审响应"""
        response = {
            "reviewer_id": "reviewer_001",
            "reviewer_role": "novelty_reviewer",
            "aspect_scores": [
                {
                    "aspect": "novelty",
                    "score": 8.5,
                    "rationale": "研究问题具有较好的新颖性"
                }
            ],
            "overall_score": 8.0,
            "decision": "accept",
            "confidence": 0.9,
            "strengths": ["研究问题新颖", "方法创新"],
            "weaknesses": ["实验数据有限"],
            "specific_comments": ["建议增加更多实验验证"],
            "suggestions": ["扩大实验范围", "增加对比实验"]
        }
        return json.dumps(response, ensure_ascii=False)

    def _get_polish_response(self) -> str:
        """获取润色响应"""
        response = {
            "title": "测试论文标题",
            "abstract": "这是润色后的摘要。",
            "sections": [
                {
                    "section_id": "intro",
                    "title": "引言",
                    "content": "这是润色后的引言内容。",
                    "order": 1,
                    "word_count": 100,
                    "figures": [],
                    "references": [],
                }
            ],
            "conclusion": "这是润色后的结论。",
            "total_word_count": 500,
            "coherence_score": 0.9,
            "academic_style_score": 0.85,
        }
        return json.dumps(response, ensure_ascii=False)

    def _get_debug_response(self) -> str:
        """获取调试响应"""
        return """```python
# 修复后的代码
x = 10
print(f"Hello, World! x = {x}")
print("Execution completed successfully")
```"""


# ============================================================================
# 测试固件
# ============================================================================

@pytest.fixture
def mock_docker_client():
    """Mock Docker 客户端固件"""
    return MockDockerClient()


@pytest.fixture
def mock_llm_client():
    """Mock LLM 客户端固件"""
    return MockLLMClient()


@pytest.fixture
def mock_llm_config():
    """Mock LLM 配置固件"""
    from core.config import LLMConfig, LLMProvider
    return LLMConfig(
        provider=LLMProvider.OPENAI,
        api_key="test_key",
        model_name="gpt-4",
    )


@pytest.fixture
def sample_domain_survey():
    """示例领域综述固件"""
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


@pytest.fixture
def sample_polished_manuscript():
    """示例润色手稿固件"""
    return PolishedManuscript(
        title="深度学习在图像分类中的应用研究",
        abstract="本文综述了深度学习技术在图像分类领域的最新进展。",
        sections=[
            {
                "section_id": "intro",
                "title": "引言",
                "content": "随着深度学习技术的快速发展，图像分类任务取得了显著突破。",
                "order": 1,
                "word_count": 100,
            }
        ],
        conclusion="深度学习在图像分类领域展现出巨大潜力。",
        total_word_count=500,
        coherence_score=0.9,
        academic_style_score=0.85,
    )


# ============================================================================
# 沙箱执行测试
# ============================================================================

class TestDockerSandbox:
    """Docker 沙箱测试"""

    @pytest.mark.asyncio
    async def test_sandbox_execute_success(self, mock_docker_client, mock_llm_config):
        """测试沙箱成功执行"""
        with patch('docker.from_env', return_value=mock_docker_client):
            sandbox = DockerSandbox(
                config=SandboxConfig(timeout=60),
                llm_config=mock_llm_config,
            )

            result = await sandbox.execute(
                code="print('Hello, World!')",
            )

            assert result.status == SandboxStatus.SUCCESS
            assert result.exit_code == 0
            assert "Hello, World!" in result.stdout

    @pytest.mark.asyncio
    async def test_sandbox_execute_with_debugging(
        self,
        mock_llm_config,
    ):
        """测试沙箱执行失败后的自愈机制"""
        # 创建会失败的 Mock 客户端
        mock_client = MockDockerClient(fail_times=1)

        with patch('docker.from_env', return_value=mock_client):
            with patch.object(
                ModelClientFactory,
                'create_client',
                return_value=MockLLMClient()
            ):
                sandbox = DockerSandbox(
                    config=SandboxConfig(
                        timeout=60,
                        enable_debugging=True,
                        max_debug_depth=2,
                    ),
                    llm_config=mock_llm_config,
                )

                result = await sandbox.execute(
                    code="print(x)",  # 故意制造错误
                )

                # 应该经过调试后成功
                assert result.status == SandboxStatus.SUCCESS
                assert result.debug_attempts >= 1
                assert len(result.debug_history) >= 1

    @pytest.mark.asyncio
    async def test_sandbox_timeout(self, mock_docker_client, mock_llm_config):
        """测试沙箱超时处理"""
        # 创建一个会一直运行的 Mock 容器
        class SlowContainer(MockContainer):
            def reload(self):
                self._status = "running"  # 永远不退出

        class SlowContainersManager(MockContainersManager):
            def run(self, **kwargs):
                return SlowContainer(self._client)

        mock_docker_client._containers = SlowContainersManager(mock_docker_client)

        with patch('docker.from_env', return_value=mock_docker_client):
            sandbox = DockerSandbox(
                config=SandboxConfig(timeout=1),  # 1 秒超时
                llm_config=mock_llm_config,
            )

            result = await sandbox.execute(
                code="while True: pass",
            )

            assert result.status == SandboxStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_sandbox_health_check(self, mock_docker_client):
        """测试沙箱健康检查"""
        with patch('docker.from_env', return_value=mock_docker_client):
            sandbox = DockerSandbox()
            is_healthy = await sandbox.health_check()
            assert is_healthy is True


# ============================================================================
# VLM 图表审查测试
# ============================================================================

class TestVLMFigureReviewer:
    """VLM 图表审查测试"""

    @pytest.mark.asyncio
    async def test_review_figure(
        self,
        mock_llm_config,
        tmp_path,
    ):
        """测试图表审查"""
        # 创建临时图像文件
        image_path = tmp_path / "test_figure.png"
        image_path.write_bytes(b"fake image data")

        with patch.object(
            ModelClientFactory,
            'create_client',
            return_value=MockLLMClient()
        ):
            reviewer = VLMFigureReviewer(mock_llm_config)

            result = await reviewer.review_figure(
                str(image_path),
                figure_id="test_fig",
            )

            assert result.figure_id == "test_fig"
            assert result.figure_type == FigureType.LINE_CHART
            assert result.verdict == ReviewVerdict.ACCEPT
            assert result.overall_score >= 0

    @pytest.mark.asyncio
    async def test_batch_review(
        self,
        mock_llm_config,
        tmp_path,
    ):
        """测试批量图表审查"""
        # 创建多个临时图像文件
        image_paths = []
        for i in range(3):
            path = tmp_path / f"figure_{i}.png"
            path.write_bytes(b"fake image data")
            image_paths.append(str(path))

        with patch.object(
            ModelClientFactory,
            'create_client',
            return_value=MockLLMClient()
        ):
            reviewer = VLMFigureReviewer(mock_llm_config)

            results = await reviewer.batch_review(image_paths)

            assert len(results) == 3
            for result in results:
                assert isinstance(result, FigureReviewOutput)


# ============================================================================
# 润色与整合测试
# ============================================================================

class TestIntegrationPolishingAgent:
    """润色与整合智能体测试"""

    @pytest.mark.asyncio
    async def test_polish_manuscript(
        self,
        mock_llm_config,
        sample_domain_survey,
    ):
        """测试手稿润色"""
        with patch.object(
            ModelClientFactory,
            'create_client',
            return_value=MockLLMClient()
        ):
            agent = IntegrationPolishingAgent(mock_llm_config)

            result = await agent.polish_manuscript(sample_domain_survey)

            assert result.title is not None
            assert result.abstract is not None
            assert len(result.sections) >= 0
            assert result.coherence_score >= 0

    @pytest.mark.asyncio
    async def test_export_to_markdown(
        self,
        mock_llm_config,
        sample_polished_manuscript,
        tmp_path,
    ):
        """测试导出为 Markdown"""
        with patch.object(
            ModelClientFactory,
            'create_client',
            return_value=MockLLMClient()
        ):
            agent = IntegrationPolishingAgent(mock_llm_config)

            output_path = str(tmp_path / "manuscript.md")
            markdown = await agent.export_to_markdown(
                sample_polished_manuscript,
                output_path,
            )

            assert os.path.exists(output_path)
            assert "# " in markdown
            assert sample_polished_manuscript.title in markdown


# ============================================================================
# 同行评审测试
# ============================================================================

class TestPeerReviewCommittee:
    """同行评审委员会测试"""

    @pytest.mark.asyncio
    async def test_conduct_review(
        self,
        mock_llm_config,
        sample_polished_manuscript,
    ):
        """测试同行评审流程"""
        with patch.object(
            ModelClientFactory,
            'create_client',
            return_value=MockLLMClient()
        ):
            committee = PeerReviewCommittee(
                llm_config=mock_llm_config,
                parallel_review=False,
            )

            report = await committee.conduct_review(
                sample_polished_manuscript,
                manuscript_id="test_manuscript_001",
            )

            assert report.manuscript_id == "test_manuscript_001"
            assert report.novelty_review is not None
            assert report.methodology_review is not None
            assert report.impact_review is not None
            assert report.editor_decision is not None
            assert report.average_score >= 0
            assert report.consensus_level >= 0

            await committee.close()

    @pytest.mark.asyncio
    async def test_parallel_review(
        self,
        mock_llm_config,
        sample_polished_manuscript,
    ):
        """测试并行评审"""
        with patch.object(
            ModelClientFactory,
            'create_client',
            return_value=MockLLMClient()
        ):
            committee = PeerReviewCommittee(
                llm_config=mock_llm_config,
                parallel_review=True,
            )

            report = await committee.conduct_review(sample_polished_manuscript)

            assert report.novelty_review is not None
            assert report.methodology_review is not None
            assert report.impact_review is not None

            await committee.close()


# ============================================================================
# SSE 流式输出测试
# ============================================================================

class TestEventBus:
    """事件总线测试"""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        """测试订阅和发布"""
        # 清空事件总线
        event_bus._subscriptions.clear()
        event_bus._queues.clear()

        # 订阅
        queue = await event_bus.subscribe("session_1")

        # 发布事件
        event = SSEEvent(
            event_type=EventType.AGENT_THOUGHT,
            session_id="session_1",
            data={"thought": "测试思考"},
        )
        await event_bus.publish(event)

        # 获取事件
        received = await event_bus.get_event("session_1", timeout=1.0)

        assert received is not None
        assert received.event_type == EventType.AGENT_THOUGHT
        assert received.data["thought"] == "测试思考"

        # 取消订阅
        await event_bus.unsubscribe("session_1")

    @pytest.mark.asyncio
    async def test_event_type_filter(self):
        """测试事件类型过滤"""
        # 清空事件总线
        event_bus._subscriptions.clear()
        event_bus._queues.clear()

        # 订阅特定事件类型
        queue = await event_bus.subscribe(
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

        await event_bus.publish(thought_event)
        await event_bus.publish(action_event)

        # 只应该收到 thought 事件
        received = await event_bus.get_event("session_2", timeout=1.0)
        assert received.event_type == EventType.AGENT_THOUGHT

        # 不应该有更多事件
        received = await event_bus.get_event("session_2", timeout=0.5)
        assert received is None

        await event_bus.unsubscribe("session_2")

    @pytest.mark.asyncio
    async def test_event_history(self):
        """测试事件历史"""
        # 发布多个事件
        for i in range(5):
            event = SSEEvent(
                event_type=EventType.HEARTBEAT,
                session_id="test",
                data={"count": i},
            )
            await event_bus.publish(event)

        # 获取历史
        history = event_bus.get_history(limit=3)

        assert len(history) == 3
        # 应该是最新的 3 个事件
        assert history[0].data["count"] == 2
        assert history[1].data["count"] == 3
        assert history[2].data["count"] == 4


# ============================================================================
# 完整工作流集成测试
# ============================================================================

class TestEndToEndWorkflow:
    """端到端工作流集成测试"""

    @pytest.mark.asyncio
    async def test_complete_workflow(
        self,
        mock_llm_config,
        sample_domain_survey,
        tmp_path,
    ):
        """
        测试完整工作流：
        1. 沙箱执行实验代码
        2. VLM 审查生成的图表
        3. 润色整合手稿
        4. 同行评审
        5. SSE 事件流
        """
        # 清空事件总线
        event_bus._subscriptions.clear()
        event_bus._queues.clear()

        # 1. 沙箱执行
        mock_docker = MockDockerClient()
        with patch('docker.from_env', return_value=mock_docker):
            sandbox = DockerSandbox(
                config=SandboxConfig(timeout=60),
                llm_config=mock_llm_config,
            )

            execution_result = await sandbox.execute(
                code="""
import matplotlib.pyplot as plt
plt.plot([1, 2, 3], [1, 4, 9])
plt.savefig('result.png')
print("Experiment completed")
""",
            )

            assert execution_result.status == SandboxStatus.SUCCESS

        # 2. VLM 图表审查
        with patch.object(
            ModelClientFactory,
            'create_client',
            return_value=MockLLMClient()
        ):
            # 创建模拟图表文件
            figure_path = tmp_path / "result.png"
            figure_path.write_bytes(b"fake chart data")

            reviewer = VLMFigureReviewer(mock_llm_config)
            figure_review = await reviewer.review_figure(str(figure_path))

            assert figure_review.verdict in [
                ReviewVerdict.ACCEPT,
                ReviewVerdict.MINOR_REVISION,
                ReviewVerdict.MAJOR_REVISION,
            ]

        # 3. 润色整合
        with patch.object(
            ModelClientFactory,
            'create_client',
            return_value=MockLLMClient()
        ):
            polishing_agent = IntegrationPolishingAgent(mock_llm_config)
            polished_manuscript = await polishing_agent.polish_manuscript(
                sample_domain_survey,
                figure_reviews=[figure_review],
            )

            assert polished_manuscript.title is not None
            assert polished_manuscript.coherence_score >= 0

        # 4. 同行评审
        with patch.object(
            ModelClientFactory,
            'create_client',
            return_value=MockLLMClient()
        ):
            committee = PeerReviewCommittee(mock_llm_config)
            review_report = await committee.conduct_review(
                polished_manuscript,
                figure_reviews=[figure_review],
            )

            assert review_report.editor_decision is not None
            assert review_report.average_score >= 0

            await committee.close()

        # 5. SSE 事件流验证
        # 订阅事件
        queue = await event_bus.subscribe("e2e_test_session")

        # 发布工作流完成事件
        complete_event = SSEEvent(
            event_type=EventType.WORKFLOW_COMPLETE,
            session_id="e2e_test_session",
            data={
                "manuscript_id": review_report.manuscript_id,
                "decision": review_report.editor_decision.value,
            },
        )
        await event_bus.publish(complete_event)

        # 验证事件接收
        received = await event_bus.get_event("e2e_test_session", timeout=1.0)
        assert received.event_type == EventType.WORKFLOW_COMPLETE
        assert received.data["manuscript_id"] == review_report.manuscript_id

        await event_bus.unsubscribe("e2e_test_session")

    @pytest.mark.asyncio
    async def test_workflow_with_hitl(
        self,
        mock_llm_config,
        sample_domain_survey,
    ):
        """测试带 HITL 的工作流"""
        # 清空事件总线
        event_bus._subscriptions.clear()
        event_bus._queues.clear()

        # 订阅事件
        queue = await event_bus.subscribe("hitl_test_session")

        # 模拟 HITL 中断
        interrupt_event = SSEEvent(
            event_type=EventType.HITL_INTERRUPT,
            session_id="hitl_test_session",
            priority=EventPriority.HIGH,
            data={
                "reason": "methodology_approval",
                "context": {"stage": "methodology_design"},
            },
        )
        await event_bus.publish(interrupt_event)

        # 验证中断事件
        received = await event_bus.get_event("hitl_test_session", timeout=1.0)
        assert received.event_type == EventType.HITL_INTERRUPT

        # 模拟人工反馈
        feedback_event = SSEEvent(
            event_type=EventType.HITL_FEEDBACK,
            session_id="hitl_test_session",
            data={
                "feedback": "方法论设计合理，继续执行",
                "approved": True,
            },
        )
        await event_bus.publish(feedback_event)

        # 验证反馈事件
        received = await event_bus.get_event("hitl_test_session", timeout=1.0)
        assert received.event_type == EventType.HITL_FEEDBACK
        assert received.data["approved"] is True

        await event_bus.unsubscribe("hitl_test_session")


# ============================================================================
# 性能测试
# ============================================================================

class TestPerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_concurrent_sandbox_executions(self, mock_llm_config):
        """测试并发沙箱执行"""
        mock_docker = MockDockerClient()

        with patch('docker.from_env', return_value=mock_docker):
            sandbox = DockerSandbox(
                config=SandboxConfig(timeout=60),
                llm_config=mock_llm_config,
            )

            # 并发执行 10 个任务
            tasks = [
                sandbox.execute(code=f"print('Task {i}')")
                for i in range(10)
            ]

            results = await asyncio.gather(*tasks)

            assert len(results) == 10
            for result in results:
                assert result.status == SandboxStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_event_bus_throughput(self):
        """测试事件总线吞吐量"""
        # 清空事件总线
        event_bus._subscriptions.clear()
        event_bus._queues.clear()

        # 订阅
        queue = await event_bus.subscribe("throughput_test")

        # 发布大量事件
        num_events = 100
        start_time = datetime.now()

        for i in range(num_events):
            event = SSEEvent(
                event_type=EventType.HEARTBEAT,
                session_id="throughput_test",
                data={"index": i},
            )
            await event_bus.publish(event)

        publish_duration = (datetime.now() - start_time).total_seconds()

        # 验证所有事件都能接收
        received_count = 0
        for _ in range(num_events):
            event = await event_bus.get_event("throughput_test", timeout=1.0)
            if event:
                received_count += 1

        assert received_count == num_events

        await event_bus.unsubscribe("throughput_test")

        # 打印性能指标
        print(f"\n事件发布吞吐量: {num_events / publish_duration:.2f} events/s")


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
