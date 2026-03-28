"""
数据库模型测试
测试数据库模型的功能
"""

from datetime import datetime
from typing import Dict, Any
import pytest

from models.base import BaseModel
from models.workflow_state import WorkflowState, WorkflowStage, WorkflowStatus


class TestBaseModel:
    """基础模型测试"""

    def test_base_model_to_dict(self):
        """测试模型转字典"""

        # 创建测试模型实例
        class TestModel(BaseModel):
            __tablename__ = "test_model"

            id: int = 1
            name: str = "test"
            value: int = 100

            def __init__(self):
                # 设置实例属性
                self.id = 1
                self.name = "test"
                self.value = 100
                # 模拟SQLAlchemy列
                self.__table__ = type("Table", (), {"columns": []})()
                self.__table__.columns = [
                    type("Column", (), {"name": "id"})(),
                    type("Column", (), {"name": "name"})(),
                    type("Column", (), {"name": "value"})(),
                ]

        model = TestModel()

        # 测试基本转换
        result = model.to_dict()
        assert result == {"id": 1, "name": "test", "value": 100}

        # 测试排除字段
        result = model.to_dict(exclude=["value"])
        assert "value" not in result
        assert result == {"id": 1, "name": "test"}

    def test_base_model_update_from_dict(self):
        """测试从字典更新模型"""

        # 创建测试模型实例
        class TestModel(BaseModel):
            __tablename__ = "test_model"

            def __init__(self):
                self.id = 1
                self.name = "old"
                self.value = 0
                self.__table__ = type("Table", (), {"columns": []})()

        model = TestModel()

        # 更新模型
        update_data = {"name": "new", "value": 200}
        model.update_from_dict(update_data)

        assert model.name == "new"
        assert model.value == 200
        assert model.id == 1  # 未更新的字段保持不变


