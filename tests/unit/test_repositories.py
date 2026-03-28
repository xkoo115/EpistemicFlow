"""
数据库仓库测试
测试数据库仓库的功能
"""

from datetime import datetime, timedelta
from typing import Dict, Any
import pytest

from models.workflow_state import WorkflowState, WorkflowStage, WorkflowStatus
from database.repositories.workflow_state_repository import WorkflowStateRepository


class TestWorkflowStateRepository:
    """工作流状态仓库测试"""

    @pytest.mark.asyncio
    async def test_create_workflow_state(
        self,
        db_session,
        sample_workflow_data: Dict[str, Any],
    ):
        """测试创建工作流状态"""
        repository = WorkflowStateRepository(db_session)

        # 创建工作流状态
        workflow_state = await repository.create(
            session_id=sample_workflow_data["session_id"],
            workflow_name=sample_workflow_data["workflow_name"],
            current_stage=WorkflowStage(sample_workflow_data["current_stage"]),
            status=WorkflowStatus(sample_workflow_data["status"]),
            agent_state=sample_workflow_data["agent_state"],
            metadata=sample_workflow_data["metadata"],
        )

        # 验证创建成功
        assert workflow_state.id is not None
        assert workflow_state.session_id == sample_workflow_data["session_id"]
        assert workflow_state.workflow_name == sample_workflow_data["workflow_name"]
        assert workflow_state.current_stage == sample_workflow_data["current_stage"]
        assert workflow_state.status == sample_workflow_data["status"]
        assert workflow_state.agent_state == sample_workflow_data["agent_state"]
        assert workflow_state.metadata_json == sample_workflow_data["metadata"]
        assert workflow_state.created_at is not None
        assert workflow_state.updated_at is not None

    @pytest.mark.asyncio
    async def test_get_by_id(
        self,
        db_session,
        sample_workflow_data: Dict[str, Any],
    ):
        """测试根据ID获取工作流状态"""
        repository = WorkflowStateRepository(db_session)

        # 先创建记录
        created_state = await repository.create(
            session_id=sample_workflow_data["session_id"],
            workflow_name=sample_workflow_data["workflow_name"],
            current_stage=WorkflowStage(sample_workflow_data["current_stage"]),
            status=WorkflowStatus(sample_workflow_data["status"]),
        )

        # 根据ID获取
        retrieved_state = await repository.get_by_id(created_state.id)

        # 验证获取成功
        assert retrieved_state is not None
        assert retrieved_state.id == created_state.id
        assert retrieved_state.session_id == created_state.session_id

        # 测试获取不存在的ID
        non_existent = await repository.get_by_id(99999)
        assert non_existent is None

    @pytest.mark.asyncio
    async def test_get_by_session_id(
        self,
        db_session,
    ):
        """测试根据会话ID获取工作流状态列表"""
        repository = WorkflowStateRepository(db_session)
        session_id = "test-session-multiple"

        # 创建多个记录
        for i in range(5):
            await repository.create(
                session_id=session_id,
                workflow_name=f"workflow-{i}",
                current_stage=WorkflowStage.CONCEPTION,
                status=WorkflowStatus.PENDING,
            )

        # 获取记录
        states = await repository.get_by_session_id(session_id)

        # 验证获取成功
        assert len(states) == 5
        for state in states:
            assert state.session_id == session_id

        # 测试限制和偏移
        limited_states = await repository.get_by_session_id(
            session_id, limit=2, offset=1
        )
        assert len(limited_states) == 2

    @pytest.mark.asyncio
    async def test_get_latest_by_session_and_stage(
        self,
        db_session,
    ):
        """测试获取指定会话和阶段的最新工作流状态"""
        repository = WorkflowStateRepository(db_session)
        session_id = "test-session-latest"

        # 创建多个阶段的记录
        stages = [
            WorkflowStage.CONCEPTION,
            WorkflowStage.LITERATURE_REVIEW,
            WorkflowStage.CONCEPTION,  # 再次创建构思阶段
        ]

        created_states = []
        for stage in stages:
            state = await repository.create(
                session_id=session_id,
                workflow_name="test-workflow",
                current_stage=stage,
                status=WorkflowStatus.PENDING,
            )
            created_states.append(state)

        # 获取最新构思阶段记录
        latest_conception = await repository.get_latest_by_session_and_stage(
            session_id,
            WorkflowStage.CONCEPTION,
        )

        # 验证获取的是最新的构思阶段记录
        assert latest_conception is not None
        assert latest_conception.id == created_states[-1].id  # 最后一个记录
        assert latest_conception.current_stage == WorkflowStage.CONCEPTION

        # 测试获取不存在的阶段
        non_existent = await repository.get_latest_by_session_and_stage(
            session_id,
            WorkflowStage.ANALYSIS,
        )
        assert non_existent is None

    @pytest.mark.asyncio
    async def test_update_status(
        self,
        db_session,
        sample_workflow_data: Dict[str, Any],
    ):
        """测试更新工作流状态"""
        repository = WorkflowStateRepository(db_session)

        # 创建记录
        created_state = await repository.create(
            session_id=sample_workflow_data["session_id"],
            workflow_name=sample_workflow_data["workflow_name"],
            current_stage=WorkflowStage(sample_workflow_data["current_stage"]),
            status=WorkflowStatus(sample_workflow_data["status"]),
        )

        # 更新状态
        updated_state = await repository.update_status(
            created_state.id,
            WorkflowStatus.COMPLETED,
            error_message="Test error",
        )

        # 验证更新成功
        assert updated_state is not None
        assert updated_state.status == WorkflowStatus.COMPLETED
        assert updated_state.error_message == "Test error"
        assert updated_state.updated_at is not None

        # 测试更新不存在的记录
        non_existent = await repository.update_status(99999, WorkflowStatus.FAILED)
        assert non_existent is None

    @pytest.mark.asyncio
    async def test_update_agent_state(
        self,
        db_session,
        sample_workflow_data: Dict[str, Any],
    ):
        """测试更新智能体状态"""
        repository = WorkflowStateRepository(db_session)

        # 创建记录
        created_state = await repository.create(
            session_id=sample_workflow_data["session_id"],
            workflow_name=sample_workflow_data["workflow_name"],
            current_stage=WorkflowStage(sample_workflow_data["current_stage"]),
            status=WorkflowStatus(sample_workflow_data["status"]),
            agent_state={"initial": "state"},
        )

        # 合并更新
        updated_state = await repository.update_agent_state(
            created_state.id,
            {"new_key": "new_value", "progress": 0.8},
            merge=True,
        )

        # 验证合并成功
        assert updated_state is not None
        assert updated_state.agent_state == {
            "initial": "state",
            "new_key": "new_value",
            "progress": 0.8,
        }

        # 替换更新
        replaced_state = await repository.update_agent_state(
            created_state.id,
            {"replaced": "state"},
            merge=False,
        )

        # 验证替换成功
        assert replaced_state is not None
        assert replaced_state.agent_state == {"replaced": "state"}

        # 测试更新不存在的记录
        non_existent = await repository.update_agent_state(99999, {"test": "data"})
        assert non_existent is None

    @pytest.mark.asyncio
    async def test_add_human_feedback(
        self,
        db_session,
        sample_workflow_data: Dict[str, Any],
    ):
        """测试添加人工反馈"""
        repository = WorkflowStateRepository(db_session)

        # 创建记录
        created_state = await repository.create(
            session_id=sample_workflow_data["session_id"],
            workflow_name=sample_workflow_data["workflow_name"],
            current_stage=WorkflowStage(sample_workflow_data["current_stage"]),
            status=WorkflowStatus(sample_workflow_data["status"]),
        )

        # 添加第一次反馈
        updated_state = await repository.add_human_feedback(
            created_state.id,
            "First feedback",
        )

        # 验证添加成功
        assert updated_state is not None
        assert updated_state.human_feedback == "First feedback"

        # 添加第二次反馈（追加）
        updated_state = await repository.add_human_feedback(
            created_state.id,
            "Second feedback",
        )

        # 验证追加成功
        assert updated_state is not None
        assert "First feedback" in updated_state.human_feedback
        assert "Second feedback" in updated_state.human_feedback

        # 测试添加反馈到不存在的记录
        non_existent = await repository.add_human_feedback(99999, "Test feedback")
        assert non_existent is None

    @pytest.mark.asyncio
    async def test_delete_by_id(
        self,
        db_session,
        sample_workflow_data: Dict[str, Any],
    ):
        """测试根据ID删除工作流状态"""
        repository = WorkflowStateRepository(db_session)

        # 创建记录
        created_state = await repository.create(
            session_id=sample_workflow_data["session_id"],
            workflow_name=sample_workflow_data["workflow_name"],
            current_stage=WorkflowStage(sample_workflow_data["current_stage"]),
            status=WorkflowStatus(sample_workflow_data["status"]),
        )

        # 确认记录存在
        existing_state = await repository.get_by_id(created_state.id)
        assert existing_state is not None

        # 删除记录
        deleted = await repository.delete_by_id(created_state.id)

        # 验证删除成功
        assert deleted is True

        # 确认记录已删除
        deleted_state = await repository.get_by_id(created_state.id)
        assert deleted_state is None

        # 测试删除不存在的记录
        non_existent_deleted = await repository.delete_by_id(99999)
        assert non_existent_deleted is False

    @pytest.mark.asyncio
    async def test_cleanup_old_states(
        self,
        db_session,
    ):
        """测试清理旧的工作流状态记录"""
        repository = WorkflowStateRepository(db_session)

        # 创建一些记录
        for i in range(10):
            await repository.create(
                session_id=f"session-{i}",
                workflow_name="test-workflow",
                current_stage=WorkflowStage.CONCEPTION,
                status=WorkflowStatus.COMPLETED,
            )

        # 清理（实际上不会删除，因为记录是新的）
        deleted_count = await repository.cleanup_old_states(days=1)

        # 验证没有记录被删除
        assert deleted_count == 0

        # 测试按状态清理
        deleted_count = await repository.cleanup_old_states(
            days=0,  # 立即清理
            statuses=[WorkflowStatus.COMPLETED],
        )

        # 验证所有完成状态的记录被删除
        assert deleted_count == 10

    @pytest.mark.asyncio
    async def test_get_statistics(
        self,
        db_session,
    ):
        """测试获取工作流统计信息"""
        repository = WorkflowStateRepository(db_session)

        # 创建测试数据
        test_data = [
            # session_id, workflow_name, stage, status
            ("s1", "workflow-a", WorkflowStage.CONCEPTION, WorkflowStatus.PENDING),
            (
                "s1",
                "workflow-a",
                WorkflowStage.LITERATURE_REVIEW,
                WorkflowStatus.RUNNING,
            ),
            ("s2", "workflow-a", WorkflowStage.CONCEPTION, WorkflowStatus.COMPLETED),
            ("s3", "workflow-b", WorkflowStage.ANALYSIS, WorkflowStatus.FAILED),
            ("s4", "workflow-b", WorkflowStage.WRITING, WorkflowStatus.COMPLETED),
        ]

        for session_id, workflow_name, stage, status in test_data:
            await repository.create(
                session_id=session_id,
                workflow_name=workflow_name,
                current_stage=stage,
                status=status,
            )

        # 获取总体统计
        stats = await repository.get_statistics()

        # 验证统计信息
        assert stats["total"] == 5
        assert stats["status_stats"]["pending"] == 1
        assert stats["status_stats"]["running"] == 1
        assert stats["status_stats"]["completed"] == 2
        assert stats["status_stats"]["failed"] == 1
        assert stats["stage_stats"]["conception"] == 2
        assert stats["stage_stats"]["literature_review"] == 1
        assert stats["stage_stats"]["analysis"] == 1
        assert stats["stage_stats"]["writing"] == 1

        # 获取特定工作流统计
        workflow_a_stats = await repository.get_statistics(workflow_name="workflow-a")
        assert workflow_a_stats["total"] == 3

        # 获取日期范围统计
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=1)
        date_stats = await repository.get_statistics(
            start_date=start_date, end_date=end_date
        )
        assert date_stats["total"] == 5
