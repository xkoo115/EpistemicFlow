"""
集成测试：EpistemicFlow 完整工作流

测试 agents/epistemic_workflow.py 中的端到端工作流执行。
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncIterator

from agent_framework import (
    WorkflowEvent,
    WorkflowRunState,
    State,
)

from agents.epistemic_workflow import (
    EpistemicWorkflow,
    EpistemicWorkflowInput,
    EpistemicWorkflowOutput,
    EpistemicStage,
    run_epistemic_workflow,
    resume_epistemic_workflow,
)
from agents.polishing_and_review import (
    Manuscript,
    ConsolidatedReview,
    ReviewVerdict,
)


class TestEpistemicWorkflow:
    """EpistemicFlow 工作流集成测试"""
    
    @pytest.fixture
    def mock_llm_config(self):
        """Mock LLM 配置"""
        return MagicMock(
            model_name="test-model",
            api_key="test-key",
            base_url="https://test.api",
            temperature=0.7,
        )
    
    @pytest.fixture
    def workflow_input(self):
        """工作流输入"""
        return EpistemicWorkflowInput(
            research_idea="研究深度学习在药物发现中的应用",
            target_journal="Nature",
        )
    
    @pytest.mark.asyncio
    async def test_workflow_initialization(self, mock_llm_config):
        """测试工作流初始化"""
        workflow = EpistemicWorkflow(llm_config=mock_llm_config)
        
        assert workflow._llm_config == mock_llm_config
        assert workflow._workflow is not None
        assert workflow._saga_manager is not None
    
    @pytest.mark.asyncio
    async def test_workflow_run_basic(self, mock_llm_config, workflow_input):
        """测试基本工作流执行"""
        workflow = EpistemicWorkflow(llm_config=mock_llm_config)
        
        # Mock 工作流执行
        with patch.object(
            workflow._workflow,
            'run',
            new_callable=AsyncMock,
        ) as mock_run:
            # 设置 mock 返回值
            mock_result = MagicMock()
            mock_result.get_output.return_value = {
                "research_type": "research_paper",
            }
            mock_result.metadata = {"checkpoint_id": "cp_001"}
            mock_run.return_value = mock_result
            
            # 执行
            output = await workflow.run(workflow_input)
            
            # 验证
            assert output.research_idea == workflow_input.research_idea
            assert output.research_type == "research_paper"
            mock_run.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_workflow_run_stream(self, mock_llm_config, workflow_input):
        """测试流式工作流执行"""
        workflow = EpistemicWorkflow(llm_config=mock_llm_config)
        
        # 创建 mock 事件流
        async def mock_event_stream():
            yield WorkflowEvent.started()
            yield WorkflowEvent.status(WorkflowRunState.IN_PROGRESS)
            yield WorkflowEvent.executor_invoked("ideation")
            yield WorkflowEvent.executor_completed("ideation")
            yield WorkflowEvent.output("final", {"result": "success"})
        
        # Mock 工作流执行
        with patch.object(
            workflow._workflow,
            'run',
            return_value=mock_event_stream(),
        ):
            # 收集事件
            events = []
            async for event in workflow.run_stream(workflow_input):
                events.append(event)
            
            # 验证
            assert len(events) == 5
            assert events[0].type == "started"
            assert events[1].type == "status"
            assert events[2].type == "executor_invoked"
            assert events[3].type == "executor_completed"
            assert events[4].type == "output"
    
    @pytest.mark.asyncio
    async def test_workflow_fork_from_checkpoint(self, mock_llm_config):
        """测试从检查点 Fork"""
        workflow = EpistemicWorkflow(llm_config=mock_llm_config)
        
        # Mock Saga 管理器
        with patch.object(
            workflow._saga_manager,
            'fork_from_checkpoint',
            new_callable=AsyncMock,
        ) as mock_fork:
            mock_fork.return_value = MagicMock(checkpoint_id="cp_forked")
            
            # Fork
            new_checkpoint_id = await workflow.fork_from_checkpoint(
                checkpoint_id="cp_original",
                new_session_id="fork_session",
                human_feedback={"comment": "请修改"},
            )
            
            # 验证
            assert new_checkpoint_id == "cp_forked"
            mock_fork.assert_called_once_with(
                checkpoint_id="cp_original",
                new_session_id="fork_session",
                human_feedback={"comment": "请修改"},
            )


class TestWorkflowStages:
    """工作流阶段测试"""
    
    @pytest.mark.asyncio
    async def test_ideation_stage(self):
        """测试构思阶段"""
        from agents.epistemic_workflow import IdeationExecutor
        
        executor = IdeationExecutor(id="test_ideation")
        
        # Mock Agent
        with patch.object(
            executor,
            '_get_agent',
        ) as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=MagicMock(
                text='{"research_type": "research_paper", "research_questions": ["Q1"]}'
            ))
            mock_get_agent.return_value = mock_agent
            
            # Mock 上下文
            ctx = MagicMock()
            ctx.set_state = MagicMock()
            ctx.send_message = AsyncMock()
            
            # 执行
            input_data = EpistemicWorkflowInput(
                research_idea="测试想法",
            )
            await executor.ideate(input_data, ctx)
            
            # 验证
            ctx.set_state.assert_called()
            ctx.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_methodology_design_stage(self):
        """测试方法论设计阶段"""
        from agents.epistemic_workflow import MethodologyDesignExecutor
        
        executor = MethodologyDesignExecutor(id="test_methodology")
        
        # Mock Agent
        with patch.object(
            executor,
            '_get_agent',
        ) as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=MagicMock(
                text='{"methodology": "实验设计"}'
            ))
            mock_get_agent.return_value = mock_agent
            
            # Mock 上下文
            ctx = MagicMock()
            ctx.set_state = MagicMock()
            ctx.send_message = AsyncMock()
            
            # 执行
            literature_result = {
                "research_topic": "测试主题",
                "key_findings": ["发现1"],
            }
            await executor.design(literature_result, ctx)
            
            # 验证
            ctx.send_message.assert_called_once()


class TestPolishingAndReview:
    """润色和评审测试"""
    
    @pytest.mark.asyncio
    async def test_polishing_agent(self):
        """测试润色智能体"""
        from agents.polishing_and_review import PolishingAgent
        
        agent = PolishingAgent()
        
        # Mock Agent
        with patch.object(
            agent,
            '_get_agent',
        ) as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=MagicMock(
                text="\\documentclass{article}\\begin{document}Test\\end{document}"
            ))
            mock_get_agent.return_value = mock_agent
            
            # 执行润色
            manuscript = await agent.polish(
                research_results={"methodology": "test"},
                figures=[],
                tables=[],
            )
            
            # 验证
            assert manuscript is not None
            assert manuscript.latex_source != ""
    
    @pytest.mark.asyncio
    async def test_peer_review_board(self):
        """测试评审委员会"""
        from agents.polishing_and_review import (
            PeerReviewBoardBuilder,
            NoveltyReviewer,
        )
        
        builder = PeerReviewBoardBuilder()
        workflow = builder.build()
        
        # 验证工作流构建
        assert workflow is not None


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    @pytest.mark.asyncio
    async def test_run_epistemic_workflow(self):
        """测试便捷运行函数"""
        # Mock EpistemicWorkflow
        with patch(
            "agents.epistemic_workflow.EpistemicWorkflow",
        ) as mock_workflow_class:
            mock_workflow = MagicMock()
            mock_workflow.run_stream = MagicMock()
            
            # 创建 mock 事件流
            async def mock_stream():
                yield WorkflowEvent.output("final", EpistemicWorkflowOutput(
                    research_idea="test",
                    research_type="research_paper",
                ))
            
            mock_workflow.run_stream.return_value = mock_stream()
            mock_workflow_class.return_value = mock_workflow
            
            # 执行
            result = await run_epistemic_workflow(
                research_idea="测试想法",
                stream=True,
            )
            
            # 验证
            assert result is not None


class TestEventStreamIntegration:
    """事件流集成测试"""
    
    @pytest.mark.asyncio
    async def test_sse_stream_generation(self):
        """测试 SSE 流生成"""
        from agents.event_stream_native import (
            SSEStreamGenerator,
            SSEEventType,
        )
        
        generator = SSEStreamGenerator(heartbeat_interval=5.0)
        
        # 创建 mock 事件流
        async def mock_event_stream():
            yield WorkflowEvent.started()
            yield WorkflowEvent.executor_invoked("test_executor")
            yield WorkflowEvent.output("test_executor", {"result": "success"})
        
        # 生成 SSE 流
        sse_events = []
        async for sse_str in generator.generate(mock_event_stream(), "test_session"):
            sse_events.append(sse_str)
        
        # 验证
        assert len(sse_events) >= 3  # 至少 3 个事件 + 可能的心跳
        
        # 验证 SSE 格式
        for event in sse_events:
            assert "event:" in event
            assert "data:" in event


class TestSagaIntegration:
    """Saga 集成测试"""
    
    @pytest.mark.asyncio
    async def test_checkpoint_persistence(self):
        """测试检查点持久化"""
        from agents.saga_integration import SagaStateManager
        
        manager = SagaStateManager(storage_path=None)  # 使用内存存储
        
        # 创建检查点
        state = State()
        state.set("test_key", "test_value")
        
        checkpoint1 = await manager.create_checkpoint(
            workflow_name="test_workflow",
            state=state,
            messages={},
            pending_requests={},
        )
        
        # 恢复检查点
        checkpoint2 = await manager.restore_checkpoint(checkpoint1.checkpoint_id)
        
        # 验证
        assert checkpoint1.checkpoint_id == checkpoint2.checkpoint_id
        assert checkpoint2.state.get("test_key") == "test_value"
    
    @pytest.mark.asyncio
    async def test_hitl_interrupt_and_resume(self):
        """测试 HITL 中断和恢复"""
        from agents.saga_integration import SagaStateManager, HITLManager
        
        saga_manager = SagaStateManager()
        hitl_manager = HITLManager(saga_manager)
        
        # 创建中断
        event = MagicMock()
        event.request_id = "req_test"
        event.source_executor_id = "executor_test"
        event.request_type = MagicMock(__name__="HumanInput")
        event.data = {"prompt": "请确认"}
        event.response_type = MagicMock(__name__="UserResponse")
        
        interrupt = await hitl_manager.create_interrupt(event)
        
        # 验证中断创建
        assert interrupt.request_id == "req_test"
        
        # 获取待处理中断
        pending = await hitl_manager.get_pending_interrupts("session")
        assert len(pending) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