class TestWorkflowStateModel:
    """工作流状态模型测试"""

    def test_workflow_state_creation(self):
        """测试工作流状态创建"""
        workflow_state = WorkflowState(
            session_id="test-session-123",
            workflow_name="test-workflow",
            current_stage=WorkflowStage.CONCEPTION,
            status=WorkflowStatus.PENDING,
        )

        assert workflow_state.session_id == "test-session-123"
        assert workflow_state.workflow_name == "test-workflow"
        assert workflow_state.current_stage == WorkflowStage.CONCEPTION
        assert workflow_state.status == WorkflowStatus.PENDING
        assert workflow_state.agent_state_json is None
        assert workflow_state.human_feedback is None
        assert workflow_state.error_message is None
        assert workflow_state.metadata_json is None

    def test_workflow_state_agent_state_property(self):
        """测试智能体状态属性"""
        workflow_state = WorkflowState(
            session_id="test",
            workflow_name="test",
            current_stage=WorkflowStage.CONCEPTION,
            status=WorkflowStatus.PENDING,
        )

        # 初始为None
        assert workflow_state.agent_state is None

        # 设置状态
        test_state = {"key": "value", "progress": 0.5}
        workflow_state.agent_state = test_state

        # 验证设置成功
        assert workflow_state.agent_state == test_state
        assert workflow_state.agent_state_json == test_state

    def test_workflow_state_metadata_property(self):
        """测试元数据属性"""
        workflow_state = WorkflowState(
            session_id="test",
            workflow_name="test",
            current_stage=WorkflowStage.CONCEPTION,
            status=WorkflowStatus.PENDING,
        )

        # 初始为None
        assert workflow_state.metadata_json is None

        # 设置元数据
        test_metadata = {"creator": "user", "priority": "high"}
        workflow_state.metadata_json = test_metadata

        # 验证设置成功
        assert workflow_state.metadata_json == test_metadata

    def test_workflow_state_add_agent_state(self):
        """测试添加智能体状态"""
        workflow_state = WorkflowState(
            session_id="test",
            workflow_name="test",
            current_stage=WorkflowStage.CONCEPTION,
            status=WorkflowStatus.PENDING,
        )

        # 添加状态项
        workflow_state.add_agent_state("key1", "value1")
        workflow_state.add_agent_state("key2", 100)

        # 验证添加成功
        assert workflow_state.agent_state == {"key1": "value1", "key2": 100}

        # 测试获取状态项
        assert workflow_state.get_agent_state("key1") == "value1"
        assert workflow_state.get_agent_state("key2") == 100
        assert workflow_state.get_agent_state("key3") is None
        assert workflow_state.get_agent_state("key3", "default") == "default"

    def test_workflow_state_add_metadata(self):
        """测试添加元数据"""
        workflow_state = WorkflowState(
            session_id="test",
            workflow_name="test",
            current_stage=WorkflowStage.CONCEPTION,
            status=WorkflowStatus.PENDING,
        )

        # 添加元数据项
        workflow_state.add_metadata("creator", "test-user")
        workflow_state.add_metadata("tags", ["ai", "research"])

        # 验证添加成功
        assert workflow_state.metadata_json == {
            "creator": "test-user",
            "tags": ["ai", "research"],
        }

        # 测试获取元数据项
        assert workflow_state.get_metadata("creator") == "test-user"
        assert workflow_state.get_metadata("tags") == ["ai", "research"]
        assert workflow_state.get_metadata("non-existent") is None
        assert workflow_state.get_metadata("non-existent", []) == []

    def test_workflow_state_to_summary_dict(self):
        """测试转换为摘要字典"""
        workflow_state = WorkflowState(
            id=1,
            session_id="test-session-123",
            workflow_name="test-workflow",
            current_stage=WorkflowStage.CONCEPTION,
            status=WorkflowStatus.RUNNING,
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            updated_at=datetime(2024, 1, 1, 12, 30, 0),
            agent_state_json={"progress": 0.5},
            human_feedback="Good work!",
            error_message="Some error",
        )

        summary = workflow_state.to_summary_dict()

        assert summary["id"] == 1
        assert summary["session_id"] == "test-session-123"
        assert summary["workflow_name"] == "test-workflow"
        assert summary["current_stage"] == WorkflowStage.CONCEPTION
        assert summary["status"] == WorkflowStatus.RUNNING
        assert summary["created_at"] == "2024-01-01T12:00:00"
        assert summary["updated_at"] == "2024-01-01T12:30:00"
        assert summary["has_agent_state"] is True
        assert summary["has_human_feedback"] is True
        assert summary["has_error"] is True

    def test_workflow_state_repr(self):
        """测试字符串表示"""
        workflow_state = WorkflowState(
            id=42,
            session_id="session-123",
            workflow_name="research-workflow",
            current_stage=WorkflowStage.ANALYSIS,
            status=WorkflowStatus.COMPLETED,
        )

        repr_str = repr(workflow_state)

        assert "WorkflowState" in repr_str
        assert "id=42" in repr_str
        assert "session_id=session-123" in repr_str
        assert "workflow_name=research-workflow" in repr_str
        assert "stage=analysis" in repr_str
        assert "status=completed" in repr_str


class TestWorkflowEnums:
    """工作流枚举测试"""

    def test_workflow_stage_enum(self):
        """测试工作流阶段枚举"""
        assert WorkflowStage.INITIALIZATION == "initialization"
        assert WorkflowStage.CONCEPTION == "conception"
        assert WorkflowStage.LITERATURE_REVIEW == "literature_review"
        assert WorkflowStage.METHODOLOGY_DESIGN == "methodology_design"
        assert WorkflowStage.DATA_COLLECTION == "data_collection"
        assert WorkflowStage.ANALYSIS == "analysis"
        assert WorkflowStage.WRITING == "writing"
        assert WorkflowStage.REVIEW == "review"
        assert WorkflowStage.COMPLETION == "completion"
        assert WorkflowStage.ERROR == "error"

        # 测试枚举值
        stages = list(WorkflowStage)
        assert len(stages) == 10
        assert "conception" in [stage.value for stage in stages]

    def test_workflow_status_enum(self):
        """测试工作流状态枚举"""
        assert WorkflowStatus.PENDING == "pending"
        assert WorkflowStatus.RUNNING == "running"
        assert WorkflowStatus.PAUSED == "paused"
        assert WorkflowStatus.COMPLETED == "completed"
        assert WorkflowStatus.FAILED == "failed"
        assert WorkflowStatus.CANCELLED == "cancelled"

        # 测试枚举值
        statuses = list(WorkflowStatus)
        assert len(statuses) == 6
        assert "running" in [status.value for status in statuses]
